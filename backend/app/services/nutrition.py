"""Checks and conversions that apply to nutrition figures from any source.

These three functions were each written for one caller and then needed by a second. They live
here so the PDF import path and the photo path cannot drift into two slightly different ideas
of what "this number is trustworthy" means.

`appears_in_source` and `atwater_gap` are both *verification*, and they exist because of a
constraint the project keeps running into: wherever a model transcribes rather than describes,
its output has to be checked by something that cannot hallucinate. For a prose diary the check
is against the document text; for a photographed label it is against the model's own verbatim
transcript of the panel. Same function, different source.
"""

import re

#: Calories per gram — the Atwater factors, the arithmetic every nutrition panel obeys.
KCAL_PER_GRAM = {"protein_g": 4.0, "carbs_g": 4.0, "fat_g": 9.0}


def appears_in_source(value: float, source: str) -> bool:
    """Is this number actually written in the source text?

    Matches the digits as they would be typed — `320`, `320.0` and `1,234` all count — with a
    boundary check so 32 does not match inside 320.
    """
    candidates = {f"{value:g}", f"{value:.0f}", f"{value:.1f}"}
    if value >= 1000:
        candidates.add(f"{value:,.0f}")
    return any(re.search(rf"(?<![\d.]){re.escape(text)}(?![\d.])", source) for text in candidates)


def atwater_gap(values: dict) -> float | None:
    """How far the stated calories sit from what the macros imply, as a fraction.

    A nutrition panel is arithmetic: calories come from protein, carbohydrate and fat at 4, 4
    and 9 kcal per gram. When a digit is misread — 250 becoming 850 — the sum stops matching,
    which is a signal no amount of plausibility can fake.

    Returns `None` unless there is a complete set to compare — calories plus *all three*
    macros. A partial set is not a weaker signal, it is a meaningless one: with fat missing,
    the implied total is guaranteed to fall short and every such row would be flagged.

    The result is a *gap*, not a verdict — fibre, sugar alcohols and alcohol itself all make
    honest deviation possible, so the caller flags rather than rejects.
    """
    calories = values.get("calories")
    if not isinstance(calories, int | float) or calories <= 0:
        return None

    macros = {}
    for field in KCAL_PER_GRAM:
        value = values.get(field)
        if not isinstance(value, int | float):
            return None
        macros[field] = value

    implied = sum(amount * KCAL_PER_GRAM[field] for field, amount in macros.items())
    if implied <= 0:
        return None
    return abs(calories - implied) / calories


def scale_per_100g(values: dict, grams: float, fields: tuple[str, ...]) -> None:
    """Rewrite per-100g figures in place to describe `grams` of the food.

    The quantity becomes 1, not `grams`: after scaling, the numbers already describe the whole
    portion, so the entry is one serving of that size rather than many servings.
    """
    factor = grams / 100
    for field in fields:
        if field in values and isinstance(values[field], int | float):
            values[field] = round(values[field] * factor, 3)

    values["quantity"] = 1.0
    values.setdefault("unit", f"{grams:g} g")
