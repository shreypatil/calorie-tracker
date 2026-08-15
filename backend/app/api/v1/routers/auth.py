"""Authentication endpoints (FR-7)."""

from fastapi import APIRouter, Request, status

from app.core.deps import CurrentUser, DbSession
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    UserResponse,
)
from app.services import auth as auth_service
from app.services.rate_limit import limiter

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def register(request: Request, payload: RegisterRequest, session: DbSession) -> UserResponse:
    user = auth_service.register_user(
        session,
        email=payload.email,
        password=payload.password,
        display_name=payload.display_name,
    )
    return UserResponse.model_validate(user)


@router.post("/login", response_model=TokenPair)
@limiter.limit("10/minute")
def login(request: Request, payload: LoginRequest, session: DbSession) -> TokenPair:
    user = auth_service.authenticate_user(session, email=payload.email, password=payload.password)
    return auth_service.issue_token_pair(session, user)


@router.post("/refresh", response_model=TokenPair)
@limiter.limit("20/minute")
def refresh(request: Request, payload: RefreshRequest, session: DbSession) -> TokenPair:
    return auth_service.rotate_refresh_token(session, payload.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(payload: RefreshRequest, session: DbSession) -> None:
    auth_service.revoke_refresh_token(session, payload.refresh_token)


@router.get("/me", response_model=UserResponse)
def me(current_user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(current_user)
