from __future__ import annotations

"""
outers/payment.py 文件定义了支付任务（PaymentTask）相关的所有 API 端点，是后端提供给前端或客户端调用的 RESTful 接口集合。
它基于 FastAPI 框架，使用 SQLAlchemy 进行数据库操作，并依赖多个公共工具函数来简化统计和数据处理。
"""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, List

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import and_, case, func, or_
from sqlalchemy.orm import Session

from ..constants import TZ_CHINA as tz_cn
from ..db import get_db
from ..enums import TaskStatus
from ..models import PaymentTask
from ..utils import resolve_task_dir
from ..schemas.common import (
    DailyTrendItem,
    FailureSummary,
    FailureTypeDistributionItem,
    FailureTypesResponse,
    StatusDistributionItem,
    TaskStatsSummary,
)
from ..schemas.stats_response import (
    DailyTrendResponse,
    FailureTypesStatsResponse,
    StatusDistributionResponse,
)
from ..schemas.payment import (
    PaymentArtifactsResponse,
    PaymentItem,
    PaymentListResponse,
    RecentTasksResponse,
    SummaryResponse,
)
from .common import (
    compute_daily_trend,
    compute_failure_stats,
    compute_recent_tasks,
    compute_status_distribution,
    format_datetime,
    get_failure_types_endpoint,
    parse_date_range,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/payment",
    tags=["payment"],
)


# list_payment – 支付任务列表（分页 + 多条件检索）
@router.get(
    "/list",
    response_model=PaymentListResponse,
    summary="支付任务列表（分页 + 简单检索）",
)
def list_payment(
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    q: str | None = Query(None, description="按 url / account 包含匹配"),
    status: list[str] | None = Query(
        None, description="按任务状态过滤（小写，如 failed/success，支持多个值）"
    ),
    failure_type: str | None = Query(
        None, description="按失败类型过滤（通常与 status=failed 配合使用）"
    ),
    start_date: str | None = Query(None, description="开始日期 YYYY-MM-DD 格式"),
    end_date: str | None = Query(None, description="结束日期 YYYY-MM-DD 格式"),
    db: Session = Depends(get_db),
):
    query = db.query(PaymentTask)

    if q:
        keyword = f"%{q.lower()}%"
        query = query.filter(
            func.lower(PaymentTask.url).like(keyword)
            | func.lower(PaymentTask.account).like(keyword)
        )

    if status:
        # 将小写参数列表转为大写枚举值列表
        status_enums = []
        for s in status:
            try:
                status_enums.append(TaskStatus(s.upper()))
            except ValueError:
                # 无效的状态值，忽略
                pass
        if status_enums:
            query = query.filter(PaymentTask.status.in_(status_enums))

    if failure_type:
        query = query.filter(PaymentTask.failure_type == failure_type)

    if start_date and end_date:
        start_time, end_time = parse_date_range(start_date, end_date, tz_cn)
        if start_time and end_time:
            # 判断时间范围是否包含今天
            now_cn = datetime.now(tz_cn)
            today_end = now_cn.replace(
                hour=23, minute=59, second=59, microsecond=999999
            )
            today_end_utc = today_end.astimezone(timezone.utc)

            if end_time >= today_end_utc:
                # 包含今天：显示所有任务，包括 PENDING 和 RUNNING
                query = query.filter(
                    or_(
                        PaymentTask.status.in_(
                            [TaskStatus.PENDING, TaskStatus.RUNNING]
                        ),
                        and_(
                            PaymentTask.executed_at.isnot(None),
                            PaymentTask.executed_at >= start_time,
                            PaymentTask.executed_at <= end_time,
                        ),
                    )
                )
            else:
                # 纯历史时间范围：只显示已完成的任务
                query = query.filter(
                    PaymentTask.executed_at.isnot(None),
                    PaymentTask.executed_at >= start_time,
                    PaymentTask.executed_at <= end_time,
                )

    total = query.count()
    status_priority = case(
        (PaymentTask.status == TaskStatus.RUNNING, 0),
        (PaymentTask.status.in_([TaskStatus.SUCCESS, TaskStatus.FAILED]), 1),
        else_=2,
    )

    records: List[PaymentTask] = (
        query.order_by(
            status_priority,
            PaymentTask.executed_at.desc().nulls_last(),
            PaymentTask.id.asc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    def _format_dt(dt):
        return format_datetime(dt, tz_cn)

    items = []
    for rec in records:
        items.append(_build_payment_item(rec, _format_dt))

    return PaymentListResponse(items=items, total=total, page=page, page_size=page_size)


def _read_task_summary(task_dir_abs: Path) -> dict:
    """读取任务摘要文件"""
    summary_path = task_dir_abs / "task_summary.json"
    if not summary_path.exists():
        return {}
    try:
        return json.loads(summary_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


@router.get(
    "/{task_id}/artifacts",
    response_model=PaymentArtifactsResponse,
    summary="获取任务产物路径（支付二维码截图）",
)
# 2. get_task_artifacts – 获取任务产物路径
# 功能：返回任务执行过程中生成的产物路径（二维码截图、登录截图、视频等），不返回文件内容，只提供路径元数据
# 读取任务目录下的 task_summary.json 文件，从中提取 operations_results.payment.qr_code_image（二维码图片）、operations_results.login.cover_image_path 或 last_capture_path（登录截图）、以及 coordinator.video_path 和 video_seek_seconds（视频路径及定位点）。返回 PaymentArtifactsResponse 结构。
def get_task_artifacts(
    task_id: int,
    db: Session = Depends(get_db),
):
    """获取任务产物，包括支付二维码截图等"""
    task = db.get(PaymentTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    status_value = task.status.value if hasattr(task.status, "value") else task.status
    task_dir = task.task_dir
    if not task_dir:
        return PaymentArtifactsResponse(status=status_value or "")

    task_dir_abs = resolve_task_dir(task_dir)
    summary = _read_task_summary(task_dir_abs)
    coordinator = summary.get("coordinator_output") or {}
    operations_results = coordinator.get("operations_results") or {}

    # 提取支付二维码相关产物
    payment_result = operations_results.get("payment") or {}

    # 支付二维码图片路径
    qr_code_image = payment_result.get("qr_code_image")

    # 登录截图
    login_image_path = None
    login_result = operations_results.get("login")
    if isinstance(login_result, dict):
        login_image_path = login_result.get("cover_image_path") or login_result.get(
            "last_capture_path"
        )

    video_path = coordinator.get("video_path")
    video_seek_seconds = coordinator.get("video_seek_seconds")

    # 三张关键截图
    screenshot_1 = payment_result.get("screenshot_1")
    screenshot_2 = payment_result.get("screenshot_2")
    screenshot_3 = payment_result.get("screenshot_3")

    return PaymentArtifactsResponse(
        status=status_value or "",
        qr_code_image=str(qr_code_image) if qr_code_image else None,
        login_image_path=str(login_image_path) if login_image_path else None,
        video_path=str(video_path) if video_path else None,
        video_seek_seconds=float(video_seek_seconds)
        if video_seek_seconds is not None
        else None,
        screenshot_1=str(screenshot_1) if screenshot_1 else None,
        screenshot_2=str(screenshot_2) if screenshot_2 else None,
        screenshot_3=str(screenshot_3) if screenshot_3 else None,
    )


@router.get(
    "/{task_id}/artifact",
    summary="下载单个任务产物文件（截图/视频）",
)
# 3. get_task_artifact – 下载单个产物文件
# 功能：通过查询参数 path 指定相对路径，下载具体的截图或视频文件。
def get_task_artifact(
    task_id: int,
    path: str = Query(..., description="相对任务目录的产物路径"),
    db: Session = Depends(get_db),
):
    """下载具体的产物文件（截图或视频）"""
    task = db.get(PaymentTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not task.task_dir:
        raise HTTPException(status_code=404, detail="任务暂无产物")

    task_dir_abs = resolve_task_dir(task.task_dir)
    raw = Path(path)
    if raw.is_absolute() or ".." in raw.parts:
        raise HTTPException(status_code=400, detail="非法 path")

    allowed_suffixes = {".png", ".webm"}
    if raw.suffix.lower() not in allowed_suffixes:
        raise HTTPException(status_code=400, detail="不支持的文件类型")

    target = (task_dir_abs / raw).resolve()
    try:
        target.relative_to(task_dir_abs.resolve())
    except Exception as exc:
        raise HTTPException(status_code=400, detail="非法 path") from exc

    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")

    media_type = None
    if target.suffix.lower() == ".png":
        media_type = "image/png"
    elif target.suffix.lower() == ".webm":
        media_type = "video/webm"

    return FileResponse(target, media_type=media_type)


# 这个是计算汇总统计的工具函数
def _compute_summary(
    db: Session,
    range_start_utc: datetime | None,
    range_end_utc: datetime | None,
    tz_cn: timezone,
) -> TaskStatsSummary:
    """计算汇总统计"""
    from .common import compute_task_summary

    return compute_task_summary(db, PaymentTask, range_start_utc, range_end_utc, tz_cn)


def _build_payment_item(rec: PaymentTask, _format_dt: Callable) -> PaymentItem:
    """构建 PaymentItem 对象"""
    from .common import build_task_item

    return build_task_item(rec, PaymentItem, _format_dt)


# ===== 专用统计端点 =====


@router.get(
    "/stats/summary",
    response_model=SummaryResponse,
    summary="获取支付任务汇总统计",
)
# 4. get_payment_stats_summary – 汇总统计
# 功能：返回任务的汇总数据（总数、成功数、失败数、成功率等）。
# 实现：调用 _compute_summary，最终由 compute_task_summary 计算。
def get_payment_stats_summary(
    start_date: str | None = Query(None, description="开始日期 YYYY-MM-DD 格式"),
    end_date: str | None = Query(None, description="结束日期 YYYY-MM-DD 格式"),
    db: Session = Depends(get_db),
):
    """获取支付任务的汇总统计数据"""
    if start_date and end_date:
        range_start_utc, range_end_utc = parse_date_range(start_date, end_date, tz_cn)
        if range_start_utc is None or range_end_utc is None:
            range_start_utc = None
            range_end_utc = None
    else:
        range_start_utc = None
        range_end_utc = None

    summary = _compute_summary(db, range_start_utc, range_end_utc, tz_cn)
    return SummaryResponse(summary=summary)


@router.get(
    "/stats/daily-trend",
    response_model=DailyTrendResponse,
    summary="获取支付任务每日趋势",
)
# 每日趋势：返回最近 10 天每天的任务完成数、成功数、失败数等趋势数据。
# 实现：调用 compute_daily_trend 生成 DailyTrendItem 列表。
def get_payment_stats_daily_trend(
    db: Session = Depends(get_db),
):
    """获取支付任务的每日趋势数据（最近10天）"""
    daily_trend = compute_daily_trend(
        db, PaymentTask, tz_cn, days=10, daily_trend_item_cls=DailyTrendItem
    )
    return DailyTrendResponse(daily_trend=daily_trend)


@router.get(
    "/stats/status-distribution",
    response_model=StatusDistributionResponse,
    summary="获取支付任务状态分布",
)
# 功能：按任务状态（PENDING、RUNNING、SUCCESS、FAILED）统计数量。
# 实现：调用 compute_status_distribution。
def get_payment_stats_status_distribution(
    start_date: str | None = Query(None, description="开始日期 YYYY-MM-DD 格式"),
    end_date: str | None = Query(None, description="结束日期 YYYY-MM-DD 格式"),
    db: Session = Depends(get_db),
):
    """获取支付任务的状态分布数据"""
    if start_date and end_date:
        range_start_utc, range_end_utc = parse_date_range(start_date, end_date, tz_cn)
        if range_start_utc is None or range_end_utc is None:
            range_start_utc = None
            range_end_utc = None
    else:
        range_start_utc = None
        range_end_utc = None

    status_distribution = compute_status_distribution(
        db,
        PaymentTask,
        start_date,
        end_date,
        range_start_utc,
        range_end_utc,
        StatusDistributionItem,
    )
    return StatusDistributionResponse(status_distribution=status_distribution)


@router.get(
    "/stats/recent-tasks",
    response_model=RecentTasksResponse,
    summary="获取最新任务列表",
)
# 最新任务列表
# 功能：返回最近执行的任务（最多 100 条），按执行时间倒序。
# 实现：调用 compute_recent_tasks，使用 _build_payment_item 构造响应项。
def get_payment_stats_recent_tasks(
    start_date: str | None = Query(None, description="开始日期 YYYY-MM-DD 格式"),
    end_date: str | None = Query(None, description="结束日期 YYYY-MM-DD 格式"),
    db: Session = Depends(get_db),
):
    """获取最新任务列表（最多 100 条）"""
    if start_date and end_date:
        range_start_utc, range_end_utc = parse_date_range(start_date, end_date, tz_cn)
        if range_start_utc is None or range_end_utc is None:
            range_start_utc = None
            range_end_utc = None
    else:
        range_start_utc = None
        range_end_utc = None

    recent_tasks = compute_recent_tasks(
        db,
        PaymentTask,
        start_date,
        end_date,
        range_start_utc,
        range_end_utc,
        tz_cn,
        PaymentItem,
        _build_payment_item,
    )
    return RecentTasksResponse(recent_tasks=recent_tasks)


@router.get(
    "/stats/failure-types",
    response_model=FailureTypesStatsResponse,
    summary="获取失败类型统计",
)
# 功能：返回失败任务的分布（按 failure_type 分组）以及失败总数、失败类型数量等摘要。
# 实现：调用 compute_failure_stats 生成分布列表和 FailureSummary
def get_payment_stats_failure_types(
    start_date: str | None = Query(None, description="开始日期 YYYY-MM-DD 格式"),
    end_date: str | None = Query(None, description="结束日期 YYYY-MM-DD 格式"),
    db: Session = Depends(get_db),
):
    """获取失败类型分布统计和失败总览"""
    failure_type_distribution, failure_summary = compute_failure_stats(
        db,
        PaymentTask,
        start_date,
        end_date,
        tz_cn,
        FailureTypeDistributionItem,
        FailureSummary,
    )

    return FailureTypesStatsResponse(
        failure_type_distribution=failure_type_distribution,
        failure_summary=failure_summary,
    )


@router.get(
    "/failure-types",
    response_model=FailureTypesResponse,
    summary="获取失败类型列表",
)
# 失败类型枚举列表
# 功能：返回系统中所有可能失败类型（value + 中文 label），用于前端下拉选择。
# 实现：直接调用 get_failure_types_endpoint，返回 FailureTypesResponse。
def get_failure_types():
    """
    获取所有失败类型及其中文标签，按业务优先级排序。

    Returns:
        失败类型列表，包含 value 和 label 字段。
    """
    return get_failure_types_endpoint()
