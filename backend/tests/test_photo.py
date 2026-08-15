"""Photo extraction (FR-5).

The tests that carry the design are the verification ones. Because a photograph has no text
layer, the label path has no way to derive its numbers independently of the model — the whole
argument for trusting it rests on checking each reported figure against the model's own
verbatim transcript, and dropping what is not there. `test_a_fabricated_number_is_dropped` is
what keeps that argument true.

Everything runs against the stub provider: no key, no network, no quota.
"""

import io
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.core.errors import PayloadTooLargeError, ValidationError
from app.db.models import MealType
from app.schemas.import_ import NutritionBasis, RowStatus
from app.schemas.photo import PhotoExtraction, PhotoKind, RawFoodItem
from app.services.photo import analyze_photo, build_draft
from app.services.photo.prepare import MAX_EDGE_PX, prepare_image

FIXTURES = Path(__file__).parent / "fixtures"
ANALYZE = "/api/v1/ai/analyze-image"


def upload(client: TestClient, headers: dict, name: str, **params) -> dict:
    with (FIXTURES / name).open("rb") as handle:
        response = client.post(
            ANALYZE,
            params={"kind": "label", **params},
            files={"file": (name, handle, "image/jpeg")},
            headers=headers,
        )
    assert response.status_code == 200, response.text
    return response.json()


def entry_count(client: TestClient, headers: dict) -> int:
    return client.get("/api/v1/entries", headers=headers).json()["total"]


# ---------------------------------------------------------------------------
# Verification — the reason this feature needs no second OCR engine
# ---------------------------------------------------------------------------


def _extraction(transcript: str, **item_values) -> PhotoExtraction:
    return PhotoExtraction(
        kind=PhotoKind.LABEL,
        transcript=transcript,
        basis=NutritionBasis.PER_SERVING,
        items=[RawFoodItem(food_name="Oats", **item_values)],
        confidence=0.9,
    )


def _draft(extraction: PhotoExtraction):
    return build_draft(
        extraction, filename="x.jpg", meal_type=MealType.BREAKFAST, on_date=date.today()
    ).rows[0]


def test_a_fabricated_number_is_dropped() -> None:
    """A figure the model reported that is not on the label must not reach the entry.

    This is the failure that matters: an invented calorie count is indistinguishable from a
    correct one by eye, so nothing downstream can catch it.
    """
    row = _draft(_extraction("Energy 379 kcal\nProtein 13.2 g", calories=379, protein_g=99.9))

    assert row.entry.calories == 379
    # Not merely zeroed — never set, and said so.
    assert row.entry.protein_g == 0
    assert any(issue.field == "protein_g" for issue in row.issues)
    assert "does not appear" in next(i.message for i in row.issues if i.field == "protein_g")


def test_a_transcribed_number_is_kept() -> None:
    row = _draft(_extraction("Energy 379 kcal\nProtein 13.2 g", calories=379, protein_g=13.2))
    assert row.entry.calories == 379
    assert row.entry.protein_g == 13.2
    assert not [issue for issue in row.issues if issue.field]


def test_thousands_separators_still_verify() -> None:
    """`1,234` on the panel and `1234.0` in the JSON are the same number."""
    row = _draft(_extraction("Energy 1,234 kcal", calories=1234))
    assert row.entry.calories == 1234


def test_atwater_mismatch_is_flagged_but_kept() -> None:
    """Fibre and sugar alcohols make honest deviation possible, so this warns, never deletes."""
    transcript = "Energy 850 kcal\nProtein 13 g\nCarbohydrate 68 g\nFat 6 g"
    row = _draft(_extraction(transcript, calories=850, protein_g=13, carbs_g=68, fat_g=6))

    assert row.entry.calories == 850, "a flagged value is still shown to the user"
    assert any("misread" in issue.message for issue in row.issues)


def test_partial_macros_are_not_flagged() -> None:
    """With fat and carbs missing, the implied total must fall short — flagging it is noise.

    A panel listing only protein would otherwise be reported as misread every single time.
    """
    row = _draft(_extraction("Energy 379 kcal\nProtein 13.2 g", calories=379, protein_g=13.2))
    assert not any("misread" in issue.message for issue in row.issues)


def test_consistent_macros_are_not_flagged() -> None:
    transcript = "Energy 379 kcal\nProtein 13.2 g\nCarbohydrate 67.7 g\nFat 6.5 g"
    row = _draft(_extraction(transcript, calories=379, protein_g=13.2, carbs_g=67.7, fat_g=6.5))
    assert not any("misread" in issue.message for issue in row.issues)


def test_meal_photos_skip_the_transcript_check() -> None:
    """Nothing is written on a plate, so there is nothing to check against — only to label."""
    extraction = PhotoExtraction(
        kind=PhotoKind.MEAL,
        transcript="",
        items=[RawFoodItem(food_name="Rice", quantity=200, unit="g", calories=260)],
        confidence=0.7,
    )
    row = _draft(extraction)

    assert row.entry.calories == 260
    assert any("Estimated from a photo" in issue.message for issue in row.issues)


def test_photo_rows_are_never_marked_ready() -> None:
    for extraction in (
        _extraction("Energy 379 kcal", calories=379),
        PhotoExtraction(kind=PhotoKind.MEAL, items=[RawFoodItem(food_name="Rice")]),
    ):
        assert _draft(extraction).status is RowStatus.NEEDS_REVIEW


def test_per_100g_scales_to_the_stated_serving() -> None:
    extraction = PhotoExtraction(
        kind=PhotoKind.LABEL,
        transcript="Per 100 g\nEnergy 379 kcal\nProtein 13.2 g\nServing size 40 g",
        basis=NutritionBasis.PER_100G,
        serving_size_g=40,
        items=[RawFoodItem(food_name="Oats", unit="g", calories=379, protein_g=13.2)],
    )
    row = _draft(extraction)

    assert row.entry.calories == pytest.approx(151.6)
    assert row.entry.protein_g == pytest.approx(5.28)
    # One serving of 40 g — not 40 servings, and not the model's stray "g".
    assert row.entry.quantity == 1.0
    assert row.entry.unit == "40 g"


def test_per_100g_without_a_serving_size_is_left_alone() -> None:
    """Inventing a serving weight would silently rewrite every figure on the label."""
    extraction = PhotoExtraction(
        kind=PhotoKind.LABEL,
        transcript="Per 100 g\nEnergy 379 kcal",
        basis=NutritionBasis.PER_100G,
        serving_size_g=None,
        items=[RawFoodItem(food_name="Oats", calories=379)],
    )
    row = _draft(extraction)

    assert row.entry.calories == 379
    assert row.entry.unit == "100 g"
    assert any("per 100 g" in issue.message for issue in row.issues)


def test_low_confidence_is_surfaced() -> None:
    extraction = _extraction("Energy 379 kcal", calories=379)
    extraction.confidence = 0.2
    draft = build_draft(
        extraction, filename="x.jpg", meal_type=MealType.SNACK, on_date=date.today()
    )
    assert "hard to read" in draft.notes


# ---------------------------------------------------------------------------
# Image preparation
# ---------------------------------------------------------------------------


def _open(name: str) -> Image.Image:
    return Image.open(io.BytesIO((FIXTURES / name).read_bytes()))


def test_exif_rotation_is_applied() -> None:
    """A phone stores a portrait photo sideways plus a tag. Ignore the tag, misread the label."""
    stored = _open("label_rotated.jpg")
    assert stored.height > stored.width, "fixture should be stored rotated"

    prepared = prepare_image(
        (FIXTURES / "label_rotated.jpg").read_bytes(),
        content_type="image/jpeg",
        max_bytes=10_000_000,
    )
    upright = _open("label.jpg")
    assert prepared.width > prepared.height
    assert prepared.width / prepared.height == pytest.approx(
        upright.width / upright.height, rel=0.1
    )


def test_large_images_are_downscaled() -> None:
    buffer = io.BytesIO()
    Image.new("RGB", (4000, 3000), "white").save(buffer, "JPEG")

    prepared = prepare_image(buffer.getvalue(), content_type="image/jpeg", max_bytes=10_000_000)

    assert max(prepared.width, prepared.height) == MAX_EDGE_PX
    assert prepared.media_type == "image/jpeg"


def test_a_decompression_bomb_is_refused() -> None:
    """Small on disk, enormous in memory — a byte-size limit alone does not catch this."""
    with pytest.raises(PayloadTooLargeError):
        prepare_image(
            (FIXTURES / "huge.png").read_bytes(), content_type="image/png", max_bytes=10_000_000
        )


def test_oversized_uploads_are_refused() -> None:
    with pytest.raises(PayloadTooLargeError):
        prepare_image(
            (FIXTURES / "label.jpg").read_bytes(), content_type="image/jpeg", max_bytes=100
        )


def test_non_images_are_refused() -> None:
    with pytest.raises(ValidationError):
        prepare_image(b"not an image", content_type="application/pdf", max_bytes=10_000_000)
    with pytest.raises(ValidationError):
        prepare_image(b"not an image at all", content_type="image/png", max_bytes=10_000_000)


def test_heic_gets_a_useful_message() -> None:
    heic = b"\x00\x00\x00\x20ftypheic\x00\x00\x00\x00" + b"\x00" * 64
    with pytest.raises(ValidationError) as caught:
        prepare_image(heic, content_type=None, max_bytes=10_000_000)
    assert "HEIC" in caught.value.detail


def test_metadata_does_not_survive() -> None:
    """Re-encoding drops EXIF, including the GPS tags a phone attaches. We never want them."""
    prepared = prepare_image(
        (FIXTURES / "label_rotated.jpg").read_bytes(),
        content_type="image/jpeg",
        max_bytes=10_000_000,
    )
    assert not Image.open(io.BytesIO(prepared.data)).getexif()


# ---------------------------------------------------------------------------
# The endpoint
# ---------------------------------------------------------------------------


def test_label_scan_returns_a_reviewable_draft(client: TestClient, auth_headers: dict) -> None:
    body = upload(client, auth_headers, "label.jpg", meal_type="breakfast")

    assert body["kind"] == "label"
    assert len(body["rows"]) == 1
    row = body["rows"][0]
    assert row["status"] == "needs_review"
    assert row["entry"]["source"] == "photo"
    assert row["entry"]["meal_type"] == "breakfast"
    # The stub's label is per 100 g with a 40 g serving: 379 * 0.4.
    assert row["entry"]["calories"] == pytest.approx(151.6)


def test_meal_scan_returns_one_row_per_food(client: TestClient, auth_headers: dict) -> None:
    body = upload(client, auth_headers, "plate.jpg", kind="meal", meal_type="dinner")

    assert body["kind"] == "meal"
    assert len(body["rows"]) == 3
    names = {row["entry"]["food_name"] for row in body["rows"]}
    assert "White rice" in names
    assert all(row["entry"]["meal_type"] == "dinner" for row in body["rows"])


def test_analyzing_persists_nothing(client: TestClient, auth_headers: dict) -> None:
    before = entry_count(client, auth_headers)
    upload(client, auth_headers, "label.jpg")
    upload(client, auth_headers, "plate.jpg", kind="meal")
    assert entry_count(client, auth_headers) == before


def test_a_non_image_upload_is_rejected(client: TestClient, auth_headers: dict) -> None:
    response = client.post(
        ANALYZE,
        params={"kind": "label"},
        files={"file": ("diary.pdf", b"%PDF-1.4 nope", "application/pdf")},
        headers=auth_headers,
    )
    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")


def test_an_empty_upload_is_rejected(client: TestClient, auth_headers: dict) -> None:
    response = client.post(
        ANALYZE,
        params={"kind": "label"},
        files={"file": ("empty.jpg", b"", "image/jpeg")},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_an_unknown_kind_is_rejected(client: TestClient, auth_headers: dict) -> None:
    with (FIXTURES / "label.jpg").open("rb") as handle:
        response = client.post(
            ANALYZE,
            params={"kind": "barcode"},
            files={"file": ("label.jpg", handle, "image/jpeg")},
            headers=auth_headers,
        )
    assert response.status_code == 422


def test_analyze_requires_authentication(client: TestClient) -> None:
    with (FIXTURES / "label.jpg").open("rb") as handle:
        response = client.post(
            ANALYZE, params={"kind": "label"}, files={"file": ("label.jpg", handle, "image/jpeg")}
        )
    assert response.status_code == 401


def test_the_draft_commits_through_the_normal_entry_path(
    client: TestClient, auth_headers: dict
) -> None:
    """Extracted rows must travel the same validation path as anything typed by hand."""
    body = upload(client, auth_headers, "plate.jpg", kind="meal", meal_type="lunch")
    entries = [row["entry"] for row in body["rows"]]

    response = client.post("/api/v1/entries/bulk", json={"entries": entries}, headers=auth_headers)
    assert response.status_code == 201, response.text

    listed = client.get("/api/v1/entries", headers=auth_headers).json()
    assert listed["total"] == 3
    assert {item["source"] for item in listed["items"]} == {"photo"}


def test_the_analyzed_image_is_never_stored(
    tmp_path, client: TestClient, auth_headers: dict
) -> None:
    """FR-5: the bytes are processed in memory and discarded."""
    upload(client, auth_headers, "label.jpg")

    data_dir = Path("data")
    written = list(data_dir.rglob("*.jpg")) if data_dir.exists() else []
    assert written == []


def test_stub_analysis_needs_no_credentials() -> None:
    """`git clone && make dev` must exercise this with no key at all."""
    from app.ai.stub import StubProvider

    draft = analyze_photo(
        (FIXTURES / "label.jpg").read_bytes(),
        filename="label.jpg",
        content_type="image/jpeg",
        kind=PhotoKind.LABEL,
        meal_type=MealType.SNACK,
        on_date=date.today(),
        provider=StubProvider(),
        max_bytes=10_000_000,
    )
    assert draft.rows and draft.rows[0].entry is not None
