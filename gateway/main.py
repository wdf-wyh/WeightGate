# FastAPI OpenAI-compatible gateway (data plane) — Phase 4.
# Auth: Bearer API key → tenant_id. Hybrid route: Ollama / vLLM / cloud providers.
# Vector: per-tenant LocalVectorStore under data/tenants/{id}/vector/.

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Any

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
GW = Path(__file__).resolve().parent
for p in (ROOT, GW):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from packages.contracts import (  # noqa: E402
    ChatCompletionRequest,
    ErrorBody,
    ErrorResponse,
    ModelListResponse,
    ModelObject,
)
from packages.tenantkit import (  # noqa: E402
    LocalVectorStore,
    TenantIsolationError,
    assert_model_allowed_for_tenant,
    chroma_persist_dir,
    ensure_tenant_layout,
    tenant_root,
    tenant_vector_dir,
)
from packages.tenantkit.keys import KeyRecord  # noqa: E402

from adapter import apply_adapter_to_payload, extract_adapter_ref  # noqa: E402
from auth import require_tenant  # noqa: E402
import cloud_proxy  # noqa: E402
import ollama_proxy  # noqa: E402
from preset_index import backend_for_model  # noqa: E402
from rate_limit import check_rpm, get_redis  # noqa: E402
from router import PolicyMode, choose_route  # noqa: E402
from usage import extract_usage_tokens, record_usage  # noqa: E402
import vllm_proxy  # noqa: E402

# Re-export for smoke tests that patch gw.forward_models
forward_models = ollama_proxy.forward_models
forward_chat_completions = ollama_proxy.forward_chat_completions

app = FastAPI(title="automatic-funicular gateway", version="0.4.0")


class VectorUpsertBody(BaseModel):
    collection: str = "default"
    ids: list[str] = Field(min_length=1)
    documents: list[str] = Field(min_length=1)
    metadatas: list[dict[str, Any]] | None = None


class VectorQueryBody(BaseModel):
    collection: str = "default"
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=50)


def _touch_last_active(tenant_id: str) -> None:
    try:
        r = get_redis()
        if r is not None:
            r.set(f"af:last_active:{tenant_id}", str(time.time()), ex=86400 * 7)
    except Exception:
        pass
    try:
        path = tenant_root(tenant_id) / "cache" / "last_active"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(time.time()), encoding="utf-8")
    except OSError:
        pass


def _error(status: int, message: str, err_type: str, code: str | None = None) -> JSONResponse:
    body = ErrorResponse(
        error=ErrorBody(message=message, type=err_type, param=None, code=code)
    )
    return JSONResponse(status_code=status, content=body.model_dump())


async def _fetch_route_policy(tenant_id: str) -> tuple[PolicyMode, int]:
    cp = os.environ.get("CONTROL_PLANE_URL", "").rstrip("/")
    default_mode: PolicyMode = "hybrid"
    default_chars = int(os.environ.get("AF_HYBRID_SHORT_MAX_CHARS", "800"))
    if not cp:
        return default_mode, default_chars
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{cp}/internal/v1/tenants/{tenant_id}/route-policy")
        if resp.status_code == 200:
            data = resp.json()
            mode = data.get("mode") or default_mode
            if mode not in ("local_only", "cloud_only", "hybrid"):
                mode = default_mode
            chars = int(data.get("short_max_chars") or default_chars)
            return mode, chars  # type: ignore[return-value]
    except Exception:
        pass
    return default_mode, default_chars


async def _dispatch_chat(route: str, payload: dict[str, Any]) -> httpx.Response:
    """Send to backend; cloud/vllm failures may degrade to Ollama when allowed."""
    allow_degrade = os.environ.get("AF_ROUTE_DEGRADE", "1").strip() != "0"

    if route == "local":
        return await ollama_proxy.forward_chat_completions(payload)

    if route == "vllm":
        try:
            return await vllm_proxy.forward_chat_completions(payload)
        except Exception:
            if allow_degrade:
                return await ollama_proxy.forward_chat_completions(payload)
            raise

    if route == "cloud":
        try:
            if not cloud_proxy.cloud_configured():
                raise RuntimeError("cloud not configured")
            return await cloud_proxy.forward_chat_completions(payload)
        except Exception:
            if allow_degrade:
                return await ollama_proxy.forward_chat_completions(payload)
            raise

    return await ollama_proxy.forward_chat_completions(payload)


@app.on_event("startup")
def _startup() -> None:
    for tid in ("tenant_a", "tenant_b"):
        try:
            ensure_tenant_layout(tid)
            tenant_vector_dir(tid)
        except Exception:
            pass


@app.get("/health")
async def health() -> dict[str, Any]:
    info = cloud_proxy.provider_info()
    return {
        "status": "ok",
        "plane": "data",
        "phase": "4",
        "ollama": await ollama_proxy.ollama_health(),
        "vllm": await vllm_proxy.vllm_health(),
        "cloud_configured": cloud_proxy.cloud_configured(),
        "cloud_provider": info.name,
        "cloud_base_url": info.base_url,
        "night_window": cloud_proxy.night_window_config(),
        "in_night_window": cloud_proxy.is_night_window(),
    }


@app.get("/v1/models")
async def list_models(tenant: KeyRecord = Depends(require_tenant)) -> Any:
    allowed, _ = check_rpm(tenant.tenant_id, tenant.rpm_limit)
    if not allowed:
        return _error(429, "Rate limit exceeded", "rate_limit_error", "rate_limit_exceeded")

    ensure_tenant_layout(tenant.tenant_id)
    _touch_last_active(tenant.tenant_id)
    try:
        upstream = await forward_models()
    except Exception as exc:
        return _error(502, f"Ollama unreachable: {exc}", "server_error", "upstream_error")

    if upstream.status_code >= 400:
        return Response(content=upstream.content, status_code=upstream.status_code, media_type="application/json")

    data = upstream.json()
    models = data.get("data") or []
    filtered: list[dict[str, Any]] = []
    for m in models:
        mid = str(m.get("id", ""))
        try:
            assert_model_allowed_for_tenant(tenant.tenant_id, mid)
        except TenantIsolationError:
            continue
        if tenant.allowed_models and mid not in tenant.allowed_models:
            continue
        filtered.append(
            ModelObject(
                id=mid,
                created=int(m.get("created") or int(time.time())),
                owned_by=tenant.tenant_id,
            ).model_dump()
        )

    root = tenant_root(tenant.tenant_id)
    for sub in ("models", "loras"):
        d = root / sub
        if not d.is_dir():
            continue
        for p in d.iterdir():
            if p.name.startswith("."):
                continue
            mid = f"{sub}/{p.name}"
            filtered.append(
                ModelObject(
                    id=mid,
                    created=int(p.stat().st_mtime),
                    owned_by=tenant.tenant_id,
                ).model_dump()
            )

    return ModelListResponse(data=[ModelObject.model_validate(x) for x in filtered]).model_dump()


@app.post("/v1/chat/completions")
async def chat_completions(
    body: ChatCompletionRequest,
    request: Request,
    tenant: KeyRecord = Depends(require_tenant),
) -> Any:
    allowed, _ = check_rpm(tenant.tenant_id, tenant.rpm_limit)
    if not allowed:
        return _error(429, "Rate limit exceeded", "rate_limit_error", "rate_limit_exceeded")

    try:
        assert_model_allowed_for_tenant(tenant.tenant_id, body.model)
    except TenantIsolationError as exc:
        return _error(403, str(exc), "permission_error", "cross_tenant_denied")

    if tenant.allowed_models and body.model not in tenant.allowed_models:
        if "/" in body.model or body.model.startswith("loras/") or body.model.startswith("models/"):
            return _error(403, "model not allowed for tenant", "permission_error", "model_denied")
        return _error(403, "model not allowed for tenant", "permission_error", "model_denied")

    ensure_tenant_layout(tenant.tenant_id)
    _touch_last_active(tenant.tenant_id)

    if body.stream:
        return _error(
            501,
            "Streaming not enabled in Phase 3 prototype; set stream=false",
            "invalid_request_error",
            "stream_not_supported",
        )

    payload = body.model_dump(exclude_none=True)
    payload.pop("user", None)

    adapter_ref = extract_adapter_ref(request, payload)
    try:
        payload, adapter_norm = apply_adapter_to_payload(tenant.tenant_id, payload, adapter_ref)
    except TenantIsolationError as exc:
        return _error(403, str(exc), "permission_error", "cross_tenant_denied")

    policy_mode, short_max = await _fetch_route_policy(tenant.tenant_id)
    preset_backend = backend_for_model(body.model)
    decision = choose_route(
        policy_mode=policy_mode,
        short_max_chars=short_max,
        payload=payload,
        preset_backend=preset_backend,
    )
    route = decision.route

    t0 = time.perf_counter()
    try:
        upstream = await _dispatch_chat(route, payload)
    except Exception as exc:
        return _error(502, f"Upstream unreachable: {exc}", "server_error", "upstream_error")
    latency_ms = int((time.perf_counter() - t0) * 1000)

    if upstream.status_code >= 400:
        return Response(
            content=upstream.content,
            status_code=upstream.status_code,
            media_type=upstream.headers.get("content-type", "application/json"),
        )

    data = upstream.json()
    data.setdefault("object", "chat.completion")
    data["af_route"] = route
    data["af_route_reason"] = decision.reason
    if adapter_norm:
        data["af_adapter"] = adapter_norm

    pt, ct = extract_usage_tokens(data)
    await record_usage(
        tenant_id=tenant.tenant_id,
        model=body.model,
        prompt_tokens=pt,
        completion_tokens=ct,
        route=route,
        latency_ms=latency_ms,
    )

    return JSONResponse(content=data)


# ---------------------------------------------------------------------------
# Per-tenant vector store (Phase 3)
# ---------------------------------------------------------------------------
@app.get("/v1/vector/info")
async def vector_info(tenant: KeyRecord = Depends(require_tenant)) -> dict[str, Any]:
    ensure_tenant_layout(tenant.tenant_id)
    vdir = tenant_vector_dir(tenant.tenant_id)
    return {
        "tenant_id": tenant.tenant_id,
        "vector_root": str(vdir),
        "chroma_persist_dir": str(chroma_persist_dir(tenant.tenant_id)),
        "backend": "local_jsonl",
    }


@app.post("/v1/vector/upsert")
async def vector_upsert(
    body: VectorUpsertBody,
    tenant: KeyRecord = Depends(require_tenant),
) -> dict[str, Any]:
    allowed, _ = check_rpm(tenant.tenant_id, tenant.rpm_limit)
    if not allowed:
        return _error(429, "Rate limit exceeded", "rate_limit_error", "rate_limit_exceeded")
    try:
        store = LocalVectorStore(tenant.tenant_id, body.collection)
        n = store.upsert(ids=body.ids, documents=body.documents, metadatas=body.metadatas)
    except TenantIsolationError as exc:
        return _error(403, str(exc), "permission_error", "cross_tenant_denied")
    except ValueError as exc:
        return _error(400, str(exc), "invalid_request_error", "bad_vector_payload")
    _touch_last_active(tenant.tenant_id)
    return {"tenant_id": tenant.tenant_id, "collection": body.collection, "upserted": n}


@app.post("/v1/vector/query")
async def vector_query(
    body: VectorQueryBody,
    tenant: KeyRecord = Depends(require_tenant),
) -> dict[str, Any]:
    allowed, _ = check_rpm(tenant.tenant_id, tenant.rpm_limit)
    if not allowed:
        return _error(429, "Rate limit exceeded", "rate_limit_error", "rate_limit_exceeded")
    try:
        store = LocalVectorStore(tenant.tenant_id, body.collection)
        hits = store.query(text=body.query, top_k=body.top_k)
    except TenantIsolationError as exc:
        return _error(403, str(exc), "permission_error", "cross_tenant_denied")
    _touch_last_active(tenant.tenant_id)
    return {
        "tenant_id": tenant.tenant_id,
        "collection": body.collection,
        "hits": [
            {"id": h.id, "score": h.score, "document": h.document, "metadata": h.metadata}
            for h in hits
        ],
    }


@app.exception_handler(HTTPException)
async def http_exc_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, dict) and "error" in detail:
        return JSONResponse(status_code=exc.status_code, content=detail)
    return _error(exc.status_code, str(detail), "invalid_request_error", None)


def main() -> None:
    import uvicorn

    host = os.environ.get("AF_HOST", "0.0.0.0")
    port = int(os.environ.get("AF_PORT", "8000"))
    uvicorn.run("main:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
