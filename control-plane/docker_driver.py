"""Local Docker Compose driver for tenant instances (best-effort)."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from jinja2 import Template

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "tenant-compose.yml.j2"


def _docker_available() -> bool:
    if os.environ.get("AF_DOCKER_DRIVER", "auto") == "off":
        return False
    return shutil.which("docker") is not None


def render_tenant_compose(
    *,
    tenant_id: str,
    preset_id: str,
    backend: str,
    data_root: str,
) -> str:
    runtime_image = (
        os.environ.get("AF_VLLM_IMAGE", "vllm/vllm-openai:latest")
        if backend == "vllm"
        else os.environ.get("AF_OLLAMA_IMAGE", "ollama/ollama:latest")
    )
    text = TEMPLATE.read_text(encoding="utf-8")
    return Template(text).render(
        tenant_id=tenant_id,
        runtime_image=runtime_image,
        model_preset_id=preset_id,
        data_root=data_root,
    )


def project_name(tenant_id: str, instance_id: str) -> str:
    # docker compose project names: lowercase, limited charset
    safe = f"af-{tenant_id}-{instance_id}"[:50].lower().replace("_", "-")
    return "".join(c if c.isalnum() or c == "-" else "-" for c in safe)


def start_instance(
    *,
    tenant_id: str,
    instance_id: str,
    preset_id: str,
    backend: str,
) -> tuple[str, str]:
    """
    Returns (status, note).
    status: running | created (simulated when docker unavailable)
    """
    data_root = os.environ.get("AF_DATA_ROOT", str(ROOT / "data" / "tenants"))
    compose_body = render_tenant_compose(
        tenant_id=tenant_id,
        preset_id=preset_id,
        backend=backend,
        data_root=data_root,
    )
    proj = project_name(tenant_id, instance_id)
    if not _docker_available():
        return "created", "docker unavailable; instance recorded only (simulated)"

    work = Path(tempfile.mkdtemp(prefix=f"af-compose-{proj}-"))
    compose_file = work / "docker-compose.yml"
    # Wrap fragment as a valid compose file
    compose_file.write_text(f"name: {proj}\n{compose_body}", encoding="utf-8")
    try:
        proc = subprocess.run(
            ["docker", "compose", "-f", str(compose_file), "-p", proj, "up", "-d"],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(work),
        )
        if proc.returncode != 0:
            return "created", f"compose up failed: {(proc.stderr or proc.stdout)[:400]}"
        return "running", f"compose project {proj}"
    except Exception as exc:  # noqa: BLE001
        return "created", f"compose error: {exc}"


def stop_instance(compose_project: str | None) -> tuple[str, str]:
    if not compose_project:
        return "stopped", "no compose project"
    if not _docker_available():
        return "stopped", "docker unavailable; marked stopped"
    try:
        proc = subprocess.run(
            ["docker", "compose", "-p", compose_project, "stop"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if proc.returncode != 0:
            return "stopped", f"compose stop warn: {(proc.stderr or '')[:200]}"
        return "stopped", f"stopped {compose_project}"
    except Exception as exc:  # noqa: BLE001
        return "stopped", f"stop error: {exc}"


def wake_instance(
    *,
    tenant_id: str,
    instance_id: str,
    preset_id: str,
    backend: str,
    compose_project: str | None,
) -> tuple[str, str]:
    if compose_project and _docker_available():
        try:
            proc = subprocess.run(
                ["docker", "compose", "-p", compose_project, "start"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if proc.returncode == 0:
                return "running", f"woke {compose_project}"
        except Exception:
            pass
    return start_instance(
        tenant_id=tenant_id,
        instance_id=instance_id,
        preset_id=preset_id,
        backend=backend,
    )
