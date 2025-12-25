from pydantic import BaseModel, Field


class EvidenceItem(BaseModel):
    id: int = Field(..., description="记录 ID")
    url: str = Field(..., description="未订阅站点 URL")
    account: str | None = Field(None, description="账号")
    password: str | None = Field(None, description="密码")
    status: str = Field(..., description="任务状态")
    created_at: str = Field(..., description="任务创建时间 ISO 字符串")
    executed_at: str = Field(..., description="任务执行时间 ISO 字符串")
    duration_seconds: int = Field(..., description="任务时长（秒）")
    result: str | None = Field(None, description="任务结果")
    failure_type: str | None = Field(None, description="失败类型")
    task_dir: str | None = Field(None, description="任务目录")
    llm_usage: dict | None = Field(None, description="LLM 使用统计")


class EvidenceListResponse(BaseModel):
    items: list[EvidenceItem]
    total: int
    page: int
    page_size: int
