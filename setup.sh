#!/usr/bin/env bash
set -euo pipefail
PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"
if command -v python3.11 >/dev/null 2>&1; then
  exec python3.11 scripts/setup_env.py
else
  exec python3 scripts/setup_env.py
fi
