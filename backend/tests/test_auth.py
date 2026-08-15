"""Authentication flows (FR-7)."""

from fastapi.testclient import TestClient

VALID = {
    "email": "alice@example.com",
    "password": "correct-horse-battery",
    "display_name": "Alice",
}


def test_register_returns_user_without_password(client: TestClient) -> None:
    response = client.post("/api/v1/auth/register", json=VALID)

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "alice@example.com"
    assert "password" not in body
    assert "password_hash" not in body


def test_register_normalizes_email_case(client: TestClient) -> None:
    client.post("/api/v1/auth/register", json={**VALID, "email": "Alice@Example.COM"})

    response = client.post(
        "/api/v1/auth/login", json={"email": "alice@example.com", "password": VALID["password"]}
    )
    assert response.status_code == 200


def test_duplicate_email_conflicts(client: TestClient) -> None:
    client.post("/api/v1/auth/register", json=VALID)
    response = client.post("/api/v1/auth/register", json=VALID)

    assert response.status_code == 409
    assert response.json()["title"] == "Conflict"


def test_short_password_rejected(client: TestClient) -> None:
    response = client.post("/api/v1/auth/register", json={**VALID, "password": "short"})

    assert response.status_code == 422
    assert any(err["field"] == "password" for err in response.json()["errors"])


def test_login_with_wrong_password_fails(client: TestClient) -> None:
    client.post("/api/v1/auth/register", json=VALID)

    response = client.post(
        "/api/v1/auth/login", json={"email": VALID["email"], "password": "wrong-password-here"}
    )
    assert response.status_code == 401


def test_login_for_unknown_email_gives_same_error_as_wrong_password(client: TestClient) -> None:
    """The API must not reveal which email addresses are registered."""
    client.post("/api/v1/auth/register", json=VALID)

    unknown = client.post(
        "/api/v1/auth/login", json={"email": "nobody@example.com", "password": "whatever-xyz"}
    )
    wrong = client.post(
        "/api/v1/auth/login", json={"email": VALID["email"], "password": "wrong-password-here"}
    )

    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json()["detail"] == wrong.json()["detail"]


def test_me_requires_authentication(client: TestClient) -> None:
    assert client.get("/api/v1/auth/me").status_code == 401


def test_me_rejects_garbage_token(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert response.status_code == 401


def test_me_returns_current_user(client: TestClient, auth_headers: dict) -> None:
    response = client.get("/api/v1/auth/me", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["display_name"] == "Test User"


def test_refresh_rotates_and_invalidates_the_old_token(client: TestClient) -> None:
    client.post("/api/v1/auth/register", json=VALID)
    tokens = client.post(
        "/api/v1/auth/login", json={"email": VALID["email"], "password": VALID["password"]}
    ).json()

    rotated = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert rotated.status_code == 200
    assert rotated.json()["refresh_token"] != tokens["refresh_token"]

    # Replaying the consumed token must fail.
    replay = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert replay.status_code == 401


def test_logout_revokes_the_refresh_token(client: TestClient) -> None:
    client.post("/api/v1/auth/register", json=VALID)
    tokens = client.post(
        "/api/v1/auth/login", json={"email": VALID["email"], "password": VALID["password"]}
    ).json()

    assert (
        client.post(
            "/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]}
        ).status_code
        == 204
    )
    assert (
        client.post(
            "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        ).status_code
        == 401
    )


def test_login_is_rate_limited(rate_limited_client: TestClient) -> None:
    rate_limited_client.post("/api/v1/auth/register", json=VALID)
    body = {"email": VALID["email"], "password": "wrong-password-here"}

    statuses = [
        rate_limited_client.post("/api/v1/auth/login", json=body).status_code for _ in range(12)
    ]
    assert 429 in statuses
