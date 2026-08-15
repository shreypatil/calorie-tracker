"""Goals, versioned by `effective_from`.

Targets are never mutated in place across time: each change is a version with
its own start date, and the goal in force on a date is the latest version at or
before it. Without this, a user changing their target would silently rewrite
what every past day had been measured against, and goal-vs-actual history would
become fiction.
"""

import uuid
from datetime import date

from sqlalchemy import JSON, Date, Float, ForeignKey, Index, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Goal(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "goals"
    __table_args__ = (
        UniqueConstraint("user_id", "effective_from", name="uq_goals_user_effective_from"),
        Index("ix_goals_user_effective_from", "user_id", "effective_from"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)

    calorie_target: Mapped[float | None] = mapped_column(Float, default=None)
    protein_g: Mapped[float | None] = mapped_column(Float, default=None)
    carbs_g: Mapped[float | None] = mapped_column(Float, default=None)
    fat_g: Mapped[float | None] = mapped_column(Float, default=None)
    weight_target_kg: Mapped[float | None] = mapped_column(Float, default=None)

    #: Optional per-micronutrient targets, keyed by the column names in
    #: MICRONUTRIENT_FIELDS. JSON is fine here: targets are read per goal, never
    #: aggregated across rows.
    micro_targets: Mapped[dict | None] = mapped_column(JSON, default=None)
