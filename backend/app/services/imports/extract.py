"""Getting text and tables out of a PDF.

The file is read from memory and never written to disk. `pdfplumber` and
`pypdf` are pure Python — nothing here shells out — so a hostile PDF's blast
radius is a parse failure, bounded by the size and page limits enforced first.
"""

import io
from dataclasses import dataclass, field
from typing import Literal

import pdfplumber
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.core.config import get_settings
from app.core.errors import AppError, PayloadTooLargeError, ValidationError

PDF_MAGIC = b"%PDF-"

#: Below this much extractable text we treat the document as having no text
#: layer. A scanned page usually yields nothing; a handful of stray characters
#: from an embedded logo should not count as content.
MIN_TEXT_CHARACTERS = 40


class ScannedPdfError(AppError):
    """The PDF has no text layer — it is images of pages.

    Reading these needs vision, which is Phase 3c. `ExtractedDocument` carries
    `has_text_layer` and the page count so that routing can be added there
    without changing this module.
    """

    status_code = 422
    title = "Unsupported PDF"
    error_type = "/errors/scanned-pdf"


@dataclass
class ExtractedTable:
    headers: list[str]
    rows: list[list[str]]

    @property
    def is_usable(self) -> bool:
        return len(self.headers) >= 2 and bool(self.rows)


@dataclass
class ExtractedDocument:
    page_count: int
    has_text_layer: bool
    text: str
    table: ExtractedTable | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def kind(self) -> Literal["table", "prose"]:
        return "table" if self.table and self.table.is_usable else "prose"


def _clean(cell: object) -> str:
    """Normalize a cell: pdfplumber yields None for empties and keeps newlines."""
    if cell is None:
        return ""
    return " ".join(str(cell).split())


def _guard(content: bytes) -> None:
    settings = get_settings()

    if len(content) > settings.max_upload_bytes:
        limit_mb = settings.max_upload_bytes / 1_048_576
        raise PayloadTooLargeError(f"That file is larger than the {limit_mb:.0f} MB limit.")

    if not content.startswith(PDF_MAGIC):
        raise ValidationError("That file is not a PDF.")


def _page_count(content: bytes) -> int:
    settings = get_settings()
    try:
        reader = PdfReader(io.BytesIO(content))
    except PdfReadError as exc:
        raise ValidationError("That PDF could not be read — it may be damaged.") from exc

    if reader.is_encrypted:
        raise ValidationError(
            "That PDF is password-protected. Remove the password and upload it again."
        )

    count = len(reader.pages)
    if count > settings.max_pdf_pages:
        raise ValidationError(
            f"That PDF has {count} pages, more than the {settings.max_pdf_pages}-page limit."
        )
    if count == 0:
        raise ValidationError("That PDF has no pages.")
    return count


def _stitch(tables: list[ExtractedTable]) -> ExtractedTable | None:
    """Join tables that continue across pages.

    A multi-page diary repeats its header on each page, so tables whose headers
    match are one table. Tables with different headers are left behind — better
    to import the largest coherent one than to interleave unrelated columns.
    """
    usable = [table for table in tables if table.is_usable]
    if not usable:
        return None

    primary = usable[0]
    merged = ExtractedTable(headers=primary.headers, rows=list(primary.rows))
    for table in usable[1:]:
        if table.headers == primary.headers:
            merged.rows.extend(table.rows)
    return merged


def extract_document(content: bytes) -> ExtractedDocument:
    """Read a PDF from memory into text plus, where present, one table."""
    _guard(content)
    page_count = _page_count(content)

    texts: list[str] = []
    tables: list[ExtractedTable] = []

    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            texts.append(page.extract_text() or "")
            for raw in page.extract_tables() or []:
                cleaned = [[_clean(cell) for cell in row] for row in raw if any(row)]
                if len(cleaned) < 2:
                    continue
                tables.append(ExtractedTable(headers=cleaned[0], rows=cleaned[1:]))

    text = "\n".join(part for part in texts if part).strip()
    has_text_layer = len(text) >= MIN_TEXT_CHARACTERS or bool(tables)

    if not has_text_layer:
        raise ScannedPdfError(
            "This PDF has no selectable text, so it looks like a scan. "
            "Reading scanned pages is not supported yet — try a PDF exported from an app."
        )

    document = ExtractedDocument(
        page_count=page_count,
        has_text_layer=True,
        text=text,
        table=_stitch(tables),
    )

    if len(tables) > 1 and document.table is not None:
        distinct = sum(1 for table in tables if table.headers != tables[0].headers)
        if distinct:
            document.warnings.append(
                f"Found {distinct + 1} differently-shaped tables; imported the first one only."
            )

    return document
