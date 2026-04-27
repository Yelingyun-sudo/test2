from __future__ import annotations

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
from ..models import SubscriptionTask
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
from ..schemas.subscription import (
    RecentTasksResponse,
    SubscriptionArtifactsResponse,
    SubscriptionItem,
    SubscriptionListResponse,
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
    prefix="/subscription",
    tags=["subscription"],
)


@router.get(
    "/list",
    response_model=SubscriptionListResponse,
    summary="订阅网站列表（分页 + 简单检索，读取数据库）",
)
def list_subscription(
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    q: str | None = Query(None, description="按 url / account / password 包含匹配"),
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
    query = db.query(SubscriptionTask)

    if q:
        keyword = f"%{q.lower()}%"
        query = query.filter(
            func.lower(SubscriptionTask.url).like(keyword)
            | func.lower(SubscriptionTask.account).like(keyword)
            | func.lower(SubscriptionTask.password).like(keyword)
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
            query = query.filter(SubscriptionTask.status.in_(status_enums))

    if failure_type:
        query = query.filter(SubscriptionTask.failure_type == failure_type)

    if start_date and end_date:
        start_time, end_time = parse_date_range(start_date, end_date, tz_cn)
        if start_time and end_time:
            # 判断时间范围是否包含今天
            # 如果 end_time 是今天，则包含 PENDING 和 RUNNING 任务
            # 如果 end_time 是昨天或更早，则不包含 PENDING 和 RUNNING
            now_cn = datetime.now(tz_cn)
            today_end = now_cn.replace(
                hour=23, minute=59, second=59, microsecond=999999
            )
            today_end_utc = today_end.astimezone(timezone.utc)

            # 如果结束时间 >= 今天的结束时间（UTC），说明包含今天
            if end_time >= today_end_utc:
                # 包含今天：显示所有任务，包括 PENDING、RUNNING 和 RETRYING
                query = query.filter(
                    or_(
                        SubscriptionTask.status.in_(
                            [TaskStatus.PENDING, TaskStatus.RUNNING, TaskStatus.RETRYING]
                        ),
                        and_(
                            SubscriptionTask.executed_at.isnot(None),
                            SubscriptionTask.executed_at >= start_time,
                            SubscriptionTask.executed_at <= end_time,
                        ),
                    )
                )
            else:
                # 纯历史时间范围：只显示已完成的任务
                query = query.filter(
                    SubscriptionTask.executed_at.isnot(None),
                    SubscriptionTask.executed_at >= start_time,
                    SubscriptionTask.executed_at <= end_time,
                )
    # 如果没有提供日期范围，不应用时间过滤，显示所有任务

    total = query.count()
    status_priority = case(
        (SubscriptionTask.status == TaskStatus.RUNNING, 0),
        (SubscriptionTask.status.in_([TaskStatus.SUCCESS, TaskStatus.FAILED]), 1),
        else_=2,  # PENDING / RETRYING
    )

    records: List[SubscriptionTask] = (
        query.order_by(
            status_priority,
            SubscriptionTask.executed_at.desc().nulls_last(),
            SubscriptionTask.id.asc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    def _format_dt(dt):
        return format_datetime(dt, tz_cn)

    items = []
    for rec in records:
        items.append(_build_subscription_item(rec, _format_dt))

    return SubscriptionListResponse(
        items=items, total=total, page=page, page_size=page_size
    )


def _read_task_summary(task_dir_abs: Path) -> dict:
    summary_path = task_dir_abs / "task_summary.json"
    if not summary_path.exists():
        return {}
    try:
        return json.loads(summary_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


@router.get(
    "/{task_id}/artifacts",
    response_model=SubscriptionArtifactsResponse,
    summary="获取任务产物路径（截图/视频）",
)
def get_task_artifacts(
    task_id: int,
    db: Session = Depends(get_db),
):
    task = db.get(SubscriptionTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    status_value = task.status.value if hasattr(task.status, "value") else task.status
    task_dir = task.task_dir
    if not task_dir:
        return SubscriptionArtifactsResponse(status=status_value or "")

    task_dir_abs = resolve_task_dir(task_dir)
    summary = _read_task_summary(task_dir_abs)
    coordinator = summary.get("coordinator_output") or {}
    operations_results = coordinator.get("operations_results") or {}

    login_image_path = None
    login_result = operations_results.get("login")
    if isinstance(login_result, dict):
        # 向后兼容：优先使用 cover_image_path，如果没有则使用 last_capture_path
        login_image_path = login_result.get("cover_image_path") or login_result.get(
            "last_capture_path"
        )

    extract_image_path = None
    extract_result = operations_results.get("extract")
    if isinstance(extract_result, dict):
        # 向后兼容：优先使用 cover_image_path，如果没有则使用 last_capture_path
        extract_image_path = extract_result.get(
            "cover_image_path"
        ) or extract_result.get("last_capture_path")

    video_path = coordinator.get("video_path")
    video_seek_seconds = coordinator.get("video_seek_seconds")

    return SubscriptionArtifactsResponse(
        status=status_value or "",
        login_image_path=str(login_image_path) if login_image_path else None,
        extract_image_path=str(extract_image_path) if extract_image_path else None,
        video_path=str(video_path) if video_path else None,
        video_seek_seconds=float(video_seek_seconds)
        if video_seek_seconds is not None
        else None,
    )


@router.get(
    "/{task_id}/artifact",
    summary="下载单个任务产物文件（截图/视频）",
)
def get_task_artifact(
    task_id: int,
    path: str = Query(..., description="相对任务目录的产物路径"),
    db: Session = Depends(get_db),
):
    task = db.get(SubscriptionTask, task_id)
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


def _compute_summary(
    db: Session,
    range_start_utc: datetime | None,
    range_end_utc: datetime | None,
    tz_cn: timezone,
) -> TaskStatsSummary:
    """计算汇总统计"""
    from .common import compute_task_summary

    return compute_task_summary(
        db, SubscriptionTask, range_start_utc, range_end_utc, tz_cn
    )


def _build_subscription_item(
    rec: SubscriptionTask, _format_dt: Callable
) -> SubscriptionItem:
    """构建 SubscriptionItem 对象"""
    from .common import build_task_item

    return build_task_item(rec, SubscriptionItem, _format_dt)


# ===== 专用统计端点 =====


@router.get(
    "/stats/summary",
    response_model=SummaryResponse,
    summary="获取订阅任务汇总统计",
)
def get_subscription_stats_summary(
    start_date: str | None = Query(None, description="开始日期 YYYY-MM-DD 格式"),
    end_date: str | None = Query(None, description="结束日期 YYYY-MM-DD 格式"),
    db: Session = Depends(get_db),
):
    """获取订阅任务的汇总统计数据"""
    if start_date and end_date:
        range_start_utc, range_end_utc = parse_date_range(start_date, end_date, tz_cn)
        if range_start_utc is None or range_end_utc is None:
            # 日期解析失败时，不应用日期过滤（返回全部数据）
            range_start_utc = None
            range_end_utc = None
    else:
        # 没有日期参数时，不应用日期过滤（返回全部数据）
        range_start_utc = None
        range_end_utc = None

    summary = _compute_summary(db, range_start_utc, range_end_utc, tz_cn)
    return SummaryResponse(summary=summary)


@router.get(
    "/stats/daily-trend",
    response_model=DailyTrendResponse,
    summary="获取订阅任务每日趋势",
)
def get_subscription_stats_daily_trend(
    db: Session = Depends(get_db),
):
    """获取订阅任务的每日趋势数据（最近10天）"""
    daily_trend = compute_daily_trend(
        db, SubscriptionTask, tz_cn, days=10, daily_trend_item_cls=DailyTrendItem
    )
    return DailyTrendResponse(daily_trend=daily_trend)


@router.get(
    "/stats/status-distribution",
    response_model=StatusDistributionResponse,
    summary="获取订阅任务状态分布",
)
def get_subscription_stats_status_distribution(
    start_date: str | None = Query(None, description="开始日期 YYYY-MM-DD 格式"),
    end_date: str | None = Query(None, description="结束日期 YYYY-MM-DD 格式"),
    db: Session = Depends(get_db),
):
    """获取订阅任务的状态分布数据"""
    if start_date and end_date:
        range_start_utc, range_end_utc = parse_date_range(start_date, end_date, tz_cn)
        if range_start_utc is None or range_end_utc is None:
            # 日期解析失败时，不应用日期过滤（返回全部数据）
            range_start_utc = None
            range_end_utc = None
    else:
        # 没有日期参数时，不应用日期过滤（返回全部数据）
        range_start_utc = None
        range_end_utc = None

    status_distribution = compute_status_distribution(
        db,
        SubscriptionTask,
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
def get_subscription_stats_recent_tasks(
    start_date: str | None = Query(None, description="开始日期 YYYY-MM-DD 格式"),
    end_date: str | None = Query(None, description="结束日期 YYYY-MM-DD 格式"),
    db: Session = Depends(get_db),
):
    """获取最新任务列表（最多 100 条）"""
    if start_date and end_date:
        range_start_utc, range_end_utc = parse_date_range(start_date, end_date, tz_cn)
        if range_start_utc is None or range_end_utc is None:
            # 日期解析失败时，不应用日期过滤（返回全部数据）
            range_start_utc = None
            range_end_utc = None
    else:
        # 没有日期参数时，不应用日期过滤（返回全部数据）
        range_start_utc = None
        range_end_utc = None

    recent_tasks = compute_recent_tasks(
        db,
        SubscriptionTask,
        start_date,
        end_date,
        range_start_utc,
        range_end_utc,
        tz_cn,
        SubscriptionItem,
        _build_subscription_item,
    )
    return RecentTasksResponse(recent_tasks=recent_tasks)


@router.get(
    "/stats/failure-types",
    response_model=FailureTypesStatsResponse,
    summary="获取失败类型统计",
)
def get_subscription_stats_failure_types(
    start_date: str | None = Query(None, description="开始日期 YYYY-MM-DD 格式"),
    end_date: str | None = Query(None, description="结束日期 YYYY-MM-DD 格式"),
    db: Session = Depends(get_db),
):
    """获取失败类型分布统计和失败总览"""
    failure_type_distribution, failure_summary = compute_failure_stats(
        db,
        SubscriptionTask,
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
def get_failure_types():
    """
    获取所有失败类型及其中文标签，按业务优先级排序。

    Returns:
        失败类型列表，包含 value 和 label 字段。
    """
    return get_failure_types_endpoint()
