from __future__ import annotations
"""SQLAlchemy 模型，定义表结构"""

from datetime import datetime

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

from ..constants import TZ_CHINA
from ..db import Base
from ..enums import TaskReportStatus, TaskStatus


class EvidenceTask(Base):
    __tablename__ = "evidence_tasks"
    __table_args__ = (
        UniqueConstraint("url", "created_date", name="uq_evidence_url_date"),
    )

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String(2048), nullable=False, index=True)
    account = Column(String(255), nullable=True)
    password = Column(String(255), nullable=True)

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
        return f"<EvidenceTask id={self.id} url={self.url}>"
