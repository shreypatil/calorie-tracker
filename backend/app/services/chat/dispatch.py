"""Resolving a tool name and validating a model's arguments before anything runs.

Everything the model produces passes through here, and nothing else in the chat layer trusts
it. A name that is not in the registry never becomes a call, and arguments that do not fit the
tool's Pydantic model never reach a service.

Validation failures become the application's own `ValidationError`, so a bad confirm request
renders as the same `problem+json` body every other endpoint produces, and a bad *model* guess
can be handed back to the model as a readable tool result for it to correct.
"""

from typing import Any

from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from app.core.errors import ValidationError
from app.services.chat.tools import TOOLS, Tool


def resolve(name: str) -> Tool:
    """Look up a tool by name, or fail with the list of names that do exist."""
    tool = TOOLS.get(name)
    if tool is None:
        raise ValidationError(
            f"Unknown tool: {name}.",
            errors=[
                {
                    "field": "tool",
                    "message": f"allowed values are {', '.join(sorted(TOOLS))}",
                    "type": "value_error",
                }
            ],
        )
    return tool


def validate_args(tool: Tool, arguments: dict[str, Any]) -> BaseModel:
    """Parse raw arguments into the tool's argument model."""
    try:
        return tool.args_model.model_validate(arguments or {})
    except PydanticValidationError as exc:
        raise ValidationError(
            f"Invalid arguments for {tool.name}.",
            errors=[
                {
                    "field": ".".join(str(part) for part in error["loc"]),
                    "message": error["msg"],
                    "type": error["type"],
                }
                for error in exc.errors()
            ],
        ) from exc


def summarize(tool: Tool, args: BaseModel) -> str:
    """The one-line description shown on a draft card."""
    return tool.summarize(args) if tool.summarize else f"Run {tool.name}"
