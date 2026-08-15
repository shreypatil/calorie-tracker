"""Report endpoints (FR-4).

Every route here is a thin caller of the aggregation layer. `/aggregate` exposes
that layer directly, so new report shapes need no backend change at all.
"""

from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Query

from app.core.deps import CurrentUser, DbSession
from app.schemas.report import (
    AggregateResponse,
    DailySummaryResponse,
    GoalVsActualResponse,
    MacroBreakdownResponse,
    MetricCatalogueResponse,
    MicroSummaryResponse,
    TrendResponse,
)
from app.services import reports
from app.services.reports import DIMENSIONS, METRICS, Granularity
from app.services.reports.query import ReportFilters

router = APIRouter(prefix="/reports", tags=["reports"])

DEFAULT_RANGE_DAYS = 27  # 28 days inclusive — four whole weeks

DateFrom = Annotated[date | None, Query(description="Inclusive start; defaults to 28 days ago")]
DateTo = Annotated[date | None, Query(description="Inclusive end; defaults to today")]
GranularityParam = Annotated[Granularity, Query(description="Time bucket size")]


def _resolve_range(date_from: date | None, date_to: date | None) -> tuple[date, date]:
    end = date_to or date.today()
    start = date_from or end - timedelta(days=DEFAULT_RANGE_DAYS)
    return start, end


@router.get("/catalogue", response_model=MetricCatalogueResponse)
def catalogue() -> MetricCatalogueResponse:
    """The metrics and dimensions `/aggregate` accepts."""
    return MetricCatalogueResponse(metrics=sorted(METRICS), dimensions=sorted(DIMENSIONS))


@router.get("/aggregate", response_model=AggregateResponse)
def aggregate_report(
    current_user: CurrentUser,
    session: DbSession,
    metrics: Annotated[list[str], Query(description="Metric names to sum")],
    group_by: Annotated[list[str], Query(description="Dimension names to group by")] = [],  # noqa: B006
    date_from: DateFrom = None,
    date_to: DateTo = None,
) -> AggregateResponse:
    """Run an arbitrary metric-by-dimension aggregation.

    The open-ended extension point: any combination the registries allow is
    available without a code change.
    """
    rows = reports.aggregate(
        session,
        current_user.id,
        metrics=metrics,
        group_by=group_by,
        filters=ReportFilters(date_from=date_from, date_to=date_to),
    )
    return AggregateResponse(group_by=group_by, metrics=metrics, rows=rows)


@router.get("/daily-summary", response_model=DailySummaryResponse)
def daily_summary(
    current_user: CurrentUser,
    session: DbSession,
    on: Annotated[date | None, Query(description="Day to summarize; defaults to today")] = None,
) -> DailySummaryResponse:
    result = reports.daily_summary(session, current_user.id, on or date.today())
    return DailySummaryResponse.model_validate(result)


@router.get("/trend", response_model=TrendResponse)
def calorie_trend(
    current_user: CurrentUser,
    session: DbSession,
    date_from: DateFrom = None,
    date_to: DateTo = None,
    granularity: GranularityParam = Granularity.DAY,
) -> TrendResponse:
    start, end = _resolve_range(date_from, date_to)
    points = reports.calorie_trend(
        session, current_user.id, date_from=start, date_to=end, granularity=granularity
    )
    return TrendResponse(
        granularity=granularity.value,
        date_from=start,
        date_to=end,
        points=[{"bucket": p[granularity.value], **p} for p in points],
    )


@router.get("/macros", response_model=MacroBreakdownResponse)
def macro_breakdown(
    current_user: CurrentUser,
    session: DbSession,
    date_from: DateFrom = None,
    date_to: DateTo = None,
    granularity: GranularityParam = Granularity.DAY,
) -> MacroBreakdownResponse:
    start, end = _resolve_range(date_from, date_to)
    result = reports.macro_breakdown(
        session, current_user.id, date_from=start, date_to=end, granularity=granularity
    )
    return MacroBreakdownResponse(
        granularity=granularity.value,
        date_from=start,
        date_to=end,
        points=[{"bucket": p[granularity.value], **p} for p in result["series"]],
        totals=result["totals"],
        share_of_calories=result["share_of_calories"],
    )


@router.get("/micros", response_model=MicroSummaryResponse)
def micro_summary(
    current_user: CurrentUser,
    session: DbSession,
    date_from: DateFrom = None,
    date_to: DateTo = None,
) -> MicroSummaryResponse:
    start, end = _resolve_range(date_from, date_to)
    result = reports.micro_summary(session, current_user.id, date_from=start, date_to=end)
    return MicroSummaryResponse.model_validate(result)


@router.get("/goal-vs-actual", response_model=GoalVsActualResponse)
def goal_vs_actual(
    current_user: CurrentUser,
    session: DbSession,
    date_from: DateFrom = None,
    date_to: DateTo = None,
    granularity: GranularityParam = Granularity.DAY,
) -> GoalVsActualResponse:
    start, end = _resolve_range(date_from, date_to)
    points = reports.goal_vs_actual(
        session, current_user.id, date_from=start, date_to=end, granularity=granularity
    )
    return GoalVsActualResponse(
        granularity=granularity.value, date_from=start, date_to=end, points=points
    )
