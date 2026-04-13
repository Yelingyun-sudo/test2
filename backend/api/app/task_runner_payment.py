from __future__ import annotations

"""支付任务执行器：

核心职责是：从数据库中读取待处理的 PaymentTask 记录（如账号密码、目标 URL）

构造指令字符串（例如"登录某网站并提取支付二维码"）

调用底层的指令执行引擎 run_single_instruction_async 来实际执行自动化任务（基于 Playwright 浏览器自动化）

将执行结果（成功或失败）持久化回数据库，包括执行耗时、返回的支付码信息、失败原因类型、任务目录等

支持并发控制（通过信号量）和任务恢复（恢复那些被标记为 RUNNING 但可能因异常中断的任务）

这个模块通常作为后台常驻任务运行，定期扫描并调度待执行的任务。
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
from .models import PaymentTask
from .enums import TaskReportStatus, TaskStatus

logger = logging.getLogger(__name__)

# ===== 工具函数与业务辅助函数 =====


def _build_instruction(task: PaymentTask) -> str:
    """构建支付任务执行指令。

    根据任务中的 url、account、password 生成指令字符串：
    - 登录 {url}（账号和密码分别为 {account} 和 {password}）并提取支付二维码
    """
    return f"登录 {task.url}（账号和密码分别为 {task.account} 和 {task.password}）并提取支付二维码"


def _extract_success_result(exec_result: ExecutionResult | None) -> str:
    """从 ExecutionResult 提取成功结果（支付码信息）。

    从 coordinator_output["operations_results"]["payment"]["payment_code"] 中提取支付码。
    支付码可能是：
    - 微信支付二维码图片路径
    - 支付宝支付二维码图片路径
    - 其他支付方式信息
    """
    if not exec_result or not exec_result.coordinator_output:
        return "任务结果不可用"
    try:
        coordinator = exec_result.coordinator_output
        operations_results = coordinator.get("operations_results") or {}
        payment_result = operations_results.get("payment") or {}

        # 提取支付码信息（可以是图片路径或文本信息）
        payment_code = payment_result.get("payment_code")
        if payment_code:
            return str(payment_code)

        # 备用：提取二维码图片路径
        qr_code_image = payment_result.get("qr_code_image")
        if qr_code_image:
            return f"支付二维码已提取：{qr_code_image}"

        return "未返回支付码信息"
    except Exception as exc:  # pragma: no cover - 防御性处理
        return f"解析任务结果失败: {exc}"


def _extract_failure_result(
    exec_result: ExecutionResult | None,
    exc: Exception | None = None,
) -> str:
    """从 ExecutionResult 提取失败结果信息。

    优先级：
    1. coordinator_output["message"] - 业务层错误消息
    2. exec_result.message - 执行框架默认消息
    3. exc 异常信息
    4. 兜底消息
    """
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


# ===== 数据库状态管理函数 =====


def _mark_running(db: Session, task: PaymentTask) -> None:
    """更新任务状态为 RUNNING，并记录执行开始时间（UTC）"""
    task.status = TaskStatus.RUNNING
    task.executed_at = datetime.now(timezone.utc)
    db.add(task)
    db.commit()
    db.refresh(task)


def _update_task_success(
    db: Session,
    task: PaymentTask,
    *,
    duration: float,
    result: str,
    task_dir: str | None,
    llm_usage: dict[str, Any] | None = None,
) -> None:
    """更新任务为成功状态。

    设置 status = SUCCESS，清空 failure_type，设置 report_status = PENDING，
    记录耗时、结果、目录和 LLM 用量。
    """
    task.status = TaskStatus.SUCCESS
    task.duration_seconds = int(duration)
    task.result = result
    task.task_dir = task_dir
    task.failure_type = None
    task.report_status = TaskReportStatus.PENDING
    task.llm_usage = llm_usage
    db.add(task)
    db.commit()


def _update_task_failure(
    db: Session,
    task: PaymentTask,
    *,
    duration: float,
    result: str,
    failure_type: str,
    task_dir: str | None,
    llm_usage: dict[str, Any] | None = None,
) -> None:
    """更新任务为失败状态。

    类似成功更新，但状态为 FAILED，并记录 failure_type（如 task_timeout、login_failed 等）。
    result 字段存放错误描述。
    """
    task.status = TaskStatus.FAILED
    task.duration_seconds = int(duration)
    task.result = result
    task.task_dir = task_dir
    task.failure_type = failure_type
    task.report_status = TaskReportStatus.PENDING
    task.llm_usage = llm_usage
    db.add(task)
    db.commit()


# ===== 任务查询函数 =====


def _get_pending_batch(db: Session, limit: int = 1) -> list[PaymentTask]:
    """从数据库中获取状态为 PENDING 的任务，按 ID 升序排列，最多返回 limit 个。"""
    return (
        db.query(PaymentTask)
        .filter(PaymentTask.status == TaskStatus.PENDING)
        .order_by(PaymentTask.id.asc())
        .limit(limit)
        .all()
    )


def _get_running_batch_before(
    db: Session, before_ts: datetime, limit: int = 1
) -> list[PaymentTask]:
    """获取那些状态为 RUNNING 但执行开始时间早于指定时间戳的任务，用于恢复检测。

    筛选条件：status == RUNNING 且（executed_at IS NULL 或 executed_at < before_ts）。
    """
    return (
        db.query(PaymentTask)
        .filter(
            PaymentTask.status == TaskStatus.RUNNING,
            or_(
                PaymentTask.executed_at.is_(None),
                PaymentTask.executed_at < before_ts,
            ),
        )
        .order_by(
            PaymentTask.executed_at.asc().nullsfirst(),
            PaymentTask.created_at.asc(),
        )
        .limit(limit)
        .all()
    )


# ===== 核心执行函数 =====


async def _run_task(task_id: int, instruction: str) -> None:
    """异步执行单个任务的核心逻辑。

    步骤：
    1. 获取配置（超时设置等）
    2. 记录开始时间
    3. 调用 run_single_instruction_async 执行任务
    4. 计算耗时，更新任务状态到数据库
    """
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
        task_obj = db.get(PaymentTask, task_id)
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


# ===== 调度与并发控制层 =====


async def process_once(
    semaphore: asyncio.Semaphore,
    *,
    recovery_before: datetime | None,
    recovering: bool,
) -> bool:
    """单次调度，从数据库中选择一批任务（最多 1 个），标记为运行中，然后异步启动 _run_task。

    逻辑：
    1. 检查信号量是否还有可用槽位
    2. 如果处于恢复模式，优先获取运行中的陈旧任务
    3. 否则获取待处理任务
    4. 标记为 RUNNING 并异步执行
    """
    # 当前可用并发槽
    available = semaphore._value  # type: ignore[attr-defined]
    if available <= 0:
        return recovering

    db = SessionLocal()
    tasks: list[PaymentTask] = []
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


async def run_payment_runner_loop() -> None:
    """支付任务执行器的入口，会一直循环运行，定期调度 process_once。

    流程：
    1. 从配置中获取轮询间隔 interval（至少 1 秒）、最大并发数 max_concurrent
    2. 创建信号量，初始值为 max_concurrent
    3. 记录启动时间戳 startup_ts，用于恢复检测
    4. 初始化 recovering = True（表示启动后先尝试恢复历史运行中的任务）
    5. 进入无限循环，调用 process_once 并等待 interval 秒
    """
    settings = get_settings()
    interval = max(1, settings.task_runner_interval_seconds)
    max_concurrent = max(1, settings.task_runner_max_concurrent)
    semaphore = asyncio.Semaphore(max_concurrent)
    startup_ts = datetime.now(timezone.utc)
    recovering = True
    logger.info(
        "支付任务执行器已启动, interval=%ss, max_concurrent=%s",
        settings.task_runner_interval_seconds,
        settings.task_runner_max_concurrent,
    )

    while True:
        try:
            recovering = await process_once(
                semaphore, recovery_before=startup_ts, recovering=recovering
            )
        except Exception as exc:  # pragma: no cover - 防御性日志
            logger.exception("支付任务调度异常: %s", exc)
        await asyncio.sleep(interval)
