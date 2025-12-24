from __future__ import annotations

from datetime import timedelta, timezone
from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import EvidenceTask
from ..schemas.evidence import EvidenceItem, EvidenceListResponse

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
    records: List[EvidenceTask] = (
        query.order_by(EvidenceTask.id.asc())
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

    sliced = [
        EvidenceItem(
            id=int(rec.id),
            url=rec.url,
            status=rec.status.value if rec.status else "PENDING",
            created_at=_format_dt(rec.created_at),
            executed_at=_format_dt(rec.executed_at),
            duration_seconds=rec.duration_seconds or 0,
        )
        for rec in records
    ]

    return EvidenceListResponse(
        items=sliced,
        total=total,
        page=page,
        page_size=page_size,
    )
