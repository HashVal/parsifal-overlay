"""A tiny MCP-compatible stdio JSON-RPC server (stdlib only).

This is not a complete MCP implementation; it's the minimal subset required for:

- initialize
- tools/list
- tools/call

Protocol:
- newline-delimited JSON messages on stdin/stdout
- JSON-RPC 2.0 envelope

Tool call result format (MCP-style):
{
  "content": [{"type": "text", "text": "..."}],
  "isError": false
}

"""

from __future__ import annotations

import json
import sys
import traceback
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Callable, Dict, Optional


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    input_schema: dict
    handler: Callable[[dict], Any]


def _json_default(obj: Any) -> Any:
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")


def _json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, default=_json_default)


def _ok_text(text: str) -> dict:
    return {"content": [{"type": "text", "text": text}], "isError": False}


def _err_text(text: str) -> dict:
    return {"content": [{"type": "text", "text": text}], "isError": True}


class StdioMcpServer:
    def __init__(self, *, name: str, version: str = "0.1", protocol_version: str = "2024-11-05") -> None:
        self._name = name
        self._version = version
        self._protocol_version = protocol_version
        self._tools: dict[str, Tool] = {}

    def add_tool(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"duplicate tool: {tool.name}")
        self._tools[tool.name] = tool

    def _handle_initialize(self, params: dict) -> dict:
        # Minimal response; many clients only need serverInfo.
        return {
            "protocolVersion": self._protocol_version,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": self._name, "version": self._version},
        }

    def _handle_tools_list(self, params: dict) -> dict:
        tools = []
        for t in self._tools.values():
            tools.append({
                "name": t.name,
                "description": t.description,
                "inputSchema": t.input_schema,
            })
        return {"tools": tools}

    def _handle_tools_call(self, params: dict) -> dict:
        name = params.get("name")
        arguments = params.get("arguments")
        if not isinstance(name, str) or not name:
            return _err_text("missing tool name")
        if not isinstance(arguments, dict):
            arguments = {}

        tool = self._tools.get(name)
        if tool is None:
            return _err_text(f"unknown tool: {name}")

        try:
            out = tool.handler(arguments)
            if isinstance(out, str):
                return _ok_text(out)
            return _ok_text(_json(out))
        except Exception as exc:
            tb = traceback.format_exc(limit=8)
            return _err_text(f"tool error: {exc}\n{tb}")

    def _dispatch(self, method: str, params: dict) -> dict:
        if method == "initialize":
            return self._handle_initialize(params)
        if method == "tools/list":
            return self._handle_tools_list(params)
        if method == "tools/call":
            return self._handle_tools_call(params)

        # Notifications (no id) are ignored.
        if method.startswith("notifications/"):
            return {}

        raise ValueError(f"unsupported method: {method}")

    def run_forever(self) -> None:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue

            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue

            if not isinstance(msg, dict):
                continue

            msg_id = msg.get("id")
            method = msg.get("method")
            params = msg.get("params")

            if not isinstance(method, str):
                continue
            if not isinstance(params, dict):
                params = {}

            # Notifications: no response expected.
            if msg_id is None:
                try:
                    self._dispatch(method, params)
                except Exception:
                    pass
                continue

            resp: dict
            try:
                result = self._dispatch(method, params)
                resp = {"jsonrpc": "2.0", "id": msg_id, "result": result}
            except Exception as exc:
                resp = {"jsonrpc": "2.0", "id": msg_id, "error": {"message": str(exc)}}

            sys.stdout.write(_json(resp) + "\n")
            sys.stdout.flush()
