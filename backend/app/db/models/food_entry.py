"""Food entries — the fact table the whole reporting layer aggregates over.

Design rule (see requirements.md §5.1): anything that might ever be aggregated
gets a typed column. `micros_extra` is display-only overflow for micronutrients
an AI extraction happened to find, and aggregation never reaches into it. When
a micronutrient becomes chart-worthy it is promoted to a real column by
migration and registered as a metric.
"""

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Date,
    Enum,
    Float,
    ForeignKey,
    Index,
    String,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UtcDateTime, UUIDPrimaryKeyMixin, enum_values


class MealType(enum.StrEnum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"


class EntrySource(enum.StrEnum):
    MANUAL = "manual"
    PHOTO = "photo"
    CHAT = "chat"
    PDF = "pdf"


class FoodEntry(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "food_entries"
    __table_args__ = (
        # Every list and report query leads with these.
        Index("ix_food_entries_user_date", "user_id", "consumed_on"),
        Index("ix_food_entries_user_date_meal", "user_id", "consumed_on", "meal_type"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    consumed_on: Mapped[date] = mapped_column(Date, nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(UtcDateTime, default=None)
    meal_type: Mapped[MealType] = mapped_column(
        Enum(MealType, native_enum=False, length=20, values_callable=enum_values),
        nullable=False,
    )

    food_name: Mapped[str] = mapped_column(String(200), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    unit: Mapped[str] = mapped_column(String(30), nullable=False, default="serving")

    calories: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    protein_g: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    carbs_g: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    fat_g: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Fixed micronutrient set — typed so they can be aggregated and charted.
    fiber_g: Mapped[float | None] = mapped_column(Float, default=None)
    sugar_g: Mapped[float | None] = mapped_column(Float, default=None)
    sodium_mg: Mapped[float | None] = mapped_column(Float, default=None)
    potassium_mg: Mapped[float | None] = mapped_column(Float, default=None)
    calcium_mg: Mapped[float | None] = mapped_column(Float, default=None)
    iron_mg: Mapped[float | None] = mapped_column(Float, default=None)
    cholesterol_mg: Mapped[float | None] = mapped_column(Float, default=None)
    vitamin_a_mcg: Mapped[float | None] = mapped_column(Float, default=None)
    vitamin_c_mg: Mapped[float | None] = mapped_column(Float, default=None)
    vitamin_d_mcg: Mapped[float | None] = mapped_column(Float, default=None)
    vitamin_b12_mcg: Mapped[float | None] = mapped_column(Float, default=None)

    micros_extra: Mapped[dict | None] = mapped_column(JSON, default=None)

    source: Mapped[EntrySource] = mapped_column(
        Enum(EntrySource, native_enum=False, length=20, values_callable=enum_values),
        nullable=False,
        default=EntrySource.MANUAL,
    )
    source_ref: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("import_batches.id", ondelete="SET NULL"), default=None
    )
    notes: Mapped[str | None] = mapped_column(String(1000), default=None)


#: Typed micronutrient columns, in display order. Referenced by the schemas and
#: by the reports metric registry so the set is defined in exactly one place.
MICRONUTRIENT_FIELDS: tuple[str, ...] = (
    "fiber_g",
    "sugar_g",
    "sodium_mg",
    "potassium_mg",
    "calcium_mg",
    "iron_mg",
    "cholesterol_mg",
    "vitamin_a_mcg",
    "vitamin_c_mg",
    "vitamin_d_mcg",
    "vitamin_b12_mcg",
)

MACRONUTRIENT_FIELDS: tuple[str, ...] = ("protein_g", "carbs_g", "fat_g")
