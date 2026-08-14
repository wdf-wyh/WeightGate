# Trade agent example (Phase 3 — follow-along)

Shows an agent-style client calling the OpenAI-compatible gateway with a tenant API key, optional tools (hybrid → cloud), and a trade LoRA adapter.

## Prerequisites

- Local Ollama demo: `docker compose … --profile app --profile ollama` + `ollama pull tinyllama`
- Dev key: `sk-af-tenant-a-devonly` (tenant_a)
- Optional cloud: set `AF_CLOUD_PROVIDER=deepseek` (or `dashscope`) + `AF_CLOUD_API_KEY`

## 1. Marker adapter

```powershell
New-Item -ItemType Directory -Force -Path data\tenants\tenant_a\loras\trade-v1 | Out-Null
Set-Content data\tenants\tenant_a\loras\trade-v1\adapter_config.json '{"placeholder":true,"domain":"trade"}'
```

## 2. Short local call (hybrid → Ollama)

```powershell
curl http://127.0.0.1:8000/v1/chat/completions `
  -H "Authorization: Bearer sk-af-tenant-a-devonly" `
  -H "X-AF-Adapter: loras/trade-v1" `
  -H "Content-Type: application/json" `
  -d '{"model":"tinyllama","messages":[{"role":"user","content":"ping"}],"max_tokens":32}'
```

Response includes `af_route` / `af_adapter` for correlation.

## 3. Tools signal → cloud (when configured)

Hybrid policy routes tool-bearing requests to cloud (or vLLM by preset). Without `AF_CLOUD_API_KEY`, gateway degrades to local when `AF_ROUTE_DEGRADE=1`.

```powershell
curl http://127.0.0.1:8000/v1/chat/completions `
  -H "Authorization: Bearer sk-af-tenant-a-devonly" `
  -H "Content-Type: application/json" `
  -d '{
    "model":"tinyllama",
    "adapter":"loras/trade-v1",
    "messages":[{"role":"user","content":"查一下沪深300最近波动"}],
    "tools":[{"type":"function","function":{"name":"get_index","parameters":{"type":"object"}}}],
    "max_tokens":64
  }'
```

## 4. Tenant-scoped RAG snippet

```powershell
curl http://127.0.0.1:8000/v1/vector/upsert `
  -H "Authorization: Bearer sk-af-tenant-a-devonly" `
  -H "Content-Type: application/json" `
  -d '{"collection":"trade","ids":["note-1"],"documents":["隔夜美联储会议纪要偏鸽"]}'

curl http://127.0.0.1:8000/v1/vector/query `
  -H "Authorization: Bearer sk-af-tenant-a-devonly" `
  -H "Content-Type: application/json" `
  -d '{"collection":"trade","query":"美联储","top_k":3}'
```

Tenant B cannot see these docs (separate `data/tenants/tenant_b/vector/` volume).

## 5. Minimal Python client

```python
import httpx

BASE = "http://127.0.0.1:8000"
KEY = "sk-af-tenant-a-devonly"

r = httpx.post(
    f"{BASE}/v1/chat/completions",
    headers={"Authorization": f"Bearer {KEY}", "X-AF-Adapter": "loras/trade-v1"},
    json={
        "model": "tinyllama",
        "messages": [{"role": "user", "content": "给出三条风控检查项"}],
        "max_tokens": 128,
    },
    timeout=60.0,
)
print(r.status_code, r.json())
```

## Status

Runnable walkthrough (Phase 3). Phase 4: catalog product `trade-agent-v1` + license activate
writes `loras/trade-v1` (see `manifest.yaml`). No live market data feed and no real LoRA weights in this repo.
