"""Chat endpoint behaviour (FR-6).

The load-bearing test in this file is `test_proposing_a_write_changes_nothing`. Everything
about the design depends on a write tool being *proposed* rather than executed, and that is
exactly the kind of guarantee that a refactor can quietly remove without breaking anything
else. The rest covers the action lifecycle, isolation, and the standard list contract.

All of it runs against the stub provider, so the suite needs no key, no network and no quota.
"""

from datetime import date

from fastapi.testclient import TestClient

CHAT = "/api/v1/chat/messages"


def send(client: TestClient, headers: dict, message: str) -> dict:
    response = client.post(CHAT, json={"message": message}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def pending_actions(turn: dict) -> list[dict]:
    return [
        action
        for message in turn["messages"]
        for action in message["actions"]
        if action["status"] == "pending"
    ]


def entry_count(client: TestClient, headers: dict) -> int:
    response = client.get("/api/v1/entries", headers=headers)
    assert response.status_code == 200
    return response.json()["total"]


# ---------------------------------------------------------------------------
# The confirmation gate
# ---------------------------------------------------------------------------


def test_proposing_a_write_changes_nothing(client: TestClient, auth_headers: dict) -> None:
    """A write tool must never execute inside the agent loop."""
    turn = send(client, auth_headers, "log 2 eggs and toast for breakfast")

    actions = pending_actions(turn)
    assert len(actions) == 1
    assert actions[0]["tool"] == "log_meal"
    assert entry_count(client, auth_headers) == 0


def test_confirming_writes_the_entries(client: TestClient, auth_headers: dict) -> None:
    turn = send(client, auth_headers, "log 2 eggs and toast for breakfast")
    action = pending_actions(turn)[0]

    response = client.post(
        f"/api/v1/chat/actions/{action['id']}/confirm", json={}, headers=auth_headers
    )
    assert response.status_code == 200, response.text
    assert response.json()["actions"][0]["status"] == "confirmed"

    entries = client.get("/api/v1/entries", headers=auth_headers).json()
    assert entries["total"] == 2
    names = {item["food_name"].lower() for item in entries["items"]}
    assert "eggs" in names and "toast" in names
    # Provenance: every row says where it came from.
    assert {item["source"] for item in entries["items"]} == {"chat"}
    assert {item["meal_type"] for item in entries["items"]} == {"breakfast"}


def test_confirming_twice_is_rejected(client: TestClient, auth_headers: dict) -> None:
    turn = send(client, auth_headers, "log 1 apple")
    action = pending_actions(turn)[0]
    url = f"/api/v1/chat/actions/{action['id']}/confirm"

    assert client.post(url, json={}, headers=auth_headers).status_code == 200
    replay = client.post(url, json={}, headers=auth_headers)
    assert replay.status_code == 409
    assert client.get("/api/v1/entries", headers=auth_headers).json()["total"] == 1


def test_discarding_writes_nothing(client: TestClient, auth_headers: dict) -> None:
    turn = send(client, auth_headers, "log 1 banana")
    action = pending_actions(turn)[0]

    response = client.post(f"/api/v1/chat/actions/{action['id']}/discard", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["actions"][0]["status"] == "discarded"
    assert entry_count(client, auth_headers) == 0

    # And a discarded draft cannot then be confirmed.
    late = client.post(
        f"/api/v1/chat/actions/{action['id']}/confirm", json={}, headers=auth_headers
    )
    assert late.status_code == 409


def test_confirm_accepts_corrected_arguments(client: TestClient, auth_headers: dict) -> None:
    """The user fixing a number before committing is the point of the draft."""
    turn = send(client, auth_headers, "log 1 apple")
    action = pending_actions(turn)[0]

    corrected = {
        "items": [
            {
                "food_name": "Granny Smith apple",
                "meal_type": "snack",
                "calories": 72,
                "quantity": 1,
            }
        ]
    }
    response = client.post(
        f"/api/v1/chat/actions/{action['id']}/confirm",
        json={"arguments": corrected},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text

    items = client.get("/api/v1/entries", headers=auth_headers).json()["items"]
    assert items[0]["food_name"] == "Granny Smith apple"
    assert items[0]["calories"] == 72


def test_confirm_revalidates_corrected_arguments(client: TestClient, auth_headers: dict) -> None:
    """Edited arguments go through the same model — a bad edit is a 422, not a 500."""
    turn = send(client, auth_headers, "log 1 apple")
    action = pending_actions(turn)[0]

    response = client.post(
        f"/api/v1/chat/actions/{action['id']}/confirm",
        json={"arguments": {"items": [{"food_name": "x", "meal_type": "brunch"}]}},
        headers=auth_headers,
    )
    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["errors"]
    assert entry_count(client, auth_headers) == 0


def test_unknown_action_is_not_found(client: TestClient, auth_headers: dict) -> None:
    response = client.post(
        "/api/v1/chat/actions/does-not-exist/confirm", json={}, headers=auth_headers
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


def test_read_tools_answer_without_proposing_anything(
    client: TestClient, auth_headers: dict
) -> None:
    turn = send(client, auth_headers, "what did I eat today?")

    roles = [message["role"] for message in turn["messages"]]
    assert roles[0] == "user"
    assert "tool" in roles, "a read tool should have run inside the loop"
    assert roles[-1] == "assistant"
    assert pending_actions(turn) == []
    assert turn["messages"][-1]["content"]


def test_goal_can_be_read_and_set_through_chat(client: TestClient, auth_headers: dict) -> None:
    turn = send(client, auth_headers, "set my calorie goal to 2200")
    action = pending_actions(turn)[0]
    assert action["tool"] == "set_goal"

    confirm = client.post(
        f"/api/v1/chat/actions/{action['id']}/confirm", json={}, headers=auth_headers
    )
    assert confirm.status_code == 200, confirm.text

    current = client.get("/api/v1/goals/current", headers=auth_headers).json()
    assert current["calorie_target"] == 2200
    # Versioned, not mutated: the new targets start today rather than rewriting history.
    assert current["effective_from"] == date.today().isoformat()


def test_unrecognised_message_gets_a_helpful_reply(client: TestClient, auth_headers: dict) -> None:
    turn = send(client, auth_headers, "tell me a joke about penguins")
    assert pending_actions(turn) == []
    assert "log meals" in turn["messages"][-1]["content"]


# ---------------------------------------------------------------------------
# Transcript
# ---------------------------------------------------------------------------


def test_conversation_persists_and_paginates(client: TestClient, auth_headers: dict) -> None:
    send(client, auth_headers, "what's my goal?")
    send(client, auth_headers, "what did I eat today?")

    response = client.get(CHAT, params={"page_size": 2}, headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["page_size"] == 2
    assert len(body["items"]) == 2
    assert body["total"] > 2
    assert body["has_next"] is True


def test_clearing_removes_the_conversation(client: TestClient, auth_headers: dict) -> None:
    send(client, auth_headers, "what's my goal?")
    assert client.delete(CHAT, headers=auth_headers).status_code == 204
    assert client.get(CHAT, headers=auth_headers).json()["total"] == 0


def test_chat_requires_authentication(client: TestClient) -> None:
    for method, url in (
        ("get", CHAT),
        ("delete", CHAT),
        ("post", "/api/v1/chat/actions/abc/discard"),
    ):
        assert getattr(client, method)(url).status_code == 401
    assert client.post(CHAT, json={"message": "hi"}).status_code == 401


def test_empty_message_is_rejected(client: TestClient, auth_headers: dict) -> None:
    response = client.post(CHAT, json={"message": "   "}, headers=auth_headers)
    # Whitespace is accepted by min_length but produces no intent; an empty string is not.
    assert response.status_code in (200, 422)
    assert client.post(CHAT, json={"message": ""}, headers=auth_headers).status_code == 422


# ---------------------------------------------------------------------------
# Isolation
# ---------------------------------------------------------------------------


def test_users_cannot_see_each_others_conversations(
    client: TestClient, auth_headers: dict, other_user_headers: dict
) -> None:
    send(client, auth_headers, "what's my goal?")
    assert client.get(CHAT, headers=other_user_headers).json()["total"] == 0


def test_users_cannot_confirm_each_others_actions(
    client: TestClient, auth_headers: dict, other_user_headers: dict
) -> None:
    turn = send(client, auth_headers, "log 1 apple")
    action = pending_actions(turn)[0]

    for verb in ("confirm", "discard"):
        response = client.post(
            f"/api/v1/chat/actions/{action['id']}/{verb}",
            json={},
            headers=other_user_headers,
        )
        # 404, not 403: the API never confirms another user's action exists.
        assert response.status_code == 404

    # The owner's draft is untouched and still usable.
    assert (
        client.post(
            f"/api/v1/chat/actions/{action['id']}/confirm", json={}, headers=auth_headers
        ).status_code
        == 200
    )


def test_clearing_only_affects_the_calling_user(
    client: TestClient, auth_headers: dict, other_user_headers: dict
) -> None:
    send(client, auth_headers, "what's my goal?")
    send(client, other_user_headers, "what's my goal?")

    client.delete(CHAT, headers=auth_headers)

    assert client.get(CHAT, headers=auth_headers).json()["total"] == 0
    assert client.get(CHAT, headers=other_user_headers).json()["total"] > 0
