"""Date bucketing — the only dialect-specific SQL in the codebase.

Grouping a date column by day, week, or month is the one thing SQLite and
PostgreSQL genuinely disagree about. Isolating it in a single compiled construct
means the rest of the reporting layer is written once and runs unchanged on
either backend, which is what makes the SQLite-to-PostgreSQL move a
configuration change rather than a rewrite.

Weeks start on Monday on both backends.
"""

import enum
from datetime import date, timedelta

from sqlalchemy import Date
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.functions import FunctionElement


class Granularity(enum.StrEnum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


class date_bucket(FunctionElement):  # noqa: N801 (reads as a SQL function)
    """Truncate a date column to the start of its day, week, or month."""

    type = Date()
    inherit_cache = True

    def __init__(self, column, granularity: Granularity) -> None:
        self.granularity = Granularity(granularity)
        super().__init__(column)


@compiles(date_bucket)
def _compile_default(element: date_bucket, compiler, **kw) -> str:
    """PostgreSQL and other backends with `date_trunc`."""
    column = compiler.process(element.clauses.clauses[0], **kw)
    if element.granularity is Granularity.DAY:
        return column
    return f"CAST(date_trunc('{element.granularity.value}', {column}) AS DATE)"


@compiles(date_bucket, "sqlite")
def _compile_sqlite(element: date_bucket, compiler, **kw) -> str:
    column = compiler.process(element.clauses.clauses[0], **kw)
    if element.granularity is Granularity.DAY:
        return f"date({column})"
    if element.granularity is Granularity.MONTH:
        return f"date({column}, 'start of month')"
    # Monday on or before the given date: step back six days, then forward to
    # the next Monday. SQLite's 'weekday 1' stays put if already a Monday, so
    # the shift is what stops a Monday from landing on itself a week early.
    return f"date({column}, '-6 days', 'weekday 1')"


def bucket_start(value: date, granularity: Granularity) -> date:
    """The Python equivalent of `date_bucket`, used for gap filling."""
    if granularity is Granularity.DAY:
        return value
    if granularity is Granularity.WEEK:
        return value - timedelta(days=value.weekday())
    return value.replace(day=1)


def next_bucket(value: date, granularity: Granularity) -> date:
    """The start of the bucket following the one beginning at `value`."""
    if granularity is Granularity.DAY:
        return value + timedelta(days=1)
    if granularity is Granularity.WEEK:
        return value + timedelta(days=7)
    return (value.replace(day=28) + timedelta(days=4)).replace(day=1)


def bucket_range(start: date, end: date, granularity: Granularity) -> list[date]:
    """Every bucket start from `start` to `end` inclusive."""
    current = bucket_start(start, granularity)
    last = bucket_start(end, granularity)
    buckets = []
    while current <= last:
        buckets.append(current)
        current = next_bucket(current, granularity)
    return buckets
