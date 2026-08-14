"""Gateway auth: Bearer API key → tenant record."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx
from fastapi import Header, HTTPException, Request

ROOT = Path(__file__).resolve().parents[1]
GW = Path(__file__).resolve().parent
for p in (ROOT, GW):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from packages.tenantkit.keys import KeyRecord, load_keys_from_env, resolve_key

_LOCAL_REGISTRY: dict[str, KeyRecord] | None = None


def _registry() -> dict[str, KeyRecord]:
    global _LOCAL_REGISTRY
    if _LOCAL_REGISTRY is None:
        _LOCAL_REGISTRY = load_keys_from_env()
    return _LOCAL_REGISTRY


def parse_bearer(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "message": "Missing Authorization header",
                    "type": "authentication_error",
                    "code": "invalid_api_key",
                }
            },
        )
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "message": "Authorization must be Bearer <api_key>",
                    "type": "authentication_error",
                    "code": "invalid_api_key",
                }
            },
        )
    return parts[1].strip()


async def resolve_tenant_from_authorization(authorization: str | None) -> KeyRecord:
    api_key = parse_bearer(authorization)
    cp = os.environ.get("CONTROL_PLANE_URL", "").rstrip("/")
    if cp:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(
                    f"{cp}/internal/v1/resolve-key",
                    json={"api_key": api_key},
                )
            if resp.status_code == 401:
                raise HTTPException(
                    status_code=401,
                    detail={
                        "error": {
                            "message": "Incorrect API key provided",
                            "type": "authentication_error",
                            "code": "invalid_api_key",
                        }
                    },
                )
            resp.raise_for_status()
            data = resp.json()
            return KeyRecord(
                api_key=api_key,
                tenant_id=data["tenant_id"],
                rpm_limit=int(data.get("rpm_limit", 60)),
                allowed_models=tuple(data.get("allowed_models") or []),
            )
        except HTTPException:
            raise
        except Exception:
            # Fall back to local env registry if control-plane unreachable (local smoke)
            pass

    rec = resolve_key(api_key, _registry())
    if rec is None:
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "message": "Incorrect API key provided",
                    "type": "authentication_error",
                    "code": "invalid_api_key",
                }
            },
        )
    return rec


async def require_tenant(
    request: Request,
    authorization: str | None = Header(default=None),
) -> KeyRecord:
    rec = await resolve_tenant_from_authorization(authorization)
    request.state.tenant_id = rec.tenant_id
    return rec
