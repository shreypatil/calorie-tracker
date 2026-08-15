"""Turning tool argument models into JSON Schema the providers actually accept.

Pydantic's `model_json_schema()` is correct but not portable. It factors nested models and
enums out into `$defs` and refers to them with `$ref`, and it expresses an optional field as
`anyOf: [T, null]`. Several OpenAI-compatible endpoints — Gemini's among them — reject both,
so a schema that works against OpenAI fails against the project's default provider.

Rather than hand-write JSON Schema for ten tools and let it drift from the models that
validate the arguments, the schema is still generated and then normalized here: references are
inlined, nullable unions are collapsed to their real type, and annotations no provider needs
are dropped. One generated source of truth, cleaned once, for every provider.
"""

from typing import Any

from pydantic import BaseModel

from app.schemas.chat import ToolSpec
from app.services.chat.tools import TOOLS

#: Guards against a self-referential model turning inlining into infinite recursion. Nothing
#: in the registry is recursive today; this keeps that from becoming a hang if one ever is.
_MAX_DEPTH = 12

#: Carry no meaning for a tool call, and some endpoints reject them outright.
_STRIP_KEYS = ("title", "default", "$schema", "additionalProperties", "discriminator")


def _inline_refs(node: Any, defs: dict[str, Any], depth: int = 0) -> Any:
    """Replace every `$ref` with the definition it points at."""
    if depth > _MAX_DEPTH:
        return {}
    if isinstance(node, list):
        return [_inline_refs(item, defs, depth + 1) for item in node]
    if not isinstance(node, dict):
        return node

    ref = node.get("$ref")
    if isinstance(ref, str) and ref.startswith("#/$defs/"):
        target = defs.get(ref.removeprefix("#/$defs/"), {})
        # Sibling keys (a description on the field) outrank the definition's own.
        merged = {**target, **{k: v for k, v in node.items() if k != "$ref"}}
        return _inline_refs(merged, defs, depth + 1)

    return {key: _inline_refs(value, defs, depth + 1) for key, value in node.items()}


def _collapse_nullable(node: dict[str, Any]) -> dict[str, Any]:
    """Turn `anyOf: [T, null]` into plain `T`.

    An optional argument is already expressed by leaving it out of `required`, so the null
    variant carries no information the provider needs — and costs compatibility.
    """
    variants = node.get("anyOf")
    if not isinstance(variants, list):
        return node

    real = [v for v in variants if isinstance(v, dict) and v.get("type") != "null"]
    if len(real) != 1:
        return node

    rest = {k: v for k, v in node.items() if k != "anyOf"}
    return {**real[0], **rest}


def _clean(node: Any) -> Any:
    if isinstance(node, list):
        return [_clean(item) for item in node]
    if not isinstance(node, dict):
        return node

    node = _collapse_nullable(node)
    return {key: _clean(value) for key, value in node.items() if key not in _STRIP_KEYS}


def json_schema_for(model: type[BaseModel]) -> dict[str, Any]:
    """A flat, reference-free JSON Schema for a tool's arguments."""
    raw = model.model_json_schema()
    defs = raw.pop("$defs", {})
    return _clean(_inline_refs(raw, defs))


def tool_specs() -> list[ToolSpec]:
    """Every registered tool, as advertised to the model."""
    return [
        ToolSpec(
            name=tool.name,
            description=tool.description,
            parameters=json_schema_for(tool.args_model),
        )
        for tool in TOOLS.values()
    ]
