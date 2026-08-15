"""Food entry request/response schemas."""

import uuid
from datetime import UTC, date, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.db.models import EntrySource, MealType

#: Nutritional amounts are never negative. Upper bounds are loose sanity checks
#: that catch unit mistakes and bad AI extractions without rejecting real food.
NonNegative = Annotated[float, Field(ge=0, le=1_000_000)]
OptionalNonNegative = Annotated[float | None, Field(default=None, ge=0, le=1_000_000)]


class MicronutrientsMixin(BaseModel):
    fiber_g: OptionalNonNegative
    sugar_g: OptionalNonNegative
    sodium_mg: OptionalNonNegative
    potassium_mg: OptionalNonNegative
    calcium_mg: OptionalNonNegative
    iron_mg: OptionalNonNegative
    cholesterol_mg: OptionalNonNegative
    vitamin_a_mcg: OptionalNonNegative
    vitamin_c_mg: OptionalNonNegative
    vitamin_d_mcg: OptionalNonNegative
    vitamin_b12_mcg: OptionalNonNegative


class EntryCreate(MicronutrientsMixin):
    consumed_on: date
    consumed_at: datetime | None = None
    meal_type: MealType
    food_name: str = Field(min_length=1, max_length=200)
    quantity: Annotated[float, Field(gt=0, le=100_000)] = 1.0
    unit: str = Field(default="serving", min_length=1, max_length=30)

    calories: NonNegative = 0.0
    protein_g: NonNegative = 0.0
    carbs_g: NonNegative = 0.0
    fat_g: NonNegative = 0.0

    micros_extra: dict[str, float] | None = None
    source: EntrySource = EntrySource.MANUAL
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("food_name", "unit")
    @classmethod
    def _strip(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped

    @field_validator("consumed_on")
    @classmethod
    def _reject_future_dates(cls, value: date) -> date:
        if value > datetime.now(UTC).date():
            raise ValueError("cannot be in the future")
        return value

    @model_validator(mode="after")
    def _consumed_at_matches_date(self) -> "EntryCreate":
        if self.consumed_at is not None and self.consumed_at.date() != self.consumed_on:
            raise ValueError("consumed_at must fall on consumed_on")
        return self


class EntryUpdate(MicronutrientsMixin):
    """Partial update — only the supplied fields are changed."""

    consumed_on: date | None = None
    consumed_at: datetime | None = None
    meal_type: MealType | None = None
    food_name: str | None = Field(default=None, min_length=1, max_length=200)
    quantity: Annotated[float | None, Field(default=None, gt=0, le=100_000)] = None
    unit: str | None = Field(default=None, min_length=1, max_length=30)

    calories: OptionalNonNegative
    protein_g: OptionalNonNegative
    carbs_g: OptionalNonNegative
    fat_g: OptionalNonNegative

    micros_extra: dict[str, float] | None = None
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("consumed_on")
    @classmethod
    def _reject_future_dates(cls, value: date | None) -> date | None:
        if value is not None and value > datetime.now(UTC).date():
            raise ValueError("cannot be in the future")
        return value


class EntryBulkCreate(BaseModel):
    entries: list[EntryCreate] = Field(min_length=1, max_length=500)
    import_filename: str | None = Field(
        default=None,
        max_length=255,
        description="When set, the entries are recorded as one undoable import batch.",
    )


class EntryResponse(MicronutrientsMixin):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    consumed_on: date
    consumed_at: datetime | None
    meal_type: MealType
    food_name: str
    quantity: float
    unit: str
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    micros_extra: dict[str, float] | None
    source: EntrySource
    source_ref: uuid.UUID | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
