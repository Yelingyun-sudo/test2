from __future__ import annotations

import json
from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException, Query, status

from ..schemas.unsubscribed import UnsubscribedItem, UnsubscribedListResponse

router = APIRouter(prefix="/unsubscribed", tags=["unsubscribed"])

_DATA_PATH = (
    Path(__file__).resolve().parents[3] / "resources" / "unsubscribed_clean.jsonl"
)


def _load_data() -> List[UnsubscribedItem]:
    if not _DATA_PATH.exists():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="未订阅数据文件不存在",
        )
    items: List[UnsubscribedItem] = []
    with _DATA_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            payload = json.loads(line)
            items.append(UnsubscribedItem(**payload))
    return items


@router.get(
    "/list",
    response_model=UnsubscribedListResponse,
    summary="未订阅网站列表（分页 + 简单检索）",
)
def list_unsubscribed(
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    q: str | None = Query(None, description="按 url 包含匹配"),
):
    items = _load_data()

    if q:
        keyword = q.lower()
        items = [item for item in items if keyword in item.url.lower()]

    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    sliced = items[start:end]

    return UnsubscribedListResponse(
        items=sliced,
        total=total,
        page=page,
        page_size=page_size,
    )
