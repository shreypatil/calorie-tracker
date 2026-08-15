"""Weight measurements — the actual side of the weight goal."""

import uuid
from datetime import date

from sqlalchemy import Date, Float, ForeignKey, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class WeightLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "weight_logs"
    __table_args__ = (
        # One weight per day per user; logging again corrects that day's value.
        UniqueConstraint("user_id", "logged_on", name="uq_weight_logs_user_day"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    logged_on: Mapped[date] = mapped_column(Date, nullable=False)
    weight_kg: Mapped[float] = mapped_column(Float, nullable=False)
