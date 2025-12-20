from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from website_analytics.settings import get_settings

from .db import SessionLocal
from .models import SubscribedTask, TaskStatus

logger = logging.getLogger(__name__)


def _normalize_dt(dt: Optional[datetime]) -> Optional[datetime]:
    if not dt:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _get_stale_task(db: Session, cutoff: datetime) -> SubscribedTask | None:
    return (
        db.query(SubscribedTask)
        .filter(
            SubscribedTask.status == TaskStatus.RUNNING,
            or_(
                and_(
                    SubscribedTask.executed_at.isnot(None),
                    SubscribedTask.executed_at < cutoff,
                ),
                and_(
                    SubscribedTask.executed_at.is_(None),
                    SubscribedTask.created_at < cutoff,
                ),
            ),
        )
        .order_by(
            SubscribedTask.executed_at.asc().nullsfirst(),
            SubscribedTask.created_at.asc(),
        )
        .first()
    )


def _mark_cleaned(
    db: Session, task: SubscribedTask, *, timeout_seconds: int, now: datetime
) -> None:
    task.status = TaskStatus.FAILED
    task.failure_type = "task_cleaned"
    task.result = f"任务被清理：超过 {timeout_seconds}s 未完成"

    started_at = (
        _normalize_dt(task.executed_at) or _normalize_dt(task.created_at) or now
    )
    duration = max(0, int((now - started_at).total_seconds()))
    task.duration_seconds = duration

    db.add(task)
    db.commit()


async def process_once() -> None:
    settings = get_settings()
    timeout = max(1, settings.task_cleaner_timeout_seconds)
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=timeout)

    db = SessionLocal()
    try:
        stale_task = _get_stale_task(db, cutoff)
        if not stale_task:
            return

        now = datetime.now(timezone.utc)
        _mark_cleaned(db, stale_task, timeout_seconds=timeout, now=now)
        logger.warning("清理超时任务: id=%s, url=%s", stale_task.id, stale_task.url)
    finally:
        db.close()


async def run_task_cleaner_loop() -> None:
    settings = get_settings()
    interval = max(1, settings.task_cleaner_interval_seconds)
    logger.info(
        "任务清理器已启动, interval=%ss, timeout=%ss",
        settings.task_cleaner_interval_seconds,
        settings.task_cleaner_timeout_seconds,
    )

    while True:
        try:
            await process_once()
        except Exception as exc:  # pragma: no cover - 防御性日志
            logger.exception("任务清理异常: %s", exc)
        await asyncio.sleep(interval)
