"""Reporting: one composable aggregation layer, and the named reports on top."""

from app.services.reports.buckets import Granularity
from app.services.reports.query import (
    DIMENSIONS,
    METRICS,
    ReportFilters,
    aggregate,
    aggregate_over_time,
)
from app.services.reports.service import (
    calorie_trend,
    daily_summary,
    goal_vs_actual,
    macro_breakdown,
    micro_summary,
)

__all__ = [
    "DIMENSIONS",
    "METRICS",
    "Granularity",
    "ReportFilters",
    "aggregate",
    "aggregate_over_time",
    "calorie_trend",
    "daily_summary",
    "goal_vs_actual",
    "macro_breakdown",
    "micro_summary",
]
