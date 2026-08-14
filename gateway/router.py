"""Hybrid routing rules (Phase 2) — non-ML heuristic."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

RouteLabel = Literal["local", "cloud", "vllm"]
PolicyMode = Literal["local_only", "cloud_only", "hybrid"]


@dataclass(frozen=True)
class RouteDecision:
    route: RouteLabel
    reason: str


def estimate_input_chars(payload: dict[str, Any]) -> int:
    total = 0
    for msg in payload.get("messages") or []:
        content = msg.get("content")
        if isinstance(content, str):
            total += len(content)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    total += len(str(part.get("text") or ""))
                else:
                    total += 64
        # tool / function noise
        if msg.get("tool_calls"):
            total += 256
    return total


def has_tools_signal(payload: dict[str, Any]) -> bool:
    if payload.get("tools") or payload.get("functions") or payload.get("tool_choice"):
        return True
    for msg in payload.get("messages") or []:
        if msg.get("tool_calls") or msg.get("role") == "tool":
            return True
    return False


def choose_route(
    *,
    policy_mode: PolicyMode,
    short_max_chars: int,
    payload: dict[str, Any],
    preset_backend: str | None,
) -> RouteDecision:
    """
    Rules:
    - local_only → local (Ollama)
    - cloud_only → cloud
    - hybrid: short + no tools → local; long / tools → cloud or vllm (by preset)
    """
    backend = (preset_backend or "ollama").lower()

    if policy_mode == "local_only":
        return RouteDecision("local", "policy_local_only")

    if policy_mode == "cloud_only":
        return RouteDecision("cloud", "policy_cloud_only")

    # hybrid
    chars = estimate_input_chars(payload)
    tools = has_tools_signal(payload)
    if tools:
        if backend == "vllm":
            return RouteDecision("vllm", "hybrid_tools_vllm_preset")
        return RouteDecision("cloud", "hybrid_tools")
    if chars > short_max_chars:
        if backend == "vllm":
            return RouteDecision("vllm", "hybrid_long_context_vllm")
        return RouteDecision("cloud", "hybrid_long_context")

    # short, no tools
    if backend == "vllm":
        # Still prefer local for short unless forced by env AF_HYBRID_SHORT_TO_PRESET=1
        import os

        if os.environ.get("AF_HYBRID_SHORT_TO_PRESET", "").strip() == "1":
            return RouteDecision("vllm", "hybrid_short_preset_vllm")
    return RouteDecision("local", "hybrid_short_local")
