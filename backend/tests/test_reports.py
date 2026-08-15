"""Reporting layer (FR-4).

Tested against a fixed seeded dataset so every total is a known number. This is
the suite that makes adding future reports safe: if the aggregation layer stays
correct, new reports are just new callers.
"""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

# A Wednesday, so week bucketing has something to actually do.
ANCHOR = date(2026, 6, 17)


def log(client: TestClient, headers: dict, on: date, meal: str, **fields) -> None:
    body = {
        "consumed_on": on.isoformat(),
        "meal_type": meal,
        "food_name": fields.pop("food_name", "Test Food"),
        "calories": 0,
        **fields,
    }
    response = client.post("/api/v1/entries", json=body, headers=headers)
    assert response.status_code == 201, response.text


@pytest.fixture
def dataset(client: TestClient, auth_headers: dict) -> dict:
    """Three days of known entries, plus two goal versions.

    Mon 15th: 500 kcal   (before the goal change — target 2000)
    Wed 17th: 300 + 700 = 1000 kcal, across two meals
    Thu 18th: nothing logged — the gap-filling case
    Fri 19th: 250 kcal   (after the goal change — target 2500)
    """
    client.post(
        "/api/v1/goals",
        json={
            "effective_from": "2026-06-01",
            "calorie_target": 2000,
            "protein_g": 100,
            "micro_targets": {"fiber_g": 30},
        },
        headers=auth_headers,
    )
    client.post(
        "/api/v1/goals",
        json={"effective_from": "2026-06-19", "calorie_target": 2500, "protein_g": 150},
        headers=auth_headers,
    )

    log(client, auth_headers, date(2026, 6, 15), "breakfast", calories=500, protein_g=20)
    log(client, auth_headers, ANCHOR, "breakfast", calories=300, protein_g=10, fiber_g=5)
    log(client, auth_headers, ANCHOR, "dinner", calories=700, protein_g=40, fiber_g=3)
    log(client, auth_headers, date(2026, 6, 19), "lunch", calories=250, protein_g=15)
    return auth_headers


# --------------------------------------------------------------------------
# The generic aggregation layer
# --------------------------------------------------------------------------


def test_aggregate_totals_without_grouping(client: TestClient, dataset: dict) -> None:
    response = client.get(
        "/api/v1/reports/aggregate?metrics=calories&metrics=entry_count"
        "&date_from=2026-06-01&date_to=2026-06-30",
        headers=dataset,
    )

    assert response.status_code == 200
    rows = response.json()["rows"]
    assert len(rows) == 1
    assert rows[0]["calories"] == 1750
    assert rows[0]["entry_count"] == 4


def test_aggregate_group_by_meal_type(client: TestClient, dataset: dict) -> None:
    response = client.get(
        "/api/v1/reports/aggregate?metrics=calories&group_by=meal_type"
        "&date_from=2026-06-01&date_to=2026-06-30",
        headers=dataset,
    )

    totals = {row["meal_type"]: row["calories"] for row in response.json()["rows"]}
    assert totals == {"breakfast": 800, "dinner": 700, "lunch": 250}


def test_aggregate_group_by_day_returns_real_dates(client: TestClient, dataset: dict) -> None:
    """Bucket keys must come back as dates, not backend-specific strings."""
    response = client.get(
        "/api/v1/reports/aggregate?metrics=calories&group_by=day"
        "&date_from=2026-06-01&date_to=2026-06-30",
        headers=dataset,
    )

    rows = response.json()["rows"]
    assert [row["day"] for row in rows] == ["2026-06-15", "2026-06-17", "2026-06-19"]
    assert [row["calories"] for row in rows] == [500, 1000, 250]


def test_aggregate_group_by_week_starts_on_monday(client: TestClient, dataset: dict) -> None:
    response = client.get(
        "/api/v1/reports/aggregate?metrics=calories&group_by=week"
        "&date_from=2026-06-01&date_to=2026-06-30",
        headers=dataset,
    )

    rows = response.json()["rows"]
    # 15th, 17th and 19th June 2026 all fall in the week beginning Monday 15th.
    assert [row["week"] for row in rows] == ["2026-06-15"]
    assert rows[0]["calories"] == 1750


def test_aggregate_group_by_month(client: TestClient, dataset: dict) -> None:
    response = client.get(
        "/api/v1/reports/aggregate?metrics=calories&group_by=month"
        "&date_from=2026-06-01&date_to=2026-06-30",
        headers=dataset,
    )

    assert response.json()["rows"] == [{"month": "2026-06-01", "calories": 1750}]


def test_aggregate_multiple_dimensions(client: TestClient, dataset: dict) -> None:
    response = client.get(
        "/api/v1/reports/aggregate?metrics=calories&group_by=day&group_by=meal_type"
        "&date_from=2026-06-17&date_to=2026-06-17",
        headers=dataset,
    )

    rows = response.json()["rows"]
    assert len(rows) == 2
    assert {row["meal_type"] for row in rows} == {"breakfast", "dinner"}


def test_every_metric_and_dimension_in_the_catalogue_works(
    client: TestClient, dataset: dict
) -> None:
    """Guards the registries: anything advertised must actually be queryable."""
    catalogue = client.get("/api/v1/reports/catalogue", headers=dataset).json()

    for metric in catalogue["metrics"]:
        for dimension in catalogue["dimensions"]:
            response = client.get(
                f"/api/v1/reports/aggregate?metrics={metric}&group_by={dimension}",
                headers=dataset,
            )
            assert response.status_code == 200, f"{metric} by {dimension}: {response.text}"


def test_unknown_metric_is_rejected(client: TestClient, dataset: dict) -> None:
    response = client.get("/api/v1/reports/aggregate?metrics=calorie", headers=dataset)

    assert response.status_code == 422
    assert "calorie" in response.json()["detail"]


def test_unknown_dimension_is_rejected(client: TestClient, dataset: dict) -> None:
    response = client.get(
        "/api/v1/reports/aggregate?metrics=calories&group_by=; DROP TABLE users",
        headers=dataset,
    )

    assert response.status_code == 422


def test_aggregate_requires_a_metric(client: TestClient, dataset: dict) -> None:
    assert client.get("/api/v1/reports/aggregate", headers=dataset).status_code == 422


def test_reports_are_scoped_to_the_user(
    client: TestClient, dataset: dict, other_user_headers: dict
) -> None:
    response = client.get(
        "/api/v1/reports/aggregate?metrics=calories&date_from=2026-06-01&date_to=2026-06-30",
        headers=other_user_headers,
    )

    assert response.json()["rows"][0]["calories"] == 0


def test_reports_require_authentication(client: TestClient) -> None:
    assert client.get("/api/v1/reports/trend").status_code == 401
    assert client.get("/api/v1/reports/daily-summary").status_code == 401


# --------------------------------------------------------------------------
# Named reports
# --------------------------------------------------------------------------


def test_trend_fills_empty_days_with_zero(client: TestClient, dataset: dict) -> None:
    """Charts must not have holes where nothing was logged."""
    response = client.get(
        "/api/v1/reports/trend?date_from=2026-06-15&date_to=2026-06-19&granularity=day",
        headers=dataset,
    )

    points = response.json()["points"]
    assert [p["bucket"] for p in points] == [
        "2026-06-15",
        "2026-06-16",
        "2026-06-17",
        "2026-06-18",
        "2026-06-19",
    ]
    assert [p["calories"] for p in points] == [500, 0, 1000, 0, 250]


def test_trend_by_week(client: TestClient, dataset: dict) -> None:
    response = client.get(
        "/api/v1/reports/trend?date_from=2026-06-08&date_to=2026-06-21&granularity=week",
        headers=dataset,
    )

    points = response.json()["points"]
    assert [p["bucket"] for p in points] == ["2026-06-08", "2026-06-15"]
    assert [p["calories"] for p in points] == [0, 1750]


def test_daily_summary_totals_and_meal_breakdown(client: TestClient, dataset: dict) -> None:
    response = client.get(f"/api/v1/reports/daily-summary?on={ANCHOR}", headers=dataset)

    body = response.json()
    assert body["totals"]["calories"] == 1000
    assert body["totals"]["protein_g"] == 50
    assert body["totals"]["fiber_g"] == 8

    by_meal = {row["meal_type"]: row["calories"] for row in body["by_meal"]}
    # All four meal types present, so the dashboard has a stable shape.
    assert by_meal == {"breakfast": 300, "lunch": 0, "dinner": 700, "snack": 0}


def test_daily_summary_uses_the_goal_in_force_that_day(client: TestClient, dataset: dict) -> None:
    """The 17th predates the goal change, so it must use the 2000 target."""
    earlier = client.get(f"/api/v1/reports/daily-summary?on={ANCHOR}", headers=dataset).json()
    later = client.get("/api/v1/reports/daily-summary?on=2026-06-19", headers=dataset).json()

    assert earlier["goal"]["calorie_target"] == 2000
    assert earlier["remaining_calories"] == 1000  # 2000 - 1000

    assert later["goal"]["calorie_target"] == 2500
    assert later["remaining_calories"] == 2250  # 2500 - 250


def test_daily_summary_without_a_goal(client: TestClient, auth_headers: dict) -> None:
    response = client.get("/api/v1/reports/daily-summary", headers=auth_headers)

    body = response.json()
    assert body["goal"] is None
    assert body["remaining_calories"] is None
    assert body["totals"]["calories"] == 0


def test_macro_breakdown_splits_by_energy_not_grams(client: TestClient, dataset: dict) -> None:
    """A gram of fat carries more energy than a gram of protein."""
    response = client.get(
        "/api/v1/reports/macros?date_from=2026-06-17&date_to=2026-06-17", headers=dataset
    )

    body = response.json()
    assert body["totals"]["protein_g"] == 50
    # Only protein was logged that day, so it accounts for all the macro energy.
    assert body["share_of_calories"] == {"protein_g": 100.0, "carbs_g": 0.0, "fat_g": 0.0}


def test_macro_share_is_zero_when_nothing_logged(client: TestClient, auth_headers: dict) -> None:
    response = client.get("/api/v1/reports/macros", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["share_of_calories"] == {
        "protein_g": 0.0,
        "carbs_g": 0.0,
        "fat_g": 0.0,
    }


def test_micro_summary_reports_totals_averages_and_targets(
    client: TestClient, dataset: dict
) -> None:
    response = client.get(
        "/api/v1/reports/micros?date_from=2026-06-15&date_to=2026-06-18", headers=dataset
    )

    body = response.json()
    assert body["days"] == 4
    fiber = next(n for n in body["nutrients"] if n["name"] == "fiber_g")
    assert fiber["total"] == 8
    assert fiber["daily_average"] == 2.0  # 8 over 4 days
    assert fiber["target"] == 30

    # Untracked micronutrients still appear, so the report shape is stable.
    sodium = next(n for n in body["nutrients"] if n["name"] == "sodium_mg")
    assert sodium["total"] == 0
    assert sodium["target"] is None


def test_goal_vs_actual_compares_against_the_right_version(
    client: TestClient, dataset: dict
) -> None:
    response = client.get(
        "/api/v1/reports/goal-vs-actual?date_from=2026-06-17&date_to=2026-06-19&granularity=day",
        headers=dataset,
    )

    points = {p["bucket"]: p for p in response.json()["points"]}
    assert points["2026-06-17"]["actual"]["calories"] == 1000
    assert points["2026-06-17"]["target"]["calories"] == 2000
    assert points["2026-06-19"]["target"]["calories"] == 2500


def test_goal_vs_actual_sums_daily_targets_across_a_week(client: TestClient, dataset: dict) -> None:
    """A weekly total must be compared against a week's worth of target."""
    response = client.get(
        "/api/v1/reports/goal-vs-actual?date_from=2026-06-15&date_to=2026-06-18&granularity=week",
        headers=dataset,
    )

    point = response.json()["points"][0]
    assert point["days"] == 4  # clipped to the requested range, not a full week
    assert point["actual"]["calories"] == 1500  # 500 + 1000
    assert point["target"]["calories"] == 8000  # 4 days at 2000


def test_goal_vs_actual_target_is_null_before_any_goal(
    client: TestClient, auth_headers: dict
) -> None:
    log(client, auth_headers, date.today(), "lunch", calories=400)

    response = client.get(
        f"/api/v1/reports/goal-vs-actual?date_from={date.today()}&date_to={date.today()}",
        headers=auth_headers,
    )

    point = response.json()["points"][0]
    assert point["actual"]["calories"] == 400
    assert point["target"]["calories"] is None


def test_reversed_date_range_is_rejected(client: TestClient, dataset: dict) -> None:
    response = client.get(
        "/api/v1/reports/trend?date_from=2026-06-20&date_to=2026-06-01", headers=dataset
    )
    assert response.status_code == 422


def test_default_range_is_the_last_four_weeks(client: TestClient, auth_headers: dict) -> None:
    response = client.get("/api/v1/reports/trend", headers=auth_headers)

    body = response.json()
    assert len(body["points"]) == 28
    assert body["date_to"] == date.today().isoformat()
    assert body["date_from"] == (date.today() - timedelta(days=27)).isoformat()


def test_aggregate_fill_gaps_emits_zero_buckets(client: TestClient, dataset: dict) -> None:
    """A chart needs every bucket present; a line that skips a day misreports it.

    Thursday the 18th has nothing logged. Without gap filling the series jumps from the 17th
    straight to the 19th and the chart slopes through the missing day as if intake were
    somewhere between the two.
    """
    response = client.get(
        "/api/v1/reports/aggregate?metrics=calories&group_by=day&fill_gaps=true"
        "&date_from=2026-06-15&date_to=2026-06-19",
        headers=dataset,
    )

    rows = response.json()["rows"]
    assert [row["day"] for row in rows] == [
        "2026-06-15",
        "2026-06-16",
        "2026-06-17",
        "2026-06-18",
        "2026-06-19",
    ]
    assert [row["calories"] for row in rows] == [500, 0, 1000, 0, 250]


def test_aggregate_stays_sparse_by_default(client: TestClient, dataset: dict) -> None:
    """The opt-in must really be opt-in — existing callers keep the sparse contract."""
    response = client.get(
        "/api/v1/reports/aggregate?metrics=calories&group_by=day"
        "&date_from=2026-06-15&date_to=2026-06-19",
        headers=dataset,
    )
    assert [row["day"] for row in response.json()["rows"]] == [
        "2026-06-15",
        "2026-06-17",
        "2026-06-19",
    ]


def test_fill_gaps_is_ignored_for_non_date_grouping(client: TestClient, dataset: dict) -> None:
    """There is no such thing as a missing meal type, so the flag must not change anything."""
    response = client.get(
        "/api/v1/reports/aggregate?metrics=calories&group_by=meal_type&fill_gaps=true"
        "&date_from=2026-06-15&date_to=2026-06-19",
        headers=dataset,
    )
    assert response.status_code == 200
    assert {row["meal_type"] for row in response.json()["rows"]} == {
        "breakfast",
        "dinner",
        "lunch",
    }
