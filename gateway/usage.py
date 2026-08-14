"""Post usage events to control-plane (best-effort)."""

from __future__ import annotations

import os
from typing import Any

import httpx


async def record_usage(
    *,
    tenant_id: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    route: str,
    latency_ms: int,
) -> None:
    cp = os.environ.get("CONTROL_PLANE_URL", "").rstrip("/")
    if not cp:
        return
    headers: dict[str, str] = {}
    token = os.environ.get("AF_INTERNAL_TOKEN", "").strip()
    if token:
        headers["X-AF-Internal"] = token
    body: dict[str, Any] = {
        "tenant_id": tenant_id,
        "model": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "route": route,
        "latency_ms": latency_ms,
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(f"{cp}/internal/v1/usage", json=body, headers=headers)
    except Exception:
        pass


def extract_usage_tokens(data: dict[str, Any]) -> tuple[int, int]:
    usage = data.get("usage") or {}
    return int(usage.get("prompt_tokens") or 0), int(usage.get("completion_tokens") or 0)
