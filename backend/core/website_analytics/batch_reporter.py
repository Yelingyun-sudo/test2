"""批次任务执行报告生成模块。"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class TaskResult:
    """单个任务的执行结果。"""

    task_id: str
    index: int
    instruction: str
    duration_seconds: float
    task_dir: str
    coordinator_output: dict[str, Any] | None
    exit_code: int
    start_time: str
    end_time: str
    llm_usage: dict[str, int] | None = None

    @property
    def message(self) -> str:
        """安全提取用户消息。"""
        if self.coordinator_output and "message" in self.coordinator_output:
            return self.coordinator_output["message"]
        return "无输出信息"

    @property
    def status(self) -> str:
        """从协调器输出推导任务状态，默认为 exit_code 判定。"""
        try:
            if self.coordinator_output and "status" in self.coordinator_output:
                return str(self.coordinator_output.get("status")).lower()
        except Exception:
            pass

        if self.exit_code == 0:
            return "success"
        if self.exit_code:
            return "failed"
        return "unknown"


@dataclass
class TaskReference:
    """批次报告中的任务引用。"""

    task_dir: str
    task_summary_file: str
    status: str


@dataclass
class BatchReport:
    """批次任务执行报告。"""

    batch_id: str
    start_time: str
    end_time: str
    total_duration_seconds: float
    total: int
    success: int
    failed: int
    tasks: list[TaskResult]


def save_task_summary(task: TaskResult, task_dir: Path) -> None:
    """保存单个任务的总结文件。

    Args:
        task: 任务执行结果
        task_dir: 任务目录路径
    """
    summary_path = task_dir / "task_summary.json"
    task_dict = asdict(task)
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(task_dict, f, ensure_ascii=False, indent=2)


def generate_batch_report(
    batch_id: str,
    batch_dir: Path,
    tasks: list[TaskResult],
    start_time: datetime,
    end_time: datetime,
) -> None:
    """生成批次任务执行报告（Markdown 和 JSON 格式）。

    Args:
        batch_id: 批次任务 ID
        batch_dir: 批次任务目录
        tasks: 任务结果列表
        start_time: 批次开始时间
        end_time: 批次结束时间
    """
    # 注意：每个任务的 task_summary.json 已经在任务完成时保存
    # 这里只需要生成批次级别的汇总报告

    total_duration = (end_time - start_time).total_seconds()
    success_count = sum(1 for task in tasks if task.status == "success")
    failed_count = len(tasks) - success_count

    # 生成 JSON 报告（引用模式）
    json_path = batch_dir / "summary.json"
    task_references = [
        TaskReference(
            task_dir=task.task_dir,
            task_summary_file=f"{task.task_dir}/task_summary.json",
            status=task.status,
        )
        for task in tasks
    ]
    batch_json_report = {
        "batch_id": batch_id,
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "total_duration_seconds": total_duration,
        "summary": {
            "total": len(tasks),
            "success": success_count,
            "failed": failed_count,
        },
        "tasks": [asdict(ref) for ref in task_references],
    }
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(batch_json_report, f, ensure_ascii=False, indent=2)

    # 生成 Markdown 报告（详细信息）
    report = BatchReport(
        batch_id=batch_id,
        start_time=start_time.isoformat(),
        end_time=end_time.isoformat(),
        total_duration_seconds=total_duration,
        total=len(tasks),
        success=success_count,
        failed=failed_count,
        tasks=tasks,
    )
    md_path = batch_dir / "summary.md"
    md_content = _generate_markdown_report(report)
    md_path.write_text(md_content, encoding="utf-8")


def _generate_markdown_report(report: BatchReport) -> str:
    """生成 Markdown 格式的报告内容。"""
    lines = [
        "# 批次任务执行报告",
        "",
        f"**批次 ID**: {report.batch_id}",
        f"**开始时间**: {report.start_time}",
        f"**结束时间**: {report.end_time}",
        f"**总任务数**: {report.total}",
        f"**成功**: {report.success}",
        f"**失败**: {report.failed}",
        f"**总耗时**: {_format_duration(report.total_duration_seconds)}",
        "",
        "---",
        "",
        "## 任务详情",
        "",
    ]

    for task in report.tasks:
        status_icon = "✅" if task.status == "success" else "❌"
        task_dir_path = Path(task.task_dir) if task.task_dir else None
        detail_dir_display = f"`{task_dir_path.name}`" if task_dir_path else "未记录"
        log_dir_display = task.task_dir if task.task_dir else "未记录"

        lines.extend(
            [
                f"### {status_icon} 任务 {task.index}: {task.instruction}",
                f"- **状态**: {task.status}",
                f"- **开始时间**: {task.start_time}",
                f"- **结束时间**: {task.end_time}",
                f"- **耗时**: {_format_duration(task.duration_seconds)}",
                f"- **详情文件夹**: {detail_dir_display}",
                f"- **日志目录**: {log_dir_display}",
                f"- **退出码**: {task.exit_code}",
            ]
        )

        # 显示消息和结构化信息
        if task.coordinator_output:
            message = task.message
            if message:
                output_preview = (
                    message[:200] + "..." if len(message) > 200 else message
                )
                lines.append(f"- **输出**: {output_preview}")

            # 显示执行的操作
            operations = task.coordinator_output.get("operations_executed", [])
            if operations:
                lines.append(f"- **执行操作**: {', '.join(operations)}")

        lines.append("")

    return "\n".join(lines)


def _format_duration(seconds: float) -> str:
    """格式化时长显示。"""
    if seconds < 60:
        return f"{seconds:.1f}秒"
    minutes = int(seconds // 60)
    remaining_seconds = int(seconds % 60)
    if minutes < 60:
        return f"{minutes}分{remaining_seconds}秒"
    hours = minutes // 60
    remaining_minutes = minutes % 60
    return f"{hours}小时{remaining_minutes}分{remaining_seconds}秒"


def print_task_start(index: int, instruction: str) -> None:
    """打印任务启动信息。"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    preview = instruction[:80] + "..." if len(instruction) > 80 else instruction
    print(f"[{timestamp}] 任务 {index} 启动: {preview}")


def print_task_complete(index: int, status: str, duration: float) -> None:
    """打印任务完成信息。"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    status_icon = "✅" if status == "success" else "❌"
    print(
        f"[{timestamp}] {status_icon} 任务 {index} {status} (耗时: {_format_duration(duration)})"
    )


def print_batch_summary(
    total: int,
    success: int,
    failed: int,
    duration: float,
    summary_path: Path,
) -> None:
    """打印批次任务汇总信息。"""
    print()
    print("=" * 60)
    print("批次任务执行完成！")
    print(
        f"成功: {success}/{total}, 失败: {failed}/{total}, 总耗时: {_format_duration(duration)}"
    )
    print(f"汇总报告已保存至: {summary_path}")
    print("=" * 60)
