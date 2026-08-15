"""The composable aggregation layer every report is built on.

The design point is that **a new report must not mean new SQL**. Reports are
expressed as a choice of metrics (what to sum) and dimensions (what to group
by), both looked up in server-side registries. Adding a metric or dimension is
one dict entry; adding a report is a new caller of `aggregate`.

Because names are resolved through the registries rather than interpolated,
user-supplied strings never reach the query text — extensibility without an
injection surface.
"""

import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import ColumnElement, Select, func, select
from sqlalchemy.orm import Session

from app.core.errors import ValidationError
from app.db.models import MACRONUTRIENT_FIELDS, MICRONUTRIENT_FIELDS, FoodEntry, MealType
from app.services.reports.buckets import Granularity, bucket_range, date_bucket


def _total(column) -> ColumnElement:
    """Sum a nullable column, treating "no data" as zero rather than null."""
    return func.coalesce(func.sum(column), 0.0)


#: What can be measured. Every entry is an aggregate over `food_entries`.
METRICS: dict[str, ColumnElement] = {
    "calories": _total(FoodEntry.calories),
    **{name: _total(getattr(FoodEntry, name)) for name in MACRONUTRIENT_FIELDS},
    **{name: _total(getattr(FoodEntry, name)) for name in MICRONUTRIENT_FIELDS},
    "entry_count": func.count(FoodEntry.id),
}

#: What results can be grouped by.
DIMENSIONS: dict[str, ColumnElement] = {
    "day": date_bucket(FoodEntry.consumed_on, Granularity.DAY),
    "week": date_bucket(FoodEntry.consumed_on, Granularity.WEEK),
    "month": date_bucket(FoodEntry.consumed_on, Granularity.MONTH),
    "meal_type": FoodEntry.meal_type,
    "source": FoodEntry.source,
    "food_name": FoodEntry.food_name,
}

#: Dimensions that produce a date, and the granularity each one buckets to.
DATE_DIMENSIONS: dict[str, Granularity] = {
    "day": Granularity.DAY,
    "week": Granularity.WEEK,
    "month": Granularity.MONTH,
}

MACRO_METRICS = list(MACRONUTRIENT_FIELDS)
MICRO_METRICS = list(MICRONUTRIENT_FIELDS)


@dataclass(frozen=True)
class ReportFilters:
    date_from: date | None = None
    date_to: date | None = None
    meal_type: MealType | None = None
    search: str | None = None

    def validate(self) -> None:
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValidationError("date_from must not be after date_to.")


def _apply_filters(stmt: Select, user_id: uuid.UUID, filters: ReportFilters) -> Select:
    stmt = stmt.where(FoodEntry.user_id == user_id)
    if filters.date_from:
        stmt = stmt.where(FoodEntry.consumed_on >= filters.date_from)
    if filters.date_to:
        stmt = stmt.where(FoodEntry.consumed_on <= filters.date_to)
    if filters.meal_type:
        stmt = stmt.where(FoodEntry.meal_type == filters.meal_type)
    if filters.search:
        stmt = stmt.where(FoodEntry.food_name.ilike(f"%{filters.search.strip()}%"))
    return stmt


def _resolve(names: list[str], registry: dict[str, ColumnElement], kind: str) -> None:
    unknown = [name for name in names if name not in registry]
    if unknown:
        raise ValidationError(
            f"Unknown {kind}: {', '.join(sorted(unknown))}.",
            errors=[
                {
                    "field": kind,
                    "message": f"allowed values are {', '.join(sorted(registry))}",
                    "type": "value_error",
                }
            ],
        )


def aggregate(
    session: Session,
    user_id: uuid.UUID,
    *,
    metrics: list[str],
    group_by: list[str],
    filters: ReportFilters | None = None,
) -> list[dict]:
    """Sum `metrics` over the user's entries, grouped by `group_by`.

    Returns one dict per group, containing the dimension values followed by the
    metric totals. With no `group_by`, returns a single row of overall totals.
    """
    filters = filters or ReportFilters()
    filters.validate()

    if not metrics:
        raise ValidationError("At least one metric is required.")
    _resolve(metrics, METRICS, "metrics")
    _resolve(group_by, DIMENSIONS, "group_by")

    dimensions = [DIMENSIONS[name].label(name) for name in group_by]
    measures = [METRICS[name].label(name) for name in metrics]

    stmt = _apply_filters(select(*dimensions, *measures), user_id, filters)
    if dimensions:
        stmt = stmt.group_by(*dimensions).order_by(*dimensions)

    columns = group_by + metrics
    return [dict(zip(columns, row, strict=True)) for row in session.execute(stmt).all()]


def aggregate_over_time(
    session: Session,
    user_id: uuid.UUID,
    *,
    metrics: list[str],
    granularity: Granularity,
    date_from: date,
    date_to: date,
    filters: ReportFilters | None = None,
) -> list[dict]:
    """`aggregate` grouped by time, with empty buckets filled in as zeros.

    Gap filling happens here rather than in SQL: a recursive CTE to generate a
    date series is one of the least portable things either backend offers, and
    the ranges a chart asks for are small.
    """
    dimension = granularity.value
    base = filters or ReportFilters()
    filters = ReportFilters(
        date_from=date_from,
        date_to=date_to,
        meal_type=base.meal_type,
        search=base.search,
    )

    rows = aggregate(session, user_id, metrics=metrics, group_by=[dimension], filters=filters)
    by_bucket = {row[dimension]: row for row in rows}

    empty = dict.fromkeys(metrics, 0.0)
    return [
        by_bucket.get(bucket, {dimension: bucket, **empty})
        for bucket in bucket_range(date_from, date_to, granularity)
    ]
