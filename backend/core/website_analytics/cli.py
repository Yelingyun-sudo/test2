from __future__ import annotations

"""
cli.py 文件是 Website Analytics 项目的命令行入口模块。它提供了两种主要的执行模式：

    单任务模式：直接传入一条自然语言指令，执行并输出结果。
    批次模式：从一个文本文件中读取多条指令，并发执行它们（可控制最大并发数）。

模块内部封装了底层协调器（orchestrator）的调用，并统一处理了格式化和退出码，使得该 CLI 既可以作为终端用户直接调用的工具，也可以作为其他模块（如任务调度器）的异步调用接口。
"""
"""
整体结构
解析命令行参数
根据模式执行（单任务 / 批处理）
格式化并输出结果
提供同步和异步的执行函数供内部使用
"""
import argparse
import asyncio
import logging
import sys
from pathlib import Path

from agents import set_tracing_disabled

from website_analytics.formatter import format_execution_result
from website_analytics.orchestrator import ExecutionResult, execute, execute_batch


# 作用：定义并解析命令行参数。
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Website Analytics entrypoint.")
    group = parser.add_mutually_exclusive_group(required=True)
    # 单任务模式，直接提供指令文本。(互斥组)
    group.add_argument(
        "--instruction",
        help="要交给协调代理的顶层指令（单任务模式）。",
    )
    # 批次模式，指定包含指令列表的文件路径（每行一个指令，支持 # 注释）。（互斥组）
    group.add_argument(
        "--batch-file",
        type=Path,
        help="包含多个任务指令的文件路径，每行一个指令（批次并发模式）。",
    )
    # 批次模式下的最大并发任务数，默认无限制（None）。
    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=None,
        help="批次模式下的最大并发任务数（默认无限制）。",
    )
    # 以无头模式运行浏览器（不显示 UI 界面）
    parser.add_argument(
        "--headless",
        action="store_true",
        help="以无头模式运行浏览器（不显示界面）。",
    )
    return parser.parse_args()


"""作用：处理单任务的执行结果，格式化并输出到标准输出（成功）或标准错误（失败），并以适当的退出码退出进程。
逻辑：
调用 format_execution_result(result) 将 ExecutionResult 格式化为人类可读的字符串（可能包含成功信息、错误详情等）。
如果执行成功，将格式化结果打印到 stdout，然后以 SystemExit(0) 正常退出。
如果执行失败，将格式化结果打印到 stderr，并使用 result.exit_code 作为退出码（默认 1）退出。
"""


def _handle_result(result: ExecutionResult) -> None:
    formatted = format_execution_result(result)

    if result.success:
        print(formatted)
        raise SystemExit(0)

    print(formatted, file=sys.stderr)
    raise SystemExit(result.exit_code or 1)


# 作用：读取批处理文件，过滤空行和注释（以 # 开头的行），返回指令列表。
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


# CLI 主入口（命令行模式）,负责解析参数，调度执行，处理异常
"""
流程：
配置日志级别为 INFO（简单格式）
禁用 tracing 功能（set_tracing_disabled(True)），避免可能的 401 错误（某些 API 调用需要关闭 tracing）。
解析参数。
参数验证：如果 --max-concurrent 小于 1 则报错；如果批次模式与 --max-concurrent 同时存在但又是单任务模式，则给出警告。
根据参数分支：
    如果 batch_file 存在：进入批次模式。
        读取文件获取指令列表。
        如果列表为空则报错。
        使用 asyncio.run(execute_batch(...)) 异步执行批处理任务。
    否则进入单任务模式：
        调用 run_single_instruction(...) 同步执行。
        将结果传入 _handle_result 进行处理。
捕获所有未预期的异常，打印错误并以退出码 2 退出。
"""


def main() -> None:
    # 配置日志级别为 INFO，确保调试信息可见
    logging.basicConfig(level=logging.INFO, format="%(message)s")

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
            result = run_single_instruction(args.instruction, headless=args.headless)
            _handle_result(result)
    except Exception as exc:  # pragma: no cover - defensive guard for event loop errors
        print(f"执行失败：{exc}", file=sys.stderr)
        raise SystemExit(2) from exc


# 同步执行入口，CLI 使用
# 作用：同步执行单条指令，返回 ExecutionResult 对象。
def run_single_instruction(
    instruction: str, *, headless: bool = False
) -> ExecutionResult:
    """供内部调用的单任务执行入口，返回 ExecutionResult。"""

    # 确保 tracing 关闭（与 CLI 行为一致）
    set_tracing_disabled(True)

    return asyncio.run(
        execute(
            instruction,
            headless=headless,
        )
    )


# 异步执行入口，供调度器调用
# 作用：异步执行单条指令，返回 ExecutionResult 对象。
async def run_single_instruction_async(
    instruction: str, *, headless: bool = False
) -> ExecutionResult:
    """供异步场景调用的单任务执行入口，返回 ExecutionResult。

    与 `run_single_instruction()` 不同：不创建新 event loop，便于在外部用
    `asyncio.wait_for()` 做可靠超时控制与取消清理。
    """

    # 确保 tracing 关闭（与 CLI 行为一致）
    set_tracing_disabled(True)

    return await execute(
        instruction,
        headless=headless,
    )
