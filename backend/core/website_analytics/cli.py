from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from agents import set_tracing_disabled

from website_analytics.formatter import format_execution_result
from website_analytics.orchestrator import ExecutionResult, execute, execute_batch


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Website Analytics entrypoint.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--instruction",
        help="要交给协调代理的顶层指令（单任务模式）。",
    )
    group.add_argument(
        "--batch-file",
        type=Path,
        help="包含多个任务指令的文件路径，每行一个指令（批次并发模式）。",
    )
    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=None,
        help="批次模式下的最大并发任务数（默认无限制）。",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="以无头模式运行浏览器（不显示界面）。",
    )
    return parser.parse_args()


def _handle_result(result: ExecutionResult) -> None:
    formatted = format_execution_result(result)

    if result.success:
        print(formatted)
        raise SystemExit(0)

    print(formatted, file=sys.stderr)
    raise SystemExit(result.exit_code or 1)


def _read_batch_file(file_path: Path) -> list[str]:
    """从文件中读取批次任务列表。"""
    if not file_path.exists():
        print(f"错误：文件不存在 - {file_path}", file=sys.stderr)
        raise SystemExit(1)

    try:
        content = file_path.read_text(encoding="utf-8")
        # 过滤掉空行和注释行（以 # 开头）
        instructions = [
            line.strip()
            for line in content.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        return instructions
    except Exception as exc:
        print(f"错误：读取文件失败 - {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


def main() -> None:
    # 禁用 tracing 功能，避免 401 错误
    set_tracing_disabled(True)

    args = parse_args()

    # 参数验证
    if args.max_concurrent is not None and args.max_concurrent < 1:
        print("错误：--max-concurrent 必须是正整数", file=sys.stderr)
        raise SystemExit(1)

    if args.max_concurrent and args.instruction:
        print("警告：单任务模式下 --max-concurrent 参数无效", file=sys.stderr)

    try:
        if args.batch_file:
            # 批次并发模式
            instructions = _read_batch_file(args.batch_file)
            if not instructions:
                print("错误：批次文件中没有有效的任务指令", file=sys.stderr)
                raise SystemExit(1)
            asyncio.run(
                execute_batch(
                    instructions,
                    max_concurrent=args.max_concurrent,
                    headless=args.headless,
                )
            )
        else:
            # 单任务模式
            result = asyncio.run(
                execute(
                    args.instruction,
                    headless=args.headless,
                )
            )
            _handle_result(result)
    except Exception as exc:  # pragma: no cover - defensive guard for event loop errors
        print(f"执行失败：{exc}", file=sys.stderr)
        raise SystemExit(2) from exc
