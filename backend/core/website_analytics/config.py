from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path

from dotenv import load_dotenv


def find_project_root() -> Path:
    """向上查找含 pyproject.toml 的目录，作为项目根。"""
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    return current.parent.parent


def find_and_load_env():
    """
    按优先级查找并加载 .env 文件：
    1. 当前工作目录的 .env
    2. 项目根目录的 .env（开发模式）
    3. 用户 home 目录的 .explorer-agent.env
    4. 仅依赖环境变量
    """

    # 优先级 1: 当前工作目录
    cwd_env = Path.cwd() / ".env"
    if cwd_env.exists():
        load_dotenv(cwd_env)
        return

    # 优先级 2: 项目根目录（开发模式）
    project_root = find_project_root()
    root_env = project_root / ".env"
    if root_env.exists():
        load_dotenv(root_env)
        return

    # 优先级 3: 用户 home 目录
    home_env = Path.home() / ".explorer-agent.env"
    if home_env.exists():
        load_dotenv(home_env)
        return


# 加载配置
find_and_load_env()

# 项目根目录（用于定位资源）
PROJECT_ROOT = find_project_root()

# 应用基础目录
BASE_DIR = Path(__file__).resolve().parent
INSTRUCTIONS_DIR = PROJECT_ROOT / "instructions"

MODEL_ENV_VAR = "EXPLORER_AGENT_MODEL"
DEFAULT_MODEL = "gpt-5-mini"
MODEL_NAME = os.getenv(MODEL_ENV_VAR, DEFAULT_MODEL)

PLAYWRIGHT_PROXY_ENV_VAR = "PLAYWRIGHT_PROXY_SERVER"
# 移除 PLAYWRIGHT_HEADLESS_ENV_VAR，不再使用环境变量控制 headless

_proxy_server = os.getenv(PLAYWRIGHT_PROXY_ENV_VAR, "").strip() or None

BASE_PLAYWRIGHT_ARGS: Sequence[str] = (
    "@playwright/mcp@latest",
    "--browser=chrome",
    "--no-sandbox",
    "--isolated",
    "--grant-permissions=clipboard-read,clipboard-write",
    "--allowed-hosts=*",
    "--save-trace",
    "--viewport-size=1280x800",
    "--save-video=1280x800",
    "--output-dir={output_dir}",
    "--ignore-https-errors",
    "--caps=vision,pdf",
    "--timeout-action=5000",
    "--timeout-navigation=20000",
)

_playwright_args: list[str] = list(BASE_PLAYWRIGHT_ARGS)

# 移除环境变量自动添加 --headless 的逻辑
# if _headless_enabled:
#     _playwright_args.append("--headless")

if _proxy_server:
    _playwright_args.append(f"--proxy-server={_proxy_server}")

PLAYWRIGHT_ARGS_TEMPLATE: Sequence[str] = tuple(_playwright_args)

INSPECT_MAX_MENU_ENTRIES_ENV_VAR = "INSPECT_MAX_MENU_ENTRIES"
INSPECT_MAX_MENU_ENTRIES = int(os.getenv(INSPECT_MAX_MENU_ENTRIES_ENV_VAR, 3))
