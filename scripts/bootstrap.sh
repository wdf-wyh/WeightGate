#!/usr/bin/env bash
# Bootstrap local Phase 1 (dual-tenant dirs + env). GPU optional.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> ensuring dual-tenant data roots (gitignored)"
for tid in tenant_a tenant_b _example; do
  for sub in models loras cache logs vector; do
    mkdir -p "data/tenants/${tid}/${sub}"
  done
done
if [[ ! -f data/tenants/tenant_a/loras/adapter_a.txt ]]; then
  echo "tenant_a adapter placeholder" > data/tenants/tenant_a/loras/adapter_a.txt
fi
if [[ ! -f data/tenants/tenant_b/loras/adapter_b.txt ]]; then
  echo "tenant_b adapter placeholder" > data/tenants/tenant_b/loras/adapter_b.txt
fi

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "==> wrote .env from .env.example (dev defaults only)"
else
  echo "==> .env already exists; leaving untouched"
fi

echo "==> validating compose config"
if command -v docker >/dev/null 2>&1; then
  docker compose -f compose/docker-compose.yml config >/dev/null
  docker compose -f compose/docker-compose.yml --profile app config >/dev/null
  docker compose -f compose/docker-compose.yml --profile ollama config >/dev/null
  echo "    compose config: OK (default/app/ollama)"
else
  echo "    docker not found; skip compose config"
fi

echo "==> Phase 1 bootstrap done"
echo "    Next: pip install -r requirements-dev.txt && python scripts/smoke_test.py"
echo "    Chat stack:"
echo "      docker compose -f compose/docker-compose.yml --profile app --profile ollama up -d --build"
echo "      docker compose -f compose/docker-compose.yml --profile ollama exec ollama ollama pull tinyllama"
