"""Pydantic mirrors of schemas/openai/chat-completions.*.json (Phase 0 contract)."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ChatMessageRole(str, Enum):
    system = "system"
    user = "user"
    assistant = "assistant"
    tool = "tool"


FinishReason = Literal["stop", "length", "tool_calls", "content_filter"]


class ChatMessage(BaseModel):
    """Request/history message (OpenAI-compatible)."""

    model_config = ConfigDict(extra="allow")

    role: ChatMessageRole
    content: str | list[dict[str, Any]] | None = None
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[dict[str, Any]] | None = None


class AssistantMessage(BaseModel):
    """Response choice message — role must be assistant."""

    model_config = ConfigDict(extra="allow")

    role: Literal["assistant"] = "assistant"
    content: str | None = None
    tool_calls: list[dict[str, Any]] | None = None


class ChatCompletionRequest(BaseModel):
    """POST /v1/chat/completions body."""

    model_config = ConfigDict(extra="allow")

    model: str
    messages: list[ChatMessage] = Field(min_length=1)
    temperature: float | None = Field(default=None, ge=0, le=2)
    top_p: float | None = Field(default=None, ge=0, le=1)
    n: int | None = Field(default=1, ge=1, le=8)
    stream: bool | None = False
    stop: str | list[str] | None = None
    max_tokens: int | None = Field(default=None, ge=1)
    presence_penalty: float | None = Field(default=None, ge=-2, le=2)
    frequency_penalty: float | None = Field(default=None, ge=-2, le=2)
    user: str | None = None
    tools: list[dict[str, Any]] | None = None
    tool_choice: str | dict[str, Any] | None = None
    response_format: dict[str, Any] | None = None
    seed: int | None = None


class ChatCompletionChoice(BaseModel):
    model_config = ConfigDict(extra="allow")

    index: int = Field(ge=0)
    message: AssistantMessage
    finish_reason: FinishReason | None = None
    logprobs: dict[str, Any] | None = None


class CompletionUsage(BaseModel):
    model_config = ConfigDict(extra="allow")

    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)


class ChatCompletionResponse(BaseModel):
    """Non-streaming chat.completion response."""

    model_config = ConfigDict(extra="allow")

    id: str
    object: Literal["chat.completion"] = "chat.completion"
    created: int
    model: str
    choices: list[ChatCompletionChoice] = Field(min_length=1)
    usage: CompletionUsage | None = None
    system_fingerprint: str | None = None


class ChatCompletionChunkChoice(BaseModel):
    model_config = ConfigDict(extra="allow")

    index: int = Field(ge=0)
    delta: dict[str, Any] = Field(default_factory=dict)
    finish_reason: FinishReason | None = None


class ChatCompletionChunk(BaseModel):
    """Streaming chat.completion.chunk payload (one SSE data object)."""

    model_config = ConfigDict(extra="allow")

    id: str
    object: Literal["chat.completion.chunk"] = "chat.completion.chunk"
    created: int
    model: str
    choices: list[ChatCompletionChunkChoice] = Field(min_length=1)
