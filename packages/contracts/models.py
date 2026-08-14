"""GET /v1/models list (tenant-scoped in Phase 1+)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ModelObject(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    object: Literal["model"] = "model"
    created: int
    owned_by: str = "automatic-funicular"


class ModelListResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    object: Literal["list"] = "list"
    data: list[ModelObject] = Field(default_factory=list)
