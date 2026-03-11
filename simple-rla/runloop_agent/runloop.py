from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from .config import RunloopConfig
from .mcp_stdio_client import McpStdioClient, McpToolSpec, RunloopArtifacts


@dataclass(frozen=True)
class ToolCall:
    tool: str
    args: dict


@dataclass(frozen=True)
class ToolCallRecord:
    tool: str
    args: dict
    result_text: str
    request_ref: str
    response_ref: str


class ToolRouter:
    """Routes tool calls of the form "server.tool" to the right MCP server.

    If the tool name has no prefix, and exactly one server is registered, it is used.
    """

    def __init__(self, cfg: RunloopConfig) -> None:
        self._cfg = cfg
        self._clients: dict[str, McpStdioClient] = {}
        self._tools: dict[str, McpToolSpec] = {}

    async def start(self) -> None:
        for s in self._cfg.servers:
            client = McpStdioClient(
                name=self._cfg.client_name,
                command=s.command,
                args=s.args,
                env=s.env,
                protocol_version=self._cfg.protocol_version,
                cwd=s.cwd,
            )
            await client.start()
            await client.initialize(client_version=self._cfg.client_version)
            self._clients[s.name] = client

        await self.refresh_tools()

    async def close(self) -> None:
        for c in self._clients.values():
            await c.close()
        self._clients.clear()
        self._tools.clear()

    async def refresh_tools(self) -> None:
        tools: dict[str, McpToolSpec] = {}
        for server_name, client in self._clients.items():
            for spec in await client.list_tools():
                fq = f"{server_name}.{spec.name}"
                tools[fq] = spec
        self._tools = tools

    def list_tools(self) -> dict[str, McpToolSpec]:
        return dict(self._tools)

    def _split(self, tool: str) -> Tuple[str, str]:
        if "." in tool:
            server, name = tool.split(".", 1)
            return server, name
        if len(self._clients) == 1:
            (server,) = list(self._clients.keys())
            return server, tool
        raise ValueError(f"Tool name must be qualified as <server>.<tool>: {tool}")

    async def call_tool(self, tool: str, args: dict) -> str:
        server, name = self._split(tool)
        client = self._clients.get(server)
        if client is None:
            raise ValueError(f"Unknown server: {server}")

        result = await client.call_tool(name=name, arguments=args)
        return result.text


class Budget:
    def __init__(self, *, max_device_calls: int = 20, max_code_calls: int = 30) -> None:
        self.max_device_calls = max_device_calls
        self.max_code_calls = max_code_calls
        self.device_calls = 0
        self.code_calls = 0

    def can_call(self, tool_name: str) -> bool:
        if tool_name.startswith("device_exec"):
            return self.device_calls < self.max_device_calls
        if tool_name.startswith("code_scan"):
            return self.code_calls < self.max_code_calls
        return True

    def record(self, tool_name: str) -> None:
        if tool_name.startswith("device_exec"):
            self.device_calls += 1
        elif tool_name.startswith("code_scan"):
            self.code_calls += 1


class RunloopAgent:
    """A tiny runloop executor.

    For demo purposes this agent does not implement an LLM planner.

    It provides:

    - MCP tool router (multi-server)
    - per-run artifacts capture (request+response JSON)
    - basic budget accounting
    """

    def __init__(self, cfg: RunloopConfig) -> None:
        self._cfg = cfg
        self._router = ToolRouter(cfg)
        self._artifacts = RunloopArtifacts(cfg.artifacts_root)

    async def __aenter__(self) -> "RunloopAgent":
        await self._router.start()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self._router.close()

    def list_tools(self) -> dict[str, McpToolSpec]:
        return self._router.list_tools()

    async def call_tool(self, tool: str, args: dict) -> str:
        return await self._router.call_tool(tool, args)

    async def run_scripted(
        self,
        *,
        issue_id: str,
        calls: list[ToolCall],
        budget: Optional[Budget] = None,
    ) -> list[ToolCallRecord]:
        run_dir = self._artifacts.init_run_dir(issue_id)
        budget = budget or Budget()

        records: list[ToolCallRecord] = []

        for idx, call in enumerate(calls, start=1):
            fq_tool = call.tool

            # Budget gating (best-effort; device/code servers should still enforce on their side).
            # We gate by unqualified prefix; users typically call "device_exec.exec" etc.
            unqualified = fq_tool.split(".", 1)[-1]
            if not budget.can_call(unqualified):
                raise RuntimeError(f"Budget exceeded for tool: {fq_tool}")

            req_ref = self._artifacts.save_json(
                run_dir,
                f"{idx:03d}_request.json",
                {"tool": fq_tool, "args": call.args},
            )

            text = await self._router.call_tool(fq_tool, call.args)

            resp_ref = self._artifacts.save_json(
                run_dir,
                f"{idx:03d}_response.json",
                {"tool": fq_tool, "text": text},
            )

            budget.record(unqualified)

            records.append(
                ToolCallRecord(
                    tool=fq_tool,
                    args=call.args,
                    result_text=text,
                    request_ref=req_ref.ref,
                    response_ref=resp_ref.ref,
                )
            )

        return records


def load_script(path: str) -> list[ToolCall]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    calls_raw = raw.get("calls") if isinstance(raw, dict) else raw
    if not isinstance(calls_raw, list):
        raise ValueError("script must be a list or {calls:[...]} JSON")

    calls: list[ToolCall] = []
    for c in calls_raw:
        if not isinstance(c, dict):
            continue
        tool = str(c.get("tool") or "")
        args = c.get("args") or {}
        if not tool:
            raise ValueError(f"script call missing tool: {c}")
        if not isinstance(args, dict):
            raise ValueError(f"script call args must be object: {c}")
        calls.append(ToolCall(tool=tool, args=args))

    return calls
