"""Request models for the OpenAI-compatible chat completions endpoint.

Validation here is intentionally permissive on unknown/extra fields (we are a
pass-through to LM Studio and must not reject fields we don't know about),
but strict on the shape that we actually depend on (a non-empty message
list with a role per message).
"""
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, field_validator


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="allow")

    role: str
    content: Optional[Any] = None


class ChatCompletionRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    model: Optional[str] = None
    messages: List[ChatMessage]

    @field_validator("messages")
    @classmethod
    def messages_not_empty(cls, value: List[ChatMessage]) -> List[ChatMessage]:
        if not value:
            raise ValueError("messages must contain at least one message")
        return value
