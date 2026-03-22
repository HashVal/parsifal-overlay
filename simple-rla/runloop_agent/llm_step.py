from __future__ import annotations

from runloop_agent.mcp_client import McpClient
from runloop_agent.model_provider import ModelProvider
from runloop_agent.step import BaseStep, StepContext, StepResult, StepSpec, StepStatus
from runloop_agent.step_runner import run_llm_step, run_llm_tool_step


class LLMStep(BaseStep):
    def __init__(self, spec: StepSpec, provider: ModelProvider | None = None) -> None:
        super().__init__(spec)
        self._provider = provider or ModelProvider()

    def build_prompt(self, ctx: StepContext):
        del ctx
        return "delegated to step_runner"

    def run(self, ctx: StepContext) -> StepResult:
        return run_llm_step(self.spec, ctx, provider=self._provider)

    def validate_exit(self, result: StepResult, ctx: StepContext) -> bool:
        del ctx
        return result.status == StepStatus.COMPLETED


class LLMToolStep(BaseStep):
    def __init__(self, spec: StepSpec, *, mcp_client: McpClient, provider: ModelProvider | None = None) -> None:
        super().__init__(spec)
        self._provider = provider or ModelProvider()
        self._mcp_client = mcp_client

    def build_prompt(self, ctx: StepContext):
        del ctx
        return "delegated to step_runner"

    def run(self, ctx: StepContext) -> StepResult:
        return run_llm_tool_step(self.spec, ctx, mcp_client=self._mcp_client, provider=self._provider)

    def validate_exit(self, result: StepResult, ctx: StepContext) -> bool:
        del ctx
        return result.status == StepStatus.COMPLETED
