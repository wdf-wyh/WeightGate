# Tenant isolation (Phase 3 contract)

## Goals

- One tenant cannot read another tenant's keys, weights, vectors, or request logs.
- Isolation is enforced at **API key**, **filesystem**, **vector store**, and **runtime** boundaries.

## API keys

- Each tenant has one or more API keys issued by the control plane.
- Gateway authenticates `Authorization: Bearer <key>` and resolves `tenant_id` **only** from the key record.
- Request body fields such as `user`, `model`, or `adapter` must never be trusted as tenant identity.
- Cross-tenant model / adapter / path names are rejected even if guessed (**403**).

## Filesystem layout

```
data/tenants/{tenant_id}/
  models/          # base / pulled weights for this tenant
  loras/           # optional adapters (multi-LoRA mounts stay under this tree)
  vector/          # per-tenant vector index (LocalVectorStore / Chroma persist)
    collections/   # default JSONL collections
    chroma/        # optional Chroma persist_directory binding
  cache/           # runtime cache (optional)
  logs/            # tenant-scoped logs (optional)
```

Rules:

- Process working directories and volume mounts are scoped to `data/tenants/{id}/`.
- Gateway mounts tenant data; vector upsert may write under `{id}/vector/` only. Path traversal and cross-tenant refs remain forbidden.
- Path traversal (`../`) out of the tenant root is forbidden.
- The `data/` tree is gitignored; never commit weights, vectors dumps with secrets, or keys.

## Vector store (Phase 3)

- Each tenant gets an independent directory: `data/tenants/{id}/vector/`.
- Gateway APIs (`POST /v1/vector/upsert`, `POST /v1/vector/query`, `GET /v1/vector/info`) bind the store from the **authenticated** tenant only.
- Control-plane `GET /internal/v1/tenants/{id}/root` returns `vector_root` / `chroma_persist_dir` for operators; still tenant-scoped.
- There is no shared “global” collection. Do not mount multiple tenants' `vector/` into one Chroma process.

## LoRA / adapter selection

- Clients may pass `X-AF-Adapter: loras/<name>` or body `adapter` / `af_adapter`.
- Gateway validates with the same cross-tenant rules as `model` paths.
- vLLM multi-LoRA templates (`runtime/vllm/start_multi_lora.*`, `templates/vllm-multi-lora.yml.j2`) must only mount one tenant's `loras/`.

## Runtime / network

- Tenant runtimes are labeled `af.tenant_id={id}` (see `templates/tenant-compose.yml.j2`).
- Gateway routes only in the context of the authenticated tenant (shared Ollama demo uses FS/model-path isolation).
- Shared Redis keys must be prefixed by `tenant_id` (e.g. `af:rpm:{tenant_id}`, `af:last_active:{tenant_id}`).
- Postgres rows always carry `tenant_id`; queries are tenant-scoped.

## Dual-tenant smoke

Bootstrap creates `tenant_a` and `tenant_b` under `data/tenants/` with `models/`, `loras/`, `cache/`, `logs/`, `vector/`. Built-in dev keys map 1:1. A request that references the other tenant's path (e.g. `tenants/tenant_b/loras/...` or `X-AF-Adapter` to that path) returns **403**. Missing/invalid Bearer → **401**. Vector upsert/query never reads sibling tenant directories.

## Explicit non-goals (still)

- Full RBAC UI, org hierarchies, or billing isolation.
- Hardware-level GPU MIG partitioning.
- Shared multi-tenant vector SaaS.
