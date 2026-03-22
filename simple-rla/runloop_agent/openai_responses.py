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
from typing import Any, Callable, Dict, List, Optional


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


def _stream_text_delta(event: dict[str, Any]) -> str:
    candidates: list[str] = []
    delta = event.get("delta")
    if isinstance(delta, str):
        candidates.append(delta)
    elif isinstance(delta, dict):
        text = delta.get("text")
        if isinstance(text, str):
            candidates.append(text)

    item = event.get("item")
    if isinstance(item, dict):
        text = item.get("text")
        if isinstance(text, str):
            candidates.append(text)
        content = item.get("content")
        if isinstance(content, list):
            for part in content:
                if not isinstance(part, dict):
                    continue
                text = part.get("text")
                if isinstance(text, str):
                    candidates.append(text)
                delta = part.get("delta")
                if isinstance(delta, str):
                    candidates.append(delta)

    for value in candidates:
        if value:
            return value
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


def _create_response_streaming(
    *,
    req: urllib.request.Request,
    timeout_s: int,
    stream_observer: Callable[[str], None] | None,
) -> ResponseResult:
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
                event_type = str(event.get("type") or "")
                if event_type in {"response.completed", "response.done", "completed", "done"}:
                    response = event.get("response")
                    if isinstance(response, dict):
                        final_data = response
                elif {"id", "output"}.issubset(event.keys()) or "output_text" in event:
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
            "id": "streaming_response",
            "output_text": output_text,
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": output_text}],
                }
            ],
        }
    elif not final_data.get("output_text") and aggregated_text_parts:
        final_data = dict(final_data)
        final_data["output_text"] = "".join(aggregated_text_parts).strip()

    rid = final_data.get("id")
    if not isinstance(rid, str) or not rid:
        raise OpenAIError(f"missing response id: {final_data}")

    return ResponseResult(
        response_id=rid,
        output_text=_extract_output_text(final_data),
        function_calls=_extract_function_calls(final_data),
        raw=final_data,
    )


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
    enable_real_time_output: bool = False,
    stream_observer: Callable[[str], None] | None = None,
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
        return _create_response_streaming(req=req, timeout_s=timeout_s, stream_observer=stream_observer)

    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        if exc.code == 404 and url.endswith("/responses"):
            raise OpenAIError(
                "HTTP 404 on /responses. Your OpenAI-compatible gateway likely does not implement the Responses API. "
                "Use a backend that supports /v1/responses, or fall back to the archived ChatCompletions runloop under runloop_agent/legacy/code/. "
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
