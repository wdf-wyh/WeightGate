# Local deploy — Phase 2

## Prerequisites

- Git, Docker (Compose v2), Python 3.12+
- Node 20+ optional (console `npm run dev`)
- Ollama optional for structural smoke; required for live chat

## Bootstrap

```bash
# Git Bash / WSL / macOS / Linux
chmod +x scripts/bootstrap.sh
./scripts/bootstrap.sh
pip install -r requirements-dev.txt
python scripts/smoke_test.py
python scripts/deep_test.py
```

Windows PowerShell:

```powershell
.\scripts\bootstrap.ps1
pip install -r requirements-dev.txt
python scripts\smoke_test.py
python scripts\deep_test.py
```

## Compose services

| Service | Profile | Ports | Notes |
|---------|---------|-------|-------|
| `postgres` | default | 5432 | Tenants, keys, instances, usage |
| `redis` | default | 6379 | RPM + last_active |
| `control-plane` | `app` | 8080 | Admin API + resolve-key |
| `gateway` | `app` | 8000 | OpenAI-compatible edge (hybrid) |
| `console` | `console` | 5173 | Vue admin (needs `app` too) |
| `ollama` | `ollama` | 11434 | Local inference |
| `open-webui` | `open-webui` | 3000 | Optional chat UI |

```bash
docker compose -f compose/docker-compose.yml --profile app --profile ollama up -d --build
docker compose -f compose/docker-compose.yml --profile ollama exec ollama ollama pull tinyllama
docker compose -f compose/docker-compose.yml --profile app --profile console up -d --build
```

Optional UI: add `--profile open-webui`.

## Dev API keys

Built-in placeholders (override with `AF_API_KEYS` JSON in `.env` only):

- tenant_a / tenant_b → `packages/tenantkit/keys.py` (`default_dev_keys`)
- Additional keys: `POST /v1/tenants/{id}/keys` (plaintext returned once; hash stored)

Never commit real keys. `.env.example` intentionally omits key material.

## Hybrid / cloud / vLLM env

| Var | Purpose |
|-----|---------|
| `VLLM_BASE_URL` | vLLM OpenAI server |
| `AF_CLOUD_PROVIDER` | `openai` \| `dashscope`/`bailian` \| `deepseek` |
| `AF_CLOUD_API_KEY` / `AF_CLOUD_BASE_URL` / `AF_CLOUD_MODEL` | Cloud adapter |
| `AF_CLOUD_NIGHT_*` | Night discount window (docs/estimate only) |
| `AF_ROUTE_DEGRADE` | `1` = fall back to Ollama on cloud/vLLM failure |
| `AF_DOCKER_DRIVER` | `off` in containers (instance records only) |

## What Phase 3 does **not** include

- Streaming completions
- K8s / GPU marketplace / paid model store backend

See also: [deploy-autodl.md](deploy-autodl.md), [phase3-checklist.md](phase3-checklist.md).
