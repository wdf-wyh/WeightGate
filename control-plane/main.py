"""Control-plane FastAPI app — tenants, keys, instances, policies, usage, hosts, alerts, mirrors (Phase 4)."""

from __future__ import annotations

import json
import os
import secrets
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.tenantkit import ensure_tenant_layout, tenant_root, validate_tenant_id  # noqa: E402
from packages.tenantkit.keys import (  # noqa: E402
    KeyRecord,
    generate_api_key,
    hash_api_key,
    key_prefix,
    load_keys_from_env,
    resolve_key,
)

from alerts import (  # noqa: E402
    fingerprint,
    post_webhook,
    scan_disk,
    scan_instances_rows,
    scan_quota,
)
from db import init_db, session_scope  # noqa: E402
from docker_driver import start_instance, stop_instance, wake_instance  # noqa: E402
from mirror_catalog import get_product, list_products  # noqa: E402
from mirror_install import install_product_marker  # noqa: E402
from models import (  # noqa: E402
    AlertRow,
    ApiKeyRow,
    HostRow,
    InstanceRow,
    LicenseRow,
    RoutePolicyRow,
    TenantRow,
    UsageEventRow,
)
from presets import get_preset, list_presets  # noqa: E402
from schemas import (  # noqa: E402
    AlertOut,
    AlertScanResult,
    ApiKeyCreate,
    ApiKeyOut,
    HostCreate,
    HostOut,
    HostUpdate,
    InstanceCreate,
    InstanceOut,
    LicenseActivate,
    LicenseIssue,
    LicenseOut,
    MirrorProductOut,
    PresetOut,
    ResolveKeyRequest,
    ResolveKeyResponse,
    RoutePolicyOut,
    RoutePolicyUpdate,
    TenantCreate,
    TenantOut,
    TenantUpdate,
    UsageEventIn,
    UsageEventOut,
    UsageSummary,
)
from ssh_driver import (  # noqa: E402
    HostEndpoint,
    install_remote_agent,
    probe_host,
    start_remote_runtime,
    stop_remote_runtime,
)

app = FastAPI(title="automatic-funicular control-plane", version="0.4.0")

_cors = os.environ.get("AF_CORS_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_ENV_REGISTRY: dict[str, KeyRecord] = {}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(8)}"


def _parse_models(raw: str) -> list[str]:
    try:
        data = json.loads(raw or "[]")
        return [str(x) for x in data] if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def _seed_dev_tenants() -> None:
    """Ensure Phase-1 dual tenants + default hybrid policy exist in DB."""
    with session_scope() as session:
        for tid, name in (("tenant_a", "Tenant A"), ("tenant_b", "Tenant B")):
            row = session.get(TenantRow, tid)
            if row is None:
                session.add(TenantRow(id=tid, name=name, status="active"))
            pol = session.get(RoutePolicyRow, tid)
            if pol is None:
                session.add(RoutePolicyRow(tenant_id=tid, mode="hybrid", short_max_chars=800))
            ensure_tenant_layout(tid)


def _tenant_or_404(session, tenant_id: str) -> TenantRow:
    validate_tenant_id(tenant_id)
    row = session.get(TenantRow, tenant_id)
    if row is None:
        raise HTTPException(status_code=404, detail="unknown_tenant")
    return row


def _key_out(row: ApiKeyRow, plaintext: str | None = None) -> ApiKeyOut:
    return ApiKeyOut(
        id=row.id,
        tenant_id=row.tenant_id,
        key_prefix=row.key_prefix,
        rpm_limit=row.rpm_limit,
        allowed_models=_parse_models(row.allowed_models),
        created_at=row.created_at,
        revoked_at=row.revoked_at,
        api_key=plaintext,
    )


def _instance_out(row: InstanceRow) -> InstanceOut:
    return InstanceOut(
        id=row.id,
        tenant_id=row.tenant_id,
        preset_id=row.preset_id,
        status=row.status,  # type: ignore[arg-type]
        backend=row.backend,
        compose_project=row.compose_project,
        host_id=row.host_id,
        note=row.note,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _host_out(row: HostRow) -> HostOut:
    return HostOut(
        id=row.id,
        name=row.name,
        ssh_host=row.ssh_host,
        ssh_port=row.ssh_port,
        ssh_user=row.ssh_user,
        identity_file=row.identity_file,
        tenant_id=row.tenant_id,
        status=row.status,
        agent_version=row.agent_version,
        note=row.note,
        last_seen_at=row.last_seen_at,
        created_at=row.created_at,
    )


def _alert_out(row: AlertRow) -> AlertOut:
    return AlertOut(
        id=row.id,
        fingerprint=row.fingerprint,
        kind=row.kind,
        severity=row.severity,
        tenant_id=row.tenant_id,
        resource_id=row.resource_id,
        message=row.message,
        status=row.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
        resolved_at=row.resolved_at,
    )


def _license_out(row: LicenseRow, plaintext: str | None = None) -> LicenseOut:
    return LicenseOut(
        id=row.id,
        product_id=row.product_id,
        tenant_id=row.tenant_id,
        key_prefix=row.key_prefix,
        status=row.status,
        activated_at=row.activated_at,
        expires_at=row.expires_at,
        created_at=row.created_at,
        license_key=plaintext,
    )


def _endpoint_from_host(row: HostRow) -> HostEndpoint:
    return HostEndpoint(
        host=row.ssh_host,
        port=row.ssh_port,
        user=row.ssh_user,
        identity_file=row.identity_file,
    )


@app.on_event("startup")
def _startup() -> None:
    global _ENV_REGISTRY
    init_db()
    _ENV_REGISTRY = load_keys_from_env()
    _seed_dev_tenants()
    for rec in _ENV_REGISTRY.values():
        ensure_tenant_layout(rec.tenant_id)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "plane": "control", "phase": "4"}


# ---------------------------------------------------------------------------
# Tenants CRUD
# ---------------------------------------------------------------------------
@app.get("/v1/tenants", response_model=list[TenantOut])
def list_tenants() -> list[TenantOut]:
    with session_scope() as session:
        rows = session.scalars(select(TenantRow).order_by(TenantRow.created_at)).all()
        return [
            TenantOut(id=r.id, name=r.name, status=r.status, created_at=r.created_at) for r in rows
        ]


@app.post("/v1/tenants", response_model=TenantOut, status_code=201)
def create_tenant(body: TenantCreate) -> TenantOut:
    validate_tenant_id(body.id)
    with session_scope() as session:
        if session.get(TenantRow, body.id) is not None:
            raise HTTPException(status_code=409, detail="tenant_exists")
        row = TenantRow(id=body.id, name=body.name, status="active")
        session.add(row)
        session.add(RoutePolicyRow(tenant_id=body.id, mode="hybrid", short_max_chars=800))
        session.flush()
        ensure_tenant_layout(body.id)
        return TenantOut(id=row.id, name=row.name, status=row.status, created_at=row.created_at)


@app.get("/v1/tenants/{tenant_id}", response_model=TenantOut)
def get_tenant(tenant_id: str) -> TenantOut:
    with session_scope() as session:
        row = _tenant_or_404(session, tenant_id)
        return TenantOut(id=row.id, name=row.name, status=row.status, created_at=row.created_at)


@app.patch("/v1/tenants/{tenant_id}", response_model=TenantOut)
def update_tenant(tenant_id: str, body: TenantUpdate) -> TenantOut:
    with session_scope() as session:
        row = _tenant_or_404(session, tenant_id)
        if body.name is not None:
            row.name = body.name
        if body.status is not None:
            row.status = body.status
        session.flush()
        return TenantOut(id=row.id, name=row.name, status=row.status, created_at=row.created_at)


@app.delete("/v1/tenants/{tenant_id}")
def delete_tenant(tenant_id: str) -> dict[str, str]:
    with session_scope() as session:
        row = _tenant_or_404(session, tenant_id)
        # Protect built-in dual tenants used by Phase 1 smoke keys
        if tenant_id in ("tenant_a", "tenant_b") and os.environ.get("AF_ALLOW_DELETE_DEV") != "1":
            raise HTTPException(status_code=400, detail="cannot_delete_dev_tenant")
        session.delete(row)
    return {"status": "deleted"}


# ---------------------------------------------------------------------------
# API keys (hash at rest)
# ---------------------------------------------------------------------------
@app.get("/v1/tenants/{tenant_id}/keys", response_model=list[ApiKeyOut])
def list_keys(tenant_id: str) -> list[ApiKeyOut]:
    with session_scope() as session:
        _tenant_or_404(session, tenant_id)
        rows = session.scalars(
            select(ApiKeyRow)
            .where(ApiKeyRow.tenant_id == tenant_id)
            .order_by(ApiKeyRow.created_at.desc())
        ).all()
        return [_key_out(r) for r in rows]


@app.post("/v1/tenants/{tenant_id}/keys", response_model=ApiKeyOut, status_code=201)
def issue_key(tenant_id: str, body: ApiKeyCreate) -> ApiKeyOut:
    with session_scope() as session:
        _tenant_or_404(session, tenant_id)
        plaintext = generate_api_key()
        row = ApiKeyRow(
            id=_new_id("key"),
            tenant_id=tenant_id,
            key_hash=hash_api_key(plaintext),
            key_prefix=key_prefix(plaintext),
            rpm_limit=body.rpm_limit,
            allowed_models=json.dumps(body.allowed_models),
        )
        session.add(row)
        session.flush()
        return _key_out(row, plaintext=plaintext)


@app.post("/v1/tenants/{tenant_id}/keys/{key_id}/rotate", response_model=ApiKeyOut)
def rotate_key(tenant_id: str, key_id: str) -> ApiKeyOut:
    with session_scope() as session:
        _tenant_or_404(session, tenant_id)
        row = session.get(ApiKeyRow, key_id)
        if row is None or row.tenant_id != tenant_id:
            raise HTTPException(status_code=404, detail="unknown_key")
        if row.revoked_at is not None:
            raise HTTPException(status_code=400, detail="key_revoked")
        plaintext = generate_api_key()
        row.key_hash = hash_api_key(plaintext)
        row.key_prefix = key_prefix(plaintext)
        session.flush()
        return _key_out(row, plaintext=plaintext)


@app.delete("/v1/tenants/{tenant_id}/keys/{key_id}")
def revoke_key(tenant_id: str, key_id: str) -> dict[str, str]:
    with session_scope() as session:
        _tenant_or_404(session, tenant_id)
        row = session.get(ApiKeyRow, key_id)
        if row is None or row.tenant_id != tenant_id:
            raise HTTPException(status_code=404, detail="unknown_key")
        row.revoked_at = _utcnow()
    return {"status": "revoked"}


# ---------------------------------------------------------------------------
# Model presets
# ---------------------------------------------------------------------------
@app.get("/v1/presets", response_model=list[PresetOut])
def presets() -> list[PresetOut]:
    out: list[PresetOut] = []
    for p in list_presets():
        out.append(
            PresetOut(
                id=p["id"],
                display_name=p["display_name"],
                params_b=int(p["params_b"]),
                backend=p["backend"],
                quant=p["quant"],
                min_vram_gb=int(p["min_vram_gb"]),
                notes=p.get("notes"),
            )
        )
    return out


# ---------------------------------------------------------------------------
# Instances (Docker Compose driver)
# ---------------------------------------------------------------------------
@app.get("/v1/tenants/{tenant_id}/instances", response_model=list[InstanceOut])
def list_instances(tenant_id: str) -> list[InstanceOut]:
    with session_scope() as session:
        _tenant_or_404(session, tenant_id)
        rows = session.scalars(
            select(InstanceRow)
            .where(InstanceRow.tenant_id == tenant_id)
            .order_by(InstanceRow.created_at.desc())
        ).all()
        return [_instance_out(r) for r in rows]


@app.post("/v1/tenants/{tenant_id}/instances", response_model=InstanceOut, status_code=201)
def create_instance(tenant_id: str, body: InstanceCreate) -> InstanceOut:
    preset = get_preset(body.preset_id)
    if preset is None:
        raise HTTPException(status_code=400, detail="unknown_preset")
    backend = str(preset.get("backend") or "ollama")
    with session_scope() as session:
        _tenant_or_404(session, tenant_id)
        host_row: HostRow | None = None
        if body.host_id:
            host_row = session.get(HostRow, body.host_id)
            if host_row is None:
                raise HTTPException(status_code=404, detail="unknown_host")
            if host_row.tenant_id and host_row.tenant_id != tenant_id:
                raise HTTPException(status_code=403, detail="host_tenant_mismatch")

        iid = _new_id("inst")
        if host_row is not None:
            status, note = start_remote_runtime(
                _endpoint_from_host(host_row),
                tenant_id=tenant_id,
                instance_id=iid,
                preset_id=body.preset_id,
                backend=backend,
            )
            compose = None
        else:
            status, note = start_instance(
                tenant_id=tenant_id,
                instance_id=iid,
                preset_id=body.preset_id,
                backend=backend,
            )
            from docker_driver import project_name

            compose = project_name(tenant_id, iid) if status == "running" else None

        row = InstanceRow(
            id=iid,
            tenant_id=tenant_id,
            preset_id=body.preset_id,
            status=status,
            backend=backend,
            compose_project=compose,
            host_id=body.host_id,
            note=note,
            updated_at=_utcnow(),
        )
        session.add(row)
        session.flush()
        return _instance_out(row)


@app.post("/v1/instances/{instance_id}/stop", response_model=InstanceOut)
def stop_instance_api(instance_id: str) -> InstanceOut:
    with session_scope() as session:
        row = session.get(InstanceRow, instance_id)
        if row is None:
            raise HTTPException(status_code=404, detail="unknown_instance")
        if row.host_id:
            host = session.get(HostRow, row.host_id)
            if host is None:
                status, note = "stopped", "host missing; marked stopped"
            else:
                status, note = stop_remote_runtime(
                    _endpoint_from_host(host), instance_id=row.id
                )
        else:
            status, note = stop_instance(row.compose_project)
        row.status = status
        row.note = note
        row.updated_at = _utcnow()
        session.flush()
        return _instance_out(row)


@app.post("/v1/instances/{instance_id}/wake", response_model=InstanceOut)
def wake_instance_api(instance_id: str) -> InstanceOut:
    with session_scope() as session:
        row = session.get(InstanceRow, instance_id)
        if row is None:
            raise HTTPException(status_code=404, detail="unknown_instance")
        if row.host_id:
            host = session.get(HostRow, row.host_id)
            if host is None:
                raise HTTPException(status_code=400, detail="host_missing")
            status, note = start_remote_runtime(
                _endpoint_from_host(host),
                tenant_id=row.tenant_id,
                instance_id=row.id,
                preset_id=row.preset_id,
                backend=row.backend,
            )
        else:
            status, note = wake_instance(
                tenant_id=row.tenant_id,
                instance_id=row.id,
                preset_id=row.preset_id,
                backend=row.backend,
                compose_project=row.compose_project,
            )
            from docker_driver import project_name

            if status == "running" and not row.compose_project:
                row.compose_project = project_name(row.tenant_id, row.id)
        row.status = status
        row.note = note
        row.updated_at = _utcnow()
        session.flush()
        return _instance_out(row)


# ---------------------------------------------------------------------------
# Hosts (SSH remote provider)
# ---------------------------------------------------------------------------
@app.get("/v1/hosts", response_model=list[HostOut])
def list_hosts() -> list[HostOut]:
    with session_scope() as session:
        rows = session.scalars(select(HostRow).order_by(HostRow.created_at.desc())).all()
        return [_host_out(r) for r in rows]


@app.post("/v1/hosts", response_model=HostOut, status_code=201)
def create_host(body: HostCreate) -> HostOut:
    with session_scope() as session:
        if body.tenant_id:
            _tenant_or_404(session, body.tenant_id)
        row = HostRow(
            id=_new_id("host"),
            name=body.name,
            ssh_host=body.ssh_host,
            ssh_port=body.ssh_port,
            ssh_user=body.ssh_user,
            identity_file=body.identity_file,
            tenant_id=body.tenant_id,
            status="unknown",
        )
        session.add(row)
        session.flush()
        return _host_out(row)


@app.get("/v1/hosts/{host_id}", response_model=HostOut)
def get_host(host_id: str) -> HostOut:
    with session_scope() as session:
        row = session.get(HostRow, host_id)
        if row is None:
            raise HTTPException(status_code=404, detail="unknown_host")
        return _host_out(row)


@app.patch("/v1/hosts/{host_id}", response_model=HostOut)
def update_host(host_id: str, body: HostUpdate) -> HostOut:
    with session_scope() as session:
        row = session.get(HostRow, host_id)
        if row is None:
            raise HTTPException(status_code=404, detail="unknown_host")
        if body.name is not None:
            row.name = body.name
        if body.ssh_port is not None:
            row.ssh_port = body.ssh_port
        if body.ssh_user is not None:
            row.ssh_user = body.ssh_user
        if body.identity_file is not None:
            row.identity_file = body.identity_file
        if body.tenant_id is not None:
            if body.tenant_id:
                _tenant_or_404(session, body.tenant_id)
            row.tenant_id = body.tenant_id or None
        session.flush()
        return _host_out(row)


@app.delete("/v1/hosts/{host_id}")
def delete_host(host_id: str) -> dict[str, str]:
    with session_scope() as session:
        row = session.get(HostRow, host_id)
        if row is None:
            raise HTTPException(status_code=404, detail="unknown_host")
        session.delete(row)
    return {"status": "deleted"}


@app.post("/v1/hosts/{host_id}/probe", response_model=HostOut)
def probe_host_api(host_id: str) -> HostOut:
    with session_scope() as session:
        row = session.get(HostRow, host_id)
        if row is None:
            raise HTTPException(status_code=404, detail="unknown_host")
        status, note = probe_host(_endpoint_from_host(row))
        row.status = status
        row.note = note
        row.last_seen_at = _utcnow() if status in {"online", "simulated"} else row.last_seen_at
        session.flush()
        return _host_out(row)


@app.post("/v1/hosts/{host_id}/install-agent", response_model=HostOut)
def install_agent_api(host_id: str) -> HostOut:
    with session_scope() as session:
        row = session.get(HostRow, host_id)
        if row is None:
            raise HTTPException(status_code=404, detail="unknown_host")
        status, note = install_remote_agent(_endpoint_from_host(row))
        row.status = status if status != "error" else "offline"
        row.note = note
        row.agent_version = "0.4.0" if status == "installed" else row.agent_version
        row.last_seen_at = _utcnow()
        session.flush()
        return _host_out(row)


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------
@app.get("/v1/alerts", response_model=list[AlertOut])
def list_alerts(
    status: str | None = Query(default="open"),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[AlertOut]:
    with session_scope() as session:
        stmt = select(AlertRow).order_by(AlertRow.created_at.desc()).limit(limit)
        if status:
            stmt = stmt.where(AlertRow.status == status)
        rows = session.scalars(stmt).all()
        return [_alert_out(r) for r in rows]


@app.post("/v1/alerts/scan", response_model=AlertScanResult)
def scan_alerts() -> AlertScanResult:
    drafts = []
    drafts.extend(scan_disk())
    with session_scope() as session:
        instances = session.scalars(select(InstanceRow)).all()
        drafts.extend(scan_instances_rows(list(instances)))
        keys = session.scalars(select(ApiKeyRow)).all()
        redis_client = None
        try:
            import redis

            url = os.environ.get("REDIS_URL", "").strip()
            if url:
                redis_client = redis.Redis.from_url(url, decode_responses=True)
        except Exception:  # noqa: BLE001
            redis_client = None
        drafts.extend(scan_quota(list(keys), redis_client))

        created = 0
        for d in drafts:
            fp = fingerprint(d)
            existing = session.scalars(
                select(AlertRow).where(AlertRow.fingerprint == fp, AlertRow.status == "open")
            ).first()
            if existing is not None:
                existing.updated_at = _utcnow()
                existing.message = d.message
                continue
            session.add(
                AlertRow(
                    id=_new_id("alert"),
                    fingerprint=fp,
                    kind=d.kind,
                    severity=d.severity,
                    tenant_id=d.tenant_id,
                    resource_id=d.resource_id,
                    message=d.message,
                    status="open",
                )
            )
            created += 1
        session.flush()
        open_rows = session.scalars(select(AlertRow).where(AlertRow.status == "open")).all()
        result = AlertScanResult(
            created=created,
            open_total=len(open_rows),
            alerts=[_alert_out(r) for r in open_rows[:50]],
        )
    post_webhook(drafts)
    return result


@app.post("/v1/alerts/{alert_id}/ack", response_model=AlertOut)
def ack_alert(alert_id: str) -> AlertOut:
    with session_scope() as session:
        row = session.get(AlertRow, alert_id)
        if row is None:
            raise HTTPException(status_code=404, detail="unknown_alert")
        row.status = "acked"
        row.updated_at = _utcnow()
        session.flush()
        return _alert_out(row)


@app.post("/v1/alerts/{alert_id}/resolve", response_model=AlertOut)
def resolve_alert(alert_id: str) -> AlertOut:
    with session_scope() as session:
        row = session.get(AlertRow, alert_id)
        if row is None:
            raise HTTPException(status_code=404, detail="unknown_alert")
        row.status = "resolved"
        row.resolved_at = _utcnow()
        row.updated_at = _utcnow()
        session.flush()
        return _alert_out(row)


# ---------------------------------------------------------------------------
# Vertical mirror store + licenses
# ---------------------------------------------------------------------------
@app.get("/v1/mirrors", response_model=list[MirrorProductOut])
def list_mirrors() -> list[MirrorProductOut]:
    out: list[MirrorProductOut] = []
    for p in list_products():
        out.append(
            MirrorProductOut(
                id=str(p["id"]),
                display_name=str(p.get("display_name") or p["id"]),
                domain=str(p.get("domain") or ""),
                price_cny=int(p.get("price_cny") or 0),
                example_path=str(p.get("example_path") or ""),
                adapter_slug=str(p.get("adapter_slug") or ""),
                base_preset_hint=p.get("base_preset_hint"),
                description=p.get("description"),
            )
        )
    return out


@app.post("/v1/mirrors/{product_id}/licenses", response_model=LicenseOut, status_code=201)
def issue_license(product_id: str, body: LicenseIssue) -> LicenseOut:
    product = get_product(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="unknown_product")
    with session_scope() as session:
        _tenant_or_404(session, body.tenant_id)
        plaintext = generate_api_key(prefix="lic-af")
        expires = None
        if body.days_valid:
            expires = _utcnow() + timedelta(days=body.days_valid)
        row = LicenseRow(
            id=_new_id("lic"),
            product_id=product_id,
            tenant_id=body.tenant_id,
            key_hash=hash_api_key(plaintext),
            key_prefix=key_prefix(plaintext),
            status="active",
            expires_at=expires,
        )
        session.add(row)
        session.flush()
        return _license_out(row, plaintext=plaintext)


@app.get("/v1/tenants/{tenant_id}/licenses", response_model=list[LicenseOut])
def list_tenant_licenses(tenant_id: str) -> list[LicenseOut]:
    with session_scope() as session:
        _tenant_or_404(session, tenant_id)
        rows = session.scalars(
            select(LicenseRow)
            .where(LicenseRow.tenant_id == tenant_id)
            .order_by(LicenseRow.created_at.desc())
        ).all()
        return [_license_out(r) for r in rows]


@app.post("/v1/mirrors/activate", response_model=LicenseOut)
def activate_license(body: LicenseActivate) -> LicenseOut:
    digest = hash_api_key(body.license_key)
    with session_scope() as session:
        row = session.scalars(
            select(LicenseRow).where(LicenseRow.key_hash == digest, LicenseRow.status == "active")
        ).first()
        if row is None:
            raise HTTPException(status_code=404, detail="invalid_license")
        if row.expires_at is not None:
            exp = row.expires_at
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp < _utcnow():
                row.status = "expired"
                session.flush()
                raise HTTPException(status_code=400, detail="license_expired")
        product = get_product(row.product_id)
        if product is None:
            raise HTTPException(status_code=400, detail="product_missing")
        adapter_path = install_product_marker(
            tenant_id=row.tenant_id,
            product=product,
            license_id=row.id,
        )
        row.activated_at = _utcnow()
        session.flush()
        out = _license_out(row)
        # Surface install path via unused field is awkward; append to response by mutating note
        # Clients can read adapter from product catalog + tenant layout.
        _ = adapter_path
        return out


# ---------------------------------------------------------------------------
# Route policy
# ---------------------------------------------------------------------------
@app.get("/v1/tenants/{tenant_id}/route-policy", response_model=RoutePolicyOut)
def get_route_policy(tenant_id: str) -> RoutePolicyOut:
    with session_scope() as session:
        _tenant_or_404(session, tenant_id)
        pol = session.get(RoutePolicyRow, tenant_id)
        if pol is None:
            pol = RoutePolicyRow(tenant_id=tenant_id, mode="hybrid", short_max_chars=800)
            session.add(pol)
            session.flush()
        return RoutePolicyOut(
            tenant_id=pol.tenant_id,
            mode=pol.mode,  # type: ignore[arg-type]
            short_max_chars=pol.short_max_chars,
            updated_at=pol.updated_at,
        )


@app.put("/v1/tenants/{tenant_id}/route-policy", response_model=RoutePolicyOut)
def put_route_policy(tenant_id: str, body: RoutePolicyUpdate) -> RoutePolicyOut:
    with session_scope() as session:
        _tenant_or_404(session, tenant_id)
        pol = session.get(RoutePolicyRow, tenant_id)
        if pol is None:
            pol = RoutePolicyRow(tenant_id=tenant_id, mode=body.mode)
            session.add(pol)
        else:
            pol.mode = body.mode
        if body.short_max_chars is not None:
            pol.short_max_chars = body.short_max_chars
        pol.updated_at = _utcnow()
        session.flush()
        return RoutePolicyOut(
            tenant_id=pol.tenant_id,
            mode=pol.mode,  # type: ignore[arg-type]
            short_max_chars=pol.short_max_chars,
            updated_at=pol.updated_at,
        )


# ---------------------------------------------------------------------------
# Usage
# ---------------------------------------------------------------------------
@app.get("/v1/tenants/{tenant_id}/usage", response_model=UsageSummary)
def get_usage(tenant_id: str, limit: int = Query(default=50, ge=1, le=500)) -> UsageSummary:
    with session_scope() as session:
        _tenant_or_404(session, tenant_id)
        rows = session.scalars(
            select(UsageEventRow)
            .where(UsageEventRow.tenant_id == tenant_id)
            .order_by(UsageEventRow.created_at.desc())
            .limit(limit)
        ).all()
        # Aggregate over all events for tenant (not just page)
        all_rows = session.scalars(
            select(UsageEventRow).where(UsageEventRow.tenant_id == tenant_id)
        ).all()
        by_route: dict[str, int] = {}
        pt = ct = tt = 0
        for r in all_rows:
            by_route[r.route] = by_route.get(r.route, 0) + 1
            pt += r.prompt_tokens
            ct += r.completion_tokens
            tt += r.total_tokens
        events = [
            UsageEventOut(
                id=r.id,
                tenant_id=r.tenant_id,
                model=r.model,
                prompt_tokens=r.prompt_tokens,
                completion_tokens=r.completion_tokens,
                total_tokens=r.total_tokens,
                route=r.route,
                latency_ms=r.latency_ms,
                created_at=r.created_at,
            )
            for r in rows
        ]
        return UsageSummary(
            tenant_id=tenant_id,
            total_events=len(all_rows),
            prompt_tokens=pt,
            completion_tokens=ct,
            total_tokens=tt,
            by_route=by_route,
            events=events,
        )


@app.post("/internal/v1/usage", response_model=UsageEventOut, status_code=201)
def ingest_usage(
    body: UsageEventIn,
    x_af_internal: str | None = Header(default=None, alias="X-AF-Internal"),
) -> UsageEventOut:
    expected = os.environ.get("AF_INTERNAL_TOKEN", "").strip()
    if expected and x_af_internal != expected:
        raise HTTPException(status_code=403, detail="forbidden")
    total = body.total_tokens
    if total is None:
        total = body.prompt_tokens + body.completion_tokens
    with session_scope() as session:
        # Tenant may exist only in env registry; still record usage by id
        row = UsageEventRow(
            id=_new_id("usage"),
            tenant_id=body.tenant_id,
            model=body.model,
            prompt_tokens=body.prompt_tokens,
            completion_tokens=body.completion_tokens,
            total_tokens=total,
            route=body.route,
            latency_ms=body.latency_ms,
        )
        session.add(row)
        session.flush()
        return UsageEventOut(
            id=row.id,
            tenant_id=row.tenant_id,
            model=row.model,
            prompt_tokens=row.prompt_tokens,
            completion_tokens=row.completion_tokens,
            total_tokens=row.total_tokens,
            route=row.route,
            latency_ms=row.latency_ms,
            created_at=row.created_at,
        )


# ---------------------------------------------------------------------------
# Internal: resolve-key (DB hash lookup + env fallback)
# ---------------------------------------------------------------------------
@app.post("/internal/v1/resolve-key", response_model=ResolveKeyResponse)
def internal_resolve_key(body: ResolveKeyRequest) -> ResolveKeyResponse:
    digest = hash_api_key(body.api_key)
    with session_scope() as session:
        row = session.scalars(
            select(ApiKeyRow).where(ApiKeyRow.key_hash == digest, ApiKeyRow.revoked_at.is_(None))
        ).first()
        if row is not None:
            tenant = session.get(TenantRow, row.tenant_id)
            if tenant is None or tenant.status != "active":
                raise HTTPException(status_code=401, detail="invalid_api_key")
            return ResolveKeyResponse(
                tenant_id=row.tenant_id,
                rpm_limit=row.rpm_limit,
                allowed_models=_parse_models(row.allowed_models),
            )

    rec = resolve_key(body.api_key, _ENV_REGISTRY or load_keys_from_env())
    if rec is None:
        raise HTTPException(status_code=401, detail="invalid_api_key")
    return ResolveKeyResponse(
        tenant_id=rec.tenant_id,
        rpm_limit=rec.rpm_limit,
        allowed_models=list(rec.allowed_models),
    )


@app.get("/internal/v1/tenants/{tenant_id}/route-policy", response_model=RoutePolicyOut)
def internal_route_policy(tenant_id: str) -> RoutePolicyOut:
    return get_route_policy(tenant_id)


@app.get("/internal/v1/tenants/{tenant_id}/root")
def tenant_data_root(
    tenant_id: str,
    x_af_internal: str | None = Header(default=None, alias="X-AF-Internal"),
) -> dict[str, str]:
    expected = os.environ.get("AF_INTERNAL_TOKEN", "").strip()
    if expected and x_af_internal != expected:
        raise HTTPException(status_code=403, detail="forbidden")
    with session_scope() as session:
        known_db = session.get(TenantRow, tenant_id) is not None
    known_env = tenant_id in {r.tenant_id for r in (_ENV_REGISTRY or load_keys_from_env()).values()}
    if not known_db and not known_env:
        raise HTTPException(status_code=404, detail="unknown_tenant")
    root = tenant_root(tenant_id)
    vector = root / "vector"
    return {
        "tenant_id": tenant_id,
        "root": str(root),
        "vector_root": str(vector),
        "chroma_persist_dir": str(vector / "chroma"),
    }


def main() -> None:
    import uvicorn

    host = os.environ.get("AF_HOST", "0.0.0.0")
    port = int(os.environ.get("AF_PORT", "8080"))
    uvicorn.run("main:app", host=host, port=port, factory=False, reload=False)


if __name__ == "__main__":
    main()
