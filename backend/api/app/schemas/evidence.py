from pydantic import BaseModel, Field


class EvidenceItem(BaseModel):
    id: int = Field(..., description="记录 ID")
    url: str = Field(..., description="未订阅站点 URL")
    created_at: str = Field(..., description="任务创建时间 ISO 字符串")


class EvidenceListResponse(BaseModel):
    items: list[EvidenceItem]
    total: int
    page: int
    page_size: int
