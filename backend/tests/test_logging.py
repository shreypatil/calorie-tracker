"""Logging behaviour (observability).

These exist because logging is the one subsystem whose failures are invisible by construction: if
it silently stops recording something, nothing breaks until the day you need it and it is not
there. So the properties worth asserting are the ones that would otherwise rot unnoticed — that
secrets never reach the file, that oversized values are cut, that every error response leaves a
line, and above all that a *handled* error still gets written down.

That last one is the regression for the failure that prompted all of this: a chat tool call with
the wrong shape was swallowed into a discarded action, reached no exception handler, and left no
trace anywhere but the database.
"""

import json
import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.logging import (
    REDACTED,
    ConsoleFormatter,
    JsonFormatter,
    configure_logging,
    logger,
    scrub,
    set_request_id,
)


@pytest.fixture
def captured() -> list[logging.LogRecord]:
    """Collect records without disturbing the handlers the app installed."""
    records: list[logging.LogRecord] = []

    class Collector(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    handler = Collector()
    previous_level = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    try:
        yield records
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous_level)


def rendered(records: list[logging.LogRecord]) -> str:
    """Every record as it would reach the file."""
    formatter = JsonFormatter()
    return "\n".join(formatter.format(record) for record in records)


def find(records: list[logging.LogRecord], message: str) -> logging.LogRecord | None:
    return next((r for r in records if r.getMessage() == message), None)


# ---------------------------------------------------------------------------
# Scrubbing
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "key",
    ["password", "api_key", "access_token", "refresh_token", "jwt_secret", "Authorization"],
)
def test_sensitive_keys_are_redacted(key: str) -> None:
    assert scrub({key: "hunter2"})[key] == REDACTED


def test_redaction_reaches_into_nested_structures() -> None:
    scrubbed = scrub({"body": {"user": {"password": "hunter2"}}, "list": [{"api_key": "abc"}]})
    assert scrubbed["body"]["user"]["password"] == REDACTED
    assert scrubbed["list"][0]["api_key"] == REDACTED


def test_a_login_password_never_reaches_the_log(client: TestClient, captured: list) -> None:
    """The whole reason redaction is enforced in the formatter rather than at call sites."""
    client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "super-secret-value"},
    )
    assert "super-secret-value" not in rendered(captured)


def test_inline_image_data_is_not_written_out() -> None:
    """One photo upload would otherwise put over a megabyte of base64 into the file."""
    data_url = "data:image/jpeg;base64," + ("A" * 50_000)
    result = scrub({"image_url": data_url})["image_url"]

    assert result.startswith("data:image/jpeg;base64,")
    assert "AAAA" not in result
    assert len(result) < 200


def test_long_values_are_truncated() -> None:
    result = scrub("x" * 10_000)
    assert "truncated" in result
    assert len(result) < 3000


def test_long_sequences_are_clipped() -> None:
    result = scrub(list(range(500)))
    assert len(result) < 100
    assert "more omitted" in result[-1]


def test_scrubbing_survives_a_cycle() -> None:
    """A logging call must never be the thing that takes the process down."""
    cyclic: dict = {}
    cyclic["self"] = cyclic
    assert scrub(cyclic)  # does not recurse forever


# ---------------------------------------------------------------------------
# The record itself
# ---------------------------------------------------------------------------


def test_reserved_field_names_do_not_raise(captured: list) -> None:
    """`extra={"message": ...}` raises in stdlib logging; ours renames instead.

    Words like `message`, `filename` and `name` are unavoidable in this domain, and a log line
    that crashes the request it was added to observe is worse than no log line.
    """
    logger.info("collision", extra={"message": "hello", "filename": "x.pdf", "name": "n"})

    payload = json.loads(rendered(captured))
    assert payload["message"] == "collision"
    assert payload["message_"] == "hello"
    assert payload["filename_"] == "x.pdf"


def test_request_id_is_on_every_line(captured: list) -> None:
    set_request_id("abc123")
    logger.info("something")
    assert json.loads(rendered(captured))["request_id"] == "abc123"


def test_console_format_is_not_json(captured: list) -> None:
    logger.info("readable", extra={"tool": "log_meal"})
    line = ConsoleFormatter().format(captured[0])

    assert line.startswith(tuple("0123456789"))
    assert "readable" in line
    assert "tool=" in line


# ---------------------------------------------------------------------------
# Error handlers — the choke point every error response passes through
# ---------------------------------------------------------------------------


def test_an_app_error_is_logged(client: TestClient, auth_headers: dict, captured: list) -> None:
    client.get(f"/api/v1/entries/{'0' * 8}-0000-0000-0000-000000000000", headers=auth_headers)

    record = find(captured, "request_failed")
    assert record is not None
    assert record.status_code == 404
    assert record.error_type == "/errors/not-found"
    assert record.levelno == logging.WARNING


def test_a_validation_error_logs_its_field_errors(
    client: TestClient, auth_headers: dict, captured: list
) -> None:
    """Without the field list a 422 log says only "validation failed", which helps nobody."""
    client.post("/api/v1/entries", json={"food_name": ""}, headers=auth_headers)

    record = find(captured, "request_failed")
    assert record is not None
    assert record.status_code == 422
    assert record.errors, "the per-field errors are the whole story for a 422"


def test_every_request_is_bracketed(client: TestClient, auth_headers: dict, captured: list) -> None:
    client.get("/api/v1/entries", headers=auth_headers)

    assert find(captured, "request_started") is not None
    completed = find(captured, "request_completed")
    assert completed is not None and completed.status_code == 200


# ---------------------------------------------------------------------------
# The regression: a handled error must still be written down
# ---------------------------------------------------------------------------


def test_a_swallowed_tool_failure_is_logged_with_its_arguments(db_session, captured: list) -> None:
    """The "prawns curry" case.

    The model returned `log_meal` with `items` as a list of strings and `meal_type` hoisted to the
    top level. `_propose` caught the validation error and turned it into a discarded action, so it
    never reached an exception handler — and nothing logged it. Diagnosing it needed a database
    query. This asserts the arguments and the field errors now reach the log.
    """
    from app.schemas.chat import AssistantTurn, ToolCall
    from app.services.chat import agent
    from tests.test_chat_tools import make_user

    class WrongShapeProvider:
        name = "wrong-shape"

        def converse(self, messages, tools) -> AssistantTurn:
            return AssistantTurn(
                tool_calls=[
                    ToolCall(
                        id="c1",
                        name="log_meal",
                        arguments={"meal_type": "dinner", "items": ["prawns curry"]},
                    )
                ]
            )

    user = make_user(db_session, "prawns@example.com")
    agent.send_message(db_session, user.id, "Add a prawns curry for dinner", WrongShapeProvider())

    record = find(captured, "chat_write_rejected")
    assert record is not None, "a swallowed write failure must still be logged"
    assert record.levelno == logging.WARNING
    assert record.tool == "log_meal"
    # The two things that made the original diagnosis possible only via the database.
    assert record.arguments == {"meal_type": "dinner", "items": ["prawns curry"]}
    assert record.errors, "the per-field errors say which part of the shape was wrong"


# ---------------------------------------------------------------------------
# The file handler
# ---------------------------------------------------------------------------


def test_the_file_handler_writes_json_lines(tmp_path: Path) -> None:
    try:
        configure_logging("INFO", to_file=True, log_dir=str(tmp_path), filename="test.log")
        set_request_id("fileline")
        logger.info("written_to_disk", extra={"tool": "log_meal", "password": "hunter2"})

        for handler in logger.handlers:
            handler.flush()

        lines = (tmp_path / "test.log").read_text().strip().splitlines()
        payload = json.loads(lines[-1])
        assert payload["message"] == "written_to_disk"
        assert payload["request_id"] == "fileline"
        assert payload["tool"] == "log_meal"
        # Redaction applies to the file exactly as it does to the console.
        assert payload["password"] == REDACTED
    finally:
        configure_logging("INFO", to_file=False)


def test_the_log_directory_is_created(tmp_path: Path) -> None:
    """A fresh clone has no `logs/`, and a logger that raises on startup is worse than none."""
    target = tmp_path / "does" / "not" / "exist"
    try:
        configure_logging("INFO", to_file=True, log_dir=str(target))
        assert target.is_dir()
    finally:
        configure_logging("INFO", to_file=False)
