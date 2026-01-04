from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Union

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from website_analytics.settings import get_settings

from .db import SessionLocal
from .models import EvidenceTask, SubscriptionTask
from .enums import TaskStatus

TaskModel = Union[SubscriptionTask, EvidenceTask]

logger = logging.getLogger(__name__)


def _normalize_dt(dt: Optional[datetime]) -> Optional[datetime]:
    if not dt:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _get_stale_subscription_task(
    db: Session, cutoff: datetime
) -> SubscriptionTask | None:
    return (
        db.query(SubscriptionTask)
        .filter(
            SubscriptionTask.status == TaskStatus.RUNNING,
            or_(
                and_(
                    SubscriptionTask.executed_at.isnot(None),
                    SubscriptionTask.executed_at < cutoff,
                ),
                and_(
                    SubscriptionTask.executed_at.is_(None),
                    SubscriptionTask.created_at < cutoff,
                ),
            ),
        )
        .order_by(
            SubscriptionTask.executed_at.asc().nullsfirst(),
            SubscriptionTask.created_at.asc(),
        )
        .first()
    )


def _get_stale_evidence_task(db: Session, cutoff: datetime) -> EvidenceTask | None:
    return (
        db.query(EvidenceTask)
        .filter(
            EvidenceTask.status == TaskStatus.RUNNING,
            or_(
                and_(
                    EvidenceTask.executed_at.isnot(None),
                    EvidenceTask.executed_at < cutoff,
                ),
                and_(
                    EvidenceTask.executed_at.is_(None),
                    EvidenceTask.created_at < cutoff,
                ),
            ),
        )
        .order_by(
            EvidenceTask.executed_at.asc().nullsfirst(),
            EvidenceTask.created_at.asc(),
        )
        .first()
    )


def _mark_cleaned(
    db: Session, task: TaskModel, *, timeout_seconds: int, now: datetime
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
        now = datetime.now(timezone.utc)

        # 清理超时的 SubscriptionTask
        stale_sub = _get_stale_subscription_task(db, cutoff)
        if stale_sub:
            _mark_cleaned(db, stale_sub, timeout_seconds=timeout, now=now)
            logger.warning(
                "清理超时订阅任务: id=%s, url=%s", stale_sub.id, stale_sub.url
            )

        # 清理超时的 EvidenceTask
        stale_evi = _get_stale_evidence_task(db, cutoff)
        if stale_evi:
            _mark_cleaned(db, stale_evi, timeout_seconds=timeout, now=now)
            logger.warning(
                "清理超时证据任务: id=%s, url=%s", stale_evi.id, stale_evi.url
            )
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
