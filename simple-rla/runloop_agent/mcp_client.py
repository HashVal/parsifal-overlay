from __future__ import annotations

import json
import logging
import os
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from runloop_agent.runtime_config import McpServerConfig, RuntimeConfig

log = logging.getLogger("simple_rla.mcp_client")
_JSONRPC = "2.0"


@dataclass(slots=True)
class McpTool:
    name: str
    description: str
    input_schema: dict[str, Any]
    server_name: str


@dataclass(slots=True)
class McpToolCallResult:
    tool_name: str
    server_name: str
    arguments: dict[str, Any]
    content: Any
    is_error: bool = False
    raw_content: Any = None


def _decode_mcp_content(content: Any) -> Any:
    if not isinstance(content, list) or len(content) != 1:
        return content
    item = content[0]
    if not isinstance(item, dict):
        return content
    if item.get("type") != "text":
        return content
    text = item.get("text")
    if not isinstance(text, str):
        return content
    stripped = text.strip()
    if not stripped:
        return ""
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return text


class _StdioSession:
    def __init__(self, server: McpServerConfig, *, protocol_version: str | None, workspace_root: str | None) -> None:
        self.server = server
        self.protocol_version = protocol_version or "2024-11-05"
        self.workspace_root = workspace_root
        self._proc: subprocess.Popen[str] | None = None
        self._lock = threading.Lock()
        self._id = 0
        self._stderr_thread: threading.Thread | None = None

    def start(self) -> None:
        env = os.environ.copy()
        env.update(self.server.env)
        if self.workspace_root:
            workspace_root = Path(self.workspace_root).resolve()
            env.setdefault("SIMPLE_RLA_WORKSPACE_DIR", str(workspace_root))
            env.setdefault("FILE_TOOLS_ROOT", str(workspace_root))
            env.setdefault("SIMPLE_RLA_ATTACHMENTS_DIR", str((workspace_root / "attachments").resolve()))
        cwd = self.server.cwd or None
        self._proc = subprocess.Popen(
            [self.server.command, *self.server.args],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
            cwd=cwd,
            env=env,
        )
        self._stderr_thread = threading.Thread(target=self._drain_stderr, name=f"mcp-stderr-{self.server.name}", daemon=True)
        self._stderr_thread.start()
        self._rpc(
            "initialize",
            {
                "protocolVersion": self.protocol_version,
                "clientInfo": {"name": "simple-rla-skeleton", "version": "0.2"},
                "capabilities": {},
            },
        )

    def close(self) -> None:
        proc = self._proc
        self._proc = None
        if proc is None:
            return
        try:
            if proc.stdin:
                proc.stdin.close()
        except Exception:
            pass
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    def list_tools(self) -> list[McpTool]:
        result = self._rpc("tools/list", {})
        tools = result.get("tools") if isinstance(result, dict) else []
        out: list[McpTool] = []
        for item in tools or []:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            out.append(McpTool(
                name=name,
                description=str(item.get("description") or ""),
                input_schema=dict(item.get("inputSchema") or item.get("input_schema") or {}),
                server_name=self.server.name,
            ))
        return out

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> McpToolCallResult:
        result = self._rpc("tools/call", {"name": tool_name, "arguments": arguments})
        raw_content = result.get("content") if isinstance(result, dict) else result
        decoded_content = _decode_mcp_content(raw_content)
        is_error = bool(result.get("isError")) if isinstance(result, dict) else False
        return McpToolCallResult(
            tool_name=tool_name,
            server_name=self.server.name,
            arguments=dict(arguments),
            content=decoded_content,
            is_error=is_error,
            raw_content=raw_content,
        )

    def _drain_stderr(self) -> None:
        proc = self._proc
        if proc is None or proc.stderr is None:
            return
        for line in proc.stderr:
            msg = line.rstrip()
            if msg:
                log.info("mcp.stderr server=%s %s", self.server.name, msg)

    def _rpc(self, method: str, params: dict[str, Any], timeout_s: int = 30) -> Any:
        proc = self._proc
        if proc is None or proc.stdin is None or proc.stdout is None:
            raise RuntimeError(f"MCP server not running: {self.server.name}")
        with self._lock:
            self._id += 1
            req_id = self._id
            payload = {"jsonrpc": _JSONRPC, "id": req_id, "method": method, "params": params}
            proc.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
            proc.stdin.flush()
            deadline = time.time() + timeout_s
            while True:
                if time.time() > deadline:
                    raise RuntimeError(f"MCP request timed out: server={self.server.name} method={method}")
                line = proc.stdout.readline()
                if not line:
                    raise RuntimeError(f"MCP server closed stream: {self.server.name}")
                msg = json.loads(line)
                if msg.get("id") != req_id:
                    continue
                if "error" in msg:
                    raise RuntimeError(f"MCP error from {self.server.name} method={method}: {msg['error']}")
                return msg.get("result")


class McpClient:
    def __init__(self, cfg: RuntimeConfig, *, workspace_root: str | None = None) -> None:
        self._cfg = cfg
        self._workspace_root = workspace_root or cfg.artifacts_root
        self._sessions: dict[str, _StdioSession] = {}
        self._tools: dict[str, McpTool] = {}

    def start(self) -> None:
        if self._sessions:
            return
        for server in self._cfg.mcp_servers:
            sess = _StdioSession(server, protocol_version=self._cfg.protocol_version, workspace_root=self._workspace_root)
            sess.start()
            self._sessions[server.name] = sess
        self.refresh_tools()

    def close(self) -> None:
        sessions = list(self._sessions.values())
        self._sessions.clear()
        self._tools.clear()
        for sess in sessions:
            sess.close()

    def refresh_tools(self) -> list[McpTool]:
        tools: dict[str, McpTool] = {}
        for server_name, sess in self._sessions.items():
            for tool in sess.list_tools():
                if tool.name in tools:
                    raise RuntimeError(f"duplicate MCP tool name discovered: {tool.name}")
                tools[tool.name] = tool
                log.info("mcp.tool.discovered server=%s tool=%s", server_name, tool.name)
        self._tools = tools
        return list(self._tools.values())

    def list_tools(self) -> list[McpTool]:
        return list(self._tools.values())

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> McpToolCallResult:
        tool = self._tools.get(tool_name)
        if tool is None:
            raise RuntimeError(f"unknown MCP tool: {tool_name}")
        sess = self._sessions.get(tool.server_name)
        if sess is None:
            raise RuntimeError(f"MCP session not found for server: {tool.server_name}")
        return sess.call_tool(tool_name, arguments)
