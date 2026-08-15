"""Turning an uploaded PDF into a preview the user can review.

Nothing in this module writes to the database. That is the guarantee the whole
feature rests on: an upload can be wrong, surprising, or hostile, and the worst
outcome is a preview the user rejects.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.provider import AIProvider
from app.core.config import get_settings
from app.db.models import FoodEntry, MealType
from app.schemas.import_ import (
    DateFormat,
    DraftRow,
    ImportSummary,
    PdfImportPreview,
    RowIssue,
    RowStatus,
    TableMapping,
    TableSample,
)
from app.services.imports.extract import ExtractedDocument, extract_document
from app.services.imports.mapping import apply_mapping
from app.services.imports.prose import extract_prose_rows


def _sample(document: ExtractedDocument) -> TableSample:
    settings = get_settings()
    table = document.table
    assert table is not None  # guarded by document.kind
    return TableSample(
        headers=table.headers,
        rows=table.rows[: settings.ai_mapping_sample_rows],
        page_count=document.page_count,
    )


def _apply_overrides(
    mapping: TableMapping,
    date_format: DateFormat | None,
    default_meal_type: MealType | None,
) -> TableMapping:
    """Let the user correct the two things most often read wrong."""
    if date_format is None and default_meal_type is None:
        return mapping

    corrected = mapping.model_copy(deep=True)
    if date_format is not None:
        corrected.date_format = date_format
        corrected.notes = f"Dates read as {date_format.value} at your request."
    if default_meal_type is not None:
        corrected.default_meal_type = default_meal_type
    return corrected


def _flag_duplicates(session: Session, user_id: uuid.UUID, rows: list[DraftRow]) -> int:
    """Mark rows that repeat an entry the user already has.

    Re-importing the same diary is an easy mistake to make, and silently
    doubling a month of data is a bad way to find out.
    """
    dated = [row for row in rows if row.entry is not None]
    if not dated:
        return 0

    dates = {row.entry.consumed_on for row in dated}  # type: ignore[union-attr]
    existing = session.execute(
        select(
            FoodEntry.id,
            FoodEntry.consumed_on,
            func.lower(FoodEntry.food_name),
            FoodEntry.calories,
        ).where(FoodEntry.user_id == user_id, FoodEntry.consumed_on.in_(dates))
    ).all()

    index = {
        (consumed_on, name, round(calories)): entry_id
        for entry_id, consumed_on, name, calories in existing
    }

    count = 0
    for row in dated:
        entry = row.entry
        assert entry is not None
        key = (entry.consumed_on, entry.food_name.lower(), round(entry.calories))
        match = index.get(key)
        if match is None:
            continue

        row.duplicate_of = match
        row.issues.append(RowIssue(message="You already have an entry like this on that date."))
        if row.status is RowStatus.OK:
            row.status = RowStatus.NEEDS_REVIEW
        count += 1

    return count


def build_preview(
    session: Session,
    user_id: uuid.UUID,
    *,
    content: bytes,
    filename: str,
    provider: AIProvider,
    date_format: DateFormat | None = None,
    default_meal_type: MealType | None = None,
) -> PdfImportPreview:
    document = extract_document(content)

    if document.kind == "table":
        mapping = provider.infer_table_mapping(_sample(document))
        mapping = _apply_overrides(mapping, date_format, default_meal_type)
        assert document.table is not None
        rows = apply_mapping(document.table, mapping)
    else:
        # No table to describe, so the mapping only carries the reading hints
        # the prose path needs.
        mapping = _apply_overrides(
            TableMapping(
                date_format=DateFormat.DMY,
                default_meal_type=MealType.SNACK,
                notes="No table found — entries were read from the text.",
            ),
            date_format,
            default_meal_type,
        )
        rows = extract_prose_rows(provider, document.text, mapping)

    duplicates = _flag_duplicates(session, user_id, rows)

    if document.warnings:
        mapping.notes = " ".join([mapping.notes, *document.warnings]).strip()

    return PdfImportPreview(
        summary=ImportSummary(
            filename=filename,
            page_count=document.page_count,
            row_count=len(rows),
            ready=sum(1 for row in rows if row.status is RowStatus.OK),
            needs_review=sum(1 for row in rows if row.status is RowStatus.NEEDS_REVIEW),
            invalid=sum(1 for row in rows if row.status is RowStatus.INVALID),
            duplicates=duplicates,
        ),
        mapping=mapping,
        source_kind=document.kind,
        rows=rows,
    )
