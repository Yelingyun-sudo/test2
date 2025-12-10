from __future__ import annotations


from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from ..db import Base


class RevokedToken(Base):
    __tablename__ = "revoked_tokens"
    __table_args__ = (UniqueConstraint("jti", name="uq_revoked_tokens_jti"),)

    id = Column(Integer, primary_key=True, index=True)
    jti = Column(String(255), nullable=False, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    revoked_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at = Column(DateTime(timezone=True), nullable=False)

    user = relationship("User", backref="revoked_tokens")
