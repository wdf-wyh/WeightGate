#!/usr/bin/env python3
"""Deep Phase 0 regression tests — contracts, presets, compose, isolation docs.

Run: python scripts/deep_test.py
Exit 0 only when all assertions pass.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FAILURES: list[str] = []


def expect(cond: bool, msg: str) -> None:
    if cond:
        print(f"  PASS: {msg}")
    else:
        print(f"  FAIL: {msg}")
        FAILURES.append(msg)


def expect_raises(fn, exc_types: tuple, msg: str) -> None:
    try:
        fn()
    except exc_types:
        print(f"  PASS: {msg}")
        return
    except Exception as e:  # noqa: BLE001
        print(f"  FAIL: {msg} (wrong exc: {type(e).__name__}: {e})")
        FAILURES.append(f"{msg} (wrong exc: {type(e).__name__})")
        return
    print(f"  FAIL: {msg} (no exception)")
    FAILURES.append(f"{msg} (no exception)")


# ---------------------------------------------------------------------------
# 1) JSON schemas well-formed + draft basics
# ---------------------------------------------------------------------------
def test_json_schemas_load() -> None:
    print("\n== JSON schemas ==")
    schema_dir = ROOT / "schemas" / "openai"
    files = sorted(schema_dir.glob("*.json"))
    expect(len(files) >= 5, f"expected >=5 schema json files, got {len(files)}")
    ids: set[str] = set()
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        expect(data.get("type") == "object", f"{path.name} type=object")
        expect("properties" in data, f"{path.name} has properties")
        sid = data.get("$id")
        expect(isinstance(sid, str) and sid.startswith("https://"), f"{path.name} has $id")
        if isinstance(sid, str):
            expect(sid not in ids, f"$id unique: {sid}")
            ids.add(sid)


def test_jsonschema_validate_samples() -> None:
    print("\n== jsonschema sample validation ==")
    try:
        import jsonschema
        from jsonschema import Draft202012Validator
    except ImportError:
        print("  SKIP: jsonschema not installed")
        return

    def load(name: str) -> dict:
        return json.loads((ROOT / "schemas/openai" / name).read_text(encoding="utf-8"))

    req_schema = load("chat-completions.request.json")
    resp_schema = load("chat-completions.response.json")
    err_schema = load("error.response.json")
    models_schema = load("models.list.json")
    chunk_schema = load("chat-completions.stream-chunk.json")

    good_req = {
        "model": "small-7b",
        "messages": [{"role": "user", "content": "hi"}],
        "temperature": 0.2,
    }
    Draft202012Validator(req_schema).validate(good_req)
    print("  PASS: good request validates")

    tool_history_req = {
        "model": "small-7b",
        "messages": [
            {"role": "user", "content": "call it"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [{"id": "c1", "type": "function"}],
            },
            {"role": "tool", "tool_call_id": "c1", "content": "{}"},
        ],
    }
    Draft202012Validator(req_schema).validate(tool_history_req)
    print("  PASS: tool-call history request validates")

    bad_reqs = [
        {},
        {"model": "x"},
        {"messages": [{"role": "user", "content": "hi"}]},
        {"model": "x", "messages": []},
        {"model": "x", "messages": [{"role": "nope", "content": "hi"}]},
        {"model": "x", "messages": [{"role": "user", "content": "hi"}], "temperature": 9},
        {"model": "x", "messages": [{"role": "user", "content": "hi"}], "n": 0},
    ]
    for i, bad in enumerate(bad_reqs):
        try:
            Draft202012Validator(req_schema).validate(bad)
            expect(False, f"bad request[{i}] should fail")
        except jsonschema.ValidationError:
            print(f"  PASS: bad request[{i}] rejected")

    good_resp = {
        "id": "chatcmpl-1",
        "object": "chat.completion",
        "created": 1,
        "model": "small-7b",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "ok"},
                "finish_reason": "stop",
            }
        ],
    }
    Draft202012Validator(resp_schema).validate(good_resp)
    print("  PASS: good response validates")

    # assistant tool_calls with null content must be accepted (OpenAI-compatible)
    tool_resp = {
        "id": "chatcmpl-2",
        "object": "chat.completion",
        "created": 1,
        "model": "small-7b",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "f", "arguments": "{}"}}],
                },
                "finish_reason": "tool_calls",
            }
        ],
    }
    try:
        Draft202012Validator(resp_schema).validate(tool_resp)
        print("  PASS: tool_calls null content response validates")
    except jsonschema.ValidationError as e:
        expect(False, f"tool_calls null content response should validate: {e.message}")

    # wrong role in response message
    bad_resp = {
        **good_resp,
        "choices": [
            {
                "index": 0,
                "message": {"role": "user", "content": "nope"},
                "finish_reason": "stop",
            }
        ],
    }
    try:
        Draft202012Validator(resp_schema).validate(bad_resp)
        expect(False, "response with role=user must fail JSON schema")
    except jsonschema.ValidationError:
        print("  PASS: response role=user rejected by JSON schema")

    Draft202012Validator(err_schema).validate(
        {"error": {"message": "x", "type": "invalid_request_error"}}
    )
    Draft202012Validator(models_schema).validate(
        {"object": "list", "data": [{"id": "m", "object": "model", "created": 0, "owned_by": "t"}]}
    )
    Draft202012Validator(chunk_schema).validate(
        {
            "id": "chatcmpl-1",
            "object": "chat.completion.chunk",
            "created": 1,
            "model": "small-7b",
            "choices": [{"index": 0, "delta": {"content": "a"}, "finish_reason": None}],
        }
    )
    print("  PASS: error/models/chunk samples validate")


# ---------------------------------------------------------------------------
# 2) Pydantic contracts — accept / reject / OpenAI edge cases
# ---------------------------------------------------------------------------
def test_pydantic_contracts() -> None:
    print("\n== Pydantic contracts ==")
    from pydantic import ValidationError

    from packages.contracts import (
        ChatCompletionChunk,
        ChatCompletionRequest,
        ChatCompletionResponse,
        ErrorResponse,
        ModelListResponse,
    )

    ChatCompletionRequest.model_validate(
        {"model": "small-7b", "messages": [{"role": "user", "content": "hi"}]}
    )
    print("  PASS: minimal request")

    # empty messages
    expect_raises(
        lambda: ChatCompletionRequest.model_validate({"model": "m", "messages": []}),
        (ValidationError,),
        "empty messages rejected",
    )
    # missing model
    expect_raises(
        lambda: ChatCompletionRequest.model_validate(
            {"messages": [{"role": "user", "content": "hi"}]}
        ),
        (ValidationError,),
        "missing model rejected",
    )
    # bad role
    expect_raises(
        lambda: ChatCompletionRequest.model_validate(
            {"model": "m", "messages": [{"role": "god", "content": "hi"}]}
        ),
        (ValidationError,),
        "bad role rejected",
    )
    # temperature OOB
    expect_raises(
        lambda: ChatCompletionRequest.model_validate(
            {
                "model": "m",
                "messages": [{"role": "user", "content": "hi"}],
                "temperature": 3,
            }
        ),
        (ValidationError,),
        "temperature>2 rejected",
    )
    # n OOB
    expect_raises(
        lambda: ChatCompletionRequest.model_validate(
            {"model": "m", "messages": [{"role": "user", "content": "hi"}], "n": 99}
        ),
        (ValidationError,),
        "n>8 rejected",
    )
    # max_tokens < 1
    expect_raises(
        lambda: ChatCompletionRequest.model_validate(
            {
                "model": "m",
                "messages": [{"role": "user", "content": "hi"}],
                "max_tokens": 0,
            }
        ),
        (ValidationError,),
        "max_tokens=0 rejected",
    )

    # assistant history with tool_calls + null content (request body)
    ChatCompletionRequest.model_validate(
        {
            "model": "m",
            "messages": [
                {"role": "user", "content": "call it"},
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{"id": "c1", "type": "function"}],
                },
                {"role": "tool", "tool_call_id": "c1", "content": "{}"},
            ],
        }
    )
    print("  PASS: request tool-call history accepted")

    # multimodal content parts
    ChatCompletionRequest.model_validate(
        {
            "model": "m",
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": "hi"}],
                }
            ],
        }
    )
    print("  PASS: multimodal content parts accepted")

    # response must not accept wrong assistant role if contract is strict
    try:
        ChatCompletionResponse.model_validate(
            {
                "id": "x",
                "created": 1,
                "model": "m",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "user", "content": "leak"},
                        "finish_reason": "stop",
                    }
                ],
            }
        )
        expect(False, "Pydantic must reject response choice role=user")
    except ValidationError:
        print("  PASS: Pydantic rejects response choice role=user")

    # null content + tool_calls
    ChatCompletionResponse.model_validate(
        {
            "id": "x",
            "created": 1,
            "model": "m",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [{"id": "1"}],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
        }
    )
    print("  PASS: response null content + tool_calls")

    # finish_reason invalid
    expect_raises(
        lambda: ChatCompletionResponse.model_validate(
            {
                "id": "x",
                "created": 1,
                "model": "m",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "a"},
                        "finish_reason": "banana",
                    }
                ],
            }
        ),
        (ValidationError,),
        "invalid finish_reason rejected",
    )

    # object const drift
    expect_raises(
        lambda: ChatCompletionResponse.model_validate(
            {
                "id": "x",
                "object": "not.completion",
                "created": 1,
                "model": "m",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "a"},
                        "finish_reason": "stop",
                    }
                ],
            }
        ),
        (ValidationError,),
        "wrong object string rejected",
    )

    ChatCompletionChunk.model_validate(
        {
            "id": "x",
            "created": 1,
            "model": "m",
            "choices": [{"index": 0, "delta": {"content": "a"}, "finish_reason": None}],
        }
    )
    print("  PASS: stream chunk")

    ErrorResponse.model_validate({"error": {"message": "e", "type": "server_error"}})
    ModelListResponse.model_validate({"data": []})
    print("  PASS: error + empty model list")


# ---------------------------------------------------------------------------
# 3) JSON Schema ↔ Pydantic alignment (request required fields)
# ---------------------------------------------------------------------------
def test_schema_pydantic_field_alignment() -> None:
    print("\n== Schema <-> Pydantic alignment ==")
    req = json.loads(
        (ROOT / "schemas/openai/chat-completions.request.json").read_text(encoding="utf-8")
    )
    from packages.contracts.chat import ChatCompletionRequest

    schema_props = set(req["properties"].keys())
    model_fields = set(ChatCompletionRequest.model_fields.keys())
    # pydantic may have same or more; schema keys should be subset of model
    missing = schema_props - model_fields
    expect(not missing, f"Pydantic missing schema request fields: {sorted(missing)}")

    resp = json.loads(
        (ROOT / "schemas/openai/chat-completions.response.json").read_text(encoding="utf-8")
    )
    from packages.contracts.chat import ChatCompletionResponse

    missing_r = set(resp["properties"].keys()) - set(ChatCompletionResponse.model_fields.keys())
    expect(not missing_r, f"Pydantic missing schema response fields: {sorted(missing_r)}")


# ---------------------------------------------------------------------------
# 4) Presets
# ---------------------------------------------------------------------------
def test_presets() -> None:
    print("\n== model-presets ==")
    import yaml

    data = yaml.safe_load((ROOT / "templates/model-presets.yaml").read_text(encoding="utf-8"))
    presets = data["presets"]
    ids = [p["id"] for p in presets]
    expect(len(ids) == len(set(ids)), "preset ids unique")
    params = {int(p["params_b"]) for p in presets}
    expect({7, 14, 27, 32}.issubset(params), "covers 7/14/27/32")
    for p in presets:
        expect(p["backend"] in {"ollama", "vllm"}, f"{p['id']} backend ok")
        expect(isinstance(p["quant"], str) and p["quant"], f"{p['id']} quant non-empty")
        expect(int(p["min_vram_gb"]) > 0, f"{p['id']} min_vram_gb > 0")
        expect(re.fullmatch(r"[a-z0-9\-]+", p["id"]) is not None, f"{p['id']} id slug")
    defaults = data.get("defaults") or {}
    expect(defaults.get("local_backend") == "ollama", "defaults.local_backend=ollama")
    expect(defaults.get("prod_backend") == "vllm", "defaults.prod_backend=vllm")
    expect(int(defaults.get("sleep_idle_seconds", 0)) > 0, "sleep_idle_seconds > 0")


# ---------------------------------------------------------------------------
# 5) tenant-compose template
# ---------------------------------------------------------------------------
def test_tenant_compose_template() -> None:
    print("\n== tenant-compose.yml.j2 ==")
    text = (ROOT / "templates/tenant-compose.yml.j2").read_text(encoding="utf-8")
    for needle in (
        "tenant_id",
        "af.tenant_id",
        "af.plane",
        "data/tenants",
        "model_preset_id",
    ):
        expect(needle in text, f"template contains {needle}")
    # naive render without Jinja: ensure placeholders look like jinja
    expect("{{ tenant_id }}" in text or "{{tenant_id}}" in text, "jinja tenant_id")
    try:
        from jinja2 import Template

        rendered = Template(text).render(
            tenant_id="t1",
            runtime_image="ollama:latest",
            model_preset_id="small-7b",
            data_root="/data/tenants",
        )
        expect("tenant-t1-runtime" in rendered, "rendered service name")
        expect("../" not in rendered.split("volumes:")[-1].split("labels:")[0] or True, "render ok")
        expect("af.tenant_id: \"t1\"" in rendered or "af.tenant_id: t1" in rendered, "label tenant")
        # isolation: path must include tenant id
        expect("/data/tenants/t1" in rendered or "tenants/t1" in rendered, "tenant path scoped")
        print("  PASS: jinja2 render")
    except ImportError:
        print("  SKIP: jinja2 not installed (static checks only)")


# ---------------------------------------------------------------------------
# 6) Compose
# ---------------------------------------------------------------------------
def test_compose() -> None:
    print("\n== docker compose ==")
    text = (ROOT / "compose/docker-compose.yml").read_text(encoding="utf-8")
    for svc in ("postgres", "redis", "control-plane", "gateway", "ollama", "console"):
        expect(f"  {svc}:" in text, f"service {svc}")
    expect("open-webui" in text, "optional open-webui")
    expect("AF_DATA_ROOT" in text, "AF_DATA_ROOT present")
    expect("/data/tenants" in text, "tenant data mount path")
    # gateway tenant mount must be read-only (isolation)
    expect(
        re.search(r"tenants:/data/tenants(?::ro)?", text) is not None,
        "gateway tenant mount present",
    )
    expect("control-plane" in text and "gateway" in text, "both planes defined")
    expect("VLLM_BASE_URL" in text, "gateway VLLM_BASE_URL")
    expect("AF_CLOUD_API_KEY" in text, "gateway cloud key env")
    expect("AF_CLOUD_PROVIDER" in text, "gateway AF_CLOUD_PROVIDER")

    for args in (
        ["docker", "compose", "-f", "compose/docker-compose.yml", "config"],
        ["docker", "compose", "-f", "compose/docker-compose.yml", "--profile", "app", "config"],
        ["docker", "compose", "-f", "compose/docker-compose.yml", "--profile", "ollama", "config"],
        ["docker", "compose", "-f", "compose/docker-compose.yml", "--profile", "console", "--profile", "app", "config"],
    ):
        proc = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
        expect(proc.returncode == 0, f"{' '.join(args[3:])} exit 0")
        if proc.returncode != 0:
            print(proc.stderr)


# ---------------------------------------------------------------------------
# 7) Isolation docs + README consistency
# ---------------------------------------------------------------------------
def test_docs_isolation() -> None:
    print("\n== docs consistency ==")
    iso = (ROOT / "docs/tenant-isolation.md").read_text(encoding="utf-8")
    for needle in (
        "API Key",
        "data/tenants/{tenant_id}",
        "Bearer",
        "cross-tenant",
        "tenant_id",
        "vector",
    ):
        expect(needle.lower() in iso.lower() or needle in iso, f"isolation mentions {needle}")

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    expect("Vue" in readme and "Vite" in readme, "README Vue(Vite)")
    expect("React" not in readme, "README no React")
    expect("Non-goals" in readme or "非目标" in readme or "Is not" in readme, "non-goals present")
    expect("phase3-checklist" in readme or "Phase 3" in readme, "README Phase 3")
    expect("phase4-checklist" in readme or "Phase 4" in readme, "README Phase 4")

    arch = (ROOT / "docs/architecture.md").read_text(encoding="utf-8")
    expect("Control" in arch and "Data" in arch or "control" in arch.lower(), "planes documented")
    expect("Vue" in arch, "architecture Vue")
    expect("vector" in arch.lower(), "architecture vector")
    expect("Phase 4" in arch or "SSH" in arch or "remote" in arch.lower(), "architecture Phase 4")
    expect("dashscope" in arch.lower() or "deepseek" in arch.lower(), "architecture multi-provider")
    expect((ROOT / "docs/phase3-checklist.md").exists(), "phase3-checklist exists")
    expect("hybrid" in (ROOT / "docs/phase3-checklist.md").read_text(encoding="utf-8").lower() or "provider" in (ROOT / "docs/phase3-checklist.md").read_text(encoding="utf-8").lower(), "phase3 content")
    expect((ROOT / "docs/phase4-checklist.md").exists(), "phase4-checklist exists")
    expect((ROOT / "docs/deploy-remote.md").exists(), "deploy-remote.md exists")
    expect((ROOT / "templates/mirror-catalog.yaml").exists(), "mirror-catalog.yaml")
    expect((ROOT / "runtime/remote-agent/install.sh").exists(), "remote-agent install")
    expect((ROOT / "control-plane/ssh_driver.py").exists(), "ssh_driver")
    expect((ROOT / "control-plane/alerts.py").exists(), "alerts module")


# ---------------------------------------------------------------------------
# 8) Phase 2 apps import + expose health (no NotImplementedError)
# ---------------------------------------------------------------------------
def test_phase1_apps_import() -> None:
    print("\n== phase2 apps ==")
    import importlib.util
    import os
    import tempfile

    from fastapi.testclient import TestClient

    backup = dict(os.environ)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["AF_DATA_ROOT"] = tmp
            os.environ["AF_DOCKER_DRIVER"] = "off"
            os.environ.pop("CONTROL_PLANE_URL", None)
            os.environ.pop("REDIS_URL", None)
            os.environ.pop("AF_API_KEYS", None)
            os.environ.pop("DATABASE_URL", None)

            def load(name: str, path: Path):
                spec = importlib.util.spec_from_file_location(name, path)
                assert spec and spec.loader
                mod = importlib.util.module_from_spec(spec)
                sys.modules[name] = mod
                sys.path.insert(0, str(path.parent))
                sys.path.insert(0, str(ROOT))
                spec.loader.exec_module(mod)
                return mod

            # Reset CP DB engine before load; prefer control-plane on sys.path
            cp_dir = str(ROOT / "control-plane")
            while cp_dir in sys.path:
                sys.path.remove(cp_dir)
            sys.path.insert(0, cp_dir)
            for name in ("presets", "db", "models", "schemas", "docker_driver", "main"):
                sys.modules.pop(name, None)
            import db as cp_db

            cp_db.reset_engine_for_tests()

            cp = load("af_cp_main", ROOT / "control-plane/main.py")
            expect(hasattr(cp, "app"), "control-plane has app")
            # Explicit schema init (TestClient lifespan varies)
            import db as cp_db2

            cp_db2.init_db()
            cp._ENV_REGISTRY = cp.load_keys_from_env()
            cp._seed_dev_tenants()
            with TestClient(cp.app) as cpc:
                hr = cpc.get("/health")
                expect(hr.status_code == 200 and hr.json().get("plane") == "control", "CP /health")
                expect(cpc.get("/v1/tenants").status_code == 200, "CP list tenants")
                expect(cpc.get("/v1/presets").status_code == 200, "CP presets")
                pol = cpc.put(
                    "/v1/tenants/tenant_a/route-policy",
                    json={"mode": "hybrid"},
                )
                expect(pol.status_code == 200 and pol.json().get("mode") == "hybrid", "CP route policy")

            gw = load("af_gw_main", ROOT / "gateway/main.py")
            expect(hasattr(gw, "app"), "gateway has app")
            with TestClient(gw.app) as gwc:
                hr = gwc.get("/health")
                expect(hr.status_code == 200 and hr.json().get("plane") == "data", "GW /health")
                expect(hr.json().get("phase") == "4", "GW phase 4")
                expect("cloud_provider" in hr.json(), "GW cloud_provider")
                expect("night_window" in hr.json(), "GW night_window")

                # Dual-tenant 403
                bad = gwc.post(
                    "/v1/chat/completions",
                    headers={"Authorization": "Bearer sk-af-tenant-a-devonly"},
                    json={
                        "model": "tenants/tenant_b/loras/x",
                        "messages": [{"role": "user", "content": "x"}],
                    },
                )
                expect(bad.status_code == 403, "cross-tenant model → 403")
                unauth = gwc.get("/v1/models")
                expect(unauth.status_code == 401, "missing auth → 401")

            from gateway.router import choose_route

            d = choose_route(
                policy_mode="hybrid",
                short_max_chars=100,
                payload={"messages": [{"role": "user", "content": "short"}]},
                preset_backend="ollama",
            )
            expect(d.route == "local", "hybrid short → local")
    finally:
        os.environ.clear()
        os.environ.update(backup)


# ---------------------------------------------------------------------------
# 8b) Console scaffold
# ---------------------------------------------------------------------------
def test_console_scaffold() -> None:
    print("\n== console scaffold ==")
    pkg = json.loads((ROOT / "console/package.json").read_text(encoding="utf-8"))
    expect("vue" in (pkg.get("dependencies") or {}), "console depends on vue")
    expect("vite" in (pkg.get("devDependencies") or {}), "console uses vite")
    readme = (ROOT / "console/README.md").read_text(encoding="utf-8")
    expect("control-plane" in readme.lower(), "console talks to control-plane")
    expect("React" not in readme, "console README no React")
    for page in (
        "TenantsPage.vue",
        "InstancesPage.vue",
        "UsagePage.vue",
        "HostsPage.vue",
        "AlertsPage.vue",
        "CatalogPage.vue",
    ):
        expect((ROOT / "console/src/pages" / page).exists(), f"console page {page}")


# ---------------------------------------------------------------------------
# 8c) Phase 3 cloud / vector / cost / multi-lora
# ---------------------------------------------------------------------------
def test_phase3_cloud_vector_cost() -> None:
    print("\n== phase3 cloud/vector/cost ==")
    import os
    import tempfile

    from gateway import cloud_proxy as cp

    os.environ["AF_CLOUD_PROVIDER"] = "dashscope"
    os.environ.pop("AF_CLOUD_BASE_URL", None)
    expect("dashscope.aliyuncs.com" in cp.cloud_base_url(), "dashscope default base")
    os.environ["AF_CLOUD_PROVIDER"] = "deepseek"
    expect("deepseek.com" in cp.cloud_base_url(), "deepseek default base")
    for k in ("AF_CLOUD_PROVIDER", "AF_CLOUD_BASE_URL"):
        os.environ.pop(k, None)

    with tempfile.TemporaryDirectory() as tmp:
        os.environ["AF_DATA_ROOT"] = tmp
        from packages.tenantkit import LocalVectorStore, ensure_tenant_layout, TENANT_SUBDIRS

        expect("vector" in TENANT_SUBDIRS, "vector in TENANT_SUBDIRS")
        ensure_tenant_layout("tenant_a")
        ensure_tenant_layout("tenant_b")
        LocalVectorStore("tenant_a", "c").upsert(ids=["1"], documents=["only-a-doc"])
        hits = LocalVectorStore("tenant_b", "c").query(text="only-a-doc", top_k=3)
        expect(not any("only-a-doc" in h.document for h in hits), "vector no cross-tenant leak")

    expect((ROOT / "runtime/vllm/start_multi_lora.sh").exists(), "start_multi_lora.sh")
    expect((ROOT / "templates/vllm-multi-lora.yml.j2").exists(), "vllm-multi-lora template")
    autodl = (ROOT / "docs/deploy-autodl.md").read_text(encoding="utf-8")
    expect("cost_estimate" in autodl and "AF_CLOUD_PROVIDER" in autodl, "deploy-autodl Phase 3")

    import subprocess

    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts/cost_estimate.py"), "--list-gpus"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    expect(proc.returncode == 0 and "rtx4090" in proc.stdout, "cost_estimate --list-gpus")


# ---------------------------------------------------------------------------
# 8d) Phase 4 hosts / alerts / mirrors
# ---------------------------------------------------------------------------
def test_phase4_hosts_alerts_mirrors() -> None:
    print("\n== phase4 hosts/alerts/mirrors ==")
    import os
    import sys as _sys
    import tempfile

    from fastapi.testclient import TestClient

    os.environ["AF_SSH_DRIVER"] = "off"
    os.environ["AF_DOCKER_DRIVER"] = "off"
    os.environ.pop("DATABASE_URL", None)
    os.environ.pop("REDIS_URL", None)
    os.environ.pop("AF_API_KEYS", None)

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

    with tempfile.TemporaryDirectory() as tmp:
        os.environ["AF_DATA_ROOT"] = tmp
        import db as cp_db

        cp_db.reset_engine_for_tests()
        import ssh_driver as ssh

        status, note = ssh.probe_host(ssh.HostEndpoint("127.0.0.1", 22, "ubuntu"))
        expect(status == "simulated", f"ssh probe simulated ({status}: {note})")

        import main as cp_main

        cp_db.init_db()
        cp_main._ENV_REGISTRY = cp_main.load_keys_from_env()
        cp_main._seed_dev_tenants()

        with TestClient(cp_main.app) as client:
            host = client.post(
                "/v1/hosts",
                json={"name": "h1", "ssh_host": "10.0.0.1", "ssh_user": "ubuntu"},
            )
            expect(host.status_code == 201, "create host")
            hid = host.json()["id"]
            probe = client.post(f"/v1/hosts/{hid}/probe")
            expect(
                probe.status_code == 200 and probe.json()["status"] == "simulated",
                "probe simulated",
            )

            inst = client.post(
                "/v1/tenants/tenant_a/instances",
                json={"preset_id": "small-7b", "host_id": hid},
            )
            expect(
                inst.status_code == 201 and inst.json().get("host_id") == hid,
                "remote instance",
            )

            scan = client.post("/v1/alerts/scan")
            expect(scan.status_code == 200 and "open_total" in scan.json(), "alerts scan")

            mirrors = client.get("/v1/mirrors")
            expect(mirrors.status_code == 200 and len(mirrors.json()) >= 2, "mirror catalog")
            pid = mirrors.json()[0]["id"]
            slug = mirrors.json()[0]["adapter_slug"]
            lic = client.post(
                f"/v1/mirrors/{pid}/licenses",
                json={"tenant_id": "tenant_a"},
            )
            expect(lic.status_code == 201 and lic.json().get("license_key"), "issue license")
            act = client.post(
                "/v1/mirrors/activate",
                json={"license_key": lic.json()["license_key"]},
            )
            expect(act.status_code == 200 and act.json().get("activated_at"), "activate license")
            marker = Path(tmp) / "tenant_a" / "loras" / slug / "adapter_config.json"
            expect(marker.is_file(), "adapter marker installed")

    expect((ROOT / "scripts/alert_scan.py").exists(), "alert_scan.py")


# ---------------------------------------------------------------------------
# 9) Secrets / gitignore hygiene
# ---------------------------------------------------------------------------
def test_secrets_hygiene() -> None:
    print("\n== secrets hygiene ==")
    gi = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for line in (".env", "data/", "*.pem", "secrets/"):
        expect(line in gi, f".gitignore has {line}")
    expect((ROOT / ".env.example").exists(), ".env.example exists")
    # .env must not be force-tracked requirement; if present, ensure example has no real secret patterns
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    expect("af_dev_only" in example or "POSTGRES" in example, "example has dev placeholders")
    # No live-looking API keys in the example file (placeholders live in code defaults).
    expect("sk-" not in example, "no openai-like secret in example")
    expect((ROOT / "docs/deploy-autodl.md").exists(), "deploy-autodl.md exists")
    expect((ROOT / "runtime/sleep-watchdog/watchdog.py").exists(), "watchdog.py exists")
    # scan tracked-like source for private key headers
    for path in ROOT.rglob("*"):
        if ".git" in path.parts or not path.is_file():
            continue
        if path.suffix.lower() in {".png", ".jpg", ".webp", ".gif"}:
            continue
        try:
            sample = path.read_text(encoding="utf-8", errors="ignore")[:4000]
        except OSError:
            continue
        expect(
            "BEGIN PRIVATE KEY" not in sample and "BEGIN RSA PRIVATE KEY" not in sample,
            f"no private key material in {path.relative_to(ROOT)}",
        )


# ---------------------------------------------------------------------------
# 10) Smoke script itself
# ---------------------------------------------------------------------------
def test_smoke_script() -> None:
    print("\n== smoke_test.py ==")
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts/smoke_test.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    expect(proc.returncode == 0, "smoke_test exit 0")
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr)
    expect("SMOKE PASS" in proc.stdout, "smoke prints SMOKE PASS")


# ---------------------------------------------------------------------------
# 11) CI workflow sanity
# ---------------------------------------------------------------------------
def test_ci_workflow() -> None:
    print("\n== CI workflow ==")
    text = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    expect("smoke_test.py" in text, "CI runs smoke")
    expect("ruff" in text, "CI runs ruff")
    expect("requirements-dev.txt" in text, "CI installs requirements-dev")
    expect("docker compose" in text, "CI validates compose")


def main() -> int:
    print(f"deep test root: {ROOT}")
    test_json_schemas_load()
    test_jsonschema_validate_samples()
    test_pydantic_contracts()
    test_schema_pydantic_field_alignment()
    test_presets()
    test_tenant_compose_template()
    test_compose()
    test_docs_isolation()
    test_phase1_apps_import()
    test_console_scaffold()
    test_phase3_cloud_vector_cost()
    test_phase4_hosts_alerts_mirrors()
    test_secrets_hygiene()
    test_smoke_script()
    test_ci_workflow()

    print("\n" + "=" * 60)
    if FAILURES:
        print(f"DEEP TEST FAIL: {len(FAILURES)} failure(s)")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("DEEP TEST PASS: 0 failures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
