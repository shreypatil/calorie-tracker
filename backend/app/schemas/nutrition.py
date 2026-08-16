"""Schemas for AI nutrition estimation.

The user names a dish, optionally says how much of it and whatever figures they already know, and
the model fills in the rest. Two properties shape these types.

**Only what was asked for comes back.** `fields` is the exact set the caller wants estimated, and
the service returns nothing outside it. That is what makes "never overwrite what the user typed" a
structural guarantee rather than a promise the frontend has to keep — a model that volunteers extra
values, or a second caller written later, cannot break it.

**Names resolve through an allow-list.** `ESTIMABLE_FIELDS` plays the same role here that the
`METRICS`/`DIMENSIONS` registries play for reports and `TOOLS` plays for chat: a caller cannot name
a column that is not estimable, and the set is one obvious place to extend.
"""

from typing import Annotated

from pydantic import BaseModel, Field, field_validator

#: What a model can estimate for an arbitrary dish with any credibility.
#:
#: The eight remaining micronutrients — potassium, calcium, iron, cholesterol and the vitamins —
#: are deliberately absent. A figure for the iron content of "chicken biryani" is close to
#: invention, and rendering it beside the calorie count would give it the same apparent authority.
ESTIMABLE_FIELDS: tuple[str, ...] = (
    "calories",
    "protein_g",
    "carbs_g",
    "fat_g",
    "fiber_g",
    "sugar_g",
    "sodium_mg",
)

#: The same ceiling `EntryCreate` enforces, applied before an estimate ever reaches the form.
MAX_VALUE = 1_000_000.0


def _reject_unknown(names) -> None:
    unknown = sorted(set(names) - set(ESTIMABLE_FIELDS))
    if unknown:
        raise ValueError(
            f"not estimable: {', '.join(unknown)}. Allowed: {', '.join(ESTIMABLE_FIELDS)}"
        )


class NutritionEstimateRequest(BaseModel):
    """What the user has told us, and what they want filled in."""

    food_name: Annotated[str, Field(min_length=1, max_length=200)]
    quantity: Annotated[float | None, Field(default=None, gt=0, le=100_000)]
    unit: Annotated[str | None, Field(default=None, max_length=30)]

    #: Values the user already entered. Treated as fixed: they anchor the estimate and are never
    #: returned, so they cannot be overwritten by what comes back.
    known: dict[str, float] = Field(default_factory=dict)

    #: Exactly which fields to estimate.
    fields: Annotated[list[str], Field(min_length=1, max_length=len(ESTIMABLE_FIELDS))]

    @field_validator("known")
    @classmethod
    def _check_known(cls, value: dict[str, float]) -> dict[str, float]:
        _reject_unknown(value)
        if any(amount < 0 or amount > MAX_VALUE for amount in value.values()):
            raise ValueError("values must be between 0 and 1,000,000")
        return value

    @field_validator("fields")
    @classmethod
    def _check_fields(cls, value: list[str]) -> list[str]:
        _reject_unknown(value)
        # Deduplicated but order-preserving, so the prompt lists each field once.
        return list(dict.fromkeys(value))


class NutritionEstimate(BaseModel):
    """What a provider returns. Filtered and clamped by the service before it reaches the client."""

    values: dict[str, float] = Field(default_factory=dict)
    notes: str = ""
    confidence: Annotated[float, Field(default=0.5, ge=0, le=1)]
