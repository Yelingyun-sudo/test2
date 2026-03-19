from __future__ import annotations

from typing import Generic, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class LLMUsage(BaseModel):
    """LLM token 使用统计。"""

    total_input_tokens: int = Field(..., description="总输入 token 数")
    total_output_tokens: int = Field(..., description="总输出 token 数")
    total_tokens: int = Field(..., description="总 token 数")
    llm_turns: int = Field(..., description="LLM 调用轮次")
    total_cached_tokens: Optional[int] = Field(None, description="缓存 token 数")
    total_reasoning_tokens: Optional[int] = Field(None, description="推理 token 数")


class FailureTypeItem(BaseModel):
    """失败类型项。"""

    value: str = Field(..., description="失败类型值")
    label: str = Field(..., description="失败类型中文标签")


class FailureTypesResponse(BaseModel):
    """失败类型列表响应。"""

    items: list[FailureTypeItem] = Field(
        ..., description="失败类型列表（按业务优先级排序）"
    )


class PaginatedListResponse(BaseModel, Generic[T]):
    """分页列表响应（泛型）。"""

    items: list[T] = Field(..., description="当前页的数据项列表")
    total: int = Field(..., description="总记录数")
    page: int = Field(..., description="当前页码（从 1 开始）")
    page_size: int = Field(..., description="每页记录数")


class DailyTrendItem(BaseModel):
    """每日趋势数据项"""

    date: str = Field(..., description="日期 ISO 格式 YYYY-MM-DD")
    total_count: int = Field(..., description="当日总任务数")
    success_count: int = Field(..., description="当日成功任务数")
    failed_count: int = Field(..., description="当日失败任务数")
    success_rate: float = Field(..., description="当日成功率（0.0 - 1.0）")


class StatusDistributionItem(BaseModel):
    """状态分布数据项"""

    status: str = Field(..., description="任务状态")
    count: int = Field(..., description="该状态的任务数量")


class FailureTypeDistributionItem(BaseModel):
    """失败类型分布数据项"""

    type: str = Field(..., description="失败类型值")
    label: str = Field(..., description="失败类型中文标签")
    count: int = Field(..., description="该失败类型的任务数量")
    percentage: float = Field(..., description="占失败任务总数的百分比（0.0 - 100.0）")


class FailureSummary(BaseModel):
    """失败任务总览"""

    total_failed: int = Field(..., description="失败任务总数")
    unique_types: int = Field(..., description="失败类型数量")


class TaskStatsSummary(BaseModel):
    """任务统计汇总（通用）"""

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
