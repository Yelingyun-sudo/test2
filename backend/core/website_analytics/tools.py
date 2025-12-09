from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from agents import Tool, function_tool


def build_save_page_text_tool(task_dir: Path) -> Tool:
    inspect_dir = task_dir / "inspect"
    inspect_dir.mkdir(parents=True, exist_ok=True)

    @function_tool(
        name_override="save_page_text",
        description_override=(
            "将文本内容写入根据文件名生成的 `.txt` 文件（从文件名提取前缀，扩展名为 `.txt`）。"
        ),
    )
    def save_page_text(filename: str, content: str) -> str:
        base_name = Path(filename).name.strip()
        if not base_name:
            raise ValueError("filename 不能为空。")

        stem = base_name.rsplit(".", 1)[0] if "." in base_name else base_name
        target_path = inspect_dir / f"{stem}.txt"
        try:
            target_path.write_text(content, encoding="utf-8")
        except OSError as exc:  # pragma: no cover - IO errors are surfaced to the agent
            raise ValueError(f"写入失败：{exc}") from exc

        try:
            relative_path = target_path.relative_to(task_dir)
        except ValueError:
            relative_path = target_path
        return f"文本已保存到 {relative_path}"

    return save_page_text


def build_save_entry_result_tool(task_dir: Path) -> Tool:
    inspect_dir = task_dir / "inspect"
    inspect_dir.mkdir(parents=True, exist_ok=True)

    @function_tool(
        name_override="save_entry_result",
        description_override="将单个入口的巡检结果写入与文本/截图同名前缀的 `.json` 文件。",
    )
    def save_entry_result(filename: str, result_json: str) -> str:
        base_name = Path(filename).name.strip()
        if not base_name:
            raise ValueError("filename 不能为空。")

        stem = base_name.rsplit(".", 1)[0] if "." in base_name else base_name
        target_path = inspect_dir / f"{stem}.json"

        try:
            parsed = json.loads(result_json)
        except json.JSONDecodeError as exc:
            raise ValueError(f"result_json 不是有效的 JSON：{exc}") from exc

        try:
            serialized = json.dumps(parsed, ensure_ascii=False, indent=2)
            target_path.write_text(serialized, encoding="utf-8")
        except OSError as exc:  # pragma: no cover - IO errors are surfaced to the agent
            raise ValueError(f"写入失败：{exc}") from exc

        try:
            relative_path = target_path.relative_to(task_dir)
        except ValueError:
            relative_path = target_path
        return f"结果已保存到 {relative_path}"

    return save_entry_result


def build_compile_inspect_report_tool(task_dir: Path) -> Tool:
    inspect_dir = task_dir / "inspect"

    @function_tool(
        name_override="compile_inspect_report",
        description_override="读取巡检入口 JSON 结果并生成 Markdown 报告与统计信息。",
    )
    def compile_inspect_report(
        output_filename: str | None = None,
    ) -> str:
        if not inspect_dir.exists():
            raise ValueError("inspect 目录不存在，无法生成巡检报告。")

        json_files = sorted(
            path
            for path in inspect_dir.glob("*.json")
            if path.is_file() and path.name != "report.json"
        )
        if not json_files:
            raise ValueError("inspect 目录中未找到任何入口 JSON 结果，无法生成报告。")

        entry_list_path = inspect_dir / "inspectEntryList.txt"
        menu_names: list[str] = []
        notes: list[str] = []
        if entry_list_path.exists():
            raw_lines = entry_list_path.read_text(encoding="utf-8").splitlines()
            for line in raw_lines:
                cleaned = line.strip().strip('"').strip()
                if cleaned:
                    menu_names.append(cleaned)
        else:
            notes.append("缺少 inspectEntryList.txt，已按文件名前缀推断入口名称。")

        if output_filename:
            candidate = Path(output_filename.strip())
            target_path = candidate if candidate.is_absolute() else task_dir / candidate
        else:
            target_path = inspect_dir / "report.md"

        if not target_path.suffix:
            target_path = target_path.with_suffix(".md")
        elif target_path.suffix.lower() != ".md":
            target_path = target_path.with_suffix(".md")

        target_path.parent.mkdir(parents=True, exist_ok=True)
        report_parent = target_path.parent

        def _to_posix_relative(path: Path) -> str:
            try:
                rel_path = path.relative_to(report_parent)
                return rel_path.as_posix()
            except ValueError:
                return Path(os.path.relpath(path, report_parent)).as_posix()

        def _safe_escape_markdown(text: str) -> str:
            return text.replace("|", r"\|").replace("\n", "<br>")

        def _derive_label(json_path: Path, entry_idx: int | None) -> str:
            if entry_idx and 1 <= entry_idx <= len(menu_names):
                return menu_names[entry_idx - 1]
            stem = json_path.stem
            if "_" in stem:
                return stem.split("_", 1)[1].replace("_", " ")
            return stem

        compiled_records: list[dict[str, Any]] = []
        failed_entries: list[dict[str, str]] = []

        entry_id_pattern = re.compile(r"^(\d+)_")
        for json_path in json_files:
            try:
                data = json.loads(json_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                failed_entries.append(
                    {
                        "entry_id": json_path.stem,
                        "reason": f"JSON 解码失败：{exc}",
                    }
                )
                continue

            entry_id = data.get("entry_id") or json_path.stem
            status = data.get("status", "unknown")
            summary = data.get("summary")
            error = data.get("error")
            screenshot_field = data.get("screenshot")
            text_field = data.get("text_snapshot")

            match = entry_id_pattern.match(json_path.name)
            entry_idx = int(match.group(1)) if match else None
            label = _derive_label(json_path, entry_idx)

            screenshot_path = None
            screenshot_exists = False
            if isinstance(screenshot_field, str) and screenshot_field:
                screenshot_path = (
                    Path(screenshot_field)
                    if Path(screenshot_field).is_absolute()
                    else task_dir / screenshot_field
                )
                screenshot_exists = screenshot_path.exists()

            text_path = None
            text_exists = False
            if isinstance(text_field, str) and text_field:
                text_path = (
                    Path(text_field)
                    if Path(text_field).is_absolute()
                    else task_dir / text_field
                )
                text_exists = text_path.exists()

            json_rel = _to_posix_relative(json_path)
            screenshot_rel = (
                _to_posix_relative(screenshot_path)
                if screenshot_exists and screenshot_path
                else "-"
            )
            text_rel = (
                _to_posix_relative(text_path) if text_exists and text_path else "-"
            )

            status_normalized = str(status).lower()
            detail_for_table = (
                summary
                if status_normalized == "success"
                else error or summary or "无可用信息"
            )
            detail_for_table = (
                _safe_escape_markdown(detail_for_table)
                if isinstance(detail_for_table, str)
                else "-"
            )

            record = {
                "entry_id": entry_id,
                "label": label,
                "status": status,
                "summary": summary,
                "error": error,
                "screenshot_rel": screenshot_rel,
                "screenshot_exists": screenshot_exists,
                "text_rel": text_rel,
                "text_exists": text_exists,
                "json_rel": json_rel,
                "detail_for_table": detail_for_table,
            }

            missing_reasons: list[str] = []
            if status_normalized != "success":
                missing_reasons.append(error or "入口状态非 success。")
            if screenshot_field and not screenshot_exists:
                missing_reasons.append(f"缺少截图：{screenshot_field}")
            if text_field and not text_exists:
                missing_reasons.append(f"缺少文本快照：{text_field}")

            if missing_reasons:
                failed_entries.append(
                    {
                        "entry_id": entry_id,
                        "reason": "；".join(missing_reasons),
                    }
                )

            compiled_records.append(record)

        if not compiled_records:
            raise ValueError("所有入口 JSON 文件解析失败，无法生成巡检报告。")

        compiled_records.sort(key=lambda item: item["entry_id"])

        entry_count = len(compiled_records)
        success_count = sum(
            1
            for record in compiled_records
            if str(record["status"]).lower() == "success"
        )
        failure_count = entry_count - success_count

        now = datetime.now(UTC).astimezone(timezone(timedelta(hours=8)))

        header_lines = [
            "# 巡检结果报告",
            "",
            f"- 生成时间（UTC+8）：{now.strftime('%Y-%m-%d %H:%M:%S')}",
        ]
        header_lines.extend(
            [
                f"- 任务目录：{task_dir.name}",
                f"- 巡检入口总数：{entry_count}",
                f"- 成功入口数：{success_count}",
                f"- 失败或缺资源入口数：{failure_count}",
            ]
        )
        if notes:
            header_lines.append(f"- 备注：{'；'.join(notes)}")
        header_lines.append("")

        table_lines = [
            "| entry_id | 名称 | 状态 | 摘要/错误 |",
            "| --- | --- | --- | --- |",
        ]
        for record in compiled_records:
            row = (
                f"| {record['entry_id']} | "
                f"{_safe_escape_markdown(record['label'])} | "
                f"{record['status']} | "
                f"{record['detail_for_table']} |"
            )
            table_lines.append(row)
        table_lines.append("")

        detail_lines = []
        for record in compiled_records:
            detail_lines.append(f"## {record['entry_id']} {record['label']}")
            detail_lines.append("")
            if record["screenshot_rel"] != "-":
                detail_lines.append(
                    f"![{record['label']} 页面截图]({record['screenshot_rel']})"
                )
                detail_lines.append("")
            detail_lines.append(f"- 状态：{record['status']}")
            if record["error"]:
                detail_lines.append(f"- 错误信息：{record['error']}")
            if record["summary"]:
                detail_lines.append(f"- 摘要：{record['summary']}")
            detail_lines.append(f"- JSON：[{record['json_rel']}]({record['json_rel']})")
            if record["screenshot_rel"] != "-":
                detail_lines.append(
                    f"- 截图：[{record['screenshot_rel']}]({record['screenshot_rel']})"
                )
            else:
                detail_lines.append("- 截图：未生成")
            if record["text_rel"] != "-":
                detail_lines.append(f"- 文本：{record['text_rel']}")
            else:
                detail_lines.append("- 文本：未生成")
            detail_lines.append("")

        appendix_lines = ["## 附录", ""]
        appendix_lines.append("### 处理文件清单")
        appendix_lines.append("")
        for json_path in json_files:
            appendix_lines.append(f"- {json_path.relative_to(task_dir).as_posix()}")
        appendix_lines.append("")
        if failed_entries:
            appendix_lines.append("### 异常入口")
            appendix_lines.append("")
            for item in failed_entries:
                appendix_lines.append(f"- {item['entry_id']}: {item['reason']}")
            appendix_lines.append("")

        markdown_content = "\n".join(
            [*header_lines, *table_lines, *detail_lines, *appendix_lines]
        )

        target_path.write_text(markdown_content, encoding="utf-8")

        try:
            report_relative = target_path.relative_to(task_dir).as_posix()
        except ValueError:
            report_relative = target_path.as_posix()

        result_payload: dict[str, Any] = {
            "status": "success",
            "report_file": report_relative,
            "entry_count": entry_count,
            "success_count": success_count,
            "failed_entries": failed_entries,
        }
        if notes:
            result_payload["notes"] = notes

        return json.dumps(result_payload, ensure_ascii=False, indent=2)

    return compile_inspect_report


__all__ = [
    "build_save_page_text_tool",
    "build_save_entry_result_tool",
    "build_compile_inspect_report_tool",
]
