from __future__ import annotations

import asyncio
import json
import logging

from kafka import KafkaProducer
from sqlalchemy.orm import Session

from website_analytics.settings import get_settings

from .db import SessionLocal
from .models import SubscribedTask, TaskReportStatus, TaskStatus

logger = logging.getLogger(__name__)

_producer: KafkaProducer | None = None


def _get_producer() -> KafkaProducer:
    """获取或创建 Kafka Producer 单例"""
    global _producer
    if _producer is None:
        settings = get_settings()
        _producer = KafkaProducer(
            bootstrap_servers=[settings.kafka_bootstrap_servers],
            security_protocol="SASL_PLAINTEXT",
            sasl_mechanism="SCRAM-SHA-512",
            sasl_plain_username=settings.kafka_sasl_username,
            sasl_plain_password=settings.kafka_sasl_password,
            value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode("utf-8"),
        )
    return _producer


def _get_pending_report_task(db: Session) -> SubscribedTask | None:
    """获取一条待汇报的任务"""
    return (
        db.query(SubscribedTask)
        .filter(
            SubscribedTask.report_status == TaskReportStatus.PENDING,
            SubscribedTask.status.in_([TaskStatus.SUCCESS, TaskStatus.FAILED]),
        )
        .order_by(SubscribedTask.id.asc())
        .first()
    )


def _build_message(task: SubscribedTask) -> dict:
    """构建汇报消息"""
    message = {
        "domain": task.url,
        "account": task.account,
        "password": task.password,
        "result": task.result or "",
    }
    if task.status == TaskStatus.FAILED and task.failure_type:
        message["failType"] = task.failure_type
    return message


def _update_report_status(
    db: Session, task: SubscribedTask, status: TaskReportStatus
) -> None:
    """更新任务的汇报状态"""
    task.report_status = status
    db.add(task)
    db.commit()


def _report_task(task: SubscribedTask) -> bool:
    """
    汇报单个任务到 Kafka。
    返回 True 表示成功，False 表示失败。
    """
    settings = get_settings()
    producer = _get_producer()
    message = _build_message(task)

    if task.status == TaskStatus.SUCCESS:
        topic = settings.kafka_topic_report_success
    else:
        topic = settings.kafka_topic_report_failed

    try:
        future = producer.send(topic, value=message)
        future.get(timeout=10)  # 等待发送完成
        return True
    except Exception as exc:
        logger.error("Kafka 发送失败: task_id=%s, error=%s", task.id, exc)
        return False


def _sync_process_once() -> None:
    """同步处理一条待汇报的任务（在线程中执行）"""
    db = SessionLocal()
    try:
        task = _get_pending_report_task(db)
        if not task:
            return

        success = _report_task(task)
        if success:
            _update_report_status(db, task, TaskReportStatus.SUCCESS)
            logger.info(
                "汇报成功: id=%s, status=%s, url=%s",
                task.id,
                task.status.value,
                task.url,
            )
        else:
            _update_report_status(db, task, TaskReportStatus.FAILED)
            logger.warning(
                "汇报失败: id=%s, status=%s, url=%s",
                task.id,
                task.status.value,
                task.url,
            )
    finally:
        db.close()


async def process_once() -> None:
    """异步入口，在线程中执行同步操作"""
    await asyncio.to_thread(_sync_process_once)


async def run_task_reporter_loop() -> None:
    """任务汇报主循环"""
    settings = get_settings()
    interval = max(1, settings.task_reporter_interval_seconds)

    while True:
        try:
            await process_once()
        except Exception as exc:  # pragma: no cover - 防御性日志
            logger.exception("任务汇报异常: %s", exc)
        await asyncio.sleep(interval)
