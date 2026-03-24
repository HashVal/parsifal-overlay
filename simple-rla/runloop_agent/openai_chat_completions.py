"""OpenAI Chat Completions API client (stdlib-only).

Env:
- OPENAI_API_KEY (required)
- OPENAI_BASE_URL (optional, default: https://api.openai.com/v1)

This module mirrors the small surface used by the workflow runtime and keeps
backend-specific response differences local to this file.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable


logger = logging.getLogger("simple_rla.openai.chat_completions")


class OpenAIError(RuntimeError):
    pass


@dataclass(frozen=True)
class FunctionCall:
    call_id: str
    name: str
    arguments_json: str


@dataclass(frozen=True)
class ChatCompletionsResult:
    response_id: str
    output_text: str
    function_calls: list[FunctionCall]
    raw: dict[str, Any]


def _base_url() -> str:
    return (os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")


def _api_key() -> str:
    key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if not key:
        raise OpenAIError("OPENAI_API_KEY is required")
    return key


def _extract_output_text(data: dict[str, Any]) -> str:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    message = choices[0].get("message")
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "\n".join(p for p in parts if p).strip()
    return ""


def _extract_function_calls(data: dict[str, Any]) -> list[FunctionCall]:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return []
    message = choices[0].get("message")
    if not isinstance(message, dict):
        return []
    tool_calls = message.get("tool_calls")
    if not isinstance(tool_calls, list):
        return []

    out: list[FunctionCall] = []
    for index, item in enumerate(tool_calls, start=1):
        if not isinstance(item, dict):
            continue
        if item.get("type") != "function":
            continue
        fn = item.get("function")
        if not isinstance(fn, dict):
            continue
        name = fn.get("name")
        if not isinstance(name, str) or not name:
            continue
        arguments = fn.get("arguments")
        if isinstance(arguments, str):
            arguments_json = arguments
        elif isinstance(arguments, dict):
            arguments_json = json.dumps(arguments, ensure_ascii=False)
        else:
            arguments_json = "{}"
        call_id = item.get("id")
        if not isinstance(call_id, str) or not call_id:
            call_id = f"tool_call_{index}"
        out.append(FunctionCall(call_id=call_id, name=name, arguments_json=arguments_json))
    return out


def _stream_text_delta(event: dict[str, Any]) -> str:
    choices = event.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    delta = choices[0].get("delta")
    if not isinstance(delta, dict):
        return ""
    content = delta.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)
    return ""


def _iter_sse_events(resp: Any):
    data_lines: list[str] = []
    for raw_line in resp:
        line = raw_line.decode("utf-8", errors="replace")
        if line.startswith(":"):
            continue
        stripped = line.strip()
        if not stripped:
            if not data_lines:
                continue
            payload = "\n".join(data_lines)
            data_lines = []
            if payload == "[DONE]":
                break
            try:
                yield json.loads(payload)
            except json.JSONDecodeError:
                logger.debug("openai.stream.invalid_event payload=%r", payload[:200])
            continue
        if stripped.startswith("data:"):
            data_lines.append(stripped[5:].lstrip())
    if data_lines:
        payload = "\n".join(data_lines)
        if payload != "[DONE]":
            try:
                yield json.loads(payload)
            except json.JSONDecodeError:
                logger.debug("openai.stream.invalid_tail_event payload=%r", payload[:200])


def _create_chat_completion_streaming(
    *,
    req: urllib.request.Request,
    timeout_s: int,
    stream_observer: Callable[[str], None] | None,
) -> ChatCompletionsResult:
    final_data: dict[str, Any] | None = None
    aggregated_text_parts: list[str] = []
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            for event in _iter_sse_events(resp):
                if not isinstance(event, dict):
                    continue
                delta_text = _stream_text_delta(event)
                if delta_text:
                    aggregated_text_parts.append(delta_text)
                    if stream_observer is not None:
                        try:
                            stream_observer(delta_text)
                        except Exception:
                            logger.exception("openai.stream_observer_failed")
                choices = event.get("choices")
                if isinstance(choices, list) and choices:
                    finish_reason = choices[0].get("finish_reason")
                    if finish_reason is not None:
                        final_data = event
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise OpenAIError(f"HTTP {exc.code} URL={req.full_url} body={raw[:2000]}")
    except urllib.error.URLError as exc:
        raise OpenAIError(f"URL error: {exc}")

    if final_data is None:
        output_text = "".join(aggregated_text_parts).strip()
        if not output_text:
            raise OpenAIError("streaming response ended without a final response payload")
        final_data = {
            "id": "streaming_chat_completion",
            "choices": [{"message": {"role": "assistant", "content": output_text}}],
        }
    else:
        if aggregated_text_parts:
            final_data = dict(final_data)
            choices = list(final_data.get("choices") or [])
            if choices:
                first = dict(choices[0])
                message = dict(first.get("message") or {})
                if not message.get("content"):
                    message["content"] = "".join(aggregated_text_parts).strip()
                first["message"] = message
                choices[0] = first
                final_data["choices"] = choices

    rid = final_data.get("id")
    if not isinstance(rid, str) or not rid:
        rid = "chatcmpl_stream"

    return ChatCompletionsResult(
        response_id=rid,
        output_text=_extract_output_text(final_data),
        function_calls=_extract_function_calls(final_data),
        raw=final_data,
    )


def create_chat_completion(
    *,
    model: str,
    messages: list[dict[str, Any]],
    tools: list[dict] | None = None,
    tool_choice: str | dict | None = "auto",
    temperature: float | None = 0.2,
    timeout_s: int = 90,
    enable_real_time_output: bool = False,
    stream_observer: Callable[[str], None] | None = None,
) -> ChatCompletionsResult:
    url = _base_url() + "/chat/completions"
    logger.info("openai.request url=%s model=%s", url, model)

    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
    }
    if temperature is not None:
        payload["temperature"] = temperature
    if tools is not None:
        payload["tools"] = tools
    if tool_choice is not None:
        payload["tool_choice"] = tool_choice
    if enable_real_time_output:
        payload["stream"] = True

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {_api_key()}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    if enable_real_time_output:
        return _create_chat_completion_streaming(req=req, timeout_s=timeout_s, stream_observer=stream_observer)

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

    rid = data.get("id")
    if not isinstance(rid, str) or not rid:
        rid = "chatcmpl"

    return ChatCompletionsResult(
        response_id=rid,
        output_text=_extract_output_text(data),
        function_calls=_extract_function_calls(data),
        raw=data,
    )


__all__ = ["ChatCompletionsResult", "FunctionCall", "OpenAIError", "create_chat_completion"]
