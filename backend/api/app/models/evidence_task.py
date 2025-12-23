from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import Column, Date, DateTime, Integer, String, UniqueConstraint, func

from ..db import Base

TZ_CHINA = timezone(timedelta(hours=8))


class EvidenceTask(Base):
    __tablename__ = "evidence_tasks"
    __table_args__ = (
        UniqueConstraint("url", "created_date", name="uq_evidence_url_date"),
    )

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String(2048), nullable=False, index=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_date = Column(
        Date, nullable=False, default=lambda: datetime.now(TZ_CHINA).date()
    )

    def __repr__(self) -> str:  # pragma: no cover - 调试辅助
        return f"<EvidenceTask id={self.id} url={self.url}>"
