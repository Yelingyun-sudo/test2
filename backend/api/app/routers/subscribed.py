from __future__ import annotations

import json
from datetime import timedelta, timezone
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import SubscribedTask, TaskStatus
from ..schemas.subscribed import (
    SubscribedArtifactsResponse,
    SubscribedItem,
    SubscribedListResponse,
)
from website_analytics.utils import PROJECT_ROOT

router = APIRouter(
    prefix="/subscribed",
    tags=["subscribed"],
)


@router.get(
    "/list",
    response_model=SubscribedListResponse,
    summary="订阅网站列表（分页 + 简单检索，读取数据库）",
)
def list_subscribed(
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    q: str | None = Query(None, description="按 url / account / password 包含匹配"),
    status: TaskStatus | None = Query(None, description="按任务状态过滤"),
    db: Session = Depends(get_db),
):
    query = db.query(SubscribedTask)

    if q:
        keyword = f"%{q.lower()}%"
        query = query.filter(
            func.lower(SubscribedTask.url).like(keyword)
            | func.lower(SubscribedTask.account).like(keyword)
            | func.lower(SubscribedTask.password).like(keyword)
        )

    if status:
        query = query.filter(SubscribedTask.status == status)

    total = query.count()

    tz_cn = timezone(timedelta(hours=8))
    status_priority = case(
        (SubscribedTask.status == TaskStatus.RUNNING, 0),
        (SubscribedTask.status.in_([TaskStatus.SUCCESS, TaskStatus.FAILED]), 1),
        else_=2,
    )

    records: List[SubscribedTask] = (
        query.order_by(status_priority, SubscribedTask.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    def _format_dt(dt):
        if not dt:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(tz_cn).isoformat()

    items = []
    for rec in records:
        status_value = rec.status.value if hasattr(rec.status, "value") else rec.status
        items.append(
            SubscribedItem(
                id=int(rec.id) if rec.id is not None else None,  # type: ignore[arg-type]
                url=rec.url,
                account=rec.account,
                password=rec.password,
                status=status_value or "",
                created_at=_format_dt(rec.created_at),
                duration_seconds=rec.duration_seconds,
                retry_count=rec.retry_count,
                history_extract_count=rec.history_extract_count,
                executed_at=_format_dt(rec.executed_at),
                task_dir=rec.task_dir,
                result=rec.result,
            )
        )

    return SubscribedListResponse(
        items=items, total=total, page=page, page_size=page_size
    )


def _resolve_task_dir(task_dir: str) -> Path:
    raw = Path(task_dir)
    if raw.is_absolute() or ".." in raw.parts:
        raise HTTPException(status_code=400, detail="非法 task_dir")
    resolved = (PROJECT_ROOT / raw).resolve()
    try:
        resolved.relative_to(PROJECT_ROOT.resolve())
    except Exception as exc:
        raise HTTPException(status_code=400, detail="非法 task_dir") from exc
    return resolved


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
    response_model=SubscribedArtifactsResponse,
    summary="获取任务产物路径（截图/视频）",
)
def get_task_artifacts(
    task_id: int,
    db: Session = Depends(get_db),
):
    task = db.get(SubscribedTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    status_value = task.status.value if hasattr(task.status, "value") else task.status
    task_dir = task.task_dir
    if not task_dir:
        return SubscribedArtifactsResponse(status=status_value or "")

    task_dir_abs = _resolve_task_dir(task_dir)
    summary = _read_task_summary(task_dir_abs)
    coordinator = summary.get("coordinator_output") or {}
    operations_results = coordinator.get("operations_results") or {}

    login_image_path = None
    login_result = operations_results.get("login")
    if isinstance(login_result, dict):
        login_image_path = login_result.get("last_capture_path")

    extract_image_path = None
    extract_result = operations_results.get("extract")
    if isinstance(extract_result, dict):
        extract_image_path = extract_result.get("last_capture_path")

    video_path = coordinator.get("video_path")
    video_seek_seconds = coordinator.get("video_seek_seconds")

    return SubscribedArtifactsResponse(
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
    task = db.get(SubscribedTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not task.task_dir:
        raise HTTPException(status_code=404, detail="任务暂无产物")

    task_dir_abs = _resolve_task_dir(task.task_dir)
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
