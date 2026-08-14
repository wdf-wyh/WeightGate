# automatic-funicular

Open-source **weight-hosting middleware** for small models: local/prod hybrid routing, OpenAI-compatible edge, and multi-tenant isolation.

Not a flagship self-hosted “cloud”, and not a regional Hugging Face mirror.

## Positioning

| Is | Is not |
|----|--------|
| Small-model hosting + gateway middleware | Full MLOps / training platform |
| Hybrid route: **Ollama (local)** ↔ **vLLM (prod)** / cloud providers | GPU marketplace or managed GPU billing |
| Multi-tenant: API keys + `data/tenants/{id}/` (+ `vector/`) | Cross-tenant model zoo / public hub |
| Control plane ≠ data plane | Monolithic “all-in-one” inference appliance |

## Non-goals

- Flagship self-built public cloud UX
- “国产 Hugging Face” hub / social model discovery
- Shipping secrets or real weights in git

## Phase roadmap

| Phase | Focus | Status |
|-------|--------|--------|
| **0** | Monorepo layout, Compose skeleton, CI/smoke, OpenAI schemas, presets, isolation docs | Done |
| **1** | Ollama path live, gateway auth + chat/completions forward, dual-tenant isolation, sleep-watchdog, AutoDL/vLLM docs | Done |
| **2** | Control-plane Postgres APIs, hybrid routing, vLLM + cloud stub, Vue/Vite console MVP | Done |
| **3** | Multi-provider cloud (百炼/DeepSeek), per-tenant vectors, multi-LoRA examples, AutoDL cost estimate | Done |
| **4 (current)** | SSH remote hosts, alerts, vertical mirror licenses, remote deploy docs | **This repo** |
| **5+** | Fixed GPU pool only after prepaid customers; optional k3s | Planned |

## Repo layout

```
automatic-funicular/
├── README.md
├── docs/                 # architecture, isolation, local + AutoDL deploy, phase checklists
├── compose/              # docker-compose (postgres/redis + app/ollama/console)
├── control-plane/        # FastAPI control plane (tenants, keys, instances, policy, usage)
├── gateway/              # FastAPI OpenAI-compatible edge (hybrid + vector + adapters)
├── console/              # Vue 3 + Vite admin UI
├── runtime/              # ollama / vllm / sleep-watchdog / remote-agent
├── templates/            # model-presets, tenant-compose, vllm-multi-lora, mirror-catalog
├── schemas/openai/       # chat/completions request & response contracts
├── packages/contracts/   # Pydantic mirrors of OpenAI schemas
├── packages/tenantkit/   # tenant FS + API key + vector helpers
├── scripts/              # bootstrap, smoke_test, deep_test, cost_estimate, alert_scan
└── examples/             # law-lora, trade-agent (+ manifests)
```

## One-shot local chat (Ollama)

Windows PowerShell:

```powershell
.\scripts\bootstrap.ps1
pip install -r requirements-dev.txt
python scripts\smoke_test.py
python scripts\deep_test.py

# deps + app + ollama
docker compose -f compose/docker-compose.yml --profile app --profile ollama up -d --build
docker compose -f compose/docker-compose.yml --profile ollama exec ollama ollama pull tinyllama

# optional Vue console
docker compose -f compose/docker-compose.yml --profile app --profile console up -d --build

# chat via gateway (dev key for tenant_a — see packages/tenantkit/keys.py)
curl http://127.0.0.1:8000/v1/chat/completions `
  -H "Authorization: Bearer sk-af-tenant-a-devonly" `
  -H "Content-Type: application/json" `
  -d '{"model":"tinyllama","messages":[{"role":"user","content":"ping"}],"max_tokens":32}'
```

Linux / macOS / Git Bash: same with `./scripts/bootstrap.sh` and `curl` one-liners.

- Console: http://127.0.0.1:5173 (profile `console`) or `cd console && npm install && npm run dev`
- Optional Open WebUI: add `--profile open-webui` (http://127.0.0.1:3000)

Dev keys (local only): `sk-af-tenant-a-devonly` / `sk-af-tenant-b-devonly`. Cross-tenant adapter paths return **403**.

Hybrid routing uses tenant `RoutePolicy` (`local_only` | `cloud_only` | `hybrid`). Cloud: set `AF_CLOUD_PROVIDER` (`dashscope` / `deepseek` / `openai`), `AF_CLOUD_API_KEY`, optional `AF_CLOUD_MODEL` / `AF_CLOUD_BASE_URL`. vLLM: `VLLM_BASE_URL`. Failures degrade to Ollama when `AF_ROUTE_DEGRADE=1`.

Night discount window (docs/estimate only): `AF_CLOUD_NIGHT_START` / `END` / `DISCOUNT` / `TZ` — see [deploy-autodl](docs/deploy-autodl.md) and `python scripts/cost_estimate.py --help`.

## Docs

- [Architecture](docs/architecture.md)
- [Tenant isolation](docs/tenant-isolation.md)
- [Local deploy](docs/deploy-local.md)
- [AutoDL / vLLM (pay-as-you-go)](docs/deploy-autodl.md)
- [Remote / customer SSH hosts](docs/deploy-remote.md)
- [Phase 0 checklist](docs/phase0-checklist.md)
- [Phase 1 checklist](docs/phase1-checklist.md)
- [Phase 2 checklist](docs/phase2-checklist.md)
- [Phase 3 checklist](docs/phase3-checklist.md)
- [Phase 4 checklist](docs/phase4-checklist.md)
- [OpenAI schemas](schemas/openai/README.md)
- [Console](console/README.md)
- Examples: [law-lora](examples/law-lora/README.md), [trade-agent](examples/trade-agent/README.md)

## License

TBD — choose before public release.
