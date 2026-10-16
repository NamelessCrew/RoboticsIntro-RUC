#!/usr/bin/env bash
# 在仓库根目录运行，统一 Python、缓存和 Vulkan 配置。
set -euo pipefail
PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"
export PYTHONPATH="$PROJECT_DIR${PYTHONPATH:+:$PYTHONPATH}"
export MPLCONFIGDIR="$PROJECT_DIR/.cache/matplotlib"
export XDG_CACHE_HOME="$PROJECT_DIR/.cache"
export MS_ASSET_DIR="$PROJECT_DIR/.assets"
export PYTHONUNBUFFERED=1
mkdir -p "$MPLCONFIGDIR" "$MS_ASSET_DIR"

if [[ ! -x .venv/bin/python ]]; then
    echo '未找到 .venv，请先运行 bash setup.sh。' >&2
    exit 1
fi

# macOS 的 Vulkan 由 MoltenVK 转接到 Metal。允许传 SDK 根目录或 macOS 子目录。
if [[ "$(uname -s)" == Darwin ]]; then
    export VULKAN_SDK="${VULKAN_SDK:-$HOME/VulkanSDK/1.3.290.0/macOS}"
    if [[ -f "$VULKAN_SDK/macOS/share/vulkan/icd.d/MoltenVK_icd.json" ]]; then
        export VULKAN_SDK="$VULKAN_SDK/macOS"
    fi
    if [[ ! -f "$VULKAN_SDK/share/vulkan/icd.d/MoltenVK_icd.json" ]]; then
        echo '未找到 Vulkan SDK。请按 README 安装，并设置 VULKAN_SDK。' >&2
        exit 1
    fi
    export PATH="$VULKAN_SDK/bin:$PATH"
    export VK_ICD_FILENAMES="$VULKAN_SDK/share/vulkan/icd.d/MoltenVK_icd.json"
    export VK_DRIVER_FILES="$VK_ICD_FILENAMES"
    export VK_LAYER_PATH="$VULKAN_SDK/share/vulkan/explicit_layer.d"
    export DYLD_LIBRARY_PATH="$VULKAN_SDK/lib${DYLD_LIBRARY_PATH:+:$DYLD_LIBRARY_PATH}"
fi

if [[ "${1:-}" == doctor ]]; then
    shift
    exec "$PROJECT_DIR/.venv/bin/python" -m scripts.doctor "$@"
fi
if [[ "${1:-}" == python ]]; then
    shift
    exec "$PROJECT_DIR/.venv/bin/python" "$@"
fi
# 不传参数时，experiments 默认运行 scene 并保存图片。
exec "$PROJECT_DIR/.venv/bin/python" -m chapters.week06.experiments "$@"
