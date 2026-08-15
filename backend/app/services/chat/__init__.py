"""Conversational control of the app (FR-6).

The model asks; this package decides. A request names a tool in `tools.TOOLS` and carries
arguments; `dispatch` validates them, `agent` supplies the user's identity and runs the
handler, and a handler that writes is held as a draft until the user confirms it.
"""

from app.services.chat.agent import (
    clear_messages,
    confirm_action,
    discard_action,
    list_messages,
    send_message,
    to_response,
)
from app.services.chat.schema import tool_specs
from app.services.chat.tools import TOOLS

__all__ = [
    "TOOLS",
    "clear_messages",
    "confirm_action",
    "discard_action",
    "list_messages",
    "send_message",
    "to_response",
    "tool_specs",
]
