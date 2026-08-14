"""Forward OpenAI-compatible calls to Ollama."""

from __future__ import annotations

import os
from typing import Any

import httpx

DEFAULT_OLLAMA = "http://127.0.0.1:11434"


def ollama_base_url() -> str:
    return os.environ.get("OLLAMA_BASE_URL", DEFAULT_OLLAMA).rstrip("/")


async def forward_chat_completions(payload: dict[str, Any]) -> httpx.Response:
    url = f"{ollama_base_url()}/v1/chat/completions"
    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
        return await client.post(url, json=payload)


async def forward_models() -> httpx.Response:
    url = f"{ollama_base_url()}/v1/models"
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
        return await client.get(url)


async def ollama_health() -> bool:
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{ollama_base_url()}/api/tags")
            return resp.status_code == 200
    except Exception:
        return False
