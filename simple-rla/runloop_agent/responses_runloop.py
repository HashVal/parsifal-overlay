from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict

# Allow running as a script from inside the runloop_agent/ directory:
#   python3 responses_runloop.py ...
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from runloop_agent.config import load_config
from runloop_agent.openai_responses import create_response
from runloop_agent.runloop import RunloopAgent
from runloop_agent.workflow_config import load_workflow, format_message, exit_enabled


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
    p.add_argument("--workflow", default="workflow.yaml", help="Path to workflow YAML")
    p.add_argument("--model", required=True, help="OpenAI model id")
    p.add_argument("--jira-key", default="", help="Optional Jira key to start from")
    p.add_argument("--max-steps", type=int, default=None, help="Override max steps from workflow")
    p.add_argument("--log-level", default=os.environ.get("LOG_LEVEL", "INFO"), help="DEBUG|INFO|WARNING|ERROR")
    args = p.parse_args()

    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    log = logging.getLogger("simple_rla.responses_runloop")

    # Load workflow configuration
    workflow = load_workflow(args.workflow)
    max_steps = args.max_steps if args.max_steps is not None else workflow.execution.max_steps
    no_tool_exit = exit_enabled(workflow, "no_tool_calls", default=True)
    max_steps_exit = exit_enabled(workflow, "max_steps_reached", default=True)
    if not max_steps_exit and args.max_steps is None:
        max_steps = 100000

    log.info("start model=%s jira_key=%s max_steps=%s workflow=%s", args.model, args.jira_key, max_steps, workflow.name)

    cfg = load_config(args.config)

    system_prompt = workflow.llm.system_prompt
    if args.jira_key:
        initial_message = format_message(workflow.llm.initial_message_template, {"jira_key": args.jira_key})
    else:
        initial_message = workflow.llm.default_message

    async with RunloopAgent(cfg) as agent:
        mcp_tools = agent.list_tools()
        log.info("mcp.tools count=%d", len(mcp_tools))
        name_to_fq, _fq_to_name = _build_tool_map(mcp_tools)
        tools = [_mcp_to_responses_tool_schema(name, mcp_tools[fq]) for name, fq in name_to_fq.items()]

        input_items: list[dict[str, Any]] = [
            _msg("system", system_prompt),
            _msg("user", initial_message),
        ]

        prev_id: str | None = None

        for step in range(1, max_steps + 1):
            log.info("step=%d/%d create_response prev_id=%s", step, max_steps, prev_id)
            rr = create_response(
                model=args.model,
                input_items=input_items,
                tools=tools,
                tool_choice=workflow.llm.tool_choice,
                previous_response_id=prev_id,
                temperature=workflow.llm.temperature,
                timeout_s=workflow.execution.request_timeout_s,
            )
            prev_id = rr.response_id
            log.info("response id=%s function_calls=%d", rr.response_id, len(rr.function_calls))

            if rr.function_calls:
                # For subsequent turns, only send tool outputs (Responses keeps context via previous_response_id).
                input_items = []

                for fc in rr.function_calls:
                    fq = name_to_fq.get(fc.name)
                    log.info("tool_call name=%s fq=%s call_id=%s", fc.name, fq, fc.call_id)
                    if not fq:
                        out = json.dumps({"error": f"unknown tool: {fc.name}"})
                    else:
                        try:
                            tool_args = json.loads(fc.arguments_json) if fc.arguments_json.strip() else {}
                            if not isinstance(tool_args, dict):
                                raise ValueError("tool arguments must be an object")
                            out = await agent.call_tool(fq, tool_args)
                        except Exception as exc:
                            if workflow.tools.include_traceback:
                                import traceback
                                out = json.dumps({"error": str(exc), "traceback": traceback.format_exc()})
                            else:
                                out = json.dumps({"error": str(exc)})
                            if workflow.tools.on_error == "abort":
                                log.error("tool_error aborting name=%s error=%s", fc.name, exc)
                                raise

                    input_items.append(_tool_out(fc.call_id, out))

                continue

            # No tool calls -> final.
            if not no_tool_exit:
                log.warning("exit_condition no_tool_calls disabled; exiting anyway")
            if rr.output_text:
                print(rr.output_text)
            else:
                if workflow.output.print_raw_on_empty:
                    if workflow.output.pretty_print:
                        print(json.dumps(rr.raw, ensure_ascii=False, indent=2))
                    else:
                        print(json.dumps(rr.raw, ensure_ascii=False))
            return

    if not max_steps_exit:
        log.warning("exit_condition max_steps_reached disabled; loop ended at cap=%s", max_steps)
    raise SystemExit("max steps exceeded without final answer")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.getLogger("simple_rla.responses_runloop").warning("interrupted")
        raise SystemExit(130)
