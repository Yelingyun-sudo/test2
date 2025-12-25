from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from website_analytics.cli import run_single_instruction_async
from website_analytics.orchestrator import ExecutionResult
from website_analytics.settings import get_settings
from website_analytics.utils import to_project_relative

from .db import SessionLocal
from .models import EvidenceTask, TaskReportStatus, TaskStatus

logger = logging.getLogger(__name__)


def _build_instruction(task: EvidenceTask) -> str:
    """构建证据任务执行指令。

    根据 account/password 是否存在，生成不同的指令：
    - 有账密：登录 {url}（账号和密码分别为 {account} 和 {password}）并完成巡检
    - 无账密：访问 {url} 并完成巡检
    """
    if task.account and task.password:
        return f"登录 {task.url}（账号和密码分别为 {task.account} 和 {task.password}）并完成巡检"
    else:
        return f"访问 {task.url} 并完成巡检"


def _extract_success_result(exec_result: ExecutionResult | None) -> str:
    """从 ExecutionResult 提取成功结果（巡检摘要）。

    返回格式：
    - "巡检完成。成功 3/3 个入口。报告：inspect/report.md"
    - "巡检部分成功。成功 2/3 个入口。报告：inspect/report.md"
    """
    if not exec_result or not exec_result.coordinator_output:
        return "任务结果不可用"
    try:
        coordinator = exec_result.coordinator_output
        operations_results = coordinator.get("operations_results") or {}
        inspect_result = operations_results.get("inspect") or {}

        # 提取核心信息
        entries_total = inspect_result.get("entries_total", 0)
        entries_success = inspect_result.get("entries_success", 0)
        entries_failed = inspect_result.get("entries_failed", 0)
        report_file = inspect_result.get("report_file", "")
        message = inspect_result.get("message", "")

        # 构建摘要
        if entries_total > 0:
            summary = f"巡检完成。成功 {entries_success}/{entries_total} 个入口"
            if entries_failed > 0:
                summary = f"巡检部分成功。成功 {entries_success}/{entries_total} 个入口"
        else:
            summary = message or "巡检完成"

        if report_file:
            summary += f"。报告：{report_file}"

        return summary
    except Exception as exc:  # pragma: no cover - 防御性处理
        return f"解析任务结果失败: {exc}"


def _extract_failure_result(
    exec_result: ExecutionResult | None,
    exc: Exception | None = None,
) -> str:
    """从 ExecutionResult 提取失败结果信息。"""
    # 优先使用 ExecutionResult 中的消息
    if exec_result and exec_result.coordinator_output:
        try:
            message = exec_result.coordinator_output.get("message")
            if message:
                return str(message)
        except Exception as parse_exc:  # pragma: no cover - 防御性处理
            return f"解析失败信息时出错: {parse_exc}"

    # 其次使用 ExecutionResult.message 属性
    if exec_result:
        try:
            return exec_result.message
        except Exception:
            pass

    # 最后使用异常信息
    if exc is not None:
        return f"执行异常：{exc.__class__.__name__}: {str(exc)}"

    return "任务失败，未提供错误信息"


def _format_failure_type(
    exc: Exception | None,
    timed_out: bool,
    exec_result: ExecutionResult | None = None,
) -> str:
    """格式化失败类型，优先使用业务层 error_type。

    优先级:
    1. 执行超时 → "task_timeout"
    2. 业务层错误 → coordinator_output.error_type
    3. 执行异常或兜底 → "unknown_error"（异常详情记录在 result 中）
    """
    if timed_out:
        return "task_timeout"

    # 从 exec_result 的 coordinator_output 读取业务层 error_type
    if exec_result and exec_result.coordinator_output:
        error_type = exec_result.coordinator_output.get("error_type")
        if error_type:
            return str(error_type)

    # 统一为 unknown_error，异常详情在 result 字段中
    return "unknown_error"


def _mark_running(db: Session, task: EvidenceTask) -> None:
    task.status = TaskStatus.RUNNING
    task.executed_at = datetime.now(timezone.utc)
    db.add(task)
    db.commit()
    db.refresh(task)


def _update_task_success(
    db: Session,
    task: EvidenceTask,
    *,
    duration: float,
    result: str,
    task_dir: str | None,
    llm_usage: dict[str, Any] | None = None,
) -> None:
    task.status = TaskStatus.SUCCESS
    task.duration_seconds = int(duration)
    task.result = result
    task.task_dir = task_dir
    task.failure_type = None
    task.report_status = TaskReportStatus.PENDING
    task.llm_usage = llm_usage
    db.add(task)
    db.commit()


def _update_task_failure(
    db: Session,
    task: EvidenceTask,
    *,
    duration: float,
    result: str,
    failure_type: str,
    task_dir: str | None,
    llm_usage: dict[str, Any] | None = None,
) -> None:
    task.status = TaskStatus.FAILED
    task.duration_seconds = int(duration)
    task.result = result
    task.task_dir = task_dir
    task.failure_type = failure_type
    task.report_status = TaskReportStatus.PENDING
    task.llm_usage = llm_usage
    db.add(task)
    db.commit()


def _get_pending_batch(db: Session, limit: int = 1) -> list[EvidenceTask]:
    return (
        db.query(EvidenceTask)
        .filter(EvidenceTask.status == TaskStatus.PENDING)
        .order_by(EvidenceTask.id.asc())
        .limit(limit)
        .all()
    )


def _get_running_batch_before(
    db: Session, before_ts: datetime, limit: int = 1
) -> list[EvidenceTask]:
    return (
        db.query(EvidenceTask)
        .filter(
            EvidenceTask.status == TaskStatus.RUNNING,
            or_(
                EvidenceTask.executed_at.is_(None),
                EvidenceTask.executed_at < before_ts,
            ),
        )
        .order_by(
            EvidenceTask.executed_at.asc().nullsfirst(),
            EvidenceTask.created_at.asc(),
        )
        .limit(limit)
        .all()
    )


async def _run_task(task_id: int, instruction: str) -> None:
    settings = get_settings()
    start_time = datetime.now(timezone.utc)
    exec_error: Exception | None = None
    timed_out = False

    try:
        # 为清理预留额外时间（用于 Playwright 优雅关闭和孤儿进程清理）
        execution_timeout = settings.task_runner_timeout_seconds
        cleanup_buffer = settings.playwright_cleanup_buffer_seconds

        logger.info("开始执行任务: task_id=%s, instruction=%s", task_id, instruction)
        exec_result = await asyncio.wait_for(
            run_single_instruction_async(
                instruction,
                headless=settings.task_runner_headless,
            ),
            timeout=execution_timeout + cleanup_buffer,  # 增加清理缓冲时间
        )
    except asyncio.TimeoutError:
        exec_result = None
        timed_out = True
    except Exception as exc:
        exec_result = None
        exec_error = exc

    duration = (datetime.now(timezone.utc) - start_time).total_seconds()
    task_dir_value = (
        to_project_relative(exec_result.task_dir)
        if exec_result and exec_result.task_dir
        else None
    )

    db = SessionLocal()
    try:
        task_obj = db.get(EvidenceTask, task_id)
        if not task_obj:
            return

        if exec_result and exec_result.success and exec_result.task_dir:
            result_text = _extract_success_result(exec_result)
            llm_usage = exec_result.llm_usage
            _update_task_success(
                db,
                task_obj,
                duration=duration,
                result=result_text,
                task_dir=task_dir_value,
                llm_usage=llm_usage,
            )
            logger.info(
                "任务成功: id=%s, url=%s, result=%s",
                task_obj.id,
                task_obj.url,
                result_text,
            )
        else:
            result_text = _extract_failure_result(exec_result, exc=exec_error)
            llm_usage = exec_result.llm_usage if exec_result else None
            failure_type = _format_failure_type(exec_error, timed_out, exec_result)
            _update_task_failure(
                db,
                task_obj,
                duration=duration,
                result=result_text,
                failure_type=failure_type,
                task_dir=task_dir_value,
                llm_usage=llm_usage,
            )
            logger.warning(
                "任务失败: id=%s, url=%s, failure_type=%s, result=%s",
                task_obj.id,
                task_obj.url,
                failure_type,
                result_text,
            )
    finally:
        db.close()


async def process_once(
    semaphore: asyncio.Semaphore,
    *,
    recovery_before: datetime | None,
    recovering: bool,
) -> bool:
    # 当前可用并发槽
    available = semaphore._value  # type: ignore[attr-defined]
    if available <= 0:
        return recovering

    db = SessionLocal()
    tasks: list[EvidenceTask] = []
    try:
        if recovering and recovery_before:
            tasks = _get_running_batch_before(db, recovery_before, limit=1)
            if not tasks:
                recovering = False

        if not tasks:
            tasks = _get_pending_batch(db, limit=1)
        if not tasks:
            return recovering

        for task in tasks:
            _mark_running(db, task)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    for task in tasks:
        instruction = _build_instruction(task)

        async def _worker(tid: int, instr: str):
            async with semaphore:
                await _run_task(tid, instr)

        asyncio.create_task(_worker(task.id, instruction))

    return recovering


async def run_evidence_runner_loop() -> None:
    settings = get_settings()
    interval = max(1, settings.task_runner_interval_seconds)
    max_concurrent = max(1, settings.task_runner_max_concurrent)
    semaphore = asyncio.Semaphore(max_concurrent)
    startup_ts = datetime.now(timezone.utc)
    recovering = True
    logger.info(
        "证据任务执行器已启动, interval=%ss, max_concurrent=%s",
        settings.task_runner_interval_seconds,
        settings.task_runner_max_concurrent,
    )

    while True:
        try:
            recovering = await process_once(
                semaphore, recovery_before=startup_ts, recovering=recovering
            )
        except Exception as exc:  # pragma: no cover - 防御性日志
            logger.exception("证据任务调度异常: %s", exc)
        await asyncio.sleep(interval)
