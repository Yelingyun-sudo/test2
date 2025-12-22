from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum

from sqlalchemy import (
    JSON,
    Column,
    Date,
    DateTime,
    Enum as SAEnum,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)

from ..db import Base


TZ_CHINA = timezone(timedelta(hours=8))


class TaskStatus(str, Enum):
    PENDING = "pending"  # 待执行
    RUNNING = "running"  # 执行中
    SUCCESS = "success"  # 成功
    FAILED = "failed"  # 失败


class TaskReportStatus(str, Enum):
    PENDING = "pending"  # 待汇报（任务已完成，等待发送）
    SUCCESS = "success"  # Kafka 发送成功
    FAILED = "failed"  # Kafka 发送失败


class SubscribedTask(Base):
    __tablename__ = "subscribed_tasks"
    __table_args__ = (
        UniqueConstraint(
            "url", "account", "created_date", name="uq_tasks_url_account_date"
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String(2048), nullable=False, index=True)
    account = Column(String(255), nullable=False)
    password = Column(String(255), nullable=False)

    status = Column(SAEnum(TaskStatus), nullable=False, default=TaskStatus.PENDING)
    duration_seconds = Column(Integer, nullable=False, default=0)
    executed_at = Column(DateTime(timezone=True), nullable=True)
    task_dir = Column(String(1024), nullable=True)

    result = Column(Text, nullable=True)
    failure_type = Column(String(255), nullable=True)
    report_status = Column(SAEnum(TaskReportStatus), nullable=True, default=None)

    # LLM token 使用统计（存储为 JSON）
    llm_usage = Column(JSON, nullable=True, comment="LLM token 使用统计")

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_date = Column(
        Date, nullable=False, default=lambda: datetime.now(TZ_CHINA).date()
    )

    def __repr__(self) -> str:  # pragma: no cover - 调试辅助
        return f"<SubscribedTask id={self.id} url={self.url}>"
