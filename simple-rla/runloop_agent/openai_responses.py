"""OpenAI Responses API client (stdlib-only).

Env:
- OPENAI_API_KEY (required)
- OPENAI_BASE_URL (optional, default: https://api.openai.com/v1)

This is a small wrapper around POST /v1/responses.

It supports function tools and parsing of function call outputs.

Note: The Responses schema has evolved. This client is written to be tolerant:
- For text: uses top-level `output_text` when present; otherwise extracts from `output` items.
- For tool calls: looks for output items of type `function_call` (and a few fallback keys).
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


logger = logging.getLogger("simple_rla.openai.responses")


class OpenAIError(RuntimeError):
    pass


@dataclass(frozen=True)
class FunctionCall:
    call_id: str
    name: str
    arguments_json: str


@dataclass(frozen=True)
class ResponseResult:
    response_id: str
    output_text: str
    function_calls: list[FunctionCall]
    raw: dict


def _base_url() -> str:
    return (os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")


def _api_key() -> str:
    key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if not key:
        raise OpenAIError("OPENAI_API_KEY is required")
    return key


def _extract_output_text(data: dict) -> str:
    ot = data.get("output_text")
    if isinstance(ot, str) and ot.strip():
        return ot

    out = data.get("output")
    if not isinstance(out, list):
        return ""

    parts: list[str] = []
    for item in out:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "message":
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for c in content:
            if not isinstance(c, dict):
                continue
            # Responses typically uses output_text blocks.
            if c.get("type") in ("output_text", "text") and isinstance(c.get("text"), str):
                parts.append(c["text"])
    return "\n".join(p for p in parts if p).strip()


def _extract_function_calls(data: dict) -> list[FunctionCall]:
    out = data.get("output")
    if not isinstance(out, list):
        return []

    calls: list[FunctionCall] = []
    for item in out:
        if not isinstance(item, dict):
            continue

        t = item.get("type")
        if t not in ("function_call", "tool_call"):
            continue

        name = item.get("name") or item.get("tool_name")
        if not isinstance(name, str) or not name:
            continue

        call_id = item.get("call_id") or item.get("id") or item.get("tool_call_id")
        if not isinstance(call_id, str) or not call_id:
            # Some variants omit ids; generate a synthetic one.
            call_id = f"call_{len(calls)+1}"

        args = item.get("arguments")
        if isinstance(args, str):
            arguments_json = args
        elif isinstance(args, dict):
            arguments_json = json.dumps(args, ensure_ascii=False)
        else:
            arguments_json = "{}"

        calls.append(FunctionCall(call_id=call_id, name=name, arguments_json=arguments_json))

    return calls


def create_response(
    *,
    model: str,
    input_items: list[dict] | str,
    tools: list[dict] | None = None,
    tool_choice: str | dict | None = "auto",
    previous_response_id: str | None = None,
    temperature: float | None = 0.2,
    max_output_tokens: int | None = None,
    timeout_s: int = 90,
) -> ResponseResult:
    url = _base_url() + "/responses"
    logger.info("openai.request url=%s model=%s", url, model)

    payload: dict[str, Any] = {
        "model": model,
        "input": input_items,
    }
    if previous_response_id:
        payload["previous_response_id"] = previous_response_id
    if tools is not None:
        payload["tools"] = tools
    if tool_choice is not None:
        payload["tool_choice"] = tool_choice
    if temperature is not None:
        payload["temperature"] = temperature
    if max_output_tokens is not None:
        payload["max_output_tokens"] = max_output_tokens

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {_api_key()}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        if exc.code == 404 and url.endswith("/responses"):
            raise OpenAIError(
                "HTTP 404 on /responses. Your OpenAI-compatible gateway likely does not implement the Responses API. "
                "Use the ChatCompletions runloop (fc_runloop.py) or point OPENAI_BASE_URL to a backend that supports /v1/responses. "
                f"URL={url} body={raw[:500]}"
            )
        raise OpenAIError(f"HTTP {exc.code} URL={url} body={raw[:2000]}")
    except urllib.error.URLError as exc:
        raise OpenAIError(f"URL error: {exc}")

    logger.debug("openai.response bytes=%d", len(raw))

    data = json.loads(raw)
    rid = data.get("id")
    if not isinstance(rid, str) or not rid:
        raise OpenAIError(f"missing response id: {data}")

    return ResponseResult(
        response_id=rid,
        output_text=_extract_output_text(data),
        function_calls=_extract_function_calls(data),
        raw=data,
    )
