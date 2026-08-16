"""Authentication business logic.

Refresh tokens rotate: using one revokes it and issues a replacement, so a
stolen token is usable at most once before the legitimate client's next refresh
invalidates the thief's copy.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ConflictError, UnauthorizedError
from app.core.logging import logger
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    refresh_token_expiry,
    verify_password,
)
from app.db.models import RefreshToken, User
from app.schemas.auth import TokenPair


def register_user(session: Session, *, email: str, password: str, display_name: str) -> User:
    # The email identifies the attempt; the password is never logged, and the scrubber would
    # redact it even if a careless caller passed it through.
    logger.info("auth.register", extra={"email": email})
    user = User(email=email, password_hash=hash_password(password), display_name=display_name)
    session.add(user)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise ConflictError("An account with that email address already exists.") from exc
    session.refresh(user)
    return user


def authenticate_user(session: Session, *, email: str, password: str) -> User:
    user = session.scalar(select(User).where(User.email == email))

    # Hash even when the user does not exist, so response time does not reveal
    # which email addresses are registered.
    password_hash = user.password_hash if user else hash_password("dummy-password")
    if not verify_password(password, password_hash) or user is None:
        # Distinguishing "no such account" from "wrong password" in the log is fine — the log is
        # ours. The *response* stays identical, which is what protects account enumeration.
        logger.warning(
            "auth.login.failed",
            extra={"email": email, "reason": "no_such_user" if user is None else "bad_password"},
        )
        raise UnauthorizedError("Email or password is incorrect.")
    logger.info("auth.login.ok", extra={"email": email, "user_id": str(user.id)})
    return user


def issue_token_pair(session: Session, user: User) -> TokenPair:
    settings = get_settings()
    refresh_token = generate_refresh_token()

    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_refresh_token(refresh_token),
            expires_at=refresh_token_expiry(),
        )
    )
    session.commit()

    return TokenPair(
        access_token=create_access_token(user.id),
        refresh_token=refresh_token,
        expires_in=settings.access_token_ttl_minutes * 60,
    )


def _load_active_refresh_token(session: Session, token: str) -> RefreshToken:
    stored = session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(token))
    )
    if stored is None or stored.revoked_at is not None:
        raise UnauthorizedError("Refresh token is invalid or has been revoked.")

    # UtcDateTime guarantees this is timezone-aware on every backend.
    if stored.expires_at <= datetime.now(UTC):
        raise UnauthorizedError("Refresh token has expired.")
    return stored


def rotate_refresh_token(session: Session, token: str) -> TokenPair:
    stored = _load_active_refresh_token(session, token)
    stored.revoked_at = datetime.now(UTC)

    user = session.get(User, stored.user_id)
    if user is None:
        raise UnauthorizedError("Refresh token is invalid or has been revoked.")
    return issue_token_pair(session, user)


def revoke_refresh_token(session: Session, token: str) -> None:
    """Log out. Revoking an already-revoked token is a no-op, not an error."""
    stored = session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(token))
    )
    if stored is not None and stored.revoked_at is None:
        stored.revoked_at = datetime.now(UTC)
        session.commit()


def revoke_all_user_tokens(session: Session, user_id: uuid.UUID) -> None:
    tokens = session.scalars(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None)
        )
    ).all()
    now = datetime.now(UTC)
    for token in tokens:
        token.revoked_at = now
    session.commit()
