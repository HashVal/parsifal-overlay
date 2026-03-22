"""OpenAI Chat Completions client with tool (function) calling.

Stdlib-only HTTP client using urllib.

Env:
- OPENAI_API_KEY (required)
- OPENAI_BASE_URL (optional, default: https://api.openai.com/v1)

This module intentionally keeps the surface small so you can swap to Responses API later.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


logger = logging.getLogger("simple_rla.openai.chat_completions")


class OpenAIError(RuntimeError):
    pass


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments_json: str


@dataclass(frozen=True)
class ModelMessage:
    role: str
    content: str | None
    tool_calls: list[ToolCall]


def _base_url() -> str:
    return (os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")


def _api_key() -> str:
    key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if not key:
        raise OpenAIError("OPENAI_API_KEY is required")
    return key


def chat_completions(
    *,
    model: str,
    messages: list[dict],
    tools: list[dict] | None = None,
    tool_choice: str | dict | None = "auto",
    temperature: float = 0.2,
    timeout_s: int = 60,
) -> ModelMessage:
    url = _base_url() + "/chat/completions"
    logger.info("openai.request url=%s model=%s", url, model)

    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if tools is not None:
        payload["tools"] = tools
    if tool_choice is not None:
        payload["tool_choice"] = tool_choice

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
        raise OpenAIError(f"HTTP {exc.code} URL={url} body={raw[:2000]}")
    except urllib.error.URLError as exc:
        raise OpenAIError(f"URL error: {exc}")

    logger.debug("openai.response bytes=%d", len(raw))

    data = json.loads(raw)
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise OpenAIError(f"unexpected response: {data}")

    msg = choices[0].get("message")
    if not isinstance(msg, dict):
        raise OpenAIError(f"missing message: {data}")

    tool_calls: list[ToolCall] = []
    tc = msg.get("tool_calls")
    if isinstance(tc, list):
        for item in tc:
            if not isinstance(item, dict):
                continue
            if item.get("type") != "function":
                continue
            fn = item.get("function")
            if not isinstance(fn, dict):
                continue
            tool_calls.append(
                ToolCall(
                    id=str(item.get("id") or ""),
                    name=str(fn.get("name") or ""),
                    arguments_json=str(fn.get("arguments") or "{}"),
                )
            )

    return ModelMessage(
        role=str(msg.get("role") or "assistant"),
        content=msg.get("content"),
        tool_calls=tool_calls,
    )
