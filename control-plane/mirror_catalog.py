"""Load vertical mirror catalog from templates/mirror-catalog.yaml."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "templates" / "mirror-catalog.yaml"


@lru_cache(maxsize=1)
def load_catalog() -> dict[str, Any]:
    data = yaml.safe_load(CATALOG_PATH.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("mirror-catalog.yaml must be a mapping")
    products = data.get("products") or []
    if not isinstance(products, list):
        raise ValueError("products must be a list")
    return data


def list_products() -> list[dict[str, Any]]:
    return list(load_catalog().get("products") or [])


def get_product(product_id: str) -> dict[str, Any] | None:
    for p in list_products():
        if str(p.get("id")) == product_id:
            return p
    return None


def clear_catalog_cache() -> None:
    load_catalog.cache_clear()
