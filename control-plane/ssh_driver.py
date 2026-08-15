"""SSH remote-host provider for customer-owned machines (Phase 4).

Uses system ``ssh``/``scp`` when available. Set ``AF_SSH_DRIVER=off`` (default in
``.env.example``) to record-only / simulate — never pads GPU cost on the seller side.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / "runtime" / "remote-agent"


@dataclass(frozen=True)
class HostEndpoint:
    host: str
    port: int
    user: str
    identity_file: str | None = None


def _ssh_enabled() -> bool:
    if os.environ.get("AF_SSH_DRIVER", "off").strip().lower() in {"0", "false", "off", "no"}:
        return False
    return shutil.which("ssh") is not None


def _ssh_base_args(ep: HostEndpoint) -> list[str]:
    args = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-o",
        f"ConnectTimeout={os.environ.get('AF_SSH_CONNECT_TIMEOUT', '8')}",
        "-p",
        str(ep.port),
    ]
    if ep.identity_file:
        args.extend(["-i", ep.identity_file])
    args.append(f"{ep.user}@{ep.host}")
    return args


def probe_host(ep: HostEndpoint) -> tuple[str, str]:
    """
    Returns (status, note).
    status: online | offline | simulated
    """
    if not _ssh_enabled():
        return "simulated", "AF_SSH_DRIVER off or ssh binary missing; probe simulated"
    cmd = [*_ssh_base_args(ep), "echo", "af-ok"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        if proc.returncode == 0 and "af-ok" in (proc.stdout or ""):
            return "online", "ssh probe ok"
        err = (proc.stderr or proc.stdout or "")[:300]
        return "offline", f"ssh probe failed: {err}"
    except Exception as exc:  # noqa: BLE001
        return "offline", f"ssh probe error: {exc}"


def remote_run(ep: HostEndpoint, remote_command: str, timeout: int = 120) -> tuple[int, str, str]:
    if not _ssh_enabled():
        return 0, f"[simulated] {remote_command}", ""
    cmd = [*_ssh_base_args(ep), remote_command]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return proc.returncode, proc.stdout or "", proc.stderr or ""
    except Exception as exc:  # noqa: BLE001
        return 1, "", str(exc)


def install_remote_agent(ep: HostEndpoint, *, remote_dir: str | None = None) -> tuple[str, str]:
    """Copy remote-agent scripts and run healthcheck on the customer host."""
    target = remote_dir or os.environ.get("AF_REMOTE_AGENT_DIR", "~/weightgate-agent")
    if not _ssh_enabled():
        return (
            "installed",
            f"simulated agent install at {target} (enable AF_SSH_DRIVER=on for real SSH)",
        )

    health = AGENT_DIR / "healthcheck.sh"
    install = AGENT_DIR / "install.sh"
    if not health.exists() or not install.exists():
        return "error", "remote-agent scripts missing in repo"

    # Ensure remote directory, then scp scripts
    code, _, err = remote_run(ep, f"mkdir -p {target}")
    if code != 0:
        return "error", f"mkdir failed: {err[:200]}"

    scp = shutil.which("scp")
    if scp is None:
        return "error", "scp binary missing"

    scp_args = [scp, "-P", str(ep.port), "-o", "BatchMode=yes"]
    if ep.identity_file:
        scp_args.extend(["-i", ep.identity_file])
    for name in ("install.sh", "healthcheck.sh", "start_runtime.sh"):
        local = AGENT_DIR / name
        if not local.exists():
            continue
        dest = f"{ep.user}@{ep.host}:{target}/{name}"
        try:
            proc = subprocess.run(
                [*scp_args, str(local), dest],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if proc.returncode != 0:
                return "error", f"scp {name} failed: {(proc.stderr or '')[:200]}"
        except Exception as exc:  # noqa: BLE001
            return "error", f"scp error: {exc}"

    code, out, err = remote_run(ep, f"chmod +x {target}/*.sh && {target}/healthcheck.sh")
    if code != 0:
        return "error", f"healthcheck failed: {(err or out)[:300]}"
    return "installed", f"agent ready at {target}"


def start_remote_runtime(
    ep: HostEndpoint,
    *,
    tenant_id: str,
    instance_id: str,
    preset_id: str,
    backend: str,
) -> tuple[str, str]:
    """Ask remote agent to start a runtime for this tenant instance."""
    if not _ssh_enabled():
        return (
            "running",
            f"simulated remote {backend} on {ep.user}@{ep.host} "
            f"(tenant={tenant_id} inst={instance_id} preset={preset_id})",
        )
    target = os.environ.get("AF_REMOTE_AGENT_DIR", "~/weightgate-agent")
    cmd = (
        f"{target}/start_runtime.sh "
        f"--tenant {tenant_id} --instance {instance_id} "
        f"--preset {preset_id} --backend {backend}"
    )
    code, out, err = remote_run(ep, cmd, timeout=180)
    if code != 0:
        return "created", f"remote start failed: {(err or out)[:300]}"
    return "running", (out or f"remote {backend} started")[:400]


def stop_remote_runtime(ep: HostEndpoint, *, instance_id: str) -> tuple[str, str]:
    if not _ssh_enabled():
        return "stopped", f"simulated remote stop {instance_id} on {ep.host}"
    target = os.environ.get("AF_REMOTE_AGENT_DIR", "~/weightgate-agent")
    code, out, err = remote_run(
        ep,
        f"{target}/start_runtime.sh --stop --instance {instance_id}",
        timeout=60,
    )
    if code != 0:
        return "stopped", f"remote stop warn: {(err or out)[:200]}"
    return "stopped", f"remote stopped {instance_id}"
