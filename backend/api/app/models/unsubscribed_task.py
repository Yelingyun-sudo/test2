from __future__ import annotations

from sqlalchemy import Column, DateTime, Integer, String, UniqueConstraint, func

from ..db import Base


class UnsubscribedTask(Base):
    __tablename__ = "unsubscribed_tasks"
    __table_args__ = (UniqueConstraint("url", name="uq_unsubscribed_url"),)

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String(2048), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - 调试辅助
        return f"<UnsubscribedTask id={self.id} url={self.url}>"

