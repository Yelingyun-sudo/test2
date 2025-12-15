from pydantic import BaseModel, Field


class UnsubscribedItem(BaseModel):
    url: str = Field(..., description="未订阅站点 URL")
    created_at: str = Field(..., description="任务创建时间 ISO 字符串")


class UnsubscribedListResponse(BaseModel):
    items: list[UnsubscribedItem]
    total: int
    page: int
    page_size: int
