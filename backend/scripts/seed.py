"""Seed a demo account with 30 days of realistic data.

Run with `python -m scripts.seed` (or `make seed`). Safe to re-run: it clears
the demo user's existing data first, so the dataset stays reproducible — which
also makes it usable as a fixture for eyeballing the reports in Phase 2.
"""

import random
from datetime import date, timedelta

from sqlalchemy import delete, select

from app.core.security import hash_password
from app.db.models import FoodEntry, Goal, MealType, User, WeightLog
from app.db.session import SessionLocal

DEMO_EMAIL = "demo@example.com"
DEMO_PASSWORD = "demo-password-1234"
DAYS = 30

# (name, unit, calories, protein_g, carbs_g, fat_g, fiber_g, sodium_mg)
BREAKFASTS = [
    ("Oatmeal with banana", "bowl", 320, 11, 54, 6, 8, 140),
    ("Scrambled eggs on toast", "plate", 400, 22, 30, 21, 3, 520),
    ("Greek yoghurt with berries", "cup", 210, 18, 24, 4, 4, 80),
    ("Poha", "plate", 270, 6, 45, 8, 3, 380),
]
LUNCHES = [
    ("Grilled chicken salad", "bowl", 480, 42, 18, 26, 6, 620),
    ("Rajma chawal", "plate", 620, 21, 96, 14, 12, 700),
    ("Turkey sandwich", "sandwich", 520, 30, 55, 18, 5, 980),
    ("Paneer wrap", "wrap", 560, 24, 52, 28, 4, 840),
]
DINNERS = [
    ("Salmon with quinoa", "plate", 610, 44, 45, 26, 7, 480),
    ("Dal, rice and sabzi", "plate", 540, 18, 84, 13, 11, 650),
    ("Stir-fried tofu and noodles", "bowl", 580, 26, 68, 22, 6, 900),
    ("Chicken curry with roti", "plate", 650, 38, 62, 27, 5, 760),
]
SNACKS = [
    ("Apple", "piece", 95, 0.5, 25, 0.3, 4, 2),
    ("Almonds", "handful", 170, 6, 6, 15, 3, 1),
    ("Protein shake", "glass", 160, 25, 8, 3, 1, 120),
]


def _entry(user_id, on_date: date, meal: MealType, spec: tuple) -> FoodEntry:
    name, unit, kcal, protein, carbs, fat, fiber, sodium = spec
    return FoodEntry(
        user_id=user_id,
        consumed_on=on_date,
        meal_type=meal,
        food_name=name,
        quantity=1,
        unit=unit,
        calories=kcal,
        protein_g=protein,
        carbs_g=carbs,
        fat_g=fat,
        fiber_g=fiber,
        sodium_mg=sodium,
    )


def seed() -> None:
    rng = random.Random(42)  # fixed seed: the demo dataset is reproducible
    session = SessionLocal()
    try:
        user = session.scalar(select(User).where(User.email == DEMO_EMAIL))
        if user is None:
            user = User(
                email=DEMO_EMAIL,
                password_hash=hash_password(DEMO_PASSWORD),
                display_name="Demo User",
            )
            session.add(user)
            session.commit()
            session.refresh(user)
        else:
            for model in (FoodEntry, Goal, WeightLog):
                session.execute(delete(model).where(model.user_id == user.id))
            session.commit()

        today = date.today()

        # Two goal versions, so goal-vs-actual has real history to compare.
        session.add_all(
            [
                Goal(
                    user_id=user.id,
                    effective_from=today - timedelta(days=DAYS),
                    calorie_target=2000,
                    protein_g=130,
                    carbs_g=230,
                    fat_g=65,
                    weight_target_kg=72.0,
                    micro_targets={"fiber_g": 30, "sodium_mg": 2300},
                ),
                Goal(
                    user_id=user.id,
                    effective_from=today - timedelta(days=10),
                    calorie_target=2200,
                    protein_g=150,
                    carbs_g=240,
                    fat_g=70,
                    weight_target_kg=70.0,
                    micro_targets={"fiber_g": 35, "sodium_mg": 2300},
                ),
            ]
        )

        entries: list[FoodEntry] = []
        weights: list[WeightLog] = []
        for offset in range(DAYS):
            day = today - timedelta(days=offset)

            entries.append(_entry(user.id, day, MealType.BREAKFAST, rng.choice(BREAKFASTS)))
            entries.append(_entry(user.id, day, MealType.LUNCH, rng.choice(LUNCHES)))
            entries.append(_entry(user.id, day, MealType.DINNER, rng.choice(DINNERS)))
            # Snacks on most but not all days, so trends are not perfectly flat.
            if rng.random() < 0.7:
                entries.append(_entry(user.id, day, MealType.SNACK, rng.choice(SNACKS)))

            if offset % 3 == 0:
                weights.append(
                    WeightLog(
                        user_id=user.id,
                        logged_on=day,
                        weight_kg=round(74.5 - (DAYS - offset) * 0.05 + rng.uniform(-0.3, 0.3), 1),
                    )
                )

        session.add_all(entries + weights)
        session.commit()

        print(f"Seeded {len(entries)} entries and {len(weights)} weight logs.")
        print(f"Login with {DEMO_EMAIL} / {DEMO_PASSWORD}")
    finally:
        session.close()


if __name__ == "__main__":
    seed()
