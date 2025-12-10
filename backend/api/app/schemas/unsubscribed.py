from pydantic import BaseModel, Field


class UnsubscribedItem(BaseModel):
    url: str = Field(..., description="未订阅站点 URL")


class UnsubscribedListResponse(BaseModel):
    items: list[UnsubscribedItem]
    total: int
    page: int
    page_size: int
