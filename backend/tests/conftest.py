"""Test fixtures.

Each test gets a fresh SQLite file and its own FastAPI app, so tests never see
each other's data and can run in any order.
"""

import os
import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("JWT_SECRET", "test-secret-not-used-anywhere-real")

# Force the stub provider, overriding any real key in the developer's .env.
# Without this, a configured AI_API_KEY makes `auto` pick the real provider and
# the suite silently starts calling a paid API over the network — slow,
# non-deterministic, and quietly billable. Tests must never leave the machine.
os.environ["AI_PROVIDER"] = "stub"

# Keep the suite out of the developer's real log file. Tests assert on log output by attaching
# their own handler; a rotating file handler here would just scribble into logs/app.log.
os.environ.setdefault("LOG_TO_FILE", "false")

from app.core.config import get_settings  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import create_db_engine, get_db  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services.rate_limit import limiter  # noqa: E402


@pytest.fixture
def db_session(tmp_path) -> Iterator[Session]:
    engine = create_db_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    app = create_app(get_settings())

    # Rate limits are exercised in their own test; elsewhere they would make
    # results depend on how many requests earlier tests happened to make.
    limiter.enabled = False

    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    limiter.enabled = True


@pytest.fixture
def rate_limited_client(db_session: Session) -> Iterator[TestClient]:
    """Same app, but with rate limiting left switched on."""
    app = create_app(get_settings())
    limiter.enabled = True
    limiter.reset()
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def register_and_login(client: TestClient, email: str | None = None) -> dict[str, str]:
    """Create a user and return an Authorization header for them."""
    email = email or f"user-{uuid.uuid4().hex[:8]}@example.com"
    payload = {"email": email, "password": "correct-horse-battery", "display_name": "Test User"}

    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201, response.text

    response = client.post(
        "/api/v1/auth/login", json={"email": email, "password": payload["password"]}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def auth_headers(client: TestClient) -> dict[str, str]:
    return register_and_login(client)


@pytest.fixture
def other_user_headers(client: TestClient) -> dict[str, str]:
    return register_and_login(client, email="other@example.com")
