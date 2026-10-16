#!/usr/bin/env bash
# 安装到本仓库的 .venv，不修改系统 Python。可重复执行。
set -euo pipefail
PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"
export UV_CACHE_DIR="${UV_CACHE_DIR:-$PROJECT_DIR/.cache/uv}"
if ! command -v uv >/dev/null 2>&1; then
    echo '请先安装 uv：https://docs.astral.sh/uv/getting-started/installation/' >&2
    exit 1
fi
if [[ ! -x .venv/bin/python ]]; then
    uv venv --python 3.10 .venv
fi
.venv/bin/python -c 'import sys; assert sys.version_info[:2] == (3, 10), "本课请使用 Python 3.10；已有环境版本不同，请将 .venv 改名后重新安装。"'
if [[ "$(uname -s)" == Darwin ]]; then
    uv pip install --python .venv/bin/python -r requirements-macos.lock.txt
else
    uv pip install --python .venv/bin/python -r requirements.txt
fi
uv pip check --python .venv/bin/python
# 导入检查不创建场景，Vulkan 是否可用由后续 scene 验证。
.venv/bin/python -m scripts.doctor
echo '依赖安装完成。接着运行：bash run.sh scene'
echo '交互窗口：bash run.sh scene --human --seconds 120'
