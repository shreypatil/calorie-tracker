"""Chat schemas — the conversation types, the tool-calling contract, and the API bodies.

Two vocabularies meet in this file.

*Provider-facing*: `ProviderMessage`, `ToolSpec`, `ToolCall` and `AssistantTurn` are the shapes
an `AIProvider` consumes and returns. They are deliberately provider-neutral — nothing here
mentions OpenAI's wire format, so a second adapter would not need new types.

*User-facing*: `ChatMessageResponse` and `PendingAction` are what the web app renders.

`PendingAction` is the centre of the design. A tool that writes is never executed inside the
agent loop; it is recorded as a pending action and shown to the user as a draft. Only an
explicit confirm dispatches it. The action therefore has a lifecycle, and that lifecycle is
persisted on the assistant message that proposed it.
"""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.db.models import ChatRole

# ---------------------------------------------------------------------------
# Provider-facing
# ---------------------------------------------------------------------------


class ToolCall(BaseModel):
    """A model's request to run one tool.

    `arguments` is whatever the model produced and is **not** trusted: it is validated
    against the tool's own Pydantic argument model at dispatch time, not here.
    """

    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    #: Opaque per-provider data attached to this call that must be handed back verbatim when
    #: the call is replayed. Gemini's thinking models put a `thought_signature` here and
    #: reject the follow-up request if it is missing. Never inspected — only round-tripped.
    provider_extra: dict[str, Any] | None = None


class AssistantTurn(BaseModel):
    """One reply from the model: prose, tool calls, or both."""

    content: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)


class ProviderMessage(BaseModel):
    """One message in the conversation as the provider sees it."""

    role: Literal["system", "user", "assistant", "tool"]
    content: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    tool_call_id: str | None = None
    name: str | None = None


class ToolSpec(BaseModel):
    """A tool as advertised to the model. `parameters` is a JSON Schema object."""

    name: str
    description: str
    parameters: dict[str, Any]


# ---------------------------------------------------------------------------
# User-facing
# ---------------------------------------------------------------------------


class ActionStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    DISCARDED = "discarded"


class PendingAction(BaseModel):
    """A write the model proposed, awaiting the user's decision.

    Stored as JSON on the proposing assistant message rather than in a table of its own —
    the same reasoning that kept imports free of a job/status table. The status field is
    what makes confirming twice impossible.
    """

    id: str
    tool: str
    summary: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    status: ActionStatus = ActionStatus.PENDING
    result: dict[str, Any] | None = None


class ChatMessageResponse(BaseModel):
    id: uuid.UUID
    role: ChatRole
    content: str
    #: Populated only on assistant messages that proposed a write.
    actions: list[PendingAction] = Field(default_factory=list)
    #: Populated only on `tool` rows — the read tool whose result this is.
    tool_name: str | None = None
    created_at: datetime


class ChatSendRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class ActionDecisionRequest(BaseModel):
    """Confirming a draft, optionally with corrections.

    The user can fix a number before committing — the same affordance the import review
    table gives PDF rows. Edited arguments go through the tool's argument model exactly as
    the model's own would.
    """

    arguments: dict[str, Any] | None = Field(
        default=None, description="Corrected arguments. Omit to confirm exactly as proposed."
    )


class ChatTurnResponse(BaseModel):
    """Everything the turn appended to the transcript, oldest first."""

    messages: list[ChatMessageResponse]
