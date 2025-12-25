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

