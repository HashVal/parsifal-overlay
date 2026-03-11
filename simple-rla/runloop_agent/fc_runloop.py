from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Tuple

# Allow running as a script from inside the runloop_agent/ directory:
#   python3 fc_runloop.py ...
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from runloop_agent.config import load_config
from runloop_agent.openai_fc import chat_completions
from runloop_agent.runloop import RunloopAgent


_NAME_SAFE = re.compile(r"[^a-zA-Z0-9_-]+")


def _to_fc_name(fq_tool: str) -> str:
    # OpenAI tool names are safest as [a-zA-Z0-9_-]. Replace dots and other chars.
    # Example: "jira.jira_get" -> "jira__jira_get".
    return _NAME_SAFE.sub("_", fq_tool.replace(".", "__"))


def _from_fc_name(name: str) -> str:
    # Reverse only the dot mapping; other sanitization is lossy.
    # We keep a mapping table at runtime to ensure reversibility.
    return name


@dataclass(frozen=True)
class ToolMap:
    fc_to_fq: dict[str, str]
    fq_to_fc: dict[str, str]


def _build_tool_map(tools: dict) -> ToolMap:
    fc_to_fq: dict[str, str] = {}
    fq_to_fc: dict[str, str] = {}
    for fq_name, spec in tools.items():
        fc = _to_fc_name(fq_name)
        # Collision handling: suffix if needed.
        if fc in fc_to_fq:
            i = 2
            while f"{fc}_{i}" in fc_to_fq:
                i += 1
            fc = f"{fc}_{i}"
        fc_to_fq[fc] = fq_name
        fq_to_fc[fq_name] = fc
    return ToolMap(fc_to_fq=fc_to_fq, fq_to_fc=fq_to_fc)


def _mcp_to_openai_tool_schema(tool_name_fc: str, spec) -> dict:
    # MCP inputSchema is already JSON Schema-ish.
    return {
        "type": "function",
        "function": {
            "name": tool_name_fc,
            "description": spec.description or "",
            "parameters": spec.input_schema or {"type": "object"},
        },
    }


async def main() -> None:
    p = argparse.ArgumentParser(description="Runloop agent using OpenAI function calling + MCP tools")
    p.add_argument("--config", required=True, help="Path to MCP config TOML")
    p.add_argument("--model", required=True, help="OpenAI model id")
    p.add_argument("--jira-key", default="", help="Optional Jira key to start from")
    p.add_argument("--max-steps", type=int, default=12)
    args = p.parse_args()

    cfg = load_config(args.config)

    system_prompt = (
        "You are a kernel RCA runloop agent. "
        "Use tools to fetch Jira issues, scan code, and run device checks. "
        "Keep outputs short; prefer tool calls. "
        "When you have enough evidence, write a final RCA summary."
    )

    async with RunloopAgent(cfg) as agent:
        tools = agent.list_tools()
        tool_map = _build_tool_map(tools)
        openai_tools = [_mcp_to_openai_tool_schema(fc, tools[fq]) for fc, fq in tool_map.fc_to_fq.items()]

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
        ]

        if args.jira_key:
            messages.append({"role": "user", "content": f"Start RCA for Jira issue {args.jira_key}. Fetch details and propose first-round DEBUG_STEPS."})
        else:
            messages.append({"role": "user", "content": "List available tools and explain what you can do."})

        for _step in range(args.max_steps):
            mm = chat_completions(
                model=args.model,
                messages=messages,
                tools=openai_tools,
                tool_choice="auto",
                temperature=0.2,
            )

            # Tool calls
            if mm.tool_calls:
                messages.append({"role": "assistant", "content": mm.content, "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": tc.arguments_json},
                    }
                    for tc in mm.tool_calls
                ]})

                for tc in mm.tool_calls:
                    fq = tool_map.fc_to_fq.get(tc.name)
                    if not fq:
                        tool_out = json.dumps({"error": f"unknown tool: {tc.name}"})
                    else:
                        try:
                            tool_args = json.loads(tc.arguments_json) if tc.arguments_json.strip() else {}
                            if not isinstance(tool_args, dict):
                                raise ValueError("tool arguments must be an object")
                            tool_out = await agent.call_tool(fq, tool_args)
                        except Exception as exc:
                            tool_out = json.dumps({"error": str(exc)})

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": tc.name,
                        "content": tool_out,
                    })

                continue

            # Final
            if mm.content:
                print(mm.content)
            return

    raise SystemExit("max steps exceeded")


if __name__ == "__main__":
    asyncio.run(main())
