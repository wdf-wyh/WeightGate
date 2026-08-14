#!/usr/bin/env bash
# Ollama health check — exit 0 when /api/tags responds.
set -euo pipefail
BASE="${OLLAMA_BASE_URL:-http://127.0.0.1:11434}"
BASE="${BASE%/}"
curl -fsS --max-time 5 "${BASE}/api/tags" >/dev/null
echo "OK ollama health: ${BASE}"
