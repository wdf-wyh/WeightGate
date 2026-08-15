# Architecture (Phase 4)

## Product

**WeightGate** is open-source middleware for hosting small-model weights with hybrid routing and multi-tenant isolation. It is not a flagship self-built cloud and not a China-local Hugging Face clone.

## Planes

| Plane | Components | Responsibility |
|-------|------------|----------------|
| **Control** | `control-plane` (FastAPI), Postgres metadata, Vue/Vite console | Tenants, hashed API keys, presets, instances wake/sleep, route policy, usage, **SSH hosts**, **alerts**, **mirror licenses** |
| **Data** | `gateway` (FastAPI), Ollama / vLLM / cloud providers, Redis, per-tenant vector dirs | OpenAI-compatible inference edge; authn; RPM; hybrid route; tenant vector upsert/query |

Control plane never serves model tokens. Gateway never mutates tenant admin state except via control-plane APIs / shared contracts.

Shared **OpenAI-compatible contracts** live in `schemas/openai/` (JSON Schema) and `packages/contracts/` (Pydantic). Tenant FS + key + vector helpers: `packages/tenantkit`.

```
 Client / Agent / Console
       │  Bearer <tenant_api_key>     (console → CP only)
       ▼
   gateway  ── hybrid ──►  runtime (ollama | vllm | cloud providers)
       │                      ▲
       │ usage events         │ wake / unload / multi-LoRA
       │ vector/{tenant}      │ SSH remote-agent (customer host)
       ▼                      │
 control-plane  ◄── sleep-watchdog / alert scan
       │
       ├── Postgres (tenants, keys, instances, hosts, alerts, licenses, policies, usage)
       ├── Redis (af:rpm:{tenant_id}, af:last_active:{tenant_id})
       └── data/tenants/{id}/ (models, loras, vector/, logs — FS isolation)
```

## Stack (agreed)

- **API**: FastAPI (`control-plane`, `gateway`)
- **Console**: Vue 3 + Vite + TypeScript
- **Store**: Postgres + Redis
- **Local runtime**: Ollama (default zero-GPU demo)
- **Prod runtime**: vLLM (`VLLM_BASE_URL`, optional multi-LoRA)
- **Remote**: SSH provider (`AF_SSH_DRIVER`, `runtime/remote-agent/`) on customer-owned machines
- **Cloud**: OpenAI-compatible multi-provider (`AF_CLOUD_PROVIDER`: `dashscope` / `bailian` / `deepseek` / `openai`)

## Hybrid routing

Gateway chooses backend by tenant **RoutePolicy** + preset (`templates/model-presets.yaml`: `backend: ollama|vllm`):

| Policy | Behavior |
|--------|----------|
| `local_only` | Always Ollama |
| `cloud_only` | Cloud adapter (degrade to Ollama if unset/fails) |
| `hybrid` | Short / no tools → local; long context or tool signals → cloud or vLLM by preset |

Cloud failures and missing keys degrade to local when `AF_ROUTE_DEGRADE=1`. Night discount window env (`AF_CLOUD_NIGHT_*`) is informational for ops / `cost_estimate.py` — not a live billing API.

## Vector isolation

Each tenant persists embeddings under `data/tenants/{id}/vector/` (JSONL `LocalVectorStore` by default; `vector/chroma/` reserved for Chroma persist). Gateway vector routes never accept a caller-supplied tenant id.

## Phase 4 scope

SSH remote hosts + agent install, alert scan (instance / quota / disk), vertical mirror catalog + license activate, console Hosts/Alerts/Catalog pages, `docs/deploy-remote.md`. Seller capital still never sits in a GPU pool.
