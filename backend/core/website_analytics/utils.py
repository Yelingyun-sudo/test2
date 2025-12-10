from __future__ import annotations

import random
import string
from datetime import datetime
from pathlib import Path

from website_analytics.config import (
    INSTRUCTIONS_DIR,
    PLAYWRIGHT_ARGS_TEMPLATE,
    PROJECT_ROOT,
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
    # 构建基础参数
    args = [
        arg.format(output_dir=str(output_dir)) if "{output_dir}" in arg else arg
        for arg in PLAYWRIGHT_ARGS_TEMPLATE
    ]

    # 如果启用 headless，添加 --headless 参数
    if headless:
        args.append("--headless")

    return args


def generate_task_directory(root: Path | None = None) -> Path:
    base_dir = root if root is not None else PROJECT_ROOT / "logs"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
    task_dir = base_dir / f"task_{timestamp}_{suffix}"
    task_dir.mkdir(parents=True, exist_ok=True)
    return task_dir
