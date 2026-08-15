"""Pagination behaviour, shared by every list endpoint (NFR-3)."""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

TODAY = date.today()


@pytest.fixture
def seeded_entries(client: TestClient, auth_headers: dict) -> dict:
    """30 entries on 30 distinct days, newest first when listed."""
    for offset in range(30):
        client.post(
            "/api/v1/entries",
            json={
                "consumed_on": (TODAY - timedelta(days=offset)).isoformat(),
                "meal_type": "lunch",
                "food_name": f"Meal-{offset:02d}",
                "calories": 100 + offset,
            },
            headers=auth_headers,
        )
    return auth_headers


def test_default_page_size_applies(client: TestClient, seeded_entries: dict) -> None:
    body = client.get("/api/v1/entries", headers=seeded_entries).json()

    assert body["page"] == 1
    assert body["page_size"] == 25
    assert body["total"] == 30
    assert len(body["items"]) == 25
    assert body["has_next"] is True


def test_last_page_reports_no_next(client: TestClient, seeded_entries: dict) -> None:
    body = client.get("/api/v1/entries?page=2", headers=seeded_entries).json()

    assert len(body["items"]) == 5
    assert body["has_next"] is False


def test_page_beyond_the_end_is_empty_not_an_error(
    client: TestClient, seeded_entries: dict
) -> None:
    body = client.get("/api/v1/entries?page=99", headers=seeded_entries).json()

    assert body["items"] == []
    assert body["total"] == 30
    assert body["has_next"] is False


def test_pages_do_not_overlap_or_skip(client: TestClient, seeded_entries: dict) -> None:
    first = client.get("/api/v1/entries?page=1&page_size=10", headers=seeded_entries).json()
    second = client.get("/api/v1/entries?page=2&page_size=10", headers=seeded_entries).json()
    third = client.get("/api/v1/entries?page=3&page_size=10", headers=seeded_entries).json()

    ids = [item["id"] for page in (first, second, third) for item in page["items"]]
    assert len(ids) == 30
    assert len(set(ids)) == 30  # no repeats across pages


def test_page_size_is_capped_server_side(client: TestClient, seeded_entries: dict) -> None:
    """No caller can ask for an unbounded result set."""
    body = client.get("/api/v1/entries?page_size=100000", headers=seeded_entries).json()

    assert body["page_size"] == 100


def test_invalid_pagination_params_rejected(client: TestClient, auth_headers: dict) -> None:
    assert client.get("/api/v1/entries?page=0", headers=auth_headers).status_code == 422
    assert client.get("/api/v1/entries?page_size=0", headers=auth_headers).status_code == 422


def test_total_reflects_filters_not_the_whole_table(
    client: TestClient, seeded_entries: dict
) -> None:
    body = client.get(
        f"/api/v1/entries?date_from={(TODAY - timedelta(days=4)).isoformat()}",
        headers=seeded_entries,
    ).json()

    assert body["total"] == 5


def test_goal_and_weight_lists_are_also_paginated(client: TestClient, auth_headers: dict) -> None:
    for offset in range(5):
        day = (TODAY - timedelta(days=offset)).isoformat()
        client.post(
            "/api/v1/goals",
            json={"effective_from": day, "calorie_target": 2000 + offset},
            headers=auth_headers,
        )
        client.post(
            "/api/v1/weights",
            json={"logged_on": day, "weight_kg": 70 + offset},
            headers=auth_headers,
        )

    goals = client.get("/api/v1/goals?page_size=2", headers=auth_headers).json()
    weights = client.get("/api/v1/weights?page_size=2", headers=auth_headers).json()

    for body in (goals, weights):
        assert body["total"] == 5
        assert len(body["items"]) == 2
        assert body["has_next"] is True
