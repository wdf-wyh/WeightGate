# Ollama runtime (local / Phase 1)

Local inference backend. Gateway forwards OpenAI-compatible
`POST /v1/chat/completions` and `GET /v1/models` to Ollama's `/v1/*` API.

## Compose

```bash
docker compose -f compose/docker-compose.yml --profile ollama up -d
```

Optional chat UI:

```bash
docker compose -f compose/docker-compose.yml --profile ollama --profile open-webui up -d
# Open WebUI → http://127.0.0.1:3000
```

With gateway:

```bash
docker compose -f compose/docker-compose.yml --profile app --profile ollama up -d --build
```

## Pull a tiny model (after Ollama is up)

```bash
docker compose -f compose/docker-compose.yml --profile ollama exec ollama ollama pull tinyllama
```

Or host-installed Ollama:

```bash
ollama pull tinyllama
ollama serve   # if not already running; default http://127.0.0.1:11434
```

Point the gateway at a host Ollama from Compose by setting in `.env`:

```
OLLAMA_BASE_URL=http://host.docker.internal:11434
```

## Health check

```bash
# Linux / macOS / Git Bash
./runtime/ollama/healthcheck.sh

# Windows PowerShell
.\runtime\ollama\healthcheck.ps1
```

Manual:

```bash
curl -s http://127.0.0.1:11434/api/tags
curl -s http://127.0.0.1:11434/v1/models
```

Exit 0 from the health scripts means Ollama responded successfully.
