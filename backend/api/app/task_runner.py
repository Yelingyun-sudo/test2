from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from website_analytics.cli import run_single_instruction_async
from website_analytics.orchestrator import ExecutionResult
from website_analytics.settings import get_settings
from website_analytics.utils import to_project_relative

from .db import SessionLocal
from .models import SubscribedTask, TaskReportStatus, TaskStatus

logger = logging.getLogger(__name__)


def _build_instruction(task: SubscribedTask) -> str:
    return f"登录 {task.url}（账号和密码分别为 {task.account} 和 {task.password}）并提取订阅地址"


def _read_task_summary(task_dir: Path) -> dict[str, Any] | None:
    summary_path = task_dir / "task_summary.json"
    if not summary_path.exists():
        return None
    try:
        with summary_path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:  # pragma: no cover - 防御性处理
        logger.warning("读取 task_summary.json 失败: %s", exc)
        return None


def _extract_success_result(summary: dict[str, Any] | None) -> str:
    if not summary:
        return "未找到任务总结文件"
    try:
        coordinator = summary.get("coordinator_output") or {}
        operations_results = coordinator.get("operations_results") or {}
        extract_result = operations_results.get("extract") or {}
        url = extract_result.get("subscription_url")
        if url:
            return str(url)
        return "未返回订阅地址"
    except Exception as exc:  # pragma: no cover - 防御性处理
        return f"解析任务总结失败: {exc}"


def _extract_failure_result(
    summary: dict[str, Any] | None, fallback: str | None = None
) -> str:
    if not summary:
        return fallback or "任务总结不存在"
    try:
        coordinator = summary.get("coordinator_output") or {}
        message = coordinator.get("message")
        if message:
            return str(message)
        return fallback or "任务失败，未提供错误信息"
    except Exception as exc:  # pragma: no cover - 防御性处理
        return f"解析失败信息时出错: {exc}"


def _format_failure_type(
    exc: Exception | None,
    timed_out: bool,
    exec_result: ExecutionResult | None = None,
) -> str:
    """格式化失败类型，优先使用业务层 error_type。

    优先级:
    1. 执行超时 → "timeout"
    2. 执行异常 → 异常类名
    3. 业务层错误 → coordinator_output.error_type
    4. 兜底 → "run_error"
    """
    if timed_out:
        return "timeout"
    if exc is not None:
        return exc.__class__.__name__

    # 从 exec_result 的 coordinator_output 读取业务层 error_type
    if exec_result and exec_result.coordinator_output:
        error_type = exec_result.coordinator_output.get("error_type")
        if error_type:
            return str(error_type)

    return "run_error"


def _mark_running(db: Session, task: SubscribedTask) -> None:
    task.status = TaskStatus.RUNNING
    task.executed_at = datetime.now(timezone.utc)
    db.add(task)
    db.commit()
    db.refresh(task)


def _update_task_success(
    db: Session,
    task: SubscribedTask,
    *,
    duration: float,
    result: str,
    task_dir: str | None,
) -> None:
    task.status = TaskStatus.SUCCESS
    task.duration_seconds = int(duration)
    task.history_extract_count = (task.history_extract_count or 0) + 1
    task.result = result
    task.task_dir = task_dir
    task.failure_type = None
    task.report_status = TaskReportStatus.PENDING
    db.add(task)
    db.commit()


def _update_task_failure(
    db: Session,
    task: SubscribedTask,
    *,
    duration: float,
    result: str,
    failure_type: str,
    task_dir: str | None,
) -> None:
    task.status = TaskStatus.FAILED
    task.duration_seconds = int(duration)
    task.result = result
    task.task_dir = task_dir
    task.failure_type = failure_type
    task.report_status = TaskReportStatus.PENDING
    db.add(task)
    db.commit()


def _get_pending_batch(db: Session, limit: int = 1) -> list[SubscribedTask]:
    return (
        db.query(SubscribedTask)
        .filter(SubscribedTask.status == TaskStatus.PENDING)
        .order_by(SubscribedTask.id.asc())
        .limit(limit)
        .all()
    )


def _get_running_batch_before(
    db: Session, before_ts: datetime, limit: int = 1
) -> list[SubscribedTask]:
    return (
        db.query(SubscribedTask)
        .filter(
            SubscribedTask.status == TaskStatus.RUNNING,
            or_(
                SubscribedTask.executed_at.is_(None),
                SubscribedTask.executed_at < before_ts,
            ),
        )
        .order_by(
            SubscribedTask.executed_at.asc().nullsfirst(),
            SubscribedTask.created_at.asc(),
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
        task_obj = db.get(SubscribedTask, task_id)
        if not task_obj:
            return

        if exec_result and exec_result.success and exec_result.task_dir:
            summary = _read_task_summary(exec_result.task_dir)
            result_text = _extract_success_result(summary)
            _update_task_success(
                db,
                task_obj,
                duration=duration,
                result=result_text,
                task_dir=task_dir_value,
            )
            logger.info(
                "任务成功: id=%s, url=%s, result=%s",
                task_obj.id,
                task_obj.url,
                result_text,
            )
        else:
            if exec_result and exec_result.task_dir:
                summary = _read_task_summary(exec_result.task_dir)
                result_text = _extract_failure_result(
                    summary, getattr(exec_result, "message", None)
                )
            else:
                fallback_msg = (
                    getattr(exec_result, "message", None) if exec_result else None
                )
                result_text = _extract_failure_result(None, fallback_msg)
            failure_type = _format_failure_type(exec_error, timed_out, exec_result)
            _update_task_failure(
                db,
                task_obj,
                duration=duration,
                result=result_text,
                failure_type=failure_type,
                task_dir=task_dir_value,
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
    tasks: list[SubscribedTask] = []
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


async def run_task_loop() -> None:
    settings = get_settings()
    interval = max(1, settings.task_runner_interval_seconds)
    max_concurrent = max(1, settings.task_runner_max_concurrent)
    semaphore = asyncio.Semaphore(max_concurrent)
    startup_ts = datetime.now(timezone.utc)
    recovering = True
    logger.info(
        "任务执行器已启动, interval=%ss, max_concurrent=%s",
        settings.task_runner_interval_seconds,
        settings.task_runner_max_concurrent,
    )

    while True:
        try:
            recovering = await process_once(
                semaphore, recovery_before=startup_ts, recovering=recovering
            )
        except Exception as exc:  # pragma: no cover - 防御性日志
            logger.exception("任务调度异常: %s", exc)
        await asyncio.sleep(interval)
