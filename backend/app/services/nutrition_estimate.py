"""Estimating the nutrition of a described dish (assisted manual entry).

This is the one AI path in the app with no source to check the answer against. A PDF has a text
layer, a photographed label has a transcript, and both are verified against them. A dish someone
names has nothing — the model is being asked for a judgement, and there is no way to prove it right.

So the safeguards here are different in kind, and there are three:

**Only the requested fields come back.** The filtering happens here rather than in the browser
because "never overwrite what the user typed" has to be a property of the system, not a promise the
frontend keeps. A provider that volunteers extra values, or a second caller written next year,
cannot break it.

**Values are clamped** to the same range `EntryCreate` accepts, so an absurd figure is refused at
the boundary rather than at form submission, where the user would have to work out which field was
at fault.

**Inconsistency is logged, not shown.** When the estimate does not square with what the user typed,
that is worth having in the log for diagnosis; it is deliberately not surfaced, because a warning on
every rough figure trains people to dismiss warnings.
"""

from app.ai.provider import AIProvider
from app.core.logging import logger, operation
from app.schemas.nutrition import (
    MAX_VALUE,
    NutritionEstimate,
    NutritionEstimateRequest,
)
from app.services.nutrition import atwater_gap

#: How far the estimate may sit from the user's own figures before it is worth a log line. Matches
#: the tolerance the photo path uses, for the same reason: fibre and rounding move it a little.
ATWATER_TOLERANCE = 0.25


def _clamp(value: float) -> float:
    return round(min(max(value, 0.0), MAX_VALUE), 3)


def _check_consistency(request: NutritionEstimateRequest, values: dict[str, float]) -> None:
    """Log when the estimate and the user's own numbers do not add up.

    Not surfaced to the user by design. It is a signal that either the model estimated badly or the
    user mistyped a quantity, and the log is where that belongs — a banner on every approximate
    figure would just teach people to ignore banners.
    """
    combined = {**request.known, **values}
    gap = atwater_gap(combined)
    if gap is not None and gap > ATWATER_TOLERANCE:
        logger.warning(
            "nutrition_estimate_inconsistent",
            extra={
                "food_name": request.food_name,
                "gap": round(gap, 3),
                "known": request.known,
                "estimated": values,
            },
        )


def estimate(request: NutritionEstimateRequest, provider: AIProvider) -> NutritionEstimate:
    """Estimate the fields the caller asked for. **Persists nothing.**"""
    with operation(
        "nutrition.estimate",
        food_name=request.food_name,
        quantity=request.quantity,
        unit=request.unit,
        wanted=request.fields,
        anchors=sorted(request.known),
    ):
        result = provider.estimate_nutrition(request)

    wanted = set(request.fields) - set(request.known)
    dropped = sorted(set(result.values) - wanted)
    if dropped:
        # Not an error — models volunteer extra fields routinely. Worth a line because it is also
        # what an attempt to overwrite a user's value would look like.
        logger.info(
            "nutrition_estimate_fields_dropped",
            extra={"dropped": dropped, "wanted": sorted(wanted)},
        )

    # No type check needed: `NutritionEstimate.values` is `dict[str, float]`, so a provider
    # returning "about 500" fails at the schema boundary and never reaches here.
    values = {field: _clamp(value) for field, value in result.values.items() if field in wanted}
    _check_consistency(request, values)

    return NutritionEstimate(values=values, notes=result.notes, confidence=result.confidence)
