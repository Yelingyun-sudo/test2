"""任务执行结果的格式化输出模块。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from website_analytics.orchestrator import ExecutionResult


def format_execution_result(result: ExecutionResult) -> str:
    output = result.coordinator_output or {}
    status_raw = output.get("status") or ("success" if result.success else "failed")
    status = str(status_raw).lower()
    message = output.get("message") or "无输出信息"

    lines: list[str] = [
        f"任务状态: {status}",
        f"提示: {message}",
    ]

    operations: list[str] = output.get("operations_executed") or []
    if operations:
        operations_display = " -> ".join(operations)
        lines.append(f"执行操作: {operations_display}")
    else:
        lines.append("执行操作: 未记录")

    results: dict[str, Any] = output.get("operations_results") or {}
    if results:
        lines.append("操作详情:")
        for name in operations if operations else sorted(results.keys()):
            detail_lines = _format_operation_result(name, results.get(name))
            lines.extend(detail_lines)

    if result.task_dir:
        summary_path = result.task_dir / "task_summary.json"
        lines.append(f"任务目录: {result.task_dir}")
        lines.append(f"任务总结: {summary_path}")

    return "\n".join(lines)


def _format_operation_result(name: str, payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return [f"- {name}: 未提供结构化结果"]

    lines = [f"- {name}:"]
    handled_keys: set[str] = set()

    if "success" in payload:
        success = payload.get("success")
        lines.append(f"  结果: {'成功' if success else '失败'}")
        handled_keys.add("success")

    message = payload.get("message")
    if message:
        lines.append(f"  提示: {message}")
        handled_keys.add("message")

    if name == "extract":
        subscription_key = "subscription_url"
        subscription_url = payload.get(subscription_key)
        if subscription_url:
            lines.append(f"  订阅地址: {subscription_url}")
            handled_keys.add(subscription_key)
    elif name == "evidence":
        entries_keys = (
            "entries_total",
            "entries_success",
            "entries_failed",
            "report_file",
        )
        for entry_key in entries_keys:
            if entry_key in payload and payload.get(entry_key) not in (None, ""):
                label = {
                    "entries_total": "入口总数",
                    "entries_success": "成功入口",
                    "entries_failed": "失败入口",
                    "report_file": "取证报告",
                }[entry_key]
                lines.append(f"  {label}: {payload.get(entry_key)}")
                handled_keys.add(entry_key)

    for key in payload:
        if key in handled_keys:
            continue
        lines.append(f"  {key}: {payload.get(key)}")

    return lines
