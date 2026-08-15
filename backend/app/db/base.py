"""Declarative base, the UTC datetime type, and shared column mixins."""

import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, TypeDecorator, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC)


def enum_values(enum_class: type[enum.Enum]) -> list[str]:
    """Persist enum *values*, not member names.

    Pass as `values_callable` to `sa.Enum`. SQLAlchemy stores `BREAKFAST` by
    default while the API speaks `breakfast`; keeping the two identical means a
    report grouped by meal type, and anyone reading the table directly, sees
    exactly what the API returns.
    """
    return [member.value for member in enum_class]


class UtcDateTime(TypeDecorator):
    """A timezone-aware datetime that stays aware on every backend.

    SQLite has no native timezone support and hands back naive datetimes, which
    a client would then read as local time — silently shifting every timestamp
    the API returns. This normalizes to UTC on the way in and re-attaches UTC on
    the way out, so values are correct regardless of the backend.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


class Base(DeclarativeBase):
    pass


class UUIDPrimaryKeyMixin:
    """UUID keys so IDs are not guessable and never collide across imports."""

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    # Python-side defaults rather than server_default: SQLite's CURRENT_TIMESTAMP
    # writes a naive string, which would defeat UtcDateTime on the way back out.
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime, default=utcnow, onupdate=utcnow, nullable=False
    )
