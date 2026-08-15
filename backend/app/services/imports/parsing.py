"""Turning document cells into typed values.

Every nutrition figure the import writes comes from here, not from the model.
That is the whole point of the mapping design: the AI says *which* column is
calories, and this file reads what that column actually contains.
"""

import re
from datetime import date, datetime

from app.db.models import MealType
from app.schemas.import_ import DateFormat

#: Values a diary uses for "nothing here".
BLANKS = {"", "-", "--", "—", "–", "n/a", "na", "nil", "none", "?", "."}

_NUMBER = re.compile(r"-?\d[\d,\s]*(?:\.\d+)?")

MEAL_SYNONYMS: dict[str, MealType] = {
    "breakfast": MealType.BREAKFAST,
    "brekkie": MealType.BREAKFAST,
    "brekky": MealType.BREAKFAST,
    "morning": MealType.BREAKFAST,
    "am": MealType.BREAKFAST,
    "b": MealType.BREAKFAST,
    "lunch": MealType.LUNCH,
    "midday": MealType.LUNCH,
    "noon": MealType.LUNCH,
    "l": MealType.LUNCH,
    "dinner": MealType.DINNER,
    "supper": MealType.DINNER,
    "evening": MealType.DINNER,
    "tea": MealType.DINNER,
    "pm": MealType.DINNER,
    "d": MealType.DINNER,
    "snack": MealType.SNACK,
    "snacks": MealType.SNACK,
    "other": MealType.SNACK,
    "extra": MealType.SNACK,
    "s": MealType.SNACK,
}

_DATE_PATTERNS: dict[DateFormat, tuple[str, ...]] = {
    DateFormat.ISO: ("%Y-%m-%d", "%Y/%m/%d"),
    DateFormat.YMD: ("%Y-%m-%d", "%Y/%m/%d", "%y/%m/%d"),
    DateFormat.DMY: ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y", "%d-%m-%y"),
    DateFormat.MDY: ("%m/%d/%Y", "%m-%d-%Y", "%m.%d.%Y", "%m/%d/%y", "%m-%d-%y"),
}

#: Written-out dates are unambiguous, so they are tried whatever the declared
#: format says.
_TEXTUAL_PATTERNS = ("%d %b %Y", "%d %B %Y", "%b %d %Y", "%B %d %Y", "%d %b %y")


def is_blank(value: str | None) -> bool:
    return value is None or value.strip().lower() in BLANKS


def parse_number(value: str | None) -> float | None:
    """Read a number out of a messy cell, or None if there isn't one.

    Handles `1,234`, `320 kcal`, `12.5 g`, `~320`, `approx 90`. Returns None
    rather than 0 for a blank — a missing micronutrient is unknown, not zero,
    and writing 0 would claim the food genuinely contains none.
    """
    if is_blank(value):
        return None

    text = str(value).strip()

    # A range like "300-350": take the midpoint rather than silently picking an
    # end, and let the caller decide whether that deserves review.
    range_match = re.match(r"^\s*(\d+(?:\.\d+)?)\s*[-–—]\s*(\d+(?:\.\d+)?)\s*\w*\s*$", text)
    if range_match:
        low, high = float(range_match.group(1)), float(range_match.group(2))
        return (low + high) / 2

    match = _NUMBER.search(text)
    if not match:
        return None

    cleaned = match.group(0).replace(",", "").replace(" ", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_date(value: str | None, fmt: DateFormat) -> date | None:
    """Read a date, resolving 01/02 ambiguity with the declared format."""
    if is_blank(value):
        return None

    text = " ".join(str(value).split())
    # Ordinal suffixes ("3rd May 2026") are common in hand-written diaries.
    text = re.sub(r"(\d+)(st|nd|rd|th)\b", r"\1", text, flags=re.I)

    for pattern in (*_DATE_PATTERNS.get(fmt, ()), *_TEXTUAL_PATTERNS):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue

    # Last resort: ISO, which is unambiguous wherever it appears.
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def parse_meal_type(value: str | None) -> MealType | None:
    if is_blank(value):
        return None

    key = re.sub(r"[^a-z]+", "", str(value).lower())
    if key in MEAL_SYNONYMS:
        return MEAL_SYNONYMS[key]

    # "Breakfast (8am)" and similar — match on the leading word.
    for synonym, meal in MEAL_SYNONYMS.items():
        if len(synonym) > 2 and key.startswith(synonym):
            return meal
    return None


def parse_text(value: str | None, *, limit: int) -> str | None:
    if is_blank(value):
        return None
    return " ".join(str(value).split())[:limit]
