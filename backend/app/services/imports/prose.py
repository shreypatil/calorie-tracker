"""The fallback for diaries with no table.

Here the model *does* transcribe values, so unlike the mapping path we cannot
rely on the numbers coming from the document by construction. Instead every
number the model returns is checked to literally appear in the source text; one
that does not is dropped and the row flagged.

That check is cheap and it catches the exact failure that matters — a plausible
calorie count that was never written down. Rows from this path are never better
than `needs_review`, so a person sees them all regardless.
"""

from app.ai.provider import AIProvider
from app.core.logging import logger
from app.db.models import EntrySource
from app.schemas.entry import EntryCreate
from app.schemas.import_ import DraftRow, RawEntry, RowIssue, RowStatus, TableMapping
from app.services.imports.parsing import parse_date, parse_meal_type, parse_text
from app.services.nutrition import appears_in_source

#: Lines per request. Small enough to keep each call cheap and bounded, large
#: enough that a day's entries usually stay together with their date heading.
CHUNK_LINES = 60

NUMERIC_FIELDS = ("calories", "protein_g", "carbs_g", "fat_g", "quantity")


def _chunk(text: str) -> list[str]:
    lines = [line for line in text.splitlines()]
    return [
        "\n".join(lines[start : start + CHUNK_LINES]) for start in range(0, len(lines), CHUNK_LINES)
    ] or [text]


def _to_draft(index: int, raw: RawEntry, source: str, mapping: TableMapping) -> DraftRow:
    issues: list[RowIssue] = [
        RowIssue(message="Read from prose rather than a table — please check it.")
    ]
    values: dict[str, object] = {"source": EntrySource.PDF}

    for field in NUMERIC_FIELDS:
        value = getattr(raw, field, None)
        if value is None:
            continue
        if not appears_in_source(float(value), source):
            logger.warning("prose_value_not_in_source", extra={"field": field, "value": value})
            label = field.replace("_", " ")
            issues.append(
                RowIssue(
                    field=field,
                    message=f"Discarded a {label} value that is not in the document.",
                )
            )
            continue
        values[field] = float(value)

    values["food_name"] = parse_text(raw.food_name, limit=200)
    values["unit"] = parse_text(raw.unit, limit=30) or "serving"
    values.setdefault("quantity", 1.0)

    consumed_on = parse_date(raw.consumed_on, mapping.date_format)
    meal_type = parse_meal_type(raw.meal_type) or mapping.default_meal_type

    if consumed_on is None:
        issues.append(RowIssue(field="consumed_on", message="No date for this entry."))
        return DraftRow(index=index, status=RowStatus.INVALID, issues=issues, raw={})
    if not values["food_name"]:
        issues.append(RowIssue(field="food_name", message="No food name for this entry."))
        return DraftRow(index=index, status=RowStatus.INVALID, issues=issues, raw={})

    values["consumed_on"] = consumed_on
    values["meal_type"] = meal_type or mapping.default_meal_type

    if values["meal_type"] is None:
        issues.append(RowIssue(field="meal_type", message="No meal type for this entry."))
        return DraftRow(index=index, status=RowStatus.INVALID, issues=issues, raw={})

    try:
        entry = EntryCreate(**values)
    except Exception as exc:  # noqa: BLE001 - surfaced to the user as an issue
        issues.append(RowIssue(message=str(exc).splitlines()[0]))
        return DraftRow(index=index, status=RowStatus.INVALID, issues=issues, raw={})

    return DraftRow(
        index=index,
        # Never `ok`: a transcribed row always gets a human look.
        status=RowStatus.NEEDS_REVIEW,
        issues=issues,
        entry=entry,
        raw={"text": raw.food_name},
    )


def extract_prose_rows(provider: AIProvider, text: str, mapping: TableMapping) -> list[DraftRow]:
    rows: list[DraftRow] = []
    for chunk in _chunk(text):
        for raw in provider.extract_entries_from_text(chunk):
            rows.append(_to_draft(len(rows), raw, chunk, mapping))
    return rows
