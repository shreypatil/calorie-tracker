"""Goal and weight endpoints (FR-1)."""

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.core.deps import CurrentUser, DbSession
from app.core.errors import NotFoundError
from app.core.pagination import Page, PageParamsDep, build_page
from app.schemas.goal import (
    GoalCreate,
    GoalResponse,
    GoalUpdate,
    WeightLogCreate,
    WeightLogResponse,
)
from app.services import goals as goals_service

router = APIRouter(tags=["goals"])


@router.get("/goals", response_model=Page[GoalResponse])
def list_goals(
    current_user: CurrentUser, session: DbSession, params: PageParamsDep
) -> Page[GoalResponse]:
    rows, total = goals_service.list_goals(session, current_user.id, params)
    items = [GoalResponse.model_validate(row) for row in rows]
    return Page[GoalResponse](**build_page(items, total, params))


@router.get("/goals/current", response_model=GoalResponse)
def get_current_goal(current_user: CurrentUser, session: DbSession) -> GoalResponse:
    goal = goals_service.get_current_goal(session, current_user.id)
    if goal is None:
        raise NotFoundError("No goal has been set yet.")
    return GoalResponse.model_validate(goal)


@router.post("/goals", response_model=GoalResponse, status_code=status.HTTP_201_CREATED)
def create_goal(payload: GoalCreate, current_user: CurrentUser, session: DbSession) -> GoalResponse:
    goal = goals_service.upsert_goal(session, current_user.id, payload)
    return GoalResponse.model_validate(goal)


@router.patch("/goals/{goal_id}", response_model=GoalResponse)
def update_goal(
    goal_id: uuid.UUID,
    payload: GoalUpdate,
    current_user: CurrentUser,
    session: DbSession,
) -> GoalResponse:
    goal = goals_service.update_goal(session, current_user.id, goal_id, payload)
    return GoalResponse.model_validate(goal)


@router.delete("/goals/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_goal(goal_id: uuid.UUID, current_user: CurrentUser, session: DbSession) -> None:
    goals_service.delete_goal(session, current_user.id, goal_id)


@router.get("/weights", response_model=Page[WeightLogResponse])
def list_weights(
    current_user: CurrentUser,
    session: DbSession,
    params: PageParamsDep,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
) -> Page[WeightLogResponse]:
    rows, total = goals_service.list_weight_logs(
        session, current_user.id, params, date_from=date_from, date_to=date_to
    )
    items = [WeightLogResponse.model_validate(row) for row in rows]
    return Page[WeightLogResponse](**build_page(items, total, params))


@router.post("/weights", response_model=WeightLogResponse, status_code=status.HTTP_201_CREATED)
def record_weight(
    payload: WeightLogCreate, current_user: CurrentUser, session: DbSession
) -> WeightLogResponse:
    log = goals_service.record_weight(session, current_user.id, payload)
    return WeightLogResponse.model_validate(log)
