from typing import TypeAlias

"""文件整体作用：定义支付任务相关的 Pydantic schema，用于 API 的请求/响应验证、响应序列化和api文档生成。"""
"""数据模型（ORM）用于数据库操作，而 Pydantic 模型用于 API 层的数据传输和验证。它是 API 接口与内部数据模型（models/payment_task.py）之间的转换层。"""
from pydantic import BaseModel, Field

from .common import LLMUsage, PaginatedListResponse, TaskStatsSummary


# 用途：表示列表页中单个支付任务项的展示信息。
# 作用：作为 /list 接口中 items 数组的元素类型。
class PaymentItem(BaseModel):
    """支付任务项，用于列表展示"""

    id: int = Field(..., description="记录 ID")
    url: str = Field(..., description="支付页面 URL")
    account: str = Field(..., description="登录账号")
    password: str = Field(..., description="登录密码")
    status: str = Field(..., description="任务状态：PENDING/RUNNING/SUCCESS/FAILED")
    duration_seconds: int = Field(default=0, description="执行耗时（秒）")
    executed_at: str | None = Field(default=None, description="实际开始执行时间")
    task_dir: str | None = Field(default=None, description="任务执行目录")
    result: str | None = Field(default=None, description="任务执行结果")
    failure_type: str | None = Field(default=None, description="失败类型")
    llm_usage: LLMUsage | None = Field(default=None, description="LLM token 使用统计")
    created_at: str = Field(..., description="任务创建时间 ISO 字符串")


# 用于 /payment/{task_id}/artifacts 接口的响应，返回任务执行过程中生成的产物路径元数据
# 作用：前端可以通过这些路径拼接下载 URL 来获取实际文件。
class PaymentArtifactsResponse(BaseModel):
    """支付任务产物响应"""

    status: str = Field(..., description="任务状态")
    qr_code_image: str | None = Field(
        default=None, description="支付二维码图片相对路径"
    )
    login_image_path: str | None = Field(default=None, description="登录截图相对路径")
    video_path: str | None = Field(default=None, description="视频相对路径")
    video_seek_seconds: float | None = Field(
        default=None, description="视频建议 seek 秒数"
    )
    # 三张关键截图
    screenshot_1: str | None = Field(
        default=None, description="订阅页面截图（含域名和订阅/套餐购买标注）"
    )
    screenshot_2: str | None = Field(default=None, description="支付方式选择页面截图")
    screenshot_3: str | None = Field(default=None, description="支付二维码页面截图")


# 用途：封装 /stats/summary 接口的返回数据。
# 作用：提供统计仪表盘所需的关键指标。
class SummaryResponse(BaseModel):
    """汇总统计响应"""

    summary: TaskStatsSummary = Field(
        ..., description="汇总统计数据"
    )  # TaskStatsSummary 对象（定义在 common.py 中），如总任务数、成功数、失败数、成功率等汇总信息。


# 用途：用于 /stats/recent-tasks 接口，返回最近的任务列表（最多 100 条）。
# 作用：展示最近执行的任务，便于监控和调试。
class RecentTasksResponse(BaseModel):
    """最新任务响应"""

    recent_tasks: list[PaymentItem] = Field(..., description="最新任务列表（最近5条）")


PaymentListResponse: TypeAlias = PaginatedListResponse[PaymentItem]
