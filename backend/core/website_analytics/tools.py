from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from agents import Tool, function_tool


def build_save_page_text_tool(task_dir: Path) -> Tool:
    evidence_dir = task_dir / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)

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
        target_path = evidence_dir / f"{stem}.txt"
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
    evidence_dir = task_dir / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    @function_tool(
        name_override="save_entry_result",
        description_override="将单个入口的取证结果写入与文本/截图同名前缀的 `.json` 文件。",
    )
    def save_entry_result(filename: str, result_json: str) -> str:
        base_name = Path(filename).name.strip()
        if not base_name:
            raise ValueError("filename 不能为空。")

        stem = base_name.rsplit(".", 1)[0] if "." in base_name else base_name
        target_path = evidence_dir / f"{stem}.json"

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


def build_compile_evidence_report_tool(task_dir: Path) -> Tool:
    evidence_dir = task_dir / "evidence"

    @function_tool(
        name_override="compile_evidence_report",
        description_override="读取取证入口 JSON 结果并生成 Markdown 报告与统计信息。",
    )
    def compile_evidence_report(
        output_filename: str | None = None,
    ) -> str:
        if not evidence_dir.exists():
            raise ValueError("evidence 目录不存在，无法生成取证报告。")

        json_files = sorted(
            path
            for path in evidence_dir.glob("*.json")
            if path.is_file() and path.name != "report.json"
        )
        if not json_files:
            raise ValueError("evidence 目录中未找到任何入口 JSON 结果，无法生成报告。")

        entry_list_path = evidence_dir / "evidenceEntryList.txt"
        menu_names: list[str] = []
        notes: list[str] = []
        if entry_list_path.exists():
            raw_lines = entry_list_path.read_text(encoding="utf-8").splitlines()
            for line in raw_lines:
                cleaned = line.strip().strip('"').strip()
                if cleaned:
                    menu_names.append(cleaned)
        else:
            notes.append("缺少 evidenceEntryList.txt，已按文件名前缀推断入口名称。")

        if output_filename:
            candidate = Path(output_filename.strip())
            target_path = candidate if candidate.is_absolute() else task_dir / candidate
        else:
            target_path = evidence_dir / "report.md"

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

            record = {
                "entry_id": entry_id,
                "label": label,
                "status": status,
                "error": error,
                "screenshot_rel": screenshot_rel,
                "screenshot_exists": screenshot_exists,
                "text_rel": text_rel,
                "text_exists": text_exists,
                "json_rel": json_rel,
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
            raise ValueError("所有入口 JSON 文件解析失败，无法生成取证报告。")

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
            "# 取证结果报告",
            "",
            f"- 生成时间（UTC+8）：{now.strftime('%Y-%m-%d %H:%M:%S')}",
        ]
        header_lines.extend(
            [
                f"- 任务目录：{task_dir.name}",
                f"- 取证入口总数：{entry_count}",
                f"- 成功入口数：{success_count}",
                f"- 失败或缺资源入口数：{failure_count}",
            ]
        )
        if notes:
            header_lines.append(f"- 备注：{'；'.join(notes)}")
        header_lines.append("")

        table_lines = [
            "| entry_id | 名称 | 状态 | 截图 | 文本快照 |",
            "| --- | --- | --- | --- | --- |",
        ]
        for record in compiled_records:
            screenshot_link = (
                f"[查看]({record['screenshot_rel']})"
                if record["screenshot_rel"] != "-"
                else "-"
            )
            text_link = (
                f"[查看]({record['text_rel']})" if record["text_rel"] != "-" else "-"
            )
            row = (
                f"| {record['entry_id']} | "
                f"{_safe_escape_markdown(record['label'])} | "
                f"{record['status']} | "
                f"{screenshot_link} | "
                f"{text_link} |"
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
            "entries_total": entry_count,
            "entries_success": success_count,
            "entries_failed": failure_count,
        }
        if notes:
            result_payload["notes"] = notes
        if failed_entries:
            result_payload["failed_entries"] = failed_entries

        return json.dumps(result_payload, ensure_ascii=False, indent=2)

    return compile_evidence_report


def build_capture_and_save_tool(task_dir: Path) -> Tool:
    """创建数据采集与保存复合工具。

    合并原 Turn 6-7 的操作：
    - save_page_text（保存文本）
    - save_entry_result（保存 JSON）
    """
    evidence_dir = task_dir / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    @function_tool(
        name_override="capture_and_save",
        description_override=(
            "一次性完成数据保存：将页面文本和取证结果保存到文件。"
            "接受 entry_index, entry_label, text_content, screenshot_path 参数，"
            "生成 .txt 和 .json 文件。"
        ),
    )
    def capture_and_save(
        entry_id: str,
        entry_index: int,
        entry_label: str,
        text_content: str,
        screenshot_path: str,
    ) -> str:
        """保存文本快照和取证结果。

        Args:
            entry_id: 入口唯一标识
            entry_index: 入口序号（1-based）
            entry_label: 菜单标签
            text_content: 页面文本内容（来自 browser_evaluate）
            screenshot_path: 截图文件路径（来自 browser_take_screenshot）

        Returns:
            JSON 字符串，包含保存路径和结果
        """
        # 文件名安全处理
        safe_label = (
            entry_label.strip()
            .replace(" ", "_")
            .translate(str.maketrans("", "", r'/\:*?"<>|'))
        )
        prefix = f"{entry_index:02d}_{safe_label}"

        # 清理 Playwright 调试输出（### Result\n"..."）
        clean_text = text_content
        if clean_text.startswith('### Result\n"') and clean_text.endswith('"'):
            # 去除 ### Result\n" 前缀和尾部的 "
            clean_text = clean_text[14:-1]
        elif clean_text.startswith("### Result\n"):
            # 去除 ### Result\n 前缀
            clean_text = clean_text[12:]

        # 保存文本
        text_path = evidence_dir / f"{prefix}.txt"
        text_path.write_text(clean_text, encoding="utf-8")

        # 保存 JSON 结果
        result_data = {
            "entry_id": entry_id,
            "status": "success",
            "screenshot": screenshot_path,
            "text_snapshot": f"evidence/{prefix}.txt",
            "error": None,
        }
        json_path = evidence_dir / f"{prefix}.json"
        json_path.write_text(
            json.dumps(result_data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        try:
            rel_text = text_path.relative_to(task_dir)
            rel_json = json_path.relative_to(task_dir)
        except ValueError:
            rel_text = text_path
            rel_json = json_path

        return json.dumps(
            {
                "text_saved": str(rel_text),
                "json_saved": str(rel_json),
                "result": result_data,
            },
            ensure_ascii=False,
        )

    return capture_and_save


def _find_ref_by_label(snapshot_text: str, label: str) -> str | None:
    """从快照文本中查找匹配标签的 ref。

    Playwright MCP 的快照格式：
    - link "套餐商店" [ref=e37] [cursor=pointer]:
    - generic [ref=e39]: 套餐商店

    Args:
        snapshot_text: browser_snapshot 返回的文本内容
        label: 要查找的菜单标签

    Returns:
        匹配的 ref ID，如果未找到则返回 None
    """
    # 精确匹配：link "label" [ref=eXXX] 或 generic [ref=eXXX]: label
    # Pattern 1: link "套餐商店" [ref=e37]
    pattern = rf'"{re.escape(label)}"\s+\[ref=(e\d+)\]'
    match = re.search(pattern, snapshot_text)
    if match:
        return match.group(1)

    # Pattern 2: [ref=e39]: 套餐商店
    pattern = rf"\[ref=(e\d+)\]:\s*{re.escape(label)}"
    match = re.search(pattern, snapshot_text)
    if match:
        return match.group(1)

    # 模糊匹配：label 包含在文本中
    pattern = rf"\[ref=(e\d+)\][^\n]*{re.escape(label)}"
    match = re.search(pattern, snapshot_text, re.IGNORECASE)
    if match:
        return match.group(1)

    return None


def build_programmatic_evidence_entry_tool(
    task_dir: Path,
    playwright_server: Any,
) -> Tool:
    """创建完全程序化的单入口取证工具（异步版本）。

    将 8 轮 LLM 调用减少到 1 轮，直接在工具内部调用浏览器操作。
    使用异步函数直接 await playwright_server.call_tool()，无需 event loop 桥接。

    Args:
        task_dir: 任务目录
        playwright_server: AutoSwitchingPlaywrightServer 实例

    Returns:
        程序化取证工具
    """
    evidence_dir = task_dir / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    async def _wait_for_page_ready(target_label: str) -> None:
        """等待页面加载完成（最多等待 4 秒）

        Args:
            target_label: 目标菜单标签，用于验证页面内容是否符合预期

        等待策略：
        1. 每秒检查一次 DOM
        2. 检查三个条件：
           a) 目标菜单项仍然存在（说明导航栏已加载）
           b) DOM 元素数量充足（页面不是空白）
           c) DOM 稳定（连续2次 ref 数量相同）
        3. 所有条件都满足时才认为加载完成
        4. 超时后也直接返回（不报错）
        """
        max_wait_seconds = 4
        stable_count = 0
        last_ref_count = 0

        for _ in range(max_wait_seconds):
            await playwright_server.call_tool("browser_wait_for", {"time": 1})

            check_snapshot = await playwright_server.call_tool("browser_snapshot", {})
            snapshot_text = check_snapshot.content[0].text

            # 条件1: 目标菜单项是否存在（导航栏已加载）
            target_ref = _find_ref_by_label(snapshot_text, target_label)
            if not target_ref:
                stable_count = 0
                continue  # 目标菜单项不存在，继续等待

            # 条件2: DOM 元素数量是否充足
            ref_count = snapshot_text.count("[ref=")
            if ref_count < 15:
                stable_count = 0
                continue  # DOM 元素太少，继续等待

            # 条件3: DOM 是否稳定
            if ref_count == last_ref_count:
                stable_count += 1
                if stable_count >= 2:
                    return  # 目标存在 + DOM 稳定，返回
            else:
                stable_count = 0

            last_ref_count = ref_count

        # 超时，也直接返回（尝试继续截图）

    @function_tool(
        name_override="programmatic_evidence_entry",
        description_override="程序化取证单个菜单入口，自动完成点击、截图、文本采集。",
    )
    async def programmatic_evidence_entry(
        entry_id: str,
        entry_index: int,
        entry_label: str,
        total_entries: int,
    ) -> str:
        """程序化取证单个入口（异步版本）。

        Args:
            entry_id: 入口唯一标识
            entry_index: 入口序号（从1开始）
            entry_label: 菜单标签
            total_entries: 总入口数量，用于进度判断

        Returns:
            JSON 字符串，包含取证结果
        """
        try:
            # 1. 直接获取当前页面快照（不再导航回首页）
            snapshot_result = await playwright_server.call_tool("browser_snapshot", {})

            # 2. 解析快照，匹配 entry_label
            snapshot_text = snapshot_result.content[0].text
            ref = _find_ref_by_label(snapshot_text, entry_label)
            if not ref:
                result_data = {
                    "entry_id": entry_id,
                    "entry_label": entry_label,
                    "progress": f"{entry_index}/{total_entries}",
                    "status": "failed",
                    "screenshot": None,
                    "text_snapshot": None,
                    "error": f"菜单 '{entry_label}' 在快照中不存在。",
                }
                # 保存失败记录到 JSON
                safe_label = (
                    entry_label.strip()
                    .replace(" ", "_")
                    .translate(str.maketrans("", "", r'/\:*?"<>|'))
                )
                json_path = evidence_dir / f"{entry_index:02d}_{safe_label}.json"
                json_path.write_text(
                    json.dumps(result_data, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                return json.dumps(result_data, ensure_ascii=False)

            # 3. 点击菜单
            await playwright_server.call_tool(
                "browser_click", {"element": entry_label, "ref": ref}
            )

            # 4. 等待页面加载完成（验证目标菜单项仍然可见）
            await _wait_for_page_ready(entry_label)

            # 5. 截图
            safe_label = (
                entry_label.strip()
                .replace(" ", "_")
                .translate(str.maketrans("", "", r'/\:*?"<>|'))
            )
            prefix = f"{entry_index:02d}_{safe_label}"
            screenshot_path = f"evidence/{prefix}.png"

            await playwright_server.call_tool(
                "browser_take_screenshot",
                {"filename": screenshot_path, "fullPage": True},
            )

            # 6. 获取文本
            text_result = await playwright_server.call_tool(
                "browser_evaluate", {"function": "() => document.body.innerText"}
            )
            text_content = text_result.content[0].text

            # 清理 Playwright 调试输出
            clean_text = text_content
            if clean_text.startswith('### Result\n"') and clean_text.endswith('"'):
                clean_text = clean_text[14:-1]
            elif clean_text.startswith("### Result\n"):
                clean_text = clean_text[12:]

            # 7. 保存文本
            text_path = evidence_dir / f"{prefix}.txt"
            text_path.write_text(clean_text, encoding="utf-8")

            # 8. 保存 JSON
            result_data = {
                "entry_id": entry_id,
                "entry_label": entry_label,
                "progress": f"{entry_index}/{total_entries}",
                "status": "success",
                "screenshot": screenshot_path,
                "text_snapshot": f"evidence/{prefix}.txt",
                "error": None,
            }
            json_path = evidence_dir / f"{prefix}.json"
            json_path.write_text(
                json.dumps(result_data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            return json.dumps(result_data, ensure_ascii=False)

        except Exception as exc:
            result_data = {
                "entry_id": entry_id,
                "entry_label": entry_label,
                "progress": f"{entry_index}/{total_entries}",
                "status": "failed",
                "screenshot": None,
                "text_snapshot": None,
                "error": f"取证失败：{exc}",
            }
            # 保存异常记录到 JSON
            safe_label = (
                entry_label.strip()
                .replace(" ", "_")
                .translate(str.maketrans("", "", r'/\:*?"<>|'))
            )
            json_path = evidence_dir / f"{entry_index:02d}_{safe_label}.json"
            json_path.write_text(
                json.dumps(result_data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return json.dumps(result_data, ensure_ascii=False)

    return programmatic_evidence_entry


def build_capture_page_data_tool(
    task_dir: Path,
    playwright_server: Any,
) -> Tool:
    """创建页面数据采集工具（截图+文本，异步版本）。

    前提：LLM 已经导航到目标页面。
    职责：只负责采集当前页面的数据。
    使用异步函数直接 await playwright_server.call_tool()，无需 event loop 桥接。

    Args:
        task_dir: 任务目录
        playwright_server: AutoSwitchingPlaywrightServer 实例

    Returns:
        页面数据采集工具
    """
    evidence_dir = task_dir / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    @function_tool(
        name_override="capture_page_data",
        description_override="采集当前页面的截图和文本，保存为指定格式。前提：LLM已导航到目标页面。",
    )
    async def capture_page_data(
        entry_id: str,
        entry_index: int,
        entry_label: str,
    ) -> str:
        """采集当前页面的截图和文本（异步版本）。

        Args:
            entry_id: 入口唯一标识
            entry_index: 入口序号（用于文件命名）
            entry_label: 菜单标签（用于文件命名）

        Returns:
            JSON 字符串，包含采集结果
        """
        try:
            # 1. 截图
            safe_label = (
                entry_label.strip()
                .replace(" ", "_")
                .translate(str.maketrans("", "", r'/\:*?"<>|'))
            )
            prefix = f"{entry_index:02d}_{safe_label}"
            screenshot_path = f"evidence/{prefix}.png"

            await playwright_server.call_tool(
                "browser_take_screenshot",
                {"filename": screenshot_path, "fullPage": True},
            )

            # 2. 文本采集
            text_result = await playwright_server.call_tool(
                "browser_evaluate", {"function": "() => document.body.innerText"}
            )
            text_content = text_result.content[0].text

            # 清理 Playwright 调试输出
            clean_text = text_content
            if clean_text.startswith('### Result\n"') and clean_text.endswith('"'):
                clean_text = clean_text[14:-1]
            elif clean_text.startswith("### Result\n"):
                clean_text = clean_text[12:]

            # 3. 保存文本
            text_path = evidence_dir / f"{prefix}.txt"
            text_path.write_text(clean_text, encoding="utf-8")

            # 4. 保存 JSON
            result_data = {
                "entry_id": entry_id,
                "status": "success",
                "screenshot": screenshot_path,
                "text_snapshot": f"evidence/{prefix}.txt",
                "error": None,
            }
            json_path = evidence_dir / f"{prefix}.json"
            json_path.write_text(
                json.dumps(result_data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            return json.dumps(result_data, ensure_ascii=False)

        except Exception as exc:
            result_data = {
                "entry_id": entry_id,
                "status": "failed",
                "screenshot": None,
                "text_snapshot": None,
                "error": f"数据采集失败：{exc}",
            }
            return json.dumps(result_data, ensure_ascii=False)

    return capture_page_data


def build_fetch_email_code_tool() -> Tool:
    """创建邮箱验证码获取工具（Mock 版本）。

    当前为 Mock 实现，始终返回固定验证码 123456。
    后续可替换为真实的 IMAP/POP3 邮箱读取实现。
    """

    @function_tool(
        name_override="fetch_email_code",
        description_override="获取发送到指定邮箱的验证码。在点击「发送验证码」按钮后调用此工具。",
    )
    def fetch_email_code(email: str) -> str:
        """获取邮箱验证码。

        Args:
            email: 接收验证码的邮箱地址

        Returns:
            JSON 字符串，包含 success、code/message 字段
        """
        # Mock 实现：始终返回固定验证码
        return json.dumps(
            {
                "success": True,
                "code": "123456",
                "message": f"已获取 {email} 的验证码",
            },
            ensure_ascii=False,
        )

    return fetch_email_code


__all__ = [
    "build_save_page_text_tool",
    "build_save_entry_result_tool",
    "build_compile_evidence_report_tool",
    "build_capture_and_save_tool",
    "build_capture_page_data_tool",
    "build_programmatic_evidence_entry_tool",
    "build_fetch_email_code_tool",
]
