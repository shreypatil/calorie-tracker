"""One definition of "is this date in the future".

There is no single correct "today" in a system with a server and a browser in different places, and
this codebase had accidentally accumulated three: entry validation compared against the UTC date,
goal and weight validation against the server's local date, and everything that *produced* a date —
routes, chat tools, the frontend — used whatever local date its own clock reported.

That is not a theoretical inconsistency. In UTC+5:30, between midnight and 05:30 local, the
browser's "today" is one day ahead of the UTC date, so a user logging breakfast was told the date
was in the future and the entry was refused. Every assisted path failed the same way, because they
all stamp entries with the local date.

The fix is to ask a different question. Rather than "is this after today", which depends on whose
today, ask **"is this after today anywhere on earth"** — no inhabited timezone is more than one day
ahead of UTC, so a legitimate local "today" always passes. Someone can date an entry a few hours
early from an extreme timezone; that is a far better failure than refusing a real meal.
"""

from datetime import UTC, date, datetime, timedelta


def today_anywhere() -> date:
    """The latest date that is still "today" for someone, somewhere.

    UTC+14 (Kiritimati) is the furthest ahead any inhabited timezone runs, so one day past the UTC
    date covers every client without needing to know where they are.
    """
    return datetime.now(UTC).date() + timedelta(days=1)


def is_future(value: date) -> bool:
    """Whether a date is genuinely in the future rather than merely ahead of the server's clock."""
    return value > today_anywhere()
