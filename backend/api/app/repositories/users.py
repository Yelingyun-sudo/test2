from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from ..models import User


def normalize_username(username: str) -> str:
    return username.strip().lower()


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_username(db: Session, username: str) -> Optional[User]:
    normalized = normalize_username(username)
    return db.query(User).filter(User.username == normalized).first()


def create_user(
    db: Session,
    *,
    username: str,
    password_hash: str,
    is_admin: bool = False,
    is_active: bool = True,
) -> User:
    normalized = normalize_username(username)
    user = User(
        username=normalized,
        password_hash=password_hash,
        is_admin=is_admin,
        is_active=is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_last_login(db: Session, user: User, ts: datetime | None = None) -> User:
    user.last_login_at = ts or datetime.now(timezone.utc)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
