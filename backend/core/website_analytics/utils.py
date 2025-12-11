from __future__ import annotations

import random
import string
from datetime import datetime
from pathlib import Path

from website_analytics.settings import get_settings


def find_project_root() -> Path:
    """向上查找含 pyproject.toml 的目录，作为项目根。"""

    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    return current.parent.parent


PROJECT_ROOT = find_project_root()
INSTRUCTIONS_DIR = PROJECT_ROOT / "instructions"
LOGS_DIR = PROJECT_ROOT / "logs"

BASE_PLAYWRIGHT_ARGS = (
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


def load_instruction(filename: str, replacements: dict[str, str] | None = None) -> str:
    instruction_path = INSTRUCTIONS_DIR / filename
    text = instruction_path.read_text(encoding="utf-8").strip()
    if replacements:
        for key, value in replacements.items():
            text = text.replace(key, value)
    return text


def build_playwright_args(output_dir: Path, headless: bool = False) -> list[str]:
    """构建 Playwright 参数。

    Args:
        output_dir: 输出目录
        headless: 是否使用无头模式，默认 False

    Returns:
        Playwright 参数列表
    """
    settings = get_settings()

    # 构建基础参数
    args = [
        arg.format(output_dir=str(output_dir)) if "{output_dir}" in arg else arg
        for arg in BASE_PLAYWRIGHT_ARGS
    ]

    # 代理设置
    if settings.playwright_proxy_server:
        args.append(f"--proxy-server={settings.playwright_proxy_server}")

    # 如果启用 headless，添加 --headless 参数
    if headless:
        args.append("--headless")

    return args


def generate_task_directory(root: Path | None = None) -> Path:
    base_dir = root if root is not None else LOGS_DIR
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
    task_dir = base_dir / f"task_{timestamp}_{suffix}"
    task_dir.mkdir(parents=True, exist_ok=True)
    return task_dir


def to_project_relative(path: Path) -> str:
    """返回相对于项目根目录的路径，不可相对时退回绝对路径。"""

    try:
        return path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path)
