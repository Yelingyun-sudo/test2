from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, description="用户名")
    password: str = Field(..., min_length=1, description="密码")


class LoginResponse(BaseModel):
    access_token: str = Field(..., description="静态示例 token，后续对接真实鉴权")
    token_type: str = Field(default="bearer")
