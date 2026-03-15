from __future__ import annotations

from typing import Any

from runloop_agent.llm_step import LLMStep, LLMToolStep
from runloop_agent.mcp_client import McpClient
from runloop_agent.step import BaseStep, StepContext, StepResult, StepSpec, StepStatus


class DeterministicArtifactStep(BaseStep):
    def build_prompt(self, ctx: StepContext) -> str | dict[str, Any]:
        del ctx
        return {"mode": "deterministic_artifact"}

    def run(self, ctx: StepContext) -> StepResult:
        key = str(self.spec.metadata.get("artifact_key") or f"artifact:{self.step_id}")
        value = self.spec.metadata.get("artifact_value")
        output = {
            "step_id": self.step_id,
            "phase_id": ctx.phase_id,
            "artifact_key": key,
            "artifact_value": value,
        }
        return StepResult(
            step_id=self.step_id,
            status=StepStatus.COMPLETED,
            output=output,
            compact_output={"artifact_key": key},
            produced_artifacts={key: value},
            notes=[f"produced artifact: {key}"],
        )

    def validate_exit(self, result: StepResult, ctx: StepContext) -> bool:
        del ctx
        return result.status == StepStatus.COMPLETED


def build_step(step_cfg: dict[str, Any], *, mcp_client: McpClient | None = None) -> BaseStep:
    if not isinstance(step_cfg, dict):
        raise ValueError(f"invalid step config: {step_cfg!r}")

    step_type = str(step_cfg.get("type") or "").strip()
    step_id = str(step_cfg.get("id") or "").strip()
    if not step_type or not step_id:
        raise ValueError(f"step requires id and type: {step_cfg!r}")

    config = dict(step_cfg.get("config") or {})
    description = str(config.get("instruction") or step_cfg.get("description") or "").strip()
    spec = StepSpec(
        step_id=step_id,
        description=description,
        allowed_tool_families=tuple(str(x) for x in (config.get("allowed_tool_families") or [])),
        allowed_tools=tuple(str(x) for x in (config.get("allowed_tools") or [])),
        metadata=config,
    )

    if step_type == "deterministic_step":
        return DeterministicArtifactStep(spec)
    if step_type == "llm_step":
        return LLMStep(spec)
    if step_type == "llm_tool_step":
        if mcp_client is None:
            raise ValueError("llm_tool_step requires an initialized mcp_client")
        return LLMToolStep(spec, mcp_client=mcp_client)

    raise ValueError(f"unknown step type: {step_type}")
