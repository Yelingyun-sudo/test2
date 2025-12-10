from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import SubscribedTask
from ..schemas.subscribed import SubscribedItem, SubscribedListResponse

router = APIRouter(prefix="/subscribed", tags=["subscribed"])


@router.get(
    "/list",
    response_model=SubscribedListResponse,
    summary="订阅网站列表（分页 + 简单检索，读取数据库）",
)
def list_subscribed(
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    q: str | None = Query(None, description="按 url / account / password 包含匹配"),
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

    total = query.count()
    records: List[SubscribedTask] = (
        query.order_by(SubscribedTask.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    def _format_dt(dt):
        return dt.isoformat() if dt else None

    items = []
    for rec in records:
        status_value = rec.status.value if hasattr(rec.status, "value") else rec.status
        items.append(
            SubscribedItem(
                id=int(rec.id) if rec.id is not None else None,  # type: ignore[arg-type]
                url=rec.url,
                status=status_value or "",
                duration_seconds=rec.duration_seconds,
                retry_count=rec.retry_count,
                history_extract_count=rec.history_extract_count,
                last_extracted_at=_format_dt(rec.last_extracted_at),
                result=rec.result,
            )
        )

    return SubscribedListResponse(items=items, total=total, page=page, page_size=page_size)
