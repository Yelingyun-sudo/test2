from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import ValidationError
from sqlalchemy import Integer, and_, case, func, or_
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import SubscriptionTask, TaskStatus
from ..utils import resolve_task_dir
from ..schemas.common import FailureTypeItem, FailureTypesResponse, LLMUsage
from ..schemas.subscription import (
    DailyTrendItem,
    FailureSummary,
    FailureTypeDistributionItem,
    StatusDistributionItem,
    SubscriptionArtifactsResponse,
    SubscriptionItem,
    SubscriptionListResponse,
    SubscriptionStatsResponse,
    SubscriptionStatsSummary,
)
from website_analytics.output_types import (
    FAILURE_TYPE_LABELS,
    get_failure_types_ordered,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/subscription",
    tags=["subscription"],
)


def _parse_time_range(
    range_key: str | None, tz_cn: timezone
) -> tuple[datetime | None, datetime | None]:
    """
    解析预设时间范围，返回 UTC 时区的 (开始时间, 结束时间)

    Args:
        range_key: 时间范围键值（today/yesterday/3d/7d/30d 或 YYYY-MM-DD 日期格式）
        tz_cn: 中国时区

    Returns:
        (start_time_utc, end_time_utc) 或 (None, None)

    Note:
        内部先计算东八区的时间范围，然后转换为 UTC 返回。
        这样可以确保与数据库中存储的 UTC 时间正确比较。
    """
    if not range_key:
        return None, None

    # 检测具体日期格式 YYYY-MM-DD
    if re.match(r'^\d{4}-\d{2}-\d{2}$', range_key):
        try:
            date = datetime.strptime(range_key, '%Y-%m-%d')
            start = date.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=tz_cn)
            end = date.replace(hour=23, minute=59, second=59, microsecond=999999, tzinfo=tz_cn)
            return start.astimezone(timezone.utc), end.astimezone(timezone.utc)
        except ValueError:
            # 日期格式无效，继续处理预设选项
            pass

    now_cn = datetime.now(tz_cn)
    today_start = now_cn.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = now_cn.replace(hour=23, minute=59, second=59, microsecond=999999)

    if range_key == "today":
        # 转换为 UTC 时间返回
        return today_start.astimezone(timezone.utc), today_end.astimezone(timezone.utc)
    elif range_key == "yesterday":
        yesterday_start = today_start - timedelta(days=1)
        yesterday_end = yesterday_start.replace(
            hour=23, minute=59, second=59, microsecond=999999
        )
        # 转换为 UTC 时间返回
        return yesterday_start.astimezone(timezone.utc), yesterday_end.astimezone(
            timezone.utc
        )
    elif range_key == "3d":
        start = today_start - timedelta(days=2)
        # 转换为 UTC 时间返回
        return start.astimezone(timezone.utc), today_end.astimezone(timezone.utc)
    elif range_key == "7d":
        start = today_start - timedelta(days=6)
        # 转换为 UTC 时间返回
        return start.astimezone(timezone.utc), today_end.astimezone(timezone.utc)
    elif range_key == "30d":
        start = today_start - timedelta(days=29)
        # 转换为 UTC 时间返回
        return start.astimezone(timezone.utc), today_end.astimezone(timezone.utc)
    else:
        return None, None


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
    time_range: str | None = Query(
        None, description="按执行时间范围过滤（today/yesterday/3d/7d/30d）"
    ),
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

    tz_cn = timezone(timedelta(hours=8))
    if time_range:
        start_time, end_time = _parse_time_range(time_range, tz_cn)
        if start_time and end_time:
            # 判断时间范围是否包含今天
            # 如果 end_time 是今天，则包含 PENDING 和 RUNNING 任务
            # 如果 end_time 是昨天或更早，则不包含 PENDING 和 RUNNING
            now_cn = datetime.now(tz_cn)
            today_end = now_cn.replace(hour=23, minute=59, second=59, microsecond=999999)
            today_end_utc = today_end.astimezone(timezone.utc)
            
            # 如果结束时间 >= 今天的结束时间（UTC），说明包含今天
            if end_time >= today_end_utc:
                # 包含今天：显示所有任务，包括 PENDING 和 RUNNING
                query = query.filter(
                    or_(
                        SubscriptionTask.status.in_([TaskStatus.PENDING, TaskStatus.RUNNING]),
                        and_(
                            SubscriptionTask.executed_at.isnot(None),
                            SubscriptionTask.executed_at >= start_time,
                            SubscriptionTask.executed_at <= end_time,
                        )
                    )
                )
            else:
                # 纯历史时间范围：只显示已完成的任务
                query = query.filter(
                    SubscriptionTask.executed_at.isnot(None),
                    SubscriptionTask.executed_at >= start_time,
                    SubscriptionTask.executed_at <= end_time,
                )
    # 如果 time_range 是 "ALL" 或 None，不应用时间过滤，显示所有任务

    total = query.count()
    status_priority = case(
        (SubscriptionTask.status == TaskStatus.RUNNING, 0),
        (SubscriptionTask.status.in_([TaskStatus.SUCCESS, TaskStatus.FAILED]), 1),
        else_=2,
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

    def _format_dt(dt) -> str:
        if not dt:
            return ""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(tz_cn).isoformat()

    items = []
    for rec in records:
        status_value = rec.status.value if hasattr(rec.status, "value") else rec.status

        # 安全地转换 llm_usage
        llm_usage_value = None
        if rec.llm_usage is not None:
            try:
                llm_usage_value = LLMUsage(**rec.llm_usage)
            except (ValidationError, TypeError) as exc:
                logger.error(
                    "任务 ID=%s 的 llm_usage 数据格式错误，已跳过: %s",
                    rec.id,
                    exc,
                )

        items.append(
            SubscriptionItem(
                id=int(rec.id),
                url=rec.url,
                account=rec.account,
                password=rec.password,
                status=status_value or "",
                created_at=_format_dt(rec.created_at),
                duration_seconds=rec.duration_seconds,
                executed_at=_format_dt(rec.executed_at),
                task_dir=rec.task_dir,
                result=rec.result,
                failure_type=rec.failure_type,
                llm_usage=llm_usage_value,
            )
        )

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
        login_image_path = login_result.get("cover_image_path")

    extract_image_path = None
    extract_result = operations_results.get("extract")
    if isinstance(extract_result, dict):
        extract_image_path = extract_result.get("cover_image_path")

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


@router.get(
    "/stats",
    response_model=SubscriptionStatsResponse,
    summary="获取订阅任务统计数据",
)
def get_subscription_stats(
    time_range: str | None = Query(
        None, description="按执行时间范围过滤统计数据（today/yesterday/3d/7d/30d）"
    ),
    db: Session = Depends(get_db),
):
    """
    获取订阅任务的统计数据，包括：
    - 汇总统计（总数、今日新增、成功率、平均时长等）
    - 每日趋势（最近10天）
    - 状态分布
    - 最新任务列表（最近6条）
    - 失败类型分布（支持时间范围过滤）
    """
    tz_cn = timezone(timedelta(hours=8))
    cn_today = datetime.now(tz_cn).date()

    # 根据 time_range 参数计算时间范围（默认今天）
    now_cn = datetime.now(tz_cn)
    today_start_cn = now_cn.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end_cn = now_cn.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    if time_range:
        range_start_utc, range_end_utc = _parse_time_range(time_range, tz_cn)
        if range_start_utc is None or range_end_utc is None:
            # 无效参数，使用今天
            range_start_utc = today_start_cn.astimezone(timezone.utc)
            range_end_utc = today_end_cn.astimezone(timezone.utc)
    else:
        range_start_utc = today_start_cn.astimezone(timezone.utc)
        range_end_utc = today_end_cn.astimezone(timezone.utc)

    # 调试日志：排查统计数据异常
    logger.info(f"[统计查询] cn_today={cn_today}")
    logger.info(f"[统计查询] time_range={time_range}")
    logger.info(f"[统计查询] 时间范围(UTC): {range_start_utc} ~ {range_end_utc}")
    logger.info(f"[统计查询] 系统时区={datetime.now().astimezone().tzinfo}")

    # 1. 汇总统计
    summary_result = db.query(
        func.count(SubscriptionTask.id).label("total_tasks"),
        func.sum(case((SubscriptionTask.created_date == cn_today, 1), else_=0)).label(
            "today_tasks"
        ),
        func.sum(
            case((SubscriptionTask.status == TaskStatus.SUCCESS, 1), else_=0)
        ).label("success_count"),
        func.sum(
            case((SubscriptionTask.status == TaskStatus.FAILED, 1), else_=0)
        ).label("failed_count"),
        func.sum(
            case((SubscriptionTask.status == TaskStatus.PENDING, 1), else_=0)
        ).label("pending_count"),
        func.sum(
            case((SubscriptionTask.status == TaskStatus.RUNNING, 1), else_=0)
        ).label("running_count"),
        func.avg(
            case(
                (
                    SubscriptionTask.status == TaskStatus.SUCCESS,
                    SubscriptionTask.duration_seconds,
                ),
                else_=None,
            )
        ).label("avg_success_duration"),
        func.avg(
            case(
                (
                    SubscriptionTask.status == TaskStatus.FAILED,
                    SubscriptionTask.duration_seconds,
                ),
                else_=None,
            )
        ).label("avg_failed_duration"),
        func.sum(
            func.coalesce(
                func.cast(
                    func.json_extract(SubscriptionTask.llm_usage, "$.total_tokens"),
                    Integer,
                ),
                0,
            )
        ).label("total_tokens"),
        func.sum(
            case(
                (
                    (SubscriptionTask.executed_at.isnot(None))
                    & (SubscriptionTask.executed_at >= range_start_utc)
                    & (SubscriptionTask.executed_at <= range_end_utc),
                    func.coalesce(
                        func.cast(
                            func.json_extract(
                                SubscriptionTask.llm_usage, "$.total_tokens"
                            ),
                            Integer,
                        ),
                        0,
                    ),
                ),
                else_=0,
            )
        ).label("today_tokens"),
        func.avg(
            case(
                (
                    SubscriptionTask.status == TaskStatus.SUCCESS,
                    func.cast(
                        func.json_extract(SubscriptionTask.llm_usage, "$.total_tokens"),
                        Integer,
                    ),
                ),
                else_=None,
            )
        ).label("avg_success_tokens"),
        func.avg(
            case(
                (
                    SubscriptionTask.status == TaskStatus.FAILED,
                    func.cast(
                        func.json_extract(SubscriptionTask.llm_usage, "$.total_tokens"),
                        Integer,
                    ),
                ),
                else_=None,
            )
        ).label("avg_failed_tokens"),
        # 今日任务详细统计（基于执行时间）
        func.sum(
            case(
                (
                    (SubscriptionTask.executed_at.isnot(None))
                    & (SubscriptionTask.executed_at >= range_start_utc)
                    & (SubscriptionTask.executed_at <= range_end_utc)
                    & (SubscriptionTask.status == TaskStatus.SUCCESS),
                    1,
                ),
                else_=0,
            )
        ).label("today_success_count"),
        func.sum(
            case(
                (
                    (SubscriptionTask.executed_at.isnot(None))
                    & (SubscriptionTask.executed_at >= range_start_utc)
                    & (SubscriptionTask.executed_at <= range_end_utc)
                    & (SubscriptionTask.status == TaskStatus.FAILED),
                    1,
                ),
                else_=0,
            )
        ).label("today_failed_count"),
        func.avg(
            case(
                (
                    (SubscriptionTask.executed_at.isnot(None))
                    & (SubscriptionTask.executed_at >= range_start_utc)
                    & (SubscriptionTask.executed_at <= range_end_utc)
                    & (SubscriptionTask.status == TaskStatus.SUCCESS),
                    SubscriptionTask.duration_seconds,
                ),
                else_=None,
            )
        ).label("today_avg_success_duration"),
        func.avg(
            case(
                (
                    (SubscriptionTask.executed_at.isnot(None))
                    & (SubscriptionTask.executed_at >= range_start_utc)
                    & (SubscriptionTask.executed_at <= range_end_utc)
                    & (SubscriptionTask.status == TaskStatus.FAILED),
                    SubscriptionTask.duration_seconds,
                ),
                else_=None,
            )
        ).label("today_avg_failed_duration"),
        func.avg(
            case(
                (
                    (SubscriptionTask.executed_at.isnot(None))
                    & (SubscriptionTask.executed_at >= range_start_utc)
                    & (SubscriptionTask.executed_at <= range_end_utc)
                    & (SubscriptionTask.status == TaskStatus.SUCCESS),
                    func.cast(
                        func.json_extract(SubscriptionTask.llm_usage, "$.total_tokens"),
                        Integer,
                    ),
                ),
                else_=None,
            )
        ).label("today_avg_success_tokens"),
        func.avg(
            case(
                (
                    (SubscriptionTask.executed_at.isnot(None))
                    & (SubscriptionTask.executed_at >= range_start_utc)
                    & (SubscriptionTask.executed_at <= range_end_utc)
                    & (SubscriptionTask.status == TaskStatus.FAILED),
                    func.cast(
                        func.json_extract(SubscriptionTask.llm_usage, "$.total_tokens"),
                        Integer,
                    ),
                ),
                else_=None,
            )
        ).label("today_avg_failed_tokens"),
    ).first()

    total_tasks = summary_result.total_tasks or 0
    today_tasks = summary_result.today_tasks or 0
    success_count = summary_result.success_count or 0
    failed_count = summary_result.failed_count or 0
    pending_count = summary_result.pending_count or 0
    running_count = summary_result.running_count or 0
    
    # 如果指定了历史时间范围，待执行和执行中应该为0
    # 因为这些是当前状态，不应该出现在历史时间范围内
    if time_range and time_range != "today":
        pending_count = 0
        running_count = 0
    
    avg_success_duration = summary_result.avg_success_duration or 0.0
    avg_failed_duration = summary_result.avg_failed_duration or 0.0
    total_tokens = summary_result.total_tokens or 0
    today_tokens = summary_result.today_tokens or 0
    avg_success_tokens = summary_result.avg_success_tokens or 0.0
    avg_failed_tokens = summary_result.avg_failed_tokens or 0.0
    today_success_count = summary_result.today_success_count or 0
    today_failed_count = summary_result.today_failed_count or 0
    today_avg_success_duration = summary_result.today_avg_success_duration or 0.0
    today_avg_failed_duration = summary_result.today_avg_failed_duration or 0.0
    today_avg_success_tokens = summary_result.today_avg_success_tokens or 0.0
    today_avg_failed_tokens = summary_result.today_avg_failed_tokens or 0.0

    # 调试日志：输出今日统计结果
    logger.info(
        f"[统计结果] today_success_count={today_success_count}, "
        f"today_failed_count={today_failed_count}, "
        f"today_tasks={today_tasks}"
    )

    # 计算成功率
    total_completed = success_count + failed_count
    success_rate = (success_count / total_completed) if total_completed > 0 else 0.0

    # 计算今日成功率
    today_completed = today_success_count + today_failed_count
    today_success_rate = (
        (today_success_count / today_completed) if today_completed > 0 else 0.0
    )

    summary = SubscriptionStatsSummary(
        total_tasks=total_tasks,
        today_tasks=today_tasks,
        success_count=success_count,
        failed_count=failed_count,
        pending_count=pending_count,
        running_count=running_count,
        success_rate=success_rate,
        avg_success_duration_seconds=avg_success_duration,
        avg_failed_duration_seconds=avg_failed_duration,
        total_tokens=total_tokens,
        today_tokens=today_tokens,
        avg_success_tokens=avg_success_tokens,
        avg_failed_tokens=avg_failed_tokens,
        today_success_count=today_success_count,
        today_failed_count=today_failed_count,
        today_success_rate=today_success_rate,
        today_avg_success_duration_seconds=today_avg_success_duration,
        today_avg_failed_duration_seconds=today_avg_failed_duration,
        today_avg_success_tokens=today_avg_success_tokens,
        today_avg_failed_tokens=today_avg_failed_tokens,
    )

    # 2. 每日趋势（最近10天）
    today = cn_today
    ten_days_ago = today - timedelta(days=10)

    daily_trend_results = (
        db.query(
            SubscriptionTask.created_date.label("date"),
            func.count(SubscriptionTask.id).label("total_count"),
            func.sum(
                case((SubscriptionTask.status == TaskStatus.SUCCESS, 1), else_=0)
            ).label("success_count"),
            func.sum(
                case((SubscriptionTask.status == TaskStatus.FAILED, 1), else_=0)
            ).label("failed_count"),
        )
        .filter(SubscriptionTask.created_date >= ten_days_ago)
        .group_by(SubscriptionTask.created_date)
        .order_by(SubscriptionTask.created_date.asc())
        .all()
    )

    daily_trend = []
    for row in daily_trend_results:
        total_count = row.total_count or 0
        success_count_day = row.success_count or 0
        failed_count_day = row.failed_count or 0
        completed_day = success_count_day + failed_count_day
        day_success_rate = (
            (success_count_day / completed_day) if completed_day > 0 else 0.0
        )

        daily_trend.append(
            DailyTrendItem(
                date=row.date.isoformat() if row.date else "",
                total_count=total_count,
                success_count=success_count_day,
                failed_count=failed_count_day,
                success_rate=day_success_rate,
            )
        )

    # 3. 状态分布（根据时间范围过滤）
    status_query = db.query(
        SubscriptionTask.status.label("status"),
        func.count(SubscriptionTask.id).label("count"),
    )
    
    # 应用时间范围过滤（如果指定）
    if time_range:
        status_query = status_query.filter(
            SubscriptionTask.executed_at.isnot(None),
            SubscriptionTask.executed_at >= range_start_utc,
            SubscriptionTask.executed_at <= range_end_utc,
        )
    
    status_results = status_query.group_by(SubscriptionTask.status).all()

    status_distribution = []
    for row in status_results:
        status_value = row.status.value if hasattr(row.status, "value") else row.status
        status_distribution.append(
            StatusDistributionItem(status=status_value or "", count=row.count or 0)
        )

    # 4. 最新任务列表（最近6条）
    def _format_dt(dt):
        if not dt:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(tz_cn).isoformat()

    # 状态优先级：running > success/failed > pending
    recent_status_priority = case(
        (SubscriptionTask.status == TaskStatus.RUNNING, 0),
        (SubscriptionTask.status.in_([TaskStatus.SUCCESS, TaskStatus.FAILED]), 1),
        else_=2,
    )

    recent_task_query = db.query(SubscriptionTask)
    
    # 应用时间范围过滤（如果指定）
    if time_range:
        recent_task_query = recent_task_query.filter(
            SubscriptionTask.executed_at.isnot(None),
            SubscriptionTask.executed_at >= range_start_utc,
            SubscriptionTask.executed_at <= range_end_utc,
        )
    
    recent_task_records = (
        recent_task_query
        .order_by(
            recent_status_priority,
            SubscriptionTask.executed_at.desc().nulls_last(),
            SubscriptionTask.id.asc(),
        )
        .limit(5)
        .all()
    )

    recent_tasks = []
    for rec in recent_task_records:
        status_value = rec.status.value if hasattr(rec.status, "value") else rec.status

        # 安全地转换 llm_usage
        llm_usage_value = None
        if rec.llm_usage is not None:
            try:
                llm_usage_value = LLMUsage(**rec.llm_usage)
            except (ValidationError, TypeError) as exc:
                logger.error(
                    "任务 ID=%s 的 llm_usage 数据格式错误，已跳过: %s",
                    rec.id,
                    exc,
                )

        recent_tasks.append(
            SubscriptionItem(
                id=int(rec.id) if rec.id is not None else 0,
                url=rec.url,
                account=rec.account,
                password=rec.password,
                status=status_value or "",
                created_at=_format_dt(rec.created_at),
                duration_seconds=rec.duration_seconds or 0,
                executed_at=_format_dt(rec.executed_at),
                task_dir=rec.task_dir,
                result=rec.result,
                failure_type=rec.failure_type,
                llm_usage=llm_usage_value,
            )
        )

    # 5. 失败类型分布统计（支持时间范围过滤）
    failure_type_query = db.query(
        SubscriptionTask.failure_type,
        func.count(SubscriptionTask.id).label("count"),
    ).filter(
        SubscriptionTask.status == TaskStatus.FAILED,
        SubscriptionTask.failure_type.isnot(None),
    )

    # 应用时间范围过滤（如果指定）
    if time_range:
        start_time, end_time = _parse_time_range(time_range, tz_cn)
        if start_time and end_time:
            failure_type_query = failure_type_query.filter(
                SubscriptionTask.executed_at.isnot(None),
                SubscriptionTask.executed_at >= start_time,
                SubscriptionTask.executed_at <= end_time,
            )

    failure_type_results = (
        failure_type_query.group_by(SubscriptionTask.failure_type)
        .order_by(func.count(SubscriptionTask.id).desc())
        .all()
    )

    # 计算时间范围内的实际失败总数（用于百分比计算）
    range_failed_count = sum(row.count or 0 for row in failure_type_results)

    # Top 5 + "其他"
    top_5_types = failure_type_results[:5]
    others_count = sum(row.count or 0 for row in failure_type_results[5:])

    failure_type_distribution = []
    for row in top_5_types:
        count = row.count or 0
        # 使用时间范围内的失败数计算百分比
        percentage = (count / range_failed_count * 100) if range_failed_count > 0 else 0.0
        failure_type_distribution.append(
            FailureTypeDistributionItem(
                type=row.failure_type or "",
                label=FAILURE_TYPE_LABELS.get(
                    row.failure_type or "", row.failure_type or ""
                ),
                count=count,
                percentage=round(percentage, 1),
            )
        )

    # 添加"其他"类别
    if others_count > 0:
        others_percentage = (
            (others_count / range_failed_count * 100) if range_failed_count > 0 else 0.0
        )
        failure_type_distribution.append(
            FailureTypeDistributionItem(
                type="others",
                label="其他",
                count=others_count,
                percentage=round(others_percentage, 1),
            )
        )

    failure_summary = FailureSummary(
        total_failed=range_failed_count,  # 使用时间范围内的数量
        unique_types=len(failure_type_results),
    )

    return SubscriptionStatsResponse(
        summary=summary,
        daily_trend=daily_trend,
        status_distribution=status_distribution,
        recent_tasks=recent_tasks,
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
    types_list = get_failure_types_ordered()
    return FailureTypesResponse(items=[FailureTypeItem(**item) for item in types_list])
