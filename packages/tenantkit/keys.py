"""Shared API-key records + hashing helpers (control-plane + gateway)."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
from dataclasses import dataclass


@dataclass(frozen=True)
class KeyRecord:
    api_key: str
    tenant_id: str
    rpm_limit: int
    allowed_models: tuple[str, ...]


def hash_api_key(api_key: str) -> str:
    """SHA-256 hex digest for high-entropy API keys (lookup + at-rest storage)."""
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def generate_api_key(prefix: str = "sk-af") -> str:
    return f"{prefix}-{secrets.token_urlsafe(24)}"


def key_prefix(api_key: str, n: int = 12) -> str:
    return api_key[:n] if len(api_key) >= n else api_key


def default_dev_keys() -> list[KeyRecord]:
    return [
        KeyRecord("sk-af-tenant-a-devonly", "tenant_a", 60, ()),
        KeyRecord("sk-af-tenant-b-devonly", "tenant_b", 60, ()),
    ]


def load_keys_from_env() -> dict[str, KeyRecord]:
    raw = os.environ.get("AF_API_KEYS", "").strip()
    if not raw:
        records = default_dev_keys()
    else:
        data = json.loads(raw)
        if not isinstance(data, list) or not data:
            raise ValueError("AF_API_KEYS must be a non-empty JSON array")
        records = []
        for item in data:
            records.append(
                KeyRecord(
                    api_key=str(item["key"]),
                    tenant_id=str(item["tenant_id"]),
                    rpm_limit=int(item.get("rpm", 60)),
                    allowed_models=tuple(str(m) for m in (item.get("models") or [])),
                )
            )
    return {r.api_key: r for r in records}


def resolve_key(api_key: str, registry: dict[str, KeyRecord] | None = None) -> KeyRecord | None:
    reg = registry if registry is not None else load_keys_from_env()
    return reg.get(api_key)
