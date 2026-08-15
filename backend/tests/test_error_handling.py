"""Error envelope consistency (NFR-6).

Every error the API emits has the same shape, so the frontend needs exactly one
error path.
"""

from fastapi.testclient import TestClient

PROBLEM_FIELDS = {"type", "title", "status", "detail", "errors", "request_id"}


def test_health_endpoint(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_not_found_uses_the_problem_envelope(client: TestClient, auth_headers: dict) -> None:
    response = client.get(
        "/api/v1/entries/00000000-0000-0000-0000-000000000000", headers=auth_headers
    )

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json().keys() >= PROBLEM_FIELDS


def test_validation_error_lists_offending_fields(client: TestClient, auth_headers: dict) -> None:
    response = client.post(
        "/api/v1/entries",
        json={"consumed_on": "not-a-date", "meal_type": "lunch", "food_name": "X"},
        headers=auth_headers,
    )

    assert response.status_code == 422
    body = response.json()
    assert body.keys() >= PROBLEM_FIELDS
    assert any(err["field"] == "consumed_on" for err in body["errors"])


def test_unauthorized_uses_the_problem_envelope(client: TestClient) -> None:
    response = client.get("/api/v1/entries")

    assert response.status_code == 401
    assert response.json().keys() >= PROBLEM_FIELDS


def test_malformed_uuid_in_path_is_a_422_not_a_500(client: TestClient, auth_headers: dict) -> None:
    response = client.get("/api/v1/entries/not-a-uuid", headers=auth_headers)

    assert response.status_code == 422
    assert response.json().keys() >= PROBLEM_FIELDS


def test_request_id_is_echoed_and_matches_the_body(client: TestClient, auth_headers: dict) -> None:
    """A user-reported failure must be traceable to its logs."""
    response = client.get(
        "/api/v1/entries/00000000-0000-0000-0000-000000000000", headers=auth_headers
    )

    assert response.headers["X-Request-ID"] == response.json()["request_id"]


def test_supplied_request_id_is_preserved(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Request-ID": "trace-me-123"})

    assert response.headers["X-Request-ID"] == "trace-me-123"
