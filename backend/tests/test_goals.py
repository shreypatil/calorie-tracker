"""Goal versioning and weight logging (FR-1)."""

from datetime import date, timedelta

from fastapi.testclient import TestClient

TODAY = date.today()


def test_no_goal_yet_returns_404(client: TestClient, auth_headers: dict) -> None:
    assert client.get("/api/v1/goals/current", headers=auth_headers).status_code == 404


def test_create_and_fetch_current_goal(client: TestClient, auth_headers: dict) -> None:
    response = client.post(
        "/api/v1/goals",
        json={"calorie_target": 2200, "protein_g": 150, "carbs_g": 220, "fat_g": 70},
        headers=auth_headers,
    )
    assert response.status_code == 201

    current = client.get("/api/v1/goals/current", headers=auth_headers)
    assert current.status_code == 200
    assert current.json()["calorie_target"] == 2200


def test_effective_from_defaults_to_today(client: TestClient, auth_headers: dict) -> None:
    response = client.post("/api/v1/goals", json={"calorie_target": 2000}, headers=auth_headers)
    assert response.json()["effective_from"] == TODAY.isoformat()


def test_setting_a_new_version_keeps_the_old_one(client: TestClient, auth_headers: dict) -> None:
    """Changing targets must not rewrite what past days were measured against."""
    last_month = TODAY - timedelta(days=30)
    client.post(
        "/api/v1/goals",
        json={"effective_from": last_month.isoformat(), "calorie_target": 1800},
        headers=auth_headers,
    )
    client.post(
        "/api/v1/goals",
        json={"effective_from": TODAY.isoformat(), "calorie_target": 2400},
        headers=auth_headers,
    )

    history = client.get("/api/v1/goals", headers=auth_headers).json()
    assert history["total"] == 2
    # Newest version first.
    assert [g["calorie_target"] for g in history["items"]] == [2400, 1800]
    current = client.get("/api/v1/goals/current", headers=auth_headers).json()
    assert current["calorie_target"] == 2400


def test_resetting_the_same_date_amends_that_version(
    client: TestClient, auth_headers: dict
) -> None:
    body = {"effective_from": TODAY.isoformat(), "calorie_target": 2000}
    first = client.post("/api/v1/goals", json=body, headers=auth_headers).json()
    second = client.post(
        "/api/v1/goals", json={**body, "calorie_target": 2100}, headers=auth_headers
    ).json()

    assert first["id"] == second["id"]
    assert second["calorie_target"] == 2100
    assert client.get("/api/v1/goals", headers=auth_headers).json()["total"] == 1


def test_micro_targets_accept_known_names(client: TestClient, auth_headers: dict) -> None:
    response = client.post(
        "/api/v1/goals",
        json={"calorie_target": 2000, "micro_targets": {"fiber_g": 30, "sodium_mg": 2300}},
        headers=auth_headers,
    )

    assert response.status_code == 201
    assert response.json()["micro_targets"] == {"fiber_g": 30, "sodium_mg": 2300}


def test_unknown_micro_target_is_rejected(client: TestClient, auth_headers: dict) -> None:
    """A typo must fail loudly rather than be silently stored and never charted."""
    response = client.post(
        "/api/v1/goals",
        json={"calorie_target": 2000, "micro_targets": {"vitamin_q_mg": 10}},
        headers=auth_headers,
    )

    assert response.status_code == 422
    assert "vitamin_q_mg" in str(response.json()["errors"])


def test_negative_target_rejected(client: TestClient, auth_headers: dict) -> None:
    response = client.post("/api/v1/goals", json={"calorie_target": -100}, headers=auth_headers)
    assert response.status_code == 422


def test_update_and_delete_goal(client: TestClient, auth_headers: dict) -> None:
    goal_id = client.post(
        "/api/v1/goals", json={"calorie_target": 2000}, headers=auth_headers
    ).json()["id"]

    updated = client.patch(
        f"/api/v1/goals/{goal_id}", json={"protein_g": 160}, headers=auth_headers
    )
    assert updated.status_code == 200
    assert updated.json()["protein_g"] == 160
    assert updated.json()["calorie_target"] == 2000

    assert client.delete(f"/api/v1/goals/{goal_id}", headers=auth_headers).status_code == 204
    assert client.get("/api/v1/goals/current", headers=auth_headers).status_code == 404


def test_record_weight(client: TestClient, auth_headers: dict) -> None:
    response = client.post("/api/v1/weights", json={"weight_kg": 72.5}, headers=auth_headers)

    assert response.status_code == 201
    assert response.json()["weight_kg"] == 72.5


def test_logging_weight_twice_in_a_day_corrects_it(client: TestClient, auth_headers: dict) -> None:
    body = {"logged_on": TODAY.isoformat(), "weight_kg": 72.5}
    first = client.post("/api/v1/weights", json=body, headers=auth_headers).json()
    second = client.post(
        "/api/v1/weights", json={**body, "weight_kg": 72.1}, headers=auth_headers
    ).json()

    assert first["id"] == second["id"]
    assert second["weight_kg"] == 72.1
    assert client.get("/api/v1/weights", headers=auth_headers).json()["total"] == 1


def test_future_weight_rejected(client: TestClient, auth_headers: dict) -> None:
    response = client.post(
        "/api/v1/weights",
        json={"logged_on": (TODAY + timedelta(days=1)).isoformat(), "weight_kg": 70},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_goals_require_authentication(client: TestClient) -> None:
    assert client.get("/api/v1/goals").status_code == 401
    assert client.post("/api/v1/goals", json={"calorie_target": 2000}).status_code == 401
