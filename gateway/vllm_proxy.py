"""Forward OpenAI-compatible calls to vLLM (OpenAI API server)."""

from __future__ import annotations

import os
from typing import Any

import httpx

DEFAULT_VLLM = "http://127.0.0.1:8001"


def vllm_base_url() -> str:
    return os.environ.get("VLLM_BASE_URL", DEFAULT_VLLM).rstrip("/")


async def forward_chat_completions(payload: dict[str, Any]) -> httpx.Response:
    url = f"{vllm_base_url()}/v1/chat/completions"
    headers: dict[str, str] = {}
    key = os.environ.get("VLLM_API_KEY", "").strip()
    if key:
        headers["Authorization"] = f"Bearer {key}"
    async with httpx.AsyncClient(timeout=httpx.Timeout(180.0, connect=10.0)) as client:
        return await client.post(url, json=payload, headers=headers)


async def forward_models() -> httpx.Response:
    url = f"{vllm_base_url()}/v1/models"
    headers: dict[str, str] = {}
    key = os.environ.get("VLLM_API_KEY", "").strip()
    if key:
        headers["Authorization"] = f"Bearer {key}"
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
        return await client.get(url, headers=headers)


async def vllm_health() -> bool:
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{vllm_base_url()}/v1/models")
            return resp.status_code < 500
    except Exception:
        return False
