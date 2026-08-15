"""AI photo extraction endpoints (FR-5).

`POST /ai/analyze-image` reads a photo and returns draft rows. **It writes nothing.** The image
is held in memory for the length of the call and discarded; committing the result goes through
the same `POST /entries` and `POST /entries/bulk` that manual entry uses, so extracted rows
travel the same validation path as anything typed by hand.
"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, File, Query, Request, UploadFile
from starlette.concurrency import run_in_threadpool

from app.ai import get_provider
from app.core.config import get_settings
from app.core.deps import CurrentUser, DbSession
from app.core.errors import ValidationError
from app.db.models import MealType
from app.schemas.photo import PhotoDraft, PhotoKind
from app.services import photo as photo_service
from app.services.rate_limit import limiter

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/analyze-image", response_model=PhotoDraft)
@limiter.limit("10/minute")
async def analyze_image(
    request: Request,
    current_user: CurrentUser,
    session: DbSession,
    file: Annotated[UploadFile, File(description="A nutrition label or meal photo")],
    kind: Annotated[
        PhotoKind, Query(description="Whether this is a product label or a plate of food")
    ] = PhotoKind.LABEL,
    meal_type: Annotated[MealType, Query(description="Meal to file the result under")] = (
        MealType.SNACK
    ),
    consumed_on: Annotated[date | None, Query(description="Defaults to today")] = None,
) -> PhotoDraft:
    """Extract nutrition data from a photo. **Nothing is saved by this call.**

    A label is transcribed and every figure checked against that transcription; a meal photo is
    estimated. Either way the rows come back for review, never marked ready.
    """
    settings = get_settings()

    content = await file.read()
    if not content:
        raise ValidationError("That file is empty.")

    # Off the event loop, deliberately: decoding and re-encoding the image is CPU-bound and the
    # vision call is blocking network I/O — several seconds in which this coroutine would
    # otherwise stall every other request the process is serving.
    return await run_in_threadpool(
        photo_service.analyze_photo,
        content,
        filename=file.filename or "photo.jpg",
        content_type=file.content_type,
        kind=kind,
        meal_type=meal_type,
        on_date=consumed_on or date.today(),
        provider=get_provider(),
        max_bytes=settings.max_upload_bytes,
    )
