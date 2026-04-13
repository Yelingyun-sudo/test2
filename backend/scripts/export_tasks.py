"""导出任务数据到 jsonl 文件（支持订阅、注册取证、支付任务）"""
from __future__ import annotations

"""
# 导出 4 月 1 日的支付任务
  uv run python scripts/export_tasks.py --type payment --start-date 2026-04-01

  # 导出 4 月 1 日到 4 月 3 日的所有任务
  uv run python scripts/export_tasks.py --type all --start-date 2026-04-01 --end-date 2026-04-03

  # 只导出注册取证任务，日期范围 3 月 10-11 日
  uv run python scripts/export_tasks.py --type evidence --start-date 2026-03-10 --end-date 2026-03-11

"""
import argparse
import json
import sqlite3
from pathlib import Path


def export_tasks(
    db_path: str,
    output_dir: str,
    task_type: str,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, int]:
    """导出指定类型任务到 jsonl 文件

    Args:
        db_path: SQLite 数据库路径
        output_dir: 输出目录
        task_type: 任务类型，可选 all/subscription/evidence/payment
        start_date: 开始日期，格式 YYYY-MM-DD
        end_date: 结束日期，格式 YYYY-MM-DD

    Returns:
        各类型导出的记录数
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 处理日期参数：只传一天时 start_date 和 end_date 相同
    if start_date and not end_date:
        end_date = start_date
    if end_date and not start_date:
        start_date = end_date

    # 构建日期范围条件
    date_condition = ""
    params = []
    if start_date and end_date:
        date_condition = "WHERE created_date BETWEEN ? AND ?"
        params = [start_date, end_date]
    elif start_date:
        date_condition = "WHERE created_date = ?"
        params = [start_date]

    results = {}

    # 1. 导出订阅任务 -> subscription88.jsonl
    if task_type in ("all", "subscription"):
        cursor.execute(
            f"SELECT url, account, password FROM subscription_tasks {date_condition}",
            params,
        )
        rows = cursor.fetchall()
        subscription_count = 0
        output_file = Path(output_dir) / "subscription88.jsonl"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            for url, account, password in rows:
                record = {
                    "url": url,
                    "account": account,
                    "password": password,
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                subscription_count += 1
        results["subscription"] = subscription_count

    # 2. 导出注册取证任务 -> evidence88.jsonl（账户和密码为空）
    if task_type in ("all", "evidence"):
        cursor.execute(
            f"SELECT url FROM evidence_tasks {date_condition}",
            params,
        )
        rows = cursor.fetchall()
        evidence_count = 0
        output_file = Path(output_dir) / "evidence88.jsonl"
        with open(output_file, "w", encoding="utf-8") as f:
            for (url,) in rows:
                record = {
                    "url": url,
                    "account": "",
                    "password": "",
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                evidence_count += 1
        results["evidence"] = evidence_count

    # 3. 导出支付任务 -> payment88.jsonl
    if task_type in ("all", "payment"):
        cursor.execute(
            f"SELECT url, account, password FROM payment_tasks {date_condition}",
            params,
        )
        rows = cursor.fetchall()
        payment_count = 0
        output_file = Path(output_dir) / "payment88.jsonl"
        with open(output_file, "w", encoding="utf-8") as f:
            for url, account, password in rows:
                record = {
                    "url": url,
                    "account": account,
                    "password": password,
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                payment_count += 1
        results["payment"] = payment_count

    conn.close()
    return results


def main():
    parser = argparse.ArgumentParser(
        description="导出任务数据到 jsonl 文件（支持日期范围）"
    )
    parser.add_argument(
        "--db", default="db/waRunning.db", help="SQLite 数据库路径（相对于 backend）"
    )
    parser.add_argument(
        "--output",
        default="resources",
        help="输出目录（相对于 backend）",
    )
    parser.add_argument(
        "--type",
        default="all",
        choices=["all", "subscription", "evidence", "payment"],
        help="导出的任务类型：all/subscription/evidence/payment",
    )
    parser.add_argument(
        "--start-date",
        help="开始日期，格式 YYYY-MM-DD，如 2026-04-01",
    )
    parser.add_argument(
        "--end-date",
        help="结束日期，格式 YYYY-MM-DD，如 2026-04-03",
    )

    args = parser.parse_args()

    # 只传一个日期时，两者设为相同
    if args.start_date and not args.end_date:
        args.end_date = args.start_date
    if args.end_date and not args.start_date:
        args.start_date = args.end_date

    # 转换为绝对路径
    script_dir = Path(__file__).parent
    backend_dir = script_dir.parent
    db_path = backend_dir / args.db
    output_dir = backend_dir / args.output

    results = export_tasks(
        db_path=str(db_path),
        output_dir=str(output_dir),
        task_type=args.type,
        start_date=args.start_date,
        end_date=args.end_date,
    )

    print(f"导出完成：")
    for key, count in results.items():
        print(f"  - {key}88.jsonl: {count} 条")


if __name__ == "__main__":
    main()