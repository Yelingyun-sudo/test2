from __future__ import annotations

import asyncio
import dataclasses
import json
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from agents.agent import Agent
from agents.items import TResponseInputItem
from agents.lifecycle import RunHooks
from agents.run_context import RunContextWrapper, TContext


@dataclass
class _TurnMetadata:
    agent_name: str
    agent_slug: str
    turn: int
    global_sequence: int
    request_started_at: datetime


class LLMTranscriptLoggerHooks(RunHooks[TContext]):
    """Persist LLM requests and responses to markdown files for easier inspection."""

    def __init__(
        self,
        output_directory: Path,
        *,
        capture_browser_state: bool = False,
        capture_full_page: bool = True,
    ) -> None:
        self._output_directory = Path(output_directory)
        self._output_directory.mkdir(parents=True, exist_ok=True)
        self._turn_counters: dict[str, int] = {}
        self._pending_turns: dict[str, _TurnMetadata] = {}
        self._global_sequence_counter: int = 0
        self._capture_browser_state = capture_browser_state
        self._capture_full_page = capture_full_page
        self._playwright_server: Any | None = None

    def set_playwright_server(self, server: Any | None) -> None:
        """注入 Playwright MCP server，便于在每个回合捕获截图/DOM。"""
        self._playwright_server = server

    async def on_llm_start(
        self,
        context: RunContextWrapper[TContext],
        agent: Agent[TContext],
        system_prompt: str | None,
        input_items: list[TResponseInputItem],
    ) -> None:
        _ = context
        agent_name = agent.name or agent.__class__.__name__
        agent_slug = _slugify(agent_name)
        turn = self._turn_counters.get(agent_name, 0) + 1
        self._turn_counters[agent_name] = turn

        self._global_sequence_counter += 1

        metadata = _TurnMetadata(
            agent_name=agent_name,
            agent_slug=agent_slug,
            turn=turn,
            global_sequence=self._global_sequence_counter,
            request_started_at=_now(),
        )
        self._pending_turns[agent_name] = metadata

        file_path = self._output_directory / _build_filename(metadata, "request")
        payload = {
            "system_prompt": system_prompt,
            "input_items": input_items,
        }

        content = _render_markdown_request(agent, metadata, payload)
        await _write_text(file_path, content)
        await self._capture_state(metadata, "request")

    async def on_llm_end(
        self,
        context: RunContextWrapper[TContext],
        agent: Agent[TContext],
        response: Any,
    ) -> None:
        _ = context
        agent_name = agent.name or agent.__class__.__name__
        metadata = self._pending_turns.pop(agent_name, None)
        if metadata is None:
            self._global_sequence_counter += 1
            metadata = _TurnMetadata(
                agent_name=agent_name,
                agent_slug=_slugify(agent_name),
                turn=self._turn_counters.get(agent_name, 1),
                global_sequence=self._global_sequence_counter,
                request_started_at=_now(),
            )

        file_path = self._output_directory / _build_filename(metadata, "response")

        content = _render_markdown_response(agent, metadata, response)
        await _write_text(file_path, content)

    async def _capture_state(self, metadata: _TurnMetadata, kind: str) -> None:
        """可选：在每个回合的 request/response 旁保存截图和 DOM."""

        if not self._capture_browser_state or not self._playwright_server:
            return

        base = Path(_build_filename(metadata, kind)).with_suffix("")
        screenshot_path = self._output_directory / base.with_suffix(".png")
        dom_path = self._output_directory / base.with_suffix(".dom.yaml")
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        dom_path.parent.mkdir(parents=True, exist_ok=True)

        # DOM snapshot
        try:
            result = await self._playwright_server.call_tool("browser_snapshot", {})
            text_blocks = [
                getattr(item, "text", "")
                for item in getattr(result, "content", []) or []
                if getattr(item, "type", "") == "text"
            ]
            dom_text = "\n".join(text_blocks).strip()
            if dom_text:
                await _write_text(dom_path, dom_text)
        except Exception as exc:  # noqa: BLE001 - 只记录，不影响主流程
            logging.getLogger(__name__).warning(
                "Failed to capture DOM snapshot (%s %s): %s",
                metadata.agent_name,
                kind,
                exc,
            )

        # Screenshot
        try:
            await self._playwright_server.call_tool(
                "browser_take_screenshot",
                {
                    "filename": str(screenshot_path),
                    "fullPage": self._capture_full_page,
                },
            )
        except Exception as exc:  # noqa: BLE001 - 只记录，不影响主流程
            logging.getLogger(__name__).warning(
                "Failed to capture screenshot (%s %s): %s",
                metadata.agent_name,
                kind,
                exc,
            )


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip()).strip("_")
    return slug or "agent"


def _build_filename(metadata: _TurnMetadata, kind: str) -> str:
    return f"{metadata.global_sequence:03d}-{metadata.agent_slug}_turn_{metadata.turn:02d}_{kind}.md"


def _render_markdown_request(
    agent: Agent[Any],
    metadata: _TurnMetadata,
    payload: dict[str, Any],
) -> str:
    system_prompt = payload.get("system_prompt")
    input_items = payload.get("input_items") or []

    lines = [
        f"# LLM Request — {metadata.agent_name}",
        "",
        f"- Timestamp: {metadata.request_started_at.isoformat()}",
        f"- Agent: {metadata.agent_name}",
        f"- Turn: {metadata.turn}",
        f"- Model: {_describe_model(agent)}",
        f"- Input item count: {len(input_items)}",
    ]

    if system_prompt:
        lines.extend(
            [
                "",
                "## System Prompt",
                "",
                "```text",
                system_prompt,
                "```",
            ]
        )

    lines.extend(
        [
            "",
            "## Input Items",
            "",
            "```json",
            _dump_json(input_items),
            "```",
        ]
    )

    return "\n".join(lines) + "\n"


def _render_markdown_response(
    agent: Agent[Any],
    metadata: _TurnMetadata,
    response: Any,
) -> str:
    finished_at = _now()
    usage_dict = {}
    if getattr(response, "usage", None) is not None:
        usage_dict = dataclasses.asdict(response.usage)

    lines = [
        f"# LLM Response — {metadata.agent_name}",
        "",
        f"- Timestamp: {finished_at.isoformat()}",
        f"- Agent: {metadata.agent_name}",
        f"- Turn: {metadata.turn}",
        f"- Model: {_describe_model(agent)}",
        f"- Response ID: {getattr(response, 'response_id', 'unknown')}",
    ]

    request_started_at = metadata.request_started_at.isoformat()
    lines.append(f"- Request timestamp: {request_started_at}")

    if usage_dict:
        lines.extend(
            [
                "",
                "## Usage",
                "",
                "```json",
                _dump_json(usage_dict),
                "```",
            ]
        )

    output = getattr(response, "output", None)
    lines.extend(
        [
            "",
            "## Output Items",
            "",
            "```json",
            _dump_json(output or []),
            "```",
        ]
    )

    return "\n".join(lines) + "\n"


async def _write_text(path: Path, content: str) -> None:
    path = path.resolve()

    def _write() -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    await asyncio.to_thread(_write)


def _dump_json(value: Any) -> str:
    return json.dumps(_prepare_for_dump(value), ensure_ascii=False, indent=2)


def _describe_model(agent: Agent[Any]) -> str:
    model = getattr(agent, "model", None)
    if isinstance(model, str):
        return model
    if model is None:
        return "default"
    if hasattr(model, "model"):
        model_name = cast(Any, model).model
        return str(model_name)
    return type(model).__name__


def _now() -> datetime:
    return datetime.now(UTC)


def _prepare_for_dump(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return _prepare_for_dump(value.model_dump())
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return _prepare_for_dump(dataclasses.asdict(value))
    if isinstance(value, dict):
        return {k: _prepare_for_dump(v) for k, v in value.items()}
    if isinstance(value, list | tuple | set):
        return [_prepare_for_dump(v) for v in value]
    return value


__all__ = ["LLMTranscriptLoggerHooks"]
