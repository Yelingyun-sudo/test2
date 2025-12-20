from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class SubscribedItem(BaseModel):
    id: int = Field(..., description="任务 ID")
    url: str = Field(..., description="订阅站点 URL")
    account: str = Field(..., description="账号")
    password: str = Field(..., description="密码")
    status: str = Field(..., description="任务状态")
    created_at: str = Field(..., description="任务创建时间 ISO 字符串")
    duration_seconds: int = Field(..., description="任务时长（秒）")
    retry_count: int = Field(..., description="重试次数")
    history_extract_count: int = Field(..., description="历史提取次数")
    executed_at: Optional[str] = Field(None, description="任务执行时间 ISO 字符串")
    task_dir: Optional[str] = Field(None, description="任务目录（相对 backend 根目录）")
    result: Optional[str] = Field(None, description="任务结果")


class SubscribedListResponse(BaseModel):
    items: list[SubscribedItem]
    total: int
    page: int
    page_size: int


class SubscribedArtifactsResponse(BaseModel):
    status: str = Field(..., description="任务状态")
    login_image_path: Optional[str] = Field(None, description="登录截图相对路径")
    extract_image_path: Optional[str] = Field(None, description="提取截图相对路径")
    video_path: Optional[str] = Field(None, description="视频相对路径")
    video_seek_seconds: Optional[float] = Field(None, description="视频建议 seek 秒数")


class SubscribedStatsSummary(BaseModel):
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


class SubscribedStatsResponse(BaseModel):
    summary: SubscribedStatsSummary = Field(..., description="汇总统计")
    daily_trend: list[DailyTrendItem] = Field(..., description="每日趋势（最近10天）")
    status_distribution: list[StatusDistributionItem] = Field(
        ..., description="状态分布"
    )
    recent_tasks: list[RecentTaskItem] = Field(
        ..., description="最近任务列表（最近5条）"
    )
