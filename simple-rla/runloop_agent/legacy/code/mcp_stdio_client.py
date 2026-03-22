"""Minimal MCP stdio client (JSON-RPC 2.0 over newline-delimited stdio).

This is intentionally small and dependency-free (stdlib only).

It is sufficient for:

- initialize
- tools/list
- tools/call

The MCP server process is spawned as a subprocess.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


logger = logging.getLogger("simple_rla.mcp")


class McpError(RuntimeError):
    pass


class McpProtocolError(McpError):
    pass


@dataclass(frozen=True)
class McpToolSpec:
    name: str
    description: str
    input_schema: dict


@dataclass(frozen=True)
class McpCallResult:
    # Raw JSON-RPC result payload for tools/call.
    raw: dict
    # Concatenated text blocks from `content` (best-effort).
    text: str


def _json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def _extract_text_content(tool_call_result: dict) -> str:
    # MCP tool call result format typically:
    # {"content": [{"type": "text", "text": "..."}, ...], "isError": false}
    content = tool_call_result.get("content")
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            parts.append(str(block))
            continue
        if block.get("type") == "text" and isinstance(block.get("text"), str):
            parts.append(block["text"])
        else:
            # Keep non-text blocks visible for debugging.
            parts.append(_json_dumps(block))
    return "\n".join(p for p in parts if p).strip()


class McpStdioClient:
    def __init__(
        self,
        *,
        name: str,
        command: str,
        args: list[str],
        env: Optional[Dict[str, str]] = None,
        protocol_version: str = "2024-11-05",
        cwd: Optional[str] = None,
        server_label: str = "mcp",
        request_timeout_s: float = 60.0,
    ) -> None:
        self._name = name
        self._command = command
        self._args = args
        self._env = {**os.environ, **(env or {})}
        self._env_override_keys = list((env or {}).keys())
        self._protocol_version = protocol_version
        self._cwd = cwd
        self._server_label = server_label
        self._request_timeout_s = request_timeout_s

        self._proc: Optional[asyncio.subprocess.Process] = None
        self._reader_task: Optional[asyncio.Task] = None
        self._stderr_task: Optional[asyncio.Task] = None

        self._next_id = 1
        self._pending: dict[int, asyncio.Future] = {}
        self._closed = False

    async def start(self) -> None:
        if self._proc is not None:
            return

        safe_keys = []
        for k in self._env_override_keys:
            if any(s in k.upper() for s in ("TOKEN", "KEY", "SECRET", "PASSWORD")):
                safe_keys.append(f"{k}=<redacted>")
            else:
                safe_keys.append(k)

        logger.info(
            "mcp.start server=%s cmd=%s args=%s cwd=%s env_overrides=%s",
            self._server_label,
            self._command,
            self._args,
            self._cwd,
            safe_keys,
        )

        self._proc = await asyncio.create_subprocess_exec(
            self._command,
            *self._args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self._env,
            cwd=self._cwd,
        )
        assert self._proc.stdout is not None
        self._reader_task = asyncio.create_task(self._read_loop(), name=f"mcp-read:{self._server_label}")
        self._reader_task.add_done_callback(self._on_bg_task_done)

        # Drain stderr in the background so server logging doesn't deadlock.
        assert self._proc.stderr is not None
        self._stderr_task = asyncio.create_task(self._drain_stderr(), name=f"mcp-stderr:{self._server_label}")
        self._stderr_task.add_done_callback(self._on_bg_task_done)

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True

        logger.info("mcp.close server=%s", self._server_label)

        if self._reader_task is not None:
            self._reader_task.cancel()
        if self._stderr_task is not None:
            self._stderr_task.cancel()

        if self._proc is not None:
            try:
                self._proc.terminate()
            except ProcessLookupError:
                pass
            try:
                await asyncio.wait_for(self._proc.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                try:
                    self._proc.kill()
                except ProcessLookupError:
                    pass

        # Fail any pending requests.
        for fut in list(self._pending.values()):
            if not fut.done():
                fut.set_exception(McpError("client closed"))
        self._pending.clear()

    async def initialize(self, *, client_version: str = "0.1") -> dict:
        params = {
            "protocolVersion": self._protocol_version,
            "capabilities": {},
            "clientInfo": {"name": self._name, "version": client_version},
        }
        result = await self._request("initialize", params)

        # Some servers expect this notification after initialize.
        await self._notify("notifications/initialized", {})
        return result

    async def list_tools(self) -> list[McpToolSpec]:
        result = await self._request("tools/list", {})
        tools = result.get("tools")
        if not isinstance(tools, list):
            raise McpProtocolError(f"tools/list returned unexpected payload: {result}")

        specs: list[McpToolSpec] = []
        for t in tools:
            if not isinstance(t, dict):
                continue
            specs.append(
                McpToolSpec(
                    name=str(t.get("name") or ""),
                    description=str(t.get("description") or ""),
                    input_schema=t.get("inputSchema") or {},
                )
            )
        return specs

    async def call_tool(self, name: str, arguments: dict) -> McpCallResult:
        logger.info("mcp.tools/call server=%s tool=%s", self._server_label, name)
        result = await self._request("tools/call", {"name": name, "arguments": arguments})
        text = _extract_text_content(result)
        return McpCallResult(raw=result, text=text)

    def _on_bg_task_done(self, task: asyncio.Task) -> None:
        # Consume exceptions to avoid "Task exception was never retrieved".
        try:
            exc = task.exception()
        except asyncio.CancelledError:
            return
        except Exception:
            return

        if exc is not None:
            logger.error("mcp.bg_task_error server=%s task=%s err=%s", self._server_label, task.get_name(), exc)

    async def _drain_stderr(self) -> None:
        assert self._proc is not None
        assert self._proc.stderr is not None
        try:
            while True:
                line = await self._proc.stderr.readline()
                if not line:
                    return
                s = line.decode("utf-8", errors="replace").rstrip("\n")
                if s:
                    logger.info("mcp.stderr server=%s %s", self._server_label, s)
        except asyncio.CancelledError:
            return

    async def _read_loop(self) -> None:
        assert self._proc is not None
        assert self._proc.stdout is not None

        try:
            while True:
                line = await self._proc.stdout.readline()
                if not line:
                    if self._closed:
                        return
                    raise McpError("server stdout closed")

                try:
                    msg = json.loads(line.decode("utf-8", errors="replace"))
                except json.JSONDecodeError as exc:
                    raise McpProtocolError(f"invalid JSON from server: {line!r}") from exc

                if not isinstance(msg, dict):
                    continue

                msg_id = msg.get("id")
                if msg_id is None:
                    # notification / server-initiated; ignore for now
                    continue
                if not isinstance(msg_id, int):
                    continue

                fut = self._pending.pop(msg_id, None)
                if fut is None:
                    continue

                if "error" in msg:
                    fut.set_exception(McpError(str(msg["error"])))
                    continue

                fut.set_result(msg.get("result"))
        except asyncio.CancelledError:
            return

    async def _write(self, msg: dict) -> None:
        if self._proc is None or self._proc.stdin is None:
            raise McpError("client not started")
        data = (_json_dumps(msg) + "\n").encode("utf-8")
        self._proc.stdin.write(data)
        await self._proc.stdin.drain()

    async def _request(self, method: str, params: dict) -> dict:
        req_id = self._next_id
        self._next_id += 1

        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pending[req_id] = fut

        logger.debug("mcp.request server=%s id=%s method=%s", self._server_label, req_id, method)
        await self._write({"jsonrpc": "2.0", "id": req_id, "method": method, "params": params})

        try:
            res = await asyncio.wait_for(fut, timeout=self._request_timeout_s)
        except asyncio.TimeoutError as exc:
            self._pending.pop(req_id, None)
            raise McpError(f"timeout waiting for {method} (server={self._server_label})") from exc

        if not isinstance(res, dict):
            raise McpProtocolError(f"{method} returned non-object result: {res!r}")
        return res

    async def _notify(self, method: str, params: dict) -> None:
        await self._write({"jsonrpc": "2.0", "method": method, "params": params})


@dataclass(frozen=True)
class ToolRef:
    """A short reference to a stored tool call."""

    ref: str
    path: str


class RunloopArtifacts:
    """Stores tool-call requests/responses for audit and ref-based citations."""

    def __init__(self, artifacts_root: Path) -> None:
        self._root = artifacts_root

    def init_run_dir(self, issue_id: str) -> Path:
        ts = time.strftime("%Y-%m-%dT%H%M%SZ", time.gmtime())
        run_dir = self._root / issue_id / ts
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    def save_json(self, run_dir: Path, filename: str, payload: dict) -> ToolRef:
        path = run_dir / filename
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        ref = str(path)
        return ToolRef(ref=ref, path=str(path))
