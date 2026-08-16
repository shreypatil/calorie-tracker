"""AI nutrition estimation for manually-typed meals.

The important tests here are the ones about what does *not* come back. This is the only AI path in
the app with no source document to verify against, so the safety property is narrower and entirely
structural: the caller names the fields it wants, and nothing else is ever returned. If that holds,
a value the user typed cannot be replaced no matter what the model says.

`test_a_field_the_caller_did_not_ask_for_is_dropped` and `test_anchors_are_never_returned` are the
two that enforce it. Everything else is ordinary behaviour.
"""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError as PydanticValidationError

from app.schemas.nutrition import ESTIMABLE_FIELDS, NutritionEstimate, NutritionEstimateRequest
from app.services import nutrition_estimate

ESTIMATE = "/api/v1/ai/estimate-nutrition"


class OverreachingProvider:
    """Returns more than it was asked for, which real models do routinely."""

    name = "overreaching"

    def __init__(self, values: dict) -> None:
        self.values = values
        self.seen: NutritionEstimateRequest | None = None

    def estimate_nutrition(self, request: NutritionEstimateRequest) -> NutritionEstimate:
        self.seen = request
        return NutritionEstimate(values=self.values, notes="", confidence=0.6)


def request_for(**overrides) -> NutritionEstimateRequest:
    return NutritionEstimateRequest(
        **{"food_name": "Chicken biryani", "fields": list(ESTIMABLE_FIELDS), **overrides}
    )


# ---------------------------------------------------------------------------
# What must never come back
# ---------------------------------------------------------------------------


def test_a_field_the_caller_did_not_ask_for_is_dropped() -> None:
    """A model volunteering extra fields must not be able to fill them in the user's form."""
    provider = OverreachingProvider({"calories": 500, "protein_g": 30, "iron_mg": 4})

    result = nutrition_estimate.estimate(request_for(fields=["calories"]), provider)

    assert set(result.values) == {"calories"}
    assert "protein_g" not in result.values
    assert "iron_mg" not in result.values


def test_anchors_are_never_returned() -> None:
    """The user typed 300 kcal. Nothing the model says may replace it.

    Filtering happens on the server rather than in the browser precisely so this cannot depend on
    the frontend choosing not to apply a value.
    """
    provider = OverreachingProvider({"calories": 999, "protein_g": 30})

    result = nutrition_estimate.estimate(
        request_for(fields=["calories", "protein_g"], known={"calories": 300}), provider
    )

    assert "calories" not in result.values, "an anchored field must never be estimated over"
    assert result.values["protein_g"] == 30


def test_anchors_reach_the_provider() -> None:
    """They are excluded from the response but must still inform the estimate."""
    provider = OverreachingProvider({"protein_g": 20})

    nutrition_estimate.estimate(
        request_for(fields=["protein_g"], known={"calories": 300}, quantity=350, unit="g"), provider
    )

    assert provider.seen is not None
    assert provider.seen.known == {"calories": 300}
    assert provider.seen.quantity == 350
    assert provider.seen.unit == "g"


def test_values_are_clamped() -> None:
    provider = OverreachingProvider({"calories": -5, "protein_g": 10_000_000})

    result = nutrition_estimate.estimate(request_for(fields=["calories", "protein_g"]), provider)

    assert result.values["calories"] == 0
    assert result.values["protein_g"] == 1_000_000


def test_a_non_numeric_value_is_refused_at_the_schema_boundary() -> None:
    """A model answering "about 500" must not reach the form as a number.

    `NutritionEstimate.values` is typed `dict[str, float]`, so this is caught by Pydantic before
    the service sees it. Pinned here so the typing is understood as load-bearing rather than
    decorative — loosening it to `dict[str, Any]` would silently open this path.
    """
    with pytest.raises(PydanticValidationError):
        NutritionEstimate(values={"calories": "about 500"}, notes="", confidence=0.6)


# ---------------------------------------------------------------------------
# Request validation
# ---------------------------------------------------------------------------


def test_a_non_estimable_field_is_rejected(client: TestClient, auth_headers: dict) -> None:
    """Names resolve through the allow-list, like every other registry in this codebase."""
    response = client.post(
        ESTIMATE,
        json={"food_name": "Biryani", "fields": ["iron_mg"]},
        headers=auth_headers,
    )

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")


def test_an_unknown_anchor_is_rejected(client: TestClient, auth_headers: dict) -> None:
    response = client.post(
        ESTIMATE,
        json={"food_name": "Biryani", "fields": ["calories"], "known": {"vitamin_c_mg": 10}},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_a_food_name_is_required(client: TestClient, auth_headers: dict) -> None:
    response = client.post(
        ESTIMATE, json={"food_name": "", "fields": ["calories"]}, headers=auth_headers
    )
    assert response.status_code == 422


def test_estimate_requires_authentication(client: TestClient) -> None:
    response = client.post(ESTIMATE, json={"food_name": "Biryani", "fields": ["calories"]})
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# The stub path — no key, no network
# ---------------------------------------------------------------------------


def test_the_stub_estimates_a_known_food(client: TestClient, auth_headers: dict) -> None:
    response = client.post(
        ESTIMATE,
        json={"food_name": "Scrambled eggs", "fields": list(ESTIMABLE_FIELDS)},
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    values = response.json()["values"]
    assert set(values) == set(ESTIMABLE_FIELDS)
    assert values["calories"] == pytest.approx(78)


def test_the_stub_scales_a_weight(client: TestClient, auth_headers: dict) -> None:
    """Grams are a weight, not a count of servings — 200 g of rice, not 200 servings."""
    response = client.post(
        ESTIMATE,
        json={"food_name": "Rice", "quantity": 200, "unit": "g", "fields": ["calories"]},
        headers=auth_headers,
    )

    assert response.json()["values"]["calories"] == pytest.approx(412, rel=0.01)


def test_an_unknown_food_is_flagged_rather_than_invented(
    client: TestClient, auth_headers: dict
) -> None:
    response = client.post(
        ESTIMATE,
        json={"food_name": "Grandmother's secret stew", "fields": ["calories"]},
        headers=auth_headers,
    )

    body = response.json()
    assert body["confidence"] < 0.4
    assert body["notes"]


def test_estimating_persists_nothing(client: TestClient, auth_headers: dict) -> None:
    before = client.get("/api/v1/entries", headers=auth_headers).json()["total"]
    client.post(
        ESTIMATE,
        json={"food_name": "Rice", "fields": list(ESTIMABLE_FIELDS)},
        headers=auth_headers,
    )
    assert client.get("/api/v1/entries", headers=auth_headers).json()["total"] == before
