# Phase 1 acceptance checklist

Phase 1 = **0-cost local prototype**: Ollama path live, gateway auth + forward, dual-tenant isolation smoke, sleep-watchdog basics, vLLM/AutoDL docs. No Vue console.

## Must pass

- [x] Compose: `ollama` (+ optional `open-webui`) profiles; `app` builds gateway + control-plane
- [x] `docker compose -f compose/docker-compose.yml --profile app --profile ollama config`
- [x] Gateway: `Authorization: Bearer …` → tenant; Redis RPM; `POST /v1/chat/completions` + `GET /v1/models` → Ollama
- [x] Uses `packages/contracts` + `packages/tenantkit`; respects `schemas/openai`
- [x] `data/tenants/{id}/{models,loras,cache,logs}/` laid out for ≥2 tenants
- [x] Dual-tenant: A key cannot use B adapter/path (403); bad key → 401
- [x] `runtime/ollama` health scripts + README
- [x] `runtime/sleep-watchdog/watchdog.py` idle stop (--once / --loop)
- [x] `runtime/vllm/start_single_gpu.*` + `docs/deploy-autodl.md` (no pad)
- [x] `python scripts/smoke_test.py` and `python scripts/deep_test.py` pass (incl. Phase 1 isolation)
- [x] README: Phase 1 status + one-shot local chat steps

## Explicitly deferred

- Vue/Vite console → Phase 2
- Full control-plane CRUD / hybrid Ollama↔vLLM routing → Phase 2
- Streaming chat completions → later
- Real secrets / weights in git → never

## Live chat (optional local)

Requires Ollama model pull; not gated in CI:

```powershell
docker compose -f compose/docker-compose.yml --profile app --profile ollama up -d --build
docker compose -f compose/docker-compose.yml --profile ollama exec ollama ollama pull tinyllama
```
