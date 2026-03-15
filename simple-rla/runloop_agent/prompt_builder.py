from __future__ import annotations

import json
from typing import Any

from runloop_agent.step import StepContext, StepSpec
from runloop_agent.tool_registry import ToolInfo


def _json_block(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def build_step_prompt(spec: StepSpec, ctx: StepContext) -> str:
    output_schema = spec.metadata.get("output_schema") or {}
    model_hint = spec.metadata.get("model") or ""
    allowed_tools = spec.metadata.get("model_tools") or []

    lines: list[str] = []
    lines.append("You are executing one workflow step.")
    lines.append(f"Phase: {ctx.phase_id}")
    lines.append(f"Step: {ctx.step_id}")
    lines.append(f"Attempt: {ctx.attempt}")
    if model_hint:
        lines.append(f"Model hint: {model_hint}")
    lines.append("")
    lines.append("Task:")
    lines.append(spec.description or "Return a valid JSON object.")
    lines.append("")
    lines.append("Visible inputs/artifacts:")
    lines.append(_json_block(ctx.inputs))
    lines.append("")
    if allowed_tools:
        lines.append("Available tools:")
        tool_summary = [
            {
                "name": t.get("name"),
                "description": t.get("description"),
                "parameters": t.get("parameters"),
            }
            for t in allowed_tools
        ]
        lines.append(_json_block(tool_summary))
        lines.append("Use only the listed tools when needed. After tool use, produce the final answer as JSON only.")
        lines.append("")
    lines.append("Output requirements:")
    if output_schema:
        lines.append(_json_block(output_schema))
    else:
        lines.append('Return a JSON object.')
    lines.append("")
    lines.append("Important: respond with JSON only. Do not include markdown fences or extra prose.")
    return "\n".join(lines)
