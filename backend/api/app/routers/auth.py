from fastapi import APIRouter, HTTPException, status

from ..schemas.auth import LoginRequest, LoginResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse, summary="登录（静态 mock）")
def login(payload: LoginRequest):
    if not payload.username or not payload.password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="用户名或密码为空"
        )

    # TODO: 后续接入真实认证/鉴权逻辑，调用 website_analytics 核心能力
    token = f"mock-token-for-{payload.username}"
    return LoginResponse(access_token=token)
