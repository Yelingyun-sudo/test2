"""类型定义模块。"""

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class ErrorType(str, Enum):
    """任务失败原因枚举（按业务优先级排序）。

    中文标签请参考 FAILURE_TYPE_LABELS 字典。
    """

    # 账号/套餐类
    ACCOUNT_BANNED = "account_banned"
    PLAN_EXPIRED = "plan_expired"

    # 网站访问类
    SITE_SERVER_ERROR = "site_server_error"
    SITE_NETWORK_ERROR = "site_network_error"
    SITE_DOMAIN_ERROR = "site_domain_error"
    LOGIN_PAGE_NOT_FOUND = "login_page_not_found"

    # 反自动化类
    ANTI_AUTOMATION_DETECTED = "anti_automation_detected"
    HUMAN_VERIFICATION_FAILED = "human_verification_failed"

    # 业务流程类
    COPY_BUTTON_NOT_FOUND = "copy_button_not_found"
    SUBSCRIPTION_URL_INVALID = "subscription_url_invalid"

    # 任务限制类
    TASK_TIMEOUT = "task_timeout"
    TASK_STEP_LIMIT = "task_step_limit"

    # 运行时错误类
    TASK_CLEANED = "task_cleaned"
    UNKNOWN_ERROR = "unknown_error"


# 失败类型中文标签映射（统一配置）
FAILURE_TYPE_LABELS: dict[str, str] = {
    # 账号/套餐类
    "account_banned": "账号被封禁",
    "plan_expired": "订阅套餐失效",
    # 网站访问类
    "site_server_error": "网站服务器错误",
    "site_network_error": "网站网络错误",
    "site_domain_error": "网站域名错误",
    "login_page_not_found": "登录页未找到",
    # 反自动化类
    "anti_automation_detected": "反自动化检测",
    "human_verification_failed": "人机验证失败",
    # 业务流程类
    "copy_button_not_found": "未找到复制按钮",
    "subscription_url_invalid": "订阅地址异常",
    # 任务限制类
    "task_timeout": "任务执行超时",
    "task_step_limit": "任务步骤超限",
    # 运行时错误类
    "task_cleaned": "任务已清理",
    "unknown_error": "未知错误",
}


def get_failure_types_ordered() -> list[dict[str, str]]:
    """获取按业务优先级排序的失败类型列表。

    Returns:
        失败类型列表，每项包含 value 和 label 字段。
    """
    # 按业务优先级排序
    ordered_types = [
        # 账号/套餐类
        "account_banned",
        "plan_expired",
        # 网站访问类
        "site_server_error",
        "site_network_error",
        "site_domain_error",
        "login_page_not_found",
        # 反自动化类
        "anti_automation_detected",
        "human_verification_failed",
        # 业务流程类
        "copy_button_not_found",
        "subscription_url_invalid",
        # 任务限制类
        "task_timeout",
        "task_step_limit",
        # 运行时错误类
        "task_cleaned",
        "unknown_error",
    ]

    return [
        {"value": type_value, "label": FAILURE_TYPE_LABELS[type_value]}
        for type_value in ordered_types
    ]


class LoginOutput(BaseModel):
    """登录代理的结构化输出。"""

    success: bool = Field(description="是否登录成功")
    message: str = Field(description="详细消息")
    error_type: str | None = Field(
        default=None,
        description="失败原因枚举值（success=false 时建议必填），取值范围同 CoordinatorOutput.error_type",
    )


class InspectOutput(BaseModel):
    """巡检代理的结构化输出。"""

    success: bool = Field(description="是否巡检成功（至少成功一个入口）")
    message: str = Field(description="详细消息")
    entries_total: int = Field(default=0, description="识别的入口总数")
    entries_success: int = Field(default=0, description="成功巡检的入口数")
    entries_failed: int = Field(default=0, description="失败的入口数")
    report_file: str = Field(default="", description="生成的报告文件路径")
    error_type: str | None = Field(
        default=None,
        description="失败原因枚举值（success=false 时建议必填），取值范围同 CoordinatorOutput.error_type",
    )


class ExtractOutput(BaseModel):
    """提取代理的结构化输出。"""

    success: bool = Field(description="是否提取成功")
    message: str = Field(description="详细消息")
    subscription_url: str = Field(default="", description="提取到的订阅链接（成功时）")
    error_type: str | None = Field(
        default=None,
        description="失败原因枚举值（success=false 时建议必填），取值范围同 CoordinatorOutput.error_type",
    )


class InspectEntryOutput(BaseModel):
    """单入口巡检代理的结构化输出。"""

    entry_id: str = Field(description="入口唯一标识")
    status: Literal["success", "failed"] = Field(description="巡检状态")
    screenshot: str | None = Field(default=None, description="截图文件路径（成功时）")
    text_snapshot: str | None = Field(
        default=None, description="文本快照文件路径（成功时）"
    )
    error: str | None = Field(default=None, description="错误信息（失败时）")


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
