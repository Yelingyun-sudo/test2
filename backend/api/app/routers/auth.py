from fastapi import APIRouter, HTTPException, status

from ..schemas.auth import LoginRequest, LoginResponse

router = APIRouter(prefix="/auth", tags=["auth"])

# 简单的静态账号，后续可替换为数据库/SSO 等真实鉴权
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin"
STATIC_TOKEN = "static-admin-token"


@router.post("/login", response_model=LoginResponse, summary="登录（静态 admin 验证）")
def login(payload: LoginRequest):
    if not payload.username or not payload.password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="用户名或密码为空"
        )

    if payload.username != ADMIN_USERNAME or payload.password != ADMIN_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误"
        )

    return LoginResponse(access_token=STATIC_TOKEN)
