"""类型定义模块。"""

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class ErrorType(str, Enum):
    """任务失败原因枚举。"""

    PLAN_EXPIRED = "plan_expired"  # 订阅套餐已失效
    ACCOUNT_BANNED = "account_banned"  # 账号被封禁
    SITE_SERVER_ERROR = "site_server_error"  # 网站无法访问-服务器错误
    SITE_NETWORK_ERROR = "site_network_error"  # 网站无法访问-网络错误
    SITE_DOMAIN_ERROR = "site_domain_error"  # 网站无法访问-域名错误
    TASK_TIMEOUT = "task_timeout"  # 任务执行超时
    TASK_STEP_LIMIT = "task_step_limit"  # 任务执行步骤超限
    COPY_BUTTON_NOT_FOUND = "copy_button_not_found"  # 未找到订阅复制按钮
    ANTI_AUTOMATION_DETECTED = "anti_automation_detected"  # 网站有反自动化检测
    LOGIN_PAGE_NOT_FOUND = "login_page_not_found"  # 网站无法找到登录页
    HUMAN_VERIFICATION_FAILED = "human_verification_failed"  # 无法完成人机验
    SUBSCRIPTION_URL_INVALID = "subscription_url_invalid"  # 订阅地址异常
    UNKNOWN_ERROR = "unknown_error"  # 兜底


class LoginOutput(BaseModel):
    """登录代理的结构化输出。"""

    success: bool = Field(description="是否登录成功")
    message: str = Field(description="详细消息")


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

    status: Literal["success", "failed"] = Field(
        description="任务整体状态：success 表示成功，failed 表示失败"
    )

    message: str = Field(
        description="给用户的详细消息，包含操作总结、生成的文件、错误原因等"
    )
    error_type: ErrorType | None = Field(
        default=None,
        description="任务失败原因，status=failed 时填写，success 时为 None",
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
