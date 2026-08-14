"""Alert scanner: instance down, quota near-exhaustion, disk pressure (Phase 4)."""

from __future__ import annotations

import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from packages.tenantkit import data_root, tenant_root
from packages.tenantkit.keys import hash_api_key

AlertKind = str  # instance_down | quota_exhausted | disk_low


@dataclass
class AlertDraft:
    kind: AlertKind
    severity: str  # info | warn | critical
    tenant_id: str | None
    resource_id: str | None
    message: str


def _disk_usage_ratio(path: Path) -> tuple[float, int, int]:
    """Return (used_ratio 0..1, free_bytes, total_bytes) for the volume containing path."""
    path.mkdir(parents=True, exist_ok=True)
    usage = shutil.disk_usage(path)
    used_ratio = 1.0 - (usage.free / usage.total) if usage.total else 0.0
    return used_ratio, usage.free, usage.total


def scan_disk(*, warn_ratio: float | None = None) -> list[AlertDraft]:
    ratio_limit = warn_ratio
    if ratio_limit is None:
        ratio_limit = float(os.environ.get("AF_DISK_WARN_RATIO", "0.90"))
    free_min = int(os.environ.get("AF_DISK_WARN_FREE_BYTES", str(2 * 1024**3)))  # 2 GiB
    out: list[AlertDraft] = []
    root = data_root()
    used_ratio, free_b, total_b = _disk_usage_ratio(root)
    if used_ratio >= ratio_limit or free_b <= free_min:
        out.append(
            AlertDraft(
                kind="disk_low",
                severity="critical" if used_ratio >= 0.95 or free_b < 512 * 1024**2 else "warn",
                tenant_id=None,
                resource_id=str(root),
                message=(
                    f"data root disk pressure: used={used_ratio:.1%} "
                    f"free={free_b // (1024**2)}MiB total={total_b // (1024**2)}MiB"
                ),
            )
        )
    # Per-tenant log dir growth (best-effort size of tenant tree)
    if root.is_dir():
        for child in root.iterdir():
            if not child.is_dir() or child.name.startswith("_"):
                continue
            try:
                size = sum(p.stat().st_size for p in child.rglob("*") if p.is_file())
            except OSError:
                continue
            soft = int(os.environ.get("AF_TENANT_DISK_SOFT_BYTES", str(20 * 1024**3)))
            if size >= soft:
                out.append(
                    AlertDraft(
                        kind="disk_low",
                        severity="warn",
                        tenant_id=child.name,
                        resource_id=str(child),
                        message=f"tenant data size {size // (1024**2)}MiB >= soft limit",
                    )
                )
    return out


def scan_instances_rows(rows: list) -> list[AlertDraft]:
    out: list[AlertDraft] = []
    stale_sec = int(os.environ.get("AF_INSTANCE_STALE_SECONDS", "3600"))
    now = time.time()
    for row in rows:
        status = getattr(row, "status", "")
        if status in {"error", "failed"}:
            out.append(
                AlertDraft(
                    kind="instance_down",
                    severity="critical",
                    tenant_id=row.tenant_id,
                    resource_id=row.id,
                    message=f"instance {row.id} status={status}: {getattr(row, 'note', '') or ''}",
                )
            )
            continue
        if status == "running":
            updated = getattr(row, "updated_at", None)
            if updated is not None:
                ts = updated.timestamp() if hasattr(updated, "timestamp") else now
                # Also check tenant last_active file
                last_active_path = tenant_root(row.tenant_id) / "cache" / "last_active"
                last_ts = ts
                if last_active_path.is_file():
                    try:
                        last_ts = float(last_active_path.read_text(encoding="utf-8").strip())
                    except (OSError, ValueError):
                        pass
                # Only alert if host-bound remote and no activity for a long time while "running"
                # For local simulated, skip unless AF_ALERT_STRICT=1
                if os.environ.get("AF_ALERT_STRICT", "0") == "1" and (now - last_ts) > stale_sec:
                    out.append(
                        AlertDraft(
                            kind="instance_down",
                            severity="warn",
                            tenant_id=row.tenant_id,
                            resource_id=row.id,
                            message=f"instance {row.id} running but idle >{stale_sec}s",
                        )
                    )
            note = (getattr(row, "note", None) or "").lower()
            if "failed" in note or "error" in note:
                out.append(
                    AlertDraft(
                        kind="instance_down",
                        severity="critical",
                        tenant_id=row.tenant_id,
                        resource_id=row.id,
                        message=f"instance {row.id} note indicates failure: {row.note}",
                    )
                )
    return out


def scan_quota(session_rows: list, redis_client=None) -> list[AlertDraft]:
    """
    Near-exhaustion when Redis ZCARD for af:rpm:{tenant} is >= 90% of rpm_limit.
    Fail-open when Redis missing (no alert).
    """
    out: list[AlertDraft] = []
    if redis_client is None:
        return out
    # Dedupe by tenant: use max rpm across keys
    by_tenant: dict[str, int] = {}
    for row in session_rows:
        if getattr(row, "revoked_at", None) is not None:
            continue
        tid = row.tenant_id
        by_tenant[tid] = max(by_tenant.get(tid, 0), int(row.rpm_limit))

    for tid, limit in by_tenant.items():
        if limit <= 0:
            continue
        try:
            count = int(redis_client.zcard(f"af:rpm:{tid}") or 0)
        except Exception:  # noqa: BLE001
            continue
        if count >= int(limit * 0.9):
            out.append(
                AlertDraft(
                    kind="quota_exhausted",
                    severity="critical" if count >= limit else "warn",
                    tenant_id=tid,
                    resource_id=f"rpm:{tid}",
                    message=f"RPM window usage {count}/{limit} for tenant {tid}",
                )
            )
    return out


def post_webhook(drafts: list[AlertDraft]) -> None:
    url = os.environ.get("AF_ALERT_WEBHOOK_URL", "").strip()
    if not url or not drafts:
        return
    try:
        import httpx

        httpx.post(
            url,
            json={
                "source": "automatic-funicular",
                "alerts": [
                    {
                        "kind": d.kind,
                        "severity": d.severity,
                        "tenant_id": d.tenant_id,
                        "resource_id": d.resource_id,
                        "message": d.message,
                    }
                    for d in drafts
                ],
            },
            timeout=10.0,
        )
    except Exception:
        pass


def fingerprint(draft: AlertDraft) -> str:
    raw = f"{draft.kind}|{draft.tenant_id}|{draft.resource_id}|{draft.message}"
    return hash_api_key(raw)[:32]
