"""Photo extraction (FR-5).

The pipeline: normalise the image in memory → ask the vision model → verify what it said →
show the user. Nothing is written until they confirm, and the bytes are discarded either way.
"""

from datetime import date

from app.ai.provider import AIProvider
from app.core.logging import logger
from app.db.models import MealType
from app.schemas.photo import PhotoDraft, PhotoKind
from app.services.photo.prepare import PreparedImage, prepare_image
from app.services.photo.verify import build_draft


def analyze_photo(
    content: bytes,
    *,
    filename: str,
    content_type: str | None,
    kind: PhotoKind,
    meal_type: MealType,
    on_date: date,
    provider: AIProvider,
    max_bytes: int,
) -> PhotoDraft:
    """Read one uploaded photo into reviewable draft rows. **Persists nothing.**"""
    image = prepare_image(content, content_type=content_type, max_bytes=max_bytes)
    logger.info(
        "photo_prepared",
        extra={"kind": str(kind), "width": image.width, "height": image.height},
    )

    extraction = provider.analyze_image(image, kind)
    # The provider is told which kind it is looking at, but the user's choice is what the
    # verification rules key off — a model that disagrees must not be able to talk its way
    # out of the transcript check.
    extraction.kind = kind

    return build_draft(extraction, filename=filename, meal_type=meal_type, on_date=on_date)


__all__ = ["PreparedImage", "analyze_photo", "build_draft", "prepare_image"]
