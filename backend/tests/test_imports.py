"""PDF import: extraction, mapping application, preview, commit and undo (FR-8)."""

from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db.models import MealType
from app.schemas.import_ import (
    ColumnMapping,
    DateFormat,
    NutritionBasis,
    RawEntry,
    TableMapping,
    TableSample,
)
from app.services.imports.extract import (
    ExtractedTable,
    ScannedPdfError,
    extract_document,
)
from app.services.imports.mapping import apply_mapping

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> bytes:
    return (FIXTURES / f"{name}.pdf").read_bytes()


def upload(client: TestClient, headers: dict, name: str = "clean_table", **params):
    query = "&".join(f"{key}={value}" for key, value in params.items())
    return client.post(
        f"/api/v1/imports/pdf{'?' + query if query else ''}",
        files={"file": (f"{name}.pdf", fixture(name), "application/pdf")},
        headers=headers,
    )


# --------------------------------------------------------------------------
# Extraction
# --------------------------------------------------------------------------


def test_extracts_a_table_from_a_clean_pdf() -> None:
    document = extract_document(fixture("clean_table"))

    assert document.kind == "table"
    assert document.table is not None
    assert document.table.headers[:3] == ["Date", "Meal", "Food"]
    assert len(document.table.rows) == 7


def test_falls_back_to_prose_when_there_is_no_table() -> None:
    document = extract_document(fixture("prose_diary"))

    assert document.kind == "prose"
    assert "Porridge with banana" in document.text


def test_scanned_pdf_is_rejected_with_an_explanation() -> None:
    """No text layer means vision, which is Phase 3c — say so rather than
    returning zero rows with no reason."""
    with pytest.raises(ScannedPdfError) as excinfo:
        extract_document(fixture("scanned"))

    assert "no selectable text" in excinfo.value.detail


def test_non_pdf_content_is_rejected() -> None:
    from app.core.errors import ValidationError

    with pytest.raises(ValidationError):
        extract_document(b"PK\x03\x04 this is a zip file")


def test_oversized_upload_is_rejected() -> None:
    from app.core.errors import PayloadTooLargeError

    oversized = b"%PDF-" + b"0" * (11 * 1024 * 1024)
    with pytest.raises(PayloadTooLargeError):
        extract_document(oversized)


# --------------------------------------------------------------------------
# Applying a mapping
# --------------------------------------------------------------------------


def build_table() -> ExtractedTable:
    return ExtractedTable(
        headers=["Date", "Meal", "Food", "Cals"],
        rows=[
            ["2026-06-15", "Breakfast", "Porridge", "320"],
            ["2026-06-15", "brekkie", "Toast", "150"],
        ],
    )


def base_mapping(**overrides) -> TableMapping:
    defaults = {
        "columns": [
            ColumnMapping(source="Date", target="consumed_on"),
            ColumnMapping(source="Meal", target="meal_type"),
            ColumnMapping(source="Food", target="food_name"),
            ColumnMapping(source="Cals", target="calories"),
        ],
        "date_format": DateFormat.ISO,
    }
    return TableMapping(**{**defaults, **overrides})


def test_a_fully_mapped_row_is_ready_to_import() -> None:
    rows = apply_mapping(build_table(), base_mapping())

    assert rows[0].status == "ok"
    assert rows[0].issues == []
    assert rows[0].entry is not None
    assert rows[0].entry.food_name == "Porridge"
    assert rows[0].entry.calories == 320
    assert rows[0].entry.meal_type == MealType.BREAKFAST
    # Row 1 uses a synonym, which resolves to the same meal.
    assert rows[1].entry.meal_type == MealType.BREAKFAST


def test_row_without_a_date_is_invalid_not_silently_dropped() -> None:
    table = ExtractedTable(
        headers=["Date", "Meal", "Food", "Cals"],
        rows=[["", "Lunch", "Soup", "200"]],
    )
    rows = apply_mapping(table, base_mapping())

    assert rows[0].status == "invalid"
    assert rows[0].entry is None
    assert any("date" in issue.message.lower() for issue in rows[0].issues)
    # The original cells survive so the user can see what was there.
    assert rows[0].raw["Food"] == "Soup"


def test_unreadable_number_is_reported_against_its_field() -> None:
    table = ExtractedTable(
        headers=["Date", "Meal", "Food", "Cals"],
        rows=[["2026-06-15", "Lunch", "Soup", "lots"]],
    )
    rows = apply_mapping(table, base_mapping())

    assert rows[0].status == "needs_review"
    assert any(issue.field == "calories" for issue in rows[0].issues)


def test_missing_meal_type_is_defaulted_and_flagged() -> None:
    table = ExtractedTable(headers=["Date", "Food", "Cals"], rows=[["2026-06-15", "Soup", "200"]])
    mapping = TableMapping(
        columns=[
            ColumnMapping(source="Date", target="consumed_on"),
            ColumnMapping(source="Food", target="food_name"),
            ColumnMapping(source="Cals", target="calories"),
        ],
        date_format=DateFormat.ISO,
        default_meal_type=MealType.SNACK,
    )

    rows = apply_mapping(table, mapping)

    assert rows[0].entry.meal_type == MealType.SNACK
    assert rows[0].status == "needs_review"
    assert any(issue.field == "meal_type" for issue in rows[0].issues)


def test_per_100g_values_are_scaled_to_the_serving() -> None:
    table = ExtractedTable(
        headers=["Date", "Food", "Serving", "Cals"],
        rows=[["2026-06-15", "Cheddar", "30", "410"]],
    )
    mapping = TableMapping(
        columns=[
            ColumnMapping(source="Date", target="consumed_on"),
            ColumnMapping(source="Food", target="food_name"),
            ColumnMapping(source="Serving", target="quantity"),
            ColumnMapping(source="Cals", target="calories"),
        ],
        date_format=DateFormat.ISO,
        basis=NutritionBasis.PER_100G,
        quantity_column="Serving",
        default_meal_type=MealType.SNACK,
    )

    rows = apply_mapping(table, mapping)

    assert rows[0].entry.calories == pytest.approx(123.0)  # 410 × 30/100
    assert rows[0].entry.unit == "30 g"


def test_per_100g_without_a_serving_column_is_flagged_not_guessed() -> None:
    table = ExtractedTable(
        headers=["Date", "Food", "Cals"], rows=[["2026-06-15", "Cheddar", "410"]]
    )
    mapping = TableMapping(
        columns=[
            ColumnMapping(source="Date", target="consumed_on"),
            ColumnMapping(source="Food", target="food_name"),
            ColumnMapping(source="Cals", target="calories"),
        ],
        date_format=DateFormat.ISO,
        basis=NutritionBasis.PER_100G,
        default_meal_type=MealType.SNACK,
    )

    rows = apply_mapping(table, mapping)

    assert rows[0].entry.calories == 410  # left alone rather than invented
    assert any("serving size" in issue.message for issue in rows[0].issues)


def test_future_date_is_flagged_as_a_probable_format_error() -> None:
    tomorrow = date.today() + timedelta(days=1)
    table = ExtractedTable(
        headers=["Date", "Meal", "Food", "Cals"],
        rows=[[tomorrow.isoformat(), "Lunch", "Soup", "200"]],
    )
    rows = apply_mapping(table, base_mapping())

    # EntryCreate rejects future dates outright, so the row cannot be built.
    assert rows[0].status == "invalid"
    assert any("future" in issue.message.lower() for issue in rows[0].issues)


def test_low_confidence_column_puts_its_rows_up_for_review() -> None:
    mapping = base_mapping(
        columns=[
            ColumnMapping(source="Date", target="consumed_on"),
            ColumnMapping(source="Meal", target="meal_type"),
            ColumnMapping(source="Food", target="food_name"),
            ColumnMapping(source="Cals", target="calories", confidence=0.3),
        ]
    )
    rows = apply_mapping(build_table(), mapping)

    assert rows[0].status == "needs_review"
    assert any("Unsure" in issue.message for issue in rows[0].issues)


def test_blank_row_is_marked_invalid() -> None:
    table = ExtractedTable(headers=["Date", "Meal", "Food", "Cals"], rows=[["", "", "", ""]])
    rows = apply_mapping(table, base_mapping())

    assert rows[0].status == "invalid"
    assert rows[0].issues[0].message == "Blank row."


# --------------------------------------------------------------------------
# The prose path's anti-hallucination check
# --------------------------------------------------------------------------


def test_a_number_absent_from_the_source_is_discarded() -> None:
    """The one guarantee the prose path can offer: no invented figures."""
    from app.services.imports.prose import _to_draft

    source = "Breakfast: porridge with banana"  # no calorie count anywhere
    fabricated = RawEntry(
        consumed_on="2026-06-15", meal_type="breakfast", food_name="Porridge", calories=320
    )

    row = _to_draft(0, fabricated, source, base_mapping())

    assert row.entry is not None
    assert row.entry.calories == 0  # dropped, not carried through
    assert any("not in the document" in issue.message for issue in row.issues)


def test_a_number_present_in_the_source_is_kept() -> None:
    from app.services.imports.prose import _to_draft

    source = "Breakfast: porridge with banana - 320 cal"
    genuine = RawEntry(
        consumed_on="2026-06-15", meal_type="breakfast", food_name="Porridge", calories=320
    )

    row = _to_draft(0, genuine, source, base_mapping())

    assert row.entry.calories == 320
    # Still never "ok" — a transcribed row always gets a human look.
    assert row.status == "needs_review"


# --------------------------------------------------------------------------
# The endpoint
# --------------------------------------------------------------------------


def test_preview_returns_rows_without_saving_anything(
    client: TestClient, auth_headers: dict
) -> None:
    """The guarantee the whole feature rests on."""
    before = client.get("/api/v1/entries", headers=auth_headers).json()["total"]

    response = upload(client, auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["row_count"] == 7
    assert body["source_kind"] == "table"

    after = client.get("/api/v1/entries", headers=auth_headers).json()["total"]
    assert after == before == 0


def test_preview_reports_what_it_understood(client: TestClient, auth_headers: dict) -> None:
    body = upload(client, auth_headers).json()

    targets = {column["target"] for column in body["mapping"]["columns"]}
    assert {"consumed_on", "meal_type", "food_name", "calories"} <= targets
    assert body["mapping"]["date_format"] == "ISO"
    assert body["summary"]["ready"] == 7


def test_date_format_override_changes_how_dates_are_read(
    client: TestClient, auth_headers: dict
) -> None:
    """The single most likely thing to be wrong, and one click to correct."""
    default = upload(client, auth_headers, "units_per_100g").json()
    assert default["rows"][0]["entry"]["consumed_on"] == "2026-06-15"

    flipped = upload(client, auth_headers, "units_per_100g", date_format="MDY").json()
    # 15/06 has no 15th month, so under MDY the row becomes unreadable —
    # which is exactly the visible signal that the override was wrong.
    assert flipped["mapping"]["date_format"] == "MDY"
    assert flipped["summary"]["invalid"] == flipped["summary"]["row_count"]


def test_default_meal_type_override_is_applied(client: TestClient, auth_headers: dict) -> None:
    body = upload(client, auth_headers, "units_per_100g", default_meal_type="lunch").json()

    assert all(row["entry"]["meal_type"] == "lunch" for row in body["rows"] if row["entry"])


def test_prose_diary_is_read_when_there_is_no_table(client: TestClient, auth_headers: dict) -> None:
    body = upload(client, auth_headers, "prose_diary").json()

    assert body["source_kind"] == "prose"
    assert body["summary"]["row_count"] > 0
    names = {row["entry"]["food_name"] for row in body["rows"] if row["entry"]}
    assert any("Porridge" in name for name in names)


def test_scanned_pdf_gets_a_clear_error(client: TestClient, auth_headers: dict) -> None:
    response = upload(client, auth_headers, "scanned")

    assert response.status_code == 422
    assert "no selectable text" in response.json()["detail"]


def test_non_pdf_upload_is_rejected(client: TestClient, auth_headers: dict) -> None:
    response = client.post(
        "/api/v1/imports/pdf",
        files={"file": ("notes.txt", b"just some text", "text/plain")},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_import_requires_authentication(client: TestClient) -> None:
    response = client.post(
        "/api/v1/imports/pdf",
        files={"file": ("diary.pdf", fixture("clean_table"), "application/pdf")},
    )
    assert response.status_code == 401


# --------------------------------------------------------------------------
# Commit, duplicates and undo
# --------------------------------------------------------------------------


def commit(client: TestClient, headers: dict, rows: list[dict], filename="clean_table.pdf"):
    return client.post(
        "/api/v1/entries/bulk",
        json={
            "entries": [row["entry"] for row in rows if row["entry"]],
            "import_filename": filename,
        },
        headers=headers,
    )


def test_confirmed_rows_are_written_as_one_undoable_batch(
    client: TestClient, auth_headers: dict
) -> None:
    preview = upload(client, auth_headers).json()

    created = commit(client, auth_headers, preview["rows"]).json()
    assert len(created) == 7
    assert len({row["source_ref"] for row in created}) == 1

    imports = client.get("/api/v1/imports", headers=auth_headers).json()
    assert imports["total"] == 1
    assert imports["items"][0]["row_count"] == 7
    assert imports["items"][0]["entries_remaining"] == 7


def test_undo_removes_the_entries_not_just_the_batch(
    client: TestClient, auth_headers: dict
) -> None:
    """source_ref is ON DELETE SET NULL, so deleting the batch alone would
    orphan the rows and leave the user's data changed."""
    preview = upload(client, auth_headers).json()
    commit(client, auth_headers, preview["rows"])
    batch_id = client.get("/api/v1/imports", headers=auth_headers).json()["items"][0]["id"]

    assert client.delete(f"/api/v1/imports/{batch_id}", headers=auth_headers).status_code == 204

    assert client.get("/api/v1/entries", headers=auth_headers).json()["total"] == 0
    assert client.get("/api/v1/imports", headers=auth_headers).json()["total"] == 0


def test_reimporting_the_same_diary_flags_duplicates(
    client: TestClient, auth_headers: dict
) -> None:
    preview = upload(client, auth_headers).json()
    commit(client, auth_headers, preview["rows"])

    second = upload(client, auth_headers).json()

    assert second["summary"]["duplicates"] == 7
    assert all(row["duplicate_of"] for row in second["rows"])
    assert second["summary"]["ready"] == 0  # every row now wants a look


def test_a_user_cannot_see_or_undo_another_users_import(
    client: TestClient, auth_headers: dict, other_user_headers: dict
) -> None:
    preview = upload(client, auth_headers).json()
    commit(client, auth_headers, preview["rows"])
    batch_id = client.get("/api/v1/imports", headers=auth_headers).json()["items"][0]["id"]

    assert client.get("/api/v1/imports", headers=other_user_headers).json()["total"] == 0
    assert (
        client.delete(f"/api/v1/imports/{batch_id}", headers=other_user_headers).status_code == 404
    )
    # And the owner's entries are untouched.
    assert client.get("/api/v1/entries", headers=auth_headers).json()["total"] == 7


# --------------------------------------------------------------------------
# The stub provider
# --------------------------------------------------------------------------


def test_stub_infers_day_first_from_an_unambiguous_value() -> None:
    from app.ai.stub import StubProvider

    mapping = StubProvider().infer_table_mapping(
        TableSample(
            headers=["Date", "Food", "Cals"],
            # 25 cannot be a month, which settles the order.
            rows=[["15/06/2026", "Cheddar", "410"], ["25/06/2026", "Oats", "380"]],
        )
    )
    assert mapping.date_format == DateFormat.DMY


def test_stub_rejects_nothing_it_cannot_recognize() -> None:
    """Unmatched columns are left unmapped rather than guessed at."""
    from app.ai.stub import StubProvider

    mapping = StubProvider().infer_table_mapping(
        TableSample(
            headers=["Date", "Food", "Mood", "Cals"],
            rows=[["2026-06-15", "Oats", ":)", "380"]],
        )
    )
    assert "Mood" not in {column.source for column in mapping.columns}
