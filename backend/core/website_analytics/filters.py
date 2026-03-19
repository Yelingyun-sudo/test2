from __future__ import annotations

import copy
import json
from collections.abc import Callable
from typing import Any, TypeVar, cast

from openai.types.responses.response_input_item_param import FunctionCallOutput

from agents.items import TResponseInputItem
from agents.logger import logger
from agents.run import CallModelData, ModelInputData

ContextT = TypeVar("ContextT")


def build_call_model_input_filter(
    compact_enabled: bool,
) -> Callable[[CallModelData[ContextT]], ModelInputData]:
    def _call_model_filter(data: CallModelData[ContextT]) -> ModelInputData:
        image_filtered = filter_large_image_data(data)
        next_data = CallModelData(
            model_data=image_filtered,
            agent=data.agent,
            context=data.context,
        )
        return compact_tool_outputs(
            next_data,
            keep_last=1,
            enabled=compact_enabled,
        )

    return _call_model_filter


_TOOL_OUTPUT_TYPES: set[str] = {
    "function_call_output",
    "computer_call_output",
    "local_shell_call_output",
}

# 需要保留完整输出的重要工具列表（这些工具的输出不会被 compact 压缩）
_PRESERVE_TOOL_NAMES: set[str] = {
    "fetch_email_code",  # 验证码工具的输出必须保留，否则 Agent 无法获取验证码
}


def compact_tool_outputs(
    data: CallModelData[Any],
    *,
    keep_last: int = 1,
    enabled: bool = True,
) -> ModelInputData:
    """Replace older tool outputs with short placeholders to shrink model input."""
    cloned_input: list[TResponseInputItem] = []
    tool_output_indexes: list[int] = []
    perform_compaction = enabled and keep_last >= 0

    # 构建 call_id -> tool_name 映射（用于白名单检查）
    call_id_to_tool_name: dict[str, str] = {}
    for item in data.model_data.input:
        if isinstance(item, dict) and item.get("type") == "function_call":
            call_id = item.get("call_id")
            tool_name = item.get("name")
            if call_id and tool_name:
                call_id_to_tool_name[call_id] = tool_name

    for item in data.model_data.input:
        cloned = copy.deepcopy(item)
        item_type = _get_item_type(cloned)

        if item_type == "reasoning":
            continue

        if (
            perform_compaction
            and item_type in _TOOL_OUTPUT_TYPES
            and isinstance(cloned, dict)
        ):
            tool_output_indexes.append(len(cloned_input))

        cloned_input.append(cloned)

    if perform_compaction and len(tool_output_indexes) > keep_last:
        cutoff = len(tool_output_indexes) - keep_last
        for idx in tool_output_indexes[:cutoff]:
            entry = cloned_input[idx]
            if isinstance(entry, dict):
                entry_dict = cast(dict[str, Any], entry)
                # 通过 call_id 查找工具名称，检查是否在白名单中
                call_id = entry_dict.get("call_id") or ""
                tool_name = call_id_to_tool_name.get(call_id, "")
                if tool_name in _PRESERVE_TOOL_NAMES:
                    continue  # 跳过白名单中的工具，保留其完整输出
                entry_dict["output"] = _placeholder_output(entry_dict)

    return ModelInputData(
        input=cloned_input,
        instructions=data.model_data.instructions,
    )


def _get_item_type(item: TResponseInputItem) -> str | None:
    if isinstance(item, dict):
        return item.get("type")
    return getattr(item, "type", None)


def _placeholder_output(entry: dict[str, Any]) -> str:
    call_id = entry.get("call_id")
    tool_name = entry.get("name") or entry.get("tool_name") or "tool"
    placeholder_text = (
        f"[Omitted previous output from {tool_name}"
        f"{f' (call_id={call_id})' if call_id else ''}. "
        "Refer to local logs for full details.]"
    )
    return placeholder_text


def filter_large_image_data(data: CallModelData[Any]) -> ModelInputData:
    """Remove large base64 image payloads from tool outputs to reduce context usage."""
    filtered_input: list[TResponseInputItem] = []
    removed_images_count = 0
    total_saved_bytes = 0

    for item in data.model_data.input:
        if not isinstance(item, dict) or item.get("type") != "function_call_output":
            filtered_input.append(copy.deepcopy(item))
            continue

        function_output = cast(FunctionCallOutput, item)
        output = function_output.get("output")
        if not output or not isinstance(output, str):
            filtered_input.append(copy.deepcopy(function_output))
            continue

        try:
            parsed_output = json.loads(output)
        except (json.JSONDecodeError, ValueError):
            filtered_input.append(copy.deepcopy(function_output))
            continue

        if isinstance(parsed_output, list):
            filtered_contents = []
            for content_item in parsed_output:
                if (
                    isinstance(content_item, dict)
                    and content_item.get("type") == "image"
                ):
                    image_data = content_item.get("data", "")
                    if image_data:
                        removed_images_count += 1
                        total_saved_bytes += len(image_data)
                        filtered_contents.append(
                            {
                                "type": "image",
                                "mimeType": content_item.get("mimeType", "image/png"),
                                "_filtered": True,
                                "_note": (
                                    "Image data removed to reduce context usage."
                                    " File saved by MCP server."
                                ),
                            }
                        )
                    else:
                        filtered_contents.append(content_item)
                else:
                    filtered_contents.append(content_item)

            modified_item: FunctionCallOutput = copy.deepcopy(function_output)
            modified_item["output"] = json.dumps(filtered_contents, ensure_ascii=False)
            filtered_input.append(modified_item)
        elif isinstance(parsed_output, dict) and parsed_output.get("type") == "image":
            image_data = parsed_output.get("data", "")
            if image_data:
                removed_images_count += 1
                total_saved_bytes += len(image_data)
                modified_item = copy.deepcopy(function_output)
                modified_item["output"] = json.dumps(
                    {
                        "type": "image",
                        "mimeType": parsed_output.get("mimeType", "image/png"),
                        "_filtered": True,
                        "_note": (
                            "Image data removed to reduce context usage. File saved by MCP server."
                        ),
                    },
                    ensure_ascii=False,
                )
                filtered_input.append(modified_item)
            else:
                filtered_input.append(copy.deepcopy(function_output))
        else:
            filtered_input.append(copy.deepcopy(function_output))

    if removed_images_count > 0:
        saved_kb = total_saved_bytes / 1024
        logger.info(
            "Image data filter: removed %d image(s), saved ~%.1f KB from context",
            removed_images_count,
            saved_kb,
        )

    return ModelInputData(
        input=filtered_input,
        instructions=data.model_data.instructions,
    )


__all__ = [
    "build_call_model_input_filter",
    "compact_tool_outputs",
    "filter_large_image_data",
]
