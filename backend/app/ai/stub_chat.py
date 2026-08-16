"""Deterministic conversation for the keyless stub provider.

FR-6 requires that the chat be fully exercisable with no API key, which means something has to
turn "log two eggs and toast for breakfast" into a `log_meal` call without a model. This does
it with ordered regex intents and a small table of common foods.

It is unapologetically weaker than a language model — it understands the phrasings listed
below and little else. That is the same bargain `stub.py` strikes for import mapping: what a
stub must get right is the *shape* of the answer, so that the agent loop, the confirmation
gate, the tool dispatcher and the web app are all exercised exactly as they would be in
production. Reviewers get a working demo on a fresh clone; the test suite gets an oracle that
is free, offline, and identical on every run.

The nutrition figures below are ordinary reference values for one common serving. They stand
in for the estimate a real model would make, and — like a real model's — the user sees and
confirms them before anything is written.
"""

import json
import re
from datetime import date, timedelta
from typing import NamedTuple

from app.schemas.chat import AssistantTurn, ProviderMessage, ToolCall
from app.schemas.nutrition import NutritionEstimate, NutritionEstimateRequest


class StubNutrition(NamedTuple):
    """One serving of a food the stub happens to know about.

    Named rather than a bare tuple because it grew from four fields to seven when nutrition
    estimation needed fibre, sugar and sodium, and positional unpacking of seven numbers is how
    silent transposition bugs happen.
    """

    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float
    sugar_g: float
    sodium_mg: float


#: Ordinary reference values for one common serving. The stub cannot look anything up, so this is
#: what stands in for a model's knowledge — small, deterministic, and enough to exercise every
#: downstream path with no API key.
STUB_FOODS: dict[str, StubNutrition] = {
    "egg": StubNutrition(78, 6.3, 0.6, 5.3, 0.0, 0.6, 62),
    "toast": StubNutrition(75, 2.6, 13.0, 1.0, 1.1, 1.4, 144),
    "bread": StubNutrition(75, 2.6, 13.0, 1.0, 1.1, 1.4, 144),
    "rice": StubNutrition(206, 4.3, 44.5, 0.4, 0.6, 0.1, 2),
    "chicken": StubNutrition(231, 43.4, 0.0, 5.0, 0.0, 0.0, 104),
    "salad": StubNutrition(33, 2.0, 6.0, 0.3, 2.2, 2.4, 27),
    "apple": StubNutrition(95, 0.5, 25.0, 0.3, 4.4, 19.0, 2),
    "banana": StubNutrition(105, 1.3, 27.0, 0.4, 3.1, 14.4, 1),
    "coffee": StubNutrition(2, 0.3, 0.0, 0.0, 0.0, 0.0, 5),
    "milk": StubNutrition(103, 8.0, 12.0, 2.4, 0.0, 12.0, 107),
    "oats": StubNutrition(154, 5.3, 27.4, 2.6, 4.0, 0.6, 9),
    "yogurt": StubNutrition(149, 8.5, 11.4, 8.0, 0.0, 11.4, 113),
    "pasta": StubNutrition(221, 8.1, 43.2, 1.3, 2.5, 0.8, 1),
    "sandwich": StubNutrition(350, 15.0, 40.0, 14.0, 3.0, 5.0, 700),
}

MEAL_WORDS = ("breakfast", "lunch", "dinner", "snack")

_NUMBER = r"(\d+(?:\.\d+)?)"
_WEIGHT = re.compile(rf"{_NUMBER}\s*(?:kg|kilos?|kilograms?)", re.I)
_LEADING_QUANTITY = re.compile(rf"^{_NUMBER}\s*(?:x\s*)?")
#: Goal field → the words that introduce it. A target is written either way round —
#: "2200 calories" and "calorie goal to 2200" are both common — so both are matched.
_GOAL_LABELS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("calorie_target", ("calorie", "kcal", "cal")),
    ("protein_g", ("protein",)),
    ("carbs_g", ("carb",)),
    ("fat_g", ("fat",)),
)

_CALL_COUNTER = "stub-call"


def _call(index: int, name: str, arguments: dict) -> ToolCall:
    return ToolCall(id=f"{_CALL_COUNTER}-{index}", name=name, arguments=arguments)


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _meal_type(text: str) -> str:
    for word in MEAL_WORDS:
        if word in text:
            return word
    # Nothing said. Snack is the least wrong bucket, and the draft is editable.
    return "snack"


def _split_items(text: str) -> list[str]:
    """Break "2 eggs, toast and a coffee" into its parts."""
    cleaned = re.sub(
        r"^\s*(?:please\s+)?(?:log|add|record|i\s+ate|i\s+had|ate|had|eat)\b",
        "",
        text,
        flags=re.I,
    )
    cleaned = re.sub(rf"\bfor\s+({'|'.join(MEAL_WORDS)})\b.*$", "", cleaned, flags=re.I)
    cleaned = re.sub(rf"\b({'|'.join(MEAL_WORDS)})\b", "", cleaned, flags=re.I)
    parts = re.split(r",|\band\b|\bwith\b|\+", cleaned, flags=re.I)
    return [part.strip(" .!?\t") for part in parts if part.strip(" .!?\t")]


def _nutrition(name: str) -> StubNutrition:
    lowered = name.lower()
    for keyword, values in STUB_FOODS.items():
        if keyword in lowered:
            return values
    # Unknown food: zeros, so the draft card shows the gap and the user fills it in rather
    # than a fabricated number slipping through unnoticed.
    return StubNutrition(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)


def _meal_items(text: str) -> list[dict]:
    meal = _meal_type(text)
    items: list[dict] = []

    for part in _split_items(text):
        quantity = 1.0
        match = _LEADING_QUANTITY.match(part)
        if match:
            quantity = float(match.group(1))
            part = part[match.end() :].strip()
        part = re.sub(r"^(?:an?|some|the)\s+", "", part, flags=re.I).strip()
        if not part:
            continue

        food = _nutrition(part)
        items.append(
            {
                "food_name": part[:200],
                "meal_type": meal,
                "quantity": quantity,
                "unit": "serving",
                "calories": round(food.calories * quantity, 1),
                "protein_g": round(food.protein_g * quantity, 1),
                "carbs_g": round(food.carbs_g * quantity, 1),
                "fat_g": round(food.fat_g * quantity, 1),
            }
        )
    return items


def _target_value(text: str, labels: tuple[str, ...]) -> float | None:
    """Find the number that belongs to a target label, on whichever side it sits."""
    for label in labels:
        before = re.search(rf"{_NUMBER}\s*(?:g|kcal)?\s*(?:of\s+)?\b{label}", text, re.I)
        if before:
            return float(before.group(1))
        # "calorie goal to 2200" — allow a few words between the label and its number,
        # but no sentence break, so a second clause cannot donate its figure.
        after = re.search(rf"\b{label}[a-z]*\b[^.\d]{{0,20}}?{_NUMBER}", text, re.I)
        if after:
            return float(after.group(1))
    return None


def estimate_nutrition(request: NutritionEstimateRequest) -> NutritionEstimate:
    """Deterministic stand-in for a model's nutritional knowledge.

    Keyword-matches the food name against `STUB_FOODS` and scales by the stated quantity. It knows
    fourteen foods and nothing else, which is the point: it is a stand-in, not a competitor. What it
    must get right is the *shape* — only the requested fields, scaled sensibly — so the service,
    the endpoint and the form are all exercised exactly as they would be with a real provider.
    """
    food = _nutrition(request.food_name)
    known = set(request.known)

    # A quantity in grams describes a weight, not a count of servings: 350 g of rice is three and a
    # half of this table's servings, not three hundred and fifty of them.
    quantity = request.quantity or 1.0
    if (request.unit or "").strip().lower() in {"g", "gram", "grams"}:
        factor = quantity / 100.0
    else:
        factor = quantity

    values = {
        field: round(getattr(food, field) * factor, 1)
        for field in request.fields
        # Anchors are never returned; the caller keeps whatever the user typed.
        if field not in known
    }

    recognised = any(getattr(food, field) for field in food._fields)
    return NutritionEstimate(
        values=values,
        notes=(
            ""
            if recognised
            else "The offline estimator does not recognise this food, so the figures are zero."
        ),
        confidence=0.6 if recognised else 0.1,
    )


def _last_user_message(messages: list[ProviderMessage]) -> str:
    for message in reversed(messages):
        if message.role == "user":
            return message.content
    return ""


# ---------------------------------------------------------------------------
# Intent matching
# ---------------------------------------------------------------------------


def _intent_calls(text: str) -> tuple[str, list[ToolCall]]:
    """Map one user message to tool calls, or to a plain reply."""
    lowered = text.lower()
    today = date.today()

    if "weigh" in lowered and (match := _WEIGHT.search(lowered)):
        return "", [_call(0, "log_weight", {"weight_kg": float(match.group(1))})]

    wants_goal = "goal" in lowered or "target" in lowered
    if wants_goal:
        targets = {
            field: value
            for field, labels in _GOAL_LABELS
            if (value := _target_value(lowered, labels)) is not None
        }
        if targets and re.search(r"\b(set|change|update|make|raise|lower)\b", lowered):
            return "", [_call(0, "set_goal", targets)]
        return "", [_call(0, "get_goal", {})]

    if re.search(r"what did i (eat|have)|show|list|entries|find|search", lowered):
        args: dict = {"limit": 20}
        if "yesterday" in lowered:
            yesterday = (today - timedelta(days=1)).isoformat()
            args |= {"date_from": yesterday, "date_to": yesterday}
        elif "today" in lowered:
            args |= {"date_from": today.isoformat(), "date_to": today.isoformat()}
        for word in MEAL_WORDS:
            if word in lowered:
                args["meal_type"] = word
        return "", [_call(0, "query_entries", args)]

    if re.search(r"how am i|progress|on track|doing this", lowered) or re.search(
        r"\b(week|month)\b", lowered
    ):
        span = 30 if "month" in lowered else 7
        granularity = "week" if "week" in lowered and span == 30 else "day"
        return "", [
            _call(
                0,
                "goal_vs_actual",
                {
                    "date_from": (today - timedelta(days=span - 1)).isoformat(),
                    "date_to": today.isoformat(),
                    "granularity": granularity,
                },
            )
        ]

    if re.search(r"top|most|breakdown|average|by food|by meal", lowered):
        group_by = ["food_name"] if "food" in lowered or "top" in lowered else ["meal_type"]
        return "", [_call(0, "nutrition_report", {"metrics": ["calories"], "group_by": group_by})]

    if re.search(r"today|summary|so far|total", lowered):
        return "", [_call(0, "daily_summary", {})]

    if re.search(r"\b(log|add|record|ate|had|eat)\b", lowered):
        items = _meal_items(text)
        if items:
            return "", [_call(0, "log_meal", {"items": items})]

    return (
        "I can log meals, read and set your goals, look up what you've eaten, and summarise "
        "your intake. Try “log 2 eggs and toast for breakfast”, “what's my goal?”, or "
        "“how am I doing this week?”.",
        [],
    )


# ---------------------------------------------------------------------------
# Rendering a tool result back into prose
# ---------------------------------------------------------------------------


def _summarize_result(tool: str, payload: dict) -> str:
    if error := payload.get("error"):
        return f"That didn't work: {error}"

    if tool == "query_entries":
        entries = payload.get("entries", [])
        if not entries:
            return "I couldn't find any entries matching that."
        listed = ", ".join(
            f"{entry['food_name']} ({entry['calories']:g} kcal)" for entry in entries[:5]
        )
        total = payload.get("total_matching", len(entries))
        noun = "entry" if total == 1 else "entries"
        return f"Found {total} matching {noun}. Most recent: {listed}."

    if tool == "get_goal":
        goal = payload.get("goal")
        if not goal:
            return "You haven't set a goal yet."
        target = goal.get("calorie_target")
        if not target:
            return f"Your goal from {goal['effective_from']} has no calorie target set."
        return f"Your goal from {goal['effective_from']} is {target:g} kcal a day."

    if tool == "daily_summary":
        totals = payload.get("totals", {})
        return (
            f"You've logged {totals.get('calories', 0):g} kcal today across "
            f"{int(totals.get('entry_count', 0))} entries."
        )

    if tool == "goal_vs_actual":
        buckets = payload.get("buckets", [])
        logged = [b for b in buckets if b.get("calories")]
        if not logged:
            return "Nothing logged in that period."
        average = sum(b["calories"] for b in logged) / len(logged)
        return (
            f"Over {len(buckets)} days you logged on {len(logged)} of them, "
            f"averaging {average:.0f} kcal on the days you logged."
        )

    if tool == "nutrition_report":
        rows = payload.get("rows", [])
        if not rows:
            return "No data for that."
        top = sorted(rows, key=lambda row: row.get("calories", 0), reverse=True)[:5]
        listed = ", ".join(
            f"{next(iter(row.values()))} ({row.get('calories', 0):.0f} kcal)" for row in top
        )
        return f"{len(rows)} groups. Highest by calories: {listed}."

    return "Done."


def converse(messages: list[ProviderMessage], _tools: list) -> AssistantTurn:
    """The stub's whole conversational behaviour.

    Two states, which is all the agent loop needs: a fresh user message produces tool calls,
    and a message whose tool results have come back produces the prose answer that ends the
    turn.
    """
    last = messages[-1] if messages else None
    if last is not None and last.role == "tool":
        try:
            payload = json.loads(last.content)
        except (json.JSONDecodeError, TypeError):
            payload = {}
        return AssistantTurn(content=_summarize_result(last.name or "", payload))

    content, calls = _intent_calls(_last_user_message(messages))
    return AssistantTurn(content=content, tool_calls=calls)
