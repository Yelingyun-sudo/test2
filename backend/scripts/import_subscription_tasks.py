#!/usr/bin/env python3
"""将 subscription_clean.jsonl 导入 subscription_tasks 表。"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.exc import IntegrityError

# 确保可以导入 api 包
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from api.app.db import SessionLocal, init_db  # noqa: E402
from api.app.models import SubscriptionTask, TaskStatus  # noqa: E402

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
示例:
  python %(prog)s data.jsonl           增量导入，跳过重复记录
  python %(prog)s data.jsonl --clear   清空表后全量导入
""",
    )
    parser.add_argument(
        "file",
        type=Path,
        nargs="?",
        help="要导入的 JSONL 数据文件路径",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="导入前清空 subscription_tasks 表",
    )
    args = parser.parse_args()
    if args.file is None:
        parser.print_help()
        sys.exit(0)
    return args


def load_records(data_path: Path):
    if not data_path.exists():
        raise SystemExit(f"数据文件不存在: {data_path}")

    with data_path.open("r", encoding="utf-8") as f:
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
    args = parse_args()
    init_db()
    session = SessionLocal()
    now = datetime.now(timezone.utc)
    tz_china = timezone(timedelta(hours=8))
    today = now.astimezone(tz_china).date()

    inserted = 0
    skipped = 0
    cleared = 0

    try:
        if args.clear:
            cleared = (
                session.query(SubscriptionTask)
                .delete(synchronize_session=False)  # type: ignore[arg-type]
            )
            session.commit()
            print(f"已清空 subscription_tasks 表：删除 {cleared} 条记录。")

        for record in load_records(args.file):
            task = SubscriptionTask(
                url=record.get("url"),
                account=record.get("account"),
                password=record.get("password"),
                status=TaskStatus.PENDING,
                duration_seconds=0,
                executed_at=None,
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

    summary = f"导入完成：新增 {inserted} 条，跳过（主键/唯一冲突） {skipped} 条。"
    if cleared:
        summary += f" 预先清空 {cleared} 条旧记录。"
    print(summary)


if __name__ == "__main__":
    main()
