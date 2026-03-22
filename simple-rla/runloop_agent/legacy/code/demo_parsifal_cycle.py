#!/usr/bin/env python3
"""Demo: run a tiny Parsifal cycle by calling MCP tools from a runloop.

Run from the `parsifal/` directory:

  python3 -m runloop_agent.demo_parsifal_cycle --config runloop_agent/example.mcp.toml --log /path/to/log

This assumes the MCP server defined in config exposes:

- parsifal_artifacts
- parsifal_render
- parsifal_validate

"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict

# Allow running as a script from inside the runloop_agent/ directory:
#   python3 demo_parsifal_cycle.py ...
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from runloop_agent.config import load_config
from runloop_agent.runloop import RunloopAgent, ToolCall


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Demo Parsifal cycle via MCP")
    p.add_argument("--config", required=True, help="Path to MCP config TOML")

    p.add_argument("--issue-id", default="KERNEL-0001")
    p.add_argument("--jira-key", default="KERNEL-0001")
    p.add_argument("--jira-url", default="")

    p.add_argument("--platform", default="raptorlake/rvp/default")
    p.add_argument("--device-id", default="device-01")

    p.add_argument("--kernel-repo", default="https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git")
    p.add_argument("--kernel-branch", default="v6.19")
    p.add_argument("--kernel-commit", default="TBD")
    p.add_argument("--kernel-localversion", default="TBD")
    p.add_argument("--kernel-dtb", default="(none/x86)")

    p.add_argument("--log", required=True, help="Path to a log file to ingest")
    p.add_argument("--out-dir", default="", help="Optional output dir for rendered markdown")

    return p.parse_args()


def _mk_debug_steps(args: argparse.Namespace, test_ref: str) -> Dict[str, Any]:
    return {
        "jira_key": args.jira_key,
        "round": 1,
        "bug": {
            "title": "[demo] parsifal runloop",
            "description_short": "Demo run: ingest a log, render templates, validate outputs.",
        },
        "target": {
            "platform": [args.platform],
            "device_id": args.device_id,
            "kernel": {
                "repo": args.kernel_repo,
                "branch": args.kernel_branch,
                "commit": args.kernel_commit,
                "localversion": args.kernel_localversion,
                "dtb": args.kernel_dtb,
            },
        },
        "inputs": {
            "jira_url": args.jira_url,
            "test_artifacts": [test_ref],
            "kb_hits": [],
        },
        "budget": {
            "max_device_commands": 20,
            "max_code_reads": 30,
        },
        "hypotheses": [
            {
                "id": "H1",
                "claim": "End-to-end toolchain wiring works.",
                "confidence": 0.5,
                "why": ["sig:demo"],
                "prove": ["parsifal tools run"],
                "disprove": ["any MCP/tool error"],
            }
        ],
        "code_check": [],
        "device_check": [],
        "stop_conditions": ["evidence_count>=1"],
        "notes": ["Demo only"],
    }


def _mk_key_evidence(args: argparse.Namespace, test_ref: str) -> Dict[str, Any]:
    return {
        "jira_key": args.jira_key,
        "bug": {
            "title": "[demo] parsifal runloop",
            "description_short": "Demo run: ingest a log, render templates, validate outputs.",
        },
        "target": {
            "platform": [args.platform],
            "device_id": args.device_id,
            "kernel": {
                "repo": args.kernel_repo,
                "branch": args.kernel_branch,
                "commit": args.kernel_commit,
                "localversion": args.kernel_localversion,
                "dtb": args.kernel_dtb,
            },
        },
        "rca": {
            "one_line": "Demo only (no RCA)",
            "scope": f"{args.platform} + {args.kernel_branch}",
        },
        "confidence": {
            "value": 0.1,
            "rationale": ["+0.1 demo ran"],
        },
        "claims": [
            {
                "id": "H1",
                "claim": "We captured at least one artifact ref.",
                "supports": [
                    {
                        "type": "log",
                        "ref": test_ref,
                        "excerpt": "demo log",
                        "collected_at": "2026-03-11T00:00:00Z",
                    }
                ],
            }
        ],
        "next_actions": ["Replace demo inputs with a real issue"],
    }


async def main() -> None:
    args = _parse_args()
    cfg = load_config(args.config)

    log_path = Path(args.log).resolve()
    if not log_path.exists():
        raise SystemExit(f"log not found: {log_path}")

    # Note: tool names are qualified as <server>.<tool>.
    # In example.mcp.toml the server name is "parsifal".
    t_artifacts = "parsifal.parsifal_artifacts"
    t_render = "parsifal.parsifal_render"
    t_validate = "parsifal.parsifal_validate"

    async with RunloopAgent(cfg) as agent:
        # 1) init run dir
        init_text = await agent.call_tool(t_artifacts, {
            "action": "init_run_dir",
            "issue_id": args.issue_id,
        })
        init_res = json.loads(init_text)
        run_dir = init_res.get("run_dir")
        if not run_dir:
            raise RuntimeError(f"init_run_dir returned no run_dir: {init_res}")

        # 2) ingest log
        ingest_text = await agent.call_tool(t_artifacts, {
            "action": "ingest_log",
            "issue_id": args.issue_id,
            "log_path": str(log_path),
            "log_name": log_path.name,
        })
        ingest_res = json.loads(ingest_text)
        refs = ingest_res.get("refs") or []
        if not refs:
            raise RuntimeError(f"ingest_log returned no refs: {ingest_res}")
        test_ref = refs[0].get("ref")
        if not test_ref:
            raise RuntimeError(f"ingest_log returned empty ref: {ingest_res}")

        # 3) render templates
        out_dir = args.out_dir or run_dir
        debug_steps = _mk_debug_steps(args, test_ref)
        key_evidence = _mk_key_evidence(args, test_ref)

        render_text = await agent.call_tool(t_render, {
            "debug_steps": debug_steps,
            "key_evidence": key_evidence,
            "out_dir": out_dir,
            "jira_key": args.jira_key,
            "round": 1,
            "evidence_index": 1,
        })
        render_res = json.loads(render_text)

        # 4) validate
        debug_steps_path = render_res.get("debug_steps_path")
        key_evidence_path = render_res.get("key_evidence_path")
        if not debug_steps_path or not key_evidence_path:
            raise RuntimeError(f"render returned missing paths: {render_res}")

        validate_text = await agent.call_tool(t_validate, {
            "paths": [debug_steps_path, key_evidence_path],
            "kind": "auto",
        })
        validate_res = json.loads(validate_text)

    print(json.dumps({
        "run_dir": run_dir,
        "render": render_res,
        "validate": validate_res,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
