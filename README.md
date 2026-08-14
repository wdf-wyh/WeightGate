# WeightGate

**OpenAI-compatible edge for small models** — hybrid route **Ollama (local) ↔ vLLM / cloud**, with **multi-tenant isolation**.

Not a self-hosted “AI cloud”. Not a Hugging Face mirror. Middleware that hosts weights, gates traffic, and keeps tenants apart.

[![CI](https://github.com/wdf-wyh/WeightGate/actions/workflows/ci.yml/badge.svg)](https://github.com/wdf-wyh/WeightGate/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

![WeightGate demo](docs/assets/demo.gif)

<p align="center">
  <img src="docs/assets/console.png" alt="WeightGate console" width="720" />
</p>

<p align="center">
  <img src="docs/assets/gateway.png" alt="Gateway OpenAPI" width="48%" />
  <img src="docs/assets/control-plane.png" alt="Control plane OpenAPI" width="48%" />
</p>

---

## Why WeightGate

| You need | WeightGate gives you |
|----------|----------------------|
| One OpenAI-shaped API for local + prod | Gateway `/v1/chat/completions` |
| Cheap laptop demos, real GPU later | Ollama → vLLM / AutoDL without rewriting clients |
| Per-customer keys & data | API keys + `data/tenants/{id}/` (+ `vector/`) |
| Control ≠ inference | FastAPI control plane + separate data plane |

**Not for:** full MLOps, public model hubs, GPU marketplaces, or shipping secrets/weights in git.

## vs similar tools

| | WeightGate | LiteLLM / OneAPI-style | Open WebUI |
|--|------------|------------------------|------------|
| Focus | Small-model **hosting + tenant isolation** | Provider proxy / key pool | Chat UI |
| Hybrid local↔prod | First-class (`RoutePolicy`) | Usually provider list | UI-centric |
| Tenant FS + vectors | Built-in paths | Rarely | N/A |
| Control / data split | Explicit | Often monolith config | App + backends |

## Quick start (≈5 min)

**Prereqs:** Docker Compose, Python 3.12+, curl.

```bash
git clone https://github.com/wdf-wyh/WeightGate.git
cd WeightGate
cp .env.example .env

# Windows: .\scripts\bootstrap.ps1
./scripts/bootstrap.sh
pip install -r requirements-dev.txt

docker compose -f compose/docker-compose.yml --profile app --profile ollama up -d --build
docker compose -f compose/docker-compose.yml --profile ollama exec ollama ollama pull tinyllama
```

Chat through the gateway (dev key for `tenant_a`):

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Authorization: Bearer sk-af-tenant-a-devonly" \
  -H "Content-Type: application/json" \
  -d '{"model":"tinyllama","messages":[{"role":"user","content":"ping"}],"max_tokens":32}'
```

PowerShell: use `` ` `` line continuations (see below) or a single-line `-d`.

| Surface | URL |
|---------|-----|
| Gateway | http://127.0.0.1:8000 |
| Console (optional) | http://127.0.0.1:5173 — add `--profile console` |
| Open WebUI (optional) | http://127.0.0.1:3000 — add `--profile open-webui` |

Dev keys (local only): `sk-af-tenant-a-devonly` / `sk-af-tenant-b-devonly`. Cross-tenant adapter paths return **403**.

Smoke checks: `python scripts/smoke_test.py` · `python scripts/deep_test.py`

## Architecture

```
 Client / Agent / Console
       │  Bearer <tenant_api_key>
       ▼
   gateway  ── hybrid ──►  ollama | vllm | cloud (百炼 / DeepSeek / OpenAI-compatible)
       │
       ▼
 control-plane  (tenants, keys, instances, route policy, usage, SSH hosts, alerts)
       │
       ├── Postgres + Redis
       └── data/tenants/{id}/   (models, loras, vector/, logs)
```

**Route policies:** `local_only` | `cloud_only` | `hybrid`  
**Degrade:** set `AF_ROUTE_DEGRADE=1` so cloud/vLLM failures fall back to Ollama.  
**Cloud:** `AF_CLOUD_PROVIDER` (`dashscope` / `bailian` / `deepseek` / `openai`) + `AF_CLOUD_API_KEY`.  
**vLLM:** `VLLM_BASE_URL`. Night window envs are for cost estimate only — see [deploy-autodl](docs/deploy-autodl.md).

## Repo layout

```
WeightGate/
├── compose/           # docker-compose (postgres/redis + app/ollama/console)
├── control-plane/     # FastAPI control plane
├── gateway/           # OpenAI-compatible edge
├── console/           # Vue 3 + Vite admin UI
├── runtime/           # ollama / vllm / sleep-watchdog / remote-agent
├── packages/          # contracts + tenantkit
├── templates/         # model presets, tenant-compose, multi-LoRA, mirrors
├── schemas/openai/    # chat/completions contracts
├── scripts/           # bootstrap, smoke/deep tests, cost_estimate, alert_scan
├── examples/          # law-lora, trade-agent
└── docs/              # architecture, isolation, deploy guides
```

## Docs

- [Architecture](docs/architecture.md) · [Tenant isolation](docs/tenant-isolation.md)
- [Local deploy](docs/deploy-local.md) · [AutoDL / vLLM](docs/deploy-autodl.md) · [Remote SSH hosts](docs/deploy-remote.md)
- Phase checklists: [0](docs/phase0-checklist.md) · [1](docs/phase1-checklist.md) · [2](docs/phase2-checklist.md) · [3](docs/phase3-checklist.md) · [4](docs/phase4-checklist.md)
- [OpenAI schemas](schemas/openai/README.md) · [Console](console/README.md)
- Examples: [law-lora](examples/law-lora/README.md) · [trade-agent](examples/trade-agent/README.md)

## Roadmap

| Phase | Focus | Status |
|-------|--------|--------|
| 0–3 | Monorepo, Ollama path, hybrid + console, multi-provider + vectors | Done |
| **4** | SSH remote hosts, alerts, mirror licenses, remote deploy docs | **Current** |
| 5+ | Fixed GPU pool (prepaid), optional k3s | Planned |

## License

[MIT](LICENSE) © 2026 wdf-wyh / WeightGate contributors.

GitHub About / Topics paste text: [docs/github-meta.md](docs/github-meta.md).
