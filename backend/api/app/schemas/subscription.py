from __future__ import annotations

from typing import Optional, TypeAlias

from pydantic import BaseModel, Field

from .common import (
    DailyTrendItem,
    FailureSummary,
    FailureTypeDistributionItem,
    LLMUsage,
    PaginatedListResponse,
    StatusDistributionItem,
    TaskStatsSummary,
)


class SubscriptionItem(BaseModel):
    id: int = Field(..., description="任务 ID")
    url: str = Field(..., description="订阅站点 URL")
    account: str = Field(..., description="账号")
    password: str = Field(..., description="密码")
    status: str = Field(..., description="任务状态")
    created_at: str = Field(..., description="任务创建时间 ISO 字符串")
    duration_seconds: int = Field(..., description="任务时长（秒）")
    executed_at: Optional[str] = Field(None, description="任务执行时间 ISO 字符串")
    task_dir: Optional[str] = Field(None, description="任务目录（相对 backend 根目录）")
    result: Optional[str] = Field(None, description="任务结果")
    failure_type: Optional[str] = Field(None, description="失败类型（仅失败任务）")
    llm_usage: Optional[LLMUsage] = Field(None, description="LLM token 使用统计")


SubscriptionListResponse: TypeAlias = PaginatedListResponse[SubscriptionItem]


class SubscriptionArtifactsResponse(BaseModel):
    status: str = Field(..., description="任务状态")
    login_image_path: Optional[str] = Field(None, description="登录截图相对路径")
    extract_image_path: Optional[str] = Field(None, description="提取截图相对路径")
    video_path: Optional[str] = Field(None, description="视频相对路径")
    video_seek_seconds: Optional[float] = Field(None, description="视频建议 seek 秒数")


class RecentTaskItem(BaseModel):
    id: int = Field(..., description="任务 ID")
    url: str = Field(..., description="订阅站点 URL")
    status: str = Field(..., description="任务状态")
    executed_at: Optional[str] = Field(None, description="任务执行时间 ISO 字符串")
    duration_seconds: Optional[int] = Field(None, description="任务时长（秒）")
    result: Optional[str] = Field(None, description="任务结果")


class SubscriptionStatsResponse(BaseModel):
    summary: Optional[TaskStatsSummary] = Field(None, description="汇总统计")
    daily_trend: Optional[list[DailyTrendItem]] = Field(
        None, description="每日趋势（最近10天）"
    )
    status_distribution: Optional[list[StatusDistributionItem]] = Field(
        None, description="状态分布"
    )
    recent_tasks: Optional[list[SubscriptionItem]] = Field(
        None, description="最新任务列表（最近6条，完整数据）"
    )
    failure_type_distribution: Optional[list[FailureTypeDistributionItem]] = Field(
        None, description="失败类型分布（Top 5 + 其他）"
    )
    failure_summary: Optional[FailureSummary] = Field(None, description="失败总览")


# ===== 专用端点响应模型 =====


class SummaryResponse(BaseModel):
    """汇总统计响应"""

    summary: TaskStatsSummary = Field(..., description="汇总统计数据")


class RecentTasksResponse(BaseModel):
    """最新任务响应"""

    recent_tasks: list[SubscriptionItem] = Field(
        ..., description="最新任务列表（最近5条）"
    )
