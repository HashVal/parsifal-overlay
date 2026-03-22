from __future__ import annotations

import json
import os
from pathlib import Path
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
            arguments = json.loads(arguments)
        if not isinstance(arguments, dict):
            arguments = {}
        out.append({"name": str(name), "arguments": arguments})
    return out


def _json_size(value: Any) -> int:
    try:
        return len(json.dumps(value, ensure_ascii=False, default=str))
    except Exception:
        return len(str(value))


def _prompt_observability(spec: StepSpec, ctx: StepContext, prompt: str) -> dict[str, Any]:
    visible_input_sizes = {
        str(key): _json_size(value)
        for key, value in sorted((ctx.inputs or {}).items(), key=lambda kv: str(kv[0]))
    }
    top_visible_inputs = [
        {"key": key, "chars": size}
        for key, size in sorted(visible_input_sizes.items(), key=lambda kv: kv[1], reverse=True)[:10]
    ]
    return {
        "workflow_id": ctx.metadata.get("workflow_id"),
        "phase_id": ctx.phase_id,
        "step_id": ctx.step_id,
        "prompt_chars": len(prompt),
        "visible_input_count": len(ctx.inputs or {}),
        "visible_inputs_chars": _json_size(ctx.inputs or {}),
        "top_visible_inputs": top_visible_inputs,
        "allowed_tool_count": len(ctx.allowed_tools or ()),
        "allowed_tool_family_count": len(ctx.allowed_tool_families or ()),
        "output_schema_chars": _json_size(spec.metadata.get("output_schema") or {}),
    }


def _log_prompt_observability(obs: dict[str, Any], *, mode: str) -> None:
    top_inputs = ", ".join(f"{item['key']}={item['chars']}" for item in obs.get("top_visible_inputs", [])) or "<none>"
    print(
        "[simple_rla.llm_prompt]"
        f" mode={mode}"
        f" workflow={obs.get('workflow_id')}"
        f" phase={obs.get('phase_id')}"
        f" step={obs.get('step_id')}"
        f" prompt_chars={obs.get('prompt_chars')}"
        f" visible_input_count={obs.get('visible_input_count')}"
        f" visible_inputs_chars={obs.get('visible_inputs_chars')}"
        f" output_schema_chars={obs.get('output_schema_chars')}"
        f" top_visible_inputs={top_inputs}"
    )


def _build_stream_observer(ctx: StepContext):
    if not ctx.metadata.get("enable_real_time_output"):
        return None, None
    run_root = str(ctx.metadata.get("run_root") or "").strip()
    if not run_root:
        return None, None
    stream_path = Path(run_root) / "step_results" / f"{ctx.phase_id}__{ctx.step_id}.stream.log"
    stream_path.parent.mkdir(parents=True, exist_ok=True)
    stream_path.write_text("", encoding="utf-8")
    print(
        "[simple_rla.llm_stream]"
        f" workflow={ctx.metadata.get('workflow_id')}"
        f" phase={ctx.phase_id}"
        f" step={ctx.step_id}"
        f" stream_log={stream_path}"
    )

    def observer(delta: str) -> None:
        if not isinstance(delta, str) or not delta:
            return
        with stream_path.open("a", encoding="utf-8") as f:
            f.write(delta)
            f.flush()

    return observer, str(stream_path)


def _build_final_result(
    *,
    spec: StepSpec,
    prompt: str,
    response_text: str,
    parse_mode_hint: str | None = None,
    prior_messages: list[dict[str, Any]] | None = None,
    tool_calls: list[Any] | None = None,
    diagnostics_extra: dict[str, Any] | None = None,
) -> StepResult:
    parse_result = parse_model_output(response_text)
    messages = list(prior_messages or [])
    messages.append({"role": "user", "content": prompt})
    messages.append({"role": "assistant", "content": response_text})
    diagnostics = {
        "raw_model_output": response_text,
        **(diagnostics_extra or {}),
    }
    if not parse_result.ok:
        diagnostics.update({
            "parse_ok": False,
            "parse_error": parse_result.error,
            "parse_mode": parse_result.mode if parse_mode_hint is None else parse_mode_hint,
            "extracted_json_text": parse_result.extracted_text,
        })
        return StepResult(
            step_id=spec.step_id,
            status=StepStatus.INVALID,
            output=response_text,
            messages=messages,
            tool_calls=list(tool_calls or []),
            diagnostics=diagnostics,
            error=StepErrorInfo(code="parse_error", message=parse_result.error or "failed to parse model output"),
        )

    validation = validate_step_output(spec, parse_result.parsed)
    status = StepStatus.COMPLETED if validation.accepted else StepStatus.INVALID
    diagnostics.update({
        "parse_ok": True,
        "parse_mode": parse_result.mode if parse_mode_hint is None else parse_mode_hint,
        "extracted_json_text": parse_result.extracted_text,
        "validation_errors": list(validation.errors),
        "validation_warnings": list(validation.warnings),
    })
    return StepResult(
        step_id=spec.step_id,
        status=status,
        output=parse_result.parsed,
        compact_output=parse_result.parsed,
        messages=messages,
        tool_calls=list(tool_calls or []),
        produced_artifacts={f"artifact:{spec.step_id}": parse_result.parsed},
        diagnostics=diagnostics,
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
    prompt_obs = _prompt_observability(spec, ctx, prompt)
    _log_prompt_observability(prompt_obs, mode="llm_step")
    model = str(spec.metadata.get("model") or os.environ.get("OPENAI_MODEL") or "").strip()
    if not model:
        return StepResult(
            step_id=spec.step_id,
            status=StepStatus.INVALID,
            diagnostics=prompt_obs,
            error=StepErrorInfo(code="missing_model", message="llm step requires metadata.model or OPENAI_MODEL"),
        )
    stream_observer, stream_path = _build_stream_observer(ctx)
    try:
        response = provider.generate(
            model=model,
            prompt=prompt,
            response_schema=spec.metadata.get("output_schema"),
            timeout_s=int(spec.metadata.get("timeout_s") or os.environ.get("OPENAI_TIMEOUT_S") or 90),
            enable_real_time_output=bool(ctx.metadata.get("enable_real_time_output")),
            stream_observer=stream_observer,
        )
    except OpenAIError as exc:
        diagnostics = dict(prompt_obs)
        if stream_path:
            diagnostics["stream_log_path"] = stream_path
        return StepResult(
            step_id=spec.step_id,
            status=StepStatus.FAILED,
            diagnostics=diagnostics,
            error=StepErrorInfo(code="model_error", message=str(exc)),
        )
    diagnostics_extra = dict(prompt_obs)
    if stream_path:
        diagnostics_extra["stream_log_path"] = stream_path
    return _build_final_result(
        spec=spec,
        prompt=prompt,
        response_text=response.text,
        diagnostics_extra=diagnostics_extra,
    )


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
    prompt_obs = _prompt_observability(spec, ctx, prompt)
    _log_prompt_observability(prompt_obs, mode="llm_tool_step")
    model = str(spec.metadata.get("model") or os.environ.get("OPENAI_MODEL") or "").strip()
    if not model:
        return StepResult(
            step_id=spec.step_id,
            status=StepStatus.INVALID,
            diagnostics=prompt_obs,
            error=StepErrorInfo(code="missing_model", message="llm tool step requires metadata.model or OPENAI_MODEL"),
        )

    registry = ToolRegistry(mcp_client.list_tools())
    selected_tools = registry.select(spec.allowed_tools, spec.allowed_tool_families)
    model_tools = [tool.to_model_tool() for tool in selected_tools]
    if not model_tools:
        return StepResult(
            step_id=spec.step_id,
            status=StepStatus.INVALID,
            diagnostics={**prompt_obs, "selected_tool_count": 0},
            error=StepErrorInfo(code="no_tools_available", message="llm tool step resolved no allowed tools"),
        )

    messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
    tool_calls: list[Any] = []
    max_turns = int(spec.metadata.get("max_model_turns") or 4)
    max_tool_calls = int(spec.metadata.get("max_tool_calls") or 4)
    timeout_s = int(spec.metadata.get("timeout_s") or os.environ.get("OPENAI_TIMEOUT_S") or 90)
    stream_observer, stream_path = _build_stream_observer(ctx)

    try:
        for turn_idx in range(max_turns):
            message_chars = _json_size(messages)
            print(
                "[simple_rla.llm_prompt]"
                f" mode=llm_tool_step_turn"
                f" workflow={ctx.metadata.get('workflow_id')}"
                f" phase={ctx.phase_id}"
                f" step={ctx.step_id}"
                f" turn={turn_idx + 1}"
                f" message_chars={message_chars}"
                f" tool_calls_so_far={len(tool_calls)}"
                f" selected_tool_count={len(model_tools)}"
            )
            response = provider.generate_with_tools(
                model=model,
                messages=messages,
                tools=model_tools,
                timeout_s=timeout_s,
                enable_real_time_output=bool(ctx.metadata.get("enable_real_time_output")),
                stream_observer=stream_observer,
            )
            response_text = getattr(response, "output_text", None) or ""
            requests = _extract_tool_requests(getattr(response, "raw", None))
            if not requests:
                diagnostics_extra = {
                    **prompt_obs,
                    "selected_tool_count": len(model_tools),
                    "tool_loop_message_chars": _json_size(messages),
                    "tool_call_count": len(tool_calls),
                }
                if stream_path:
                    diagnostics_extra["stream_log_path"] = stream_path
                return _build_final_result(
                    spec=spec,
                    prompt=prompt,
                    response_text=response_text,
                    prior_messages=[],
                    tool_calls=tool_calls,
                    diagnostics_extra=diagnostics_extra,
                )
            for req in requests:
                if len(tool_calls) >= max_tool_calls:
                    diagnostics = {
                        **prompt_obs,
                        "selected_tool_count": len(model_tools),
                        "tool_loop_message_chars": _json_size(messages),
                        "tool_call_count": len(tool_calls),
                    }
                    if stream_path:
                        diagnostics["stream_log_path"] = stream_path
                    return StepResult(
                        step_id=spec.step_id,
                        status=StepStatus.INVALID,
                        messages=messages,
                        tool_calls=tool_calls,
                        diagnostics=diagnostics,
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
        diagnostics = {
            **prompt_obs,
            "selected_tool_count": len(model_tools),
            "tool_loop_message_chars": _json_size(messages),
            "tool_call_count": len(tool_calls),
        }
        if stream_path:
            diagnostics["stream_log_path"] = stream_path
        return StepResult(
            step_id=spec.step_id,
            status=StepStatus.INVALID,
            messages=messages,
            tool_calls=tool_calls,
            diagnostics=diagnostics,
            error=StepErrorInfo(code="max_model_turns_exceeded", message="model turn budget exceeded"),
        )
    except OpenAIError as exc:
        diagnostics = {
            **prompt_obs,
            "selected_tool_count": len(model_tools),
            "tool_loop_message_chars": _json_size(messages),
            "tool_call_count": len(tool_calls),
        }
        if stream_path:
            diagnostics["stream_log_path"] = stream_path
        return StepResult(
            step_id=spec.step_id,
            status=StepStatus.FAILED,
            messages=messages,
            tool_calls=tool_calls,
            diagnostics=diagnostics,
            error=StepErrorInfo(code="model_error", message=str(exc)),
        )
    except Exception as exc:
        diagnostics = {
            **prompt_obs,
            "selected_tool_count": len(model_tools),
            "tool_loop_message_chars": _json_size(messages),
            "tool_call_count": len(tool_calls),
        }
        if stream_path:
            diagnostics["stream_log_path"] = stream_path
        return StepResult(
            step_id=spec.step_id,
            status=StepStatus.FAILED,
            messages=messages,
            tool_calls=tool_calls,
            diagnostics=diagnostics,
            error=StepErrorInfo(code="tool_loop_error", message=str(exc)),
        )
