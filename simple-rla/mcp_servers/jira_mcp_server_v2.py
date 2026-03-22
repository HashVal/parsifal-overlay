#!/usr/bin/env python3
"""Workflow-facing Jira MCP server v2 (stdlib only).

This server intentionally exposes a smaller, more deterministic tool surface for
structured workflow phases.

Env:
- JIRA_BASE_URL
- JIRA_API_PREFIX
- JIRA_AUTH
- JIRA_USER
- JIRA_PASSWORD
- JIRA_TOKEN
- JIRA_VERIFY_SSL
- JIRA_TIMEOUT_S

Tools:
- find_jira_by_key(jira_key) -> str | null
- grep_jira_properties(jira_key) -> dict
- select_jira_attachments(jira_key) -> list[str]
- download_jira_attachments(attachment_urls) -> list[str]
"""

from __future__ import annotations

import logging
import os
import re
import urllib.parse
from pathlib import Path
from typing import Any

from .jira_server import JiraClient, _default_attachment_dir, _extract_attachments, _load_cfg, _safe_filename
from .stdio_jsonrpc_server import StdioMcpServer, Tool

logger = logging.getLogger("simple_rla.jira_v2")
_LOG_LIKE_EXTS = (".dmesg", ".log", ".txt")
_LOG_LIKE_NAME = re.compile(r"(dmesg|log|txt)", re.IGNORECASE)
_REQUIRED_FIELDS = [
    "summary",
    "status",
    "priority",
    "updated",
    "assignee",
    "reporter",
    "labels",
    "components",
    "description",
    "attachment",
]


def _tool_find_jira_by_key(client: JiraClient, args: dict[str, Any]) -> str | None:
    jira_key = str(args.get("jira_key") or "").strip()
    if not jira_key:
        raise ValueError("jira_key is required")
    try:
        issue = client.request_json(
            "GET",
            f"/issue/{urllib.parse.quote(jira_key)}",
            query={"fields": "summary"},
        )
    except RuntimeError as exc:
        message = str(exc)
        if "HTTP 404" in message or "does not exist" in message.lower() or "not found" in message.lower():
            logger.info("jira_v2.find_jira_by_key miss jira_key=%s", jira_key)
            return None
        raise
    if not isinstance(issue, dict):
        return None
    key = issue.get("key")
    if isinstance(key, str) and key.strip():
        logger.info("jira_v2.find_jira_by_key hit jira_key=%s", key)
        return key.strip()
    return None


def _tool_grep_jira_properties(client: JiraClient, args: dict[str, Any]) -> dict[str, Any]:
    jira_key = str(args.get("jira_key") or "").strip()
    if not jira_key:
        raise ValueError("jira_key is required")
    issue = client.request_json(
        "GET",
        f"/issue/{urllib.parse.quote(jira_key)}",
        query={"fields": ",".join(_REQUIRED_FIELDS)},
    )
    if not isinstance(issue, dict):
        return {}
    fields = issue.get("fields") if isinstance(issue.get("fields"), dict) else {}
    labels = fields.get("labels") if isinstance(fields.get("labels"), list) else []
    components = fields.get("components") if isinstance(fields.get("components"), list) else []
    out = {
        "key": issue.get("key"),
        "summary": fields.get("summary"),
        "status": ((fields.get("status") or {}).get("name") if isinstance(fields.get("status"), dict) else None),
        "priority": ((fields.get("priority") or {}).get("name") if isinstance(fields.get("priority"), dict) else None),
        "updated": fields.get("updated"),
        "assignee": ((fields.get("assignee") or {}).get("displayName") if isinstance(fields.get("assignee"), dict) else None),
        "reporter": ((fields.get("reporter") or {}).get("displayName") if isinstance(fields.get("reporter"), dict) else None),
        "labels": [str(x) for x in labels],
        "components": [c.get("name") for c in components if isinstance(c, dict) and c.get("name")],
        "description": fields.get("description"),
    }
    compact = {k: v for k, v in out.items() if v not in (None, "", [], {})}
    logger.info("jira_v2.grep_jira_properties jira_key=%s keys=%s", jira_key, sorted(compact.keys()))
    return compact


def _tool_select_jira_attachments(client: JiraClient, args: dict[str, Any]) -> list[str]:
    jira_key = str(args.get("jira_key") or "").strip()
    if not jira_key:
        raise ValueError("jira_key is required")
    issue = client.request_json(
        "GET",
        f"/issue/{urllib.parse.quote(jira_key)}",
        query={"fields": "attachment"},
    )
    if not isinstance(issue, dict):
        return []
    attachments = _extract_attachments(issue)
    selected: list[str] = []
    for item in attachments:
        filename = str(item.get("filename") or "")
        content_url = str(item.get("content_url") or "").strip()
        if not content_url:
            continue
        lower_name = filename.lower()
        if lower_name.endswith(_LOG_LIKE_EXTS) or _LOG_LIKE_NAME.search(filename):
            selected.append(content_url)
    logger.info("jira_v2.select_jira_attachments jira_key=%s selected=%d", jira_key, len(selected))
    return selected


def _tool_download_jira_attachments(client: JiraClient, args: dict[str, Any]) -> list[str]:
    urls = args.get("attachment_urls")
    if not isinstance(urls, list):
        raise ValueError("attachment_urls must be a list")
    out_dir_arg = str(args.get("out_dir") or "").strip()
    jira_key = str(args.get("jira_key") or "").strip() or "jira"
    out_dir = Path(out_dir_arg).expanduser().resolve() if out_dir_arg else _default_attachment_dir(jira_key).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    saved_paths: list[str] = []
    for idx, url in enumerate(urls):
        if not isinstance(url, str) or not url.strip():
            continue
        data, _content_type = client.download_bytes(url)
        parsed = urllib.parse.urlparse(url)
        name = Path(parsed.path).name or f"attachment_{idx}"
        filename = _safe_filename(name)
        saved_path = out_dir / filename
        if saved_path.exists():
            stem = saved_path.stem
            suffix = saved_path.suffix
            saved_path = out_dir / f"{stem}_{idx}{suffix}"
        saved_path.write_bytes(data)
        saved_paths.append(str(saved_path))

    logger.info("jira_v2.download_jira_attachments jira_key=%s saved=%d out_dir=%s", jira_key, len(saved_paths), out_dir)
    return saved_paths


def main() -> None:
    logging.basicConfig(
        level=getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    cfg = _load_cfg()
    logger.info("jira_v2.mcp.start base_url=%s api_prefix=%s auth=%s verify_ssl=%s", cfg.base_url, cfg.api_prefix, cfg.auth, cfg.verify_ssl)
    client = JiraClient(cfg)
    server = StdioMcpServer(name="jira_v2")

    server.add_tool(
        Tool(
            name="find_jira_by_key",
            description="Return the Jira key if the issue exists, otherwise null.",
            input_schema={
                "type": "object",
                "properties": {
                    "jira_key": {"type": "string"},
                },
                "required": ["jira_key"],
            },
            handler=lambda a: _tool_find_jira_by_key(client, a),
        )
    )

    server.add_tool(
        Tool(
            name="grep_jira_properties",
            description="Return a compact dict of workflow-relevant Jira properties for the given key.",
            input_schema={
                "type": "object",
                "properties": {
                    "jira_key": {"type": "string"},
                },
                "required": ["jira_key"],
            },
            handler=lambda a: _tool_grep_jira_properties(client, a),
        )
    )

    server.add_tool(
        Tool(
            name="select_jira_attachments",
            description="Return a list of attachment URLs that match default log-like selection rules.",
            input_schema={
                "type": "object",
                "properties": {
                    "jira_key": {"type": "string"},
                },
                "required": ["jira_key"],
            },
            handler=lambda a: _tool_select_jira_attachments(client, a),
        )
    )

    server.add_tool(
        Tool(
            name="download_jira_attachments",
            description="Download a list of Jira attachment URLs and return local saved file paths.",
            input_schema={
                "type": "object",
                "properties": {
                    "attachment_urls": {"type": "array", "items": {"type": "string"}},
                    "jira_key": {"type": "string"},
                    "out_dir": {"type": "string"},
                },
                "required": ["attachment_urls"],
            },
            handler=lambda a: _tool_download_jira_attachments(client, a),
        )
    )

    server.run_forever()


if __name__ == "__main__":
    main()
