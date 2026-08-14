#!/usr/bin/env python3
"""
Sleep watchdog (Phase 1) — stop idle Docker containers labeled af.plane=data.

Idle = no gateway activity marker newer than --idle-seconds under
  data/tenants/{id}/cache/last_active (unix epoch seconds),
or container label af.last_active if present.

Usage:
  python runtime/sleep-watchdog/watchdog.py --once
  python runtime/sleep-watchdog/watchdog.py --loop --interval 60 --idle-seconds 900

Requires: docker CLI. Does not pad GPU billing — it only stops labeled containers.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def list_tenant_runtimes() -> list[dict]:
    proc = run(
        [
            "docker",
            "ps",
            "--filter",
            "label=af.plane=data",
            "--format",
            "{{json .}}",
        ]
    )
    if proc.returncode != 0:
        print(proc.stderr, file=sys.stderr)
        return []
    out = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        out.append(json.loads(line))
    return out


def last_active_for_tenant(data_root: Path, tenant_id: str) -> float | None:
    # Prefer Redis marker from gateway
    url = os.environ.get("REDIS_URL", "").strip()
    if url:
        try:
            import redis

            r = redis.Redis.from_url(url, decode_responses=True)
            raw = r.get(f"af:last_active:{tenant_id}")
            if raw is not None:
                return float(raw)
        except Exception as exc:
            print(f"redis last_active read failed: {exc}", file=sys.stderr)

    marker = data_root / tenant_id / "cache" / "last_active"
    if not marker.is_file():
        return None
    try:
        return float(marker.read_text(encoding="utf-8").strip())
    except ValueError:
        return None


def stop_container(container_id: str, name: str) -> None:
    print(f"stopping idle runtime: {name} ({container_id[:12]})")
    proc = run(["docker", "stop", container_id])
    if proc.returncode != 0:
        print(proc.stderr, file=sys.stderr)


def tick(data_root: Path, idle_seconds: int, dry_run: bool) -> int:
    now = time.time()
    stopped = 0
    for item in list_tenant_runtimes():
        cid = item.get("ID") or item.get("Id") or ""
        name = item.get("Names") or item.get("names") or cid
        labels = item.get("Labels") or ""
        # docker ps json Labels is comma-separated key=value
        label_map: dict[str, str] = {}
        if isinstance(labels, str):
            for part in labels.split(","):
                if "=" in part:
                    k, v = part.split("=", 1)
                    label_map[k] = v
        elif isinstance(labels, dict):
            label_map = {str(k): str(v) for k, v in labels.items()}

        tenant_id = label_map.get("af.tenant_id")
        if not tenant_id:
            continue
        last = last_active_for_tenant(data_root, tenant_id)
        if last is None:
            # No activity marker yet — treat container StartedAt via inspect if needed;
            # Phase 1: skip stop when unknown (avoid killing freshly started boxes).
            print(f"skip {tenant_id}: no last_active marker")
            continue
        idle = now - last
        if idle < idle_seconds:
            print(f"ok {tenant_id}: idle {int(idle)}s < {idle_seconds}s")
            continue
        if dry_run:
            print(f"dry-run would stop {name} (tenant={tenant_id}, idle={int(idle)}s)")
            continue
        stop_container(cid, str(name))
        stopped += 1
    return stopped


def touch_active(tenant_id: str, data_root: Path | None = None) -> None:
    """Helper for gateway/tests: record activity."""
    root = data_root or Path(os.environ.get("AF_DATA_ROOT", ROOT / "data" / "tenants"))
    path = root / tenant_id / "cache" / "last_active"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(time.time()), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="AF sleep watchdog")
    parser.add_argument("--idle-seconds", type=int, default=int(os.environ.get("AF_SLEEP_IDLE_SECONDS", "900")))
    parser.add_argument("--interval", type=int, default=60)
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--once", action="store_true", default=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--data-root",
        type=Path,
        default=Path(os.environ.get("AF_DATA_ROOT", str(ROOT / "data" / "tenants"))),
    )
    args = parser.parse_args()
    if args.loop:
        args.once = False

    if not args.data_root.is_dir():
        print(f"data root missing: {args.data_root}", file=sys.stderr)

    if args.once and not args.loop:
        tick(args.data_root, args.idle_seconds, args.dry_run)
        return 0

    while True:
        tick(args.data_root, args.idle_seconds, args.dry_run)
        time.sleep(max(5, args.interval))


if __name__ == "__main__":
    raise SystemExit(main())
