from __future__ import annotations

import json
from collections.abc import Sequence

from agents import Agent, RunConfig, RunHooks, Tool
from agents.agent_output import AgentOutputSchema
from agents.mcp import MCPServerStdio
from agents.result import RunResult

from website_analytics.config import MODEL_NAME
from website_analytics.output_types import (
    CoordinatorOutput,
    ExtractOutput,
    InspectEntryOutput,
    InspectOutput,
    LoginOutput,
)


async def extract_structured_output(result: RunResult) -> str:
    """提取 agent 的结构化输出并序列化为 JSON。

    适用于所有具有结构化输出的 subagent。
    """
    if hasattr(result.final_output, "model_dump"):
        # Pydantic model
        return json.dumps(
            result.final_output.model_dump(), ensure_ascii=False, indent=2
        )
    return str(result.final_output)


def build_login_agent(playwright_server: MCPServerStdio, instructions: str) -> Agent:
    return Agent(
        name="loginAgent",
        instructions=instructions,
        mcp_servers=[playwright_server],
        model=MODEL_NAME,
        output_type=LoginOutput,
    )


def build_extract_agent(playwright_server: MCPServerStdio, instructions: str) -> Agent:
    return Agent(
        name="extractAgent",
        instructions=instructions,
        mcp_servers=[playwright_server],
        model=MODEL_NAME,
        output_type=ExtractOutput,
    )


def build_inspect_entry_agent(
    playwright_server: MCPServerStdio,
    instructions: str,
    extra_tools: Sequence[Tool] | None = None,
) -> Agent:
    return Agent(
        name="inspectEntryAgent",
        instructions=instructions,
        tools=[*extra_tools] if extra_tools else [],
        mcp_servers=[playwright_server],
        model=MODEL_NAME,
        output_type=InspectEntryOutput,
    )


def build_inspect_agent(
    playwright_server: MCPServerStdio,
    instructions: str,
    extra_tools: Sequence[Tool] | None = None,
) -> Agent:
    return Agent(
        name="inspectAgent",
        instructions=instructions,
        tools=[*extra_tools] if extra_tools else [],
        mcp_servers=[playwright_server],
        model=MODEL_NAME,
        output_type=InspectOutput,
    )


def build_coordinator_agent(
    login_agent: Agent,
    extract_agent: Agent,
    inspect_agent: Agent,
    coordinator_instructions: str,
    child_hooks: RunHooks | None = None,
    run_config: RunConfig | None = None,
    extra_tools: Sequence[Tool] | None = None,
) -> Agent:
    tools = [
        login_agent.as_tool(
            tool_name="perform_login",
            tool_description="使用浏览器自动化登录指定站点。",
            max_turns=20,
            hooks=child_hooks,
            run_config=run_config,
            custom_output_extractor=extract_structured_output,
        ),
        inspect_agent.as_tool(
            tool_name="perform_inspect",
            tool_description="巡检控制台一级菜单并保存截图。",
            max_turns=100,
            hooks=child_hooks,
            run_config=run_config,
            custom_output_extractor=extract_structured_output,
        ),
        extract_agent.as_tool(
            tool_name="perform_extract",
            tool_description="在已登录状态下提取订阅链接。",
            max_turns=25,
            hooks=child_hooks,
            run_config=run_config,
            custom_output_extractor=extract_structured_output,
        ),
    ]
    if extra_tools:
        tools.extend(extra_tools)

    return Agent(
        name="coordinatorAgent",
        instructions=coordinator_instructions,
        tools=tools,
        model=MODEL_NAME,
        output_type=AgentOutputSchema(CoordinatorOutput, strict_json_schema=False),
    )
