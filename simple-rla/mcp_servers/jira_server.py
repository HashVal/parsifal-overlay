#!/usr/bin/env python3
"""Jira MCP server (stdlib only).

Supports Jira Server/Data Center (API v2) and Jira Cloud (API v3) with the same tool surface.

Env:
- JIRA_BASE_URL: e.g. https://jira.devtools.mycompany.com
- JIRA_API_PREFIX: default /rest/api/2 (server/DC), use /rest/api/3 for cloud
- JIRA_AUTH: basic|bearer (default: basic)
- JIRA_USER: username/email (for basic)
- JIRA_TOKEN: password/api_token (for basic) OR token (for bearer)
- JIRA_VERIFY_SSL: true|false (default: true)
- JIRA_TIMEOUT_S: request timeout (default: 30)

Tools:
- jira_search(jql, fields?, start_at?, max_results?)
- jira_get(key, fields?)
- jira_comment(key, body)
- jira_transitions(key)
- jira_transition(key, transition_id)

"""

from __future__ import annotations

import base64
import json
import logging
import os
import ssl
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Optional

from .stdio_jsonrpc_server import StdioMcpServer, Tool


logger = logging.getLogger("simple_rla.jira")


def _env_bool(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "y", "on")


def _env_int(name: str, default: int) -> int:
    v = os.environ.get(name)
    if v is None:
        return default
    try:
        return int(v)
    except ValueError:
        return default


@dataclass(frozen=True)
class JiraConfig:
    base_url: str
    api_prefix: str
    auth: str
    user: str
    token: str
    verify_ssl: bool
    timeout_s: int


class JiraClient:
    def __init__(self, cfg: JiraConfig) -> None:
        self._cfg = cfg

    def _headers(self) -> dict[str, str]:
        h = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        auth = self._cfg.auth
        if auth == "basic":
            raw = f"{self._cfg.user}:{self._cfg.token}".encode("utf-8")
            b64 = base64.b64encode(raw).decode("ascii")
            h["Authorization"] = f"Basic {b64}"
        elif auth == "bearer":
            h["Authorization"] = f"Bearer {self._cfg.token}"
        else:
            raise ValueError(f"unsupported JIRA_AUTH: {auth}")

        return h

    def _ssl_context(self) -> Optional[ssl.SSLContext]:
        if self._cfg.verify_ssl:
            return None
        return ssl._create_unverified_context()  # noqa: SLF001

    def _url(self, path: str, query: dict[str, str] | None = None) -> str:
        base = self._cfg.base_url.rstrip("/")
        prefix = self._cfg.api_prefix.rstrip("/")
        if not path.startswith("/"):
            path = "/" + path
        url = base + prefix + path
        if query:
            url += "?" + urllib.parse.urlencode(query)
        return url

    def request_json(self, method: str, path: str, *, query: dict[str, str] | None = None, body: Any | None = None) -> Any:
        data = None
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")

        url = self._url(path, query=query)
        logger.info("jira.request %s %s", method, url)

        req = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers=self._headers(),
        )

        try:
            with urllib.request.urlopen(req, timeout=self._cfg.timeout_s, context=self._ssl_context()) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                logger.info("jira.response status=%s bytes=%d", getattr(resp, "status", "?"), len(raw))
                # Debug: log first 500 chars of raw response to diagnose non-JSON returns
                logger.debug("jira.response.raw preview=%s", raw[:500].replace("\n", " "))
                if not raw.strip():
                    return {}
                try:
                    return json.loads(raw)
                except json.JSONDecodeError as e:
                    logger.error("jira.json_parse_error error=%s raw_preview=%s", e, raw[:500].replace("\n", " "))
                    raise RuntimeError(f"Jira returned non-JSON (status {getattr(resp, 'status', '?')}): {raw[:200]}") from e
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            logger.error("jira.http_error code=%s raw=%s", exc.code, raw[:500])
            raise RuntimeError(f"Jira HTTP {exc.code}: {raw[:2000]}")
        except urllib.error.URLError as exc:
            logger.error("jira.url_error error=%s", exc)
            raise RuntimeError(f"Jira URL error: {exc}")


def _load_cfg() -> JiraConfig:
    base_url = os.environ.get("JIRA_BASE_URL", "").strip()
    if not base_url:
        raise SystemExit("JIRA_BASE_URL is required")

    api_prefix = os.environ.get("JIRA_API_PREFIX", "/rest/api/2").strip() or "/rest/api/2"
    auth = os.environ.get("JIRA_AUTH", "basic").strip().lower() or "basic"
    user = os.environ.get("JIRA_USER", "").strip()
    token = os.environ.get("JIRA_TOKEN", "").strip()

    if auth == "basic" and (not user or not token):
        raise SystemExit("JIRA_USER and JIRA_TOKEN are required for basic auth")
    if auth == "bearer" and not token:
        raise SystemExit("JIRA_TOKEN is required for bearer auth")

    verify_ssl = _env_bool("JIRA_VERIFY_SSL", True)
    timeout_s = _env_int("JIRA_TIMEOUT_S", 30)

    return JiraConfig(
        base_url=base_url,
        api_prefix=api_prefix,
        auth=auth,
        user=user,
        token=token,
        verify_ssl=verify_ssl,
        timeout_s=timeout_s,
    )


def _tool_search(client: JiraClient, args: dict) -> dict:
    jql = str(args.get("jql") or "").strip()
    if not jql:
        raise ValueError("jql is required")

    fields = args.get("fields")
    if isinstance(fields, list):
        fields = ",".join(str(x) for x in fields)
    elif fields is None:
        fields = "summary,status,updated,assignee,labels,components"

    start_at = int(args.get("start_at") or 0)
    max_results = int(args.get("max_results") or 50)

    return client.request_json(
        "GET",
        "/search",
        query={
            "jql": jql,
            "startAt": str(start_at),
            "maxResults": str(max_results),
            "fields": str(fields),
        },
    )


def _tool_get(client: JiraClient, args: dict) -> dict:
    key = str(args.get("key") or "").strip()
    if not key:
        raise ValueError("key is required")

    fields = args.get("fields")
    query = None
    if isinstance(fields, list):
        query = {"fields": ",".join(str(x) for x in fields)}
    elif isinstance(fields, str) and fields.strip():
        query = {"fields": fields.strip()}

    return client.request_json("GET", f"/issue/{urllib.parse.quote(key)}", query=query)


def _tool_comment(client: JiraClient, args: dict) -> dict:
    key = str(args.get("key") or "").strip()
    body = args.get("body")
    if not key:
        raise ValueError("key is required")
    if not isinstance(body, str) or not body.strip():
        raise ValueError("body is required")

    payload = {"body": body}
    return client.request_json("POST", f"/issue/{urllib.parse.quote(key)}/comment", body=payload)


def _tool_transitions(client: JiraClient, args: dict) -> dict:
    key = str(args.get("key") or "").strip()
    if not key:
        raise ValueError("key is required")
    return client.request_json("GET", f"/issue/{urllib.parse.quote(key)}/transitions")


def _tool_transition(client: JiraClient, args: dict) -> dict:
    key = str(args.get("key") or "").strip()
    transition_id = str(args.get("transition_id") or "").strip()
    if not key:
        raise ValueError("key is required")
    if not transition_id:
        raise ValueError("transition_id is required")

    payload = {"transition": {"id": transition_id}}
    return client.request_json("POST", f"/issue/{urllib.parse.quote(key)}/transitions", body=payload)


def main() -> None:
    logging.basicConfig(
        level=getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    cfg = _load_cfg()
    logger.info("jira.mcp.start base_url=%s api_prefix=%s auth=%s verify_ssl=%s", cfg.base_url, cfg.api_prefix, cfg.auth, cfg.verify_ssl)
    client = JiraClient(cfg)

    server = StdioMcpServer(name="jira")

    server.add_tool(
        Tool(
            name="jira_search",
            description="Search issues using JQL",
            input_schema={
                "type": "object",
                "properties": {
                    "jql": {"type": "string"},
                    "fields": {"anyOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}]},
                    "start_at": {"type": "integer", "minimum": 0},
                    "max_results": {"type": "integer", "minimum": 1, "maximum": 200},
                },
                "required": ["jql"],
            },
            handler=lambda a: _tool_search(client, a),
        )
    )

    server.add_tool(
        Tool(
            name="jira_get",
            description="Get a Jira issue by key",
            input_schema={
                "type": "object",
                "properties": {
                    "key": {"type": "string"},
                    "fields": {"anyOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}]},
                },
                "required": ["key"],
            },
            handler=lambda a: _tool_get(client, a),
        )
    )

    server.add_tool(
        Tool(
            name="jira_comment",
            description="Add a comment to an issue",
            input_schema={
                "type": "object",
                "properties": {
                    "key": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["key", "body"],
            },
            handler=lambda a: _tool_comment(client, a),
        )
    )

    server.add_tool(
        Tool(
            name="jira_transitions",
            description="List available transitions for an issue",
            input_schema={
                "type": "object",
                "properties": {"key": {"type": "string"}},
                "required": ["key"],
            },
            handler=lambda a: _tool_transitions(client, a),
        )
    )

    server.add_tool(
        Tool(
            name="jira_transition",
            description="Transition an issue (by transition id)",
            input_schema={
                "type": "object",
                "properties": {
                    "key": {"type": "string"},
                    "transition_id": {"type": "string"},
                },
                "required": ["key", "transition_id"],
            },
            handler=lambda a: _tool_transition(client, a),
        )
    )

    server.run_forever()


if __name__ == "__main__":
    main()
