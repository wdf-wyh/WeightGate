"""Shared OpenAI-compatible contracts (Phase 0). Used by gateway in Phase 1+."""

from .chat import (
    AssistantMessage,
    ChatCompletionChoice,
    ChatCompletionChunk,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    ChatMessageRole,
    CompletionUsage,
)
from .errors import ErrorBody, ErrorResponse
from .models import ModelListResponse, ModelObject

__all__ = [
    "AssistantMessage",
    "ChatCompletionChoice",
    "ChatCompletionChunk",
    "ChatCompletionRequest",
    "ChatCompletionResponse",
    "ChatMessage",
    "ChatMessageRole",
    "CompletionUsage",
    "ErrorBody",
    "ErrorResponse",
    "ModelListResponse",
    "ModelObject",
]
