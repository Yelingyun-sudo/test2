from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, List

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from ..constants import TZ_CHINA as tz_cn
from ..db import get_db
from ..enums import TaskStatus
from ..models import EvidenceTask
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
from ..schemas.evidence import (
    EvidenceItem,
    EvidenceListResponse,
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
    prefix="/evidence",
    tags=["evidence"],
)


@router.get(
    "/list",
    response_model=EvidenceListResponse,
    summary="未订阅网站列表（分页 + 简单检索，读取数据库）",
)
def list_evidence(
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(15, ge=1, le=100, description="每页条数"),
    q: str | None = Query(None, description="按 url 包含匹配"),
    status: str | None = Query(
        None, description="按任务状态过滤（小写，如 failed/success）"
    ),
    failure_type: str | None = Query(
        None, description="按失败类型过滤（通常与 status=failed 配合使用）"
    ),
    start_date: str | None = Query(None, description="开始日期 YYYY-MM-DD 格式"),
    end_date: str | None = Query(None, description="结束日期 YYYY-MM-DD 格式"),
    db: Session = Depends(get_db),
):
    query = db.query(EvidenceTask)

    if q:
        keyword = f"%{q.lower()}%"
        query = query.filter(func.lower(EvidenceTask.url).like(keyword))

    if status:
        # 将小写参数转为大写枚举值
        try:
            status_enum = TaskStatus(status.upper())
            query = query.filter(EvidenceTask.status == status_enum)
        except ValueError:
            # 无效的状态值，忽略该过滤条件
            pass

    if failure_type:
        query = query.filter(EvidenceTask.failure_type == failure_type)

    # 时间范围筛选
    # 应用时间范围过滤
    if start_date and end_date:
        range_start_utc, range_end_utc = parse_date_range(start_date, end_date, tz_cn)
        if range_start_utc and range_end_utc:
            query = query.filter(
                EvidenceTask.executed_at.isnot(None),
                EvidenceTask.executed_at >= range_start_utc,
                EvidenceTask.executed_at <= range_end_utc,
            )

    total = query.count()

    # 按状态优先级排序：执行中 > 已完成 > 待执行
    status_priority = case(
        (EvidenceTask.status == TaskStatus.RUNNING, 0),
        (EvidenceTask.status.in_([TaskStatus.SUCCESS, TaskStatus.FAILED]), 1),
        else_=2,
    )

    records: List[EvidenceTask] = (
        query.order_by(
            status_priority,
            EvidenceTask.executed_at.desc().nulls_last(),
            EvidenceTask.id.asc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    def _format_dt(dt):
        return format_datetime(dt, tz_cn)

    sliced = []
    for rec in records:
        sliced.append(_build_evidence_item(rec, _format_dt))

    return EvidenceListResponse(
        items=sliced,
        total=total,
        page=page,
        page_size=page_size,
    )


class EvidenceEntryDetail(BaseModel):
    """证据入口详情"""

    json_data: str = Field(alias="json")
    screenshot: str
    text: str


class TaskArtifacts(BaseModel):
    """任务产物元信息"""

    register_image_path: str | None
    login_image_path: str | None
    evidence_image_path: str | None
    evidence_entries_detail: list[EvidenceEntryDetail] | None = None
    video_path: str | None
    video_seek_seconds: float | None


@router.get(
    "/{task_id}/artifacts",
    response_model=TaskArtifacts,
    summary="获取任务产物元信息（截图、视频路径）",
)
def get_task_artifacts(
    task_id: int,
    db: Session = Depends(get_db),
):
    task = db.get(EvidenceTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if not task.task_dir:
        raise HTTPException(status_code=404, detail="任务目录不存在")

    task_dir_abs = resolve_task_dir(task.task_dir)
    summary_file = task_dir_abs / "task_summary.json"

    if not summary_file.exists():
        raise HTTPException(status_code=404, detail="任务摘要文件不存在")

    try:
        with open(summary_file, encoding="utf-8") as f:
            summary = json.load(f)

        coordinator = summary.get("coordinator_output", {})
        operations = coordinator.get("operations_results", {})

        # 获取证据截图路径：优先使用 cover_image_path，否则从 entries_detail 中获取第一个入口的截图
        evidence_result = operations.get("evidence", {})
        evidence_image_path = evidence_result.get("cover_image_path")
        if not evidence_image_path:
            entries_detail = evidence_result.get("entries_detail", [])
            if entries_detail and isinstance(entries_detail, list):
                first_entry = entries_detail[0]
                if isinstance(first_entry, dict):
                    evidence_image_path = first_entry.get("screenshot")

        # 获取证据入口详情
        evidence_entries_detail = None
        entries_detail_raw = evidence_result.get("entries_detail", [])
        if entries_detail_raw and isinstance(entries_detail_raw, list):
            try:
                evidence_entries_detail = [
                    EvidenceEntryDetail(**entry)
                    for entry in entries_detail_raw
                    if isinstance(entry, dict)
                ]
            except Exception:
                # 如果解析失败，返回 None（向后兼容）
                evidence_entries_detail = None

        return TaskArtifacts(
            register_image_path=operations.get("register", {}).get("cover_image_path"),
            login_image_path=operations.get("login", {}).get("cover_image_path"),
            evidence_image_path=evidence_image_path,
            evidence_entries_detail=evidence_entries_detail,
            video_path=coordinator.get("video_path"),
            video_seek_seconds=coordinator.get("video_seek_seconds"),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"解析任务摘要失败: {str(e)}")


@router.get(
    "/{task_id}/artifact",
    summary="获取任务产物文件内容（截图、视频）",
)
def get_task_artifact(
    task_id: int,
    path: str = Query(
        ..., description="相对路径，如 captures/xxx.png 或 page-xxx.webm"
    ),
    db: Session = Depends(get_db),
):
    task = db.get(EvidenceTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if not task.task_dir:
        raise HTTPException(status_code=404, detail="任务目录不存在")

    task_dir_abs = resolve_task_dir(task.task_dir)
    raw = Path(path)
    if raw.is_absolute() or ".." in raw.parts:
        raise HTTPException(status_code=400, detail="非法路径")

    artifact_path = (task_dir_abs / raw).resolve()

    # 安全检查：防止路径穿越
    try:
        artifact_path.relative_to(task_dir_abs.resolve())
    except Exception as exc:
        raise HTTPException(status_code=403, detail="非法路径") from exc

    if not artifact_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")

    # 根据文件类型返回
    if artifact_path.suffix.lower() in [".png", ".jpg", ".jpeg"]:
        media_type = (
            "image/png" if artifact_path.suffix.lower() == ".png" else "image/jpeg"
        )
    elif artifact_path.suffix.lower() in [".webm", ".mp4"]:
        media_type = (
            "video/webm" if artifact_path.suffix.lower() == ".webm" else "video/mp4"
        )
    else:
        media_type = "application/octet-stream"

    return FileResponse(artifact_path, media_type=media_type)


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


# ===== 统计辅助函数 =====


def _compute_summary(
    db: Session,
    range_start_utc: datetime | None,
    range_end_utc: datetime | None,
    tz_cn: timezone,
) -> TaskStatsSummary:
    """计算汇总统计"""
    from .common import compute_task_summary

    return compute_task_summary(db, EvidenceTask, range_start_utc, range_end_utc, tz_cn)


def _build_evidence_item(rec: EvidenceTask, _format_dt: Callable) -> EvidenceItem:
    """构建 EvidenceItem 对象"""
    from .common import build_task_item

    return build_task_item(rec, EvidenceItem, _format_dt)


# ===== 专用统计端点 =====


@router.get(
    "/stats/summary",
    response_model=SummaryResponse,
    summary="获取取证任务汇总统计",
)
def get_evidence_stats_summary(
    start_date: str | None = Query(None, description="开始日期 YYYY-MM-DD 格式"),
    end_date: str | None = Query(None, description="结束日期 YYYY-MM-DD 格式"),
    db: Session = Depends(get_db),
):
    """获取取证任务的汇总统计数据"""
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
    summary="获取取证任务每日趋势",
)
def get_evidence_stats_daily_trend(
    db: Session = Depends(get_db),
):
    """获取取证任务的每日趋势数据（最近8天）"""
    daily_trend = compute_daily_trend(
        db, EvidenceTask, tz_cn, days=8, daily_trend_item_cls=DailyTrendItem
    )
    return DailyTrendResponse(daily_trend=daily_trend)


@router.get(
    "/stats/status-distribution",
    response_model=StatusDistributionResponse,
    summary="获取取证任务状态分布",
)
def get_evidence_stats_status_distribution(
    start_date: str | None = Query(None, description="开始日期 YYYY-MM-DD 格式"),
    end_date: str | None = Query(None, description="结束日期 YYYY-MM-DD 格式"),
    db: Session = Depends(get_db),
):
    """获取取证任务的状态分布数据"""
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
        EvidenceTask,
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
    summary="获取最新取证任务列表",
)
def get_evidence_stats_recent_tasks(
    start_date: str | None = Query(None, description="开始日期 YYYY-MM-DD 格式"),
    end_date: str | None = Query(None, description="结束日期 YYYY-MM-DD 格式"),
    db: Session = Depends(get_db),
):
    """获取最新取证任务列表（最多 100 条）"""
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
        EvidenceTask,
        start_date,
        end_date,
        range_start_utc,
        range_end_utc,
        tz_cn,
        EvidenceItem,
        _build_evidence_item,
    )
    return RecentTasksResponse(recent_tasks=recent_tasks)


@router.get(
    "/stats/failure-types",
    response_model=FailureTypesStatsResponse,
    summary="获取取证任务失败类型统计",
)
def get_evidence_stats_failure_types(
    start_date: str | None = Query(None, description="开始日期 YYYY-MM-DD 格式"),
    end_date: str | None = Query(None, description="结束日期 YYYY-MM-DD 格式"),
    db: Session = Depends(get_db),
):
    """获取失败类型分布统计和失败总览"""
    failure_type_distribution, failure_summary = compute_failure_stats(
        db,
        EvidenceTask,
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
