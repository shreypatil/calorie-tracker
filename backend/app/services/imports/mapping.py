"""Applying a `TableMapping` to every row of a document.

The AI produced the mapping; everything here is ordinary deterministic code.
A row that cannot be read is flagged with a reason rather than dropped — the
user should be able to see and fix what went wrong, not wonder why 60 rows
became 58.
"""

from pydantic import ValidationError as PydanticValidationError

from app.core.dates import is_future
from app.db.models import MACRONUTRIENT_FIELDS, MICRONUTRIENT_FIELDS, EntrySource, MealType
from app.schemas.entry import EntryCreate
from app.schemas.import_ import (
    DraftRow,
    NutritionBasis,
    RowIssue,
    RowStatus,
    TableMapping,
)
from app.services.imports.extract import ExtractedTable
from app.services.imports.parsing import (
    is_blank,
    parse_date,
    parse_meal_type,
    parse_number,
    parse_text,
)
from app.services.nutrition import scale_per_100g

#: Below this, a column mapping is a guess and its rows deserve a human look.
LOW_CONFIDENCE = 0.6

NUMERIC_FIELDS: tuple[str, ...] = ("calories", *MACRONUTRIENT_FIELDS, *MICRONUTRIENT_FIELDS)


def apply_mapping(table: ExtractedTable, mapping: TableMapping) -> list[DraftRow]:
    """Build a draft row for every data row in the table."""
    return [
        _build_row(index, cells, table.headers, mapping) for index, cells in enumerate(table.rows)
    ]


def _build_row(index: int, cells: list[str], headers: list[str], mapping: TableMapping) -> DraftRow:
    raw = {
        header: (cells[position] if position < len(cells) else "")
        for position, header in enumerate(headers)
    }

    # A row of entirely empty cells is a spacer, not a failure.
    if all(is_blank(value) for value in raw.values()):
        return DraftRow(
            index=index,
            status=RowStatus.INVALID,
            issues=[RowIssue(message="Blank row.")],
            raw=raw,
        )

    issues: list[RowIssue] = []
    values: dict[str, object] = {}

    for header, cell in raw.items():
        column = mapping.target_for(header)
        if column is None:
            continue

        parsed = _parse_cell(column.target, cell, mapping)
        if parsed is None and not is_blank(cell) and column.target in NUMERIC_FIELDS:
            issues.append(
                RowIssue(
                    field=column.target,
                    message=f'Could not read "{cell.strip()}" as a number.',
                )
            )
        if parsed is not None:
            values[column.target] = parsed

        if column.confidence < LOW_CONFIDENCE:
            issues.append(
                RowIssue(
                    field=column.target,
                    message=f'Unsure that "{header}" means {column.target.replace("_", " ")}.',
                )
            )

    _apply_basis(values, raw, mapping, issues)
    _apply_defaults(values, mapping, issues)

    entry, build_issues = _to_entry(values)
    issues.extend(build_issues)

    return DraftRow(
        index=index,
        status=_status(entry, issues),
        issues=_dedupe(issues),
        entry=entry,
        raw=raw,
    )


def _parse_cell(target: str, cell: str, mapping: TableMapping) -> object | None:
    if target == "consumed_on":
        return parse_date(cell, mapping.date_format)
    if target == "meal_type":
        return parse_meal_type(cell)
    if target == "food_name":
        return parse_text(cell, limit=200)
    if target == "unit":
        return parse_text(cell, limit=30)
    return parse_number(cell)


def _apply_basis(
    values: dict, raw: dict[str, str], mapping: TableMapping, issues: list[RowIssue]
) -> None:
    """Scale per-100g figures to the serving actually eaten."""
    if mapping.basis is not NutritionBasis.PER_100G:
        return

    grams = parse_number(raw.get(mapping.quantity_column or "", ""))
    if not grams:
        issues.append(
            RowIssue(
                message=(
                    "Values are per 100g but this row has no serving size, so they were left as-is."
                )
            )
        )
        return

    # The quantity is the weight eaten, and the figures then describe that whole
    # serving — so the entry is one serving of it, not `grams` servings.
    scale_per_100g(values, grams, NUMERIC_FIELDS)


def _apply_defaults(values: dict, mapping: TableMapping, issues: list[RowIssue]) -> None:
    if "meal_type" not in values:
        if mapping.default_meal_type is not None:
            values["meal_type"] = mapping.default_meal_type
            default = mapping.default_meal_type.value
            issues.append(
                RowIssue(
                    field="meal_type",
                    message=f"No meal in this row — defaulted to {default}.",
                )
            )
        else:
            values["meal_type"] = MealType.SNACK
            issues.append(RowIssue(field="meal_type", message="No meal type found."))

    values.setdefault("quantity", 1.0)
    values.setdefault("unit", "serving")
    values["source"] = EntrySource.PDF


def _to_entry(values: dict) -> tuple[EntryCreate | None, list[RowIssue]]:
    issues: list[RowIssue] = []

    if not values.get("food_name"):
        issues.append(RowIssue(field="food_name", message="No food name in this row."))
        return None, issues
    if not values.get("consumed_on"):
        issues.append(RowIssue(field="consumed_on", message="No readable date in this row."))
        return None, issues

    try:
        entry = EntryCreate(**values)
    except PydanticValidationError as exc:
        for error in exc.errors():
            field = ".".join(str(part) for part in error["loc"]) or None
            message = error["msg"].removeprefix("Value error, ")
            issues.append(RowIssue(field=field, message=message))
        return None, issues

    if entry.calories == 0:
        issues.append(RowIssue(field="calories", message="No calories recorded for this row."))
    if is_future(entry.consumed_on):
        # Almost always a misread date format rather than a real future meal.
        issues.append(
            RowIssue(
                field="consumed_on",
                message="This date is in the future — the date format may be the wrong way round.",
            )
        )

    return entry, issues


def _status(entry: EntryCreate | None, issues: list[RowIssue]) -> RowStatus:
    if entry is None:
        return RowStatus.INVALID
    return RowStatus.NEEDS_REVIEW if issues else RowStatus.OK


def _dedupe(issues: list[RowIssue]) -> list[RowIssue]:
    seen: set[tuple[str | None, str]] = set()
    unique: list[RowIssue] = []
    for issue in issues:
        key = (issue.field, issue.message)
        if key not in seen:
            seen.add(key)
            unique.append(issue)
    return unique
