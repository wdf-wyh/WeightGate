"""OpenAI-compatible error envelope (Phase 0)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class ErrorBody(BaseModel):
    model_config = ConfigDict(extra="allow")

    message: str
    type: str
    param: str | None = None
    code: str | None = None


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    error: ErrorBody
