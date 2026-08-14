"""Load model presets from templates/model-presets.yaml."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]


def presets_path() -> Path:
    override = os.environ.get("AF_PRESETS_PATH", "").strip()
    if override:
        return Path(override)
    return ROOT / "templates" / "model-presets.yaml"


@lru_cache(maxsize=1)
def load_presets() -> dict[str, Any]:
    path = presets_path()
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not data.get("presets"):
        raise RuntimeError(f"invalid presets file: {path}")
    return data


def list_presets() -> list[dict[str, Any]]:
    return list(load_presets()["presets"])


def get_preset(preset_id: str) -> dict[str, Any] | None:
    for p in list_presets():
        if p.get("id") == preset_id:
            return p
    return None


def clear_presets_cache() -> None:
    load_presets.cache_clear()
