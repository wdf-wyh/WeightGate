#!/usr/bin/env bash
# Customer-host remote agent healthcheck (Phase 4).
set -euo pipefail
echo "af-remote-agent ok"
command -v docker >/dev/null 2>&1 && echo "docker=yes" || echo "docker=no"
command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi -L | head -n 3 || echo "gpu=none"
df -h "$HOME" 2>/dev/null | tail -n 1 || true
