from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from runloop_agent.openai_responses import OpenAIError, create_response


@dataclass(slots=True)
class ModelResponse:
    text: str
    raw: Any = None
    usage: dict[str, Any] | None = None


class ModelProvider:
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
        result = create_response(
            model=model,
            input_items=prompt,
            tools=None,
            tool_choice=None,
            timeout_s=timeout_s,
            enable_real_time_output=enable_real_time_output,
            stream_observer=stream_observer,
        )
        return ModelResponse(text=result.output_text, raw=result.raw, usage=None)

    def generate_with_tools(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        timeout_s: int = 90,
        enable_real_time_output: bool = False,
        stream_observer: Callable[[str], None] | None = None,
    ) -> Any:
        return create_response(
            model=model,
            input_items=messages,
            tools=tools,
            tool_choice="auto",
            timeout_s=timeout_s,
            enable_real_time_output=enable_real_time_output,
            stream_observer=stream_observer,
        )


__all__ = ["ModelProvider", "ModelResponse", "OpenAIError"]
