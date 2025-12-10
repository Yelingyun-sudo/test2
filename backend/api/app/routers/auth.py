from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..repositories.tokens import revoke_token
from ..repositories.users import get_user_by_username, update_last_login
from ..schemas.auth import LoginRequest, LoginResponse, LogoutResponse
from ..security import (
    _decode_token,
    bearer_scheme,
    create_access_token,
    get_current_user,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse, summary="登录（数据库验证）")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = get_user_by_username(db, payload.username)

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="用户已被禁用"
        )

    access_token = create_access_token(
        {"sub": str(user.id), "username": user.username, "is_admin": user.is_admin}
    )
    update_last_login(db, user)

    return LoginResponse(access_token=access_token)


@router.post("/logout", response_model=LogoutResponse, summary="退出登录（撤销当前令牌）")
def logout(
    credentials=Depends(bearer_scheme),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="未提供认证凭证"
        )

    token = credentials.credentials
    payload = _decode_token(token)
    jti = payload.get("jti")
    exp = payload.get("exp")

    if not jti:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="令牌缺少标识，请重新登录"
        )

    expires_at = datetime.fromtimestamp(exp, tz=timezone.utc) if exp else datetime.now(timezone.utc)
    revoke_token(db, jti=jti, user_id=current_user.id, expires_at=expires_at)

    return LogoutResponse()
