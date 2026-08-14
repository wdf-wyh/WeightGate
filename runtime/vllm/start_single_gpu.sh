#!/usr/bin/env bash
# Single-GPU vLLM OpenAI-compatible server (prod / AutoDL).
# Usage:
#   MODEL=Qwen/Qwen2.5-7B-Instruct ./runtime/vllm/start_single_gpu.sh
# Env:
#   MODEL, PORT (8001), MAX_MODEL_LEN, GPU_MEMORY_UTILIZATION, HF_HOME
set -euo pipefail

MODEL="${MODEL:?set MODEL to a HF id or local path}"
PORT="${PORT:-8001}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-4096}"
GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.90}"

exec python -m vllm.entrypoints.openai.api_server \
  --model "${MODEL}" \
  --host 0.0.0.0 \
  --port "${PORT}" \
  --max-model-len "${MAX_MODEL_LEN}" \
  --gpu-memory-utilization "${GPU_MEMORY_UTILIZATION}" \
  "$@"
