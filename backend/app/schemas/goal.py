"""Goal and weight-log schemas."""

import uuid
from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.db.models import MICRONUTRIENT_FIELDS

OptionalTarget = Annotated[float | None, Field(default=None, ge=0, le=1_000_000)]


def _validate_micro_target_keys(value: dict[str, float] | None) -> dict[str, float] | None:
    """Reject unknown micronutrient names so typos fail loudly, not silently."""
    if value is None:
        return None
    unknown = sorted(set(value) - set(MICRONUTRIENT_FIELDS))
    if unknown:
        raise ValueError(
            f"unknown micronutrient(s): {', '.join(unknown)}. "
            f"Allowed: {', '.join(MICRONUTRIENT_FIELDS)}"
        )
    if any(amount < 0 for amount in value.values()):
        raise ValueError("micronutrient targets must not be negative")
    return value


class GoalCreate(BaseModel):
    effective_from: date = Field(
        default_factory=lambda: datetime.now().date(),
        description="Date this goal version takes effect. Defaults to today.",
    )
    calorie_target: OptionalTarget
    protein_g: OptionalTarget
    carbs_g: OptionalTarget
    fat_g: OptionalTarget
    weight_target_kg: OptionalTarget
    micro_targets: dict[str, float] | None = None

    @field_validator("micro_targets")
    @classmethod
    def _check_micro_targets(cls, value: dict[str, float] | None) -> dict[str, float] | None:
        return _validate_micro_target_keys(value)


class GoalUpdate(BaseModel):
    calorie_target: OptionalTarget
    protein_g: OptionalTarget
    carbs_g: OptionalTarget
    fat_g: OptionalTarget
    weight_target_kg: OptionalTarget
    micro_targets: dict[str, float] | None = None

    @field_validator("micro_targets")
    @classmethod
    def _check_micro_targets(cls, value: dict[str, float] | None) -> dict[str, float] | None:
        return _validate_micro_target_keys(value)


class GoalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    effective_from: date
    calorie_target: float | None
    protein_g: float | None
    carbs_g: float | None
    fat_g: float | None
    weight_target_kg: float | None
    micro_targets: dict[str, float] | None
    created_at: datetime
    updated_at: datetime


class WeightLogCreate(BaseModel):
    logged_on: date = Field(default_factory=lambda: datetime.now().date())
    weight_kg: Annotated[float, Field(gt=0, le=1000)]

    @field_validator("logged_on")
    @classmethod
    def _reject_future_dates(cls, value: date) -> date:
        if value > datetime.now().date():
            raise ValueError("cannot be in the future")
        return value


class WeightLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    logged_on: date
    weight_kg: float
    created_at: datetime
