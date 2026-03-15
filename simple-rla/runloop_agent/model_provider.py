from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from runloop_agent.openai_responses import OpenAIError, create_response


@dataclass(slots=True)
class ModelResponse:
    text: str
    raw: Any = None
    usage: dict[str, Any] | None = None


class ModelProvider:
    """Minimal no-tool model provider for milestone 1.

    This deliberately supports only a single text-generation path.
    Tool-enabled execution is out of scope for M1.
    """

    def generate(
        self,
        *,
        model: str,
        prompt: str,
        response_schema: dict[str, Any] | None = None,
        timeout_s: int = 90,
    ) -> ModelResponse:
        del response_schema  # Reserved for future structured output handling.
        result = create_response(
            model=model,
            input_items=prompt,
            tools=None,
            tool_choice=None,
            timeout_s=timeout_s,
        )
        return ModelResponse(text=result.output_text, raw=result.raw, usage=None)


__all__ = ["ModelProvider", "ModelResponse", "OpenAIError"]
