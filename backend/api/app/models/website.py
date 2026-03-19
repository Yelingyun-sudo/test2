from __future__ import annotations

from enum import Enum

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    Enum as SAEnum,
)

from ..db import Base


class WebsiteStatus(str, Enum):
    INITIALIZED = "INITIALIZED"  # 初始化
    ACTIVE = "ACTIVE"  # 正常
    ERROR = "ERROR"  # 异常


class Website(Base):
    __tablename__ = "websites"
    __table_args__ = (UniqueConstraint("url", name="uq_websites_url"),)

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String(2048), nullable=False, index=True)
    description = Column(Text, nullable=True)
    credentials = Column(JSON, nullable=True, comment="账号密码列表")
    status = Column(
        SAEnum(WebsiteStatus), nullable=False, default=WebsiteStatus.INITIALIZED
    )
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:  # pragma: no cover - 调试辅助
        return f"<Website id={self.id} url={self.url} status={self.status}>"
