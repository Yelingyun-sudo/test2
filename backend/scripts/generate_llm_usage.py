#!/usr/bin/env python3
"""从 llm 目录的 response.md 文件中提取并汇总 Usage 数据，生成 llm_usage 字段。

扫描任务日志目录下的 llm/*_response.md 文件，提取每个文件中的 Usage JSON，
汇总后补充或更新到 task_summary.json 的 llm_usage 字段中。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

# 确保可以导入 api 包
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


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
  uv run python %(prog)s                    扫描所有任务并生成 llm_usage
  uv run python %(prog)s --dry-run          预览模式，不实际写入
  uv run python %(prog)s --force            覆盖已有的 llm_usage 数据
  uv run python %(prog)s --task-id task_xxx 只处理指定任务
""",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="预览模式，显示将生成的数据但不实际写入文件",
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
    parser.add_argument(
        "--task-id",
        type=str,
        help="只处理指定的任务 ID（例如：task_20251222_150413_q2ry）",
    )

    # 如果没有提供任何参数，显示帮助信息
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    return parser.parse_args()


def extract_usage_from_response(md_file: Path) -> dict[str, Any] | None:
    """从 response.md 文件中提取 Usage JSON。

    Args:
        md_file: response.md 文件路径

    Returns:
        dict | None: 提取的 usage 数据，失败返回 None
    """
    try:
        content = md_file.read_text(encoding="utf-8")

        # 使用正则表达式提取 ## Usage 下的 JSON 代码块
        # 匹配模式：## Usage\n\n```json\n{...}\n```
        pattern = r"## Usage\s*\n\s*```json\s*\n(.*?)\n```"
        match = re.search(pattern, content, re.DOTALL)

        if not match:
            return None

        json_str = match.group(1)
        usage_data = json.loads(json_str)

        return usage_data

    except json.JSONDecodeError as e:
        print(f"  ⚠️  JSON 解析失败: {md_file.name} - {e}")
        return None
    except Exception as e:
        print(f"  ⚠️  读取文件失败: {md_file.name} - {e}")
        return None


def aggregate_llm_usage(llm_dir: Path) -> dict[str, int] | None:
    """汇总 llm 目录下所有 response 文件的 usage 数据。

    Args:
        llm_dir: llm 目录路径

    Returns:
        dict | None: 汇总的 llm_usage 数据，失败返回 None
    """
    if not llm_dir.exists():
        return None

    response_files = sorted(llm_dir.glob("*_response.md"))
    if not response_files:
        return None

    total_input_tokens = 0
    total_output_tokens = 0
    total_tokens = 0
    total_cached_tokens = 0
    llm_turns = 0

    for response_file in response_files:
        usage = extract_usage_from_response(response_file)
        if usage is None:
            continue

        total_input_tokens += usage.get("input_tokens", 0)
        total_output_tokens += usage.get("output_tokens", 0)
        total_tokens += usage.get("total_tokens", 0)

        # 提取 cached_tokens
        input_details = usage.get("input_tokens_details", {})
        total_cached_tokens += input_details.get("cached_tokens", 0)

        llm_turns += 1

    if llm_turns == 0:
        return None

    return {
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "total_tokens": total_tokens,
        "llm_turns": llm_turns,
        "total_cached_tokens": total_cached_tokens,
    }


def process_task_directory(
    task_dir: Path, force: bool = False, dry_run: bool = False
) -> str:
    """处理单个任务目录，生成或更新 llm_usage。

    Args:
        task_dir: 任务目录路径
        force: 是否覆盖已有的 llm_usage
        dry_run: 是否为预览模式

    Returns:
        str: 处理结果状态 ("updated", "skipped_existing", "skipped_no_data", "skipped_no_summary")
    """
    task_id = task_dir.name
    llm_dir = task_dir / "llm"
    summary_file = task_dir / "task_summary.json"

    # 检查 task_summary.json 是否存在
    if not summary_file.exists():
        return "skipped_no_summary"

    # 读取现有的 task_summary.json
    try:
        with summary_file.open("r", encoding="utf-8") as f:
            summary_data = json.load(f)
    except Exception as e:
        print(f"  ⚠️  读取 task_summary.json 失败: {e}")
        return "skipped_no_summary"

    # 检查是否已有 llm_usage
    if summary_data.get("llm_usage") is not None and not force:
        return "skipped_existing"

    # 汇总 llm_usage
    llm_usage = aggregate_llm_usage(llm_dir)
    if llm_usage is None:
        return "skipped_no_data"

    print(f"\n处理 {task_id}:")
    print(f"  - 找到 {llm_usage['llm_turns']} 个 response 文件")
    print(
        f"  - 汇总: 输入={llm_usage['total_input_tokens']}, "
        f"输出={llm_usage['total_output_tokens']}, "
        f"总计={llm_usage['total_tokens']}, "
        f"缓存={llm_usage['total_cached_tokens']}"
    )

    if not dry_run:
        # 更新 summary_data
        summary_data["llm_usage"] = llm_usage

        # 写回文件（保持格式化）
        with summary_file.open("w", encoding="utf-8") as f:
            json.dump(summary_data, f, indent=2, ensure_ascii=False)
            f.write("\n")

        print(f"  ✓ 已写入 task_summary.json")
    else:
        print(f"  [预览] 将写入 task_summary.json")

    return "updated"


def main() -> None:
    """主函数：执行 llm_usage 生成逻辑。"""
    args = parse_args()

    print(f"开始扫描日志目录: {args.logs_dir}")

    # 获取任务目录列表
    if args.task_id:
        task_dirs = [args.logs_dir / args.task_id]
        if not task_dirs[0].exists():
            print(f"错误：任务目录不存在: {args.task_id}")
            sys.exit(1)
    else:
        task_dirs = sorted(
            [d for d in args.logs_dir.iterdir() if d.is_dir() and d.name.startswith("task_")]
        )

    print(f"找到 {len(task_dirs)} 个任务目录\n")

    if not task_dirs:
        print("没有找到任务目录，退出。")
        return

    # 统计信息
    stats = {
        "updated": 0,
        "skipped_existing": 0,
        "skipped_no_data": 0,
        "skipped_no_summary": 0,
    }

    if args.dry_run:
        print("⚠️  【预览模式】不会实际修改文件\n")

    # 处理每个任务目录
    for task_dir in task_dirs:
        result = process_task_directory(task_dir, force=args.force, dry_run=args.dry_run)
        stats[result] += 1

    # 输出统计结果
    print("\n" + "=" * 50)
    print("处理完成，统计结果：")
    print(f"  更新成功: {stats['updated']} 条")
    print(f"  跳过（已有值）: {stats['skipped_existing']} 条")
    print(f"  跳过（无 llm 数据）: {stats['skipped_no_data']} 条")
    print(f"  跳过（无 summary 文件）: {stats['skipped_no_summary']} 条")

    if args.dry_run:
        print("\n💡 这是预览模式，数据未实际写入文件")
        print("   去掉 --dry-run 参数可执行实际更新")

    if not args.force and stats["skipped_existing"] > 0:
        print("\n💡 部分任务已有 llm_usage 数据被跳过")
        print("   使用 --force 参数可覆盖已有数据")


if __name__ == "__main__":
    main()

