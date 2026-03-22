from __future__ import annotations

from typing import Any

from runloop_agent.step import StepSpec
from runloop_agent.tool_registry import ToolInfo


def _validate_required_fields(tool: ToolInfo, arguments: dict[str, Any]) -> None:
    required = tool.input_schema.get("required") if isinstance(tool.input_schema, dict) else None
    if not isinstance(required, list):
        return
    missing = [name for name in required if name not in arguments]
    if missing:
        raise RuntimeError(f"missing required arguments for tool '{tool.name}': {missing}")


def _validate_generic_arguments(arguments: dict[str, Any]) -> None:
    if not isinstance(arguments, dict):
        raise RuntimeError("tool arguments must be a mapping")


def _validate_file_tool_arguments(arguments: dict[str, Any]) -> None:
    for key in ("path", "file_path", "target_path"):
        if key in arguments:
            value = arguments[key]
            if not isinstance(value, str) or not value.strip():
                raise RuntimeError(f"file tool argument '{key}' must be a non-empty string")


def _validate_jira_tool_arguments(arguments: dict[str, Any]) -> None:
    if "key" in arguments:
        value = arguments["key"]
        if not isinstance(value, str) or not value.strip():
            raise RuntimeError("jira tool argument 'key' must be a non-empty string")


def ensure_tool_allowed(spec: StepSpec, tool: ToolInfo, arguments: dict[str, Any]) -> None:
    allowed_tools = {str(x) for x in (spec.allowed_tools or []) if str(x).strip()}
    allowed_families = {str(x) for x in (spec.allowed_tool_families or []) if str(x).strip()}
    if allowed_tools and tool.name in allowed_tools:
        pass
    elif allowed_families and tool.family in allowed_families:
        pass
    else:
        raise RuntimeError(f"tool not allowed for step '{spec.step_id}': {tool.name}")

    _validate_generic_arguments(arguments)
    _validate_required_fields(tool, arguments)
    if tool.family == "files":
        _validate_file_tool_arguments(arguments)
    elif tool.family == "jira":
        _validate_jira_tool_arguments(arguments)
