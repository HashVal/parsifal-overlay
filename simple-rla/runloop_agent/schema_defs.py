from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ToolSchema:
    name: str
    description: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    family: str | None = None
    server_name: str | None = None


@dataclass(slots=True)
class ModelToolSpec:
    name: str
    description: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    type: str = "function"

    def as_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters or {"type": "object", "properties": {}},
        }


@dataclass(slots=True)
class ToolResultEnvelope:
    tool_name: str
    success: bool
    content: Any
    server_name: str | None = None
    latency_ms: int = 0
    is_error: bool = False
    error: str | None = None
    raw: Any = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "server_name": self.server_name,
            "success": self.success,
            "latency_ms": self.latency_ms,
            "is_error": self.is_error,
            "error": self.error,
            "content": self.content,
            "raw": self.raw,
        }


UNIFIED_CONFIG_NOTES: dict[str, Any] = {
    "runtime": ["model", "timeout_s", "protocol_version"],
    "openai": ["api_key", "base_url"],
    "mcp": ["artifacts_root"],
    "mcp.servers.*": ["command", "args", "cwd", "env"],
}
