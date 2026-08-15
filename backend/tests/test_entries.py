"""Food entry creation, validation, filtering and listing (FR-2, FR-3)."""

from datetime import date, timedelta

from fastapi.testclient import TestClient

TODAY = date.today()


def make_entry(**overrides) -> dict:
    return {
        "consumed_on": TODAY.isoformat(),
        "meal_type": "breakfast",
        "food_name": "Oatmeal",
        "quantity": 1,
        "unit": "bowl",
        "calories": 320,
        "protein_g": 11,
        "carbs_g": 54,
        "fat_g": 6,
        **overrides,
    }


def post_entry(client: TestClient, headers: dict, **overrides):
    return client.post("/api/v1/entries", json=make_entry(**overrides), headers=headers)


def test_create_entry(client: TestClient, auth_headers: dict) -> None:
    response = post_entry(client, auth_headers)

    assert response.status_code == 201
    body = response.json()
    assert body["food_name"] == "Oatmeal"
    assert body["source"] == "manual"
    assert body["source_ref"] is None


def test_create_entry_with_micronutrients(client: TestClient, auth_headers: dict) -> None:
    response = post_entry(client, auth_headers, fiber_g=8, sodium_mg=140, vitamin_c_mg=2.5)

    assert response.status_code == 201
    body = response.json()
    assert body["fiber_g"] == 8
    assert body["sodium_mg"] == 140
    assert body["potassium_mg"] is None


def test_extra_micronutrients_go_to_overflow(client: TestClient, auth_headers: dict) -> None:
    response = post_entry(client, auth_headers, micros_extra={"selenium_mcg": 12.5})

    assert response.status_code == 201
    assert response.json()["micros_extra"] == {"selenium_mcg": 12.5}


def test_future_dated_entry_is_rejected(client: TestClient, auth_headers: dict) -> None:
    response = post_entry(client, auth_headers, consumed_on=(TODAY + timedelta(days=1)).isoformat())

    assert response.status_code == 422
    assert any("future" in err["message"] for err in response.json()["errors"])


def test_negative_calories_rejected(client: TestClient, auth_headers: dict) -> None:
    response = post_entry(client, auth_headers, calories=-10)

    assert response.status_code == 422
    assert any(err["field"] == "calories" for err in response.json()["errors"])


def test_zero_quantity_rejected(client: TestClient, auth_headers: dict) -> None:
    assert post_entry(client, auth_headers, quantity=0).status_code == 422


def test_invalid_meal_type_rejected(client: TestClient, auth_headers: dict) -> None:
    assert post_entry(client, auth_headers, meal_type="brunch").status_code == 422


def test_blank_food_name_rejected(client: TestClient, auth_headers: dict) -> None:
    assert post_entry(client, auth_headers, food_name="   ").status_code == 422


def test_consumed_at_must_match_consumed_on(client: TestClient, auth_headers: dict) -> None:
    yesterday = TODAY - timedelta(days=1)
    response = post_entry(client, auth_headers, consumed_at=f"{yesterday.isoformat()}T08:00:00Z")

    assert response.status_code == 422


def test_entries_require_authentication(client: TestClient) -> None:
    assert client.get("/api/v1/entries").status_code == 401
    assert client.post("/api/v1/entries", json=make_entry()).status_code == 401


def test_filter_by_meal_type(client: TestClient, auth_headers: dict) -> None:
    post_entry(client, auth_headers, meal_type="breakfast")
    post_entry(client, auth_headers, meal_type="dinner", food_name="Curry")

    response = client.get("/api/v1/entries?meal_type=dinner", headers=auth_headers)

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["food_name"] == "Curry"


def test_filter_by_date_range_is_inclusive(client: TestClient, auth_headers: dict) -> None:
    for offset in (0, 3, 10):
        post_entry(
            client,
            auth_headers,
            consumed_on=(TODAY - timedelta(days=offset)).isoformat(),
            food_name=f"Day-{offset}",
        )

    response = client.get(
        f"/api/v1/entries?date_from={(TODAY - timedelta(days=3)).isoformat()}"
        f"&date_to={TODAY.isoformat()}",
        headers=auth_headers,
    )

    names = {item["food_name"] for item in response.json()["items"]}
    assert names == {"Day-0", "Day-3"}


def test_reversed_date_range_is_rejected(client: TestClient, auth_headers: dict) -> None:
    response = client.get(
        f"/api/v1/entries?date_from={TODAY.isoformat()}"
        f"&date_to={(TODAY - timedelta(days=5)).isoformat()}",
        headers=auth_headers,
    )

    assert response.status_code == 422


def test_search_by_food_name(client: TestClient, auth_headers: dict) -> None:
    post_entry(client, auth_headers, food_name="Greek Yoghurt")
    post_entry(client, auth_headers, food_name="Oatmeal")

    response = client.get("/api/v1/entries?q=yogh", headers=auth_headers)

    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["food_name"] == "Greek Yoghurt"


def test_update_entry_changes_only_supplied_fields(client: TestClient, auth_headers: dict) -> None:
    entry_id = post_entry(client, auth_headers).json()["id"]

    response = client.patch(
        f"/api/v1/entries/{entry_id}", json={"calories": 400}, headers=auth_headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["calories"] == 400
    assert body["food_name"] == "Oatmeal"
    assert body["protein_g"] == 11


def test_delete_entry(client: TestClient, auth_headers: dict) -> None:
    entry_id = post_entry(client, auth_headers).json()["id"]

    assert client.delete(f"/api/v1/entries/{entry_id}", headers=auth_headers).status_code == 204
    assert client.get(f"/api/v1/entries/{entry_id}", headers=auth_headers).status_code == 404


def test_bulk_create_records_an_import_batch(client: TestClient, auth_headers: dict) -> None:
    response = client.post(
        "/api/v1/entries/bulk",
        json={
            "entries": [make_entry(food_name="A"), make_entry(food_name="B")],
            "import_filename": "diary.pdf",
        },
        headers=auth_headers,
    )

    assert response.status_code == 201
    created = response.json()
    assert len(created) == 2
    # Both rows share one batch, so the import can be undone as a unit.
    assert created[0]["source_ref"] == created[1]["source_ref"] is not None


def test_bulk_create_without_filename_has_no_batch(client: TestClient, auth_headers: dict) -> None:
    response = client.post(
        "/api/v1/entries/bulk", json={"entries": [make_entry()]}, headers=auth_headers
    )

    assert response.status_code == 201
    assert response.json()[0]["source_ref"] is None


def test_bulk_create_rejects_empty_list(client: TestClient, auth_headers: dict) -> None:
    response = client.post("/api/v1/entries/bulk", json={"entries": []}, headers=auth_headers)
    assert response.status_code == 422
