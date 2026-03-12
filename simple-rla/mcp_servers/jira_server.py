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
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


_DEFAULT_SEARCH_FIELDS = "summary,status,updated,assignee,labels,components"
_DEFAULT_GET_FIELDS = "summary,status,updated,assignee,labels,components,description,issuetype,priority,reporter,attachment"
_MAX_TEXT_PREVIEW = 1200
_MAX_ITEMS = 10
_ATTACHMENT_PREVIEW_BYTES = 8192
_ATTACHMENT_PREVIEW_LINES = 50
_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")

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
    secret: str
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
            raw = f"{self._cfg.user}:{self._cfg.secret}".encode("utf-8")
            b64 = base64.b64encode(raw).decode("ascii")
            h["Authorization"] = f"Basic {b64}"
        elif auth == "bearer":
            h["Authorization"] = f"Bearer {self._cfg.secret}"
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
                status = getattr(resp, "status", "?")
                content_type = resp.headers.get("Content-Type", "")
                www_authenticate = resp.headers.get("WWW-Authenticate", "")
                seraph_reason = resp.headers.get("X-Seraph-LoginReason", "")
                raw = resp.read().decode("utf-8", errors="replace")
                logger.info("jira.response status=%s bytes=%d content_type=%s", status, len(raw), content_type)
                logger.debug(
                    "jira.response.headers status=%s content_type=%s seraph=%s www_auth=%s",
                    status,
                    content_type,
                    seraph_reason,
                    www_authenticate[:200],
                )
                logger.debug("jira.response.raw preview=%s", raw[:500].replace("\n", " "))
                if not raw.strip():
                    return {}
                if "json" not in content_type.lower():
                    if "html" in content_type.lower():
                        raise RuntimeError(
                            "Jira returned HTML instead of JSON "
                            f"(status {status}, content-type {content_type}). "
                            "This usually means auth failed, a login/SSO page intercepted the request, or the API base URL is wrong."
                        )
                    raise RuntimeError(
                        f"Jira returned unexpected content-type {content_type!r} (status {status}) instead of JSON"
                    )
                try:
                    return json.loads(raw)
                except json.JSONDecodeError as e:
                    logger.error("jira.json_parse_error error=%s raw_preview=%s", e, raw[:500].replace("\n", " "))
                    raise RuntimeError(f"Jira returned invalid JSON (status {status}): {raw[:200]}") from e
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            content_type = exc.headers.get("Content-Type", "") if exc.headers else ""
            www_authenticate = exc.headers.get("WWW-Authenticate", "") if exc.headers else ""
            seraph_reason = exc.headers.get("X-Seraph-LoginReason", "") if exc.headers else ""
            logger.error(
                "jira.http_error code=%s content_type=%s seraph=%s www_auth=%s raw=%s",
                exc.code,
                content_type,
                seraph_reason,
                www_authenticate[:200],
                raw[:500],
            )
            if exc.code == 401:
                raise RuntimeError(
                    "Jira authentication failed (401). "
                    f"content-type={content_type or '?'} seraph={seraph_reason or '?'}. "
                    "If using basic auth, verify JIRA_USER:JIRA_PASSWORD. "
                    "If using token auth, try JIRA_AUTH=bearer with JIRA_TOKEN."
                )
            raise RuntimeError(f"Jira HTTP {exc.code}: {raw[:2000]}")
        except urllib.error.URLError as exc:
            logger.error("jira.url_error error=%s", exc)
            raise RuntimeError(f"Jira URL error: {exc}")

    def download_bytes(self, url: str) -> tuple[bytes, str]:
        logger.info("jira.download %s", url)
        req = urllib.request.Request(
            url,
            headers=self._headers(),
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=self._cfg.timeout_s, context=self._ssl_context()) as resp:
                content_type = resp.headers.get("Content-Type", "")
                data = resp.read()
                logger.info("jira.download.response status=%s bytes=%d content_type=%s", getattr(resp, "status", "?"), len(data), content_type)
                return data, content_type
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            raise RuntimeError(f"Jira attachment HTTP {exc.code}: {raw[:500]}")
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Jira attachment URL error: {exc}")


def _load_cfg() -> JiraConfig:
    base_url = os.environ.get("JIRA_BASE_URL", "").strip()
    if not base_url:
        raise SystemExit("JIRA_BASE_URL is required")

    api_prefix = os.environ.get("JIRA_API_PREFIX", "/rest/api/latest").strip() or "/rest/api/latest"
    auth = os.environ.get("JIRA_AUTH", "basic").strip().lower() or "basic"
    user = os.environ.get("JIRA_USER", "").strip()
    password = os.environ.get("JIRA_PASSWORD", "").strip()
    token = os.environ.get("JIRA_TOKEN", "").strip()

    if auth == "basic":
        secret = password or token
        if not user or not secret:
            raise SystemExit("JIRA_USER and JIRA_PASSWORD are required for basic auth (JIRA_TOKEN is accepted as fallback)")
        if not password and token:
            logger.warning("basic auth is using JIRA_TOKEN as password fallback; prefer JIRA_PASSWORD for clarity")
    elif auth == "bearer":
        secret = token
        if not secret:
            raise SystemExit("JIRA_TOKEN is required for bearer auth")
    else:
        raise SystemExit(f"unsupported JIRA_AUTH: {auth}")

    verify_ssl = _env_bool("JIRA_VERIFY_SSL", True)
    timeout_s = _env_int("JIRA_TIMEOUT_S", 30)

    return JiraConfig(
        base_url=base_url,
        api_prefix=api_prefix,
        auth=auth,
        user=user,
        secret=secret,
        verify_ssl=verify_ssl,
        timeout_s=timeout_s,
    )


def _safe_filename(name: str) -> str:
    safe = _SAFE_NAME.sub("_", (name or "attachment").strip())
    return safe or "attachment"


def _default_attachment_dir(key: str) -> Path:
    return Path.cwd() / "artifacts" / "jira_attachments" / _safe_filename(key)


def _decode_preview(data: bytes) -> tuple[str, bool]:
    sample = data[:_ATTACHMENT_PREVIEW_BYTES]
    if b"\x00" in sample:
        return "<binary preview omitted>", True
    text = sample.decode("utf-8", errors="replace")
    lines = text.splitlines()
    preview = "\n".join(lines[:_ATTACHMENT_PREVIEW_LINES])
    if len(sample) < len(data) or len(lines) > _ATTACHMENT_PREVIEW_LINES:
        preview += f"\n... [truncated preview of {len(data)} bytes]"
    return preview.strip(), False


def _extract_attachments(issue: dict) -> list[dict]:
    fields = issue.get("fields") if isinstance(issue.get("fields"), dict) else {}
    attachments = fields.get("attachment") if isinstance(fields.get("attachment"), list) else []
    out: list[dict] = []
    for a in attachments[:_MAX_ITEMS]:
        if not isinstance(a, dict):
            continue
        out.append({
            "id": str(a.get("id") or ""),
            "filename": a.get("filename"),
            "mime_type": a.get("mimeType") or a.get("mime_type"),
            "size": a.get("size"),
            "created": a.get("created"),
            "author": _user_name(a.get("author")),
            "content_url": a.get("content"),
        })
    return out


def _clip_text(value: Any, limit: int = _MAX_TEXT_PREVIEW) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        if isinstance(value.get("content"), str):
            value = value.get("content")
        else:
            value = json.dumps(value, ensure_ascii=False)
    elif isinstance(value, list):
        value = json.dumps(value, ensure_ascii=False)
    else:
        value = str(value)
    value = value.strip()
    if len(value) <= limit:
        return value
    return value[:limit] + f"... [truncated {len(value) - limit} chars]"


def _user_name(user: Any) -> str | None:
    if not isinstance(user, dict):
        return None
    for k in ("displayName", "name", "emailAddress", "key"):
        v = user.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _normalize_issue(issue: dict, *, include_description: bool = True) -> dict:
    fields = issue.get("fields") if isinstance(issue.get("fields"), dict) else {}
    comments = (((fields.get("comment") or {}).get("comments") or []) if isinstance(fields.get("comment"), dict) else [])
    labels = fields.get("labels") if isinstance(fields.get("labels"), list) else []
    components = fields.get("components") if isinstance(fields.get("components"), list) else []

    out = {
        "key": issue.get("key"),
        "summary": fields.get("summary"),
        "status": ((fields.get("status") or {}).get("name") if isinstance(fields.get("status"), dict) else None),
        "issue_type": ((fields.get("issuetype") or {}).get("name") if isinstance(fields.get("issuetype"), dict) else None),
        "priority": ((fields.get("priority") or {}).get("name") if isinstance(fields.get("priority"), dict) else None),
        "updated": fields.get("updated"),
        "assignee": _user_name(fields.get("assignee")),
        "reporter": _user_name(fields.get("reporter")),
        "labels": [str(x) for x in labels[:_MAX_ITEMS]],
        "components": [c.get("name") for c in components[:_MAX_ITEMS] if isinstance(c, dict) and c.get("name")],
        "comment_count": len(comments),
    }

    if include_description:
        out["description_preview"] = _clip_text(fields.get("description"))

    attachments = _extract_attachments(issue)
    if attachments:
        out["attachments"] = attachments

    if comments:
        recent = comments[-min(len(comments), 3):]
        out["recent_comments"] = [
            {
                "author": _user_name(c.get("author")),
                "created": c.get("created"),
                "body_preview": _clip_text(c.get("body"), limit=400),
            }
            for c in recent
            if isinstance(c, dict)
        ]

    return out


def _tool_search(client: JiraClient, args: dict) -> dict:
    jql = str(args.get("jql") or "").strip()
    if not jql:
        raise ValueError("jql is required")

    fields = args.get("fields")
    if isinstance(fields, list):
        fields = ",".join(str(x) for x in fields)
    elif fields is None:
        fields = _DEFAULT_SEARCH_FIELDS

    start_at = int(args.get("start_at") or 0)
    max_results = int(args.get("max_results") or 50)

    res = client.request_json(
        "GET",
        "/search",
        query={
            "jql": jql,
            "startAt": str(start_at),
            "maxResults": str(max_results),
            "fields": str(fields),
        },
    )

    issues = res.get("issues") if isinstance(res, dict) else []
    compact_issues = [
        _normalize_issue(i, include_description=False)
        for i in issues[:_MAX_ITEMS]
        if isinstance(i, dict)
    ]

    out = {
        "jql": jql,
        "start_at": start_at,
        "max_results": max_results,
        "total": res.get("total") if isinstance(res, dict) else None,
        "returned": len(compact_issues),
        "issues": compact_issues,
    }
    logger.info("jira.search.compact total=%s returned=%s", out.get("total"), out.get("returned"))
    return out


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
    else:
        query = {"fields": _DEFAULT_GET_FIELDS}

    issue = client.request_json("GET", f"/issue/{urllib.parse.quote(key)}", query=query)
    if not isinstance(issue, dict):
        return {"key": key, "error": "unexpected Jira issue payload"}
    out = _normalize_issue(issue, include_description=True)
    logger.info("jira.get.compact key=%s comments=%s", key, out.get("comment_count"))
    return out


def _tool_list_attachments(client: JiraClient, args: dict) -> dict:
    key = str(args.get("key") or "").strip()
    if not key:
        raise ValueError("key is required")

    issue = client.request_json(
        "GET",
        f"/issue/{urllib.parse.quote(key)}",
        query={"fields": "attachment"},
    )
    if not isinstance(issue, dict):
        return {"key": key, "attachments": [], "error": "unexpected Jira issue payload"}

    attachments = _extract_attachments(issue)
    logger.info("jira.attachments.list key=%s count=%d", key, len(attachments))
    return {
        "key": key,
        "count": len(attachments),
        "attachments": attachments,
    }


def _tool_fetch_attachment(client: JiraClient, args: dict) -> dict:
    key = str(args.get("key") or "").strip()
    attachment_id = str(args.get("attachment_id") or "").strip()
    out_dir_raw = str(args.get("out_dir") or "").strip()
    if not key:
        raise ValueError("key is required")
    if not attachment_id:
        raise ValueError("attachment_id is required")

    issue = client.request_json(
        "GET",
        f"/issue/{urllib.parse.quote(key)}",
        query={"fields": "attachment"},
    )
    if not isinstance(issue, dict):
        raise RuntimeError("unexpected Jira issue payload while listing attachments")

    attachments = _extract_attachments(issue)
    match = next((a for a in attachments if a.get("id") == attachment_id), None)
    if not match:
        raise RuntimeError(f"attachment {attachment_id} not found on issue {key}")

    content_url = str(match.get("content_url") or "").strip()
    if not content_url:
        raise RuntimeError(f"attachment {attachment_id} has no content URL")

    data, content_type = client.download_bytes(content_url)

    out_dir = Path(out_dir_raw).expanduser().resolve() if out_dir_raw else _default_attachment_dir(key).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = _safe_filename(str(match.get("filename") or attachment_id))
    saved_path = out_dir / filename
    saved_path.write_bytes(data)

    preview, binary = _decode_preview(data)
    logger.info("jira.attachments.fetch key=%s attachment_id=%s bytes=%d saved=%s", key, attachment_id, len(data), saved_path)
    return {
        "key": key,
        "attachment_id": attachment_id,
        "filename": match.get("filename"),
        "saved_path": str(saved_path),
        "size": len(data),
        "mime_type": content_type or match.get("mime_type"),
        "binary": binary,
        "preview": preview,
    }


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
            name="jira_list_attachments",
            description="List attachments on a Jira issue",
            input_schema={
                "type": "object",
                "properties": {
                    "key": {"type": "string"},
                },
                "required": ["key"],
            },
            handler=lambda a: _tool_list_attachments(client, a),
        )
    )

    server.add_tool(
        Tool(
            name="jira_fetch_attachment",
            description="Download a Jira attachment to a local file and return a short preview",
            input_schema={
                "type": "object",
                "properties": {
                    "key": {"type": "string"},
                    "attachment_id": {"type": "string"},
                    "out_dir": {"type": "string"},
                },
                "required": ["key", "attachment_id"],
            },
            handler=lambda a: _tool_fetch_attachment(client, a),
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
