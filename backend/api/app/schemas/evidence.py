from __future__ import annotations

from typing import TypeAlias

from pydantic import BaseModel, Field

from .common import (
    LLMUsage,
    PaginatedListResponse,
)


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
    llm_usage: LLMUsage | None = Field(None, description="LLM 使用统计")


EvidenceListResponse: TypeAlias = PaginatedListResponse[EvidenceItem]


# ===== 统计相关 Schema =====


class EvidenceStatsSummary(BaseModel):
    """取证任务汇总统计"""

    total_tasks: int = Field(..., description="总执行任务数（SUCCESS + FAILED）")
    pending_count: int = Field(..., description="待执行任务数")
    running_count: int = Field(..., description="执行中任务数")
    today_success_count: int = Field(..., description="时间范围内成功任务数")
    today_failed_count: int = Field(..., description="时间范围内失败任务数")
    today_tokens: int = Field(..., description="时间范围内总 token 数")
    today_avg_success_tokens: float = Field(
        ..., description="时间范围内成功任务平均 token"
    )
    today_avg_failed_tokens: float = Field(
        ..., description="时间范围内失败任务平均 token"
    )
    today_avg_success_duration_seconds: float = Field(
        ..., description="时间范围内成功任务平均时长（秒）"
    )
    today_avg_failed_duration_seconds: float = Field(
        ..., description="时间范围内失败任务平均时长（秒）"
    )


# ===== 统计响应 Schema =====


class SummaryResponse(BaseModel):
    """汇总统计响应"""

    summary: EvidenceStatsSummary


class RecentTasksResponse(BaseModel):
    """最新任务列表响应"""

    recent_tasks: list[EvidenceItem]
