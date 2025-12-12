from pydantic import BaseModel, Field


class SubscribedItem(BaseModel):
    id: int = Field(..., description="任务 ID")
    url: str = Field(..., description="订阅站点 URL")
    account: str = Field(..., description="账号")
    password: str = Field(..., description="密码")
    status: str = Field(..., description="任务状态")
    duration_seconds: int = Field(..., description="任务时长（秒）")
    retry_count: int = Field(..., description="重试次数")
    history_extract_count: int = Field(..., description="历史提取次数")
    executed_at: str | None = Field(
        None, description="任务执行时间 ISO 字符串"
    )
    task_dir: str | None = Field(None, description="任务目录（相对 backend 根目录）")
    result: str | None = Field(None, description="任务结果")


class SubscribedListResponse(BaseModel):
    items: list[SubscribedItem]
    total: int
    page: int
    page_size: int
