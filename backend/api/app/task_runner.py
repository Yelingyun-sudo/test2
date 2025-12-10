from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from website_analytics.cli import run_single_instruction
from website_analytics.settings import get_settings

from .db import SessionLocal
from .models import SubscribedTask, TaskStatus

logger = logging.getLogger(__name__)


def _build_instruction(task: SubscribedTask) -> str:
    return (
        f"登录 {task.url}（账号和密码分别为 {task.account} 和 {task.password}）并提取订阅地址"
    )


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


def _extract_failure_result(summary: dict[str, Any] | None, fallback: str | None = None) -> str:
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


def _format_failure_type(exc: Exception | None, timed_out: bool) -> str:
    if timed_out:
        return "timeout"
    if exc is None:
        return "run_error"
    return exc.__class__.__name__


def _mark_running(db: Session, task: SubscribedTask) -> None:
    task.status = TaskStatus.RUNNING
    task.last_extracted_at = datetime.now(timezone.utc)
    db.add(task)
    db.commit()
    db.refresh(task)


def _update_task_success(db: Session, task: SubscribedTask, *, duration: float, result: str) -> None:
    task.status = TaskStatus.SUCCESS
    task.duration_seconds = int(duration)
    task.history_extract_count = (task.history_extract_count or 0) + 1
    task.result = result
    task.failure_type = None
    db.add(task)
    db.commit()


def _update_task_failure(
    db: Session,
    task: SubscribedTask,
    *,
    duration: float,
    result: str,
    failure_type: str,
) -> None:
    task.status = TaskStatus.FAILED
    task.duration_seconds = int(duration)
    task.result = result
    task.failure_type = failure_type
    db.add(task)
    db.commit()


def _get_pending_batch(db: Session, limit: int) -> list[SubscribedTask]:
    return (
        db.query(SubscribedTask)
        .filter(SubscribedTask.status == TaskStatus.PENDING)
        .order_by(SubscribedTask.id.desc())
        .limit(limit)
        .all()
    )


async def _run_task(task_id: int, instruction: str) -> None:
    settings = get_settings()
    start_time = datetime.now(timezone.utc)
    exec_error: Exception | None = None
    timed_out = False

    try:
        timeout = settings.task_runner_timeout_seconds
        exec_result = await asyncio.wait_for(
            asyncio.to_thread(run_single_instruction, instruction, headless=settings.task_runner_headless),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        exec_result = None
        timed_out = True
    except Exception as exc:
        exec_result = None
        exec_error = exc

    duration = (datetime.now(timezone.utc) - start_time).total_seconds()

    db = SessionLocal()
    try:
        task_obj = db.get(SubscribedTask, task_id)
        if not task_obj:
            return

        if exec_result and exec_result.success and exec_result.task_dir:
            summary = _read_task_summary(exec_result.task_dir)
            result_text = _extract_success_result(summary)
            _update_task_success(db, task_obj, duration=duration, result=result_text)
            logger.info("任务成功: id=%s, url=%s, result=%s", task_obj.id, task_obj.url, result_text)
        else:
            if exec_result and exec_result.task_dir:
                summary = _read_task_summary(exec_result.task_dir)
                result_text = _extract_failure_result(summary, getattr(exec_result, "message", None))
            else:
                fallback_msg = getattr(exec_result, "message", None) if exec_result else None
                result_text = _extract_failure_result(None, fallback_msg)
            failure_type = _format_failure_type(exec_error, timed_out)
            _update_task_failure(
                db,
                task_obj,
                duration=duration,
                result=result_text,
                failure_type=failure_type,
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


async def process_once(semaphore: asyncio.Semaphore) -> None:
    # 当前可用并发槽
    available = semaphore._value  # type: ignore[attr-defined]
    if available <= 0:
        return

    db = SessionLocal()
    tasks: list[SubscribedTask] = []
    try:
        tasks = _get_pending_batch(db, limit=available)
        if not tasks:
            return

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


async def run_task_loop() -> None:
    settings = get_settings()
    interval = max(1, settings.task_runner_interval_seconds)
    max_concurrent = max(1, settings.task_runner_max_concurrent)
    semaphore = asyncio.Semaphore(max_concurrent)

    while True:
        try:
            await process_once(semaphore)
        except Exception as exc:  # pragma: no cover - 防御性日志
            logger.exception("任务调度异常: %s", exc)
        await asyncio.sleep(interval)
