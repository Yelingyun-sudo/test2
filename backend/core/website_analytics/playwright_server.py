from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from contextlib import suppress
from typing import Any

from mcp.types import CallToolResult

from agents.logger import logger
from agents.mcp.server import MCPServerStdio

from website_analytics.settings import get_settings

_OPEN_TABS_HEADING = "### Open tabs"


@dataclass(frozen=True)
class TabInfo:
    """Represents a single browser tab entry emitted by Playwright tools."""

    index: int
    title: str
    url: str
    is_current: bool


def _parse_open_tabs(text: str) -> list[TabInfo]:
    """Extract the tab list from a Playwright tool textual payload."""

    if _OPEN_TABS_HEADING not in text:
        return []

    section = text.split(_OPEN_TABS_HEADING, maxsplit=1)[-1]
    tab_lines = [
        line.strip()
        for line in section.splitlines()
        if re.match(r"^- \d+:", line.strip())
    ]

    tabs: list[TabInfo] = []
    pattern = re.compile(r"^- (\d+):\s*(\(current\))?\s*\[([^\]]+)\]\s*\(([^)]+)\)")
    for entry in tab_lines:
        match = pattern.match(entry)
        if not match:
            continue
        index_str, current_flag, title, url = match.groups()
        tabs.append(
            TabInfo(
                index=int(index_str),
                title=title,
                url=url,
                is_current=bool(current_flag),
            )
        )

    return tabs


class AutoSwitchingPlaywrightServer(MCPServerStdio):
    """Playwright MCP server that auto-selects newly opened or active tabs.

    The login agent instructions要求在打开新标签页时立即切换，本类在每次
    Playwright 工具调用后解析输出中的 `### Open tabs` 段落，自动执行
    `browser_tabs{"action":"select"}` 将控制权切换到最新或当前标签。
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._known_tabs: dict[int, str] = {}
        self._current_index: int | None = None
        self._auto_switch_inflight = False

    async def __aexit__(self, exc_type, exc_value, traceback):
        task = asyncio.current_task()
        cancel_count_before = task.cancelling() if task else 0
        cancelled = False

        # 先让 MCP server 内部的 Playwright 尝试优雅关闭浏览器。
        # 仅靠杀掉 `npx` 进程组在某些 Linux 场景下可能无法回收 Playwright
        # 以 detached 方式拉起的 Chrome 进程组，导致 orphan Chrome 堆积。
        try:
            await self._best_effort_close_browser()
        except asyncio.CancelledError:
            cancelled = True
            if (
                task
                and task.cancelling() > cancel_count_before
                and hasattr(task, "uncancel")
            ):
                task.uncancel()
            with suppress(Exception):
                await self._best_effort_close_browser()

        # 超时取消时（`asyncio.wait_for`）需要尽量完成清理，否则子进程可能残留。
        # Python 3.11+ 支持 `Task.uncancel()`，这里做一次防御性处理。
        try:
            return await super().__aexit__(exc_type, exc_value, traceback)
        except asyncio.CancelledError:
            cancelled = True
            if (
                task
                and task.cancelling() > cancel_count_before
                and hasattr(task, "uncancel")
            ):
                task.uncancel()
            await super().__aexit__(exc_type, exc_value, traceback)
            raise
        finally:
            # 即使父类清理完成，也检查是否有残留的 Chrome 进程
            # 用 suppress 包装，确保清理失败不会掩盖原始异常
            # 注意：Python 3.12 中 CancelledError 继承自 BaseException，必须显式捕获
            with suppress(Exception, asyncio.CancelledError):
                await self._force_cleanup_orphaned_chrome()

            # 只有在没有其他异常正在传播时才抛出 CancelledError
            if cancelled and exc_type is None:
                raise asyncio.CancelledError

    async def call_tool(self, tool_name: str, arguments: dict[str, Any] | None = None):
        # Playwright MCP's `browser_snapshot` supports saving to a markdown file via
        # `filename`, but in practice this can produce empty files (and breaks
        # agents that rely on inlined snapshots for element refs). Strip it.
        sanitized_arguments = arguments
        if (
            tool_name == "browser_snapshot"
            and isinstance(arguments, dict)
            and "filename" in arguments
        ):
            sanitized_arguments = {
                k: v for k, v in arguments.items() if k != "filename"
            }
            logger.debug(
                "Stripped filename from browser_snapshot call to force inline snapshot."
            )

        result = await super().call_tool(tool_name, sanitized_arguments)

        # 避免对自动切换产生的二次调用再次触发解析。
        if not self._auto_switch_inflight:
            await self._auto_select_if_needed(tool_name, result)

        return result

    async def _auto_select_if_needed(
        self, tool_name: str, result: CallToolResult
    ) -> None:
        if not result.content:
            return

        text_blocks = [
            getattr(item, "text", "")
            for item in result.content
            if getattr(item, "type", "") == "text"
        ]
        if not text_blocks:
            return

        tabs = _parse_open_tabs("\n".join(text_blocks))
        if not tabs:
            return

        # 单个标签页时无需切换，直接记录状态后退出。
        if len(tabs) == 1:
            self._known_tabs = {tabs[0].index: tabs[0].url}
            self._current_index = tabs[0].index
            return

        known_before = self._known_tabs.copy()
        current_tab = next((tab for tab in tabs if tab.is_current), None)

        # 计算是否出现新标签，或当前标签发生变化。
        new_tabs = [
            tab
            for tab in tabs
            if tab.index not in known_before or known_before.get(tab.index) != tab.url
        ]

        should_switch = None
        if new_tabs:
            # 默认选择索引最大的标签（通常是最新打开）。
            should_switch = max(new_tabs, key=lambda tab: tab.index)
        elif current_tab and current_tab.index != self._current_index:
            should_switch = current_tab

        if should_switch is None:
            # 更新缓存后退出。
            self._known_tabs = {tab.index: tab.url for tab in tabs}
            self._current_index = (
                current_tab.index if current_tab else self._current_index
            )
            return

        logger.debug(
            "Detected tab change via tool '%s': switching to index=%s (%s)",
            tool_name,
            should_switch.index,
            should_switch.url,
        )

        self._auto_switch_inflight = True
        try:
            select_result = await super().call_tool(
                "browser_tabs",
                {"action": "select", "index": should_switch.index},
            )
        finally:
            self._auto_switch_inflight = False

        # 解析最新的标签状态（优先使用 select 的输出，否则退回原数据）。
        updated_tabs = tabs
        if select_result and getattr(select_result, "content", None):
            select_text_blocks = [
                getattr(item, "text", "")
                for item in select_result.content
                if getattr(item, "type", "") == "text"
            ]
            parsed = _parse_open_tabs("\n".join(select_text_blocks))
            if parsed:
                updated_tabs = parsed

        self._known_tabs = {tab.index: tab.url for tab in updated_tabs}
        self._current_index = should_switch.index

    async def _best_effort_close_browser(self) -> None:
        if not getattr(self, "session", None):
            return

        settings = get_settings()
        timeout = settings.playwright_close_timeout_seconds

        # 保存对父类方法的引用，避免在嵌套函数中使用 super() 的问题
        parent_call_tool = super().call_tool

        async def _call(tool_name: str, arguments: dict[str, Any] | None = None) -> Any:
            return await asyncio.wait_for(
                parent_call_tool(tool_name, arguments),
                timeout=timeout,
            )

        # 1) 优先尝试整体关闭（如果 MCP tool 支持）。
        try:
            await _call("browser_close", {})
            logger.debug("成功调用 browser_close，等待视频和 trace 保存完成")
            return
        except Exception as exc:
            logger.warning(
                "调用 browser_close 失败（可能超时或工具不支持），将尝试逐个关闭标签: %s",
                exc,
            )

        # 2) 回退：列出标签并逐个关闭（如果 MCP tool 支持）。
        try:
            result = await _call("browser_tabs", {"action": "list"})
            text_blocks = [
                getattr(item, "text", "")
                for item in getattr(result, "content", []) or []
                if getattr(item, "type", "") == "text"
            ]
            tabs = _parse_open_tabs("\n".join(text_blocks))
            for tab in sorted(tabs, key=lambda t: t.index, reverse=True):
                try:
                    await _call("browser_tabs", {"action": "close", "index": tab.index})
                    logger.debug("已关闭标签页 index=%s", tab.index)
                except Exception as exc:
                    logger.warning(
                        "关闭标签页 index=%s 失败: %s",
                        tab.index,
                        exc,
                    )
        except Exception as exc:
            logger.warning(
                "列出浏览器标签失败，可能无法优雅关闭: %s",
                exc,
            )

    async def _force_cleanup_orphaned_chrome(self) -> None:
        """通过进程特征查找并终止可能残留的 Chrome 进程。

        识别策略：
        1. 进程名包含 chrome (google-chrome, chrome, chromium等)
        2. 命令行包含 'playwright_chromiumdev_profile-' (Playwright特征)
        3. 父进程是 systemd (PID 1) - 孤儿进程标志

        这是在父类清理逻辑之后的最后一道防线，用于处理 Chrome 脱离进程组
        控制的情况（父进程变为 systemd）。
        """
        # 所有危险操作都包在 try 里，避免影响原始异常传播
        try:
            import psutil
        except ImportError:
            logger.warning(
                "psutil 未安装，无法执行孤儿进程清理。"
                "请运行: uv pip install psutil（或 pip install psutil）"
            )
            return

        import os
        import signal

        orphaned_pids: list[int] = []

        try:
            # 查找 Playwright 启动的 Chrome 孤儿进程
            for proc in psutil.process_iter(["pid", "name", "cmdline", "ppid"]):
                try:
                    proc_name = (proc.info.get("name") or "").lower()

                    # 检查是否是 Chrome 进程（支持多种命名）
                    if not any(
                        keyword in proc_name for keyword in ["chrome", "chromium"]
                    ):
                        continue

                    # 检查命令行参数中是否包含 Playwright 特征
                    cmdline = proc.info.get("cmdline") or []
                    if not any(
                        "playwright_chromiumdev_profile-" in str(arg) for arg in cmdline
                    ):
                        continue

                    # 检查父进程是否是 systemd (PID 1) - 孤儿进程的特征
                    if proc.info.get("ppid") != 1:
                        continue

                    orphaned_pids.append(proc.info["pid"])
                    logger.warning(
                        "发现 Playwright 孤儿 Chrome 进程: pid=%s name=%s",
                        proc.info["pid"],
                        proc_name,
                    )
                except (psutil.NoSuchProcess, psutil.AccessDenied, KeyError):
                    # 进程可能已退出或无权限访问，跳过
                    continue

            # 终止发现的孤儿进程
            for pid in orphaned_pids:
                try:
                    logger.warning("强制终止孤儿 Chrome 进程: pid=%s", pid)
                    os.kill(pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass  # 进程已退出
                except Exception as exc:
                    logger.error("终止孤儿进程失败 pid=%s: %s", pid, exc)

            # 等待2秒后检查是否还有残留
            if orphaned_pids:
                await asyncio.sleep(2)
                for pid in orphaned_pids:
                    try:
                        os.kill(pid, 0)  # 检查进程是否还存在
                        # 如果还存在，使用 SIGKILL
                        logger.warning("进程 %s 未响应 SIGTERM，使用 SIGKILL", pid)
                        os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass  # 进程已退出
                    except Exception as exc:
                        logger.error("SIGKILL 失败 pid=%s: %s", pid, exc)

        except Exception as exc:
            # 捕获所有异常，避免影响 __aexit__ 的正常流程
            logger.error("孤儿进程清理失败: %s", exc, exc_info=True)


__all__ = ["AutoSwitchingPlaywrightServer"]
