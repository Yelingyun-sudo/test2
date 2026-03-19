"""统计响应模型（跨模块通用）。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .common import (
    DailyTrendItem,
    FailureSummary,
    FailureTypeDistributionItem,
    StatusDistributionItem,
)


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


class FailureTypesStatsResponse(BaseModel):
    """失败类型统计响应"""

    failure_type_distribution: list[FailureTypeDistributionItem] = Field(
        ..., description="失败类型分布（Top 5 + 其他）"
    )
    failure_summary: FailureSummary = Field(..., description="失败总览")
