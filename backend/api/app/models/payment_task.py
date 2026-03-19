from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, Date, DateTime, Integer, String, UniqueConstraint, func

from ..constants import TZ_CHINA
from ..db import Base


class PaymentTask(Base):
    __tablename__ = "payment_tasks"
    __table_args__ = (
        UniqueConstraint("url", "created_date", name="uq_payment_url_date"),
    )

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String(2048), nullable=False, index=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_date = Column(
        Date, nullable=False, default=lambda: datetime.now(TZ_CHINA).date()
    )

    def __repr__(self) -> str:
        return f"<PaymentTask id={self.id} url={self.url}>"
