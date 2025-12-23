from pydantic import BaseModel, Field


class PaymentItem(BaseModel):
    id: int = Field(..., description="记录 ID")
    url: str = Field(..., description="支付链接 URL")
    created_at: str = Field(..., description="任务创建时间 ISO 字符串")


class PaymentListResponse(BaseModel):
    items: list[PaymentItem]
    total: int
    page: int
    page_size: int
