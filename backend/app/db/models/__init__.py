"""All ORM models.

Imported as a unit so Alembic autogenerate and `Base.metadata.create_all` see
every table.
"""

from app.db.models.chat_message import ChatMessage, ChatRole
from app.db.models.food_entry import (
    MACRONUTRIENT_FIELDS,
    MICRONUTRIENT_FIELDS,
    EntrySource,
    FoodEntry,
    MealType,
)
from app.db.models.goal import Goal
from app.db.models.import_batch import ImportBatch
from app.db.models.user import RefreshToken, User
from app.db.models.weight_log import WeightLog

__all__ = [
    "MACRONUTRIENT_FIELDS",
    "MICRONUTRIENT_FIELDS",
    "ChatMessage",
    "ChatRole",
    "EntrySource",
    "FoodEntry",
    "Goal",
    "ImportBatch",
    "MealType",
    "RefreshToken",
    "User",
    "WeightLog",
]
