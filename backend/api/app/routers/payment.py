from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..schemas.payment import PaymentListResponse

router = APIRouter(
    prefix="/payment",
    tags=["payment"],
)


@router.get(
    "/list",
    response_model=PaymentListResponse,
    summary="支付链接任务列表（占位，返回空列表）",
)
def list_payment(
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(15, ge=1, le=100, description="每页条数"),
    db: Session = Depends(get_db),
):
    # 占位实现：返回空列表
    return PaymentListResponse(
        items=[],
        total=0,
        page=page,
        page_size=page_size,
    )
