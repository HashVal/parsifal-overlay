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
from runloop_agent.runloop_control import (
    FORCED_DRAFT_NUDGE,
    KB_GROUNDING_NUDGE,
    PhaseState,
    advance_phase,
    check_budget,
    check_repeat_guard,
    record_call,
    record_tool_use,
    should_force_draft,
    tool_family,
)
from runloop_agent.workspace import create_run_workspace, write_workspace_meta, workspace_env, utc_now_iso
from runloop_agent.possible_failure_reason import (
    PossibleFailureReasonValidationError,
    build_step5_input,
    compact_possible_failure_reason,
    extract_possible_failure_reason_json_text,
    validate_possible_failure_reason,
    write_possible_failure_reason_artifacts,
)


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


def _extract_signal_text(signal: dict[str, Any] | None) -> str | None:
    if not isinstance(signal, dict):
        return None
    text = signal.get("text")
    if isinstance(text, str) and text.strip():
        return text.strip()
    return None


def _guess_platforms_from_text(texts: list[str]) -> list[str]:
    joined = "\n".join(texts).upper()
    platform_markers = ["BMG", "RPL", "MTL", "ARL", "LNL", "PTL", "ADL", "TGL", "ARC"]
    out: list[str] = []
    for marker in platform_markers:
        if marker in joined:
            out.append(marker)
    return out


def _strip_log_prefix(text: str) -> str:
    text = (text or "").strip()
    return re.sub(r"^\[[^\]]+\]\s*", "", text)


def _extract_function_name(text: str) -> str:
    text = _strip_log_prefix(text)
    m = re.search(r"([A-Za-z_][A-Za-z0-9_]*)\+[0-9A-Fa-fx]+/[0-9A-Fa-fx]+", text)
    if m:
        return m.group(1)
    return text


def _clip_json_chars(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"... [truncated {len(text) - limit} chars]"


def _compact_log_extract_for_llm(data: dict[str, Any]) -> dict[str, Any]:
    essential = data.get("essential") if isinstance(data.get("essential"), dict) else {}
    fatal = data.get("fatal") if isinstance(data.get("fatal"), dict) else {}
    errors = data.get("errors") if isinstance(data.get("errors"), dict) else {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    fatal_items = fatal.get("items") if isinstance(fatal.get("items"), list) else []
    error_items = errors.get("items") if isinstance(errors.get("items"), list) else []

    primary_headline = None
    primary_trace_anchor = None
    if fatal_items and isinstance(fatal_items[0], dict):
        item0 = fatal_items[0]
        if isinstance(item0.get("headline"), dict):
            primary_headline = _strip_log_prefix(str(item0["headline"].get("text") or ""))
        if isinstance(item0.get("trace_anchor"), dict):
            primary_trace_anchor = _extract_function_name(str(item0["trace_anchor"].get("text") or ""))

    top_errors: list[str] = []
    for item in error_items[:2]:
        if isinstance(item, dict):
            text = _strip_log_prefix(str(item.get("text") or "")).strip()
            if text:
                top_errors.append(text)

    return {
        "path": data.get("path"),
        "profile": data.get("profile"),
        "essential": {
            "kernel_version": _strip_log_prefix(str(essential.get("kernel_version") or "")),
            "driver_hints": essential.get("driver_hints") if isinstance(essential.get("driver_hints"), list) else [],
        },
        "fatal": {
            "count": fatal.get("count"),
            "primary": {
                "headline": primary_headline,
                "trace_anchor": primary_trace_anchor,
            },
        },
        "errors": {
            "count": errors.get("count"),
            "top": top_errors,
        },
        "summary": {
            "dominant_failure_mode": summary.get("dominant_failure_mode"),
            "primary_subsystems": summary.get("primary_subsystems") if isinstance(summary.get("primary_subsystems"), list) else [],
        },
    }


def _compact_kb_ground_for_llm(data: dict[str, Any]) -> dict[str, Any]:
    query_context = data.get("query_context") if isinstance(data.get("query_context"), dict) else {}
    matched = data.get("matched_objects") if isinstance(data.get("matched_objects"), dict) else {}

    compact_matches: list[dict[str, Any]] = []
    for bucket_name, objects in matched.items():
        if not isinstance(objects, list) or not objects:
            continue
        item = objects[0]
        if not isinstance(item, dict):
            continue
        compact_matches.append({
            "id": item.get("id"),
            "kind": item.get("kind"),
            "title": item.get("title"),
            "summary": str(item.get("summary") or "").strip(),
        })

    return {
        "query_context": {
            "case_id": query_context.get("case_id"),
            "platforms": query_context.get("platforms") if isinstance(query_context.get("platforms"), list) else [],
            "subsystems": query_context.get("subsystems") if isinstance(query_context.get("subsystems"), list) else [],
            "modes": query_context.get("modes") if isinstance(query_context.get("modes"), list) else [],
        },
        "matched_objects": compact_matches,
        "focus_areas": data.get("focus_areas") if isinstance(data.get("focus_areas"), list) else [],
        "open_questions": data.get("open_questions") if isinstance(data.get("open_questions"), list) else [],
        "recommended_next_reads": data.get("recommended_next_reads") if isinstance(data.get("recommended_next_reads"), list) else [],
    }


def _compact_tool_output_for_llm(tool_name: str, tool_out: str) -> str:
    try:
        data = json.loads(tool_out)
    except Exception:
        return _clip_json_chars(tool_out, 1200)

    if not isinstance(data, dict):
        return _clip_json_chars(tool_out, 1200)

    if tool_name == "files__log_extract_signatures":
        compact = _compact_log_extract_for_llm(data)
        return _clip_json_chars(json.dumps(compact, ensure_ascii=False), 1800)
    if tool_name == "kb__kb_ground":
        compact = _compact_kb_ground_for_llm(data)
        return _clip_json_chars(json.dumps(compact, ensure_ascii=False), 1600)
    return _clip_json_chars(tool_out, 2000)


def _latest_compacted_signature_pack(recent_tool_results: list[dict[str, Any]]) -> dict[str, Any]:
    for item in reversed(recent_tool_results):
        if item.get("name") != "files__log_extract_signatures":
            continue
        output = item.get("output")
        if not isinstance(output, str):
            continue
        try:
            parsed = json.loads(output)
        except Exception:
            continue
        if isinstance(parsed, dict):
            return _compact_log_extract_for_llm(parsed)
    return {}


def _latest_compacted_kb_pack(recent_tool_results: list[dict[str, Any]]) -> dict[str, Any]:
    for item in reversed(recent_tool_results):
        if item.get("name") != "kb__kb_ground":
            continue
        output = item.get("output")
        if not isinstance(output, str):
            continue
        try:
            parsed = json.loads(output)
        except Exception:
            continue
        if isinstance(parsed, dict):
            return _compact_kb_ground_for_llm(parsed)
    return {}


def _infer_jira_context(jira_key: str, recent_tool_results: list[dict[str, Any]]) -> dict[str, Any]:
    for item in reversed(recent_tool_results):
        if item.get("name") != "jira__jira_get":
            continue
        output = item.get("output")
        if not isinstance(output, str):
            continue
        try:
            parsed = json.loads(output)
        except Exception:
            continue
        if not isinstance(parsed, dict):
            continue
        return {
            "case_id": jira_key,
            "title": parsed.get("summary") or jira_key,
            "platforms": parsed.get("labels") if isinstance(parsed.get("labels"), list) else [],
            "components": parsed.get("components") if isinstance(parsed.get("components"), list) else [],
            "status": parsed.get("status"),
        }
    return {"case_id": jira_key, "title": jira_key}


def _step5_prompt(input_pack: dict[str, Any]) -> str:
    skeleton = {
        "case_context": {
            "case_id": input_pack.get("case_context", {}).get("case_id", ""),
            "platforms": [],
            "modes": [],
            "drivers_involved": [],
        },
        "possible_failure_reasons": [
            {
                "rank": 1,
                "confidence": "high",
                "possible_rate": 0.75,
                "title": "...",
                "reason_chain": "...",
                "factors": ["..."],
                "supporting_evidence": {
                    "jira": ["..."],
                    "signature": ["..."],
                    "kb": ["..."],
                },
                "unknowns": ["..."],
            }
        ],
        "selection_hint": {
            "primary_rank": 1,
            "debug_steps_should_focus_on": 1,
            "include_alternatives_if_primary_is_weak": False,
        },
    }
    return (
        "Generate possible failure reasons from the provided structured inputs.\n"
        "Return the final structured result as a JSON object wrapped inside <POSSIBLE_FAILURE_REASON_JSON> ... </POSSIBLE_FAILURE_REASON_JSON>.\n"
        "Anything outside that wrapper will be ignored, so ensure the wrapped JSON is complete and valid.\n"
        "Use the following JSON skeleton exactly: keep all keys, only replace the values, and optionally add rank 2 or rank 3 items inside possible_failure_reasons.\n"
        "Do not rename keys. Do not omit required keys. Do not invent alternative field names.\n"
        "Rules:\n"
        "- no more than 3 possible_failure_reasons\n"
        "- rank must start at 1 and be contiguous\n"
        "- confidence must be high, medium, or low\n"
        "- possible_rate must be within [0.0, 1.0]\n"
        "- each reason must be a complete mechanism candidate, not a fragment\n"
        "- use only the provided Jira context, signature pack, and KB pack\n"
        "- selection_hint.primary_rank must be 1\n"
        "- selection_hint.debug_steps_should_focus_on must be 1\n"
        "- keep supporting_evidence concise\n\n"
        f"Skeleton:\n{json.dumps(skeleton, ensure_ascii=False, indent=2)}\n\n"
        f"Input:\n{json.dumps(input_pack, ensure_ascii=False)}"
    )


def _step5_repair_prompt(input_pack: dict[str, Any], invalid_output: str, error_text: str) -> str:
    skeleton = {
        "case_context": {
            "case_id": input_pack.get("case_context", {}).get("case_id", ""),
            "platforms": [],
            "modes": [],
            "drivers_involved": [],
        },
        "possible_failure_reasons": [
            {
                "rank": 1,
                "confidence": "high",
                "possible_rate": 0.75,
                "title": "...",
                "reason_chain": "...",
                "factors": ["..."],
                "supporting_evidence": {
                    "jira": ["..."],
                    "signature": ["..."],
                    "kb": ["..."],
                },
                "unknowns": ["..."],
            }
        ],
        "selection_hint": {
            "primary_rank": 1,
            "debug_steps_should_focus_on": 1,
            "include_alternatives_if_primary_is_weak": False,
        },
    }
    return (
        "Repair the previous Step 5 output.\n"
        "Return the final structured result as a JSON object wrapped inside <POSSIBLE_FAILURE_REASON_JSON> ... </POSSIBLE_FAILURE_REASON_JSON>.\n"
        "Keep the same intended meaning if possible, but fix the structure.\n"
        "Use the following JSON skeleton exactly: keep all keys, only replace the values, and optionally add rank 2 or rank 3 items inside possible_failure_reasons.\n"
        "Do not rename keys. Do not omit required keys. Do not invent alternative field names.\n"
        "Requirements:\n"
        "- top-level keys: case_context, possible_failure_reasons, selection_hint\n"
        "- 1 to 3 possible_failure_reasons\n"
        "- confidence in {high, medium, low}\n"
        "- possible_rate in [0.0, 1.0]\n"
        "- complete mechanism candidates only\n"
        "- no markdown code fences around the final wrapped JSON\n\n"
        f"Validation error: {error_text}\n\n"
        f"Skeleton:\n{json.dumps(skeleton, ensure_ascii=False, indent=2)}\n\n"
        f"Input:\n{json.dumps(input_pack, ensure_ascii=False)}\n\n"
        f"Invalid output:\n{invalid_output}"
    )


def _build_auto_kb_ground_args(jira_key: str, recent_tool_results: list[dict[str, Any]]) -> dict[str, Any]:
    log_extract = None
    for item in reversed(recent_tool_results):
        if item.get("name") == "files__log_extract_signatures":
            output = item.get("output")
            if isinstance(output, str):
                try:
                    parsed = json.loads(output)
                except Exception:
                    parsed = None
                if isinstance(parsed, dict):
                    log_extract = parsed
                    break

    signals: list[dict[str, str]] = []
    platforms: list[str] = []
    subsystems: list[str] = []
    modes: list[str] = []
    keywords: list[str] = []
    summary = ""
    title = jira_key
    kernel_version = ""
    cmdline_flags: list[str] = []

    if isinstance(log_extract, dict):
        essential = log_extract.get("essential") if isinstance(log_extract.get("essential"), dict) else {}
        fatal = log_extract.get("fatal") if isinstance(log_extract.get("fatal"), dict) else {}
        summary_info = log_extract.get("summary") if isinstance(log_extract.get("summary"), dict) else {}

        kernel_version = str(essential.get("kernel_version") or "").strip()
        cmdline = str(essential.get("cmdline") or "").strip()
        dmi = str(essential.get("dmi") or "").strip()
        driver_hints = essential.get("driver_hints") if isinstance(essential.get("driver_hints"), list) else []
        fatal_items = fatal.get("items") if isinstance(fatal.get("items"), list) else []
        dominant_failure_mode = str(summary_info.get("dominant_failure_mode") or "").strip()
        primary_subsystems = summary_info.get("primary_subsystems") if isinstance(summary_info.get("primary_subsystems"), list) else []

        texts_for_platforms = [dmi, kernel_version, cmdline]
        platforms = _guess_platforms_from_text([t for t in texts_for_platforms if t])
        subsystems = [str(x) for x in primary_subsystems if isinstance(x, str) and x.strip()]

        if any("integrated" in path.lower() for path in [str(log_extract.get("path") or "")]):
            modes.append("integrated")
        if any("hybrid" in path.lower() for path in [str(log_extract.get("path") or "")]):
            modes.append("hybrid")

        if dominant_failure_mode:
            signals.append({"type": "symptom", "value": dominant_failure_mode})

        if fatal_items:
            first_fatal = fatal_items[0] if isinstance(fatal_items[0], dict) else {}
            headline = _extract_signal_text(first_fatal.get("headline") if isinstance(first_fatal.get("headline"), dict) else None)
            trace_anchor = _extract_signal_text(first_fatal.get("trace_anchor") if isinstance(first_fatal.get("trace_anchor"), dict) else None)
            if headline:
                signals.append({"type": "log_pattern", "value": headline})
                keywords.append(headline)
            if trace_anchor:
                signals.append({"type": "function", "value": trace_anchor})
                keywords.append(trace_anchor)
            if headline or trace_anchor:
                summary = " ; ".join([x for x in [headline, trace_anchor] if x])
                title = headline or title

        for hint in driver_hints[:4]:
            if isinstance(hint, str) and hint.strip():
                cmdline_flags.append(hint.strip())
                signals.append({"type": "config", "value": hint.strip()})
                if hint.strip().startswith("xe"):
                    signals.append({"type": "module", "value": "xe"})
                elif hint.strip().startswith("i915"):
                    signals.append({"type": "module", "value": "i915"})

        if dmi:
            platforms = platforms or _guess_platforms_from_text([dmi])
            keywords.append(dmi)

    dedup_signals: list[dict[str, str]] = []
    seen_signal_pairs: set[tuple[str, str]] = set()
    for sig in signals:
        key = (sig.get("type", ""), sig.get("value", ""))
        if not key[0] or not key[1] or key in seen_signal_pairs:
            continue
        seen_signal_pairs.add(key)
        dedup_signals.append(sig)

    return {
        "context": {
            "case_id": jira_key,
            "title": title,
            "summary": summary or f"Lightweight KB grounding for {jira_key}",
            "platforms": platforms,
            "subsystems": subsystems,
            "modes": modes,
            "environment": {
                "kernel_version": kernel_version,
                "cmdline": cmdline_flags,
            },
        },
        "signals": dedup_signals[:8],
        "hints": {
            "preferred_kinds": ["platform_note", "issue_pattern", "code_note"],
            "focus": [
                "shared failure path after artifact inspection",
                "driver and code-path grounding for provisional DEBUG_STEPS",
            ],
        },
        "limits": {
            "max_total_hits": 5,
            "max_hits_per_kind": 2,
            "include_kinds": ["platform_note", "issue_pattern", "code_note"],
            "include_snippets": True,
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
    ws = create_run_workspace(artifacts_root=cfg.artifacts_root, jira_key=args.jira_key)
    os.environ.update(workspace_env(ws))
    file_handler = logging.FileHandler(ws.log_path, encoding="utf-8")
    file_handler.setLevel(getattr(logging, str(args.log_level).upper(), logging.INFO))
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logging.getLogger().addHandler(file_handler)
    write_workspace_meta(ws, {
        "run_id": ws.run_id,
        "created_at": utc_now_iso(),
        "jira_key": args.jira_key,
        "model": args.model,
        "mode": "fc",
        "workflow": workflow.name,
        "workflow_path": args.workflow,
        "config_path": args.config,
        "workspace_dir": str(ws.root),
        "dump_enabled": bool(args.dump),
    })
    log.info("workspace.created dir=%s", ws.root)

    # Build messages from workflow config
    system_prompt = workflow.llm.system_prompt
    if args.jira_key:
        initial_message = format_message(workflow.llm.initial_message_template, {"jira_key": args.jira_key})
    else:
        initial_message = workflow.llm.default_message

    dumper = DumpManager.create(ws.dumps_dir) if args.dump else None
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
        phase_state = PhaseState(entered_step=1)
        phase_usage: dict[str, int] = {"jira": 0, "files": 0, "kb": 0}
        tool_history = []
        forced_draft_mode = False
        seen_files = False
        seen_kb = False
        seen_failure_signal = False
        recent_tool_results: list[dict[str, Any]] = []
        step5_full_artifact: dict[str, Any] | None = None
        step5_compact_artifact: dict[str, Any] | None = None

        for step in range(1, max_steps + 1):
            if phase_state.phase == "possible_failure_reason" and not phase_state.possible_failure_reason_ready:
                jira_context = _infer_jira_context(args.jira_key, recent_tool_results)
                signature_pack = _latest_compacted_signature_pack(recent_tool_results)
                kb_pack = _latest_compacted_kb_pack(recent_tool_results)
                step5_input = build_step5_input(
                    jira_key=args.jira_key,
                    jira_context=jira_context,
                    signature_pack=signature_pack,
                    kb_pack=kb_pack,
                )
                raw_outputs: list[str] = []
                extracted_outputs: list[str] = []
                validation_error = ""
                validated: dict[str, Any] | None = None
                for attempt in range(1, 3):
                    step5_messages = [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": _step5_prompt(step5_input) if attempt == 1 else _step5_repair_prompt(step5_input, raw_outputs[-1], validation_error)},
                    ]
                    try:
                        mm_step5 = chat_completions(
                            model=args.model,
                            messages=step5_messages,
                            tools=[],
                            tool_choice="none",
                            temperature=workflow.llm.temperature,
                            timeout_s=workflow.execution.request_timeout_s,
                        )
                    except Exception as exc:
                        log.error("step5_generation_failed step=%d attempt=%d error=%s", step, attempt, exc)
                        if dumper:
                            dumper.write_round(step, {
                                "iteration": step,
                                "timestamp": utc_now_iso(),
                                "model": args.model,
                                "status": "incomplete",
                                "failure_stage": "possible_failure_reason_request",
                                "error_type": type(exc).__name__,
                                "error_message": str(exc),
                                "phase": phase_state.phase,
                                "phase_usage": phase_usage,
                                "forced_draft_mode": forced_draft_mode,
                                "system_prompt": system_prompt,
                                "user_prompt": step5_messages[-1]["content"],
                                "messages": step5_messages,
                                "tools": [],
                                "tool_calls": [],
                                "tool_results": [],
                                "response": None,
                            })
                        raise
                    raw_text = mm_step5.content or ""
                    raw_outputs.append(raw_text)
                    try:
                        extracted_text = extract_possible_failure_reason_json_text(raw_text)
                    except PossibleFailureReasonValidationError as exc:
                        extracted_text = ""
                        extracted_outputs.append(extracted_text)
                        validation_error = str(exc)
                        log.warning(
                            "step5_extraction_failed step=%d attempt=%d error=%s raw_preview=%s",
                            step,
                            attempt,
                            validation_error,
                            _redact(raw_text[:400]),
                        )
                        validated = None
                        continue
                    extracted_outputs.append(extracted_text)
                    try:
                        validated = validate_possible_failure_reason(extracted_text)
                        break
                    except PossibleFailureReasonValidationError as exc:
                        validation_error = str(exc)
                        log.warning(
                            "step5_validation_failed step=%d attempt=%d error=%s raw_preview=%s extracted_preview=%s",
                            step,
                            attempt,
                            validation_error,
                            _redact(raw_text[:400]),
                            _redact(extracted_text[:400]),
                        )
                        validated = None
                if validated is None:
                    log.error("step5_failed step=%d error=%s", step, validation_error)
                    if dumper:
                        dumper.write_round(step, {
                            "iteration": step,
                            "timestamp": utc_now_iso(),
                            "model": args.model,
                            "status": "incomplete",
                            "failure_stage": "possible_failure_reason_validation",
                            "error_type": "PossibleFailureReasonValidationError",
                            "error_message": validation_error,
                            "phase": phase_state.phase,
                            "phase_usage": phase_usage,
                            "forced_draft_mode": forced_draft_mode,
                            "system_prompt": system_prompt,
                            "user_prompt": _step5_prompt(step5_input),
                            "messages": [],
                            "tools": [],
                            "tool_calls": [],
                            "tool_results": [],
                            "response": {"raw_outputs": raw_outputs, "extracted_outputs": extracted_outputs},
                        })
                    raise SystemExit(f"step5 possible failure reason failed: {validation_error}")

                compact = compact_possible_failure_reason(validated)
                artifact_paths = write_possible_failure_reason_artifacts(ws, validated, compact)
                step5_full_artifact = validated
                step5_compact_artifact = compact
                phase_state = PhaseState(
                    phase=phase_state.phase,
                    phase_index=phase_state.phase_index,
                    entered_step=phase_state.entered_step,
                    notes=list(phase_state.notes),
                    kb_grounding_attempted=phase_state.kb_grounding_attempted,
                    possible_failure_reason_ready=True,
                )
                messages.append({
                    "role": "assistant",
                    "content": "Generated ranked possible failure reasons and stored full/compact Step 5 artifacts.",
                })
                messages.append({
                    "role": "user",
                    "content": (
                        "Use this compact possible-failure-reason artifact as the primary input for subsequent DEBUG_STEPS drafting.\n"
                        "Do not re-expand broad Jira/signature/KB context unless a specific gap requires it.\n\n"
                        f"{json.dumps(step5_compact_artifact, ensure_ascii=False)}"
                    ),
                })
                log.info("step5_ready step=%d json=%s compact=%s markdown=%s", step, artifact_paths["json"], artifact_paths["compact_json"], artifact_paths["markdown"])
                new_phase_state, advanced = advance_phase(
                    phase_state,
                    used_jira=False,
                    used_files=False,
                    used_kb=False,
                    downloaded_text_attachment=False,
                    seen_failure_signal=seen_failure_signal,
                    seen_kb=seen_kb,
                    step=step,
                )
                if advanced:
                    log.info("phase_advance from=%s to=%s step=%d", phase_state.phase, new_phase_state.phase, step)
                    phase_state = new_phase_state
                    phase_usage = {"jira": 0, "files": 0, "kb": 0}
                if dumper:
                    dumper.write_round(step, {
                        "iteration": step,
                        "timestamp": utc_now_iso(),
                        "model": args.model,
                        "system_prompt": system_prompt,
                        "user_prompt": _step5_prompt(step5_input),
                        "llm_response": raw_outputs[-1] if raw_outputs else None,
                        "messages": messages,
                        "tools": [],
                        "tool_calls": [],
                        "tool_results": [],
                        "response": {
                            "step5_input": step5_input,
                            "raw_outputs": raw_outputs,
                            "extracted_outputs": extracted_outputs,
                            "validated": validated,
                            "compact": compact,
                            "artifact_paths": artifact_paths,
                        },
                    })
                continue

            if forced_draft_mode:
                if not messages or messages[-1].get("content") != FORCED_DRAFT_NUDGE:
                    messages.append({"role": "user", "content": FORCED_DRAFT_NUDGE})
            payload_chars = sum(len(json.dumps(m, ensure_ascii=False)) for m in messages)
            log.info("step=%d/%d chat_completions phase=%s usage=%s forced_draft=%s messages=%d payload_chars=%d", step, max_steps, phase_state.phase, phase_usage, forced_draft_mode, len(messages), payload_chars)
            try:
                mm = chat_completions(
                    model=args.model,
                    messages=messages,
                    tools=openai_tools,
                    tool_choice=workflow.llm.tool_choice,
                    temperature=workflow.llm.temperature,
                    timeout_s=workflow.execution.request_timeout_s,
                )
            except Exception as exc:
                log.error("chat_completions_failed step=%d phase=%s error=%s", step, phase_state.phase, exc)
                if dumper:
                    dumper.write_round(step, {
                        "iteration": step,
                        "timestamp": utc_now_iso(),
                        "model": args.model,
                        "status": "incomplete",
                        "failure_stage": "chat_completions_request",
                        "error_type": type(exc).__name__,
                        "error_message": str(exc),
                        "phase": phase_state.phase,
                        "phase_usage": phase_usage,
                        "forced_draft_mode": forced_draft_mode,
                        "system_prompt": system_prompt,
                        "user_prompt": last_user_message(messages),
                        "llm_response": None,
                        "messages": messages,
                        "tools": [t.get("function", {}).get("name") for t in openai_tools],
                        "tool_calls": [],
                        "tool_results": [],
                        "response": None,
                    })
                raise

            tool_calls_dump = []
            tool_results_dump = []

            # Tool calls
            if mm.tool_calls:
                used_jira = False
                used_files = False
                used_kb = False
                downloaded_text_attachment = False
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
                    log.info("tool_call name=%s fq=%s call_id=%s phase=%s", tc.name, fq, tc.id, phase_state.phase)
                    tool_calls_dump.append({"name": tc.name, "fq": fq, "id": tc.id, "arguments": tc.arguments_json, "phase": phase_state.phase})
                    if not fq:
                        error_msg = {"error": f"unknown tool: {tc.name}"}
                        log.error("tool_error unknown_tool name=%s", tc.name)
                        tool_out = json.dumps(error_msg)
                    else:
                        try:
                            tool_args = json.loads(tc.arguments_json) if tc.arguments_json.strip() else {}
                            if not isinstance(tool_args, dict):
                                raise ValueError("tool arguments must be an object")
                            family = tool_family(tc.name)
                            budget_guard = check_budget(phase_state.phase, phase_usage, family)
                            if not budget_guard.allowed:
                                log.warning("tool_blocked budget name=%s fq=%s family=%s phase=%s", tc.name, fq, family, phase_state.phase)
                                tool_out = json.dumps({"error": budget_guard.message, "guard": budget_guard.reason})
                            else:
                                repeat_guard = check_repeat_guard(phase_state.phase, step, family, tc.name, tool_args, tool_history)
                                if not repeat_guard.allowed:
                                    log.warning("tool_blocked repeat name=%s fq=%s family=%s phase=%s", tc.name, fq, family, phase_state.phase)
                                    tool_out = json.dumps({"error": repeat_guard.message, "guard": repeat_guard.reason})
                                else:
                                    log.info("tool_exec name=%s fq=%s family=%s phase=%s args=%s", tc.name, fq, family, phase_state.phase, tool_args)
                                    tool_out = await agent.call_tool(fq, tool_args)
                                    record_tool_use(phase_usage, family)
                                    record_call(tool_history, phase_state.phase, step, family, tc.name, tool_args)
                                    if family == "jira":
                                        used_jira = True
                                        if tc.name == "jira__jira_fetch_attachment":
                                            try:
                                                parsed_tool_out = json.loads(tool_out)
                                            except Exception:
                                                parsed_tool_out = None
                                            if isinstance(parsed_tool_out, dict) and not parsed_tool_out.get("binary", True):
                                                downloaded_text_attachment = True
                                    elif family == "files":
                                        used_files = True
                                        seen_files = True
                                    elif family == "kb":
                                        used_kb = True
                                        seen_kb = True
                                    # Log truncated result for debugging (redacted, DEBUG only)
                                    log.info("tool_result name=%s fq=%s len=%d", tc.name, fq, len(tool_out))
                                    log.debug("tool_result_content name=%s fq=%s content=%s", tc.name, fq, _redact(tool_out[:1000]))
                                    lowered = tool_out.lower()
                                    if any(tok in lowered for tok in ["kernel bug", "call trace", "bug at", "oops", "panic", "fatal"]):
                                        seen_failure_signal = True
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

                    tool_results_dump.append({"name": tc.name, "fq": fq, "id": tc.id, "output": tool_out, "phase": phase_state.phase})
                    recent_tool_results.append({"name": tc.name, "fq": fq, "id": tc.id, "output": tool_out, "phase": phase_state.phase})

                    llm_tool_out = _compact_tool_output_for_llm(tc.name, tool_out)
                    log.info("tool_result_compacted name=%s fq=%s raw_len=%d compact_len=%d", tc.name, fq, len(tool_out), len(llm_tool_out))
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": tc.name,
                        "content": llm_tool_out,
                    })

                new_phase_state, advanced = advance_phase(
                    phase_state,
                    used_jira=used_jira,
                    used_files=used_files,
                    used_kb=used_kb,
                    downloaded_text_attachment=downloaded_text_attachment,
                    seen_failure_signal=seen_failure_signal,
                    seen_kb=seen_kb,
                    step=step,
                )
                if advanced:
                    log.info("phase_advance from=%s to=%s step=%d", phase_state.phase, new_phase_state.phase, step)
                    phase_state = new_phase_state
                    phase_usage = {"jira": 0, "files": 0, "kb": 0}
                    if phase_state.phase == "kb_grounding" and not seen_kb and not phase_state.kb_grounding_attempted:
                        kb_args = _build_auto_kb_ground_args(args.jira_key, recent_tool_results)
                        synthetic_id = f"auto-kb-ground-{step}"
                        log.info(
                            "auto_kb_ground triggered step=%d jira_key=%s platforms=%s subsystems=%s signals=%d",
                            step,
                            args.jira_key,
                            ((kb_args.get("context") or {}).get("platforms") or []),
                            ((kb_args.get("context") or {}).get("subsystems") or []),
                            len(kb_args.get("signals") or []),
                        )
                        messages.append({
                            "role": "assistant",
                            "content": "Proceeding with one lightweight KB grounding pass based on the extracted failure signals.",
                            "tool_calls": [{
                                "id": synthetic_id,
                                "type": "function",
                                "function": {"name": "kb__kb_ground", "arguments": json.dumps(kb_args, ensure_ascii=False)},
                            }],
                        })
                        try:
                            tool_out = await agent.call_tool("kb.kb_ground", kb_args)
                            seen_kb = True
                            phase_state = PhaseState(
                                phase=phase_state.phase,
                                phase_index=phase_state.phase_index,
                                entered_step=phase_state.entered_step,
                                notes=list(phase_state.notes),
                                kb_grounding_attempted=True,
                                possible_failure_reason_ready=phase_state.possible_failure_reason_ready,
                            )
                            log.info("auto_kb_ground result len=%d", len(tool_out))
                        except Exception as exc:
                            tool_out = json.dumps({"error": str(exc)})
                            phase_state = PhaseState(
                                phase=phase_state.phase,
                                phase_index=phase_state.phase_index,
                                entered_step=phase_state.entered_step,
                                notes=list(phase_state.notes),
                                kb_grounding_attempted=True,
                                possible_failure_reason_ready=phase_state.possible_failure_reason_ready,
                            )
                            log.error("auto_kb_ground failed error=%s", exc)
                        tool_results_dump.append({"name": "kb__kb_ground", "fq": "kb.kb_ground", "id": synthetic_id, "output": tool_out, "phase": phase_state.phase, "auto": True})
                        recent_tool_results.append({"name": "kb__kb_ground", "fq": "kb.kb_ground", "id": synthetic_id, "output": tool_out, "phase": phase_state.phase, "auto": True})
                        llm_tool_out = _compact_tool_output_for_llm("kb__kb_ground", tool_out)
                        log.info("tool_result_compacted name=%s fq=%s raw_len=%d compact_len=%d", "kb__kb_ground", "kb.kb_ground", len(tool_out), len(llm_tool_out))
                        messages.append({
                            "role": "tool",
                            "tool_call_id": synthetic_id,
                            "name": "kb__kb_ground",
                            "content": llm_tool_out,
                        })
                if should_force_draft(
                    phase_state,
                    phase_usage,
                    step,
                    max_steps,
                    seen_files=seen_files,
                    seen_kb=seen_kb,
                    seen_failure_signal=seen_failure_signal,
                ):
                    if not forced_draft_mode:
                        log.info("forced_draft enabled phase=%s step=%d kb_seen=%s kb_attempted=%s", phase_state.phase, step, seen_kb, phase_state.kb_grounding_attempted)
                    forced_draft_mode = True
                    if phase_state.phase != "draft_debug_steps":
                        phase_state = PhaseState(
                            phase="draft_debug_steps",
                            phase_index=6,
                            entered_step=step,
                            notes=list(phase_state.notes),
                            kb_grounding_attempted=phase_state.kb_grounding_attempted,
                            possible_failure_reason_ready=phase_state.possible_failure_reason_ready,
                        )
                        phase_usage = {"jira": 0, "files": 0, "kb": 0}

                if dumper:
                    dumper.write_round(step, {
                        "iteration": step,
                        "timestamp": utc_now_iso(),
                        "model": args.model,
                        "system_prompt": system_prompt,
                        "user_prompt": last_user_message(messages),
                        "llm_response": mm.content,
                        "messages": messages,
                        "tools": [t.get("function", {}).get("name") for t in openai_tools],
                        "tool_calls": tool_calls_dump,
                        "tool_results": tool_results_dump,
                        "response": {"content": mm.content, "tool_calls": [tc.__dict__ for tc in mm.tool_calls]},
                    })

                continue

            # Final
            if (
                phase_state.phase == "kb_grounding"
                and not seen_kb
                and not phase_state.kb_grounding_attempted
            ):
                log.warning(
                    "kb_grounding_exit_gate triggered step=%d seen_kb=%s kb_attempted=%s content_len=%d",
                    step,
                    seen_kb,
                    phase_state.kb_grounding_attempted,
                    len(mm.content or ""),
                )
                messages.append({"role": "user", "content": KB_GROUNDING_NUDGE})
                phase_state = PhaseState(
                    phase=phase_state.phase,
                    phase_index=phase_state.phase_index,
                    entered_step=phase_state.entered_step,
                    notes=list(phase_state.notes),
                    kb_grounding_attempted=True,
                    possible_failure_reason_ready=phase_state.possible_failure_reason_ready,
                )
                if dumper:
                    dumper.write_round(step, {
                        "iteration": step,
                        "timestamp": utc_now_iso(),
                        "model": args.model,
                        "system_prompt": system_prompt,
                        "user_prompt": last_user_message(messages),
                        "llm_response": mm.content,
                        "messages": messages,
                        "tools": [t.get("function", {}).get("name") for t in openai_tools],
                        "tool_calls": [],
                        "tool_results": [],
                        "response": {"content": mm.content, "tool_calls": [], "gated": "kb_grounding_exit_gate"},
                    })
                continue
            if not no_tool_exit:
                log.warning("exit_condition no_tool_calls disabled; exiting anyway")
            log.info("step=%d final_response content_len=%d", step, len(mm.content or ""))
            if dumper:
                dumper.write_round(step, {
                    "iteration": step,
                    "timestamp": utc_now_iso(),
                    "model": args.model,
                    "system_prompt": system_prompt,
                    "user_prompt": last_user_message(messages),
                    "llm_response": mm.content,
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
