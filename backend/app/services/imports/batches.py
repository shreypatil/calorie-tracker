"""Import history and undo.

Like every other service function here, these take the owning `user_id` — there
is no way to reach a batch by ID alone.
"""

import uuid
from collections.abc import Sequence

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.core.pagination import PageParams, paginate
from app.db.models import FoodEntry, ImportBatch


def list_batches(
    session: Session, user_id: uuid.UUID, params: PageParams
) -> tuple[Sequence[ImportBatch], int]:
    stmt = (
        select(ImportBatch)
        .where(ImportBatch.user_id == user_id)
        .order_by(ImportBatch.created_at.desc())
    )
    return paginate(session, stmt, params)


def count_remaining_entries(
    session: Session, user_id: uuid.UUID, batch_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, int]:
    """How many entries each batch still has — one query, not one per batch."""
    if not batch_ids:
        return {}

    rows = session.execute(
        select(FoodEntry.source_ref, func.count(FoodEntry.id))
        .where(FoodEntry.user_id == user_id, FoodEntry.source_ref.in_(batch_ids))
        .group_by(FoodEntry.source_ref)
    ).all()
    return {source_ref: count for source_ref, count in rows if source_ref is not None}


def get_batch(session: Session, user_id: uuid.UUID, batch_id: uuid.UUID) -> ImportBatch:
    batch = session.scalar(
        select(ImportBatch).where(ImportBatch.id == batch_id, ImportBatch.user_id == user_id)
    )
    if batch is None:
        raise NotFoundError("Import not found.")
    return batch


def undo_import(session: Session, user_id: uuid.UUID, batch_id: uuid.UUID) -> int:
    """Delete a batch and the entries it created. Returns how many were removed.

    The entries must go first. `food_entries.source_ref` is `ondelete="SET NULL"`,
    so deleting the batch on its own would quietly orphan its rows — leaving the
    user's data changed and the undo looking like it worked.
    """
    batch = get_batch(session, user_id, batch_id)

    removed = session.execute(
        delete(FoodEntry).where(FoodEntry.user_id == user_id, FoodEntry.source_ref == batch.id)
    ).rowcount

    session.delete(batch)
    session.commit()
    return removed or 0
