from __future__ import annotations

import json
import logging
from datetime import timedelta, timezone
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


@router.get(
    "/list",
    response_model=EvidenceListResponse,
    summary="未订阅网站列表（分页 + 简单检索，读取数据库）",
)
def list_evidence(
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(15, ge=1, le=100, description="每页条数"),
    q: str | None = Query(None, description="按 url 包含匹配"),
    db: Session = Depends(get_db),
):
    query = db.query(EvidenceTask)
    if q:
        keyword = f"%{q.lower()}%"
        query = query.filter(func.lower(EvidenceTask.url).like(keyword))

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


class TaskArtifacts(BaseModel):
    """任务产物元信息"""

    login_image_path: str | None
    evidence_image_path: str | None
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

        return TaskArtifacts(
            login_image_path=operations.get("login", {}).get("last_capture_path"),
            evidence_image_path=operations.get("evidence", {}).get("last_capture_path"),
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
