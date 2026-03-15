from __future__ import annotations

from typing import Any

import os

from runloop_agent.model_provider import ModelProvider, OpenAIError
from runloop_agent.output_parser import parse_model_output
from runloop_agent.prompt_builder import build_step_prompt
from runloop_agent.step import BaseStep, StepContext, StepErrorInfo, StepResult, StepSpec, StepStatus
from runloop_agent.step_validator import validate_step_output


class LLMStep(BaseStep):
    """Minimal no-tool LLM step for milestone 1."""

    def __init__(self, spec: StepSpec, provider: ModelProvider | None = None) -> None:
        super().__init__(spec)
        self._provider = provider or ModelProvider()

    def build_prompt(self, ctx: StepContext) -> str | dict[str, Any]:
        return build_step_prompt(self.spec, ctx)

    def run(self, ctx: StepContext) -> StepResult:
        prompt = self.build_prompt(ctx)
        if not isinstance(prompt, str):
            return StepResult(
                step_id=self.step_id,
                status=StepStatus.INVALID,
                error=StepErrorInfo(code="invalid_prompt", message="llm step prompt must be text"),
            )

        model = str(self.spec.metadata.get("model") or os.environ.get("OPENAI_MODEL") or "").strip()
        if not model:
            return StepResult(
                step_id=self.step_id,
                status=StepStatus.INVALID,
                error=StepErrorInfo(code="missing_model", message="llm step requires metadata.model"),
            )

        try:
            response = self._provider.generate(
                model=model,
                prompt=prompt,
                response_schema=self.spec.metadata.get("output_schema"),
                timeout_s=int(self.spec.metadata.get("timeout_s") or os.environ.get("OPENAI_TIMEOUT_S") or 90),
            )
        except OpenAIError as exc:
            return StepResult(
                step_id=self.step_id,
                status=StepStatus.FAILED,
                error=StepErrorInfo(code="model_error", message=str(exc)),
            )

        parse_result = parse_model_output(response.text)
        if not parse_result.ok:
            return StepResult(
                step_id=self.step_id,
                status=StepStatus.INVALID,
                output=response.text,
                diagnostics={
                    "raw_model_output": response.text,
                    "parse_ok": False,
                    "parse_error": parse_result.error,
                },
                error=StepErrorInfo(code="parse_error", message=parse_result.error or "failed to parse model output"),
            )

        validation = validate_step_output(self.spec, parse_result.parsed)
        status = StepStatus.COMPLETED if validation.accepted else StepStatus.INVALID
        return StepResult(
            step_id=self.step_id,
            status=status,
            output=parse_result.parsed,
            compact_output=parse_result.parsed,
            produced_artifacts={f"artifact:{self.step_id}": parse_result.parsed},
            diagnostics={
                "raw_model_output": response.text,
                "parse_ok": True,
                "validation_errors": list(validation.errors),
                "validation_warnings": list(validation.warnings),
            },
            error=None if validation.accepted else StepErrorInfo(
                code="validation_error",
                message="; ".join(validation.errors) or "step output failed validation",
                details={"errors": list(validation.errors)},
            ),
        )

    def validate_exit(self, result: StepResult, ctx: StepContext) -> bool:
        del ctx
        return result.status == StepStatus.COMPLETED
