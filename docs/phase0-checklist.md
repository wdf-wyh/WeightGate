# Phase 0 acceptance checklist

Phase 0 = **仓与契约 only**. No Ollama bring-up, no gateway auth implementation, no Vue console app.

## Must pass

- [x] Monorepo dirs: control-plane, gateway, console, runtime/*, templates, schemas, scripts, examples
- [x] `docker compose -f compose/docker-compose.yml config` (and `--profile app`)
- [x] `python scripts/smoke_test.py` and `python scripts/deep_test.py` pass
- [x] CI: lint (ruff gate) + smoke + deep regression
- [x] OpenAI schemas: chat/completions (+ stream), models list, error
- [x] Pydantic mirrors under `packages/contracts`
- [x] `templates/model-presets.yaml` covers 7B/14B/27B/32B with backend/quant/min_vram
- [x] Docs: architecture, tenant-isolation, deploy-local
- [x] README: positioning, non-goals, phases, local skeleton
- [x] Stack note: FastAPI + Vue(Vite) + Postgres + Redis; Ollama local / vLLM prod

## Explicitly deferred

- Inference forward / wake-sleep orchestration → Phase 1
- Vue(Vite) console scaffold → Phase 2
- Real secrets / GPU provisioning scripts → never in Phase 0 git
