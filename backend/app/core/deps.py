"""Shared FastAPI dependencies: database session and authenticated user."""

import uuid
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.errors import UnauthorizedError
from app.core.security import decode_access_token
from app.db.models import User
from app.db.session import get_db

DbSession = Annotated[Session, Depends(get_db)]

# auto_error=False so a missing header raises our problem+json error rather
# than Starlette's plain-JSON 403.
_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    session: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    if credentials is None:
        raise UnauthorizedError("Authentication credentials were not provided.")

    payload = decode_access_token(credentials.credentials)
    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise UnauthorizedError("Access token is invalid.") from exc

    user = session.get(User, user_id)
    if user is None:
        # Token is well-formed but the account is gone.
        raise UnauthorizedError("Access token is invalid.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
