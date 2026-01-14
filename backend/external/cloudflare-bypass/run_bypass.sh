#!/bin/bash
# Cloudflare Bypass 主机调用脚本
# 用法: ./run_bypass.sh <URL> [options]

set -e

# 镜像名称
IMAGE_NAME="cloudflare-bypass"

# 检查参数
if [ $# -lt 1 ]; then
    echo "用法: $0 <URL> [options]"
    echo ""
    echo "选项:"
    echo "  --output-json    输出纯 JSON 格式（推荐用于脚本调用）"
    echo "  --wait N         初始等待时间（秒），默认 5"
    echo "  --max-wait N     最大等待时间（秒），默认 50"
    echo "  --retry N        最大重试次数，默认 1"
    echo ""
    echo "示例:"
    echo "  $0 https://example.com --output-json"
    echo "  $0 https://example.com --wait 10 --max-wait 60"
    echo ""
    echo "获取 cookies 并用 curl 请求:"
    echo '  RESULT=$($0 https://example.com --output-json)'
    echo '  CF_COOKIE=$(echo "$RESULT" | jq -r ".cookies.cf_clearance")'
    echo '  curl -H "Cookie: cf_clearance=$CF_COOKIE" https://example.com/api'
    exit 1
fi

# 检查 Docker 是否运行
if ! docker info > /dev/null 2>&1; then
    echo "[!] Docker 未运行或无权限访问" >&2
    exit 1
fi

# 检查镜像是否存在
if ! docker image inspect "$IMAGE_NAME" > /dev/null 2>&1; then
    echo "[!] 镜像 $IMAGE_NAME 不存在，请先构建:" >&2
    echo "    cd $(dirname "$0") && docker build -t $IMAGE_NAME ." >&2
    exit 1
fi

# 运行容器
# --rm: 运行后自动删除容器
# --shm-size=2g: 增加共享内存，防止 Chrome 崩溃
docker run --rm \
    --shm-size=2g \
    "$IMAGE_NAME" \
    "$@"
