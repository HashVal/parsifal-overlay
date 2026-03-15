from __future__ import annotations

import os
from typing import Any

from runloop_agent.mcp_client import McpClient
from runloop_agent.model_provider import ModelProvider, OpenAIError
from runloop_agent.output_parser import parse_model_output
from runloop_agent.prompt_builder import build_step_prompt
from runloop_agent.step import StepContext, StepErrorInfo, StepResult, StepSpec, StepStatus
from runloop_agent.step_validator import validate_step_output
from runloop_agent.tool_executor import execute_tool_call
from runloop_agent.tool_registry import ToolRegistry


def _extract_tool_requests(raw: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if raw is None:
        return out
    output = getattr(raw, "output", None)
    if not isinstance(output, list):
        return out
    for item in output:
        item_type = getattr(item, "type", None) or (item.get("type") if isinstance(item, dict) else None)
        if item_type != "function_call":
            continue
        name = getattr(item, "name", None) or (item.get("name") if isinstance(item, dict) else None)
        arguments = getattr(item, "arguments", None) or (item.get("arguments") if isinstance(item, dict) else None)
        if isinstance(arguments, str):
            import json
            arguments = json.loads(arguments)
        if not isinstance(arguments, dict):
            arguments = {}
        out.append({"name": str(name), "arguments": arguments})
    return out


def _build_final_result(
    *,
    spec: StepSpec,
    prompt: str,
    response_text: str,
    parse_mode_hint: str | None = None,
    prior_messages: list[dict[str, Any]] | None = None,
    tool_calls: list[Any] | None = None,
) -> StepResult:
    parse_result = parse_model_output(response_text)
    messages = list(prior_messages or [])
    messages.append({"role": "user", "content": prompt})
    messages.append({"role": "assistant", "content": response_text})
    if not parse_result.ok:
        return StepResult(
            step_id=spec.step_id,
            status=StepStatus.INVALID,
            output=response_text,
            messages=messages,
            tool_calls=list(tool_calls or []),
            diagnostics={
                "raw_model_output": response_text,
                "parse_ok": False,
                "parse_error": parse_result.error,
                "parse_mode": parse_result.mode if parse_mode_hint is None else parse_mode_hint,
                "extracted_json_text": parse_result.extracted_text,
            },
            error=StepErrorInfo(code="parse_error", message=parse_result.error or "failed to parse model output"),
        )

    validation = validate_step_output(spec, parse_result.parsed)
    status = StepStatus.COMPLETED if validation.accepted else StepStatus.INVALID
    return StepResult(
        step_id=spec.step_id,
        status=status,
        output=parse_result.parsed,
        compact_output=parse_result.parsed,
        messages=messages,
        tool_calls=list(tool_calls or []),
        produced_artifacts={f"artifact:{spec.step_id}": parse_result.parsed},
        diagnostics={
            "raw_model_output": response_text,
            "parse_ok": True,
            "parse_mode": parse_result.mode if parse_mode_hint is None else parse_mode_hint,
            "extracted_json_text": parse_result.extracted_text,
            "validation_errors": list(validation.errors),
            "validation_warnings": list(validation.warnings),
        },
        error=None if validation.accepted else StepErrorInfo(
            code="validation_error",
            message="; ".join(validation.errors) or "step output failed validation",
            details={"errors": list(validation.errors)},
        ),
    )


def run_llm_step(spec: StepSpec, ctx: StepContext, provider: ModelProvider | None = None) -> StepResult:
    provider = provider or ModelProvider()
    prompt = build_step_prompt(spec, ctx)
    if not isinstance(prompt, str):
        return StepResult(
            step_id=spec.step_id,
            status=StepStatus.INVALID,
            error=StepErrorInfo(code="invalid_prompt", message="llm step prompt must be text"),
        )
    model = str(spec.metadata.get("model") or os.environ.get("OPENAI_MODEL") or "").strip()
    if not model:
        return StepResult(
            step_id=spec.step_id,
            status=StepStatus.INVALID,
            error=StepErrorInfo(code="missing_model", message="llm step requires metadata.model or OPENAI_MODEL"),
        )
    try:
        response = provider.generate(
            model=model,
            prompt=prompt,
            response_schema=spec.metadata.get("output_schema"),
            timeout_s=int(spec.metadata.get("timeout_s") or os.environ.get("OPENAI_TIMEOUT_S") or 90),
        )
    except OpenAIError as exc:
        return StepResult(
            step_id=spec.step_id,
            status=StepStatus.FAILED,
            error=StepErrorInfo(code="model_error", message=str(exc)),
        )
    return _build_final_result(spec=spec, prompt=prompt, response_text=response.text)


def run_llm_tool_step(
    spec: StepSpec,
    ctx: StepContext,
    *,
    mcp_client: McpClient,
    provider: ModelProvider | None = None,
) -> StepResult:
    provider = provider or ModelProvider()
    prompt = build_step_prompt(spec, ctx)
    if not isinstance(prompt, str):
        return StepResult(
            step_id=spec.step_id,
            status=StepStatus.INVALID,
            error=StepErrorInfo(code="invalid_prompt", message="llm tool step prompt must be text"),
        )
    model = str(spec.metadata.get("model") or os.environ.get("OPENAI_MODEL") or "").strip()
    if not model:
        return StepResult(
            step_id=spec.step_id,
            status=StepStatus.INVALID,
            error=StepErrorInfo(code="missing_model", message="llm tool step requires metadata.model or OPENAI_MODEL"),
        )

    registry = ToolRegistry(mcp_client.list_tools())
    selected_tools = registry.select(spec.allowed_tools, spec.allowed_tool_families)
    model_tools = [tool.to_model_tool() for tool in selected_tools]
    if not model_tools:
        return StepResult(
            step_id=spec.step_id,
            status=StepStatus.INVALID,
            error=StepErrorInfo(code="no_tools_available", message="llm tool step resolved no allowed tools"),
        )

    messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
    tool_calls: list[Any] = []
    max_turns = int(spec.metadata.get("max_model_turns") or 4)
    max_tool_calls = int(spec.metadata.get("max_tool_calls") or 4)
    timeout_s = int(spec.metadata.get("timeout_s") or os.environ.get("OPENAI_TIMEOUT_S") or 90)

    try:
        for _ in range(max_turns):
            response = provider.generate_with_tools(model=model, messages=messages, tools=model_tools, timeout_s=timeout_s)
            response_text = getattr(response, "output_text", None) or ""
            requests = _extract_tool_requests(getattr(response, "raw", None))
            if not requests:
                return _build_final_result(
                    spec=spec,
                    prompt=prompt,
                    response_text=response_text,
                    prior_messages=[],
                    tool_calls=tool_calls,
                )
            for req in requests:
                if len(tool_calls) >= max_tool_calls:
                    return StepResult(
                        step_id=spec.step_id,
                        status=StepStatus.INVALID,
                        messages=messages,
                        tool_calls=tool_calls,
                        error=StepErrorInfo(code="max_tool_calls_exceeded", message="tool call budget exceeded"),
                    )
                step_tool_call, tool_messages = execute_tool_call(
                    mcp_client=mcp_client,
                    registry=registry,
                    spec=spec,
                    tool_name=req["name"],
                    arguments=req["arguments"],
                )
                tool_calls.append(step_tool_call)
                messages.extend(tool_messages)
        return StepResult(
            step_id=spec.step_id,
            status=StepStatus.INVALID,
            messages=messages,
            tool_calls=tool_calls,
            error=StepErrorInfo(code="max_model_turns_exceeded", message="model turn budget exceeded"),
        )
    except OpenAIError as exc:
        return StepResult(
            step_id=spec.step_id,
            status=StepStatus.FAILED,
            messages=messages,
            tool_calls=tool_calls,
            error=StepErrorInfo(code="model_error", message=str(exc)),
        )
    except Exception as exc:
        return StepResult(
            step_id=spec.step_id,
            status=StepStatus.FAILED,
            messages=messages,
            tool_calls=tool_calls,
            error=StepErrorInfo(code="tool_loop_error", message=str(exc)),
        )
