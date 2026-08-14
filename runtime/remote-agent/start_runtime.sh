#!/usr/bin/env bash
# Start / stop a lightweight runtime marker on the customer host (Phase 4).
# Real vLLM/Ollama launch is left to operators; this script is the control-plane hook.
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
STATE="$DIR/state"
mkdir -p "$STATE"

TENANT=""
INSTANCE=""
PRESET=""
BACKEND="ollama"
STOP=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tenant) TENANT="$2"; shift 2 ;;
    --instance) INSTANCE="$2"; shift 2 ;;
    --preset) PRESET="$2"; shift 2 ;;
    --backend) BACKEND="$2"; shift 2 ;;
    --stop) STOP=1; shift ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

if [[ -z "$INSTANCE" ]]; then
  echo "instance required" >&2
  exit 2
fi

MARKER="$STATE/${INSTANCE}.json"

if [[ "$STOP" -eq 1 ]]; then
  rm -f "$MARKER"
  echo "stopped $INSTANCE"
  exit 0
fi

cat >"$MARKER" <<EOF
{"tenant":"${TENANT}","instance":"${INSTANCE}","preset":"${PRESET}","backend":"${BACKEND}","status":"running"}
EOF
echo "started $INSTANCE backend=$BACKEND preset=$PRESET"
# Optional: call local start scripts if present
if [[ "$BACKEND" == "vllm" && -x "$DIR/../vllm/start_single_gpu.sh" ]]; then
  echo "hint: run ../vllm/start_single_gpu.sh on this host for real inference"
fi
