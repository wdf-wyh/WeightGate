"""Cloud OpenAI-compatible adapters (Phase 3 multi-provider).

Providers (AF_CLOUD_PROVIDER):
  - openai     — generic OpenAI-compatible (default)
  - dashscope  — 阿里云百炼 compatible-mode (alias: bailian)
  - deepseek   — DeepSeek OpenAI-compatible API

Env:
  AF_CLOUD_PROVIDER / AF_CLOUD_BASE_URL / AF_CLOUD_API_KEY / AF_CLOUD_MODEL
  AF_CLOUD_NIGHT_START / AF_CLOUD_NIGHT_END / AF_CLOUD_NIGHT_DISCOUNT
    (docs + cost_estimate only; not a live billing API)

Failures should be caught by gateway and degraded to local when AF_ROUTE_DEGRADE=1.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

import httpx

# Provider → default OpenAI-compatible base (no trailing /v1).
# Chat path is always {base}/v1/chat/completions.
PROVIDER_DEFAULTS: dict[str, str] = {
    "openai": "https://api.openai.com",
    "dashscope": "https://dashscope.aliyuncs.com/compatible-mode",
    "bailian": "https://dashscope.aliyuncs.com/compatible-mode",
    "deepseek": "https://api.deepseek.com",
}

# Common default model remaps when AF_CLOUD_MODEL is unset
PROVIDER_DEFAULT_MODELS: dict[str, str] = {
    "dashscope": "qwen-plus",
    "bailian": "qwen-plus",
    "deepseek": "deepseek-chat",
}


@dataclass(frozen=True)
class CloudProviderInfo:
    name: str
    base_url: str
    model_remap: str | None


def normalize_provider(raw: str | None) -> str:
    name = (raw or os.environ.get("AF_CLOUD_PROVIDER", "openai") or "openai").strip().lower()
    if name in ("aliyun", "alibaba", "通义", "百炼"):
        return "dashscope"
    if name == "bailian":
        return "bailian"
    if name not in PROVIDER_DEFAULTS:
        return "openai"
    return name


def cloud_provider() -> str:
    return normalize_provider(None)


def cloud_base_url() -> str:
    override = os.environ.get("AF_CLOUD_BASE_URL", "").strip()
    if override:
        return override.rstrip("/")
    return PROVIDER_DEFAULTS[cloud_provider()].rstrip("/")


def cloud_api_key() -> str:
    return os.environ.get("AF_CLOUD_API_KEY", "").strip()


def cloud_model_remap() -> str | None:
    explicit = os.environ.get("AF_CLOUD_MODEL", "").strip()
    if explicit:
        return explicit
    return PROVIDER_DEFAULT_MODELS.get(cloud_provider())


def cloud_configured() -> bool:
    return bool(cloud_api_key())


def provider_info() -> CloudProviderInfo:
    return CloudProviderInfo(
        name=cloud_provider(),
        base_url=cloud_base_url(),
        model_remap=cloud_model_remap(),
    )


def night_window_config() -> dict[str, Any]:
    """Configurable night discount window (documentation / estimators only)."""
    start = os.environ.get("AF_CLOUD_NIGHT_START", "22:00").strip() or "22:00"
    end = os.environ.get("AF_CLOUD_NIGHT_END", "08:00").strip() or "08:00"
    try:
        discount = float(os.environ.get("AF_CLOUD_NIGHT_DISCOUNT", "0.5"))
    except ValueError:
        discount = 0.5
    tz_name = os.environ.get("AF_CLOUD_NIGHT_TZ", "Asia/Shanghai").strip() or "Asia/Shanghai"
    return {
        "start": start,
        "end": end,
        "discount": discount,
        "timezone": tz_name,
        "note": "Informational only — providers bill via their own consoles; AF does not call billing APIs.",
    }


def _parse_hhmm(value: str) -> tuple[int, int]:
    parts = value.split(":")
    h = int(parts[0])
    m = int(parts[1]) if len(parts) > 1 else 0
    return h, m


def is_night_window(now: datetime | None = None) -> bool:
    """True if `now` falls in the configured night discount window (may wrap midnight)."""
    cfg = night_window_config()
    try:
        tz: Any = ZoneInfo(cfg["timezone"])
    except Exception:
        tz = timezone.utc
    if now is None:
        try:
            now = datetime.now(tz)
        except Exception:
            now = datetime.now(timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=tz)
    else:
        try:
            now = now.astimezone(tz)
        except Exception:
            now = now.astimezone(timezone.utc)

    sh, sm = _parse_hhmm(cfg["start"])
    eh, em = _parse_hhmm(cfg["end"])
    minutes = now.hour * 60 + now.minute
    start_m = sh * 60 + sm
    end_m = eh * 60 + em
    if start_m == end_m:
        return False
    if start_m < end_m:
        return start_m <= minutes < end_m
    # wraps midnight, e.g. 22:00 → 08:00
    return minutes >= start_m or minutes < end_m


async def forward_chat_completions(payload: dict[str, Any]) -> httpx.Response:
    key = cloud_api_key()
    if not key:
        raise RuntimeError("AF_CLOUD_API_KEY not configured")
    url = f"{cloud_base_url()}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    body = dict(payload)
    remap = cloud_model_remap()
    if remap:
        body["model"] = remap
    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
        return await client.post(url, json=body, headers=headers)


async def cloud_health() -> bool:
    if not cloud_configured():
        return False
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(
                f"{cloud_base_url()}/v1/models",
                headers={"Authorization": f"Bearer {cloud_api_key()}"},
            )
            return resp.status_code < 500
    except Exception:
        return False
