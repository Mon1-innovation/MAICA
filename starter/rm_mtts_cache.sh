#!/bin/bash

# 目标目录
TARGET_DIR="../maica/fs_storage/mtts"

# 检查目录是否存在
if [ ! -d "$TARGET_DIR" ]; then
    echo "警告: 目录 '$TARGET_DIR' 不存在!"
    exit 1
fi

# 切换到目标目录
cd "$TARGET_DIR" || exit 1

# 统计并删除文件（排除.gitignore）
count=$(find . -maxdepth 1 -type f ! -name '.gitignore' ! -name '.' | wc -l)

if [ "$count" -eq 0 ]; then
    echo "目录中除了.gitignore外没有其他文件。"
    exit 0
fi

# 执行删除
find . -maxdepth 1 -type f ! -name '.gitignore' ! -name '.' -delete

echo "已删除 $count 个文件。"