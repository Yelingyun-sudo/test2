from __future__ import annotations

import asyncio
import email
import json
import logging
import os
import re
import subprocess
from datetime import UTC, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import aioimaplib
from agents import Tool, function_tool

from website_analytics.settings import get_settings

if TYPE_CHECKING:
    from website_analytics.models import EmailAccount

logger = logging.getLogger(__name__)


# 创建保存页面文本工具
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


# 创建取证报告工具
# 它的核心作用是：扫描所有搜集到的证据文件，生成一份人类可读的 Markdown 格式取证报告。
"""1. 核心工作流程
这个工具的逻辑非常清晰，就像整理档案一样：

收集素材：
它会去 evidence 目录下找所有的 .json 文件（这是上一个工具生成的每一条取证记录）。它会自动忽略已经生成的 report.json，确保只处理原始数据。
校验与核查：
这一步非常关键，它不仅是汇总，还在做“质检”：
读取每个 JSON 文件，看里面的状态是成功还是失败。
核对实物：JSON 里说有截图，它真的会去检查那个截图文件存不存在；说有文本快照，也会检查文件在不在。
如果发现“账实不符”（比如 JSON 说成功，但截图文件丢了），会记录为异常。
智能命名：
它会尝试读取 evidenceEntryList.txt 来获取菜单的标准名称。如果这个文件不存在（可能上一步跑丢了），它也很聪明，会直接从文件名里提取名称（比如把 01_user_profile.json 解析为 user profile），绝不耽误干活。
生成报告：
它会生成一个格式非常漂亮的 Markdown 文件（默认叫 report.md），内容结构包括：
统计概览：总共取证多少个，成功多少，失败多少，以及生成时间。
总览表格：一目了然地列出所有入口的名称、状态、以及查看链接。
详细记录：每个入口单独一个章节，直接把截图嵌入进去（Markdown 语法），方便你在阅读报告时直接看图。
附录：列出了所有处理过的文件，以及具体的报错原因（比如哪个文件缺截图，哪个 JSON 解析失败）。"""


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


"""2. 工作流程（八步走）
这个工具被调用时，会按顺序执行以下步骤：

环境准备：在指定目录下创建一个 evidence 文件夹，专门用来存放证据。
获取快照：通过 playwright_server 获取当前网页的 DOM 快照，看看页面上有哪些按钮和菜单。
寻找目标：根据传入的 entry_label（菜单名称），在快照里找对应的按钮。如果找不到，直接记录失败并退出。
模拟点击：找到了就自动调用 browser_click 点击这个菜单。
智能等待：这是一个亮点。它不会傻傻地等固定时间，而是循环检查：
        菜单还在不在？
        页面元素够不够多（防止空白页）？
        页面元素是不是稳定了（防止还在加载中）？
        最多等 4 秒，超时也不报错，直接进行下一步（容错性很好）。
全屏截图：页面稳住后，自动截图保存为 PNG。
提取文本：抓取网页的 innerText（纯文本内容），并清理掉调试用的干扰字符，保存为 TXT。
生成报告：最后生成一个 JSON 文件，记录这次操作是成功还是失败，以及截图和文本的路径。
"""


# 创建程序化取证入口工具
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


def _extract_verification_code(text: str) -> str | None:
    """从邮件文本中提取验证码。

    支持多种常见格式：
    - 中文：验证码是：123456
    - 英文：verification code: 123456
    - 方括号：[123456]
    - 独立数字：6 位数字
    - 全角数字：验证码是：１２３４５６（自动转换为半角）
    - 空格分隔：1 2 3 4 5 6（自动移除空格）

    Args:
        text: 邮件正文内容

    Returns:
        验证码字符串，未找到则返回 None
    """
    if not text:
        return None

    # 预处理：全角数字转半角，统一处理
    # 将全角数字（０-９）转换为半角数字（0-9）
    text_normalized = text.translate(
        str.maketrans("０１２３４５６７８９", "0123456789")
    )

    # 预处理：移除可能的空格分隔（但保留关键词后的正常空格）
    # 对于常见的验证码位置，尝试移除数字之间的空格
    # 例如："1 2 3 4 5 6" → "123456"
    # 注意：只处理数字之间的空格，避免误处理其他内容
    text_normalized = re.sub(r"(\d)\s+(\d)", r"\1\2", text_normalized)

    # 多种验证码匹配模式（按优先级排序）
    patterns = [
        r"验证码[是为：:]\s*[：:]?\s*(\d{4,8})",
        r"验证码[是为]?\s*[：:]\s*(\d{4,8})",
        r"verification\s*code[:\s]+(\d{4,8})",
        r"code[:\s]+(\d{4,8})",
        r"OTP[:\s]+(\d{4,8})",
        r"pin[:\s]+(\d{4,8})",
        r"\[(\d{4,8})\]",
        r"(?<![0-9])(\d{6})(?![0-9])",
        r"(?<![0-9])(\d{4,8})(?![0-9])",
    ]

    # 先在预处理后的文本上匹配
    for pattern in patterns:
        match = re.search(pattern, text_normalized, re.IGNORECASE)
        if match:
            return match.group(1)

    # 如果预处理后的文本没有匹配到，再尝试原始文本
    # （以防预处理破坏了某些格式）
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)

    return None


def _parse_email_body(msg: email.message.Message) -> str:
    """从邮件对象中提取正文（纯文本优先）。

    Args:
        msg: email.message.Message 对象

    Returns:
        邮件正文字符串（纯文本或 HTML）
    """
    body_text = ""
    body_html = ""

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition", ""))

            if "attachment" in content_disposition:
                continue

            if content_type == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    body_text = payload.decode("utf-8", errors="ignore")
            elif content_type == "text/html":
                payload = part.get_payload(decode=True)
                if payload:
                    body_html = payload.decode("utf-8", errors="ignore")
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            body_text = payload.decode("utf-8", errors="ignore")

    return body_text if body_text else body_html


def _parse_email_date(msg: email.message.Message) -> datetime | None:
    """从邮件对象中提取发送时间。

    Args:
        msg: email.message.Message 对象

    Returns:
        邮件发送时间（UTC），解析失败则返回 None
    """
    date_str = msg.get("Date")
    if not date_str:
        return None

    try:
        # 解析 RFC 2822 格式的日期
        # 示例：Tue,  6 Jan 2026 08:32:49 +0000 (UTC)
        email_datetime = parsedate_to_datetime(date_str)

        # 转换为 UTC
        if email_datetime.tzinfo is None:
            # 无时区信息，假设为 UTC
            return email_datetime.replace(tzinfo=UTC)
        else:
            # 转换为 UTC
            return email_datetime.astimezone(UTC)
    except (ValueError, TypeError, AttributeError):
        return None


# 构建邮箱验证码获取工具
def build_fetch_email_code_tool(account: "EmailAccount") -> Tool:
    """创建邮箱验证码获取工具（真实 IMAP 实现）。

    通过 aioimaplib 连接邮箱，读取最新邮件并提取验证码。
    使用传入的 EmailAccount 配置进行连接。

    Args:
        account: 要使用的邮箱账号配置

    Returns:
        工具声明
    """
    settings = get_settings()

    @function_tool(
        name_override="fetch_email_code",
        description_override="获取发送到指定邮箱的验证码。在点击「发送验证码」按钮后调用此工具。",
    )
    async def fetch_email_code(email_address: str) -> str:
        """异步获取邮箱验证码。

        Args:
            email_address: 接收验证码的邮箱地址

        Returns:
            JSON 字符串，包含 success、code/message 字段
        """
        imap_client = None

        try:
            # 1. 记录使用的账号
            logger.info(f"使用邮箱账号: {account.register_account}")

            # 2. 连接 IMAP 服务器
            logger.info(
                "正在连接 IMAP 服务器：%s:%d", account.imap_server, account.imap_port
            )
            imap_client = aioimaplib.IMAP4_SSL(
                host=account.imap_server,
                port=account.imap_port,
            )
            await imap_client.wait_hello_from_server()
            logger.info("IMAP 连接成功")

            # 3. 登录
            login_response = await imap_client.login(
                account.imap_username,
                account.imap_password,
            )
            if login_response.result != "OK":
                error_msg = login_response.lines[0].decode("utf-8", errors="ignore")
                logger.warning("IMAP 登录失败：%s", error_msg)
                return json.dumps(
                    {
                        "success": False,
                        "message": f"IMAP 登录失败：{error_msg}",
                    },
                    ensure_ascii=False,
                )
            logger.info("IMAP 登录成功")

            # 4. 选择 INBOX 邮箱
            select_response = await imap_client.select("INBOX")
            if select_response.result != "OK":
                logger.warning("无法选择 INBOX 邮箱")
                return json.dumps(
                    {
                        "success": False,
                        "message": "无法选择 INBOX 邮箱",
                    },
                    ensure_ascii=False,
                )
            logger.debug("已选择 INBOX 邮箱")

            # 5-10. 搜索邮件并提取验证码（添加重试机制）
            for attempt in range(settings.imap_fetch_max_retries):
                # 搜索未读邮件
                logger.debug(
                    "开始搜索未读邮件（尝试 %d/%d）",
                    attempt + 1,
                    settings.imap_fetch_max_retries,
                )
                search_response = await imap_client.search("UNSEEN")

                if search_response.result != "OK":
                    if attempt < settings.imap_fetch_max_retries - 1:
                        logger.warning("搜索邮件失败，将重试")
                        await asyncio.sleep(settings.imap_fetch_retry_interval)
                        continue
                    logger.error(
                        "搜索邮件失败（已重试 %d 次）", settings.imap_fetch_max_retries
                    )
                    return json.dumps(
                        {
                            "success": False,
                            "message": "搜索邮件失败",
                        },
                        ensure_ascii=False,
                    )

                # 获取邮件 ID 列表
                email_ids_bytes = search_response.lines[0]
                if not email_ids_bytes or email_ids_bytes == b"":
                    # 未读邮件为空，可能验证码还没到，等待重试
                    if attempt < settings.imap_fetch_max_retries - 1:
                        logger.debug("未读邮件为空，等待重试")
                        await asyncio.sleep(settings.imap_fetch_retry_interval)
                        continue
                    logger.warning(
                        "未读邮件为空（已重试 %d 次）", settings.imap_fetch_max_retries
                    )
                    return json.dumps(
                        {
                            "success": False,
                            "message": f"未读邮件为空（已重试 {settings.imap_fetch_max_retries} 次）",
                        },
                        ensure_ascii=False,
                    )

                email_ids = email_ids_bytes.decode("utf-8").split()
                if not email_ids:
                    if attempt < settings.imap_fetch_max_retries - 1:
                        logger.debug("未读邮件为空，等待重试")
                        await asyncio.sleep(settings.imap_fetch_retry_interval)
                        continue
                    logger.warning(
                        "未读邮件为空（已重试 %d 次）", settings.imap_fetch_max_retries
                    )
                    return json.dumps(
                        {
                            "success": False,
                            "message": f"未读邮件为空（已重试 {settings.imap_fetch_max_retries} 次）",
                        },
                        ensure_ascii=False,
                    )

                logger.debug("搜索到 %d 封未读邮件", len(email_ids))

                # 读取最新一封未读邮件
                latest_email_id = email_ids[-1]
                logger.debug("正在获取邮件 ID: %s", latest_email_id)
                fetch_response = await imap_client.fetch(latest_email_id, "(RFC822)")
                if fetch_response.result != "OK":
                    if attempt < settings.imap_fetch_max_retries - 1:
                        logger.warning(
                            "读取邮件失败（ID: %s），将重试", latest_email_id
                        )
                        await asyncio.sleep(settings.imap_fetch_retry_interval)
                        continue
                    logger.error("读取邮件失败（ID: %s）", latest_email_id)
                    return json.dumps(
                        {
                            "success": False,
                            "message": f"读取邮件失败（ID: {latest_email_id}）",
                        },
                        ensure_ascii=False,
                    )
                logger.debug("成功获取邮件 ID: %s", latest_email_id)

                # 解析邮件内容
                # aioimaplib 返回格式：lines[1] 包含邮件原始数据
                raw_email = fetch_response.lines[1]
                msg = email.message_from_bytes(raw_email)

                # 立即标记邮件为已读，避免重复读取和时序问题
                try:
                    store_response = await imap_client.store(
                        latest_email_id, "+FLAGS", "\\Seen"
                    )
                    if store_response.result == "OK":
                        logger.debug("邮件已标记为已读（ID: %s）", latest_email_id)
                    else:
                        logger.warning("标记邮件为已读失败（ID: %s）", latest_email_id)
                except Exception as exc:
                    # 标记失败不影响后续处理，仅记录日志
                    logger.warning(
                        "标记邮件为已读时发生异常（ID: %s）: %s", latest_email_id, exc
                    )

                # 检查邮件时间（防止读取旧邮件）
                email_date = _parse_email_date(msg)
                if email_date:
                    email_age = (datetime.now(UTC) - email_date).total_seconds()
                    if email_age > settings.imap_email_max_age_seconds:
                        # 邮件太旧，跳过并重试
                        logger.debug("邮件太旧（%d 秒前），跳过", int(email_age))
                        if attempt < settings.imap_fetch_max_retries - 1:
                            await asyncio.sleep(settings.imap_fetch_retry_interval)
                            continue
                        logger.warning(
                            "邮件太旧（%d 秒前），已重试 %d 次",
                            int(email_age),
                            settings.imap_fetch_max_retries,
                        )
                        return json.dumps(
                            {
                                "success": False,
                                "message": f"邮件太旧（{int(email_age)} 秒前），已重试 {settings.imap_fetch_max_retries} 次",
                            },
                            ensure_ascii=False,
                        )

                # 提取正文
                body = _parse_email_body(msg)

                # 提取验证码
                code = _extract_verification_code(body)

                if code:
                    # 成功提取验证码
                    logger.info("成功提取验证码（邮箱: %s）", email_address)
                    return json.dumps(
                        {
                            "success": True,
                            "code": code,
                            "message": f"已获取 {email_address} 的验证码",
                        },
                        ensure_ascii=False,
                    )

                # 邮件中没有验证码，可能不是验证码邮件，等待重试
                if attempt < settings.imap_fetch_max_retries - 1:
                    logger.debug("未能从邮件中提取验证码，等待重试")
                    await asyncio.sleep(settings.imap_fetch_retry_interval)
                    continue

            # 所有重试都失败
            logger.warning(
                "未能从邮件中提取到验证码（已重试 %d 次）",
                settings.imap_fetch_max_retries,
            )
            return json.dumps(
                {
                    "success": False,
                    "message": f"未能从邮件中提取到验证码（已重试 {settings.imap_fetch_max_retries} 次）",
                },
                ensure_ascii=False,
            )

        except asyncio.TimeoutError:
            logger.warning("IMAP 连接超时")
            return json.dumps(
                {
                    "success": False,
                    "message": "连接超时",
                },
                ensure_ascii=False,
            )
        except Exception as exc:
            logger.error(
                "获取验证码失败：%s: %s", type(exc).__name__, str(exc), exc_info=True
            )
            return json.dumps(
                {
                    "success": False,
                    "message": f"获取验证码失败：{type(exc).__name__}: {str(exc)}",
                },
                ensure_ascii=False,
            )

        finally:
            # 11. 清理连接
            if imap_client:
                try:
                    logger.debug("正在断开 IMAP 连接")
                    await imap_client.logout()
                except Exception:
                    pass  # 忽略清理过程中的异常

    return fetch_email_code


# 创建截图标注工具
def build_annotate_screenshot_tool() -> Tool:
    """在截图上绘制矩形框标注。

    用于支付任务中标注域名、订阅/套餐购买等关键元素。
    """

    @function_tool(
        name_override="annotate_screenshot",
        description_override=(
            "在截图上绘制红色矩形框进行标注。"
            "接收截图路径和标注列表，每个标注包含元素的文本描述和边界框。"
            "输出标注后的截图路径。"
        ),
    )
    def annotate_screenshot(
        image_path: str,
        annotations: list[dict[str, Any]],
        output_path: str | None = None,
    ) -> str:
        from PIL import Image, ImageDraw

        img = Image.open(image_path)
        draw = ImageDraw.Draw(img)

        for ann in annotations:
            bounds = ann.get("bounds", {})
            x = bounds.get("x", 0)
            y = bounds.get("y", 0)
            w = bounds.get("width", 0)
            h = bounds.get("height", 0)
            if w > 0 and h > 0:
                # 绘制红色矩形框，线宽为3
                draw.rectangle([x, y, x + w, y + h], outline="red", width=3)

        result_path = output_path or image_path
        img.save(result_path)
        return f"标注完成: {result_path}"

    return annotate_screenshot


# 创建支付步骤截图工具
def build_save_payment_screenshot_tool(
    task_dir: Path,
) -> Tool:
    """构建支付步骤截图工具。

    该工具允许支付代理在关键步骤截图，并自动保存为标准命名格式：
    - screenshot_1.png: 订阅页面截图
    - screenshot_2.png: 支付方式选择页面截图
    - screenshot_3.png: 支付二维码页面截图

    三张截图均使用系统级截图工具（scrot + xdotool）截取整个 Chrome 窗口，
    以包含浏览器地址栏显示域名信息，保持截图风格统一。

    Args:
        task_dir: 任务目录路径

    Returns:
        截图工具函数
    """
    captures_dir = task_dir / "captures"
    captures_dir.mkdir(parents=True, exist_ok=True)

    def _get_tool_path(name: str) -> str:
        """获取系统工具路径，优先使用 ~/.local/bin 下的版本。"""
        local_path = os.path.expanduser(f"~/.local/bin/{name}")
        return local_path if os.path.exists(local_path) else name

    def _find_chrome_window(xdotool_path: str) -> str:
        """查找 Chrome 浏览器窗口 ID。

        Args:
            xdotool_path: xdotool 工具路径

        Returns:
            窗口 ID 字符串

        Raises:
            RuntimeError: 未找到窗口时抛出
        """
        # 按优先级尝试查找 Chrome 窗口
        search_patterns = ["google-chrome", "chromium"]

        for pattern in search_patterns:
            result = subprocess.run(
                [xdotool_path, "search", "--class", pattern],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                # 返回最后一个窗口（通常是最近活动的）
                window_ids = result.stdout.strip().split("\n")
                window_id = window_ids[-1].strip()
                logger.info(f"找到 Chrome 窗口 (class={pattern}): {window_id}")
                return window_id

        raise RuntimeError("无法找到 Chrome 浏览器窗口，请确保 Chrome 已启动")

    def _activate_chrome_window(xdotool_path: str, window_id: str) -> None:
        """激活 Chrome 窗口。

        Args:
            xdotool_path: xdotool 工具路径
            window_id: 窗口 ID
        """
        try:
            subprocess.run(
                [xdotool_path, "windowactivate", window_id],
                check=True,
                timeout=5,
            )
            logger.info(f"已激活 Chrome 窗口: {window_id}")
            # 等待窗口完全激活
            import time
            time.sleep(0.5)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            logger.warning(f"激活窗口失败或超时: {e}，继续尝试截图")

    def _take_scrot_screenshot(scrot_path: str, screenshot_path: Path) -> None:
        """使用 scrot 截取当前活动窗口。

        Args:
            scrot_path: scrot 工具路径
            screenshot_path: 截图保存路径

        Raises:
            RuntimeError: 截图失败时抛出
        """
        try:
            subprocess.run(
                [scrot_path, "-u", str(screenshot_path)],
                check=True,
                timeout=10,
            )
            logger.info(f"已使用 scrot -u 截取 Chrome 窗口: {screenshot_path}")
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            raise RuntimeError(f"scrot 截图失败: {e}")

    def _validate_screenshot(screenshot_path: Path) -> None:
        """验证截图文件是否成功创建且有效。

        Args:
            screenshot_path: 截图文件路径

        Raises:
            RuntimeError: 验证失败时抛出
        """
        if not screenshot_path.exists():
            raise RuntimeError("截图文件未成功创建")

        file_size = screenshot_path.stat().st_size
        if file_size < 1024:
            raise RuntimeError(f"截图文件异常（大小: {file_size} bytes），可能是空截图")

        logger.info(f"系统级截图成功保存: {screenshot_path} ({file_size} bytes)")

    def _capture_chrome_window(screenshot_path: Path) -> None:
        """使用系统级工具截取 Chrome 窗口。

        使用 xdotool 查找并激活 Chrome 窗口，然后使用 scrot 截图。
        这样可以截取到浏览器地址栏，显示当前网站域名。

        Args:
            screenshot_path: 截图保存路径

        Raises:
            RuntimeError: 截图失败时抛出
        """
        xdotool_path = _get_tool_path("xdotool")
        scrot_path = _get_tool_path("scrot")

        try:
            # 1. 查找 Chrome 窗口
            window_id = _find_chrome_window(xdotool_path)

            # 2. 确保目录存在
            screenshot_path.parent.mkdir(parents=True, exist_ok=True)

            # 3. 激活窗口并截图
            _activate_chrome_window(xdotool_path, window_id)
            _take_scrot_screenshot(scrot_path, screenshot_path)
            _validate_screenshot(screenshot_path)

        except FileNotFoundError as e:
            if "scrot" in str(e) or "xdotool" in str(e):
                raise RuntimeError(
                    "系统截图工具未安装。请运行: sudo apt-get install scrot xdotool"
                ) from e
            raise

    @function_tool(
        name_override="save_payment_screenshot",
        description_override=(
            "在支付流程的关键步骤截取页面截图（包含浏览器地址栏），保存为标准命名的文件。"
            "步骤1: 登录后显示订阅/套餐购买的页面；"
            "步骤2: 显示支付方式选择（微信/支付宝）的页面；"
            "步骤3: 显示支付二维码的页面。"
        ),
    )
    async def save_payment_screenshot(
        step: int,
        description: str,
    ) -> str:
        """保存支付流程指定步骤的截图。

        Args:
            step: 步骤编号（1=订阅页面, 2=支付方式选择, 3=二维码页面）
            description: 截图描述说明

        Returns:
            截图文件的相对路径
        """
        if step not in (1, 2, 3):
            raise ValueError("step 必须是 1、2 或 3")

        screenshot_path = captures_dir / f"screenshot_{step}.png"

        try:
            # 所有步骤统一使用系统级截图工具截取整个 Chrome 窗口（包含地址栏）
            logger.info(f"步骤{step}：使用系统级截图工具（scrot + xdotool）截取 Chrome 窗口")
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _capture_chrome_window, screenshot_path)

            relative_path = screenshot_path.relative_to(task_dir)
            return f"步骤{step}截图已保存: captures/{relative_path.name} ({description})"

        except Exception as exc:
            logger.error("支付截图保存失败 (step=%s): %s", step, exc)
            raise RuntimeError(f"截图保存失败: {exc}") from exc

    return save_payment_screenshot


__all__ = [
    "build_save_page_text_tool",
    "build_save_entry_result_tool",
    "build_compile_evidence_report_tool",
    "build_capture_and_save_tool",
    "build_capture_page_data_tool",
    "build_programmatic_evidence_entry_tool",
    "build_fetch_email_code_tool",
    "build_annotate_screenshot_tool",
    "build_save_payment_screenshot_tool",
]
