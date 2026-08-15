"""User isolation (FR-7, NFR-4).

The single most important property in a multi-user app: one user must never be
able to read or modify another's data. Asserted per resource type, and per verb,
because a leak on any one route is a leak.
"""

from datetime import date

from fastapi.testclient import TestClient

TODAY = date.today().isoformat()

ENTRY = {
    "consumed_on": TODAY,
    "meal_type": "lunch",
    "food_name": "Private Salad",
    "calories": 250,
}


def test_entry_lists_are_separate(
    client: TestClient, auth_headers: dict, other_user_headers: dict
) -> None:
    client.post("/api/v1/entries", json=ENTRY, headers=auth_headers)

    listing = client.get("/api/v1/entries", headers=other_user_headers).json()
    assert listing["total"] == 0
    assert listing["items"] == []


def test_cannot_read_another_users_entry(
    client: TestClient, auth_headers: dict, other_user_headers: dict
) -> None:
    entry_id = client.post("/api/v1/entries", json=ENTRY, headers=auth_headers).json()["id"]

    # 404, not 403: the API must not confirm that the entry exists at all.
    response = client.get(f"/api/v1/entries/{entry_id}", headers=other_user_headers)
    assert response.status_code == 404


def test_cannot_update_another_users_entry(
    client: TestClient, auth_headers: dict, other_user_headers: dict
) -> None:
    entry_id = client.post("/api/v1/entries", json=ENTRY, headers=auth_headers).json()["id"]

    response = client.patch(
        f"/api/v1/entries/{entry_id}", json={"calories": 9999}, headers=other_user_headers
    )
    assert response.status_code == 404

    # And the original is untouched.
    owner_view = client.get(f"/api/v1/entries/{entry_id}", headers=auth_headers).json()
    assert owner_view["calories"] == 250


def test_cannot_delete_another_users_entry(
    client: TestClient, auth_headers: dict, other_user_headers: dict
) -> None:
    entry_id = client.post("/api/v1/entries", json=ENTRY, headers=auth_headers).json()["id"]

    assert (
        client.delete(f"/api/v1/entries/{entry_id}", headers=other_user_headers).status_code == 404
    )
    assert client.get(f"/api/v1/entries/{entry_id}", headers=auth_headers).status_code == 200


def test_goals_are_separate(
    client: TestClient, auth_headers: dict, other_user_headers: dict
) -> None:
    client.post("/api/v1/goals", json={"calorie_target": 2200}, headers=auth_headers)

    assert client.get("/api/v1/goals/current", headers=other_user_headers).status_code == 404
    assert client.get("/api/v1/goals", headers=other_user_headers).json()["total"] == 0


def test_cannot_modify_another_users_goal(
    client: TestClient, auth_headers: dict, other_user_headers: dict
) -> None:
    goal_id = client.post(
        "/api/v1/goals", json={"calorie_target": 2200}, headers=auth_headers
    ).json()["id"]

    assert (
        client.patch(
            f"/api/v1/goals/{goal_id}", json={"calorie_target": 100}, headers=other_user_headers
        ).status_code
        == 404
    )
    assert client.delete(f"/api/v1/goals/{goal_id}", headers=other_user_headers).status_code == 404
    assert (
        client.get("/api/v1/goals/current", headers=auth_headers).json()["calorie_target"] == 2200
    )


def test_weight_logs_are_separate(
    client: TestClient, auth_headers: dict, other_user_headers: dict
) -> None:
    client.post("/api/v1/weights", json={"weight_kg": 72.5}, headers=auth_headers)

    assert client.get("/api/v1/weights", headers=other_user_headers).json()["total"] == 0
