"""The tool layer: dispatch, argument validation, schema generation, and the loop's bounds.

These tests sit below the HTTP layer, on the registry and the agent directly. The isolation
assertions here are the important ones — they check that a tool handler given user A's ID
cannot reach user B's rows even when handed B's entry ID outright, which is the failure the
whole "services always take the owning user_id" rule exists to prevent.
"""

import uuid
from datetime import date

import pytest
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationError
from app.db.models import EntrySource, MealType, User
from app.schemas.chat import AssistantTurn, ProviderMessage, ToolCall
from app.schemas.entry import EntryCreate
from app.services import entries as entries_service
from app.services.chat import agent
from app.services.chat.dispatch import resolve, validate_args
from app.services.chat.schema import json_schema_for, tool_specs
from app.services.chat.tools import TOOLS, LogMealArgs, NutritionReportArgs, QueryEntriesArgs


def make_user(session: Session, email: str) -> User:
    user = User(email=email, password_hash="x", display_name="T")
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def add_entry(session: Session, user_id: uuid.UUID, name: str = "Rice") -> uuid.UUID:
    entry = entries_service.create_entry(
        session,
        user_id,
        EntryCreate(
            consumed_on=date.today(),
            meal_type=MealType.LUNCH,
            food_name=name,
            calories=200,
        ),
    )
    return entry.id


# ---------------------------------------------------------------------------
# Registry and schema
# ---------------------------------------------------------------------------


def test_every_tool_has_a_usable_spec() -> None:
    specs = tool_specs()
    assert {spec.name for spec in specs} == set(TOOLS)
    for spec in specs:
        assert spec.description
        assert spec.parameters["type"] == "object"


def test_generated_schemas_are_flat_and_non_nullable() -> None:
    """`$ref`, `$defs` and null unions all break at least one supported provider."""
    for tool in TOOLS.values():
        schema = json_schema_for(tool.args_model)
        blob = repr(schema)
        assert "$ref" not in blob, tool.name
        assert "$defs" not in blob, tool.name
        assert "'null'" not in blob, tool.name


def test_nested_models_are_inlined() -> None:
    schema = json_schema_for(LogMealArgs)
    item = schema["properties"]["items"]["items"]
    assert item["type"] == "object"
    assert "food_name" in item["properties"]
    assert item["properties"]["meal_type"]["enum"]


def test_no_tool_accepts_a_user_identifier() -> None:
    """Identity is injected, never named. A user field would be a way in."""
    for tool in TOOLS.values():
        fields = set(tool.args_model.model_fields)
        assert not fields & {"user_id", "user", "owner_id", "email"}, tool.name


def test_unknown_tool_is_rejected_with_the_allowed_names() -> None:
    with pytest.raises(ValidationError) as caught:
        resolve("drop_all_tables")
    assert "log_meal" in caught.value.errors[0]["message"]


def test_bad_arguments_are_rejected_before_a_service_runs() -> None:
    with pytest.raises(ValidationError) as caught:
        validate_args(TOOLS["log_meal"], {"items": [{"food_name": "x", "meal_type": "brunch"}]})
    assert caught.value.errors


def test_unknown_metric_never_reaches_the_query(db_session: Session) -> None:
    user = make_user(db_session, "metrics@example.com")
    args = NutritionReportArgs(metrics=["calories); DROP TABLE users;--"], group_by=[])
    with pytest.raises(ValidationError):
        TOOLS["nutrition_report"].handler(db_session, user.id, args)


# ---------------------------------------------------------------------------
# Handlers delegate correctly
# ---------------------------------------------------------------------------


def test_log_meal_stamps_the_chat_source(db_session: Session) -> None:
    user = make_user(db_session, "logger@example.com")
    args = validate_args(
        TOOLS["log_meal"],
        {"items": [{"food_name": "Oats", "meal_type": "breakfast", "calories": 150}]},
    )
    result = TOOLS["log_meal"].handler(db_session, user.id, args)

    assert result["total_calories"] == 150
    rows, _ = entries_service.list_entries(db_session, user.id, _page())
    assert rows[0].source is EntrySource.CHAT


def test_query_entries_returns_ids_so_rows_can_be_edited(db_session: Session) -> None:
    user = make_user(db_session, "query@example.com")
    entry_id = add_entry(db_session, user.id)

    result = TOOLS["query_entries"].handler(db_session, user.id, QueryEntriesArgs())
    assert result["entries"][0]["id"] == str(entry_id)


def test_write_tools_are_declared(db_session: Session) -> None:
    writing = {name for name, tool in TOOLS.items() if tool.writes}
    assert writing == {"log_meal", "update_entry", "delete_entry", "set_goal", "log_weight"}


# ---------------------------------------------------------------------------
# Isolation, at the handler level
# ---------------------------------------------------------------------------


def _page():
    from app.core.pagination import PageParams

    return PageParams(page=1, page_size=50)


def test_a_tool_cannot_read_another_users_entries(db_session: Session) -> None:
    alice = make_user(db_session, "alice@example.com")
    bob = make_user(db_session, "bob@example.com")
    add_entry(db_session, bob.id, "Bob's lunch")

    result = TOOLS["query_entries"].handler(db_session, alice.id, QueryEntriesArgs())
    assert result["entries"] == []
    assert result["total_matching"] == 0


@pytest.mark.parametrize("tool_name", ["update_entry", "delete_entry"])
def test_a_tool_cannot_mutate_another_users_entry(db_session: Session, tool_name: str) -> None:
    """Even handed the exact ID, the owning user_id scopes it out of reach."""
    alice = make_user(db_session, f"alice-{tool_name}@example.com")
    bob = make_user(db_session, f"bob-{tool_name}@example.com")
    entry_id = add_entry(db_session, bob.id)

    arguments = {"entry_id": str(entry_id)}
    if tool_name == "update_entry":
        arguments["food_name"] = "hijacked"

    tool = TOOLS[tool_name]
    args = validate_args(tool, arguments)
    with pytest.raises(NotFoundError):
        tool.handler(db_session, alice.id, args)

    still_there = entries_service.get_entry(db_session, bob.id, entry_id)
    assert still_there.food_name == "Rice"


# ---------------------------------------------------------------------------
# The loop
# ---------------------------------------------------------------------------


class LoopingProvider:
    """A provider that always asks for another read — to prove the loop is bounded."""

    name = "looping"

    def __init__(self) -> None:
        self.calls = 0

    def converse(self, messages, tools) -> AssistantTurn:
        self.calls += 1
        return AssistantTurn(
            content="",
            tool_calls=[ToolCall(id=f"c{self.calls}", name="get_goal", arguments={})],
        )


class BadNameProvider:
    name = "bad-name"

    def __init__(self) -> None:
        self.calls = 0

    def converse(self, messages: list[ProviderMessage], tools) -> AssistantTurn:
        self.calls += 1
        if self.calls == 1:
            return AssistantTurn(tool_calls=[ToolCall(id="c1", name="rm_rf", arguments={})])
        return AssistantTurn(content="Sorry, I could not do that.")


def test_the_tool_loop_is_bounded(db_session: Session) -> None:
    user = make_user(db_session, "loop@example.com")
    provider = LoopingProvider()

    rows = agent.send_message(db_session, user.id, "what's my goal?", provider)

    assert provider.calls == agent.MAX_TOOL_ITERATIONS
    assert rows[-1].content, "the turn must still end with something to show the user"


def test_an_invented_tool_name_is_reported_back_not_raised(db_session: Session) -> None:
    """A wrong guess is the model's problem to fix, not a 500 for the user."""
    user = make_user(db_session, "badname@example.com")
    provider = BadNameProvider()

    rows = agent.send_message(db_session, user.id, "do something", provider)

    assert provider.calls == 2
    tool_rows = [row for row in rows if row.role.value == "tool"]
    assert "Unknown tool" in tool_rows[0].content
    assert rows[-1].content == "Sorry, I could not do that."


# ---------------------------------------------------------------------------
# Provider wire format
# ---------------------------------------------------------------------------


class _FakeFunction:
    def __init__(self, name: str, arguments: str) -> None:
        self.name = name
        self.arguments = arguments


class _FakeToolCall:
    """Shaped like the OpenAI SDK's tool call, including its `model_extra` passthrough."""

    def __init__(self, extra: dict | None) -> None:
        self.id = "call_1"
        self.function = _FakeFunction("get_goal", '{"on_date": "2026-01-01"}')
        self.model_extra = {"extra_content": extra} if extra else {}


def test_provider_extra_survives_a_round_trip() -> None:
    """Gemini signs each tool call and rejects a replay that drops the signature.

    Losing this made every multi-step conversation fail with a 400 on the *second* request,
    while single-step ones kept working — so it is worth pinning down.
    """
    from app.ai.openai_compatible import _call_from_wire, _call_to_wire

    signature = {"google": {"thought_signature": "abc123"}}
    call = _call_from_wire(_FakeToolCall(signature))

    assert call.arguments == {"on_date": "2026-01-01"}
    assert call.provider_extra == signature
    assert _call_to_wire(call)["extra_content"] == signature


def test_a_call_without_provider_extra_stays_clean() -> None:
    """Providers that send no extra data must not receive an empty key back."""
    from app.ai.openai_compatible import _call_from_wire, _call_to_wire

    call = _call_from_wire(_FakeToolCall(None))
    assert call.provider_extra is None
    assert "extra_content" not in _call_to_wire(call)


def test_unparsable_arguments_do_not_break_the_turn() -> None:
    from app.ai.openai_compatible import _call_from_wire

    broken = _FakeToolCall(None)
    broken.function = _FakeFunction("get_goal", "{not json")
    # An empty dict lets the tool's own validation produce a message the model can act on.
    assert _call_from_wire(broken).arguments == {}
