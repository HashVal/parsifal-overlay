from __future__ import annotations

from typing import Any

from runloop_agent.mcp_client import McpClient
from runloop_agent.step import BaseStep, StepContext, StepErrorInfo, StepResult, StepSpec, StepStatus
from runloop_agent.tool_executor import execute_tool_call
from runloop_agent.tool_registry import ToolRegistry


def _lookup_path(root: Any, path: list[str]) -> Any:
    current = root
    for part in path:
        if isinstance(current, dict):
            if part not in current:
                raise KeyError(part)
            current = current[part]
            continue
        if isinstance(current, list):
            try:
                index = int(part)
            except ValueError as exc:
                raise KeyError(part) from exc
            current = current[index]
            continue
        raise KeyError(part)
    return current


def _resolve_binding(expr: str, ctx: StepContext) -> Any:
    if not (expr.startswith("${") and expr.endswith("}")):
        return expr
    inner = expr[2:-1].strip()
    if not inner:
        return expr
    parts = inner.split(".")
    if len(parts) < 2:
        raise ValueError(f"invalid binding expression: {expr}")
    scope = parts[0]
    if scope == "workflow":
        if len(parts) < 3 or parts[1] != "inputs":
            raise ValueError(f"unsupported workflow binding: {expr}")
        return _lookup_path(ctx.inputs, parts[2:])
    if scope == "artifacts":
        return _lookup_path(ctx.available_artifacts, parts[1:])
    raise ValueError(f"unsupported binding scope: {expr}")


def _resolve_value(value: Any, ctx: StepContext) -> Any:
    if isinstance(value, str):
        return _resolve_binding(value, ctx)
    if isinstance(value, list):
        return [_resolve_value(item, ctx) for item in value]
    if isinstance(value, dict):
        return {key: _resolve_value(item, ctx) for key, item in value.items()}
    return value


class ToolStep(BaseStep):
    def __init__(self, spec: StepSpec, *, mcp_client: McpClient) -> None:
        super().__init__(spec)
        self._mcp_client = mcp_client

    def build_prompt(self, ctx: StepContext) -> dict[str, Any]:
        del ctx
        return {"mode": "tool_step", "tool": self.spec.metadata.get("tool")}

    def run(self, ctx: StepContext) -> StepResult:
        tool_name = str(self.spec.metadata.get("tool") or "").strip()
        if not tool_name:
            return StepResult(
                step_id=self.step_id,
                status=StepStatus.INVALID,
                error=StepErrorInfo(code="missing_tool", message="tool_step requires config.tool"),
            )

        outputs_cfg = self.spec.metadata.get("outputs") or {}
        artifact_key = str(outputs_cfg.get("artifact_key") or f"artifact:{self.step_id}").strip()
        nullable = bool(outputs_cfg.get("nullable", False))
        raw_args = self.spec.metadata.get("args") or {}
        if not isinstance(raw_args, dict):
            return StepResult(
                step_id=self.step_id,
                status=StepStatus.INVALID,
                error=StepErrorInfo(code="invalid_args", message="tool_step config.args must be a mapping"),
            )

        try:
            resolved_args = _resolve_value(raw_args, ctx)
        except Exception as exc:
            return StepResult(
                step_id=self.step_id,
                status=StepStatus.INVALID,
                error=StepErrorInfo(code="binding_error", message=str(exc)),
                diagnostics={"raw_args": raw_args},
            )

        registry = ToolRegistry(self._mcp_client.list_tools())
        try:
            step_tool_call, tool_messages = execute_tool_call(
                mcp_client=self._mcp_client,
                registry=registry,
                spec=self.spec,
                tool_name=tool_name,
                arguments=resolved_args,
            )
        except Exception as exc:
            return StepResult(
                step_id=self.step_id,
                status=StepStatus.FAILED,
                error=StepErrorInfo(code="tool_execution_failed", message=str(exc)),
                diagnostics={"tool": tool_name, "resolved_args": resolved_args},
            )

        tool_output = step_tool_call.output
        content = tool_output.get("content") if isinstance(tool_output, dict) else None
        if step_tool_call.success is False:
            return StepResult(
                step_id=self.step_id,
                status=StepStatus.FAILED,
                tool_calls=[step_tool_call],
                messages=tool_messages,
                error=StepErrorInfo(code="tool_call_failed", message=step_tool_call.error or "tool call failed"),
                diagnostics={"tool": tool_name, "resolved_args": resolved_args},
            )

        produced_artifacts = {}
        if content is not None or nullable:
            produced_artifacts[artifact_key] = content
        status = StepStatus.COMPLETED if (content is not None or nullable) else StepStatus.INVALID
        error = None if status == StepStatus.COMPLETED else StepErrorInfo(
            code="empty_tool_output",
            message="tool_step produced no artifact content",
        )
        return StepResult(
            step_id=self.step_id,
            status=status,
            output=content,
            compact_output=content,
            tool_calls=[step_tool_call],
            messages=tool_messages,
            produced_artifacts=produced_artifacts,
            error=error,
            diagnostics={
                "tool": tool_name,
                "resolved_args": resolved_args,
                "artifact_key": artifact_key,
                "nullable": nullable,
            },
            notes=[f"tool_step executed: {tool_name}", f"artifact_key: {artifact_key}"],
        )

    def validate_exit(self, result: StepResult, ctx: StepContext) -> bool:
        del ctx
        return result.status == StepStatus.COMPLETED and (bool(result.produced_artifacts) or result.output is not None)
