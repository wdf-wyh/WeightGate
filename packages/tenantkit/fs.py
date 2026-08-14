"""Tenant filesystem helpers (isolation contract)."""

from __future__ import annotations

import os
import re
from pathlib import Path

_TENANT_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_\-]{0,63}$")

TENANT_SUBDIRS = ("models", "loras", "cache", "logs", "vector")


class TenantIsolationError(PermissionError):
    """Raised when a path escapes the authenticated tenant root."""


def data_root() -> Path:
    return Path(os.environ.get("AF_DATA_ROOT", "./data/tenants")).resolve()


def validate_tenant_id(tenant_id: str) -> str:
    if not _TENANT_ID_RE.fullmatch(tenant_id):
        raise TenantIsolationError(f"invalid tenant_id: {tenant_id!r}")
    return tenant_id


def tenant_root(tenant_id: str) -> Path:
    tid = validate_tenant_id(tenant_id)
    root = (data_root() / tid).resolve()
    base = data_root()
    try:
        root.relative_to(base)
    except ValueError as exc:
        raise TenantIsolationError("tenant root escapes AF_DATA_ROOT") from exc
    return root


def ensure_tenant_layout(tenant_id: str) -> Path:
    root = tenant_root(tenant_id)
    for name in TENANT_SUBDIRS:
        (root / name).mkdir(parents=True, exist_ok=True)
    return root


def safe_tenant_path(tenant_id: str, *parts: str) -> Path:
    """Join under tenant root; reject '..' and absolute escapes."""
    root = tenant_root(tenant_id)
    cleaned: list[str] = []
    for part in parts:
        if Path(part).is_absolute():
            raise TenantIsolationError("absolute path forbidden")
        for seg in Path(part).parts:
            if seg in ("", "."):
                continue
            if seg == "..":
                raise TenantIsolationError("path traversal forbidden")
            cleaned.append(seg)
    candidate = root.joinpath(*cleaned).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise TenantIsolationError("path escapes tenant root") from exc
    return candidate


def assert_model_allowed_for_tenant(tenant_id: str, model: str) -> None:
    """
    Reject cross-tenant model / adapter references.
    Request body `model` is never treated as tenant identity; only as a resource name.
    """
    tid = validate_tenant_id(tenant_id)
    raw = model.strip()
    if not raw:
        raise TenantIsolationError("empty model")

    lowered = raw.replace("\\", "/").lower()

    # Deny explicit tenants/<other>/… references even if that dir is not on disk yet
    for m in re.finditer(r"(?:^|/)tenants/([a-zA-Z0-9][a-zA-Z0-9_\-]{0,63})(?=/|$)", lowered):
        other = m.group(1)
        if other != tid.lower() and not other.startswith("_"):
            raise TenantIsolationError(f"cross-tenant model reference denied: {model!r}")

    base = data_root()
    if base.is_dir():
        for other in base.iterdir():
            if not other.is_dir():
                continue
            other_id = other.name
            if other_id == tid or other_id.startswith("_"):
                continue
            markers = (
                f"tenants/{other_id.lower()}/",
                f"tenants/{other_id.lower()}",
                f"/{other_id.lower()}/loras/",
                f"/{other_id.lower()}/models/",
                f"/{other_id.lower()}/vector/",
            )
            for marker in markers:
                if marker in lowered:
                    raise TenantIsolationError(f"cross-tenant model reference denied: {model!r}")

    if "/" in raw or "\\" in raw or raw.startswith("."):
        rel = raw.replace("\\", "/")
        for prefix in (f"tenants/{tid}/", f"{tid}/", "./"):
            if rel.startswith(prefix):
                rel = rel[len(prefix) :]
                break
        parts = [p for p in rel.split("/") if p and p != "."]
        if any(p == ".." for p in parts):
            raise TenantIsolationError("path traversal forbidden")
        # If the relative path still nests another tenants/ segment, deny
        if len(parts) >= 2 and parts[0] == "tenants" and parts[1] != tid:
            raise TenantIsolationError(f"cross-tenant model reference denied: {model!r}")
        safe_tenant_path(tid, *parts)
