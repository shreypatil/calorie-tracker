"""Chat endpoints (FR-6).

Thin, like every router here: parse, authorize, delegate. All of the conversation logic —
the tool registry, the agent loop, the confirmation gate — lives in `services/chat/`.

`POST /chat/messages` never changes the user's data. When the model wants to write, the
response carries a pending action and the caller must confirm it explicitly.
"""

from fastapi import APIRouter, Request, status
from starlette.concurrency import run_in_threadpool

from app.ai import get_provider
from app.core.deps import CurrentUser, DbSession
from app.core.pagination import Page, PageParamsDep, build_page
from app.schemas.chat import (
    ActionDecisionRequest,
    ChatMessageResponse,
    ChatSendRequest,
    ChatTurnResponse,
)
from app.services import chat as chat_service
from app.services.rate_limit import limiter

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/messages", response_model=Page[ChatMessageResponse])
def list_messages(
    current_user: CurrentUser, session: DbSession, params: PageParamsDep
) -> Page[ChatMessageResponse]:
    """The conversation, newest first."""
    messages, total = chat_service.list_messages(session, current_user.id, params)
    items = [chat_service.to_response(message) for message in messages]
    return Page[ChatMessageResponse](**build_page(items, total, params))


@router.post("/messages", response_model=ChatTurnResponse)
@limiter.limit("20/minute")
async def send_message(
    request: Request,
    payload: ChatSendRequest,
    current_user: CurrentUser,
    session: DbSession,
) -> ChatTurnResponse:
    """Send a message and get the turn back. **Writes nothing to the user's data.**

    Anything the model wants to change comes back as a pending action on the assistant
    message; confirm it to apply it.
    """
    # Off the event loop: the provider call is blocking network I/O, several seconds of it,
    # during which this coroutine would otherwise stall every other request in the process.
    messages = await run_in_threadpool(
        chat_service.send_message,
        session,
        current_user.id,
        payload.message,
        get_provider(),
    )
    return ChatTurnResponse(messages=[chat_service.to_response(m) for m in messages])


@router.post("/actions/{action_id}/confirm", response_model=ChatMessageResponse)
def confirm_action(
    action_id: str,
    payload: ActionDecisionRequest,
    current_user: CurrentUser,
    session: DbSession,
) -> ChatMessageResponse:
    """Apply a proposed change, optionally with corrected values."""
    message = chat_service.confirm_action(session, current_user.id, action_id, payload.arguments)
    return chat_service.to_response(message)


@router.post("/actions/{action_id}/discard", response_model=ChatMessageResponse)
def discard_action(
    action_id: str, current_user: CurrentUser, session: DbSession
) -> ChatMessageResponse:
    """Drop a proposed change without applying it."""
    message = chat_service.discard_action(session, current_user.id, action_id)
    return chat_service.to_response(message)


@router.delete("/messages", status_code=status.HTTP_204_NO_CONTENT)
def clear_conversation(current_user: CurrentUser, session: DbSession) -> None:
    """Erase the conversation. Any un-confirmed drafts are dropped unexecuted."""
    chat_service.clear_messages(session, current_user.id)
