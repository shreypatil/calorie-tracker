"""Getting an uploaded photo into a shape worth sending, without ever storing it.

The bytes exist for the length of one request. They are decoded, normalised, re-encoded and
handed to the provider; nothing touches the disk or the database at any point.

Three of the steps here are not cosmetic:

*Orientation.* Phone cameras record rotation in EXIF rather than rotating the pixels. Skip
`exif_transpose` and a portrait photo of a label arrives sideways, which is the single most
effective way to ruin a reading — and it fails silently, because the model dutifully returns
whatever it can make out.

*Downscaling.* A modern phone photo is 12+ megapixels. Vision models bill by tile, so sending
the original costs several times more, takes longer, and reads no better than a 1568px edge.

*Re-encoding.* Producing a fresh JPEG normalises exotic colour modes and, as a side effect,
discards every EXIF tag — including the GPS coordinates a phone attaches to a photo taken at
home. We never wanted them and now cannot accidentally forward them.
"""

import base64
import io
from dataclasses import dataclass

from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.errors import PayloadTooLargeError, ValidationError
from app.core.logging import logger

#: What a browser file picker will realistically produce and Pillow can decode unaided.
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}

#: Longest edge sent upstream. Comfortably above the resolution at which label text stops
#: being legible, and well below the point where extra pixels buy anything.
MAX_EDGE_PX = 1568

#: A 100-megapixel PNG can decompress from a few hundred KB into gigabytes of memory. Pillow
#: warns above its own default; this makes it a hard refusal well before that.
MAX_DECODED_PIXELS = 50_000_000

JPEG_QUALITY = 85

#: HEIC needs an extra decoder Pillow does not bundle. Detected by magic bytes so the message
#: is about the format rather than a decode failure.
_HEIC_BRANDS = (b"ftypheic", b"ftypheix", b"ftyphevc", b"ftypmif1", b"ftypmsf1")


@dataclass(frozen=True)
class PreparedImage:
    """A normalised JPEG, ready to send. Held in memory only."""

    data: bytes
    media_type: str
    width: int
    height: int

    @property
    def data_url(self) -> str:
        """Inline form the OpenAI-compatible vision API takes."""
        encoded = base64.b64encode(self.data).decode("ascii")
        return f"data:{self.media_type};base64,{encoded}"


def _reject_heic(content: bytes) -> None:
    if any(brand in content[:32] for brand in _HEIC_BRANDS):
        raise ValidationError(
            "That looks like a HEIC photo, which this app cannot read. On iPhone, either share "
            "it as JPEG or set Camera → Formats to 'Most Compatible', then try again."
        )


def prepare_image(content: bytes, *, content_type: str | None, max_bytes: int) -> PreparedImage:
    """Validate, normalise and downscale an uploaded photo."""
    if not content:
        raise ValidationError("That file is empty.")
    if len(content) > max_bytes:
        raise PayloadTooLargeError(
            f"That image is larger than the {max_bytes / 1_048_576:.0f} MB limit."
        )
    if content_type and content_type.lower() not in ALLOWED_CONTENT_TYPES:
        raise ValidationError(
            f"Expected a JPEG, PNG or WebP image, but that file is {content_type}."
        )

    _reject_heic(content)

    try:
        image = Image.open(io.BytesIO(content))
        # Cheap: reads the header only, so an oversized image is refused before its pixels
        # are ever decoded into memory.
        pixels = (image.width or 0) * (image.height or 0)
        if pixels > MAX_DECODED_PIXELS:
            raise PayloadTooLargeError(
                f"That image is {image.width}×{image.height}, which is too large to process. "
                "Please resize it and try again."
            )
        image = ImageOps.exif_transpose(image)
        image = image.convert("RGB")
    except PayloadTooLargeError:
        raise
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        logger.info("photo_decode_failed", extra={"error": str(exc)})
        raise ValidationError(
            "That image could not be read. It may be corrupt or in an unsupported format."
        ) from exc

    image.thumbnail((MAX_EDGE_PX, MAX_EDGE_PX), Image.Resampling.LANCZOS)

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)

    return PreparedImage(
        data=buffer.getvalue(),
        media_type="image/jpeg",
        width=image.width,
        height=image.height,
    )
