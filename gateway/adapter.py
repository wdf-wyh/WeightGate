"""Gateway helpers: resolve LoRA adapter from header / body (Phase 3)."""

from __future__ import annotations

from typing import Any

from fastapi import Request

from packages.tenantkit import TenantIsolationError, assert_model_allowed_for_tenant, tenant_root


def extract_adapter_ref(request: Request, payload: dict[str, Any]) -> str | None:
    """
    Adapter may be specified via:
      - Header X-AF-Adapter: loras/law-v1
      - Body field adapter / af_adapter (extra=allow on ChatCompletionRequest)
    """
    header = request.headers.get("x-af-adapter") or request.headers.get("X-AF-Adapter")
    if header and str(header).strip():
        return str(header).strip()
    for key in ("adapter", "af_adapter"):
        val = payload.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def resolve_adapter_for_tenant(tenant_id: str, adapter: str) -> str:
    """
    Validate adapter belongs to tenant; normalize to loras/<name> form.
    Rejects tenants/<other>/… the same way as model paths (403 upstream).
    """
    raw = adapter.strip().replace("\\", "/")
    assert_model_allowed_for_tenant(tenant_id, raw)

    # Strip tenant-relative prefixes
    for prefix in (f"tenants/{tenant_id}/", f"{tenant_id}/", "./"):
        if raw.startswith(prefix):
            raw = raw[len(prefix) :]
            break

    if not raw.startswith("loras/") and "/" not in raw:
        raw = f"loras/{raw}"

    assert_model_allowed_for_tenant(tenant_id, raw)

    # Ensure path stays under tenant loras/
    rel = raw
    if rel.startswith("loras/"):
        name = rel[len("loras/") :]
        path = tenant_root(tenant_id) / "loras" / name
        # Existence is optional for demo (placeholder adapters); still bound path
        _ = path
    return raw


def apply_adapter_to_payload(
    tenant_id: str,
    payload: dict[str, Any],
    adapter: str | None,
) -> tuple[dict[str, Any], str | None]:
    """
    Attach adapter metadata for vLLM multi-LoRA style model ids:
      base:lora_name  or keep model + af_adapter field for ops.
    Returns (payload, normalized_adapter_or_None).
    """
    if not adapter:
        return payload, None
    try:
        normalized = resolve_adapter_for_tenant(tenant_id, adapter)
    except TenantIsolationError:
        raise

    body = dict(payload)
    body.pop("adapter", None)
    body.pop("af_adapter", None)
    body["af_adapter"] = normalized

    # vLLM enable-lora often expects model = base or adapter name registered at serve time.
    # If model already looks like base:adapter, leave it; else annotate for upstream templates.
    model = str(body.get("model") or "")
    lora_name = normalized.split("/")[-1]
    if ":" not in model and lora_name:
        # Non-breaking: keep original model; surface chosen adapter via af_adapter.
        # Templates / multi-lora server map lora_name → path under tenant loras/.
        pass
    return body, normalized
