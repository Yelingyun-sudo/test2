#!/usr/bin/env python3
"""将 task_summary.json 中的 llm_usage 数据同步到 subscription_tasks 表。

从日志目录扫描所有任务的 task_summary.json 文件，提取 llm_usage 字段，
并根据 task_dir 匹配更新到数据库的 subscription_tasks 表中。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# 确保可以导入 api 包
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from api.app.db import SessionLocal, init_db  # noqa: E402
from api.app.models import SubscriptionTask  # noqa: E402


def parse_args() -> argparse.Namespace:
    """解析命令行参数。

    Returns:
        argparse.Namespace: 解析后的命令行参数
    """
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
示例:
  uv run python %(prog)s                    扫描默认日志目录并更新
  uv run python %(prog)s --dry-run          预览模式，不实际更新
  uv run python %(prog)s --force            覆盖已有的 llm_usage 数据
  uv run python %(prog)s --logs-dir /path   指定日志目录
""",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="预览模式，显示将要更新的记录但不实际执行",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="覆盖已有的 llm_usage 数据（默认跳过已有值的记录）",
    )
    parser.add_argument(
        "--logs-dir",
        type=Path,
        default=ROOT / "logs",
        help="日志目录路径（默认: backend/logs）",
    )
    
    # 如果没有提供任何参数，显示帮助信息
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)
    
    return parser.parse_args()


def scan_task_summaries(logs_dir: Path) -> list[dict[str, Any]]:
    """扫描日志目录下所有 task_summary.json 文件。

    Args:
        logs_dir: 日志目录路径

    Returns:
        list[dict]: 包含 task_dir 和 llm_usage 的字典列表
    """
    if not logs_dir.exists():
        print(f"日志目录不存在: {logs_dir}")
        return []

    results = []
    task_dirs = sorted([d for d in logs_dir.iterdir() if d.is_dir() and d.name.startswith("task_")])

    for task_dir in task_dirs:
        summary_file = task_dir / "task_summary.json"
        if not summary_file.exists():
            continue

        try:
            with summary_file.open("r", encoding="utf-8") as f:
                data = json.load(f)

            # 提取 task_dir 和 llm_usage
            task_dir_value = data.get("task_dir")
            llm_usage = data.get("llm_usage")

            if not task_dir_value:
                print(f"⚠️  跳过（缺少 task_dir 字段）: {summary_file}")
                continue

            if not llm_usage:
                # 按用户选择：跳过没有 llm_usage 的记录
                continue

            results.append({
                "task_dir": task_dir_value,
                "llm_usage": llm_usage,
                "summary_file": str(summary_file),
            })

        except json.JSONDecodeError as e:
            print(f"⚠️  JSON 解析失败: {summary_file} - {e}")
            continue
        except Exception as e:
            print(f"⚠️  读取文件失败: {summary_file} - {e}")
            continue

    return results


def sync_llm_usage(
    session: Any,
    task_summaries: list[dict[str, Any]],
    force: bool = False,
    dry_run: bool = False,
) -> dict[str, int]:
    """将 llm_usage 数据同步到数据库。

    Args:
        session: SQLAlchemy 会话对象
        task_summaries: 任务摘要数据列表
        force: 是否覆盖已有的 llm_usage 数据
        dry_run: 是否为预览模式

    Returns:
        dict: 统计信息，包含 updated、skipped_existing、skipped_no_match 等计数
    """
    stats = {
        "updated": 0,
        "skipped_existing": 0,
        "skipped_no_match": 0,
    }

    for item in task_summaries:
        task_dir = item["task_dir"]
        llm_usage = item["llm_usage"]

        # 查询数据库中匹配的记录
        task = session.query(SubscriptionTask).filter(
            SubscriptionTask.task_dir == task_dir
        ).first()

        if not task:
            stats["skipped_no_match"] += 1
            continue

        # 检查是否已有 llm_usage 数据
        if task.llm_usage is not None and not force:
            stats["skipped_existing"] += 1
            continue

        # 更新数据
        if not dry_run:
            task.llm_usage = llm_usage
            stats["updated"] += 1
        else:
            # dry-run 模式：只统计，不实际更新
            stats["updated"] += 1
            print(f"  [预览] 将更新: task_dir={task_dir}")
            print(f"         Token 统计: 输入={llm_usage.get('total_input_tokens', 0)}, "
                  f"输出={llm_usage.get('total_output_tokens', 0)}, "
                  f"总计={llm_usage.get('total_tokens', 0)}")

    if not dry_run and stats["updated"] > 0:
        session.commit()

    return stats


def main() -> None:
    """主函数：执行 llm_usage 同步逻辑。"""
    args = parse_args()

    print(f"开始扫描日志目录: {args.logs_dir}")

    # 扫描日志目录
    task_summaries = scan_task_summaries(args.logs_dir)
    print(f"找到 {len(task_summaries)} 个有效任务摘要文件")

    if not task_summaries:
        print("没有找到可更新的数据，退出。")
        return

    # 初始化数据库
    init_db()
    session = SessionLocal()

    try:
        # 执行同步
        if args.dry_run:
            print("\n⚠️  【预览模式】不会实际修改数据库\n")

        stats = sync_llm_usage(
            session=session,
            task_summaries=task_summaries,
            force=args.force,
            dry_run=args.dry_run,
        )

        # 输出统计结果
        print("\n" + "=" * 50)
        print("同步完成，统计结果：")
        print(f"  更新成功: {stats['updated']} 条")
        print(f"  跳过（已有值）: {stats['skipped_existing']} 条")
        print(f"  跳过（无匹配）: {stats['skipped_no_match']} 条")

        if args.dry_run:
            print("\n💡 这是预览模式，数据未实际写入数据库")
            print("   去掉 --dry-run 参数可执行实际更新")

        if not args.force and stats['skipped_existing'] > 0:
            print("\n💡 部分记录已有 llm_usage 数据被跳过")
            print("   使用 --force 参数可覆盖已有数据")

    finally:
        session.close()


if __name__ == "__main__":
    main()

