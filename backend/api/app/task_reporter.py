from __future__ import annotations

"""任务结果汇报器"""
"""从数据库中取出已经执行完成（成功 / 失败）的订阅任务，把结果发送到 Kafka 消息队列，然后更新任务的汇报状态。"""
""" 后台异步循环服务，持续运行、自动轮询、自动上报。"""
"""
整体流程（一句话）
循环查询数据库 → 找待汇报且已完成的任务
把任务结果封装成消息
发送到 Kafka（成功 / 失败分不同主题）
更新数据库状态（汇报成功 / 失败）
"""
import asyncio
import json
import logging

from kafka import KafkaProducer
from sqlalchemy.orm import Session

from website_analytics.settings import get_settings

from .db import SessionLocal
from .models import EvidenceTask, SubscriptionTask
from .enums import TaskReportStatus, TaskStatus

logger = logging.getLogger(__name__)

_producer: KafkaProducer | None = (
    None  # 作用：Kafka 生产者单例，避免重复创建连接，全局复用一个生产者。
)


# kafka初始化函数
# 功能： 创建并返回一个全局唯一的 Kafka 生产者（单例模式）
def _get_producer() -> KafkaProducer:
    """获取或创建 Kafka Producer 单例"""
    global _producer
    if _producer is None:
        settings = get_settings()
        _producer = KafkaProducer(
            bootstrap_servers=[settings.kafka_bootstrap_servers],  # Kafka 集群地址
            security_protocol="SASL_PLAINTEXT",  # 安全协议
            sasl_mechanism="SCRAM-SHA-512",  # 认证方式
            sasl_plain_username=settings.kafka_sasl_username,  # 连接 Kafka 的账号密码
            sasl_plain_password=settings.kafka_sasl_password,
            value_serializer=lambda v: json.dumps(
                v, ensure_ascii=False
            ).encode(  # 把消息自动序列化为 JSON 并转成 utf-8 字节，这是发送 JSON 消息必须的配置
                "utf-8"
            ),
        )
    return _producer


# 从数据库取一条：待汇报 + 已完成（成功 / 失败）的任务
def _get_pending_report_subscription_task(db: Session) -> SubscriptionTask | None:
    """获取一条待汇报的订阅任务"""
    return (
        db.query(SubscriptionTask)
        .filter(
            SubscriptionTask.report_status == TaskReportStatus.PENDING,  # 待汇报
            SubscriptionTask.status.in_(
                [TaskStatus.SUCCESS, TaskStatus.FAILED]
            ),  # 任务已经执行完
        )
        .order_by(SubscriptionTask.id.asc())
        .first()
    )


def _get_pending_report_evidence_task(db: Session) -> EvidenceTask | None:
    """获取一条待汇报的注册取证任务"""
    return (
        db.query(EvidenceTask)
        .filter(
            EvidenceTask.report_status == TaskReportStatus.PENDING,
            EvidenceTask.status.in_([TaskStatus.SUCCESS, TaskStatus.FAILED]),
        )
        .order_by(EvidenceTask.id.asc())
        .first()
    )


# 把任务对象构造成要发送给 Kafka 的 JSON 消息
def _build_subscription_message(task: SubscriptionTask) -> dict:
    """构建订阅任务汇报消息"""
    message = {
        "domain": task.url,
        "account": task.account,
        "password": task.password,
        "result": task.result or "",
    }
    if task.status == TaskStatus.FAILED and task.failure_type:
        message["failType"] = (
            task.failure_type
        )  # 也就是说"failType": "可选，失败时才有"
    return message


def _build_evidence_message(task: EvidenceTask) -> dict:
    """构建注册取证任务汇报消息"""
    message = {
        "domain": task.url,
        "account": task.account,
        "password": task.password,
        "result": task.result or "",
    }
    if task.status == TaskStatus.FAILED and task.failure_type:
        message["failType"] = task.failure_type
    return message


# 发送 Kafka 后，更新数据库里的汇报状态：
def _update_subscription_report_status(
    db: Session, task: SubscriptionTask, status: TaskReportStatus
) -> None:
    """更新订阅任务的汇报状态"""
    task.report_status = status
    db.add(task)
    db.commit()


def _update_evidence_report_status(
    db: Session, task: EvidenceTask, status: TaskReportStatus
) -> None:
    """更新注册取证任务的汇报状态"""
    task.report_status = status
    db.add(task)
    db.commit()


# —— Kafka 发送核心函数
# 返回 True/False，表示发送是否成功
def _report_subscription_task(task: SubscriptionTask) -> bool:
    """
    汇报单个订阅任务到 Kafka。
    返回 True 表示成功，False 表示失败。
    """
    settings = get_settings()
    producer = _get_producer()  # 获取全局生产者
    message = _build_subscription_message(task)  # 构建消息

    # 成功/失败 发送到不同主题
    if task.status == TaskStatus.SUCCESS:
        topic = settings.kafka_topic_report_success
    else:
        topic = settings.kafka_topic_report_failed

    try:
        future = producer.send(topic, value=message)  # 真正发送消息到 Kafka
        future.get(timeout=10)  # 等待发送完成
        return True
    except Exception as exc:
        logger.error("Kafka 发送失败: task_id=%s, error=%s", task.id, exc)
        return False


def _report_evidence_task(task: EvidenceTask) -> bool:
    """
    汇报单个注册取证任务到 Kafka。
    返回 True 表示成功，False 表示失败。
    """
    settings = get_settings()
    producer = _get_producer()
    message = _build_evidence_message(task)

    # 成功/失败 发送到不同主题
    if task.status == TaskStatus.SUCCESS:
        topic = settings.kafka_topic_report_success
    else:
        topic = settings.kafka_topic_report_failed

    try:
        future = producer.send(topic, value=message)
        future.get(timeout=10)
        return True
    except Exception as exc:
        logger.error("注册取证任务 Kafka 发送失败: task_id=%s, error=%s", task.id, exc)
        return False


# 同步执行一次完整流程：
"""
取任务
发 Kafka
更新状态
关闭数据库连接
"""


def _sync_process_once() -> None:
    """同步处理一条待汇报的任务（在线程中执行）"""
    db = SessionLocal()
    try:
        # 先处理订阅任务
        task = _get_pending_report_subscription_task(db)
        if task:
            success = _report_subscription_task(task)
            if success:
                _update_subscription_report_status(db, task, TaskReportStatus.SUCCESS)
                logger.info(
                    "订阅任务汇报成功: id=%s, status=%s, url=%s",
                    task.id,
                    task.status.value,
                    task.url,
                )
            else:
                _update_subscription_report_status(db, task, TaskReportStatus.FAILED)
                logger.warning(
                    "订阅任务汇报失败: id=%s, status=%s, url=%s",
                    task.id,
                    task.status.value,
                    task.url,
                )
            return

        # 再处理注册取证任务
        evidence_task = _get_pending_report_evidence_task(db)
        if evidence_task:
            success = _report_evidence_task(evidence_task)
            if success:
                _update_evidence_report_status(
                    db, evidence_task, TaskReportStatus.SUCCESS
                )
                logger.info(
                    "注册取证任务汇报成功: id=%s, status=%s, url=%s",
                    evidence_task.id,
                    evidence_task.status.value,
                    evidence_task.url,
                )
            else:
                _update_evidence_report_status(
                    db, evidence_task, TaskReportStatus.FAILED
                )
                logger.warning(
                    "注册取证任务汇报失败: id=%s, status=%s, url=%s",
                    evidence_task.id,
                    evidence_task.status.value,
                    evidence_task.url,
                )
    finally:
        db.close()


# 异步包装函数
# 把同步的数据库 + Kafka 操作放到线程执行，不阻塞 asyncio 事件循环。
async def process_once() -> None:
    """异步入口，在线程中执行同步操作"""
    await asyncio.to_thread(_sync_process_once)


# 入口主循环
async def run_task_reporter_loop() -> None:
    """任务汇报主循环"""
    settings = get_settings()
    interval = max(1, settings.task_reporter_interval_seconds)
    logger.info(
        "任务汇报器已启动, interval=%ss",
        settings.task_reporter_interval_seconds,
    )

    while True:
        try:
            await process_once()
        except Exception as exc:  # pragma: no cover - 防御性日志
            logger.exception("任务汇报异常: %s", exc)
        await asyncio.sleep(interval)
