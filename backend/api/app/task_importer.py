from __future__ import annotations

""" 2. 从 Kafka 消费并写入数据库"""
"""核心职责是：从 Kafka 消息队列中拉取数据，解析数据内容，然后分门别类地存入数据库，等待后续的取证程序来执行。"""

import asyncio
import json
import logging
import threading
import time
from datetime import date, datetime, timezone

from kafka import KafkaConsumer
from sqlalchemy.exc import IntegrityError
from website_analytics.settings import get_settings

from .constants import TZ_CHINA
from .db import SessionLocal
from .enums import TaskStatus
from .models import EvidenceTask, PaymentTask, SubscriptionTask

logger = logging.getLogger(__name__)

# (订阅任务入库)
"""
功能：当消息里包含 url、account、password 时（说明这是一个需要登录的网站），调用此函数。
逻辑：它会向 subscription_tasks 表写入一条状态为 PENDING（待处理）的任务。
亮点：写入成功后，它还做了一件很重要的事——调用 sync_credential_from_subscription_task。这相当于在写入任务单的同时，顺便更新了"网站账号密码本"，确保后续自动化登录时能用到最新的凭证。
"""


def _insert_subscription_task(
    session, record: dict, now: datetime, today: date
) -> bool:
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


# (取证任务入数据库)
# 写入 evidence_tasks 表
"""
功能：当消息里只有 url，没有账号密码时（说明这是一个公开网站），调用此函数。
逻辑：向 evidence_tasks 表写入任务。
逻辑更简单：不需要同步账号密码，只记录 URL 即可。
"""


def _insert_evidence_task(session, record: dict, now: datetime, today: date) -> bool:
    """写入 evidence_tasks 表，返回是否成功"""
    task = EvidenceTask(url=record["url"], created_at=now, created_date=today)
    session.add(task)
    try:
        session.commit()
        return True
    except IntegrityError:
        session.rollback()
        return False  # 重复数据，跳过


# (支付任务入数据库)
# 写入 payment_tasks 表
"""
功能：当消息里包含 task_type="payment" 时，调用此函数。
逻辑：向 payment_tasks 表写入任务，包含 url、account、password。
注意：支付任务不需要同步到 websites 表（因为是支付而非订阅）。
"""


def _insert_payment_task(session, record: dict, now: datetime, today: date) -> bool:
    """写入 payment_tasks 表，返回是否成功"""
    task = PaymentTask(
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
        return True
    except IntegrityError:
        session.rollback()
        return False  # 重复数据，跳过


# 处理单条消息，判断任务类型
# 这个函数是"分类员"，负责判断收到的消息该走哪条通道
"""
判断逻辑（优先使用 task_type 字段，兼容旧逻辑）：
1. 如果消息包含 task_type 字段：
   - task_type="payment" -> 支付任务
   - task_type="subscription" -> 订阅任务
   - task_type="evidence" -> 取证任务
2. 如果没有 task_type 字段（兼容旧消息）：
   - 有 account 和 password -> 订阅任务
   - 只有 url -> 取证任务
3. 如果连 URL 都没有 -> 无效记录
"""


def _process_record(session, record: dict) -> str:
    """处理单条记录，返回处理结果"""
    now = datetime.now(timezone.utc)
    today = now.astimezone(TZ_CHINA).date()

    # 优先检查 task_type 字段，用于区分三种任务类型
    task_type = record.get("task_type", "").strip().lower()

    if task_type == "payment":
        # 支付任务：必须有 url, account, password
        if (
            record.get("url", "").strip()
            and record.get("account", "").strip()
            and record.get("password", "").strip()
        ):
            success = _insert_payment_task(session, record, now, today)
            return "payment_inserted" if success else "payment_skipped"
        else:
            return "invalid_record"
    elif task_type == "subscription":
        # 订阅任务：必须有 url, account, password
        if (
            record.get("url", "").strip()
            and record.get("account", "").strip()
            and record.get("password", "").strip()
        ):
            success = _insert_subscription_task(session, record, now, today)
            return "subscription_inserted" if success else "subscription_skipped"
        else:
            return "invalid_record"
    elif task_type == "evidence":
        # 取证任务：必须有 url
        if record.get("url", "").strip():
            success = _insert_evidence_task(session, record, now, today)
            return "evidence_inserted" if success else "evidence_skipped"
        else:
            return "invalid_record"

    # 兼容旧逻辑：没有 task_type 时，根据是否有账号密码来判断
    # 检查字段是否存在且值为非空字符串（去除首尾空白后）
    has_credentials = (
        record.get("account", "").strip()
        and record.get("password", "").strip()
        and record.get("url", "").strip()
    )

    if has_credentials:
        success = _insert_subscription_task(session, record, now, today)
        return "subscription_inserted" if success else "subscription_skipped"
    elif record.get("url", "").strip():
        success = _insert_evidence_task(session, record, now, today)
        return "evidence_inserted" if success else "evidence_skipped"
    else:
        return "invalid_record"


# 同步阻塞的 Kafka 消费循环
"""
工作流程：
建立连接：连接 Kafka 集群，配置了比较复杂的安全认证（SASL/SCRAM-SHA-512），说明数据安全性要求很高。
轮询消费：while not stop_event.is_set() 是一个死循环，每秒拉取一次消息（timeout_ms=1000）。
消息过期检查：这是一个非常实用的保护机制。如果消息积压太久（超过 kafka_message_max_age_seconds），它就会跳过不处理。这防止了处理很久之前的过期指令，比如三天前的"立即截图"命令。
手动提交 Offset：enable_auto_commit=False 和手动 consumer.commit() 保证了"至少一次处理"的严谨性。只有当这批消息真正处理成功（或者决定跳过）后，才告诉 Kafka "我已经处理完了，下回别再发给我"。
异常处理：如果处理出错，它会 rollback 数据库事务，并且不提交 offset。这意味着下次程序重启时，这条失败的消息会被重新消费，确保任务不丢失。
"""


def _sync_kafka_consumer_loop(stop_event: threading.Event) -> None:
    """同步阻塞的 Kafka 消费循环，在独立线程中运行"""
    settings = get_settings()

    logger.info(f"正在连接 Kafka: {settings.kafka_bootstrap_servers}, topic: {settings.kafka_topic_task}")

    #修改前（带 SASL 认证），使用阿里云服务器上面的kafka
    # consumer = KafkaConsumer(
    #     settings.kafka_topic_task,
    #     bootstrap_servers=[settings.kafka_bootstrap_servers],
    #     security_protocol="SASL_PLAINTEXT",
    #     sasl_mechanism="SCRAM-SHA-512",
    #     sasl_plain_username=settings.kafka_sasl_username,
    #     sasl_plain_password=settings.kafka_sasl_password,
    #     auto_offset_reset="earliest",
    #     enable_auto_commit=False,  # 关闭自动提交
    #     value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    #     group_id=settings.kafka_group_id,
    # )

    # 修改后（无 SASL 认证）使用本机9093的kafka
    consumer = KafkaConsumer(
        settings.kafka_topic_task,
        bootstrap_servers=[settings.kafka_bootstrap_servers],
        auto_offset_reset="earliest",
        enable_auto_commit=False,
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
    except Exception as e:
        logger.error(f"Kafka consumer 发生异常: {e}", exc_info=True)
        raise
    finally:
        session.close()
        consumer.close()
        logger.info("Kafka consumer 已关闭")


# 异步入口，启动 Kafka消费者线程
# 这就是你最开始问的那段代码，它是"启动按钮"。
"""
这就是你最开始问的那段代码，它是"启动按钮"。
桥梁作用：因为主程序是异步的，而消费者循环 _sync_kafka_consumer_loop 是同步阻塞的。
线程池运行：它利用 loop.run_in_executor 把同步的消费者扔到线程池里去跑，让主程序的事件循环不被卡死。
优雅退出：当主程序发出取消信号（CancelledError）时，它会设置 stop_event，通知后台线程的循环停止，从而安全关闭连接，防止数据损坏。
"""


async def run_task_importer_loop() -> None:
    """异步入口，在线程池中运行 Kafka 消费"""
    stop_event = threading.Event()
    loop = asyncio.get_event_loop()

    try:
        await loop.run_in_executor(None, _sync_kafka_consumer_loop, stop_event)
    except asyncio.CancelledError:
        stop_event.set()  # 通知线程停止
        raise
