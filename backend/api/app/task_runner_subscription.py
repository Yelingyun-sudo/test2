"""订阅任务链接提取执行器：
它的职责是：
从数据库中读取待处理的 SubscriptionTask 记录（如账号密码、目标 URL）

构造指令字符串（例如“登录某网站并提取订阅地址”）

调用底层的指令执行引擎 run_single_instruction_async 来实际执行自动化任务（基于 Playwright 浏览器自动化）

将执行结果（成功或失败）持久化回数据库，包括执行耗时、返回的订阅地址、失败原因类型、任务目录等

支持并发控制（通过信号量）和任务恢复（恢复那些被标记为 RUNNING 但可能因异常中断的任务）

这个模块通常作为后台常驻任务运行，定期扫描并调度待执行的任务。
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from website_analytics.cli import run_single_instruction_async
from website_analytics.orchestrator import ExecutionResult
from website_analytics.settings import get_settings
from website_analytics.utils import to_project_relative

from .db import SessionLocal
from .models import SubscriptionTask
from .enums import TaskReportStatus, TaskStatus

logger = logging.getLogger(__name__)


# 工具函数与业务辅助函数
# 根据任务对象构建一条人类可读的指令字符串，供自动化引擎执行。
def _build_instruction(task: SubscriptionTask) -> str:
    return f"登录 {task.url}（账号和密码分别为 {task.account} 和 {task.password}）并提取订阅地址"


# 工具函数
# 从执行结果对象中提取成功时的订阅地址。
"""逻辑：
如果 exec_result 为空或没有 coordinator_output，返回 "任务结果不可用"。

否则尝试从 coordinator_output["operations_results"]["extract"]["subscription_url"] 中获取订阅地址。

如果提取成功则返回该 URL 字符串，否则返回 "未返回订阅地址"。

捕获任何异常（防御性）返回错误信息。
"""


def _extract_success_result(exec_result: ExecutionResult | None) -> str:
    """从 ExecutionResult 提取成功结果（订阅地址）。"""
    if not exec_result or not exec_result.coordinator_output:
        return "任务结果不可用"
    try:
        coordinator = exec_result.coordinator_output
        operations_results = coordinator.get("operations_results") or {}
        extract_result = operations_results.get("extract") or {}
        url = extract_result.get("subscription_url")
        if url:
            return str(url)
        return "未返回订阅地址"
    except Exception as exc:  # pragma: no cover - 防御性处理
        return f"解析任务结果失败: {exc}"


# 从执行结果或异常中提取失败时的错误信息，用于存入任务结果字段。
"""优先级：
如果 exec_result 及其 coordinator_output 存在，尝试从中获取 "message" 字段（业务层提供的错误消息）。
否则尝试从 exec_result.message 属性获取（如果存在）。
否则若提供了异常对象 exc，则返回其类型和消息。
最后兜底返回 "任务失败，未提供错误信息"。"""


def _extract_failure_result(
    exec_result: ExecutionResult | None,
    exc: Exception | None = None,
) -> str:
    """从 ExecutionResult 提取失败结果信息。"""
    # 优先使用 ExecutionResult 中的消息
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


# 根据执行结果和异常情况，生成一个标准化的失败类型字符串，用于后续统计和监控。
"""
逻辑：
如果 timed_out 为 True（由 asyncio.TimeoutError 触发），返回 "task_timeout"。
否则，如果 exec_result 及其 coordinator_output 包含 "error_type" 字段，则返回该字段的值（业务层定义的错误类型，例如 login_failed、extract_failed）。
否则返回 "unknown_error"。
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


# 作用：将任务状态更新为 RUNNING，并记录执行开始时间（UTC），然后提交到数据库。
# 用途：在任务真正开始执行前，将该任务标记为”运行中”，防止其他调度器重复拾取，也用于恢复检测。
def _mark_running(db: Session, task: SubscriptionTask) -> None:
    task.status = TaskStatus.RUNNING
    task.executed_at = datetime.now(timezone.utc)
    task.execution_count += 1
    task.retry_at = None  # 开始执行后清除重试时间
    db.add(task)
    db.commit()
    db.refresh(task)


# 作用：更新任务为成功状态。
"""
逻辑：设置 status = SUCCESS，清空 failure_type，设置 report_status = PENDING（表示需要生成报告），记录耗时、结果、目录和 LLM 用量。
"""


def _update_task_success(
    db: Session,  # 数据库会话
    task: SubscriptionTask,  # 任务对象
    *,
    duration: float,  # 执行耗时（秒）
    result: str,  # 提取到的订阅地址（成功结果）
    task_dir: str | None,  # 任务执行过程中生成的临时目录（相对路径）
    llm_usage: dict[str, Any] | None = None,  # LLM 使用统计（可选）
) -> None:
    task.status = TaskStatus.SUCCESS
    task.duration_seconds = int(duration)
    task.result = result
    task.task_dir = task_dir
    task.failure_type = None
    task.report_status = TaskReportStatus.PENDING
    task.retry_at = None  # 成功后清除重试时间
    task.llm_usage = llm_usage
    db.add(task)
    db.commit()


"""
作用：更新任务为失败状态。
逻辑：类似成功更新，但状态为 FAILED，并记录 failure_type（如 task_timeout、login_failed 等）。result 字段存放错误描述。
"""


def _update_task_failure(
    db: Session,
    task: SubscriptionTask,
    *,
    duration: float,
    result: str,
    failure_type: str,
    task_dir: str | None,
    llm_usage: dict[str, Any] | None = None,
) -> None:
    settings = get_settings()
    # 检查是否还可以重试（execution_count 已在 _mark_running 时递增）
    if task.execution_count <= settings.subscription_retry_max_count:
        task.status = TaskStatus.RETRYING
        task.retry_at = datetime.now(timezone.utc) + timedelta(
            minutes=settings.subscription_retry_interval_minutes
        )
        task.report_status = None  # 尚未到达最终状态，不汇报
        logger.info(
            "任务失败已安排重试: id=%s, url=%s, execution_count=%s, retry_at=%s",
            task.id,
            task.url,
            task.execution_count,
            task.retry_at,
        )
    else:
        task.status = TaskStatus.FAILED
        task.report_status = TaskReportStatus.PENDING

    task.duration_seconds = int(duration)
    task.result = result
    task.task_dir = task_dir
    task.failure_type = failure_type
    task.llm_usage = llm_usage
    db.add(task)
    db.commit()


"""
作用：从数据库中获取状态为 PENDING 的任务，按 ID 升序排列，最多返回 limit 个。
用途：在正常调度中取出待执行的任务。
"""


def _get_pending_batch(db: Session, limit: int = 1) -> list[SubscriptionTask]:
    now = datetime.now(timezone.utc)
    return (
        db.query(SubscriptionTask)
        .filter(
            or_(
                SubscriptionTask.status == TaskStatus.PENDING,
                and_(
                    SubscriptionTask.status == TaskStatus.RETRYING,
                    SubscriptionTask.retry_at.isnot(None),
                    SubscriptionTask.retry_at <= now,
                ),
            )
        )
        .order_by(SubscriptionTask.id.asc())
        .limit(limit)
        .all()
    )


"""
作用：获取那些状态为 RUNNING 但执行开始时间（executed_at）早于指定时间戳的任务，用于恢复检测（即可能因进程崩溃而悬空的运行中任务）。
逻辑：
筛选条件：status == RUNNING 且（executed_at IS NULL 或 executed_at < before_ts）。
按 executed_at 升序（NULL 值优先）再按 created_at 升序排序，限制数量。
通常用于启动时恢复那些被标记为运行中但实际没有完成的任务。
"""


def _get_running_batch_before(
    db: Session, before_ts: datetime, limit: int = 1
) -> list[SubscriptionTask]:
    return (
        db.query(SubscriptionTask)
        .filter(
            SubscriptionTask.status == TaskStatus.RUNNING,
            or_(
                SubscriptionTask.executed_at.is_(None),
                SubscriptionTask.executed_at < before_ts,
            ),
        )
        .order_by(
            SubscriptionTask.executed_at.asc().nullsfirst(),
            SubscriptionTask.created_at.asc(),
        )
        .limit(limit)
        .all()
    )


# 核心执行函数
# 作用：异步执行单个任务的核心逻辑。
"""
步骤：
获取配置（超时设置等）。
记录开始时间。
在 try 块中：
计算执行超时时间 = task_runner_timeout_seconds + playwright_cleanup_buffer_seconds。前一个是任务逻辑的最大允许执行时间，后一个是给 Playwright 清理资源的额外缓冲，避免因清理超时而导致异常。
使用 asyncio.wait_for 调用 run_single_instruction_async，超时后抛出 asyncio.TimeoutError。
捕获 TimeoutError 标记 timed_out = True，其他异常保存到 exec_error。
计算实际耗时 duration。
如果有执行结果且任务目录存在，将其转为项目相对路径（to_project_relative）。
打开新数据库会话，获取任务对象（若已不存在则直接返回）。
判断执行结果：
如果 exec_result 存在且 success == True 且 task_dir 非空，则视为成功，调用 _extract_success_result 提取结果，使用 _update_task_success 更新任务。
否则视为失败，调用 _extract_failure_result 和 _format_failure_type 获取错误信息和类型，再调用 _update_task_failure 更新任务。
在 finally 中关闭数据库会话。
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
        task_obj = db.get(SubscriptionTask, task_id)
        if not task_obj:
            return

        if exec_result and exec_result.success and exec_result.task_dir:
            result_text = _extract_success_result(exec_result)
            llm_usage = exec_result.llm_usage
            _update_task_success(
                db,
                task_obj,
                duration=duration,
                result=result_text,
                task_dir=task_dir_value,
                llm_usage=llm_usage,
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
            _update_task_failure(
                db,
                task_obj,
                duration=duration,
                result=result_text,
                failure_type=failure_type,
                task_dir=task_dir_value,
                llm_usage=llm_usage,
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


# 作用：单次调度，从数据库中选择一批任务（最多 1 个，但可通过修改 limit 调整），标记为运行中，然后异步启动 _run_task。
"""
逻辑：
检查信号量是否还有可用槽位（semaphore._value），如果没有则直接返回 recovering（等待下次循环）。
创建数据库会话。
尝试获取任务：
如果处于恢复模式且提供了 recovery_before，则调用 _get_running_batch_before 获取一个运行中的陈旧任务。若获取不到，则将 recovering 设为 False（表示恢复阶段结束）。
如果仍然没有任务（即恢复模式结束或正常模式），则调用 _get_pending_batch 获取一个待处理任务。
如果没有任何任务，关闭会话并返回 recovering（可能还是 True 表示恢复未完成）。
对每个获取到的任务（目前只取一个，但代码支持批量），先调用 _mark_running 更新数据库状态。
关闭数据库会话（注意：在 try 块中提交了更改，但随后关闭会话，这里可能在 _mark_running 中已经 commit 了）。
对每个任务，构造指令，创建一个内部异步工作函数 _worker，该函数先获取信号量，再执行 _run_task。最后使用 asyncio.create_task 启动这个工作协程（不等待）。
返回 recovering 状态（可能被更新
这个函数是调度器的核心，每次调用会尝试取出并启动最多一个任务，同时管理恢复模式的转换。
"""


async def process_once(
    semaphore: asyncio.Semaphore,  # 控制并发数的信号量，每个任务执行前会先获取信号量，防止同时运行过多任务。
    *,
    recovery_before: datetime
    | None,  # 恢复模式下的时间戳边界（通常为启动时间），用于找出可能的“僵尸”任务。
    recovering: bool,  # 指示当前是否处于恢复模式（即正在尝试恢复之前未完成的任务）。
) -> bool:
    # 当前可用并发槽
    available = semaphore._value  # type: ignore[attr-defined]
    if available <= 0:
        return recovering

    db = SessionLocal()
    tasks: list[SubscriptionTask] = []
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


# 整个订阅任务执行器的入口，会一直循环运行，定期调度 process_once
"""
流程：
从配置中获取轮询间隔 interval（至少 1 秒）、最大并发数 max_concurrent。
创建信号量，初始值为 max_concurrent。
记录启动时间戳 startup_ts，用于恢复检测。
初始化 recovering = True（表示启动后先尝试恢复历史运行中的任务）。
进入无限循环：
    调用 process_once 并传递信号量、恢复时间戳和恢复标志。
    捕获任何未预期的异常，记录日志（避免循环退出）。
    等待 interval 秒，然后继续。

通过这种方式，该执行器持续运行，以固定频率检查并启动新任务，同时具备任务恢复能力（在进程重启后重新接管那些被标记为运行中但实际未完成的任务）。
"""


async def run_subscription_runner_loop() -> None:
    settings = get_settings()
    interval = max(1, settings.task_runner_interval_seconds)
    max_concurrent = max(1, settings.task_runner_max_concurrent)
    semaphore = asyncio.Semaphore(max_concurrent)
    startup_ts = datetime.now(timezone.utc)
    recovering = True
    logger.info(
        "订阅任务执行器已启动, interval=%ss, max_concurrent=%s",
        settings.task_runner_interval_seconds,
        settings.task_runner_max_concurrent,
    )

    while True:
        try:
            recovering = await process_once(
                semaphore, recovery_before=startup_ts, recovering=recovering
            )
        except Exception as exc:  # pragma: no cover - 防御性日志
            logger.exception("订阅任务调度异常: %s", exc)
        await asyncio.sleep(interval)
