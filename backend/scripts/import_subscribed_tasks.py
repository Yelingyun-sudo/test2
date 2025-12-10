#!/usr/bin/env python3
"""将 subscribed_clean.jsonl 导入 subscribed_tasks 表。"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy.exc import IntegrityError

# 确保可以导入 api 包
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from api.app.db import SessionLocal, init_db  # noqa: E402
from api.app.models import SubscribedTask, TaskStatus  # noqa: E402

DATA_PATH = ROOT / "resources" / "subscribed_clean.jsonl"


def load_records():
    if not DATA_PATH.exists():
        raise SystemExit(f"数据文件不存在: {DATA_PATH}")

    with DATA_PATH.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"第 {line_no} 行解析失败: {exc}") from exc
            yield payload


def main() -> None:
    init_db()
    session = SessionLocal()
    now = datetime.now(timezone.utc)
    today = date.today()

    inserted = 0
    skipped = 0

    try:
        for record in load_records():
            task = SubscribedTask(
                url=record.get("url"),
                account=record.get("account"),
                password=record.get("password"),
                status=TaskStatus.PENDING,
                duration_seconds=0,
                retry_count=0,
                history_extract_count=0,
                last_extracted_at=None,
                result=None,
                failure_type=None,
                created_at=now,
                created_date=today,
            )
            session.add(task)
            try:
                session.commit()
                inserted += 1
            except IntegrityError:
                session.rollback()
                skipped += 1
    finally:
        session.close()

    print(
        f"导入完成：新增 {inserted} 条，跳过（主键/唯一冲突） {skipped} 条。"
    )


if __name__ == "__main__":
    main()
