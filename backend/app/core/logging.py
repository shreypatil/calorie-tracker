"""Structured logging: a durable JSON file, a readable console, and one request ID on every line.

This module exists in its current shape because of a specific failure. A chat request produced a
user-visible error, and afterwards there was nothing to look at: logs went only to stdout, so they
died with the terminal, and the error itself was one the application *handled*, so nothing had
written it down at all. Diagnosing it needed a database query.

Three ideas fix that class of problem:

**Everything is written twice, to two audiences.** The file gets JSON so it can be grepped, filtered
by request ID and piped through `jq`; the console gets an aligned line a human can skim. Both go
through the same scrub step, so what is redacted can never differ between them.

**Redaction and truncation happen here, not at call sites.** Once logs are written to disk, a single
careless `extra={"body": ...}` on the login route writes plaintext passwords to a file, and one
photo upload writes a megabyte of base64. Enforcing it in the formatter means no call site can get
it wrong.

**`operation()` covers the risky boundaries.** "Log before every point of failure" is unachievable
by hand — the lines drift out of sync with the code within weeks. One context manager per risky
boundary yields the start, the outcome and the failure together, and they cannot disagree.
"""

import json
import logging
import logging.handlers
import sys
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from enum import StrEnum
from pathlib import Path
from typing import Any

_request_id: ContextVar[str] = ContextVar("request_id", default="-")

_STANDARD_ATTRS = set(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {
    "asctime",
    "message",
    "taskName",
}


class SafeLogger(logging.Logger):
    """A logger that cannot be crashed by the name of a field someone logs.

    `logging` raises `KeyError: Attempt to overwrite 'message' in LogRecord` if an `extra=` key
    collides with a built-in record attribute — and `message`, `filename`, `module`, `name` and
    `args` are all words that come up constantly in this application's context. A logging call
    that takes down the request it was added to observe is worse than no logging at all, so
    colliding keys are renamed with a trailing underscore instead of raising.
    """

    def makeRecord(  # noqa: N802 - overriding stdlib logging's camelCase API
        self, name, level, fn, lno, msg, args, exc_info, func=None, extra=None, sinfo=None
    ):
        if extra:
            extra = {
                (f"{key}_" if key in _STANDARD_ATTRS else key): value
                for key, value in extra.items()
            }
        return super().makeRecord(name, level, fn, lno, msg, args, exc_info, func, extra, sinfo)


# Registered before `getLogger`, so our logger is a `SafeLogger`. Scoped to this call and then
# restored, to avoid changing the class of every logger the process creates later.
_previous_class = logging.getLoggerClass()
logging.setLoggerClass(SafeLogger)
logger = logging.getLogger("calorie_tracker")
logging.setLoggerClass(_previous_class)


class LogEvent(StrEnum):
    """The stable spine of events, spelled one way so filtering is reliable.

    Domain-specific one-offs keep descriptive names of their own; these are the ones worth
    grepping for when you do not yet know what went wrong.
    """

    REQUEST_STARTED = "request_started"
    REQUEST_COMPLETED = "request_completed"
    REQUEST_FAILED = "request_failed"

    OPERATION_STARTED = "operation_started"
    OPERATION_SUCCEEDED = "operation_succeeded"
    OPERATION_FAILED = "operation_failed"

    UPSTREAM_REQUEST = "upstream_request"
    UPSTREAM_RESPONSE = "upstream_response"
    UPSTREAM_FAILED = "upstream_failed"


def get_request_id() -> str:
    return _request_id.get()


def set_request_id(value: str | None = None) -> str:
    request_id = value or uuid.uuid4().hex
    _request_id.set(request_id)
    return request_id


# ---------------------------------------------------------------------------
# Scrubbing
# ---------------------------------------------------------------------------

#: Substring match, so `jwt_secret`, `refresh_token` and `X-Api-Key` are all caught by one entry.
_SENSITIVE_KEY_PARTS = (
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "authorization",
    "credential",
)

REDACTED = "‹redacted›"

#: Long enough for a chat message, a tool-call payload or a stack frame; far short of a
#: base64-encoded image.
MAX_VALUE_CHARS = 2000

MAX_SEQUENCE_ITEMS = 50


def _is_sensitive(key: str) -> bool:
    lowered = key.lower()
    return any(part in lowered for part in _SENSITIVE_KEY_PARTS)


def _truncate(text: str) -> str:
    if len(text) <= MAX_VALUE_CHARS:
        return text
    # Inline data is the pathological case: a single photo upload carries well over a megabyte of
    # base64, which would dwarf everything else in the file and tell you nothing.
    if text.startswith("data:"):
        prefix = text.split(",", 1)[0]
        return f"{prefix},‹{len(text)} chars of inline data omitted›"
    return f"{text[:MAX_VALUE_CHARS]}…‹+{len(text) - MAX_VALUE_CHARS} chars truncated›"


def scrub(value: Any, _depth: int = 0) -> Any:
    """Recursively redact secrets and cut oversized values.

    Depth-limited because a log payload should never be deep enough to need more, and a cyclic
    structure passed by mistake must not take the process down with it.
    """
    if _depth > 6:
        return "‹too deeply nested›"
    if isinstance(value, dict):
        return {
            key: REDACTED if _is_sensitive(str(key)) else scrub(item, _depth + 1)
            for key, item in value.items()
        }
    if isinstance(value, list | tuple):
        clipped = list(value)[:MAX_SEQUENCE_ITEMS]
        scrubbed = [scrub(item, _depth + 1) for item in clipped]
        if len(value) > MAX_SEQUENCE_ITEMS:
            scrubbed.append(f"‹+{len(value) - MAX_SEQUENCE_ITEMS} more omitted›")
        return scrubbed
    if isinstance(value, str):
        return _truncate(value)
    if isinstance(value, int | float | bool) or value is None:
        return value
    return _truncate(str(value))


def _extras(record: logging.LogRecord) -> dict[str, Any]:
    """Whatever the caller passed via `extra=`, scrubbed.

    The top-level keys are checked here as well as inside `scrub`. Without this,
    `extra={"password": "..."}` leaks: `scrub` only inspects a key when it walks *into* a dict, so
    a secret passed as a field name rather than nested one level down would sail straight through
    — which is precisely the shape a careless call site is most likely to take.
    """
    return {
        key: REDACTED if _is_sensitive(key) else scrub(value)
        for key, value in record.__dict__.items()
        if key not in _STANDARD_ATTRS
    }


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------


class JsonFormatter(logging.Formatter):
    """One JSON object per line, for the file. Machine-readable and `jq`-friendly."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": get_request_id(),
        }
        payload.update(_extras(record))
        if record.exc_info:
            payload["exception"] = _truncate(self.formatException(record.exc_info))
        return json.dumps(payload, default=str)


class ConsoleFormatter(logging.Formatter):
    """An aligned single line for a human watching a terminal.

    Deliberately not JSON: the console is read by eye while developing, and a wall of braces is
    what made the previous setup unpleasant to work with.
    """

    LEVELS = {
        "DEBUG": "DEBG",
        "INFO": "INFO",
        "WARNING": "WARN",
        "ERROR": "ERR ",
        "CRITICAL": "CRIT",
    }

    def format(self, record: logging.LogRecord) -> str:
        extras = _extras(record)
        # The event name is the message; showing it twice is noise.
        extras.pop("event", None)
        fields = " ".join(
            f"{key}={value if isinstance(value, int | float) else json.dumps(value, default=str)}"
            for key, value in extras.items()
        )
        head = (
            f"{self.formatTime(record, '%H:%M:%S')} "
            f"{self.LEVELS.get(record.levelname, record.levelname):4} "
            f"{get_request_id()[:8]:8} {record.getMessage()}"
        )
        line = f"{head}  {fields}" if fields else head
        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)
        return line


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


def configure_logging(
    level: str = "INFO",
    *,
    to_file: bool = True,
    log_dir: str = "./logs",
    filename: str = "app.log",
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
) -> None:
    """Attach a console handler and, unless disabled, a rotating file handler."""
    handlers: list[logging.Handler] = []

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(ConsoleFormatter())
    handlers.append(console)

    if to_file:
        # Created here for the same reason `db/session.ensure_sqlite_directory` exists: a fresh
        # clone has no such directory, and a logger that raises on startup is worse than none.
        directory = Path(log_dir)
        directory.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            directory / filename,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setFormatter(JsonFormatter())
        handlers.append(file_handler)

    logger.handlers = handlers
    logger.setLevel(level)
    logger.propagate = False


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------


def _status_of(exc: BaseException) -> int | None:
    """An `AppError`'s status, without importing it.

    `core.errors` imports this module, so importing it back would be a cycle. Duck typing is the
    cheaper answer and works for anything else that carries a status code.
    """
    status = getattr(exc, "status_code", None)
    return status if isinstance(status, int) else None


@contextmanager
def operation(name: str, **context: Any):
    """Log the start, outcome and duration of something that can fail.

    Deliberate application errors (4xx) log at WARNING — they are expected outcomes, not defects.
    Server errors and unexpected exceptions log at ERROR with a traceback. Either way the exception
    propagates untouched; this observes, it never handles.
    """
    logger.debug(
        f"{name}.started", extra={"event": LogEvent.OPERATION_STARTED, "operation": name, **context}
    )
    started = time.perf_counter()

    def elapsed() -> float:
        return round((time.perf_counter() - started) * 1000, 2)

    try:
        yield
    except Exception as exc:
        status = _status_of(exc)
        expected = status is not None and status < 500
        logger.log(
            logging.WARNING if expected else logging.ERROR,
            f"{name}.failed",
            exc_info=not expected,
            extra={
                "event": LogEvent.OPERATION_FAILED,
                "operation": name,
                "duration_ms": elapsed(),
                "error": str(exc),
                "error_kind": type(exc).__name__,
                # Field-level detail, when the error carries any. This is what turns "invalid
                # arguments" into something you can act on without reproducing the failure.
                "errors": getattr(exc, "errors", None) or None,
                "status_code": status,
                **context,
            },
        )
        raise
    else:
        logger.info(
            f"{name}.ok",
            extra={
                "event": LogEvent.OPERATION_SUCCEEDED,
                "operation": name,
                "duration_ms": elapsed(),
            },
        )
