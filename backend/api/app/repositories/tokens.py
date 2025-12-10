from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from ..models import RevokedToken


def is_token_revoked(db: Session, jti: str) -> bool:
    return db.query(RevokedToken.id).filter(RevokedToken.jti == jti).first() is not None


def revoke_token(
    db: Session,
    *,
    jti: str,
    user_id: int,
    expires_at: datetime,
) -> RevokedToken:
    existing = db.query(RevokedToken).filter(RevokedToken.jti == jti).first()
    if existing:
        return existing

    token = RevokedToken(jti=jti, user_id=user_id, expires_at=expires_at)
    db.add(token)
    db.commit()
    db.refresh(token)
    return token
