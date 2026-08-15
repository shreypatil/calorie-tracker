"""Food entry endpoints (FR-2, FR-3).

Routes parse, authorize, and delegate — all logic lives in the service layer.
"""

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.core.deps import CurrentUser, DbSession
from app.core.pagination import Page, PageParamsDep, build_page
from app.db.models import MealType
from app.schemas.entry import (
    EntryBulkCreate,
    EntryCreate,
    EntryResponse,
    EntryUpdate,
)
from app.services import entries as entries_service

router = APIRouter(prefix="/entries", tags=["entries"])


@router.get("", response_model=Page[EntryResponse])
def list_entries(
    current_user: CurrentUser,
    session: DbSession,
    params: PageParamsDep,
    date_from: Annotated[date | None, Query(description="Inclusive start date")] = None,
    date_to: Annotated[date | None, Query(description="Inclusive end date")] = None,
    meal_type: Annotated[MealType | None, Query()] = None,
    q: Annotated[str | None, Query(max_length=200, description="Food name contains")] = None,
) -> Page[EntryResponse]:
    rows, total = entries_service.list_entries(
        session,
        current_user.id,
        params,
        date_from=date_from,
        date_to=date_to,
        meal_type=meal_type,
        search=q,
    )
    items = [EntryResponse.model_validate(row) for row in rows]
    return Page[EntryResponse](**build_page(items, total, params))


@router.post("", response_model=EntryResponse, status_code=status.HTTP_201_CREATED)
def create_entry(
    payload: EntryCreate, current_user: CurrentUser, session: DbSession
) -> EntryResponse:
    entry = entries_service.create_entry(session, current_user.id, payload)
    return EntryResponse.model_validate(entry)


@router.post("/bulk", response_model=list[EntryResponse], status_code=status.HTTP_201_CREATED)
def create_entries_bulk(
    payload: EntryBulkCreate, current_user: CurrentUser, session: DbSession
) -> list[EntryResponse]:
    created, _ = entries_service.create_entries_bulk(
        session,
        current_user.id,
        payload.entries,
        import_filename=payload.import_filename,
    )
    return [EntryResponse.model_validate(entry) for entry in created]


@router.get("/{entry_id}", response_model=EntryResponse)
def get_entry(entry_id: uuid.UUID, current_user: CurrentUser, session: DbSession) -> EntryResponse:
    entry = entries_service.get_entry(session, current_user.id, entry_id)
    return EntryResponse.model_validate(entry)


@router.patch("/{entry_id}", response_model=EntryResponse)
def update_entry(
    entry_id: uuid.UUID,
    payload: EntryUpdate,
    current_user: CurrentUser,
    session: DbSession,
) -> EntryResponse:
    entry = entries_service.update_entry(session, current_user.id, entry_id, payload)
    return EntryResponse.model_validate(entry)


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entry(entry_id: uuid.UUID, current_user: CurrentUser, session: DbSession) -> None:
    entries_service.delete_entry(session, current_user.id, entry_id)
