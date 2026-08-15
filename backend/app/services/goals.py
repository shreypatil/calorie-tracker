"""Goal and weight-log business logic.

Goals are versioned by `effective_from`. `get_goal_for_date` is the single
lookup the rest of the app uses, so reports always compare a day against the
targets that were actually in force on that day.
"""

import uuid
from collections.abc import Sequence
from datetime import date

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.core.pagination import PageParams, paginate
from app.db.models import Goal, WeightLog
from app.schemas.goal import GoalCreate, GoalUpdate, WeightLogCreate


def _goal_query(user_id: uuid.UUID) -> Select:
    return select(Goal).where(Goal.user_id == user_id).order_by(Goal.effective_from.desc())


def list_goals(
    session: Session, user_id: uuid.UUID, params: PageParams
) -> tuple[Sequence[Goal], int]:
    """Full goal history, newest version first."""
    return paginate(session, _goal_query(user_id), params)


def get_goal_for_date(session: Session, user_id: uuid.UUID, on_date: date) -> Goal | None:
    """The goal version in force on `on_date`, or None if none had started yet."""
    return session.scalar(_goal_query(user_id).where(Goal.effective_from <= on_date).limit(1))


def get_current_goal(session: Session, user_id: uuid.UUID) -> Goal | None:
    return get_goal_for_date(session, user_id, date.today())


def get_goal(session: Session, user_id: uuid.UUID, goal_id: uuid.UUID) -> Goal:
    goal = session.scalar(_goal_query(user_id).where(Goal.id == goal_id))
    if goal is None:
        raise NotFoundError("Goal not found.")
    return goal


def upsert_goal(session: Session, user_id: uuid.UUID, payload: GoalCreate) -> Goal:
    """Create the version for `effective_from`, or replace it if it exists.

    Re-setting targets for a date the user already configured is a correction,
    not a conflict — so this amends that version rather than rejecting it.
    """
    existing = session.scalar(
        _goal_query(user_id).where(Goal.effective_from == payload.effective_from)
    )
    if existing is not None:
        for field, value in payload.model_dump(exclude={"effective_from"}).items():
            setattr(existing, field, value)
        session.commit()
        session.refresh(existing)
        return existing

    goal = Goal(**payload.model_dump(), user_id=user_id)
    session.add(goal)
    session.commit()
    session.refresh(goal)
    return goal


def update_goal(
    session: Session, user_id: uuid.UUID, goal_id: uuid.UUID, payload: GoalUpdate
) -> Goal:
    goal = get_goal(session, user_id, goal_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(goal, field, value)
    session.commit()
    session.refresh(goal)
    return goal


def delete_goal(session: Session, user_id: uuid.UUID, goal_id: uuid.UUID) -> None:
    goal = get_goal(session, user_id, goal_id)
    session.delete(goal)
    session.commit()


def list_weight_logs(
    session: Session,
    user_id: uuid.UUID,
    params: PageParams,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
) -> tuple[Sequence[WeightLog], int]:
    stmt = select(WeightLog).where(WeightLog.user_id == user_id)
    if date_from:
        stmt = stmt.where(WeightLog.logged_on >= date_from)
    if date_to:
        stmt = stmt.where(WeightLog.logged_on <= date_to)
    return paginate(session, stmt.order_by(WeightLog.logged_on.desc()), params)


def record_weight(session: Session, user_id: uuid.UUID, payload: WeightLogCreate) -> WeightLog:
    """One weight per day; logging again for a day corrects that day's value."""
    existing = session.scalar(
        select(WeightLog).where(
            WeightLog.user_id == user_id, WeightLog.logged_on == payload.logged_on
        )
    )
    if existing is not None:
        existing.weight_kg = payload.weight_kg
        session.commit()
        session.refresh(existing)
        return existing

    log = WeightLog(**payload.model_dump(), user_id=user_id)
    session.add(log)
    session.commit()
    session.refresh(log)
    return log
