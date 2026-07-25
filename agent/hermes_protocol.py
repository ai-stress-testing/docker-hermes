"""Parsing/formatting for the Hermes `<tool_call>` / `<tool_response>` wire
format.

Model replies may contain zero or more `<tool_call>...</tool_call>` blocks,
each expected to hold a JSON object `{"name": ..., "arguments": {...}}`.
Malformed blocks (bad JSON, missing `name`, non-object `arguments`, etc.)
are never allowed to raise — they're surfaced as `ToolCallRequest.error` so
the caller can feed a `<tool_response>` error back to the model and keep the
loop going instead of crashing the harness.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

_TOOL_CALL_RE = re.compile(r"<tool_call>(.*?)</tool_call>", re.DOTALL)


@dataclass
class ToolCallRequest:
    """One parsed `<tool_call>` block. `error` is set (and `name`/`arguments`
    may be partial or None) when the block could not be turned into a valid
    tool invocation.
    """

    name: str | None
    arguments: dict[str, Any] | None
    raw: str
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


def has_tool_calls(reply_text: str) -> bool:
    """True if the reply contains at least one <tool_call> block."""
    return _TOOL_CALL_RE.search(reply_text) is not None


def parse_tool_calls(reply_text: str) -> list[ToolCallRequest]:
    """Extract every <tool_call> block from a model reply, tolerating
    malformed JSON or missing fields without raising.
    """
    requests: list[ToolCallRequest] = []
    for match in _TOOL_CALL_RE.finditer(reply_text):
        raw = match.group(1).strip()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            requests.append(
                ToolCallRequest(name=None, arguments=None, raw=raw, error=f"invalid JSON in tool_call: {exc}")
            )
            continue

        if not isinstance(payload, dict):
            requests.append(
                ToolCallRequest(name=None, arguments=None, raw=raw, error="tool_call JSON must be an object")
            )
            continue

        name = payload.get("name")
        if not isinstance(name, str) or not name:
            requests.append(
                ToolCallRequest(name=None, arguments=None, raw=raw, error="tool_call is missing a valid 'name'")
            )
            continue

        arguments = payload.get("arguments", {})
        if not isinstance(arguments, dict):
            requests.append(
                ToolCallRequest(
                    name=name, arguments=None, raw=raw, error="tool_call 'arguments' must be a JSON object"
                )
            )
            continue

        requests.append(ToolCallRequest(name=name, arguments=arguments, raw=raw, error=None))

    return requests


def format_tool_response(name: str, content: Any) -> str:
    """Wrap a successful tool result for the reply-back message to the model."""
    payload = {"name": name, "content": content}
    return f"<tool_response>{json.dumps(payload)}</tool_response>"


def format_tool_error_response(name: str | None, error: str) -> str:
    """Wrap a tool-execution error for the reply-back message to the model,
    so it can see what went wrong and self-correct.
    """
    payload = {"name": name if name is not None else "unknown", "error": error}
    return f"<tool_response>{json.dumps(payload)}</tool_response>"
