#!/usr/bin/env bash
# Install remote-agent helpers on a customer machine (Phase 4).
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
chmod +x "$DIR"/*.sh 2>/dev/null || true
mkdir -p "$DIR/logs" "$DIR/data"
echo "WeightGate remote-agent installed at $DIR"
"$DIR/healthcheck.sh"
