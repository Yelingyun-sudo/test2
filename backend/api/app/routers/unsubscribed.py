from __future__ import annotations

from datetime import timedelta, timezone
from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import UnsubscribedTask
from ..schemas.unsubscribed import UnsubscribedItem, UnsubscribedListResponse

router = APIRouter(
    prefix="/unsubscribed",
    tags=["unsubscribed"],
)


@router.get(
    "/list",
    response_model=UnsubscribedListResponse,
    summary="未订阅网站列表（分页 + 简单检索，读取数据库）",
)
def list_unsubscribed(
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(15, ge=1, le=100, description="每页条数"),
    q: str | None = Query(None, description="按 url 包含匹配"),
    db: Session = Depends(get_db),
):
    query = db.query(UnsubscribedTask)
    if q:
        keyword = f"%{q.lower()}%"
        query = query.filter(func.lower(UnsubscribedTask.url).like(keyword))

    total = query.count()
    records: List[UnsubscribedTask] = (
        query.order_by(UnsubscribedTask.id.asc())
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
        UnsubscribedItem(
            id=int(rec.id) if rec.id is not None else 0,  # type: ignore[arg-type]
            url=rec.url,
            created_at=_format_dt(rec.created_at),
        )
        for rec in records
    ]

    return UnsubscribedListResponse(
        items=sliced,
        total=total,
        page=page,
        page_size=page_size,
    )
