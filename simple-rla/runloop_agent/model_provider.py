from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Callable

from runloop_agent.openai_chat_completions import create_chat_completion
from runloop_agent.openai_responses import OpenAIError, create_response


@dataclass(slots=True)
class ModelResponse:
    text: str
    raw: Any = None
    usage: dict[str, Any] | None = None
    tool_requests: list[dict[str, Any]] | None = None
    backend: str | None = None


class ModelProvider:
    def __init__(self, *, api_mode: str | None = None) -> None:
        resolved_mode = api_mode or os.environ.get("OPENAI_API_MODE")
        self._api_mode = self._normalize_api_mode(resolved_mode)

    @staticmethod
    def _normalize_api_mode(api_mode: str | None) -> str:
        mode = (api_mode or "responses").strip().lower()
        if mode in {"responses", "response", "v1/responses"}:
            return "responses"
        if mode in {"chat_completions", "chat-completions", "chatcompletions", "chat", "v1/chat/completions"}:
            return "chat_completions"
        raise OpenAIError(f"unsupported OPENAI_API_MODE: {api_mode!r}")

    @staticmethod
    def _normalize_tool_requests(function_calls: list[Any]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for item in function_calls or []:
            name = getattr(item, "name", None)
            arguments_json = getattr(item, "arguments_json", None)
            if not isinstance(name, str) or not name:
                continue
            arguments: dict[str, Any] = {}
            if isinstance(arguments_json, str) and arguments_json.strip():
                try:
                    parsed = json.loads(arguments_json)
                    if isinstance(parsed, dict):
                        arguments = parsed
                except Exception:
                    arguments = {}
            out.append({"name": name, "arguments": arguments})
        return out

    def generate(
        self,
        *,
        model: str,
        prompt: str,
        response_schema: dict[str, Any] | None = None,
        timeout_s: int = 90,
        enable_real_time_output: bool = False,
        stream_observer: Callable[[str], None] | None = None,
    ) -> ModelResponse:
        del response_schema
        if self._api_mode == "chat_completions":
            result = create_chat_completion(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                tools=None,
                tool_choice=None,
                timeout_s=timeout_s,
                enable_real_time_output=enable_real_time_output,
                stream_observer=stream_observer,
            )
            return ModelResponse(
                text=result.output_text,
                raw=result.raw,
                usage=None,
                tool_requests=self._normalize_tool_requests(result.function_calls),
                backend=self._api_mode,
            )

        result = create_response(
            model=model,
            input_items=prompt,
            tools=None,
            tool_choice=None,
            timeout_s=timeout_s,
            enable_real_time_output=enable_real_time_output,
            stream_observer=stream_observer,
        )
        return ModelResponse(
            text=result.output_text,
            raw=result.raw,
            usage=None,
            tool_requests=self._normalize_tool_requests(result.function_calls),
            backend=self._api_mode,
        )

    def generate_with_tools(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        timeout_s: int = 90,
        enable_real_time_output: bool = False,
        stream_observer: Callable[[str], None] | None = None,
    ) -> ModelResponse:
        if self._api_mode == "chat_completions":
            result = create_chat_completion(
                model=model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                timeout_s=timeout_s,
                enable_real_time_output=enable_real_time_output,
                stream_observer=stream_observer,
            )
            return ModelResponse(
                text=result.output_text,
                raw=result.raw,
                usage=None,
                tool_requests=self._normalize_tool_requests(result.function_calls),
                backend=self._api_mode,
            )

        result = create_response(
            model=model,
            input_items=messages,
            tools=tools,
            tool_choice="auto",
            timeout_s=timeout_s,
            enable_real_time_output=enable_real_time_output,
            stream_observer=stream_observer,
        )
        return ModelResponse(
            text=result.output_text,
            raw=result.raw,
            usage=None,
            tool_requests=self._normalize_tool_requests(result.function_calls),
            backend=self._api_mode,
        )


__all__ = ["ModelProvider", "ModelResponse", "OpenAIError"]
