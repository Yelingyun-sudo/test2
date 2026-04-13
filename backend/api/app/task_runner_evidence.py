from __future__ import annotations

"""这个就是取证任务执行器"""
"""核心职责是：不断地从数据库中领取“待处理”的任务，驱动浏览器去完成登录、截图、取证等操作，并把最终的结果写回数据库。"""
"""
整个文件分为三层：
1. 指令与结果处理层（辅助函数）
2. 数据库状态管理层（状态流转）
3. 核心执行层（工匠干活）
4. 调度与并发控制层（工头调度）
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session
from website_analytics.cli import run_single_instruction_async
from website_analytics.orchestrator import ExecutionResult
from website_analytics.settings import get_settings
from website_analytics.utils import to_project_relative

from .db import SessionLocal
from .enums import TaskReportStatus, TaskStatus
from .models import EvidenceTask

logger = logging.getLogger(__name__)


# 构建任务指令字符串
# 作用：把数据库里的任务记录翻译成发给 AI Agent 的自然语言指令。
def _build_instruction(task: EvidenceTask) -> str:
    """构建证据任务执行指令。

    根据 account/password 是否存在，生成不同的指令：
    - 有账密：登录 {url}（账号和密码分别为 {account} 和 {password}）并完成取证
    - 无账密：访问 {url} 并完成取证
    """
    if task.account and task.password:
        return f"登录 {task.url}（账号和密码分别为 {task.account} 和 {task.password}）并完成取证"
    else:
        return f"访问 {task.url} 注册账号并登录，最终完成取证"


# 从执行结果提取成功信息
# 作用：AI Agent 干完活会返回一大堆复杂的 JSON 数据，这两个函数负责从中提炼出人类能看懂的简报。
def _extract_success_result(exec_result: ExecutionResult | None) -> str:
    """从 ExecutionResult 提取成功结果（取证摘要）。

    返回格式：
    - "取证完成。成功 3/3 个入口。报告：evidence/report.md"
    - "注册成功 → 登录成功 → 取证完成。成功 3/3 个入口。报告：evidence/report.md"
    - "注册（账号已存在）→ 登录成功 → 取证完成。成功 3/3 个入口。报告：evidence/report.md"
    """
    if not exec_result or not exec_result.coordinator_output:
        return "任务结果不可用"
    try:
        coordinator = exec_result.coordinator_output
        operations_results = coordinator.get("operations_results") or {}

        # 收集操作流程步骤
        steps = []

        # 1. 提取注册状态（如果有）
        register_result = operations_results.get("register")
        if register_result:
            register_message = register_result.get("message", "")
            if "账号已存在" in register_message:
                steps.append("注册（账号已存在）")
            elif register_result.get("success"):
                steps.append("注册成功")

        # 2. 提取登录状态（如果有）
        login_result = operations_results.get("login")
        if login_result and login_result.get("success"):
            steps.append("登录成功")

        # 3. 提取取证信息
        evidence_result = operations_results.get("evidence") or {}
        entries_total = evidence_result.get("entries_total", 0)
        entries_success = evidence_result.get("entries_success", 0)
        entries_failed = evidence_result.get("entries_failed", 0)
        report_file = evidence_result.get("report_file", "")
        message = evidence_result.get("message", "")

        # 构建取证摘要
        if entries_total > 0:
            evidence_summary = (
                f"取证完成。成功 {entries_success}/{entries_total} 个入口"
            )
            if entries_failed > 0:
                evidence_summary = (
                    f"取证部分成功。成功 {entries_success}/{entries_total} 个入口"
                )
        else:
            evidence_summary = message or "取证完成"

        if report_file:
            evidence_summary += f"。报告：{report_file}"

        # 4. 组合完整描述
        if steps:
            summary = " → ".join(steps) + " → " + evidence_summary
        else:
            summary = evidence_summary

        return summary
    except Exception as exc:  # pragma: no cover - 防御性处理
        return f"解析任务结果失败: {exc}"


# 从执行结果提取失败信息
"""
当任务执行失败时可能会有各种错误来源，按照优先级顺序，从这些杂乱的信息中“挖掘”出最有价值的错误原因，最终返回一个清晰的字符串给用户或日志。
第一优先级：协调器的输出消息（最详细）
第二优先级：执行结果对象的默认消息（次详细） 尝试直接读取 exec_result.message 属性。这通常是执行框架自带的错误摘要。
第三优先级：Python 异常信息（兜底信息）
"""


def _extract_failure_result(
    exec_result: ExecutionResult | None,
    exc: Exception | None = None,
) -> str:
    """从 ExecutionResult 提取失败结果信息。"""
    # 优先使用 ExecutionResult 中的消息
    # 如果执行结果对象 exec_result 存在，并且里面有 coordinator_output（通常是字典类型的详细输出），它就尝试从中提取 message 字段。
    if exec_result and exec_result.coordinator_output:
        try:
            message = exec_result.coordinator_output.get("message")
            if message:
                return str(message)
        except Exception as parse_exc:  # pragma: no cover - 防御性处理
            return f"解析失败信息时出错: {parse_exc}"

    # 其次使用 ExecutionResult.message 属性
    if exec_result:
        try:
            return exec_result.message
        except Exception:
            pass

    # 最后使用异常信息
    if exc is not None:
        return f"执行异常：{exc.__class__.__name__}: {str(exc)}"

    return "任务失败，未提供错误信息"


# 格式化失败类型
"""
给失败任务贴标签
上一个函数 _extract_failure_result 是为了弄清楚“发生了什么具体事”（详细的错误日志），那么这个函数就是为了弄清楚“这属于哪一类问题”（分类标签）。
核心逻辑：三层判定顺序
第一优先级：执行超时
第二优先级：业务层错误
    判定：如果没有超时，任务正常跑完了，但是结果判定为失败。
    逻辑：去 coordinator_output（协调器输出）里找 error_type 字段。
    价值：这是最宝贵的错误信息。
    比如你的 AI 任务跑完后，发现“网页登录失败”，它会在结果里填 error_type: "login_failed"。
    或者“网页打不开”，填 error_type: "page_unreachable"。
    这能让用户精准知道是业务流程的哪一步出了问题，而不是只看到一个模糊的“未知错误”。
第三优先级：兜底分类
    判定：既没超时，执行结果里也没有明确的 error_type。
    逻辑：统一归类为 "unknown_error"。
"""


def _format_failure_type(
    exc: Exception | None,
    timed_out: bool,
    exec_result: ExecutionResult | None = None,
) -> str:
    """格式化失败类型，优先使用业务层 error_type。

    优先级:
    1. 执行超时 → "task_timeout"
    2. 业务层错误 → coordinator_output.error_type
    3. 执行异常或兜底 → "unknown_error"（异常详情记录在 result 中）
    """
    if timed_out:
        return "task_timeout"

    # 从 exec_result 的 coordinator_output 读取业务层 error_type
    if exec_result and exec_result.coordinator_output:
        error_type = exec_result.coordinator_output.get("error_type")
        if error_type:
            return str(error_type)

    # 统一为 unknown_error，异常详情在 result 字段中
    return "unknown_error"


# 提取注册得到的账号密码
"""作用：这是一个非常贴心的功能。如果任务是因为“没有账号”而自动注册的，它会从执行结果里把新注册的账号密码抠出来。"""


def _extract_credentials(
    exec_result: ExecutionResult | None,
) -> tuple[str | None, str | None]:
    """从执行结果中提取注册得到的账号密码。

    Args:
        exec_result: 任务执行结果

    Returns:
        (account, password) 元组，如果未找到则返回 (None, None)
    """
    if not exec_result or not exec_result.coordinator_output:
        return None, None

    try:
        operations_results = (
            exec_result.coordinator_output.get("operations_results") or {}
        )
        register_result = operations_results.get("register") or {}

        account = register_result.get("account")
        password = register_result.get("password")

        # 只有注册成功才返回凭据
        if register_result.get("success") and account and password:
            return account, password
    except Exception:  # pragma: no cover - 防御性处理
        pass

    return None, None


# 更新任务状态为 RUNNING
"""作用：抢到任务后，先把状态改成 RUNNING，锁住这个任务，防止被其他进程重复执行。"""


def _mark_running(db: Session, task: EvidenceTask) -> None:
    task.status = TaskStatus.RUNNING
    task.executed_at = datetime.now(timezone.utc)
    db.add(task)
    db.commit()
    db.refresh(task)


# 更新任务为成功状态
"""
作用：任务结束后，更新最终状态。
细节：不仅记录成功或失败，还记录了耗时（duration）、失败原因（failure_type）、Token 消耗（llm_usage），甚至会把刚才提取到的新账号密码回填进数据库。
"""


def _update_task_success(
    db: Session,
    task: EvidenceTask,
    *,
    duration: float,
    result: str,
    task_dir: str | None,
    llm_usage: dict[str, Any] | None = None,
    account: str | None = None,
    password: str | None = None,
) -> None:
    task.status = TaskStatus.SUCCESS
    task.duration_seconds = int(duration)
    task.result = result
    task.task_dir = task_dir
    task.failure_type = None
    task.report_status = TaskReportStatus.PENDING
    task.llm_usage = llm_usage

    # 更新账号密码（如果有）
    if account and password:
        task.account = account
        task.password = password

    db.add(task)
    db.commit()


# 更新任务为失败状态
def _update_task_failure(
    db: Session,
    task: EvidenceTask,
    *,
    duration: float,
    result: str,
    failure_type: str,
    task_dir: str | None,
    llm_usage: dict[str, Any] | None = None,
    account: str | None = None,
    password: str | None = None,
) -> None:
    task.status = TaskStatus.FAILED
    task.duration_seconds = int(duration)
    task.result = result
    task.task_dir = task_dir
    task.failure_type = failure_type
    task.report_status = TaskReportStatus.PENDING
    task.llm_usage = llm_usage

    # 即使任务失败，也保存注册得到的凭据
    if account and password:
        task.account = account
        task.password = password

    db.add(task)
    db.commit()


# 从数据库查询 PENDING 状态的任务
def _get_pending_batch(db: Session, limit: int = 1) -> list[EvidenceTask]:
    return (
        db.query(EvidenceTask)
        .filter(EvidenceTask.status == TaskStatus.PENDING)
        .order_by(EvidenceTask.id.asc())
        .limit(limit)
        .all()
    )


def _get_running_batch_before(
    db: Session, before_ts: datetime, limit: int = 1
) -> list[EvidenceTask]:
    return (
        db.query(EvidenceTask)
        .filter(
            EvidenceTask.status == TaskStatus.RUNNING,
            or_(
                EvidenceTask.executed_at.is_(None),
                EvidenceTask.executed_at < before_ts,
            ),
        )
        .order_by(
            EvidenceTask.executed_at.asc().nullsfirst(),
            EvidenceTask.created_at.asc(),
        )
        .limit(limit)
        .all()
    )


# 核心执行层
# 执行单个任务的核心函数
# 由async def process_once调用
"""
流程：
超时控制：设置了一个总超时时间（包含清理浏览器的时间），防止任务无限卡死。
调用大脑：调用 run_single_instruction_async，这通常是启动 Playwright 浏览器、连接 LLM 进行决策的核心入口。
结果回写：根据执行结果调用前面的 _update_task_... 函数更新数据库。
容错性：哪怕任务失败了，它也会尝试保存已经注册好的账号密码，防止资源浪费。
"""


async def _run_task(task_id: int, instruction: str) -> None:
    settings = get_settings()
    start_time = datetime.now(timezone.utc)
    exec_error: Exception | None = None
    timed_out = False

    try:
        # 为清理预留额外时间（用于 Playwright 优雅关闭和孤儿进程清理）
        execution_timeout = settings.task_runner_timeout_seconds
        cleanup_buffer = settings.playwright_cleanup_buffer_seconds

        logger.info("开始执行任务: task_id=%s, instruction=%s", task_id, instruction)
        exec_result = await asyncio.wait_for(
            run_single_instruction_async(
                instruction,
                headless=settings.task_runner_headless,
            ),
            timeout=execution_timeout + cleanup_buffer,  # 增加清理缓冲时间
        )
    except asyncio.TimeoutError:
        exec_result = None
        timed_out = True
    except Exception as exc:
        exec_result = None
        exec_error = exc

    duration = (datetime.now(timezone.utc) - start_time).total_seconds()
    task_dir_value = (
        to_project_relative(exec_result.task_dir)
        if exec_result and exec_result.task_dir
        else None
    )

    db = SessionLocal()
    try:
        task_obj = db.get(EvidenceTask, task_id)
        if not task_obj:
            return

        if exec_result and exec_result.success and exec_result.task_dir:
            result_text = _extract_success_result(exec_result)
            llm_usage = exec_result.llm_usage

            # 提取注册得到的凭据
            account, password = _extract_credentials(exec_result)

            _update_task_success(
                db,
                task_obj,
                duration=duration,
                result=result_text,
                task_dir=task_dir_value,
                llm_usage=llm_usage,
                account=account,
                password=password,
            )
            logger.info(
                "任务成功: id=%s, url=%s, result=%s",
                task_obj.id,
                task_obj.url,
                result_text,
            )
        else:
            result_text = _extract_failure_result(exec_result, exc=exec_error)
            llm_usage = exec_result.llm_usage if exec_result else None
            failure_type = _format_failure_type(exec_error, timed_out, exec_result)

            # 即使任务失败，也尝试提取注册得到的凭据
            account, password = _extract_credentials(exec_result)

            _update_task_failure(
                db,
                task_obj,
                duration=duration,
                result=result_text,
                failure_type=failure_type,
                task_dir=task_dir_value,
                llm_usage=llm_usage,
                account=account,
                password=password,
            )
            logger.warning(
                "任务失败: id=%s, url=%s, failure_type=%s, result=%s",
                task_obj.id,
                task_obj.url,
                failure_type,
                result_text,
            )
    finally:
        db.close()


# 4. 调度与并发控制层（工头调度）
# 这是整个文件最精妙的部分，负责管理并发和任务分发
# 单次调度：查询并标记任务
"""作用：它是“工头”，负责从任务池（数据库）里捞活。"""
"""
恢复机制：
    它有一个 recovering（恢复模式）逻辑。程序刚启动时，它会先查有没有上次意外中断导致状态卡在 RUNNING 的“僵尸任务”。
    如果有，优先重跑这些僵尸任务（数据恢复）。
    如果没有，才去捞 PENDING 的新任务。
并发控制：
    它接收一个 semaphore（信号量）。
    捞到任务后，它不会傻等任务做完，而是用 asyncio.create_task 把任务扔后台跑（异步非阻塞），然后立刻结束，准备下一次调度。这保证了调度器永远不会被具体的任务卡住。
"""
"""process_once调用_run_task"""


async def process_once(
    semaphore: asyncio.Semaphore,
    *,
    recovery_before: datetime | None,
    recovering: bool,
) -> bool:
    # 当前可用并发槽
    available = semaphore._value  # type: ignore[attr-defined]
    if available <= 0:
        return recovering

    db = SessionLocal()
    tasks: list[EvidenceTask] = []
    try:
        if recovering and recovery_before:
            tasks = _get_running_batch_before(db, recovery_before, limit=1)
            if not tasks:
                recovering = False

        if not tasks:
            tasks = _get_pending_batch(db, limit=1)
        if not tasks:
            return recovering

        for task in tasks:
            _mark_running(db, task)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    for task in tasks:
        instruction = _build_instruction(task)

        async def _worker(tid: int, instr: str):
            async with semaphore:
                await _run_task(tid, instr)

        asyncio.create_task(_worker(task.id, instruction))

    return recovering


# 主循环：每隔 N 秒检查并调度任务
"""作用：程序的入口，一个永不停止的 while True 循环。"""
"""
资源管理：它创建了一个 Semaphore（信号量），比如设置最大并发数为 3。这意味着哪怕数据库里有 100 个任务，同时跑的也只有 3 个，保护你的电脑不被挤爆。
节奏控制：每次循环睡几秒（interval），避免疯狂查询数据库浪费资源。
"""


async def run_evidence_runner_loop() -> None:
    settings = get_settings()
    interval = max(1, settings.task_runner_interval_seconds)
    max_concurrent = max(1, settings.task_runner_max_concurrent)
    semaphore = asyncio.Semaphore(max_concurrent)
    startup_ts = datetime.now(timezone.utc)
    recovering = True
    logger.info(
        "证据任务执行器已启动, interval=%ss, max_concurrent=%s",
        settings.task_runner_interval_seconds,
        settings.task_runner_max_concurrent,
    )

    while True:
        try:
            recovering = await process_once(
                semaphore, recovery_before=startup_ts, recovering=recovering
            )
        except Exception as exc:  # pragma: no cover - 防御性日志
            logger.exception("证据任务调度异常: %s", exc)
        await asyncio.sleep(interval)
