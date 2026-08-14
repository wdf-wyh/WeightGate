"""Load preset backend hints from model-presets.yaml (gateway-side)."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _presets_path() -> Path:
    override = os.environ.get("AF_PRESETS_PATH", "").strip()
    if override:
        return Path(override)
    return ROOT / "templates" / "model-presets.yaml"


@lru_cache(maxsize=1)
def _load() -> dict[str, Any]:
    path = _presets_path()
    if not path.is_file():
        return {"presets": []}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {"presets": []}


def backend_for_model(model: str) -> str | None:
    """Match model id / preset id / substring against presets."""
    presets = _load().get("presets") or []
    for p in presets:
        pid = str(p.get("id") or "")
        if model == pid or model.endswith(pid) or pid in model:
            return str(p.get("backend") or "ollama")
    # Heuristic: names containing vllm
    if "vllm" in model.lower():
        return "vllm"
    return None
