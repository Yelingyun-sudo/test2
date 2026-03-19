# Cloudflare Bypass Docker Image
# 支持 ARM64 和 AMD64 架构

FROM python:3.12-slim

LABEL maintainer="cloudflare-bypass"
LABEL description="Docker image for bypassing Cloudflare Turnstile verification"

# 设置环境变量
ENV DEBIAN_FRONTEND=noninteractive
ENV DISPLAY=:99
ENV PYTHONUNBUFFERED=1

# 安装系统依赖和 Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Xvfb 虚拟显示
    xvfb \
    x11-utils \
    # Chromium 浏览器（支持 ARM64）
    chromium \
    chromium-driver \
    # Chromium 依赖
    fonts-liberation \
    libasound2t64 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    # PyAutoGUI 依赖
    python3-tk \
    python3-dev \
    scrot \
    # 其他工具
    procps \
    && rm -rf /var/lib/apt/lists/*

# 设置 Chromium 环境变量（让 undetected-chromedriver 使用系统 Chromium）
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver

# 创建工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制脚本文件
COPY bypass_cloudflare_docker.py .
COPY entrypoint.sh .

# 设置脚本权限
RUN chmod +x entrypoint.sh

# 入口点
ENTRYPOINT ["/app/entrypoint.sh"]
