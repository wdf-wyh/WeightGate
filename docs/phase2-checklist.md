# Phase 2 acceptance checklist

Phase 2 = control-plane admin API (Postgres), gateway hybrid routing + vLLM/cloud adapters, Vue console MVP. Ollama local demo remains the default zero-GPU path.

## Must pass

- [x] Control-plane: tenant CRUD, API key issue/rotate (hash at rest via `packages/tenantkit`), presets from `templates/model-presets.yaml`
- [x] Instances: create / stop / wake (local Docker Compose driver; simulated when `AF_DOCKER_DRIVER=off`)
- [x] RoutePolicy: `local_only | cloud_only | hybrid`
- [x] Usage query + gateway `POST /internal/v1/usage`
- [x] `POST /internal/v1/resolve-key` still works (DB hash + env key fallback)
- [x] Gateway hybrid rules: short/no-tools → local; long/tools → cloud or vLLM by preset; degrade on failure
- [x] vLLM proxy (`VLLM_BASE_URL`); Ollama path unchanged
- [x] Cloud adapter stub (`AF_CLOUD_API_KEY`); optional degrade to local
- [x] Console (Vue 3 + Vite + TS): Tenants / Instances / Usage — control-plane only
- [x] Compose: postgres + redis + gateway + control-plane + optional `console` profile
- [x] `python scripts/smoke_test.py` and `python scripts/deep_test.py` (incl. Phase 2 CRUD / policy / 403)
- [x] README Phase 2 status + start steps

## Explicitly deferred

- Vertical mirror / model zoo store → Phase 3+
- K8s, streaming chat, real weight ingest, GPU marketplace
- React console (repo is Vue)

## Live demo (Ollama, no GPU required)

```powershell
docker compose -f compose/docker-compose.yml --profile app --profile ollama up -d --build
docker compose -f compose/docker-compose.yml --profile ollama exec ollama ollama pull tinyllama
# optional console
docker compose -f compose/docker-compose.yml --profile app --profile console up -d --build
```
