#!/usr/bin/env bash
set -euo pipefail
PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"
for candidate in python3.11 python3.12 python3 python; do
  if command -v "$candidate" >/dev/null 2>&1; then
    exec "$candidate" scripts/setup_env.py
  fi
done
echo "请先安装 64 位 Python 3.11 或 3.12，再运行 bash setup.sh。" >&2
exit 1
