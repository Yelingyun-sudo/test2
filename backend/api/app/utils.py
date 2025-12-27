from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException
from website_analytics.utils import PROJECT_ROOT


def resolve_task_dir(task_dir: str) -> Path:
    """解析任务目录路径，确保安全"""
    raw = Path(task_dir)
    if raw.is_absolute() or ".." in raw.parts:
        raise HTTPException(status_code=400, detail="非法 task_dir")
    resolved = (PROJECT_ROOT / raw).resolve()
    try:
        resolved.relative_to(PROJECT_ROOT.resolve())
    except Exception as exc:
        raise HTTPException(status_code=400, detail="非法 task_dir") from exc
    return resolved
