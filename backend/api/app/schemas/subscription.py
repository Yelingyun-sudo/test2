from __future__ import annotations

from typing import Optional, TypeAlias

from pydantic import BaseModel, Field

from .common import LLMUsage, PaginatedListResponse


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


class SubscriptionStatsSummary(BaseModel):
    total_tasks: int = Field(..., description="总任务数")
    today_tasks: int = Field(..., description="今日新增任务数")
    success_count: int = Field(..., description="成功任务数")
    failed_count: int = Field(..., description="失败任务数")
    pending_count: int = Field(..., description="待执行任务数")
    running_count: int = Field(..., description="执行中任务数")
    success_rate: float = Field(..., description="成功率（0.0 - 1.0）")
    avg_success_duration_seconds: float = Field(
        ..., description="成功任务平均时长（秒）"
    )
    avg_failed_duration_seconds: float = Field(
        ..., description="失败任务平均时长（秒）"
    )
    total_tokens: int = Field(..., description="所有任务总 token 数")
    today_tokens: int = Field(..., description="今日任务总 token 数")
    avg_success_tokens: float = Field(..., description="成功任务平均 token")
    avg_failed_tokens: float = Field(..., description="失败任务平均 token")
    today_success_count: int = Field(..., description="今日成功任务数")
    today_failed_count: int = Field(..., description="今日失败任务数")
    today_success_rate: float = Field(..., description="今日成功率（0.0 - 1.0）")
    today_avg_success_duration_seconds: float = Field(
        ..., description="今日成功任务平均时长（秒）"
    )
    today_avg_failed_duration_seconds: float = Field(
        ..., description="今日失败任务平均时长（秒）"
    )
    today_avg_success_tokens: float = Field(..., description="今日成功任务平均 token")
    today_avg_failed_tokens: float = Field(..., description="今日失败任务平均 token")


class DailyTrendItem(BaseModel):
    date: str = Field(..., description="日期 ISO 格式 YYYY-MM-DD")
    total_count: int = Field(..., description="当日总任务数")
    success_count: int = Field(..., description="当日成功任务数")
    failed_count: int = Field(..., description="当日失败任务数")
    success_rate: float = Field(..., description="当日成功率（0.0 - 1.0）")


class StatusDistributionItem(BaseModel):
    status: str = Field(..., description="任务状态")
    count: int = Field(..., description="该状态的任务数量")


class RecentTaskItem(BaseModel):
    id: int = Field(..., description="任务 ID")
    url: str = Field(..., description="订阅站点 URL")
    status: str = Field(..., description="任务状态")
    executed_at: Optional[str] = Field(None, description="任务执行时间 ISO 字符串")
    duration_seconds: Optional[int] = Field(None, description="任务时长（秒）")
    result: Optional[str] = Field(None, description="任务结果")


class FailureTypeDistributionItem(BaseModel):
    type: str = Field(..., description="失败类型值")
    label: str = Field(..., description="失败类型中文标签")
    count: int = Field(..., description="该失败类型的任务数量")
    percentage: float = Field(..., description="占失败任务总数的百分比（0.0 - 100.0）")


class FailureSummary(BaseModel):
    total_failed: int = Field(..., description="失败任务总数")
    unique_types: int = Field(..., description="失败类型数量")


class SubscriptionStatsResponse(BaseModel):
    summary: Optional[SubscriptionStatsSummary] = Field(None, description="汇总统计")
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

    summary: SubscriptionStatsSummary = Field(..., description="汇总统计数据")


class DailyTrendResponse(BaseModel):
    """每日趋势响应"""

    daily_trend: list[DailyTrendItem] = Field(
        ..., description="每日趋势数据（最近10天）"
    )


class StatusDistributionResponse(BaseModel):
    """状态分布响应"""

    status_distribution: list[StatusDistributionItem] = Field(
        ..., description="状态分布数据"
    )


class RecentTasksResponse(BaseModel):
    """最新任务响应"""

    recent_tasks: list[SubscriptionItem] = Field(
        ..., description="最新任务列表（最近5条）"
    )


class FailureTypesStatsResponse(BaseModel):
    """失败类型统计响应"""

    failure_type_distribution: list[FailureTypeDistributionItem] = Field(
        ..., description="失败类型分布（Top 5 + 其他）"
    )
    failure_summary: FailureSummary = Field(..., description="失败总览")
