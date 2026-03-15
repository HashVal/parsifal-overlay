from __future__ import annotations

from runloop_agent.step import StepSpec
from runloop_agent.tool_registry import ToolInfo


def ensure_tool_allowed(spec: StepSpec, tool: ToolInfo) -> None:
    allowed_tools = {str(x) for x in (spec.allowed_tools or []) if str(x).strip()}
    allowed_families = {str(x) for x in (spec.allowed_tool_families or []) if str(x).strip()}
    if allowed_tools and tool.name in allowed_tools:
        return
    if allowed_families and tool.family in allowed_families:
        return
    raise RuntimeError(f"tool not allowed for step '{spec.step_id}': {tool.name}")
