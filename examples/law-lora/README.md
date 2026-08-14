# Law LoRA example (Phase 3 — follow-along, no real weights in git)

Demonstrates packing a **domain LoRA** under one tenant and selecting it through the gateway.

## Layout

```
data/tenants/tenant_a/
  models/          # optional local base (or use HF id on GPU box)
  loras/
    law-v1/        # your adapter files (adapter_config.json + weights) — gitignored
    law-v1.placeholder.txt   # created by scripts below for smoke
  vector/          # optional RAG corpus for this tenant only
```

Never put another tenant's path in `loras/` or in the request `model` / `X-AF-Adapter` field.

## 1. Fake adapter marker (zero GPU)

From repo root:

```powershell
.\scripts\bootstrap.ps1
New-Item -ItemType Directory -Force -Path data\tenants\tenant_a\loras\law-v1 | Out-Null
Set-Content data\tenants\tenant_a\loras\law-v1\adapter_config.json '{"placeholder":true,"domain":"law"}'
```

Gateway lists it as `loras/law-v1` for tenant A's key only.

## 2. Chat with adapter header

```powershell
curl http://127.0.0.1:8000/v1/chat/completions `
  -H "Authorization: Bearer sk-af-tenant-a-devonly" `
  -H "Content-Type: application/json" `
  -H "X-AF-Adapter: loras/law-v1" `
  -d '{"model":"tinyllama","messages":[{"role":"user","content":"合同违约责任要点？"}],"max_tokens":64}'
```

Equivalent body field:

```json
{"model":"tinyllama","adapter":"loras/law-v1","messages":[{"role":"user","content":"ping"}],"max_tokens":32}
```

Cross-tenant (must be **403**):

```powershell
curl http://127.0.0.1:8000/v1/chat/completions `
  -H "Authorization: Bearer sk-af-tenant-a-devonly" `
  -H "X-AF-Adapter: tenants/tenant_b/loras/adapter_b.txt" `
  -H "Content-Type: application/json" `
  -d '{"model":"tinyllama","messages":[{"role":"user","content":"leak"}],"max_tokens":8}'
```

## 3. Real multi-LoRA on AutoDL / local GPU

1. Place real adapter weights under `data/tenants/tenant_a/loras/law-v1/` (not committed).
2. Start vLLM with the multi-LoRA template:

```bash
TENANT_ID=tenant_a \
MODEL=Qwen/Qwen2.5-7B-Instruct \
LORA_MODULES="law-v1=./data/tenants/tenant_a/loras/law-v1" \
./runtime/vllm/start_multi_lora.sh
```

3. Point gateway `VLLM_BASE_URL` at that server; set tenant route policy to `hybrid` or `cloud_only` as needed.
4. Call with `X-AF-Adapter: loras/law-v1` (name must match `--lora-modules` key).

See also: [templates/vllm-multi-lora.yml.j2](../../templates/vllm-multi-lora.yml.j2), [docs/deploy-autodl.md](../../docs/deploy-autodl.md).

## Status

Follow-along example ready (Phase 3). Phase 4: issue `law-lora-v1` from `/v1/mirrors`, then
`POST /v1/mirrors/activate` to install `loras/law-v1` under the tenant (see `manifest.yaml`).
Real weights stay outside git.
