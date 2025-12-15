from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from contextlib import suppress
from typing import Any

from mcp.types import CallToolResult

from agents.logger import logger
from agents.mcp.server import MCPServerStdio

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
            if task and task.cancelling() > cancel_count_before and hasattr(
                task, "uncancel"
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
            if task and task.cancelling() > cancel_count_before and hasattr(
                task, "uncancel"
            ):
                task.uncancel()
            await super().__aexit__(exc_type, exc_value, traceback)
            raise
        finally:
            # 只有在没有其他异常正在传播时才抛出 CancelledError
            if cancelled and exc_type is None:
                raise asyncio.CancelledError

    async def call_tool(self, tool_name: str, arguments: dict[str, Any] | None = None):
        result = await super().call_tool(tool_name, arguments)

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

        async def _call(tool_name: str, arguments: dict[str, Any] | None = None) -> Any:
            return await asyncio.wait_for(
                super().call_tool(tool_name, arguments),
                timeout=8,
            )

        # 1) 优先尝试整体关闭（如果 MCP tool 支持）。
        with suppress(Exception):
            await _call("browser_close", {})
            return

        # 2) 回退：列出标签并逐个关闭（如果 MCP tool 支持）。
        with suppress(Exception):
            result = await _call("browser_tabs", {"action": "list"})
            text_blocks = [
                getattr(item, "text", "")
                for item in getattr(result, "content", []) or []
                if getattr(item, "type", "") == "text"
            ]
            tabs = _parse_open_tabs("\n".join(text_blocks))
            for tab in sorted(tabs, key=lambda t: t.index, reverse=True):
                with suppress(Exception):
                    await _call("browser_tabs", {"action": "close", "index": tab.index})


__all__ = ["AutoSwitchingPlaywrightServer"]
