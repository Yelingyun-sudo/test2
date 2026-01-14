#!/bin/bash
# Cloudflare Bypass 容器入口脚本
# 启动 Xvfb 虚拟显示并运行 Python 脚本

set -e

# 启动 Xvfb 虚拟显示（后台运行）
echo "[*] Starting Xvfb virtual display on :99..." >&2
Xvfb :99 -screen 0 1920x1080x24 -ac +extension GLX +render -noreset &
XVFB_PID=$!

# 等待 Xvfb 启动
sleep 2

# 检查 Xvfb 是否成功启动
if ! kill -0 $XVFB_PID 2>/dev/null; then
    echo "[!] Failed to start Xvfb" >&2
    exit 1
fi

echo "[*] Xvfb started successfully (PID: $XVFB_PID)" >&2

# 设置 DISPLAY 环境变量
export DISPLAY=:99

# 运行 Python 脚本，传递所有参数
echo "[*] Running bypass script..." >&2
python /app/bypass_cloudflare_docker.py "$@"
EXIT_CODE=$?

# 清理：停止 Xvfb
echo "[*] Cleaning up..." >&2
kill $XVFB_PID 2>/dev/null || true

exit $EXIT_CODE
