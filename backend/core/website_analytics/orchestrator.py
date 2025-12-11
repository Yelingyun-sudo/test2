from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from agents import (
    ModelSettings,
    RunConfig,
    RunHooks,
    Runner,
    enable_verbose_stdout_logging,
)
from agents.logger import logger

from website_analytics.agent_factory import (
    build_coordinator_agent,
    build_extract_agent,
    build_inspect_agent,
    build_inspect_entry_agent,
    build_login_agent,
    extract_structured_output,
)
from website_analytics.batch_reporter import (
    TaskResult,
    generate_batch_report,
    print_batch_summary,
    print_task_complete,
    print_task_start,
    save_task_summary,
)
from website_analytics.filters import build_call_model_input_filter
from website_analytics.formatter import format_execution_result
from website_analytics.llm_logging import LLMTranscriptLoggerHooks
from website_analytics.playwright_server import AutoSwitchingPlaywrightServer
from website_analytics.output_types import ErrorType
from website_analytics.settings import get_settings
from website_analytics.tools import (
    build_compile_inspect_report_tool,
    build_save_entry_result_tool,
    build_save_page_text_tool,
)
from website_analytics.utils import (
    LOGS_DIR,
    build_playwright_args,
    generate_task_directory,
    load_instruction,
    to_project_relative,
)


@dataclass
class ExecutionResult:
    success: bool
    exit_code: int = 0
    task_dir: Path | None = None
    coordinator_output: dict[str, Any] | None = None

    @property
    def message(self) -> str:
        """安全提取用户消息。"""
        if self.coordinator_output and "message" in self.coordinator_output:
            return self.coordinator_output["message"]
        return "无输出信息"


@dataclass
class ExplorerRunContext:
    task_dir: Path


settings = get_settings()


async def execute(
    instruction: str,
    *,
    task_dir: Path | None = None,
    enable_logging: bool = True,
    task_index: int = 1,
    headless: bool = False,
) -> ExecutionResult:
    start_time = datetime.now()
    working_dir = task_dir or generate_task_directory()
    working_dir.mkdir(parents=True, exist_ok=True)

    if enable_logging:
        enable_verbose_stdout_logging()

    capture_llm_state = settings.llm_snapshot
    capture_llm_full_page = settings.llm_snapshot_fullpage
    llm_hooks: RunHooks = LLMTranscriptLoggerHooks(
        working_dir / "llm",
        capture_browser_state=capture_llm_state,
        capture_full_page=capture_llm_full_page,
    )

    run_context = ExplorerRunContext(task_dir=working_dir)
    call_model_filter = build_call_model_input_filter(compact_enabled=True)
    model_settings = ModelSettings(
        store=False,
        tool_choice="auto",
    )
    # Subagent 使用带 compact filter 的 run_config（节省 context）
    run_config = RunConfig(
        call_model_input_filter=call_model_filter,
        model_settings=model_settings,
    )
    # Coordinator 使用不带 filter 的 run_config（需要看到所有工具输出）
    coordinator_run_config = RunConfig(
        model_settings=model_settings,
    )

    try:
        playwright_args = build_playwright_args(working_dir, headless=headless)
        playwright_env = {
            key: value
            for key, value in os.environ.items()
            if key in {"DISPLAY", "XAUTHORITY"} and value
        }
        save_page_text_tool = build_save_page_text_tool(working_dir)
        save_entry_result_tool = build_save_entry_result_tool(working_dir)
        compile_inspect_report_tool = build_compile_inspect_report_tool(working_dir)

        playwright_params: dict[str, Any] = {
            "command": "npx",
            "args": [*playwright_args],
        }
        if playwright_env:
            playwright_params["env"] = playwright_env

        async with AutoSwitchingPlaywrightServer(
            name="playwright-mcp",
            params=playwright_params,
            client_session_timeout_seconds=120,
        ) as playwright_server:
            if hasattr(llm_hooks, "set_playwright_server"):
                llm_hooks.set_playwright_server(playwright_server)
            inspect_entry_agent = build_inspect_entry_agent(
                playwright_server,
                load_instruction("inspect_entry_agent.md"),
                extra_tools=[save_page_text_tool, save_entry_result_tool],
            )
            inspect_entry_tool = inspect_entry_agent.as_tool(
                tool_name="inspect_entry",
                tool_description="巡检单个一级菜单并生成对应产物。",
                max_turns=40,
                hooks=llm_hooks,
                run_config=run_config,
                custom_output_extractor=extract_structured_output,
            )

            login_agent = build_login_agent(
                playwright_server,
                load_instruction("login_agent.md"),
            )
            extract_agent = build_extract_agent(
                playwright_server,
                load_instruction("extract_agent.md"),
            )
            inspect_agent = build_inspect_agent(
                playwright_server,
                load_instruction(
                    "inspect_agent.md",
                    replacements={
                        "{MAX_MENU_ENTRIES}": str(settings.inspect_max_menu_entries)
                    },
                ),
                extra_tools=[
                    save_page_text_tool,
                    inspect_entry_tool,
                    compile_inspect_report_tool,
                ],
            )
            coordinator_agent = build_coordinator_agent(
                login_agent,
                extract_agent,
                inspect_agent,
                load_instruction("coordinator_agent.md"),
                child_hooks=llm_hooks,
                run_config=run_config,
            )

            coordinator_result = await Runner.run(
                coordinator_agent,
                instruction,
                max_turns=50,
                hooks=llm_hooks,
                context=run_context,
                run_config=coordinator_run_config,
            )

        final_output_obj = coordinator_result.final_output

        # 使用结构化输出
        if hasattr(final_output_obj, "status") and hasattr(final_output_obj, "message"):
            # CoordinatorOutput 类型
            status_value = getattr(final_output_obj, "status", "")
            status_normalized = str(status_value).lower()
            success = status_normalized == "success"
            exit_code = 0 if success else 1

            # 提取完整结构化输出
            if hasattr(final_output_obj, "model_dump"):
                coordinator_output = final_output_obj.model_dump()
                coordinator_output["status"] = status_normalized
            else:
                coordinator_output = {
                    "status": status_normalized,
                    "message": final_output_obj.message,
                    "operations_executed": getattr(
                        final_output_obj, "operations_executed", []
                    ),
                    "operations_results": getattr(
                        final_output_obj, "operations_results", {}
                    ),
                }
            if success:
                coordinator_output["error_type"] = None
            else:
                coordinator_output["error_type"] = coordinator_output.get(
                    "error_type"
                ) or ErrorType.UNKNOWN_ERROR.value

            # 记录额外信息到日志
            logger.info(
                f"Task completed: status={status_normalized}, "
                f"operations={final_output_obj.operations_executed}"
            )
        else:
            # fast fail: 非预期类型直接构造 FAILED
            logger.error(
                f"Unexpected output type from coordinator: {type(final_output_obj)}"
            )
            coordinator_output = {
                "status": "failed",
                "message": f"内部错误：协调代理返回了非预期的输出类型 {type(final_output_obj)}",
                "error_type": ErrorType.UNKNOWN_ERROR.value,
                "operations_executed": [],
                "operations_results": {},
            }
            success = False
            exit_code = 1

        result = ExecutionResult(
            success=success,
            exit_code=exit_code,
            task_dir=working_dir,
            coordinator_output=coordinator_output,
        )
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # 保存任务总结（单任务模式）
        if enable_logging:
            _save_single_task_summary(
                instruction=instruction,
                result=result,
                task_index=task_index,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
            )

        return result
    except Exception as exc:
        # fast fail: 构造标准的失败输出
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        coordinator_output = {
            "status": "failed",
            "message": f"执行失败：{exc}",
            "error_type": ErrorType.UNKNOWN_ERROR.value,
            "operations_executed": [],
            "operations_results": {},
        }
        result = ExecutionResult(
            success=False,
            exit_code=2,
            task_dir=working_dir,
            coordinator_output=coordinator_output,
        )

        # 保存任务总结（单任务模式，即使失败也保存）
        if enable_logging:
            _save_single_task_summary(
                instruction=instruction,
                result=result,
                task_index=task_index,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
            )

        return result


def _save_single_task_summary(
    instruction: str,
    result: ExecutionResult,
    task_index: int,
    *,
    start_time: datetime | None,
    end_time: datetime | None,
    duration_seconds: float | None,
) -> None:
    """保存单个任务的总结文件（用于单任务模式）。"""
    if not result.task_dir:
        return

    task_id = result.task_dir.name
    relative_task_dir = to_project_relative(result.task_dir)
    start = start_time.isoformat() if start_time else ""
    end = end_time.isoformat() if end_time else ""
    duration = duration_seconds if duration_seconds is not None else 0.0
    task_summary = TaskResult(
        task_id=task_id,
        index=task_index,
        instruction=instruction,
        duration_seconds=duration,
        task_dir=relative_task_dir,
        coordinator_output=result.coordinator_output,
        exit_code=result.exit_code,
        start_time=start,
        end_time=end,
    )
    save_task_summary(task_summary, result.task_dir)


async def _execute_single_task(
    index: int,
    instruction: str,
    headless: bool = False,
) -> TaskResult:
    """执行单个任务并返回结果。"""
    start_time = datetime.now()
    print_task_start(index, instruction)
    result = await execute(
        instruction,
        enable_logging=False,
        task_index=index,
        headless=headless,
    )

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    status_raw = (result.coordinator_output or {}).get("status")
    status = str(status_raw).lower() if status_raw is not None else (
        "success" if result.success else "failed"
    )
    print_task_complete(index, status, duration)

    # 打印详细的任务结果
    formatted = format_execution_result(result)
    print(formatted)
    print()  # 添加空行分隔

    task_id = result.task_dir.name if result.task_dir else ""
    relative_task_dir = to_project_relative(result.task_dir) if result.task_dir else ""

    task_result = TaskResult(
        task_id=task_id,
        index=index,
        instruction=instruction,
        duration_seconds=duration,
        task_dir=relative_task_dir,
        coordinator_output=result.coordinator_output,
        exit_code=result.exit_code,
        start_time=start_time.isoformat(),
        end_time=end_time.isoformat(),
    )

    # 立即保存任务总结
    if result.task_dir:
        save_task_summary(task_result, result.task_dir)

    return task_result


async def execute_batch(
    instructions: list[str],
    max_concurrent: int | None = None,
    headless: bool = False,
) -> None:
    """并发执行多个任务并生成汇总报告。

    Args:
        instructions: 任务指令列表
        max_concurrent: 最大并发任务数，None 表示无限制
        headless: 是否使用无头模式，默认 False
    """
    if not instructions:
        print("错误：没有要执行的任务")
        return

    # 生成批次任务目录
    batch_id = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    batch_dir = LOGS_DIR / batch_id
    batch_dir.mkdir(parents=True, exist_ok=True)

    # 启用日志
    enable_verbose_stdout_logging()

    # 打印批次任务启动信息
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print("=" * 60)
    print(f"[{timestamp}] 启动批次任务，共 {len(instructions)} 个任务")
    print(f"批次 ID: {batch_id}")
    if max_concurrent:
        print(f"并发限制: 最多同时运行 {max_concurrent} 个任务")
    else:
        print("并发限制: 无限制（所有任务同时启动）")
    print(f"浏览器模式: {'无头模式' if headless else '有界面模式'}")
    print("=" * 60)
    print()

    start_time = datetime.now()

    # 创建 Semaphore 用于并发控制
    semaphore = asyncio.Semaphore(max_concurrent) if max_concurrent else None

    # 包装任务执行以支持并发限制
    async def run_with_limit(index: int, instruction: str) -> TaskResult:
        if semaphore:
            async with semaphore:
                return await _execute_single_task(
                    index,
                    instruction,
                    headless=headless,
                )
        else:
            return await _execute_single_task(
                index,
                instruction,
                headless=headless,
            )

    # 并发执行所有任务
    tasks = [
        run_with_limit(i + 1, instruction) for i, instruction in enumerate(instructions)
    ]
    results = await asyncio.gather(*tasks, return_exceptions=False)

    end_time = datetime.now()
    total_duration = (end_time - start_time).total_seconds()

    # 生成汇总报告
    generate_batch_report(
        batch_id=batch_id,
        batch_dir=batch_dir,
        tasks=results,
        start_time=start_time,
        end_time=end_time,
    )

    # 打印汇总信息
    success_count = sum(1 for r in results if r.status == "success")
    failed_count = len(results) - success_count
    print_batch_summary(
        total=len(results),
        success=success_count,
        failed=failed_count,
        duration=total_duration,
        summary_path=batch_dir / "summary.md",
    )
