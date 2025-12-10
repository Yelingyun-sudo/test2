from pydantic import BaseModel, Field


class SubscribedItem(BaseModel):
  url: str = Field(..., description="订阅站点 URL")
  account: str = Field(..., description="账号")
  password: str = Field(..., description="密码")


class SubscribedListResponse(BaseModel):
  items: list[SubscribedItem]
  total: int
  page: int
  page_size: int
