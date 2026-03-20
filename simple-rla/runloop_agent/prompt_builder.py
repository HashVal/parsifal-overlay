from __future__ import annotations

import json
from typing import Any

from runloop_agent.step import StepContext, StepSpec


def _json_block(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def _summarize_schema(schema: Any) -> list[str]:
    if not isinstance(schema, dict) or not schema:
        return ["Return one JSON object."]

    schema_type = schema.get("type")
    required = schema.get("required") or []
    properties = schema.get("properties") or {}

    lines: list[str] = []
    if schema_type == "object" and isinstance(properties, dict) and properties:
        lines.append("Return one JSON object with these fields:")
        for name, prop in properties.items():
            if not isinstance(prop, dict):
                lines.append(f"- {name}: value")
                continue
            parts: list[str] = []
            prop_type = prop.get("type")
            if prop_type == "array":
                item_type = None
                items = prop.get("items")
                if isinstance(items, dict):
                    item_type = items.get("type")
                if item_type:
                    parts.append(f"array of {item_type}s")
                else:
                    parts.append("array")
                if "maxItems" in prop:
                    parts.append(f"at most {prop['maxItems']} items")
            elif prop_type:
                parts.append(str(prop_type))
                if "maxLength" in prop:
                    parts.append(f"max {prop['maxLength']} chars")
            else:
                parts.append("value")
            lines.append(f"- {name}: {', '.join(parts)}")
        if required:
            lines.append("Required fields: " + ", ".join(str(x) for x in required))
    else:
        lines.append("Return a valid JSON value that matches the required structure.")
        if schema_type:
            lines.append(f"Top-level type: {schema_type}")
    lines.append("Return only the final JSON answer.")
    return lines


def _section(title: str, body: str | list[str]) -> list[str]:
    lines = [f"[{title}]"]
    if isinstance(body, str):
        lines.append(body)
    else:
        lines.extend(body)
    lines.append("")
    return lines


def build_step_prompt(spec: StepSpec, ctx: StepContext) -> str:
    output_schema = spec.metadata.get("output_schema") or {}
    model_hint = spec.metadata.get("model") or ""
    allowed_tools = spec.metadata.get("model_tools") or []

    lines: list[str] = []
    lines.extend(_section("runtime_constraints", [
        "You are executing one workflow step.",
        "Use only the tools explicitly exposed to this step.",
        "Your final answer must satisfy the output contract.",
        "Do not include markdown fences or extra prose in the final answer.",
    ]))
    lines.extend(_section("step_identity", [
        f"Phase: {ctx.phase_id}",
        f"Step: {ctx.step_id}",
        f"Attempt: {ctx.attempt}",
        *( [f"Model hint: {model_hint}"] if model_hint else [] ),
    ]))
    lines.extend(_section("task", spec.description or "Return a valid JSON object."))
    lines.extend(_section("visible_inputs", _json_block(ctx.inputs)))
    if allowed_tools:
        tool_summary = [
            {
                "name": t.get("name"),
                "description": t.get("description"),
                "parameters": t.get("parameters"),
            }
            for t in allowed_tools
        ]
        lines.extend(_section("tool_contract", [
            "Available tools:",
            _json_block(tool_summary),
            "Use tools only when needed. After any tool use, return the final answer under the output contract.",
        ]))
    lines.extend(_section("output_contract", [
        *_summarize_schema(output_schema),
        "Final answer format: JSON only.",
    ]))
    return "\n".join(lines)
