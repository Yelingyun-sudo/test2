from __future__ import annotations

import asyncio
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
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
from agents.mcp import ToolFilterContext

from website_analytics.agent_factory import (
    build_coordinator_agent,
    build_evidence_agent,
    build_extract_agent,
    build_login_agent,
    build_register_agent,
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
from website_analytics.output_types import ErrorType, OperationType
from website_analytics.settings import get_settings
from website_analytics.tools import (
    build_compile_evidence_report_tool,
    build_fetch_email_code_tool,
    build_programmatic_evidence_entry_tool,
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
    llm_usage: dict[str, int] | None = None

    @property
    def message(self) -> str:
        """安全提取用户消息。"""
        if self.coordinator_output and "message" in self.coordinator_output:
            return self.coordinator_output["message"]
        return "无输出信息"


@dataclass
class LLMUsageStats:
    """LLM token 使用统计（运行时累加）。"""

    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cached_tokens: int = 0
    total_reasoning_tokens: int = 0
    total_tokens: int = 0
    llm_turn_count: int = 0

    def to_dict(self) -> dict[str, int] | None:
        """转换为字典格式（用于 JSON 序列化）。

        Returns:
            token 统计字典，如果没有任何 LLM 调用则返回 None
        """
        if self.llm_turn_count == 0:
            return None

        result = {
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_tokens,
            "llm_turns": self.llm_turn_count,
        }

        # 仅包含非零的可选字段
        if self.total_cached_tokens > 0:
            result["total_cached_tokens"] = self.total_cached_tokens

        if self.total_reasoning_tokens > 0:
            result["total_reasoning_tokens"] = self.total_reasoning_tokens

        return result


@dataclass
class TaskContext:
    """任务执行上下文，贯穿整个任务生命周期。"""

    # 任务标识
    task_dir: Path
    task_id: str = ""  # 任务唯一标识（task_dir.name）

    # 任务元数据
    instruction: str = ""  # 任务指令
    index: int = 1  # 任务序号

    # 时间追踪
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # LLM 统计
    llm_usage: LLMUsageStats = field(default_factory=LLMUsageStats)


settings = get_settings()

# Playwright 工具白名单配置
# registerAgent 只能使用指令中明确提到的 5 个核心工具
REGISTER_AGENT_ALLOWED_TOOLS = {
    "browser_navigate",  # 访问 URL
    "browser_snapshot",  # 获取页面状态
    "browser_click",  # 点击元素
    "browser_fill_form",  # 填写表单
    "browser_press_key",  # 按键提交
}


def _normalize_error_type(value: Any) -> str | None:
    """将任意输入规范化为合法的 ErrorType 字符串值。"""
    if value is None:
        return None
    if isinstance(value, ErrorType):
        return value.value
    if isinstance(value, str):
        try:
            return ErrorType(value).value
        except ValueError:
            return None
    return None


def _infer_error_type_from_operations(output: dict[str, Any]) -> str | None:
    """从首个失败的子操作结果中提取 error_type。"""
    operations_results = output.get("operations_results")
    if not isinstance(operations_results, dict):
        return None

    operations_executed = output.get("operations_executed")
    if isinstance(operations_executed, list) and operations_executed:
        ordered_ops = [str(item) for item in operations_executed]
    else:
        ordered_ops = ["login", "extract", "evidence"]

    for op_name in ordered_ops:
        payload = operations_results.get(op_name)
        if not isinstance(payload, dict):
            continue
        if payload.get("success") is False:
            return _normalize_error_type(payload.get("error_type"))

    return None


async def _playwright_tool_filter(context: ToolFilterContext, tool) -> bool:
    """屏蔽特定的 Playwright 工具（黑名单 + 白名单）。

    Args:
        context: 工具过滤上下文，包含 agent 信息
        tool: 工具对象

    Returns:
        True 表示允许该工具，False 表示屏蔽该工具
    """
    # === 全局黑名单（对所有 Agent 生效） ===

    # 屏蔽 browser_handle_dialog
    # 该工具仅用于浏览器原生对话框（alert/confirm），无法处理页面内的 DOM 弹窗
    if tool.name == "browser_handle_dialog":
        return False

    # 屏蔽 browser_run_code
    # 该工具允许执行任意代码，存在安全风险，应使用更安全的替代工具
    if tool.name == "browser_run_code":
        return False

    # === Agent 级别白名单 ===

    agent_name = context.agent.name if context.agent else None

    # registerAgent: 严格限制工具使用（只允许 5 个核心工具）
    if agent_name == "registerAgent":
        return tool.name in REGISTER_AGENT_ALLOWED_TOOLS

    # 其他 Agent 允许所有工具（除全局黑名单外）
    return True


async def execute(
    instruction: str,
    *,
    task_dir: Path | None = None,
    task_index: int = 1,
    headless: bool = False,
) -> ExecutionResult:
    start_time = datetime.now(timezone.utc)
    working_dir = task_dir or generate_task_directory()
    working_dir.mkdir(parents=True, exist_ok=True)

    if settings.agents_verbose_stdout_logging:
        enable_verbose_stdout_logging()

    capture_llm_state = settings.llm_snapshot
    capture_llm_full_page = settings.llm_snapshot_fullpage
    llm_hooks: RunHooks = LLMTranscriptLoggerHooks(
        working_dir / "llm",
        capture_browser_state=capture_llm_state,
        capture_full_page=capture_llm_full_page,
    )

    task_context = TaskContext(
        task_dir=working_dir,
        task_id=working_dir.name,
        instruction=instruction,
        index=task_index,
        start_time=start_time,
    )
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
        # 创建取证报告工具
        compile_evidence_report_tool = build_compile_evidence_report_tool(working_dir)
        # 创建保存页面文本工具（用于保存 evidenceEntryList.txt）
        save_page_text_tool = build_save_page_text_tool(working_dir)

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
            tool_filter=_playwright_tool_filter,
        ) as playwright_server:
            if hasattr(llm_hooks, "set_playwright_server"):
                llm_hooks.set_playwright_server(playwright_server)
            if hasattr(llm_hooks, "set_video_start_t"):
                llm_hooks.set_video_start_t(time.perf_counter())
            # 创建程序化取证工具（替代手动流程）
            programmatic_evidence_entry_tool = build_programmatic_evidence_entry_tool(
                working_dir,
                playwright_server,
            )

            login_agent = build_login_agent(
                playwright_server,
                load_instruction("login_agent.md"),
            )
            # 创建邮箱验证码获取工具（Mock 版本）
            fetch_email_code_tool = build_fetch_email_code_tool()

            register_agent = build_register_agent(
                playwright_server,
                load_instruction(
                    "register_agent.md",
                    replacements={
                        "{REGISTER_ACCOUNT}": settings.register_account,
                        "{REGISTER_PASSWORD}": settings.register_password,
                    },
                ),
                extra_tools=[fetch_email_code_tool],
            )
            extract_agent = build_extract_agent(
                playwright_server,
                load_instruction("extract_agent.md"),
            )
            evidence_agent = build_evidence_agent(
                playwright_server,
                load_instruction(
                    "evidence_agent.md",
                    replacements={
                        "{MAX_MENU_ENTRIES}": str(settings.evidence_max_menu_entries)
                    },
                ),
                extra_tools=[
                    save_page_text_tool,
                    programmatic_evidence_entry_tool,
                    compile_evidence_report_tool,
                ],
            )
            coordinator_agent = build_coordinator_agent(
                login_agent,
                register_agent,
                extract_agent,
                evidence_agent,
                load_instruction("coordinator_agent.md"),
                child_hooks=llm_hooks,
                run_config=run_config,
            )

            coordinator_result = await Runner.run(
                coordinator_agent,
                instruction,
                max_turns=50,
                hooks=llm_hooks,
                context=task_context,
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
                coordinator_output = final_output_obj.model_dump(mode="json")
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
                inferred = _infer_error_type_from_operations(coordinator_output)
                coordinator_output["error_type"] = (
                    inferred
                    or _normalize_error_type(coordinator_output.get("error_type"))
                    or ErrorType.UNKNOWN_ERROR.value
                )

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

        operations_results = coordinator_output.get("operations_results")
        if isinstance(operations_results, dict):
            register_result = operations_results.get(OperationType.REGISTER.value)
            if isinstance(register_result, dict):
                register_result["cover_image_path"] = (
                    _find_last_capture_relative_path_for_agent(
                        working_dir,
                        "registerAgent",
                        offset=1 if register_result.get("success") is True else 0,
                    )
                )

            login_result = operations_results.get(OperationType.LOGIN.value)
            if isinstance(login_result, dict):
                login_result["cover_image_path"] = (
                    _find_last_capture_relative_path_for_agent(
                        working_dir,
                        "loginAgent",
                        offset=1 if login_result.get("success") is True else 0,
                    )
                )

            extract_result = operations_results.get(OperationType.EXTRACT.value)
            if isinstance(extract_result, dict):
                extract_result["cover_image_path"] = (
                    _find_last_capture_relative_path_for_agent(
                        working_dir, "extractAgent"
                    )
                )

            evidence_result = operations_results.get(OperationType.EVIDENCE.value)
            if isinstance(evidence_result, dict):
                # 扫描 evidence 目录，收集所有入口的文件路径
                entries_detail = _scan_evidence_entries(working_dir)
                if entries_detail:
                    evidence_result["entries_detail"] = entries_detail
                    # 设置封面图：使用第一个入口的截图
                    if "cover_image_path" not in evidence_result:
                        first_screenshot = entries_detail[0].get("screenshot")
                        if first_screenshot:
                            evidence_result["cover_image_path"] = first_screenshot

        coordinator_output["video_path"] = _find_last_video_relative_path(working_dir)
        seek_seconds = getattr(llm_hooks, "get_video_seek_seconds", lambda: None)()
        coordinator_output["video_seek_seconds"] = (
            round(seek_seconds, 1) if seek_seconds is not None else None
        )

        # 从 context 获取 LLM token 使用统计
        llm_usage = task_context.llm_usage.to_dict()

        result = ExecutionResult(
            success=success,
            exit_code=exit_code,
            task_dir=working_dir,
            coordinator_output=coordinator_output,
            llm_usage=llm_usage,
        )
        end_time = datetime.now(timezone.utc)

        # 保存任务总结
        _save_single_task_summary(
            context=task_context,
            result=result,
            end_time=end_time,
        )

        return result
    except Exception as exc:
        # fast fail: 构造标准的失败输出
        end_time = datetime.now(timezone.utc)
        coordinator_output = {
            "status": "failed",
            "message": f"执行失败：{exc}",
            "error_type": ErrorType.UNKNOWN_ERROR.value,
            "operations_executed": [],
            "operations_results": {},
        }
        operations_results = coordinator_output.get("operations_results")
        if isinstance(operations_results, dict):
            login_result = operations_results.get("login")
            if isinstance(login_result, dict):
                login_result["cover_image_path"] = (
                    _find_last_capture_relative_path_for_agent(
                        working_dir,
                        "loginAgent",
                        offset=1 if login_result.get("success") is True else 0,
                    )
                )

            extract_result = operations_results.get("extract")
            if isinstance(extract_result, dict):
                extract_result["cover_image_path"] = (
                    _find_last_capture_relative_path_for_agent(
                        working_dir, "extractAgent"
                    )
                )

            evidence_result = operations_results.get("evidence")
            if isinstance(evidence_result, dict):
                # 扫描 evidence 目录，收集所有入口的文件路径
                entries_detail = _scan_evidence_entries(working_dir)
                if entries_detail:
                    evidence_result["entries_detail"] = entries_detail
                    # 设置封面图：使用第一个入口的截图
                    if "cover_image_path" not in evidence_result:
                        first_screenshot = entries_detail[0].get("screenshot")
                        if first_screenshot:
                            evidence_result["cover_image_path"] = first_screenshot
        coordinator_output["video_path"] = _find_last_video_relative_path(working_dir)
        seek_seconds = getattr(llm_hooks, "get_video_seek_seconds", lambda: None)()
        coordinator_output["video_seek_seconds"] = (
            round(seek_seconds, 1) if seek_seconds is not None else None
        )

        # 从 context 获取 LLM token 使用统计
        llm_usage = task_context.llm_usage.to_dict()

        result = ExecutionResult(
            success=False,
            exit_code=2,
            task_dir=working_dir,
            coordinator_output=coordinator_output,
            llm_usage=llm_usage,
        )

        # 保存任务总结（即使失败也保存）
        _save_single_task_summary(
            context=task_context,
            result=result,
            end_time=end_time,
        )

        return result


_CAPTURE_PREFIX_RE = re.compile(r"^(?P<seq>\\d+)-")


def _find_last_capture_relative_path(task_dir: Path) -> str | None:
    """返回任务目录下最后一次 capture 的相对路径（例如 captures/004-xxx.png）。"""
    captures_dir = task_dir / "captures"
    if not captures_dir.is_dir():
        return None

    candidates = list(captures_dir.glob("*.png"))
    if not candidates:
        return None

    def sort_key(path: Path) -> tuple[int, int, str]:
        match = _CAPTURE_PREFIX_RE.match(path.name)
        if not match:
            return (0, -1, path.name)
        return (1, int(match.group("seq")), path.name)

    best = max(candidates, key=sort_key)
    try:
        return best.relative_to(task_dir).as_posix()
    except ValueError:
        return str(best)


def _find_last_capture_relative_path_for_agent(
    task_dir: Path, agent_name: str, *, offset: int = 0
) -> str | None:
    """返回指定 agent 的 capture 相对路径（例如 captures/006-loginAgent_xxx.png）。

    - offset=0: 最新一张
    - offset=1: 倒数第二张（上一轮）
    """
    captures_dir = task_dir / "captures"
    if not captures_dir.is_dir():
        return None

    safe_offset = max(0, int(offset))
    needle = f"-{agent_name}_"
    candidates = [path for path in captures_dir.glob("*.png") if needle in path.name]
    if not candidates:
        return None

    def sort_key(path: Path) -> tuple[int, int, str]:
        match = _CAPTURE_PREFIX_RE.match(path.name)
        if not match:
            return (0, -1, path.name)
        return (1, int(match.group("seq")), path.name)

    ordered = sorted(candidates, key=sort_key)
    index = -(1 + safe_offset) if len(ordered) > safe_offset else -1
    best = ordered[index]
    try:
        return best.relative_to(task_dir).as_posix()
    except ValueError:
        return str(best)


def _find_last_video_relative_path(task_dir: Path) -> str | None:
    """返回任务目录下最新的视频文件相对路径（例如 page-2025-...Z.webm）。"""
    page_candidates = sorted(task_dir.glob("page-*.webm"))
    if page_candidates:
        best = page_candidates[-1]
        try:
            return best.relative_to(task_dir).as_posix()
        except ValueError:
            return str(best)

    candidates = list(task_dir.glob("*.webm"))
    if not candidates:
        return None

    best = max(candidates, key=lambda path: path.stat().st_mtime)
    try:
        return best.relative_to(task_dir).as_posix()
    except ValueError:
        return str(best)


_EVIDENCE_ENTRY_PREFIX_RE = re.compile(r"^(?P<index>\d{2})_(?P<label>.+)$")


def _scan_evidence_entries(task_dir: Path) -> list[dict[str, str]]:
    """扫描 evidence 目录，收集所有入口的文件路径。

    Args:
        task_dir: 任务目录路径

    Returns:
        入口详情列表，每个元素包含 json、screenshot、text 三个文件路径。
        格式：`[{"json": "evidence/01_仪表盘.json", "screenshot": "evidence/01_仪表盘.png", "text": "evidence/01_仪表盘.txt"}, ...]`
        按入口序号排序。
    """
    evidence_dir = task_dir / "evidence"
    if not evidence_dir.is_dir():
        return []

    # 按前缀分组收集文件
    entries_map: dict[int, dict[str, str]] = {}

    # 扫描所有相关文件
    for ext in ["json", "png", "txt"]:
        pattern = f"*.{ext}"
        for file_path in evidence_dir.glob(pattern):
            # 跳过 evidenceEntryList.txt 等非入口文件
            if file_path.name == "evidenceEntryList.txt":
                continue

            stem = file_path.stem
            match = _EVIDENCE_ENTRY_PREFIX_RE.match(stem)
            if not match:
                continue

            index = int(match.group("index"))
            if index not in entries_map:
                entries_map[index] = {}

            # 确定字段名
            if ext == "json":
                field_name = "json"
            elif ext == "png":
                field_name = "screenshot"
            elif ext == "txt":
                field_name = "text"
            else:
                continue

            # 转换为相对路径
            try:
                relative_path = file_path.relative_to(task_dir).as_posix()
            except ValueError:
                relative_path = str(file_path)
            entries_map[index][field_name] = relative_path

    # 按序号排序并转换为列表
    result = []
    for index in sorted(entries_map.keys()):
        entry = entries_map[index]
        # 只包含完整的条目（至少有一个文件）
        if entry:
            result.append(entry)

    return result


def _save_single_task_summary(
    context: TaskContext,
    result: ExecutionResult,
    end_time: datetime,
) -> None:
    """保存单个任务的总结文件（用于单任务模式）。"""
    if not result.task_dir:
        return

    duration = (end_time - context.start_time).total_seconds()
    relative_task_dir = to_project_relative(result.task_dir)
    task_summary = TaskResult(
        task_id=context.task_id,
        index=context.index,
        instruction=context.instruction,
        duration_seconds=duration,
        task_dir=relative_task_dir,
        coordinator_output=result.coordinator_output,
        exit_code=result.exit_code,
        start_time=context.start_time.isoformat(),
        end_time=end_time.isoformat(),
        llm_usage=result.llm_usage,
    )
    save_task_summary(task_summary, result.task_dir)


async def _execute_single_task(
    index: int,
    instruction: str,
    headless: bool = False,
) -> TaskResult:
    """执行单个任务并返回结果。"""
    start_time = datetime.now(timezone.utc)
    print_task_start(index, instruction)
    result = await execute(
        instruction,
        task_index=index,
        headless=headless,
    )

    end_time = datetime.now(timezone.utc)
    duration = (end_time - start_time).total_seconds()

    status_raw = (result.coordinator_output or {}).get("status")
    status = (
        str(status_raw).lower()
        if status_raw is not None
        else ("success" if result.success else "failed")
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
        llm_usage=result.llm_usage,
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

    # 生成批次任务目录（使用 UTC 时间生成目录名）
    batch_id = f"batch_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    batch_dir = LOGS_DIR / batch_id
    batch_dir.mkdir(parents=True, exist_ok=True)

    # 启用日志
    enable_verbose_stdout_logging()

    # 打印批次任务启动信息（使用 UTC 时间）
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
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

    start_time = datetime.now(timezone.utc)

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

    end_time = datetime.now(timezone.utc)
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
