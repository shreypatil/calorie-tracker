"""The default provider: deterministic, offline, no API key.

This is what makes `git clone && make dev` demo the whole import flow with no
credentials, and what the test suite runs against — so those tests are fast,
free, and give the same answer every time.

It infers the mapping by keyword-matching column headers. That is genuinely
weaker than a model on unusual documents, which is the point: it is a stand-in,
not a competitor. What it must get right is the *shape* of the answer, so every
downstream stage is exercised exactly as it would be in production.
"""

import re

# Imported by module path, not `from app.ai import ...`: this module is itself imported
# while `app.ai` is still initializing, and the package attribute does not exist yet.
from app.ai.stub_chat import converse as converse_stub
from app.db.models import MealType
from app.schemas.chat import AssistantTurn, ProviderMessage, ToolSpec
from app.schemas.import_ import (
    ColumnMapping,
    DateFormat,
    NutritionBasis,
    RawEntry,
    TableMapping,
    TableSample,
)
from app.schemas.photo import PhotoExtraction, PhotoKind, RawFoodItem

#: Header keywords → entry field, most specific first. Order matters: "sugar"
#: must be tested before "sug"-free generic matches, and "carb" before "cal"
#: never collides because the patterns are checked as substrings of a
#: normalized header.
HEADER_PATTERNS: tuple[tuple[str, str], ...] = (
    ("date", "consumed_on"),
    ("day", "consumed_on"),
    ("meal", "meal_type"),
    ("time", "meal_type"),
    ("food", "food_name"),
    ("item", "food_name"),
    ("description", "food_name"),
    ("name", "food_name"),
    ("qty", "quantity"),
    ("quantity", "quantity"),
    ("serving", "quantity"),
    ("amount", "quantity"),
    ("portion", "quantity"),
    ("unit", "unit"),
    ("energy", "calories"),
    ("kcal", "calories"),
    ("calorie", "calories"),
    ("cals", "calories"),
    ("cal", "calories"),
    ("protein", "protein_g"),
    ("carb", "carbs_g"),
    ("fat", "fat_g"),
    ("fibre", "fiber_g"),
    ("fiber", "fiber_g"),
    ("sugar", "sugar_g"),
    ("sodium", "sodium_mg"),
    ("salt", "sodium_mg"),
    ("potassium", "potassium_mg"),
    ("calcium", "calcium_mg"),
    ("iron", "iron_mg"),
    ("cholesterol", "cholesterol_mg"),
    ("vitamin a", "vitamin_a_mcg"),
    ("vitamin c", "vitamin_c_mg"),
    ("vitamin d", "vitamin_d_mcg"),
    ("b12", "vitamin_b12_mcg"),
)

_DMY = re.compile(r"^\s*(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\s*$")
_ISO = re.compile(r"^\s*\d{4}-\d{2}-\d{2}\s*$")


def _normalize(header: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", header.lower()).strip()


def guess_target(header: str) -> str | None:
    """Best-guess entry field for a column header, or None."""
    normalized = _normalize(header)
    for keyword, target in HEADER_PATTERNS:
        if keyword in normalized:
            return target
    return None


def guess_date_format(values: list[str]) -> DateFormat:
    """Infer day/month order from values where only one reading is possible.

    A column of `03/04`-style dates is genuinely ambiguous. One value with a
    first part above 12 settles it — that is the same evidence a person uses.
    """
    if any(_ISO.match(value) for value in values if value):
        return DateFormat.ISO

    for value in values:
        match = _DMY.match(value or "")
        if not match:
            continue
        first, second = int(match.group(1)), int(match.group(2))
        if first > 12:
            return DateFormat.DMY
        if second > 12:
            return DateFormat.MDY

    # Nothing decisive. Day-first is the more common convention worldwide, and
    # the user can flip it in one click.
    return DateFormat.DMY


class StubProvider:
    """Keyword-based mapping inference. No network, no key, fully deterministic."""

    name = "stub"

    def infer_table_mapping(self, sample: TableSample) -> TableMapping:
        columns: list[ColumnMapping] = []
        quantity_column: str | None = None

        for header in sample.headers:
            target = guess_target(header)
            if target is None:
                continue
            if target == "quantity":
                quantity_column = header
            # A keyword match is a decent but not certain read of intent.
            columns.append(ColumnMapping(source=header, target=target, confidence=0.8))

        date_values = self._column_values(sample, "consumed_on", columns)
        mapped = {column.target for column in columns}

        return TableMapping(
            columns=columns,
            date_format=guess_date_format(date_values),
            basis=self._guess_basis(sample.headers),
            quantity_column=quantity_column,
            # With no meal column the rows still have to land somewhere; snack
            # is the least wrong bucket and the review table flags every row.
            default_meal_type=None if "meal_type" in mapped else MealType.SNACK,
            notes="Columns matched by name. Check the date format and meal types before importing.",
        )

    def extract_entries_from_text(self, chunk: str) -> list[RawEntry]:
        """Read `<food> ... <number> cal` lines out of a prose diary."""
        entries: list[RawEntry] = []
        current_date: str | None = None
        current_meal: str | None = None

        for line in chunk.splitlines():
            stripped = line.strip()
            if not stripped:
                continue

            if _ISO.match(stripped) or _DMY.match(stripped):
                current_date = stripped
                continue

            lowered = stripped.lower().rstrip(":")
            if lowered in {"breakfast", "lunch", "dinner", "snack", "snacks"}:
                current_meal = lowered
                continue

            calories = re.search(r"(\d[\d,]*(?:\.\d+)?)\s*(?:kcal|cal)\b", stripped, re.I)
            if not calories:
                continue

            name = stripped[: calories.start()].strip(" ,-–—\t")
            if not name:
                continue

            entries.append(
                RawEntry(
                    consumed_on=current_date,
                    meal_type=current_meal,
                    food_name=name[:200],
                    calories=float(calories.group(1).replace(",", "")),
                )
            )

        return entries

    def converse(self, messages: list[ProviderMessage], tools: list[ToolSpec]) -> AssistantTurn:
        """Regex intent matching — see `stub_chat` for the phrasings it understands."""
        return converse_stub(messages, tools)

    def analyze_image(self, image, kind: PhotoKind) -> PhotoExtraction:
        """A fixed draft — the stub cannot see, so it stands in for what a model would say.

        The label transcript deliberately contains every figure the label item reports, so the
        caller's verification step runs for real rather than being trivially skipped. Change
        one without the other and `test_photo.py` will notice.
        """
        if kind is PhotoKind.LABEL:
            return PhotoExtraction(
                kind=PhotoKind.LABEL,
                transcript=(
                    "ROLLED OATS\n"
                    "Nutrition Information\n"
                    "Servings per pack: 10   Serving size: 40 g\n"
                    "Per 100 g\n"
                    "Energy 379 kcal\n"
                    "Protein 13.2 g\n"
                    "Carbohydrate 67.7 g\n"
                    "Fat 6.5 g\n"
                    "Fibre 10.1 g\n"
                    "Sugars 1.1 g\n"
                    "Sodium 6 mg\n"
                ),
                basis=NutritionBasis.PER_100G,
                serving_size_g=40,
                items=[
                    RawFoodItem(
                        food_name="Rolled Oats",
                        calories=379,
                        protein_g=13.2,
                        carbs_g=67.7,
                        fat_g=6.5,
                        fiber_g=10.1,
                        sugar_g=1.1,
                        sodium_mg=6,
                    )
                ],
                notes="Read from the per-100 g column.",
                confidence=0.9,
            )

        return PhotoExtraction(
            kind=PhotoKind.MEAL,
            basis=NutritionBasis.PER_SERVING,
            items=[
                RawFoodItem(
                    food_name="Grilled chicken breast",
                    quantity=150,
                    unit="g",
                    calories=248,
                    protein_g=46.5,
                    carbs_g=0,
                    fat_g=5.4,
                ),
                RawFoodItem(
                    food_name="White rice",
                    quantity=200,
                    unit="g",
                    calories=260,
                    protein_g=5.4,
                    carbs_g=56.2,
                    fat_g=0.6,
                ),
                RawFoodItem(
                    food_name="Green salad",
                    quantity=80,
                    unit="g",
                    calories=33,
                    protein_g=1.6,
                    carbs_g=5.8,
                    fat_g=0.6,
                ),
            ],
            notes="Portion sizes estimated from the plate.",
            confidence=0.6,
        )

    @staticmethod
    def _guess_basis(headers: list[str]) -> NutritionBasis:
        joined = " ".join(headers).lower()
        if "100g" in joined.replace(" ", "") or "per 100" in joined:
            return NutritionBasis.PER_100G
        return NutritionBasis.PER_SERVING

    @staticmethod
    def _column_values(sample: TableSample, target: str, columns: list[ColumnMapping]) -> list[str]:
        headers = [column.source for column in columns if column.target == target]
        if not headers:
            return []
        index = sample.headers.index(headers[0])
        return [row[index] for row in sample.rows if index < len(row)]
