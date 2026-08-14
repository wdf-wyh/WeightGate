#!/usr/bin/env python3
"""Phase 4 smoke: Phase 3 paths + hosts / alerts / mirror licenses."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REQUIRED_PATHS = [
    "README.md",
    "docs/architecture.md",
    "docs/tenant-isolation.md",
    "docs/deploy-local.md",
    "docs/deploy-autodl.md",
    "docs/deploy-remote.md",
    "docs/phase1-checklist.md",
    "docs/phase2-checklist.md",
    "docs/phase3-checklist.md",
    "docs/phase4-checklist.md",
    "compose/docker-compose.yml",
    "control-plane/main.py",
    "control-plane/db.py",
    "control-plane/models.py",
    "control-plane/ssh_driver.py",
    "control-plane/alerts.py",
    "control-plane/mirror_catalog.py",
    "control-plane/mirror_install.py",
    "gateway/main.py",
    "gateway/router.py",
    "gateway/vllm_proxy.py",
    "gateway/cloud_proxy.py",
    "gateway/adapter.py",
    "console/README.md",
    "console/package.json",
    "console/src/main.ts",
    "console/src/pages/TenantsPage.vue",
    "console/src/pages/InstancesPage.vue",
    "console/src/pages/UsagePage.vue",
    "console/src/pages/HostsPage.vue",
    "console/src/pages/AlertsPage.vue",
    "console/src/pages/CatalogPage.vue",
    "runtime/ollama/README.md",
    "runtime/ollama/healthcheck.sh",
    "runtime/ollama/healthcheck.ps1",
    "runtime/vllm/README.md",
    "runtime/vllm/start_single_gpu.sh",
    "runtime/vllm/start_single_gpu.ps1",
    "runtime/vllm/start_multi_lora.sh",
    "runtime/vllm/start_multi_lora.ps1",
    "runtime/sleep-watchdog/README.md",
    "runtime/sleep-watchdog/watchdog.py",
    "runtime/remote-agent/README.md",
    "runtime/remote-agent/install.sh",
    "runtime/remote-agent/healthcheck.sh",
    "runtime/remote-agent/start_runtime.sh",
    "templates/model-presets.yaml",
    "templates/tenant-compose.yml.j2",
    "templates/vllm-multi-lora.yml.j2",
    "templates/mirror-catalog.yaml",
    "schemas/openai/chat-completions.request.json",
    "schemas/openai/chat-completions.response.json",
    "schemas/openai/chat-completions.stream-chunk.json",
    "schemas/openai/error.response.json",
    "schemas/openai/models.list.json",
    "packages/contracts/chat.py",
    "packages/tenantkit/fs.py",
    "packages/tenantkit/keys.py",
    "packages/tenantkit/vector.py",
    "examples/law-lora/README.md",
    "examples/law-lora/manifest.yaml",
    "examples/trade-agent/README.md",
    "examples/trade-agent/manifest.yaml",
    "scripts/bootstrap.sh",
    "scripts/bootstrap.ps1",
    "scripts/deep_test.py",
    "scripts/cost_estimate.py",
    "scripts/alert_scan.py",
    "requirements-dev.txt",
    "pyproject.toml",
]

REQUIRED_SERVICES = {"postgres", "redis", "control-plane", "gateway", "ollama", "console"}
REQUIRED_PRESET_KEYS = {"id", "display_name", "params_b", "backend", "quant", "min_vram_gb"}
EXPECTED_PARAM_CLASSES = {7, 14, 27, 32}

KEY_A = "sk-af-tenant-a-devonly"
KEY_B = "sk-af-tenant-b-devonly"


def fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    raise SystemExit(1)


def check_paths() -> None:
    missing = [p for p in REQUIRED_PATHS if not (ROOT / p).exists()]
    if missing:
        fail("missing paths:\n  - " + "\n  - ".join(missing))
    print(f"OK paths ({len(REQUIRED_PATHS)})")


def check_compose() -> None:
    text = (ROOT / "compose/docker-compose.yml").read_text(encoding="utf-8")
    for svc in REQUIRED_SERVICES:
        if f"  {svc}:" not in text:
            fail(f"compose missing service '{svc}'")
    if 'profiles: ["ollama"]' not in text and "profiles: ['ollama']" not in text:
        if "ollama" not in text or "profiles:" not in text:
            fail("compose missing ollama profile")
    if "open-webui" not in text:
        fail("compose missing optional open-webui service")
    if 'profiles: ["console"]' not in text and "profiles: ['console']" not in text:
        if "console:" not in text:
            fail("compose missing console service")
    if "AF_CLOUD_PROVIDER" not in text:
        fail("compose missing AF_CLOUD_PROVIDER")
    print(f"OK compose services ({', '.join(sorted(REQUIRED_SERVICES))}+open-webui)")


def check_schemas() -> None:
    for name in (
        "chat-completions.request.json",
        "chat-completions.response.json",
        "chat-completions.stream-chunk.json",
        "error.response.json",
        "models.list.json",
    ):
        path = ROOT / "schemas/openai" / name
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("type") != "object":
            fail(f"{name}: root type must be object")
        if "properties" not in data:
            fail(f"{name}: missing properties")
    req = json.loads(
        (ROOT / "schemas/openai/chat-completions.request.json").read_text(encoding="utf-8")
    )
    for field in ("model", "messages"):
        if field not in req.get("required", []):
            fail(f"request schema must require '{field}'")
    print("OK openai schemas")


def check_presets() -> None:
    path = ROOT / "templates/model-presets.yaml"
    raw = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore
    except ImportError:
        for key in ("backend:", "quant:", "min_vram_gb:", "params_b:"):
            if key not in raw:
                fail(f"presets missing marker '{key}'")
        for n in EXPECTED_PARAM_CLASSES:
            if f"params_b: {n}" not in raw and f"params_b:{n}" not in raw:
                fail(f"presets missing params_b class {n}")
        print("OK model-presets.yaml (marker check; install PyYAML for full parse)")
        return

    data = yaml.safe_load(raw)
    presets = data.get("presets") or []
    if not presets:
        fail("presets list empty")
    params = set()
    for p in presets:
        missing = REQUIRED_PRESET_KEYS - set(p)
        if missing:
            fail(f"preset {p.get('id')!r} missing keys: {sorted(missing)}")
        if p["backend"] not in {"ollama", "vllm"}:
            fail(f"preset {p['id']}: backend must be ollama|vllm")
        params.add(int(p["params_b"]))
    if not EXPECTED_PARAM_CLASSES.issubset(params):
        fail(f"presets must cover param classes {sorted(EXPECTED_PARAM_CLASSES)}; got {sorted(params)}")
    print(f"OK model-presets.yaml ({len(presets)} presets)")


def check_contracts() -> None:
    try:
        from packages.contracts import (
            ChatCompletionRequest,
            ChatCompletionResponse,
            ErrorResponse,
            ModelListResponse,
        )
    except ImportError as exc:
        fail(f"contracts import failed (pip install -r requirements-dev.txt): {exc}")

    req = ChatCompletionRequest.model_validate(
        {
            "model": "small-7b",
            "messages": [{"role": "user", "content": "ping"}],
            "stream": False,
        }
    )
    if req.model != "small-7b":
        fail("ChatCompletionRequest roundtrip failed")

    ChatCompletionResponse.model_validate(
        {
            "id": "chatcmpl-phase1",
            "object": "chat.completion",
            "created": 0,
            "model": "small-7b",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "pong"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }
    )
    ErrorResponse.model_validate(
        {"error": {"message": "unauthorized", "type": "authentication_error", "code": "invalid_api_key"}}
    )
    ModelListResponse.model_validate(
        {
            "object": "list",
            "data": [{"id": "small-7b", "object": "model", "created": 0, "owned_by": "tenant"}],
        }
    )
    print("OK pydantic contracts")


def check_tenant_isolation_unit() -> None:
    from packages.tenantkit import (
        TENANT_SUBDIRS,
        TenantIsolationError,
        assert_model_allowed_for_tenant,
        ensure_tenant_layout,
        safe_tenant_path,
    )
    from packages.tenantkit.keys import default_dev_keys, resolve_key

    if "vector" not in TENANT_SUBDIRS:
        fail("TENANT_SUBDIRS must include vector")

    keys = {r.api_key: r for r in default_dev_keys()}
    if resolve_key(KEY_A, keys) is None or resolve_key(KEY_B, keys) is None:
        fail("default dual-tenant keys missing")
    if resolve_key(KEY_A, keys).tenant_id == resolve_key(KEY_B, keys).tenant_id:
        fail("tenant A and B must differ")

    with tempfile.TemporaryDirectory() as tmp:
        os.environ["AF_DATA_ROOT"] = tmp
        ensure_tenant_layout("tenant_a")
        ensure_tenant_layout("tenant_b")
        if not (Path(tmp) / "tenant_a" / "vector").is_dir():
            fail("ensure_tenant_layout must create vector/")
        (Path(tmp) / "tenant_b" / "loras" / "secret_b.bin").write_bytes(b"b")
        safe_tenant_path("tenant_a", "loras", "own.txt").write_text("a", encoding="utf-8")
        try:
            safe_tenant_path("tenant_a", "..", "tenant_b", "loras", "secret_b.bin")
            fail("path traversal to tenant_b must raise")
        except TenantIsolationError:
            pass
        try:
            assert_model_allowed_for_tenant("tenant_a", "tenants/tenant_b/loras/secret_b.bin")
            fail("cross-tenant model must raise")
        except TenantIsolationError:
            pass
        assert_model_allowed_for_tenant("tenant_a", "tinyllama")
    print("OK tenant isolation unit")


def check_gateway_auth_isolation() -> None:
    """In-process FastAPI checks with mocked Ollama (no Docker required)."""
    os.environ.pop("CONTROL_PLANE_URL", None)
    os.environ.pop("REDIS_URL", None)
    os.environ.pop("AF_API_KEYS", None)

    with tempfile.TemporaryDirectory() as tmp:
        os.environ["AF_DATA_ROOT"] = tmp
        from packages.tenantkit import ensure_tenant_layout

        ensure_tenant_layout("tenant_a")
        ensure_tenant_layout("tenant_b")
        (Path(tmp) / "tenant_b" / "loras" / "adapter_b.txt").write_text("b-only", encoding="utf-8")
        (Path(tmp) / "tenant_a" / "loras" / "adapter_a.txt").write_text("a-only", encoding="utf-8")

        import importlib

        import gateway.main as gw

        importlib.reload(gw)
        from fastapi.testclient import TestClient

        client = TestClient(gw.app)

        r = client.get("/v1/models")
        if r.status_code != 401:
            fail(f"missing auth should be 401, got {r.status_code}")

        r = client.get("/v1/models", headers={"Authorization": "Bearer sk-af-bogus"})
        if r.status_code != 401:
            fail(f"bad key should be 401, got {r.status_code}")

        r = client.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {KEY_A}"},
            json={
                "model": "tenants/tenant_b/loras/adapter_b.txt",
                "messages": [{"role": "user", "content": "leak"}],
            },
        )
        if r.status_code != 403:
            fail(f"cross-tenant chat should be 403, got {r.status_code}: {r.text}")

        r = client.post(
            "/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {KEY_A}",
                "X-AF-Adapter": "tenants/tenant_b/loras/adapter_b.txt",
            },
            json={
                "model": "tinyllama",
                "messages": [{"role": "user", "content": "leak"}],
            },
        )
        if r.status_code != 403:
            fail(f"cross-tenant adapter header should be 403, got {r.status_code}: {r.text}")

        async def _fake_models():
            class R:
                status_code = 200
                content = b'{"object":"list","data":[]}'

                def json(self):
                    return {"object": "list", "data": []}

            return R()

        gw.forward_models = _fake_models  # type: ignore[assignment]
        r = client.get("/v1/models", headers={"Authorization": f"Bearer {KEY_A}"})
        if r.status_code != 200:
            fail(f"tenant A /v1/models expected 200, got {r.status_code}: {r.text}")
        ids = {m["id"] for m in r.json().get("data", [])}
        if "loras/adapter_b.txt" in ids or any("tenant_b" in i for i in ids):
            fail(f"tenant A saw tenant B adapters: {ids}")
        if "loras/adapter_a.txt" not in ids:
            fail(f"tenant A missing own adapter listing: {ids}")

        r = client.get("/v1/models", headers={"Authorization": f"Bearer {KEY_B}"})
        ids_b = {m["id"] for m in r.json().get("data", [])}
        if "loras/adapter_a.txt" in ids_b:
            fail(f"tenant B saw tenant A adapter: {ids_b}")

        hr = client.get("/health")
        if hr.status_code != 200 or hr.json().get("phase") != "4":
            fail(f"gateway health phase 4 expected: {hr.status_code} {hr.text}")
        if "cloud_provider" not in hr.json() or "night_window" not in hr.json():
            fail(f"gateway health missing cloud/night fields: {hr.json()}")

    print("OK gateway dual-tenant 401/403 isolation")


def check_hybrid_router() -> None:
    from gateway.router import choose_route

    short = {"messages": [{"role": "user", "content": "hi"}]}
    d = choose_route(
        policy_mode="hybrid", short_max_chars=800, payload=short, preset_backend="ollama"
    )
    if d.route != "local":
        fail(f"hybrid short should be local, got {d.route}")

    long_payload = {"messages": [{"role": "user", "content": "x" * 2000}]}
    d = choose_route(
        policy_mode="hybrid",
        short_max_chars=800,
        payload=long_payload,
        preset_backend="vllm",
    )
    if d.route != "vllm":
        fail(f"hybrid long+vllm preset should be vllm, got {d.route}")

    tools = {
        "messages": [{"role": "user", "content": "hi"}],
        "tools": [{"type": "function", "function": {"name": "f"}}],
    }
    d = choose_route(
        policy_mode="hybrid", short_max_chars=800, payload=tools, preset_backend="ollama"
    )
    if d.route != "cloud":
        fail(f"hybrid tools should be cloud, got {d.route}")

    d = choose_route(
        policy_mode="local_only", short_max_chars=800, payload=tools, preset_backend="vllm"
    )
    if d.route != "local":
        fail("local_only must force local")
    d = choose_route(
        policy_mode="cloud_only", short_max_chars=800, payload=short, preset_backend="ollama"
    )
    if d.route != "cloud":
        fail("cloud_only must force cloud")
    print("OK hybrid router rules")


def check_cloud_providers() -> None:
    import gateway.cloud_proxy as cp

    os.environ.pop("AF_CLOUD_BASE_URL", None)
    os.environ.pop("AF_CLOUD_MODEL", None)

    os.environ["AF_CLOUD_PROVIDER"] = "dashscope"
    if "dashscope.aliyuncs.com" not in cp.cloud_base_url():
        fail(f"dashscope base unexpected: {cp.cloud_base_url()}")
    if cp.cloud_model_remap() != "qwen-plus":
        fail(f"dashscope default model: {cp.cloud_model_remap()}")

    os.environ["AF_CLOUD_PROVIDER"] = "deepseek"
    if "deepseek.com" not in cp.cloud_base_url():
        fail(f"deepseek base unexpected: {cp.cloud_base_url()}")
    if cp.cloud_model_remap() != "deepseek-chat":
        fail(f"deepseek default model: {cp.cloud_model_remap()}")

    os.environ["AF_CLOUD_BASE_URL"] = "https://example.compat"
    if cp.cloud_base_url() != "https://example.compat":
        fail(f"base url override failed: {cp.cloud_base_url()}")

    os.environ["AF_CLOUD_NIGHT_START"] = "22:00"
    os.environ["AF_CLOUD_NIGHT_END"] = "08:00"
    cfg = cp.night_window_config()
    if cfg.get("discount") is None or "start" not in cfg:
        fail(f"night_window_config broken: {cfg}")

    from datetime import datetime, timezone

    noon = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    os.environ["AF_CLOUD_NIGHT_TZ"] = "UTC"
    late = datetime(2026, 1, 1, 23, 0, tzinfo=timezone.utc)
    early = datetime(2026, 1, 1, 3, 0, tzinfo=timezone.utc)
    if not cp.is_night_window(late):
        fail("23:00 UTC should be in 22-08 night window")
    if not cp.is_night_window(early):
        fail("03:00 UTC should be in 22-08 night window")
    if cp.is_night_window(noon):
        fail("12:00 UTC should be outside 22-08 night window")

    for k in (
        "AF_CLOUD_PROVIDER",
        "AF_CLOUD_BASE_URL",
        "AF_CLOUD_MODEL",
        "AF_CLOUD_NIGHT_START",
        "AF_CLOUD_NIGHT_END",
        "AF_CLOUD_NIGHT_TZ",
    ):
        os.environ.pop(k, None)
    print("OK cloud multi-provider + night window")


def check_vector_isolation() -> None:
    from packages.tenantkit import LocalVectorStore, ensure_tenant_layout, tenant_vector_dir
    import importlib
    from fastapi.testclient import TestClient

    os.environ.pop("CONTROL_PLANE_URL", None)
    os.environ.pop("REDIS_URL", None)
    os.environ.pop("AF_API_KEYS", None)

    with tempfile.TemporaryDirectory() as tmp:
        os.environ["AF_DATA_ROOT"] = tmp
        ensure_tenant_layout("tenant_a")
        ensure_tenant_layout("tenant_b")
        va = tenant_vector_dir("tenant_a")
        vb = tenant_vector_dir("tenant_b")
        if "tenant_a" not in str(va) or "tenant_b" not in str(vb):
            fail(f"vector dirs not tenant scoped: {va} {vb}")

        store_a = LocalVectorStore("tenant_a", "demo")
        store_a.upsert(ids=["1"], documents=["alpha secret for A only"])
        store_b = LocalVectorStore("tenant_b", "demo")
        hits_b = store_b.query(text="alpha secret", top_k=5)
        if any("A only" in h.document for h in hits_b):
            fail("tenant_b LocalVectorStore saw tenant_a docs")

        import gateway.main as gw

        importlib.reload(gw)
        with TestClient(gw.app) as client:
            up = client.post(
                "/v1/vector/upsert",
                headers={"Authorization": f"Bearer {KEY_A}"},
                json={
                    "collection": "demo",
                    "ids": ["n1"],
                    "documents": ["tenant a note about contracts"],
                },
            )
            if up.status_code != 200:
                fail(f"vector upsert: {up.status_code} {up.text}")
            qa = client.post(
                "/v1/vector/query",
                headers={"Authorization": f"Bearer {KEY_A}"},
                json={"collection": "demo", "query": "contracts", "top_k": 3},
            )
            if qa.status_code != 200 or not qa.json().get("hits"):
                fail(f"tenant_a vector query empty: {qa.status_code} {qa.text}")
            qb = client.post(
                "/v1/vector/query",
                headers={"Authorization": f"Bearer {KEY_B}"},
                json={"collection": "demo", "query": "contracts", "top_k": 3},
            )
            if qb.status_code != 200:
                fail(f"tenant_b vector query status: {qb.status_code}")
            if any("tenant a note" in h.get("document", "") for h in qb.json().get("hits", [])):
                fail("tenant_b queried tenant_a vector data")
            info = client.get("/v1/vector/info", headers={"Authorization": f"Bearer {KEY_A}"})
            if info.status_code != 200 or "vector_root" not in info.json():
                fail(f"vector info: {info.status_code} {info.text}")

    print("OK per-tenant vector isolation")


def check_cost_estimate() -> None:
    import subprocess

    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/cost_estimate.py"),
            "--gpu",
            "rtx4090",
            "--hourly-cny",
            "2",
            "--hours",
            "4",
            "--quant",
            "awq",
            "--json",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        fail(f"cost_estimate failed: {proc.stderr}")
    data = json.loads(proc.stdout)
    if data.get("effective_cost_cny") != 8.0:
        fail(f"cost_estimate unexpected: {data}")
    print("OK cost_estimate.py")


def check_examples_not_stub() -> None:
    law = (ROOT / "examples/law-lora/README.md").read_text(encoding="utf-8")
    trade = (ROOT / "examples/trade-agent/README.md").read_text(encoding="utf-8")
    if "Phase 0 stub" in law:
        fail("law-lora still Phase 0 stub")
    if "X-AF-Adapter" not in law:
        fail("law-lora must document X-AF-Adapter")
    if "/v1/vector" not in trade:
        fail("trade-agent must document vector API")
    if "Phase 0 stub" in trade:
        fail("trade-agent still Phase 0 stub")
    ml = (ROOT / "templates/vllm-multi-lora.yml.j2").read_text(encoding="utf-8")
    if "enable-lora" not in ml and "lora_modules" not in ml:
        fail("vllm-multi-lora template missing lora markers")
    print("OK examples + multi-lora template")


def check_control_plane_phase2() -> None:
    """In-process CP: tenant CRUD, route policy, key hash resolve, cross-tenant 403 via GW."""
    os.environ.pop("CONTROL_PLANE_URL", None)
    os.environ.pop("REDIS_URL", None)
    os.environ.pop("AF_API_KEYS", None)
    os.environ.pop("DATABASE_URL", None)
    os.environ["AF_DOCKER_DRIVER"] = "off"

    with tempfile.TemporaryDirectory() as tmp:
        os.environ["AF_DATA_ROOT"] = tmp
        import importlib
        import sys as _sys

        cp_dir = str(ROOT / "control-plane")
        while cp_dir in _sys.path:
            _sys.path.remove(cp_dir)
        _sys.path.insert(0, cp_dir)
        for name in ("presets", "db", "models", "schemas", "docker_driver", "main"):
            _sys.modules.pop(name, None)

        import db as cp_db

        cp_db.reset_engine_for_tests()
        import main as cp_main

        cp_db.init_db()
        cp_main._ENV_REGISTRY = cp_main.load_keys_from_env()
        cp_main._seed_dev_tenants()

        from fastapi.testclient import TestClient

        with TestClient(cp_main.app) as client:
            hr = client.get("/health")
            if hr.status_code != 200 or hr.json().get("plane") != "control":
                fail(f"CP health failed: {hr.status_code} {hr.text}")
            if hr.json().get("phase") != "4":
                fail(f"CP phase should be 4, got {hr.json()}")

            tenants = client.get("/v1/tenants")
            if tenants.status_code != 200:
                fail(f"list tenants: {tenants.status_code}")
            ids = {t["id"] for t in tenants.json()}
            if "tenant_a" not in ids or "tenant_b" not in ids:
                fail(f"seed tenants missing: {ids}")

            r = client.post("/v1/tenants", json={"id": "tenant_p2", "name": "Phase2"})
            if r.status_code != 201:
                fail(f"create tenant: {r.status_code} {r.text}")
            if not (Path(tmp) / "tenant_p2" / "vector").is_dir():
                fail("create tenant must ensure vector/")

            r = client.put(
                "/v1/tenants/tenant_p2/route-policy",
                json={"mode": "local_only", "short_max_chars": 400},
            )
            if r.status_code != 200 or r.json().get("mode") != "local_only":
                fail(f"route policy: {r.status_code} {r.text}")

            presets = client.get("/v1/presets")
            if presets.status_code != 200 or not presets.json():
                fail("presets empty/fail")

            key_resp = client.post(
                "/v1/tenants/tenant_p2/keys", json={"rpm_limit": 30, "allowed_models": []}
            )
            if key_resp.status_code != 201:
                fail(f"issue key: {key_resp.status_code} {key_resp.text}")
            plaintext = key_resp.json().get("api_key")
            if not plaintext:
                fail("issued key missing plaintext")

            resolved = client.post("/internal/v1/resolve-key", json={"api_key": plaintext})
            if resolved.status_code != 200 or resolved.json().get("tenant_id") != "tenant_p2":
                fail(f"resolve hashed key failed: {resolved.status_code} {resolved.text}")

            env_ok = client.post("/internal/v1/resolve-key", json={"api_key": KEY_A})
            if env_ok.status_code != 200 or env_ok.json().get("tenant_id") != "tenant_a":
                fail("env key resolve fallback broken")

            inst = client.post(
                "/v1/tenants/tenant_p2/instances", json={"preset_id": "small-7b"}
            )
            if inst.status_code != 201:
                fail(f"create instance: {inst.status_code} {inst.text}")
            iid = inst.json()["id"]
            stop = client.post(f"/v1/instances/{iid}/stop")
            if stop.status_code != 200 or stop.json().get("status") != "stopped":
                fail(f"stop instance: {stop.status_code} {stop.text}")
            wake = client.post(f"/v1/instances/{iid}/wake")
            if wake.status_code != 200:
                fail(f"wake instance: {wake.status_code} {wake.text}")

            usage_in = client.post(
                "/internal/v1/usage",
                json={
                    "tenant_id": "tenant_p2",
                    "model": "tinyllama",
                    "prompt_tokens": 3,
                    "completion_tokens": 5,
                    "route": "local",
                    "latency_ms": 12,
                },
            )
            if usage_in.status_code != 201:
                fail(f"usage ingest: {usage_in.status_code} {usage_in.text}")
            usage = client.get("/v1/tenants/tenant_p2/usage")
            if usage.status_code != 200 or usage.json().get("total_events", 0) < 1:
                fail(f"usage query: {usage.status_code} {usage.text}")

            root = client.get("/internal/v1/tenants/tenant_a/root")
            if root.status_code != 200 or "vector_root" not in root.json():
                fail(f"CP tenant root missing vector_root: {root.status_code} {root.text}")

        from packages.tenantkit import ensure_tenant_layout

        ensure_tenant_layout("tenant_a")
        ensure_tenant_layout("tenant_b")
        import gateway.main as gw

        importlib.reload(gw)
        with TestClient(gw.app) as gwc:
            bad = gwc.post(
                "/v1/chat/completions",
                headers={"Authorization": f"Bearer {KEY_A}"},
                json={
                    "model": "tenants/tenant_b/loras/x",
                    "messages": [{"role": "user", "content": "x"}],
                },
            )
            if bad.status_code != 403:
                fail(f"phase2 cross-tenant should be 403, got {bad.status_code}")

    print("OK control-plane Phase 2/3 CRUD/policy/usage + cross-tenant 403")


def check_phase4_hosts_alerts_mirrors() -> None:
    """Hosts (simulated SSH), alerts scan, mirror license activate."""
    os.environ.pop("CONTROL_PLANE_URL", None)
    os.environ.pop("REDIS_URL", None)
    os.environ.pop("AF_API_KEYS", None)
    os.environ.pop("DATABASE_URL", None)
    os.environ.pop("AF_INTERNAL_TOKEN", None)
    os.environ["AF_DOCKER_DRIVER"] = "off"
    os.environ["AF_SSH_DRIVER"] = "off"

    with tempfile.TemporaryDirectory() as tmp:
        os.environ["AF_DATA_ROOT"] = tmp
        import importlib
        import sys as _sys

        cp_dir = str(ROOT / "control-plane")
        while cp_dir in _sys.path:
            _sys.path.remove(cp_dir)
        _sys.path.insert(0, cp_dir)
        for name in (
            "presets",
            "db",
            "models",
            "schemas",
            "docker_driver",
            "ssh_driver",
            "alerts",
            "mirror_catalog",
            "mirror_install",
            "main",
        ):
            _sys.modules.pop(name, None)

        import db as cp_db

        cp_db.reset_engine_for_tests()
        import main as cp_main

        cp_db.init_db()
        cp_main._ENV_REGISTRY = cp_main.load_keys_from_env()
        cp_main._seed_dev_tenants()

        from fastapi.testclient import TestClient

        with TestClient(cp_main.app) as client:
            hr = client.get("/health")
            if hr.status_code != 200 or hr.json().get("phase") != "4":
                fail(f"CP health phase 4: {hr.status_code} {hr.text}")

            host = client.post(
                "/v1/hosts",
                json={
                    "name": "demo-host",
                    "ssh_host": "127.0.0.1",
                    "ssh_user": "ubuntu",
                    "tenant_id": "tenant_a",
                },
            )
            if host.status_code != 201:
                fail(f"create host: {host.status_code} {host.text}")
            host_id = host.json()["id"]

            probe = client.post(f"/v1/hosts/{host_id}/probe")
            if probe.status_code != 200 or probe.json().get("status") not in {
                "simulated",
                "online",
                "offline",
            }:
                fail(f"probe host: {probe.status_code} {probe.text}")

            install = client.post(f"/v1/hosts/{host_id}/install-agent")
            if install.status_code != 200 or install.json().get("status") != "installed":
                fail(f"install agent: {install.status_code} {install.text}")

            inst = client.post(
                "/v1/tenants/tenant_a/instances",
                json={"preset_id": "small-7b", "host_id": host_id},
            )
            if inst.status_code != 201:
                fail(f"remote instance: {inst.status_code} {inst.text}")
            if inst.json().get("host_id") != host_id:
                fail(f"instance missing host_id: {inst.json()}")
            if inst.json().get("status") not in {"running", "created"}:
                fail(f"unexpected remote instance status: {inst.json()}")

            scan = client.post("/v1/alerts/scan")
            if scan.status_code != 200 or "open_total" not in scan.json():
                fail(f"alert scan: {scan.status_code} {scan.text}")

            mirrors = client.get("/v1/mirrors")
            if mirrors.status_code != 200 or len(mirrors.json()) < 2:
                fail(f"mirrors catalog: {mirrors.status_code} {mirrors.text}")
            product = mirrors.json()[0]
            product_id = product["id"]
            slug = product["adapter_slug"]

            lic = client.post(
                f"/v1/mirrors/{product_id}/licenses",
                json={"tenant_id": "tenant_a", "days_valid": 30},
            )
            if lic.status_code != 201 or not lic.json().get("license_key"):
                fail(f"issue license: {lic.status_code} {lic.text}")
            key = lic.json()["license_key"]

            act = client.post("/v1/mirrors/activate", json={"license_key": key})
            if act.status_code != 200 or not act.json().get("activated_at"):
                fail(f"activate license: {act.status_code} {act.text}")

            marker = Path(tmp) / "tenant_a" / "loras" / slug / "adapter_config.json"
            if not marker.is_file():
                fail(f"license activate did not write marker: {marker}")

            listed = client.get("/v1/tenants/tenant_a/licenses")
            if listed.status_code != 200 or not listed.json():
                fail(f"list licenses: {listed.status_code} {listed.text}")

    print("OK phase4 hosts/alerts/mirrors")


def main() -> None:
    print(f"smoke root: {ROOT}")
    check_paths()
    check_compose()
    check_schemas()
    check_presets()
    check_contracts()
    check_tenant_isolation_unit()
    check_gateway_auth_isolation()
    check_hybrid_router()
    check_cloud_providers()
    check_vector_isolation()
    check_cost_estimate()
    check_examples_not_stub()
    check_control_plane_phase2()
    check_phase4_hosts_alerts_mirrors()
    print("SMOKE PASS (Phase 4)")


if __name__ == "__main__":
    main()
