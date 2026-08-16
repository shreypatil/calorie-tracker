"""The named reports (FR-4).

Each one is a thin caller of the aggregation layer — that is the whole point of
the design. Adding "calories by source" or "top foods this month" later means
writing a function like these, not writing SQL.
"""

import uuid
from bisect import bisect_right
from collections.abc import Callable
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import MICRONUTRIENT_FIELDS, Goal, MealType
from app.services.reports.buckets import Granularity, bucket_range, next_bucket
from app.services.reports.query import (
    MACRO_METRICS,
    MICRO_METRICS,
    ReportFilters,
    aggregate,
    aggregate_over_time,
)

CALORIES_PER_GRAM = {"protein_g": 4.0, "carbs_g": 4.0, "fat_g": 9.0}


def _goal_lookup(session: Session, user_id: uuid.UUID) -> Callable[[date], Goal | None]:
    """Return a function giving the goal version in force on any date.

    Loads the user's goal history once and binary-searches it, so a 90-day
    report does not issue 90 queries.
    """
    versions = list(
        session.scalars(
            select(Goal).where(Goal.user_id == user_id).order_by(Goal.effective_from)
        ).all()
    )
    starts = [goal.effective_from for goal in versions]

    def goal_on(on_date: date) -> Goal | None:
        index = bisect_right(starts, on_date)
        return versions[index - 1] if index else None

    return goal_on


def daily_summary(session: Session, user_id: uuid.UUID, on_date: date) -> dict:
    """Totals for one day, against the goal that was in force that day."""
    metrics = ["calories", *MACRO_METRICS, *MICRO_METRICS, "entry_count"]
    filters = ReportFilters(date_from=on_date, date_to=on_date)

    totals = aggregate(session, user_id, metrics=metrics, group_by=[], filters=filters)[0]
    by_meal = aggregate(
        session,
        user_id,
        metrics=["calories", *MACRO_METRICS, "entry_count"],
        group_by=["meal_type"],
        filters=filters,
    )

    goal = _goal_lookup(session, user_id)(on_date)
    return {
        "date": on_date,
        "totals": totals,
        "by_meal": _fill_missing_meals(by_meal),
        "goal": goal,
        "remaining_calories": (
            goal.calorie_target - totals["calories"]
            if goal and goal.calorie_target is not None
            else None
        ),
    }


def _fill_missing_meals(rows: list[dict]) -> list[dict]:
    """Every meal type appears, so the dashboard shows a stable set of rows."""
    present = {row["meal_type"]: row for row in rows}
    empty = {"calories": 0.0, **dict.fromkeys(MACRO_METRICS, 0.0), "entry_count": 0}
    return [
        present.get(meal, {"meal_type": meal, **empty})
        for meal in (MealType.BREAKFAST, MealType.LUNCH, MealType.DINNER, MealType.SNACK)
    ]


def calorie_trend(
    session: Session,
    user_id: uuid.UUID,
    *,
    date_from: date,
    date_to: date,
    granularity: Granularity,
) -> list[dict]:
    return aggregate_over_time(
        session,
        user_id,
        metrics=["calories", "entry_count"],
        granularity=granularity,
        date_from=date_from,
        date_to=date_to,
    )


def macro_breakdown(
    session: Session,
    user_id: uuid.UUID,
    *,
    date_from: date,
    date_to: date,
    granularity: Granularity,
) -> dict:
    """Macros per bucket, plus the overall split as a share of calories."""
    series = aggregate_over_time(
        session,
        user_id,
        metrics=MACRO_METRICS,
        granularity=granularity,
        date_from=date_from,
        date_to=date_to,
    )

    totals = {name: sum(row[name] for row in series) for name in MACRO_METRICS}
    # Split by energy contribution, not by gram weight — a gram of fat carries
    # more than twice the calories of a gram of protein, so comparing raw grams
    # would understate fat in every chart.
    energy = {name: totals[name] * CALORIES_PER_GRAM[name] for name in MACRO_METRICS}
    total_energy = sum(energy.values())

    return {
        "series": series,
        "totals": totals,
        "share_of_calories": {
            name: round(energy[name] / total_energy * 100, 1) if total_energy else 0.0
            for name in MACRO_METRICS
        },
    }


def micro_summary(session: Session, user_id: uuid.UUID, *, date_from: date, date_to: date) -> dict:
    """Micronutrient totals and daily averages against their targets."""
    totals = aggregate(
        session,
        user_id,
        metrics=MICRO_METRICS,
        group_by=[],
        filters=ReportFilters(date_from=date_from, date_to=date_to),
    )[0]

    days = (date_to - date_from).days + 1
    goal = _goal_lookup(session, user_id)(date_to)
    targets = (goal.micro_targets or {}) if goal else {}

    return {
        "date_from": date_from,
        "date_to": date_to,
        "days": days,
        "nutrients": [
            {
                "name": name,
                "total": totals[name],
                "daily_average": round(totals[name] / days, 2),
                "target": targets.get(name),
            }
            for name in MICRONUTRIENT_FIELDS
        ],
    }


def goal_vs_actual(
    session: Session,
    user_id: uuid.UUID,
    *,
    date_from: date,
    date_to: date,
    granularity: Granularity,
) -> list[dict]:
    """Actual intake against the goal that was in force, bucket by bucket.

    The target for a bucket is the sum of the daily targets for the days it
    covers, so a weekly total is compared against a week's worth of target
    rather than against a single day's.
    """
    metrics = ["calories", *MACRO_METRICS, *MICRO_METRICS]
    actuals = aggregate_over_time(
        session,
        user_id,
        metrics=metrics,
        granularity=granularity,
        date_from=date_from,
        date_to=date_to,
    )
    goal_on = _goal_lookup(session, user_id)

    def _target_for(goal, metric: str) -> float | None:
        """Where a metric's target lives on a goal.

        Calories are `calorie_target`, macros are columns of the same name, and micronutrients
        live in the `micro_targets` JSON. Micros were omitted here originally, which meant a user
        could set a fibre target on the Goals page and then find nothing to compare it against.
        """
        if metric == "calories":
            return goal.calorie_target
        if metric in MICRO_METRICS:
            return (goal.micro_targets or {}).get(metric)
        return getattr(goal, metric, None)

    results = []
    for row in actuals:
        bucket = row[granularity.value]
        days = _days_in_bucket(bucket, granularity, date_from, date_to)

        targets: dict[str, float | None] = {}
        for metric in metrics:
            values = [
                target
                for day in days
                if (goal := goal_on(day)) and (target := _target_for(goal, metric)) is not None
            ]
            targets[metric] = sum(values) if values else None

        results.append(
            {
                "bucket": bucket,
                "days": len(days),
                "actual": {metric: row[metric] for metric in metrics},
                "target": targets,
            }
        )
    return results


def _days_in_bucket(
    bucket: date, granularity: Granularity, date_from: date, date_to: date
) -> list[date]:
    """The days a bucket covers, clipped to the requested range."""
    end = min(next_bucket(bucket, granularity), next_bucket(date_to, Granularity.DAY))
    start = max(bucket, date_from)
    return bucket_range(start, end, Granularity.DAY)[:-1] if start < end else []
