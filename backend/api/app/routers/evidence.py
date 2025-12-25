from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, ValidationError
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from ..db import get_db
from ..utils import resolve_task_dir
from ..models import EvidenceTask, TaskStatus
from ..schemas.common import FailureTypeItem, FailureTypesResponse, LLMUsage
from ..schemas.evidence import (
    EvidenceItem,
    EvidenceListResponse,
)
from website_analytics.output_types import get_failure_types_ordered

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/evidence",
    tags=["evidence"],
)


def _parse_time_range(
    range_key: str | None, tz_cn: timezone
) -> tuple[datetime | None, datetime | None]:
    """
    解析预设时间范围，返回 UTC 时区的 (开始时间, 结束时间)

    Args:
        range_key: 时间范围键值（today/yesterday/3d/7d/30d）
        tz_cn: 中国时区

    Returns:
        (start_time_utc, end_time_utc) 或 (None, None)

    Note:
        内部先计算东八区的时间范围，然后转换为 UTC 返回。
        这样可以确保与数据库中存储的 UTC 时间正确比较。
    """
    if not range_key:
        return None, None

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
    executed_within: str | None = Query(
        None, description="按执行时间范围过滤（today/yesterday/3d/7d/30d）"
    ),
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

    tz_cn = timezone(timedelta(hours=8))
    if executed_within:
        start_time, end_time = _parse_time_range(executed_within, tz_cn)
        if start_time and end_time:
            query = query.filter(
                EvidenceTask.executed_at.isnot(None),
                EvidenceTask.executed_at >= start_time,
                EvidenceTask.executed_at <= end_time,
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

    tz_cn = timezone(timedelta(hours=8))

    def _format_dt(dt) -> str:
        if not dt:
            return ""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(tz_cn).isoformat()

    sliced = []
    for rec in records:
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

        sliced.append(
            EvidenceItem(
                id=int(rec.id),
                url=rec.url,
                account=rec.account,
                password=rec.password,
                status=rec.status.value if rec.status else "PENDING",
                created_at=_format_dt(rec.created_at),
                executed_at=_format_dt(rec.executed_at),
                duration_seconds=rec.duration_seconds or 0,
                result=rec.result,
                failure_type=rec.failure_type,
                task_dir=rec.task_dir,
                llm_usage=llm_usage_value,
            )
        )

    return EvidenceListResponse(
        items=sliced,
        total=total,
        page=page,
        page_size=page_size,
    )


class EvidenceEntryDetail(BaseModel):
    """证据入口详情"""

    json: str
    screenshot: str
    text: str


class TaskArtifacts(BaseModel):
    """任务产物元信息"""

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
                    EvidenceEntryDetail(**entry) for entry in entries_detail_raw if isinstance(entry, dict)
                ]
            except Exception:
                # 如果解析失败，返回 None（向后兼容）
                evidence_entries_detail = None

        return TaskArtifacts(
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
    types_list = get_failure_types_ordered()
    return FailureTypesResponse(items=[FailureTypeItem(**item) for item in types_list])
