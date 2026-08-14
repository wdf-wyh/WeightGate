# Phase 3 acceptance checklist

Phase 3 = portfolio polish on top of Phase 2: real cloud providers, per-tenant vectors, multi-LoRA examples, AutoDL cost tooling. Ollama local demo remains the default zero-GPU path. No K8s / marketplace / console rewrite.

## Must pass

- [x] Cloud multi-provider: `AF_CLOUD_PROVIDER` ∈ {`openai`,`dashscope`/`bailian`,`deepseek`} + `AF_CLOUD_BASE_URL` / `AF_CLOUD_API_KEY` / `AF_CLOUD_MODEL`
- [x] Degrade to local on cloud/vLLM failure when `AF_ROUTE_DEGRADE=1`
- [x] Night window env documented + exposed on gateway `/health` (`AF_CLOUD_NIGHT_*`)
- [x] `data/tenants/{id}/vector/` in layout; `LocalVectorStore` + gateway `/v1/vector/*`
- [x] Cross-tenant vector / adapter / model paths still **403**; no shared vector root
- [x] Multi-LoRA: `runtime/vllm/start_multi_lora.*` + `templates/vllm-multi-lora.yml.j2`
- [x] Adapter via `X-AF-Adapter` or body `adapter`; isolation aligned with model rules
- [x] `examples/law-lora` + `examples/trade-agent` follow-along (no real weights in git)
- [x] `docs/deploy-autodl.md` aligned with scripts; `scripts/cost_estimate.py` runs
- [x] `docs/phase3-checklist.md` (this file); README Phase 3 Done; architecture Phase 3
- [x] `python scripts/smoke_test.py` and `python scripts/deep_test.py` (Phase 3 paths)

## Explicitly deferred

- K8s / self-built GPU pool / paid model store backend
- Streaming chat
- Console framework rewrite (stays Vue)
- Real vendor billing API integration

## How to demo Phase 3 (short)

```powershell
# 0) zero-GPU baseline
.\scripts\bootstrap.ps1
pip install -r requirements-dev.txt
python scripts\smoke_test.py
python scripts\deep_test.py

# 1) optional cloud (pick one; never commit the key)
# 百炼:
#   $env:AF_CLOUD_PROVIDER="dashscope"
#   $env:AF_CLOUD_API_KEY="<dashscope-key>"
#   $env:AF_CLOUD_MODEL="qwen-plus"
# DeepSeek:
#   $env:AF_CLOUD_PROVIDER="deepseek"
#   $env:AF_CLOUD_API_KEY="<deepseek-key>"
#   $env:AF_CLOUD_MODEL="deepseek-chat"
$env:AF_ROUTE_DEGRADE="1"

# 2) app + ollama
docker compose -f compose/docker-compose.yml --profile app --profile ollama up -d --build
docker compose -f compose/docker-compose.yml --profile ollama exec ollama ollama pull tinyllama

# 3) vector isolation
curl http://127.0.0.1:8000/v1/vector/upsert -H "Authorization: Bearer sk-af-tenant-a-devonly" -H "Content-Type: application/json" -d "{\"collection\":\"demo\",\"ids\":[\"1\"],\"documents\":[\"tenant a secret note\"]}"
curl http://127.0.0.1:8000/v1/vector/query -H "Authorization: Bearer sk-af-tenant-b-devonly" -H "Content-Type: application/json" -d "{\"collection\":\"demo\",\"query\":\"secret\",\"top_k\":3}"
# tenant_b hits must be empty (separate volume)

# 4) LoRA adapter header (marker adapter)
curl http://127.0.0.1:8000/v1/chat/completions -H "Authorization: Bearer sk-af-tenant-a-devonly" -H "X-AF-Adapter: loras/adapter_a.txt" -H "Content-Type: application/json" -d "{\"model\":\"tinyllama\",\"messages\":[{\"role\":\"user\",\"content\":\"ping\"}],\"max_tokens\":16}"

# 5) cost rough-cut
python scripts\cost_estimate.py --gpu rtx4090 --hourly-cny 2 --hours 4 --quant awq
```

Follow-along: `examples/law-lora/README.md`, `examples/trade-agent/README.md`.
