"""Report response schemas (FR-4)."""

from datetime import date
from typing import Any

from pydantic import BaseModel, Field

from app.db.models import MealType
from app.schemas.goal import GoalResponse


class AggregateResponse(BaseModel):
    """Result of the generic aggregation endpoint.

    Rows are shaped by the requested dimensions and metrics, so they are typed
    loosely on purpose — this endpoint exists precisely so new report shapes do
    not need a new schema.
    """

    group_by: list[str]
    metrics: list[str]
    rows: list[dict[str, Any]]


class MetricCatalogueResponse(BaseModel):
    """What the generic endpoint accepts — lets a client build queries safely."""

    metrics: list[str]
    dimensions: list[str]


class MealTotals(BaseModel):
    meal_type: MealType
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    entry_count: int


class DailySummaryResponse(BaseModel):
    date: date
    totals: dict[str, float]
    by_meal: list[MealTotals]
    goal: GoalResponse | None
    remaining_calories: float | None = Field(
        description="Goal calories minus intake; negative when over. Null with no goal set."
    )


class TrendPoint(BaseModel):
    bucket: date
    calories: float
    entry_count: int


class TrendResponse(BaseModel):
    granularity: str
    date_from: date
    date_to: date
    points: list[TrendPoint]


class MacroPoint(BaseModel):
    bucket: date
    protein_g: float
    carbs_g: float
    fat_g: float


class MacroBreakdownResponse(BaseModel):
    granularity: str
    date_from: date
    date_to: date
    points: list[MacroPoint]
    totals: dict[str, float]
    share_of_calories: dict[str, float] = Field(
        description="Percentage of total calories from each macro, by energy not gram weight."
    )


class MicronutrientRow(BaseModel):
    name: str
    total: float
    daily_average: float
    target: float | None


class MicroSummaryResponse(BaseModel):
    date_from: date
    date_to: date
    days: int
    nutrients: list[MicronutrientRow]


class GoalComparisonPoint(BaseModel):
    bucket: date
    days: int = Field(description="Days this bucket covers within the requested range")
    actual: dict[str, float]
    target: dict[str, float | None] = Field(
        description="Daily targets summed across the bucket's days; null where unset."
    )


class GoalVsActualResponse(BaseModel):
    granularity: str
    date_from: date
    date_to: date
    points: list[GoalComparisonPoint]
