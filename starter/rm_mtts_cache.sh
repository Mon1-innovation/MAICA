#!/usr/bin/env bash
set -euo pipefail

# 目标目录
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="$SCRIPT_DIR/../maica/fs_storage/mtts"

# 检查目录是否存在
if [ ! -d "$TARGET_DIR" ]; then
    echo "警告: 目录 '$TARGET_DIR' 不存在!"
    exit 1
fi

# 切换到目标目录
cd "$TARGET_DIR"

# 统计并删除文件（排除.gitignore）
count=$(find . -maxdepth 1 -type f ! -name '.gitignore' | wc -l)

if [ "$count" -eq 0 ]; then
    echo "目录中除了.gitignore外没有其他文件。"
    exit 0
fi

# 执行删除
find . -maxdepth 1 -type f ! -name '.gitignore' -delete

echo "已删除 $count 个文件。"
