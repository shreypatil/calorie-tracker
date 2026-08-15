"""Unit tests for reading values out of document cells.

Every nutrition figure an import writes comes from these functions, so this is
where the correctness of the whole feature actually lives.
"""

from datetime import date

import pytest

from app.db.models import MealType
from app.schemas.import_ import DateFormat
from app.services.imports.parsing import (
    is_blank,
    parse_date,
    parse_meal_type,
    parse_number,
    parse_text,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("320", 320.0),
        ("1,234", 1234.0),
        ("1 234", 1234.0),
        ("320 kcal", 320.0),
        ("12.5 g", 12.5),
        ("~320", 320.0),
        ("approx 90", 90.0),
        ("0", 0.0),
        ("300-350", 325.0),  # a range collapses to its midpoint
    ],
)
def test_parse_number_reads_messy_cells(raw: str, expected: float) -> None:
    assert parse_number(raw) == expected


@pytest.mark.parametrize("raw", ["", "  ", "-", "—", "n/a", "N/A", "nil", "none", "?", None])
def test_parse_number_returns_none_for_blanks(raw: str | None) -> None:
    """None, not zero — a missing micronutrient is unknown, not absent."""
    assert parse_number(raw) is None
    assert is_blank(raw)


def test_parse_number_returns_none_for_unparseable_text() -> None:
    assert parse_number("lots") is None


def test_date_format_resolves_the_ambiguous_case() -> None:
    """01/02/2026 is 1 Feb or 2 Jan depending only on the declared format."""
    assert parse_date("01/02/2026", DateFormat.DMY) == date(2026, 2, 1)
    assert parse_date("01/02/2026", DateFormat.MDY) == date(2026, 1, 2)


@pytest.mark.parametrize(
    ("raw", "fmt", "expected"),
    [
        ("2026-06-15", DateFormat.ISO, date(2026, 6, 15)),
        ("15/06/2026", DateFormat.DMY, date(2026, 6, 15)),
        ("06/15/2026", DateFormat.MDY, date(2026, 6, 15)),
        ("15-06-2026", DateFormat.DMY, date(2026, 6, 15)),
        ("15.06.2026", DateFormat.DMY, date(2026, 6, 15)),
        # Written-out dates are unambiguous whatever the declared format says.
        ("3 May 2026", DateFormat.MDY, date(2026, 5, 3)),
        ("3rd May 2026", DateFormat.DMY, date(2026, 5, 3)),
    ],
)
def test_parse_date(raw: str, fmt: DateFormat, expected: date) -> None:
    assert parse_date(raw, fmt) == expected


def test_parse_date_returns_none_when_unreadable() -> None:
    assert parse_date("sometime last week", DateFormat.DMY) is None
    assert parse_date("", DateFormat.ISO) is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Breakfast", MealType.BREAKFAST),
        ("brekkie", MealType.BREAKFAST),
        ("Morning", MealType.BREAKFAST),
        ("LUNCH", MealType.LUNCH),
        ("Supper", MealType.DINNER),
        ("evening", MealType.DINNER),
        ("Tea", MealType.DINNER),
        ("Snacks", MealType.SNACK),
        ("Breakfast (8am)", MealType.BREAKFAST),
    ],
)
def test_parse_meal_type_handles_synonyms(raw: str, expected: MealType) -> None:
    assert parse_meal_type(raw) == expected


def test_parse_meal_type_returns_none_when_unrecognized() -> None:
    assert parse_meal_type("elevenses") is None
    assert parse_meal_type("") is None


def test_parse_text_collapses_whitespace_and_truncates() -> None:
    assert parse_text("  Greek   yoghurt \n with berries ", limit=200) == (
        "Greek yoghurt with berries"
    )
    assert len(parse_text("x" * 500, limit=200) or "") == 200
