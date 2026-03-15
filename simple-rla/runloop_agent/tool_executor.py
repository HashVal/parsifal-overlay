from __future__ import annotations

import time
from typing import Any

from runloop_agent.mcp_client import McpClient
from runloop_agent.step import StepSpec, StepToolCall
from runloop_agent.tool_permission import ensure_tool_allowed
from runloop_agent.tool_registry import ToolRegistry


def execute_tool_call(
    *,
    mcp_client: McpClient,
    registry: ToolRegistry,
    spec: StepSpec,
    tool_name: str,
    arguments: dict[str, Any],
) -> tuple[StepToolCall, list[dict[str, Any]]]:
    tool = registry.get(tool_name)
    if tool is None:
        raise RuntimeError(f"unknown tool requested by model: {tool_name}")
    ensure_tool_allowed(spec, tool)

    started = time.time()
    result = mcp_client.call_tool(tool_name, arguments)
    latency_ms = int((time.time() - started) * 1000)

    step_tool_call = StepToolCall(
        tool_name=tool_name,
        arguments=dict(arguments),
        result=result.content,
        success=not result.is_error,
        latency_ms=latency_ms,
        server_name=result.server_name,
    )
    tool_messages = [
        {
            "role": "tool",
            "name": tool_name,
            "content": result.content,
            "is_error": result.is_error,
        }
    ]
    return step_tool_call, tool_messages
