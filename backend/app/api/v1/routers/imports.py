"""Import endpoints (FR-8).

`POST /imports/pdf` returns a preview and writes nothing. Committing goes
through the existing `POST /entries/bulk`, so imported rows travel the same
validation path as anything typed by hand.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, File, Query, Request, UploadFile, status
from starlette.concurrency import run_in_threadpool

from app.ai import get_provider
from app.core.config import get_settings
from app.core.deps import CurrentUser, DbSession
from app.core.errors import PayloadTooLargeError, ValidationError
from app.core.pagination import Page, PageParamsDep, build_page
from app.db.models import MealType
from app.schemas.import_ import (
    DateFormat,
    ImportBatchResponse,
    PdfImportPreview,
)
from app.services import imports as imports_service
from app.services.rate_limit import limiter

router = APIRouter(prefix="/imports", tags=["imports"])

PDF_CONTENT_TYPES = {"application/pdf", "application/x-pdf", "application/octet-stream"}


@router.post("/pdf", response_model=PdfImportPreview)
@limiter.limit("10/minute")
async def preview_pdf_import(
    request: Request,
    current_user: CurrentUser,
    session: DbSession,
    file: Annotated[UploadFile, File(description="A PDF food diary")],
    date_format: Annotated[
        DateFormat | None, Query(description="Override how dates are read")
    ] = None,
    default_meal_type: Annotated[
        MealType | None, Query(description="Meal to use for rows with none")
    ] = None,
) -> PdfImportPreview:
    """Parse a PDF and return draft rows. **Nothing is saved by this call.**

    Re-send with `date_format` or `default_meal_type` to re-read the same file
    with a correction.
    """
    settings = get_settings()

    if file.content_type and file.content_type not in PDF_CONTENT_TYPES:
        raise ValidationError(f"Expected a PDF, but that file is {file.content_type}.")

    content = await file.read()
    if not content:
        raise ValidationError("That file is empty.")
    if len(content) > settings.max_upload_bytes:
        limit_mb = settings.max_upload_bytes / 1_048_576
        raise PayloadTooLargeError(f"That file is larger than the {limit_mb:.0f} MB limit.")

    # The bytes live only for this call: they are parsed here and never written
    # to disk or to the database.
    #
    # Off the event loop, deliberately. Parsing a PDF is CPU-bound and the AI
    # call is blocking network I/O — several seconds in which this coroutine
    # would otherwise stall *every* other request the process is serving.
    return await run_in_threadpool(
        imports_service.build_preview,
        session,
        current_user.id,
        content=content,
        filename=file.filename or "diary.pdf",
        provider=get_provider(),
        date_format=date_format,
        default_meal_type=default_meal_type,
    )


@router.get("", response_model=Page[ImportBatchResponse])
def list_imports(
    current_user: CurrentUser, session: DbSession, params: PageParamsDep
) -> Page[ImportBatchResponse]:
    batches, total = imports_service.list_batches(session, current_user.id, params)
    remaining = imports_service.count_remaining_entries(
        session, current_user.id, [batch.id for batch in batches]
    )

    items = [
        ImportBatchResponse(
            **{
                **ImportBatchResponse.model_validate(batch).model_dump(),
                "entries_remaining": remaining.get(batch.id, 0),
            }
        )
        for batch in batches
    ]
    return Page[ImportBatchResponse](**build_page(items, total, params))


@router.delete("/{batch_id}", status_code=status.HTTP_204_NO_CONTENT)
def undo_import(batch_id: uuid.UUID, current_user: CurrentUser, session: DbSession) -> None:
    """Remove an import and every entry it created."""
    imports_service.undo_import(session, current_user.id, batch_id)
