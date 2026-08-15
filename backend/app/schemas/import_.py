"""Import schemas (FR-8).

`TableMapping` does double duty: it is the API response shape *and* the JSON
schema handed to the model for structured output. One definition, so the two
can never drift apart.
"""

import enum
import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.db.models import MACRONUTRIENT_FIELDS, MICRONUTRIENT_FIELDS, MealType
from app.schemas.entry import EntryCreate

#: Fields a column may be mapped onto. The model's output is checked against
#: this set, so an invented field name fails loudly instead of writing
#: somewhere unexpected — the same discipline the reports registries use.
MAPPABLE_FIELDS: tuple[str, ...] = (
    "consumed_on",
    "meal_type",
    "food_name",
    "quantity",
    "unit",
    "calories",
    *MACRONUTRIENT_FIELDS,
    *MICRONUTRIENT_FIELDS,
)

TargetField = Literal[  # type: ignore[valid-type]
    "consumed_on",
    "meal_type",
    "food_name",
    "quantity",
    "unit",
    "calories",
    "protein_g",
    "carbs_g",
    "fat_g",
    "fiber_g",
    "sugar_g",
    "sodium_mg",
    "potassium_mg",
    "calcium_mg",
    "iron_mg",
    "cholesterol_mg",
    "vitamin_a_mcg",
    "vitamin_c_mg",
    "vitamin_d_mcg",
    "vitamin_b12_mcg",
]


class DateFormat(enum.StrEnum):
    """Which way round an ambiguous date like 01/02/2026 should be read."""

    DMY = "DMY"
    MDY = "MDY"
    YMD = "YMD"
    ISO = "ISO"


class NutritionBasis(enum.StrEnum):
    PER_SERVING = "per_serving"
    PER_100G = "per_100g"


class RowStatus(enum.StrEnum):
    OK = "ok"
    NEEDS_REVIEW = "needs_review"
    INVALID = "invalid"


# --------------------------------------------------------------------------
# What the model sees, and what it returns
# --------------------------------------------------------------------------


class TableSample(BaseModel):
    """The small slice of the document the model is shown."""

    headers: list[str]
    rows: list[list[str]]
    page_count: int = 1


class ColumnMapping(BaseModel):
    source: str = Field(description="The column header exactly as it appears in the document")
    target: TargetField = Field(description="The entry field this column supplies")
    confidence: Annotated[float, Field(ge=0, le=1)] = 1.0


class TableMapping(BaseModel):
    """A description of the table's layout — never its values."""

    columns: list[ColumnMapping] = Field(default_factory=list)
    date_format: DateFormat = DateFormat.ISO
    basis: NutritionBasis = NutritionBasis.PER_SERVING
    quantity_column: str | None = Field(
        default=None,
        description="Header of the serving-size column, when values are per 100g",
    )
    default_meal_type: MealType | None = Field(
        default=None, description="Used when the document has no meal column"
    )
    header_row_index: int = 0
    notes: str = Field(default="", description="Anything the user should know about this reading")

    def target_for(self, header: str) -> ColumnMapping | None:
        for column in self.columns:
            if column.source == header:
                return column
        return None

    @property
    def lowest_confidence(self) -> float:
        return min((column.confidence for column in self.columns), default=0.0)


class RawEntry(BaseModel):
    """One entry as read from a prose diary, before validation."""

    consumed_on: str | None = None
    meal_type: str | None = None
    food_name: str
    quantity: float | None = None
    unit: str | None = None
    calories: float | None = None
    protein_g: float | None = None
    carbs_g: float | None = None
    fat_g: float | None = None


class ProseExtraction(BaseModel):
    """Wrapper so the prose call returns an object, which schemas require."""

    entries: list[RawEntry] = Field(default_factory=list)


# --------------------------------------------------------------------------
# What the API returns
# --------------------------------------------------------------------------


class RowIssue(BaseModel):
    field: str | None = None
    message: str


class DraftRow(BaseModel):
    """One parsed row, with everything the review table needs to render it."""

    index: int
    status: RowStatus
    issues: list[RowIssue] = Field(default_factory=list)
    #: Present unless the row could not be built at all.
    entry: EntryCreate | None = None
    #: The original cells, so the UI can show what was read and the user can
    #: judge a correction against the source.
    raw: dict[str, str] = Field(default_factory=dict)
    duplicate_of: uuid.UUID | None = Field(
        default=None, description="An existing entry this row appears to repeat"
    )


class ImportSummary(BaseModel):
    filename: str
    page_count: int
    row_count: int
    ready: int
    needs_review: int
    invalid: int
    duplicates: int


class PdfImportPreview(BaseModel):
    """The result of an upload. Nothing here has been written to the database."""

    summary: ImportSummary
    mapping: TableMapping
    source_kind: Literal["table", "prose"]
    rows: list[DraftRow]


class ImportBatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    row_count: int
    created_at: datetime
    #: How many of the imported entries still exist — an undone or partly
    #: cleaned-up import shows fewer than it created.
    entries_remaining: int = 0


class DateFormatOverride(BaseModel):
    """Re-read the same file with a corrected interpretation."""

    date_format: DateFormat | None = None
    default_meal_type: MealType | None = None


def today() -> date:
    return date.today()
