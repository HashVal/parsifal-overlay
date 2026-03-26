from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from runloop_agent.mcp_client import McpTool
from runloop_agent.schema_defs import ModelToolSpec, ToolSchema


@dataclass(slots=True)
class ToolInfo:
    name: str
    description: str
    input_schema: dict[str, Any]
    family: str
    server_name: str

    def as_schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=self.input_schema or {"type": "object", "properties": {}},
            family=self.family,
            server_name=self.server_name,
        )

    def to_model_tool(self) -> dict[str, Any]:
        return ModelToolSpec(
            name=self.name,
            description=self.description,
            parameters=self.input_schema or {"type": "object", "properties": {}},
        ).as_dict()


def infer_tool_family(tool: McpTool) -> str:
    if tool.name.startswith("code_") or tool.server_name == "code":
        return "code"
    if tool.name.startswith("jira_") or tool.server_name == "jira":
        return "jira"
    if tool.name.startswith("kb_") or tool.server_name == "kb":
        return "kb"
    if tool.name.startswith("file_") or tool.name.startswith("log_") or tool.server_name == "files":
        return "files"
    return tool.server_name


class ToolRegistry:
    def __init__(self, tools: list[McpTool]) -> None:
        self._tools = {
            tool.name: ToolInfo(
                name=tool.name,
                description=tool.description,
                input_schema=tool.input_schema,
                family=infer_tool_family(tool),
                server_name=tool.server_name,
            )
            for tool in tools
        }

    def get(self, name: str) -> ToolInfo | None:
        return self._tools.get(name)

    def list_all(self) -> list[ToolInfo]:
        return list(self._tools.values())

    def list_schemas(self) -> list[ToolSchema]:
        return [tool.as_schema() for tool in self._tools.values()]

    def select(self, allowed_tools: list[str] | tuple[str, ...] | None, allowed_families: list[str] | tuple[str, ...] | None) -> list[ToolInfo]:
        tool_set = {str(x) for x in (allowed_tools or []) if str(x).strip()}
        family_set = {str(x) for x in (allowed_families or []) if str(x).strip()}
        if not tool_set and not family_set:
            return []
        out: list[ToolInfo] = []
        for tool in self._tools.values():
            if tool_set and tool.name in tool_set:
                out.append(tool)
                continue
            if family_set and tool.family in family_set:
                out.append(tool)
        return out
