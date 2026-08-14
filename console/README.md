# Console (Vue 3 + Vite + TypeScript) — Phase 4

Admin UI for **tenants**, **instances** (local Docker or remote host), **hosts**, **alerts**,
**mirror catalog**, and **usage**.

- **Stack**: Vue 3 + Vite + TypeScript + vue-router
- **Talks to**: `control-plane` only (Vite proxies `/v1` → `http://127.0.0.1:8080`)
- **Never** calls Ollama / vLLM / cloud runtimes directly
- **Secrets**: API / license keys are issued by control-plane and shown once in the UI; not baked into the bundle

## Dev

```bash
# control-plane must be up (compose profile app, or uvicorn)
cd console
npm install
npm run dev
```

Open http://127.0.0.1:5173

Optional: `VITE_API_BASE=http://127.0.0.1:8080` if not using the Vite proxy.

## Docker

```bash
docker compose -f compose/docker-compose.yml --profile app --profile console up -d --build
```

Console: http://127.0.0.1:5173
