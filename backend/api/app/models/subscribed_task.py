from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum

from sqlalchemy import (
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
    retry_count = Column(Integer, nullable=False, default=0)
    history_extract_count = Column(Integer, nullable=False, default=0)
    last_extracted_at = Column(DateTime(timezone=True), nullable=True)

    result = Column(Text, nullable=True)
    failure_type = Column(String(255), nullable=True)

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_date = Column(
        Date, nullable=False, default=lambda: datetime.now(TZ_CHINA).date()
    )

    def __repr__(self) -> str:  # pragma: no cover - 调试辅助
        return f"<SubscribedTask id={self.id} url={self.url}>"
