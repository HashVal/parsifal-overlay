from __future__ import annotations

import argparse
import asyncio
import json
import re
from typing import Any, Dict

from .config import load_config
from .openai_responses import create_response
from .runloop import RunloopAgent


_NAME_SAFE = re.compile(r"[^a-zA-Z0-9_-]+")


def _to_tool_name(fq_tool: str) -> str:
    # Responses tool names should be simple; replace dots.
    return _NAME_SAFE.sub("_", fq_tool.replace(".", "__"))


def _build_tool_map(tools: dict) -> tuple[dict[str, str], dict[str, str]]:
    name_to_fq: dict[str, str] = {}
    fq_to_name: dict[str, str] = {}
    for fq, spec in tools.items():
        n = _to_tool_name(fq)
        if n in name_to_fq:
            i = 2
            while f"{n}_{i}" in name_to_fq:
                i += 1
            n = f"{n}_{i}"
        name_to_fq[n] = fq
        fq_to_name[fq] = n
    return name_to_fq, fq_to_name


def _mcp_to_responses_tool_schema(tool_name: str, spec) -> dict:
    # Responses API uses a flattened function tool schema.
    return {
        "type": "function",
        "name": tool_name,
        "description": spec.description or "",
        "parameters": spec.input_schema or {"type": "object"},
    }


def _msg(role: str, text: str) -> dict:
    # Responses "input" supports message items with typed content.
    return {
        "role": role,
        "content": [{"type": "input_text", "text": text}],
    }


def _tool_out(call_id: str, output: str) -> dict:
    # Standard tool output item.
    return {
        "type": "function_call_output",
        "call_id": call_id,
        "output": output,
    }


async def main() -> None:
    p = argparse.ArgumentParser(description="Runloop agent using OpenAI Responses + MCP tools")
    p.add_argument("--config", required=True, help="Path to MCP config TOML")
    p.add_argument("--model", required=True, help="OpenAI model id")
    p.add_argument("--jira-key", default="", help="Optional Jira key to start from")
    p.add_argument("--max-steps", type=int, default=16)
    args = p.parse_args()

    cfg = load_config(args.config)

    system_prompt = (
        "You are a kernel RCA runloop agent. "
        "Use tools to fetch Jira issues (jira_get/jira_search), scan code, and run device checks. "
        "Keep outputs short; prefer tool calls. "
        "When you have enough evidence, write a final RCA summary."
    )

    async with RunloopAgent(cfg) as agent:
        mcp_tools = agent.list_tools()
        name_to_fq, _fq_to_name = _build_tool_map(mcp_tools)
        tools = [_mcp_to_responses_tool_schema(name, mcp_tools[fq]) for name, fq in name_to_fq.items()]

        input_items: list[dict[str, Any]] = [
            _msg("system", system_prompt),
        ]

        if args.jira_key:
            input_items.append(
                _msg(
                    "user",
                    f"Start RCA for Jira issue {args.jira_key}. Fetch details and propose first-round DEBUG_STEPS.",
                )
            )
        else:
            input_items.append(_msg("user", "List tools and explain your plan."))

        prev_id: str | None = None

        for _ in range(args.max_steps):
            rr = create_response(
                model=args.model,
                input_items=input_items,
                tools=tools,
                tool_choice="auto",
                previous_response_id=prev_id,
                temperature=0.2,
            )
            prev_id = rr.response_id

            if rr.function_calls:
                # For subsequent turns, only send tool outputs (Responses keeps context via previous_response_id).
                input_items = []

                for fc in rr.function_calls:
                    fq = name_to_fq.get(fc.name)
                    if not fq:
                        out = json.dumps({"error": f"unknown tool: {fc.name}"})
                    else:
                        try:
                            tool_args = json.loads(fc.arguments_json) if fc.arguments_json.strip() else {}
                            if not isinstance(tool_args, dict):
                                raise ValueError("tool arguments must be an object")
                            out = await agent.call_tool(fq, tool_args)
                        except Exception as exc:
                            out = json.dumps({"error": str(exc)})

                    input_items.append(_tool_out(fc.call_id, out))

                continue

            # No tool calls -> final.
            if rr.output_text:
                print(rr.output_text)
            else:
                print(json.dumps(rr.raw, ensure_ascii=False, indent=2))
            return

    raise SystemExit("max steps exceeded")


if __name__ == "__main__":
    asyncio.run(main())
