"""类型定义模块。"""

from typing import Any, Literal

from pydantic import BaseModel, Field


class LoginOutput(BaseModel):
    """登录代理的结构化输出。"""

    success: bool = Field(description="是否登录成功")
    message: str = Field(description="详细消息")
    login_form_found: bool = Field(default=False, description="是否找到登录表单")


class InspectOutput(BaseModel):
    """巡检代理的结构化输出。"""

    success: bool = Field(description="是否巡检成功（至少成功一个入口）")
    message: str = Field(description="详细消息")
    entries_total: int = Field(default=0, description="识别的入口总数")
    entries_success: int = Field(default=0, description="成功巡检的入口数")
    entries_failed: int = Field(default=0, description="失败的入口数")
    report_file: str = Field(default="", description="生成的报告文件路径")


class ExtractOutput(BaseModel):
    """提取代理的结构化输出。"""

    success: bool = Field(description="是否提取成功")
    message: str = Field(description="详细消息")
    subscription_url: str = Field(default="", description="提取到的订阅链接（成功时）")


class InspectEntryOutput(BaseModel):
    """单入口巡检代理的结构化输出。"""

    entry_id: str = Field(description="入口唯一标识")
    status: Literal["success", "failed"] = Field(description="巡检状态")
    screenshot: str | None = Field(default=None, description="截图文件路径（成功时）")
    text_snapshot: str | None = Field(
        default=None, description="文本快照文件路径（成功时）"
    )
    error: str | None = Field(default=None, description="错误信息（失败时）")
    summary: str = Field(
        description="1-3 句中文总结，成功时提炼业务信息，失败时详述原因"
    )


class CoordinatorOutput(BaseModel):
    """协调代理的结构化输出。"""

    status: Literal["SUCCESS", "FAILED"] = Field(
        description="任务整体状态：SUCCESS 表示成功，FAILED 表示失败"
    )

    message: str = Field(
        description="给用户的详细消息，包含操作总结、生成的文件、错误原因等"
    )

    operations_executed: list[str] = Field(
        default_factory=list,
        description="实际执行的操作列表，例如 ['login', 'inspect']",
    )

    operations_results: dict[str, Any] = Field(
        default_factory=dict,
        description="""各操作的完整结果（原始 JSON）。
        key: 操作名称（login/inspect/extract）
        value: 该操作的完整输出对象（直接保存子工具返回的 JSON，不要修改）

        示例：login 和 inspect 的完整 JSON 对象会原样保存。

        优势：保留所有结构化信息，便于后续统计分析和报告生成。
        """,
    )
