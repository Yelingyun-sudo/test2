#!/usr/bin/env python3
"""将 JSONL 文件导入 evidence_tasks 表。"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.exc import IntegrityError

# 确保可以导入 api 包
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from api.app.db import SessionLocal, init_db  # noqa: E402
from api.app.models import EvidenceTask  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
示例:
  uv run python %(prog)s resources/evidence.jsonl
  uv run python %(prog)s resources/evidence.jsonl --clear
""",
    )
    parser.add_argument(
        "file_path",
        type=Path,
        help="要导入的 JSONL 文件路径",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="导入前清空 evidence_tasks 表",
    )

    # 如果没有提供任何参数，显示帮助信息
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    return parser.parse_args()


def load_records(file_path: Path):
    """从 JSONL 文件中加载记录。

    Args:
        file_path: JSONL 文件路径

    Yields:
        dict: 解析后的 JSON 对象
    """
    if not file_path.exists():
        raise SystemExit(f"数据文件不存在: {file_path}")

    with file_path.open("r", encoding="utf-8") as f:
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

    inserted = 0
    skipped = 0
    cleared = 0

    try:
        if args.clear:
            cleared = (
                session.query(EvidenceTask)
                .delete(synchronize_session=False)  # type: ignore[arg-type]
            )
            session.commit()
            print(f"已清空 evidence_tasks 表：删除 {cleared} 条记录。")

        for record in load_records(args.file_path):
            url = record.get("url")
            if not url:
                continue
            task = EvidenceTask(url=url, created_at=now)
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

