"""Food entry business logic.

Every function here takes the owning `user_id` — there is deliberately no way to
fetch or mutate an entry by ID alone. That is what keeps user isolation intact
when new callers (REST routes, chat tools) are added later.
"""

import uuid
from collections.abc import Sequence
from datetime import date

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationError
from app.core.pagination import PageParams, paginate
from app.db.models import EntrySource, FoodEntry, ImportBatch, MealType
from app.schemas.entry import EntryCreate, EntryUpdate


def _base_query(user_id: uuid.UUID) -> Select:
    return select(FoodEntry).where(FoodEntry.user_id == user_id)


def build_entry_query(
    user_id: uuid.UUID,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    meal_type: MealType | None = None,
    search: str | None = None,
) -> Select:
    """Filtered, deterministically ordered entry query (FR-3)."""
    if date_from and date_to and date_from > date_to:
        raise ValidationError("date_from must not be after date_to.")

    stmt = _base_query(user_id)
    if date_from:
        stmt = stmt.where(FoodEntry.consumed_on >= date_from)
    if date_to:
        stmt = stmt.where(FoodEntry.consumed_on <= date_to)
    if meal_type:
        stmt = stmt.where(FoodEntry.meal_type == meal_type)
    if search:
        stmt = stmt.where(FoodEntry.food_name.ilike(f"%{search.strip()}%"))

    # created_at then id: a stable tiebreak keeps pagination from repeating or
    # skipping rows logged within the same second.
    return stmt.order_by(
        FoodEntry.consumed_on.desc(), FoodEntry.created_at.desc(), FoodEntry.id.desc()
    )


def list_entries(
    session: Session,
    user_id: uuid.UUID,
    params: PageParams,
    **filters,
) -> tuple[Sequence[FoodEntry], int]:
    return paginate(session, build_entry_query(user_id, **filters), params)


def get_entry(session: Session, user_id: uuid.UUID, entry_id: uuid.UUID) -> FoodEntry:
    entry = session.scalar(_base_query(user_id).where(FoodEntry.id == entry_id))
    if entry is None:
        # 404 rather than 403: the API never confirms that another user's
        # entry exists.
        raise NotFoundError("Food entry not found.")
    return entry


def create_entry(
    session: Session,
    user_id: uuid.UUID,
    payload: EntryCreate,
    *,
    source_ref: uuid.UUID | None = None,
) -> FoodEntry:
    entry = FoodEntry(**payload.model_dump(), user_id=user_id, source_ref=source_ref)
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


def create_entries_bulk(
    session: Session,
    user_id: uuid.UUID,
    payloads: list[EntryCreate],
    *,
    import_filename: str | None = None,
    source: EntrySource | None = None,
) -> tuple[list[FoodEntry], ImportBatch | None]:
    """Write many entries in one transaction.

    When `import_filename` is given, the rows are tied to a single
    `ImportBatch` so the whole import can be undone later.
    """
    batch: ImportBatch | None = None
    if import_filename:
        batch = ImportBatch(user_id=user_id, filename=import_filename, row_count=len(payloads))
        session.add(batch)
        session.flush()  # populate batch.id for the FK below

    entries = []
    for payload in payloads:
        data = payload.model_dump()
        if source is not None:
            data["source"] = source
        entries.append(FoodEntry(**data, user_id=user_id, source_ref=batch.id if batch else None))

    session.add_all(entries)
    session.commit()
    for entry in entries:
        session.refresh(entry)
    return entries, batch


def update_entry(
    session: Session, user_id: uuid.UUID, entry_id: uuid.UUID, payload: EntryUpdate
) -> FoodEntry:
    entry = get_entry(session, user_id, entry_id)

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(entry, field, value)

    if entry.consumed_at is not None and entry.consumed_at.date() != entry.consumed_on:
        raise ValidationError("consumed_at must fall on consumed_on.")

    session.commit()
    session.refresh(entry)
    return entry


def delete_entry(session: Session, user_id: uuid.UUID, entry_id: uuid.UUID) -> None:
    entry = get_entry(session, user_id, entry_id)
    session.delete(entry)
    session.commit()
