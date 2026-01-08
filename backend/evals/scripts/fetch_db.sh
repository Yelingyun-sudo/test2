#!/bin/bash

# 从线上服务器拉取数据库到评估目录
# 使用方法：在 backend/evals/ 目录下执行 ./fetch_db.sh

set -e

REMOTE_HOST="root@8.216.39.224"
REMOTE_PATH="/opt/website_analytics/backend/db/wa.db"
LOCAL_PATH="./data/wa.db"

echo "开始从线上服务器拉取数据库..."
echo "远程地址: ${REMOTE_HOST}:${REMOTE_PATH}"
echo "本地路径: ${LOCAL_PATH}"

# 确保 data 目录存在
mkdir -p ./data

# 执行 scp 拉取
if scp "${REMOTE_HOST}:${REMOTE_PATH}" "${LOCAL_PATH}"; then
    echo "✓ 数据库拉取成功！"
    
    # 验证文件是否为有效的 SQLite 数据库
    if command -v sqlite3 &> /dev/null; then
        if sqlite3 "${LOCAL_PATH}" "SELECT name FROM sqlite_master WHERE type='table' LIMIT 1;" &> /dev/null; then
            echo "✓ 数据库文件有效"
            echo "文件大小: $(du -h "${LOCAL_PATH}" | cut -f1)"
        else
            echo "✗ 警告：文件可能不是有效的 SQLite 数据库"
            exit 1
        fi
    else
        echo "⚠ 未安装 sqlite3，跳过数据库有效性检查"
    fi
else
    echo "✗ 数据库拉取失败！"
    exit 1
fi
