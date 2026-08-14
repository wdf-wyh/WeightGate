"""Pydantic request/response schemas for control-plane APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

RouteMode = Literal["local_only", "cloud_only", "hybrid"]
InstanceStatus = Literal["created", "running", "stopped", "sleeping", "error"]
RouteLabel = Literal["local", "cloud", "vllm"]


class TenantCreate(BaseModel):
    id: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_\-]{0,63}$")
    name: str = Field(min_length=1, max_length=256)


class TenantUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=256)
    status: Literal["active", "disabled"] | None = None


class TenantOut(BaseModel):
    id: str
    name: str
    status: str
    created_at: datetime


class ApiKeyCreate(BaseModel):
    rpm_limit: int = Field(default=60, ge=1, le=100_000)
    allowed_models: list[str] = Field(default_factory=list)


class ApiKeyOut(BaseModel):
    id: str
    tenant_id: str
    key_prefix: str
    rpm_limit: int
    allowed_models: list[str]
    created_at: datetime
    revoked_at: datetime | None = None
    # Only set on issue/rotate responses
    api_key: str | None = None


class RoutePolicyOut(BaseModel):
    tenant_id: str
    mode: RouteMode
    short_max_chars: int
    updated_at: datetime


class RoutePolicyUpdate(BaseModel):
    mode: RouteMode
    short_max_chars: int | None = Field(default=None, ge=64, le=100_000)


class InstanceCreate(BaseModel):
    preset_id: str = Field(min_length=1, max_length=64)
    host_id: str | None = Field(default=None, min_length=1, max_length=64)


class InstanceOut(BaseModel):
    id: str
    tenant_id: str
    preset_id: str
    status: InstanceStatus
    backend: str
    compose_project: str | None = None
    host_id: str | None = None
    note: str | None = None
    created_at: datetime
    updated_at: datetime


class HostCreate(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    ssh_host: str = Field(min_length=1, max_length=256)
    ssh_port: int = Field(default=22, ge=1, le=65535)
    ssh_user: str = Field(default="ubuntu", min_length=1, max_length=128)
    identity_file: str | None = Field(default=None, max_length=512)
    tenant_id: str | None = Field(default=None, max_length=64)


class HostUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=256)
    ssh_port: int | None = Field(default=None, ge=1, le=65535)
    ssh_user: str | None = Field(default=None, min_length=1, max_length=128)
    identity_file: str | None = Field(default=None, max_length=512)
    tenant_id: str | None = Field(default=None, max_length=64)


class HostOut(BaseModel):
    id: str
    name: str
    ssh_host: str
    ssh_port: int
    ssh_user: str
    identity_file: str | None = None
    tenant_id: str | None = None
    status: str
    agent_version: str | None = None
    note: str | None = None
    last_seen_at: datetime | None = None
    created_at: datetime


class AlertOut(BaseModel):
    id: str
    fingerprint: str
    kind: str
    severity: str
    tenant_id: str | None = None
    resource_id: str | None = None
    message: str
    status: str
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None = None


class AlertScanResult(BaseModel):
    created: int
    open_total: int
    alerts: list[AlertOut]


class MirrorProductOut(BaseModel):
    id: str
    display_name: str
    domain: str
    price_cny: int
    example_path: str
    adapter_slug: str
    base_preset_hint: str | None = None
    description: str | None = None


class LicenseIssue(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=64)
    days_valid: int | None = Field(default=365, ge=1, le=3650)


class LicenseOut(BaseModel):
    id: str
    product_id: str
    tenant_id: str
    key_prefix: str
    status: str
    activated_at: datetime | None = None
    expires_at: datetime | None = None
    created_at: datetime
    # Only set on issue
    license_key: str | None = None


class LicenseActivate(BaseModel):
    license_key: str = Field(min_length=8, max_length=256)


class PresetOut(BaseModel):
    id: str
    display_name: str
    params_b: int
    backend: str
    quant: str
    min_vram_gb: int
    notes: str | None = None


class UsageEventIn(BaseModel):
    tenant_id: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int | None = None
    route: RouteLabel
    latency_ms: int = 0


class UsageEventOut(BaseModel):
    id: str
    tenant_id: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    route: str
    latency_ms: int
    created_at: datetime


class UsageSummary(BaseModel):
    tenant_id: str
    total_events: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    by_route: dict[str, int]
    events: list[UsageEventOut]


class ResolveKeyRequest(BaseModel):
    api_key: str = Field(min_length=1)


class ResolveKeyResponse(BaseModel):
    tenant_id: str
    rpm_limit: int
    allowed_models: list[str]
