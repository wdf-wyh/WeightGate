#!/usr/bin/env bash
# Multi-LoRA vLLM server (same base, multiple adapters) — Phase 3 template.
#
# Layout expected (per tenant):
#   data/tenants/{TENANT_ID}/loras/{adapter_name}/   # adapter weights (not in git)
#   data/tenants/{TENANT_ID}/models/{base}/          # optional local base
#
# Usage:
#   TENANT_ID=tenant_a MODEL=Qwen/Qwen2.5-7B-Instruct \
#     LORA_MODULES="law-v1=./data/tenants/tenant_a/loras/law-v1,trade-v1=./data/tenants/tenant_a/loras/trade-v1" \
#     ./runtime/vllm/start_multi_lora.sh
#
# Client selects adapter via gateway:
#   Header: X-AF-Adapter: loras/law-v1
#   or body: {"adapter":"loras/law-v1", ...}
# Cross-tenant adapter paths still return 403 from the gateway.
#
# Env:
#   MODEL, PORT (8001), MAX_MODEL_LEN, MAX_LORAS, MAX_LORA_RANK, LORA_MODULES, TENANT_ID
set -euo pipefail

MODEL="${MODEL:?set MODEL to a HF id or local path}"
PORT="${PORT:-8001}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-4096}"
GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.90}"
MAX_LORAS="${MAX_LORAS:-4}"
MAX_LORA_RANK="${MAX_LORA_RANK:-16}"
TENANT_ID="${TENANT_ID:-}"

if [[ -z "${LORA_MODULES:-}" ]]; then
  echo "ERROR: set LORA_MODULES as name=path pairs, comma-separated" >&2
  echo "  e.g. LORA_MODULES=law-v1=/data/tenants/tenant_a/loras/law-v1" >&2
  exit 1
fi

# Soft isolation check: every path under LORA_MODULES should contain tenants/{TENANT_ID}/
if [[ -n "${TENANT_ID}" ]]; then
  IFS=',' read -ra _mods <<< "${LORA_MODULES}"
  for pair in "${_mods[@]}"; do
    path="${pair#*=}"
    case "${path}" in
      *"tenants/${TENANT_ID}/"*|*"tenants/${TENANT_ID}") ;;
      *)
        echo "WARN: LoRA path '${path}' does not include tenants/${TENANT_ID}/ — refuse to mix tenants" >&2
        exit 1
        ;;
    esac
  done
fi

exec python -m vllm.entrypoints.openai.api_server \
  --model "${MODEL}" \
  --host 0.0.0.0 \
  --port "${PORT}" \
  --max-model-len "${MAX_MODEL_LEN}" \
  --gpu-memory-utilization "${GPU_MEMORY_UTILIZATION}" \
  --enable-lora \
  --max-loras "${MAX_LORAS}" \
  --max-lora-rank "${MAX_LORA_RANK}" \
  --lora-modules "${LORA_MODULES}" \
  "$@"
