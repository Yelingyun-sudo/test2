from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from datetime import date, datetime, timedelta, timezone

from kafka import KafkaConsumer
from sqlalchemy.exc import IntegrityError

from website_analytics.settings import get_settings

from .db import SessionLocal
from .models import SubscriptionTask, TaskStatus, EvidenceTask

logger = logging.getLogger(__name__)

TZ_CHINA = timezone(timedelta(hours=8))


def _insert_subscription_task(session, record: dict, now: datetime, today: date) -> bool:
    """写入 subscription_tasks 表，返回是否成功"""
    task = SubscriptionTask(
        url=record["url"],
        account=record["account"],
        password=record["password"],
        status=TaskStatus.PENDING,
        created_at=now,
        created_date=today,
    )
    session.add(task)
    try:
        session.commit()

        # 同步到 websites 表
        from .repositories.websites import sync_credential_from_subscription_task

        sync_credential_from_subscription_task(
            session,
            url=record["url"],
            account=record["account"],
            password=record["password"],
        )

        return True
    except IntegrityError:
        session.rollback()
        return False  # 重复数据，跳过


def _insert_evidence_task(
    session, record: dict, now: datetime, today: date
) -> bool:
    """写入 evidence_tasks 表，返回是否成功"""
    task = EvidenceTask(url=record["url"], created_at=now, created_date=today)
    session.add(task)
    try:
        session.commit()
        return True
    except IntegrityError:
        session.rollback()
        return False  # 重复数据，跳过


def _process_record(session, record: dict) -> str:
    """处理单条记录，返回处理结果"""
    now = datetime.now(timezone.utc)
    today = now.astimezone(TZ_CHINA).date()

    if "account" in record and "password" in record and "url" in record:
        success = _insert_subscription_task(session, record, now, today)
        return "subscription_inserted" if success else "subscription_skipped"
    elif "url" in record:
        success = _insert_evidence_task(session, record, now, today)
        return "evidence_inserted" if success else "evidence_skipped"
    else:
        return "invalid_record"


def _sync_kafka_consumer_loop(stop_event: threading.Event) -> None:
    """同步阻塞的 Kafka 消费循环，在独立线程中运行"""
    settings = get_settings()
    consumer = KafkaConsumer(
        settings.kafka_topic_task,
        bootstrap_servers=[settings.kafka_bootstrap_servers],
        security_protocol="SASL_PLAINTEXT",
        sasl_mechanism="SCRAM-SHA-512",
        sasl_plain_username=settings.kafka_sasl_username,
        sasl_plain_password=settings.kafka_sasl_password,
        auto_offset_reset="earliest",
        enable_auto_commit=False,  # 关闭自动提交
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        group_id=settings.kafka_group_id,
    )
    session = SessionLocal()

    try:
        logger.info("Kafka consumer 已启动，开始消费消息...")
        while not stop_event.is_set():
            # poll 带超时，便于检查停止信号
            records = consumer.poll(timeout_ms=1000)
            processed_any = False
            for tp, messages in records.items():
                for msg in messages:
                    # 检查消息是否过期
                    msg_age = (time.time() * 1000 - msg.timestamp) / 1000  # 秒
                    if msg_age > settings.kafka_message_max_age_seconds:
                        logger.warning(
                            f"消息过期，跳过: age={msg_age:.1f}s, offset={msg.offset}"
                        )
                        processed_any = True  # 标记已处理（跳过也算处理）
                        continue

                    try:
                        data = msg.value  # 数组，例如: [{'url': '...'}, {'url': '...', 'account': '...', 'password': '...'}]
                        for record in data:
                            result = _process_record(session, record)
                            logger.info(f"处理结果: {result}, record={record}")
                        processed_any = True
                    except Exception as e:
                        session.rollback()  # 防止 session 处于 failed state
                        logger.error(f"消息处理失败: {e}", exc_info=True)
                        # 处理失败不标记，下次重启会重新消费
            # 每批消息处理完后提交 offset（包括过期跳过的消息）
            if processed_any:
                consumer.commit()
    finally:
        session.close()
        consumer.close()
        logger.info("Kafka consumer 已关闭")


async def run_task_importer_loop() -> None:
    """异步入口，在线程池中运行 Kafka 消费"""
    stop_event = threading.Event()
    loop = asyncio.get_event_loop()

    try:
        await loop.run_in_executor(None, _sync_kafka_consumer_loop, stop_event)
    except asyncio.CancelledError:
        stop_event.set()  # 通知线程停止
        raise
