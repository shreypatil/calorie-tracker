"""Turning what the model reported into draft rows we are willing to show.

A photograph has no text layer, so unlike the PDF mapping path there is no way to construct
the numbers from the document ourselves — whatever reads the digits is a model. The answer is
the one `imports/prose.py` already uses: let it transcribe, then check the transcription.

Two checks, doing different jobs:

**Every label figure must appear in the model's own verbatim transcript of the panel.** This
catches the failure that actually matters — a plausible value supplied from world knowledge
rather than read off the packet, which is indistinguishable from a correct one by eye. A number
that is not in the transcript is dropped and the field flagged, never silently kept.

**The macros must add up.** Calories are 4/4/9 per gram of protein, carbohydrate and fat, so a
misread digit usually stops the arithmetic closing. This one *flags* rather than drops: fibre,
alcohol and sugar alcohols all make honest deviation possible, and a wrongly deleted correct
value is worse than a warned-about right one.

Neither check applies to a plate of food, where nothing is written down and every figure is an
estimate by construction. That case is handled by never pretending otherwise: the rows say they
are estimates, stay editable, and are never marked `ok`.
"""

from app.core.logging import logger
from app.db.models import MACRONUTRIENT_FIELDS, MICRONUTRIENT_FIELDS, EntrySource, MealType
from app.schemas.entry import EntryCreate
from app.schemas.import_ import DraftRow, NutritionBasis, RowIssue, RowStatus
from app.schemas.photo import PhotoDraft, PhotoExtraction, PhotoKind, RawFoodItem
from app.services.nutrition import appears_in_source, atwater_gap, scale_per_100g

NUMERIC_FIELDS: tuple[str, ...] = ("calories", *MACRONUTRIENT_FIELDS, *MICRONUTRIENT_FIELDS)

#: How far the stated calories may sit from what the macros imply before it is worth saying so.
#: Loose enough that fibre and rounding on a real panel do not trip it, tight enough to catch a
#: transposed or misread digit.
ATWATER_TOLERANCE = 0.25

#: Below this the model is telling us it struggled, and the user should be told too.
LOW_CONFIDENCE = 0.5


def _verified_values(item: RawFoodItem, transcript: str, issues: list[RowIssue]) -> dict:
    """Keep the figures that are actually written on the label; drop and flag the rest."""
    values: dict = {}
    for field in NUMERIC_FIELDS:
        value = getattr(item, field, None)
        if value is None:
            continue
        if not appears_in_source(float(value), transcript):
            logger.warning(
                "photo_value_not_in_transcript",
                extra={"field": field, "value": value, "food_name": item.food_name},
            )
            issues.append(
                RowIssue(
                    field=field,
                    message=(
                        f"Dropped a {field.replace('_', ' ')} value that does not appear on "
                        "the label — please enter it yourself."
                    ),
                )
            )
            continue
        values[field] = float(value)
    return values


def _estimated_values(item: RawFoodItem) -> dict:
    return {
        field: float(value)
        for field in NUMERIC_FIELDS
        if (value := getattr(item, field, None)) is not None
    }


def _check_arithmetic(values: dict, issues: list[RowIssue]) -> None:
    gap = atwater_gap(values)
    if gap is not None and gap > ATWATER_TOLERANCE:
        issues.append(
            RowIssue(
                field="calories",
                message=(
                    f"The calories are {gap:.0%} away from what the protein, carbs and fat add "
                    "up to. One of these may have been misread."
                ),
            )
        )


def _to_draft(
    index: int, item: RawFoodItem, extraction: PhotoExtraction, meal_type: MealType, on_date
) -> DraftRow:
    is_label = extraction.kind is PhotoKind.LABEL
    issues: list[RowIssue] = []

    values = (
        _verified_values(item, extraction.transcript, issues)
        if is_label
        else _estimated_values(item)
    )
    if not is_label:
        issues.append(RowIssue(message="Estimated from a photo — check the amounts before saving."))

    _check_arithmetic(values, issues)

    values["food_name"] = item.food_name.strip()[:200]
    values["quantity"] = item.quantity or 1.0
    # Left unset when the model gave none, so `scale_per_100g` can name the serving weight it
    # scaled to. Defaulted at the end for every path that does not.
    if item.unit:
        values["unit"] = item.unit.strip()[:30]

    if is_label and extraction.basis is NutritionBasis.PER_100G:
        if extraction.serving_size_g:
            grams = extraction.serving_size_g
            # Whatever unit the model attached describes the per-100g column, not the portion
            # these figures are about to become. Clearing it lets the scaler name the serving.
            values.pop("unit", None)
            scale_per_100g(values, grams, NUMERIC_FIELDS)
            issues.append(
                RowIssue(
                    message=(
                        f"The label is per 100 g; these figures are scaled to its stated "
                        f"{grams:g} g serving."
                    )
                )
            )
        else:
            # Left as printed rather than guessed at: "1 × 100 g" is true and editable,
            # whereas inventing a serving size would quietly change every figure.
            values["quantity"] = 1.0
            values["unit"] = "100 g"
            issues.append(
                RowIssue(
                    message=(
                        "The label is per 100 g and does not state a serving size, so the "
                        "figures are for 100 g. Adjust the quantity to what you ate."
                    )
                )
            )

    values.setdefault("unit", "serving")
    values |= {"consumed_on": on_date, "meal_type": meal_type, "source": EntrySource.PHOTO}

    if not values["food_name"]:
        issues.append(RowIssue(field="food_name", message="No food name could be read."))
        return DraftRow(index=index, status=RowStatus.INVALID, issues=issues, raw={})

    try:
        entry = EntryCreate(**values)
    except Exception as exc:  # noqa: BLE001 - surfaced to the user as an issue
        issues.append(RowIssue(message=str(exc).splitlines()[0]))
        return DraftRow(index=index, status=RowStatus.INVALID, issues=issues, raw={})

    return DraftRow(
        # Never `ok`. Whether transcribed or estimated, a photo-derived row gets a human look.
        index=index,
        status=RowStatus.NEEDS_REVIEW,
        issues=issues,
        entry=entry,
        raw={"food_name": item.food_name},
    )


def build_draft(
    extraction: PhotoExtraction,
    *,
    filename: str,
    meal_type: MealType,
    on_date,
) -> PhotoDraft:
    """Verify an extraction and package it for review. Writes nothing."""
    notes = extraction.notes
    if extraction.confidence < LOW_CONFIDENCE:
        notes = (
            f"{notes} The photo was hard to read, so these values are less reliable than usual."
        ).strip()

    rows = [
        _to_draft(index, item, extraction, meal_type, on_date)
        for index, item in enumerate(extraction.items)
    ]

    return PhotoDraft(
        kind=extraction.kind,
        source_filename=filename,
        basis=extraction.basis,
        serving_size_g=extraction.serving_size_g,
        confidence=extraction.confidence,
        notes=notes,
        rows=rows,
    )
