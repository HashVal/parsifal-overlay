from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
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
from runloop_agent.workflow_config import load_workflow, format_message, exit_enabled
from runloop_agent.dump_utils import DumpManager, last_user_message


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


def _redact(text: str) -> str:
    # Basic redaction of obvious secrets
    patterns = [
        (r"(Bearer\s+)[A-Za-z0-9\-\._]+", r"\1<redacted>"),
        (r"(token\s*[:=]\s*)[^\s\"']+", r"\1<redacted>"),
        (r"(password\s*[:=]\s*)[^\s\"']+", r"\1<redacted>"),
        (r"(secret\s*[:=]\s*)[^\s\"']+", r"\1<redacted>"),
    ]
    out = text
    import re as _re
    for pat, repl in patterns:
        out = _re.sub(pat, repl, out, flags=_re.IGNORECASE)
    return out


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
    p.add_argument("--workflow", default="workflow.yaml", help="Path to workflow YAML")
    p.add_argument("--model", required=True, help="OpenAI model id")
    p.add_argument("--jira-key", default="", help="Optional Jira key to start from")
    p.add_argument("--max-steps", type=int, default=None, help="Override max steps from workflow")
    p.add_argument("--dump", action="store_true", help="Enable dump mode (save each round context)")
    p.add_argument("--log-level", default=os.environ.get("LOG_LEVEL", "INFO"), help="DEBUG|INFO|WARNING|ERROR")
    args = p.parse_args()

    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    log = logging.getLogger("simple_rla.fc_runloop")

    # Load workflow configuration
    workflow = load_workflow(args.workflow)
    max_steps = args.max_steps if args.max_steps is not None else workflow.execution.max_steps

    # Apply exit condition flags
    no_tool_exit = exit_enabled(workflow, "no_tool_calls", default=True)
    max_steps_exit = exit_enabled(workflow, "max_steps_reached", default=True)
    if not max_steps_exit and args.max_steps is None:
        # effectively unlimited, but keep a very large safety cap
        max_steps = 100000

    log.info("start model=%s jira_key=%s max_steps=%s workflow=%s", args.model, args.jira_key, max_steps, workflow.name)

    cfg = load_config(args.config)

    # Build messages from workflow config
    system_prompt = workflow.llm.system_prompt
    if args.jira_key:
        initial_message = format_message(workflow.llm.initial_message_template, {"jira_key": args.jira_key})
    else:
        initial_message = workflow.llm.default_message

    dumper = DumpManager.create() if args.dump else None
    if dumper:
        log.info("dump.mode enabled dir=%s", dumper.root)
        dumper.write_meta({
            "model": args.model,
            "workflow": workflow.name,
            "workflow_path": args.workflow,
            "config_path": args.config,
            "system": system_prompt,
            "initial_message": initial_message,
        })

    async with RunloopAgent(cfg) as agent:
        tools = agent.list_tools()
        log.info("mcp.tools count=%d", len(tools))
        tool_map = _build_tool_map(tools)
        openai_tools = [_mcp_to_openai_tool_schema(fc, tools[fq]) for fc, fq in tool_map.fc_to_fq.items()]

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": initial_message},
        ]

        for step in range(1, max_steps + 1):
            log.info("step=%d/%d chat_completions", step, max_steps)
            mm = chat_completions(
                model=args.model,
                messages=messages,
                tools=openai_tools,
                tool_choice=workflow.llm.tool_choice,
                temperature=workflow.llm.temperature,
                timeout_s=workflow.execution.request_timeout_s,
            )

            tool_calls_dump = []
            tool_results_dump = []

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
                    log.info("tool_call name=%s fq=%s call_id=%s", tc.name, fq, tc.id)
                    tool_calls_dump.append({"name": tc.name, "fq": fq, "id": tc.id, "arguments": tc.arguments_json})
                    if not fq:
                        error_msg = {"error": f"unknown tool: {tc.name}"}
                        log.error("tool_error unknown_tool name=%s", tc.name)
                        tool_out = json.dumps(error_msg)
                    else:
                        try:
                            tool_args = json.loads(tc.arguments_json) if tc.arguments_json.strip() else {}
                            if not isinstance(tool_args, dict):
                                raise ValueError("tool arguments must be an object")
                            log.info("tool_exec name=%s fq=%s args=%s", tc.name, fq, tool_args)
                            tool_out = await agent.call_tool(fq, tool_args)
                            # Log truncated result for debugging (redacted, DEBUG only)
                            log.info("tool_result name=%s fq=%s len=%d", tc.name, fq, len(tool_out))
                            log.debug("tool_result_content name=%s fq=%s content=%s", tc.name, fq, _redact(tool_out[:1000]))
                        except Exception as exc:
                            log.error("tool_error name=%s fq=%s error=%s", tc.name, fq, exc)
                            if workflow.tools.include_traceback:
                                import traceback
                                tool_out = json.dumps({"error": str(exc), "traceback": traceback.format_exc()})
                            else:
                                tool_out = json.dumps({"error": str(exc)})
                            
                            if workflow.tools.on_error == "abort":
                                log.error("tool_error aborting name=%s error=%s", tc.name, exc)
                                raise

                    tool_results_dump.append({"name": tc.name, "fq": fq, "id": tc.id, "output": tool_out})

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": tc.name,
                        "content": tool_out,
                    })

                if dumper:
                    dumper.write_round(step, {
                        "round": step,
                        "model": args.model,
                        "system": system_prompt,
                        "qprompt": last_user_message(messages),
                        "messages": messages,
                        "tools": [t.get("function", {}).get("name") for t in openai_tools],
                        "tool_calls": tool_calls_dump,
                        "tool_results": tool_results_dump,
                        "response": {"content": mm.content, "tool_calls": [tc.__dict__ for tc in mm.tool_calls]},
                    })

                continue

            # Final
            if not no_tool_exit:
                log.warning("exit_condition no_tool_calls disabled; exiting anyway")
            log.info("step=%d final_response content_len=%d", step, len(mm.content or ""))
            if dumper:
                dumper.write_round(step, {
                    "round": step,
                    "model": args.model,
                    "system": system_prompt,
                    "qprompt": last_user_message(messages),
                    "messages": messages,
                    "tools": [t.get("function", {}).get("name") for t in openai_tools],
                    "tool_calls": [],
                    "tool_results": [],
                    "response": {"content": mm.content, "tool_calls": []},
                })
            if mm.content:
                print(mm.content)
            else:
                if workflow.output.print_raw_on_empty:
                    raw = {"role": mm.role, "content": mm.content, "tool_calls": []}
                    if workflow.output.pretty_print:
                        print(json.dumps(raw, ensure_ascii=False, indent=2))
                    else:
                        print(json.dumps(raw, ensure_ascii=False))
            return

    if not max_steps_exit:
        log.warning("exit_condition max_steps_reached disabled; loop ended at cap=%s", max_steps)
    raise SystemExit("max steps exceeded without final answer")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.getLogger("simple_rla.fc_runloop").warning("interrupted")
        raise SystemExit(130)
