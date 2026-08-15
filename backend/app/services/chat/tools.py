"""The tool registry the chat model is allowed to act through.

This is the reports layer's registry idea applied to actions instead of queries. A tool name
resolves through `TOOLS` rather than being interpreted, so the model can only ever invoke
something that was deliberately put here, and its arguments are validated by a Pydantic model
before any service sees them.

Three properties matter, in descending order of importance:

**Identity is never a tool argument.** No argument model below has a user field. `user_id`
is supplied by the dispatcher from the authenticated request, so there is no slot for the
model to fill and no prompt — however cleverly written, however hostile the food names coming
back from a previous tool call — that can widen scope to another user's data. Combined with
the rule that every service function takes its owning `user_id`, isolation is structural
rather than something each tool has to remember.

**Every tool delegates.** Not one line of business logic lives here; each handler is a
translation from the model's arguments into the same service call the REST router makes. That
is what keeps the two interfaces from drifting apart.

**Writes are declared.** `writes=True` is what causes the agent loop to stop and ask the user
instead of acting. A new tool that mutates anything must set it.
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Annotated, Any

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.pagination import PageParams
from app.db.models import EntrySource, MealType
from app.schemas.entry import EntryCreate, EntryUpdate
from app.schemas.goal import GoalCreate, WeightLogCreate
from app.services import entries as entries_service
from app.services import goals as goals_service
from app.services.reports import service as reports_service
from app.services.reports.buckets import Granularity
from app.services.reports.query import DIMENSIONS, METRICS, ReportFilters, aggregate

#: How many rows a read tool may put into the model's context. Tool results are re-sent on
#: every iteration of the agent loop, so an unbounded list is both a cost and a latency bug.
MAX_ROWS = 50


@dataclass(frozen=True)
class Tool:
    """One callable the model may request.

    `summarize` renders the one-line description the user sees on a draft card. It exists so
    the confirmation UI never has to know what any particular tool means.
    """

    name: str
    description: str
    args_model: type[BaseModel]
    handler: Callable[[Session, uuid.UUID, Any], dict]
    writes: bool = False
    summarize: Callable[[Any], str] | None = None


# ---------------------------------------------------------------------------
# Argument models
#
# Kept flat and lightly typed on purpose: these become JSON Schema sent to the provider, and
# deeply nested or heavily unioned schemas are the most common source of provider-side
# rejections. `MealItem` is the one nested model, and `ai/openai_compatible.py` inlines it.
# ---------------------------------------------------------------------------


class MealItem(BaseModel):
    """One food to log. Nutrition figures are the model's estimate — the user confirms them."""

    food_name: Annotated[str, Field(max_length=200, description="e.g. 'Scrambled eggs'")]
    meal_type: MealType
    consumed_on: Annotated[date | None, Field(default=None, description="Defaults to today.")]
    quantity: Annotated[float, Field(default=1.0, gt=0)]
    unit: Annotated[str, Field(default="serving", max_length=30)]
    calories: Annotated[float, Field(default=0, ge=0)]
    protein_g: Annotated[float, Field(default=0, ge=0)]
    carbs_g: Annotated[float, Field(default=0, ge=0)]
    fat_g: Annotated[float, Field(default=0, ge=0)]
    fiber_g: Annotated[float | None, Field(default=None, ge=0)]
    sugar_g: Annotated[float | None, Field(default=None, ge=0)]
    sodium_mg: Annotated[float | None, Field(default=None, ge=0)]


class LogMealArgs(BaseModel):
    items: Annotated[list[MealItem], Field(min_length=1, max_length=20)]


class UpdateEntryArgs(BaseModel):
    entry_id: Annotated[uuid.UUID, Field(description="From a previous query_entries result.")]
    food_name: Annotated[str | None, Field(default=None, max_length=200)]
    meal_type: MealType | None = None
    quantity: Annotated[float | None, Field(default=None, gt=0)]
    calories: Annotated[float | None, Field(default=None, ge=0)]
    protein_g: Annotated[float | None, Field(default=None, ge=0)]
    carbs_g: Annotated[float | None, Field(default=None, ge=0)]
    fat_g: Annotated[float | None, Field(default=None, ge=0)]


class DeleteEntryArgs(BaseModel):
    entry_id: Annotated[uuid.UUID, Field(description="From a previous query_entries result.")]


class SetGoalArgs(BaseModel):
    effective_from: Annotated[
        date | None,
        Field(default=None, description="When the new targets start. Defaults to today."),
    ]
    calorie_target: Annotated[float | None, Field(default=None, ge=0)]
    protein_g: Annotated[float | None, Field(default=None, ge=0)]
    carbs_g: Annotated[float | None, Field(default=None, ge=0)]
    fat_g: Annotated[float | None, Field(default=None, ge=0)]
    weight_target_kg: Annotated[float | None, Field(default=None, ge=0)]


class LogWeightArgs(BaseModel):
    weight_kg: Annotated[float, Field(gt=0, le=1000)]
    logged_on: Annotated[date | None, Field(default=None, description="Defaults to today.")]


class QueryEntriesArgs(BaseModel):
    date_from: date | None = None
    date_to: date | None = None
    meal_type: MealType | None = None
    search: Annotated[str | None, Field(default=None, description="Match on food name.")]
    limit: Annotated[int, Field(default=20, ge=1, le=MAX_ROWS)]


class OnDateArgs(BaseModel):
    on_date: Annotated[date | None, Field(default=None, description="Defaults to today.")]


class DateRangeArgs(BaseModel):
    date_from: date
    date_to: date
    granularity: Granularity = Granularity.DAY


class NutritionReportArgs(BaseModel):
    metrics: Annotated[list[str], Field(min_length=1, max_length=8)]
    group_by: Annotated[list[str], Field(default_factory=list, max_length=3)]
    date_from: date | None = None
    date_to: date | None = None
    meal_type: MealType | None = None
    search: str | None = None
    limit: Annotated[int, Field(default=20, ge=1, le=MAX_ROWS)]


# ---------------------------------------------------------------------------
# Handlers — each one delegates and does nothing else
# ---------------------------------------------------------------------------


def _entry_row(entry) -> dict:
    """The compact view of an entry the model sees. IDs are included so it can edit rows."""
    return {
        "id": str(entry.id),
        "consumed_on": entry.consumed_on.isoformat(),
        "meal_type": str(entry.meal_type),
        "food_name": entry.food_name,
        "quantity": entry.quantity,
        "unit": entry.unit,
        "calories": entry.calories,
        "protein_g": entry.protein_g,
        "carbs_g": entry.carbs_g,
        "fat_g": entry.fat_g,
    }


def _goal_row(goal) -> dict | None:
    if goal is None:
        return None
    return {
        "effective_from": goal.effective_from.isoformat(),
        "calorie_target": goal.calorie_target,
        "protein_g": goal.protein_g,
        "carbs_g": goal.carbs_g,
        "fat_g": goal.fat_g,
        "weight_target_kg": goal.weight_target_kg,
    }


def _log_meal(session: Session, user_id: uuid.UUID, args: LogMealArgs) -> dict:
    today = date.today()
    payloads = [
        EntryCreate(
            **{
                **item.model_dump(exclude_none=True),
                "consumed_on": item.consumed_on or today,
            }
        )
        for item in args.items
    ]
    created, _ = entries_service.create_entries_bulk(
        session, user_id, payloads, source=EntrySource.CHAT
    )
    return {
        "logged": [_entry_row(entry) for entry in created],
        "total_calories": sum(entry.calories for entry in created),
    }


def _update_entry(session: Session, user_id: uuid.UUID, args: UpdateEntryArgs) -> dict:
    payload = EntryUpdate(**args.model_dump(exclude={"entry_id"}, exclude_none=True))
    entry = entries_service.update_entry(session, user_id, args.entry_id, payload)
    return {"updated": _entry_row(entry)}


def _delete_entry(session: Session, user_id: uuid.UUID, args: DeleteEntryArgs) -> dict:
    # Read it first so the result can say what was removed rather than just "ok".
    entry = _entry_row(entries_service.get_entry(session, user_id, args.entry_id))
    entries_service.delete_entry(session, user_id, args.entry_id)
    return {"deleted": entry}


def _set_goal(session: Session, user_id: uuid.UUID, args: SetGoalArgs) -> dict:
    data = args.model_dump(exclude_none=True)
    # Carrying effective_from is what keeps goals versioned: a new target starts on a date
    # and never rewrites what past days were measured against.
    goal = goals_service.upsert_goal(session, user_id, GoalCreate(**data))
    return {"goal": _goal_row(goal)}


def _log_weight(session: Session, user_id: uuid.UUID, args: LogWeightArgs) -> dict:
    payload = WeightLogCreate(**args.model_dump(exclude_none=True))
    log = goals_service.record_weight(session, user_id, payload)
    return {"logged_on": log.logged_on.isoformat(), "weight_kg": log.weight_kg}


def _query_entries(session: Session, user_id: uuid.UUID, args: QueryEntriesArgs) -> dict:
    rows, total = entries_service.list_entries(
        session,
        user_id,
        PageParams(page=1, page_size=args.limit),
        date_from=args.date_from,
        date_to=args.date_to,
        meal_type=args.meal_type,
        search=args.search,
    )
    return {"entries": [_entry_row(entry) for entry in rows], "total_matching": total}


def _get_goal(session: Session, user_id: uuid.UUID, args: OnDateArgs) -> dict:
    on_date = args.on_date or date.today()
    goal = goals_service.get_goal_for_date(session, user_id, on_date)
    return {"on_date": on_date.isoformat(), "goal": _goal_row(goal)}


def _daily_summary(session: Session, user_id: uuid.UUID, args: OnDateArgs) -> dict:
    return reports_service.daily_summary(session, user_id, args.on_date or date.today())


def _goal_vs_actual(session: Session, user_id: uuid.UUID, args: DateRangeArgs) -> dict:
    rows = reports_service.goal_vs_actual(
        session,
        user_id,
        date_from=args.date_from,
        date_to=args.date_to,
        granularity=args.granularity,
    )
    return {"buckets": rows[:MAX_ROWS]}


def _nutrition_report(session: Session, user_id: uuid.UUID, args: NutritionReportArgs) -> dict:
    # Unknown metric or dimension names are rejected inside aggregate(), by the same
    # registry lookup the REST report endpoints go through. Nothing the model writes ever
    # reaches the query text.
    rows = aggregate(
        session,
        user_id,
        metrics=args.metrics,
        group_by=args.group_by,
        filters=ReportFilters(
            date_from=args.date_from,
            date_to=args.date_to,
            meal_type=args.meal_type,
            search=args.search,
        ),
    )
    return {"rows": rows[: args.limit], "row_count": len(rows)}


# ---------------------------------------------------------------------------
# Draft summaries
# ---------------------------------------------------------------------------


def _summarize_log_meal(args: LogMealArgs) -> str:
    total = sum(item.calories for item in args.items)
    if len(args.items) == 1:
        item = args.items[0]
        return f"Log {item.food_name} to {item.meal_type} — {total:g} kcal"
    return f"Log {len(args.items)} items — {total:g} kcal"


def _summarize_set_goal(args: SetGoalArgs) -> str:
    parts = []
    if args.calorie_target is not None:
        parts.append(f"{args.calorie_target:g} kcal")
    for field, label in (("protein_g", "protein"), ("carbs_g", "carbs"), ("fat_g", "fat")):
        value = getattr(args, field)
        if value is not None:
            parts.append(f"{value:g}g {label}")
    if args.weight_target_kg is not None:
        parts.append(f"{args.weight_target_kg:g}kg target weight")
    when = args.effective_from or date.today()
    return f"Set goal from {when.isoformat()} — {', '.join(parts) if parts else 'no targets'}"


def _summarize_update_entry(args: UpdateEntryArgs) -> str:
    changed = args.model_dump(exclude={"entry_id"}, exclude_none=True)
    return f"Update entry — change {', '.join(changed) if changed else 'nothing'}"


def _summarize_delete_entry(_: DeleteEntryArgs) -> str:
    return "Delete this entry"


def _summarize_log_weight(args: LogWeightArgs) -> str:
    when = args.logged_on or date.today()
    return f"Record {args.weight_kg:g} kg for {when.isoformat()}"


# ---------------------------------------------------------------------------
# The registry
# ---------------------------------------------------------------------------

_REPORT_DESCRIPTION = (
    "Aggregate the user's nutrition data. Use for any 'how much', 'top', 'average' or "
    "'compare' question. Sums each metric, optionally grouped.\n"
    f"metrics: {', '.join(sorted(METRICS))}.\n"
    f"group_by: {', '.join(sorted(DIMENSIONS))}. Omit group_by for an overall total."
)

TOOLS: dict[str, Tool] = {
    tool.name: tool
    for tool in (
        Tool(
            name="log_meal",
            description=(
                "Log one or more foods the user ate. Estimate nutrition from your own "
                "knowledge when the user does not give figures; the user reviews every "
                "number before it is saved."
            ),
            args_model=LogMealArgs,
            handler=_log_meal,
            writes=True,
            summarize=_summarize_log_meal,
        ),
        Tool(
            name="update_entry",
            description="Change an already-logged entry. Find its id with query_entries first.",
            args_model=UpdateEntryArgs,
            handler=_update_entry,
            writes=True,
            summarize=_summarize_update_entry,
        ),
        Tool(
            name="delete_entry",
            description="Remove a logged entry. Find its id with query_entries first.",
            args_model=DeleteEntryArgs,
            handler=_delete_entry,
            writes=True,
            summarize=_summarize_delete_entry,
        ),
        Tool(
            name="set_goal",
            description=(
                "Set nutrition targets from a date onward. Past days keep the targets they "
                "were measured against, so this never rewrites history."
            ),
            args_model=SetGoalArgs,
            handler=_set_goal,
            writes=True,
            summarize=_summarize_set_goal,
        ),
        Tool(
            name="log_weight",
            description="Record the user's body weight for a day.",
            args_model=LogWeightArgs,
            handler=_log_weight,
            writes=True,
            summarize=_summarize_log_weight,
        ),
        Tool(
            name="query_entries",
            description="List the user's logged entries, filtered by date, meal or food name.",
            args_model=QueryEntriesArgs,
            handler=_query_entries,
        ),
        Tool(
            name="get_goal",
            description="Read the nutrition targets in force on a date.",
            args_model=OnDateArgs,
            handler=_get_goal,
        ),
        Tool(
            name="daily_summary",
            description="Totals for one day, broken down by meal and compared to that day's goal.",
            args_model=OnDateArgs,
            handler=_daily_summary,
        ),
        Tool(
            name="goal_vs_actual",
            description=(
                "Intake against the goal in force, bucket by bucket over a date range. Use "
                "for 'how am I doing this week' and progress questions."
            ),
            args_model=DateRangeArgs,
            handler=_goal_vs_actual,
        ),
        Tool(
            name="nutrition_report",
            description=_REPORT_DESCRIPTION,
            args_model=NutritionReportArgs,
            handler=_nutrition_report,
        ),
    )
}
