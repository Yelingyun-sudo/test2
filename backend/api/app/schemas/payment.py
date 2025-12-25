from typing import TypeAlias

from pydantic import BaseModel, Field

from .common import PaginatedListResponse


class PaymentItem(BaseModel):
    id: int = Field(..., description="记录 ID")
    url: str = Field(..., description="支付链接 URL")
    created_at: str = Field(..., description="任务创建时间 ISO 字符串")


PaymentListResponse: TypeAlias = PaginatedListResponse[PaymentItem]
