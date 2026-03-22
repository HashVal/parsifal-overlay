#!/usr/bin/env python3
"""Workflow-facing file/log MCP server v2 (stdlib only).

This server intentionally exposes a smaller, more deterministic tool surface for
structured workflow phases.

Env:
- SIMPLE_RLA_WORKSPACE_DIR
- FILE_TOOLS_ROOT
- FILE_TOOLS_ROOTS
- FILE_TOOLS_MAX_FILE_BYTES

Tools:
- file_head(path, lines?, max_chars?) -> dict
- file_tail(path, lines?, max_chars?) -> dict
- file_read_range(path, start_line, end_line, max_chars?) -> dict
- file_grep(path, pattern, ignore_case?, context_before?, context_after?, max_matches?, max_chars?) -> dict
- log_extract_evidence(path, profile?, max_events?, max_error_events?, max_chars?) -> dict
- log_extract_evidence_batch(paths, profile?, max_files?, max_events_per_file?, max_error_events_per_file?, max_chars_per_file?) -> dict
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any

from .file_tools_server import (
    _DEFAULT_LOG_MAX_TOTAL,
    _FATAL_RULES,
    _ERROR_RULES,
    _SUBSYSTEM_RULES,
    _extract_essential,
    _file_grep,
    _file_head,
    _file_read_range,
    _file_tail,
    _find_match,
    _make_context,
    _read_lines,
    _resolve_path,
)
from .stdio_jsonrpc_server import StdioMcpServer, Tool

logger = logging.getLogger("simple_rla.file_tools_v2")


_FATAL_EVENT_PRIORITY = {
    "kernel-panic": 0,
    "kernel-bug-at": 1,
    "oops": 2,
    "gpf": 3,
    "null-deref": 4,
    "bug": 5,
}


def _extract_functions_from_trace(trace_excerpt: list[str], *, max_functions: int = 8) -> list[str]:
    out: list[str] = []
    for line in trace_excerpt:
        m = re.search(r"\?\s*([A-Za-z0-9_.$]+)\+0x[0-9a-fA-F]+/[0-9a-fA-Fx]+", line)
        if not m:
            m = re.search(r"([A-Za-z0-9_.$]+)\+0x[0-9a-fA-F]+/[0-9a-fA-Fx]+", line)
        if not m:
            continue
        fn = m.group(1)
        if fn not in out:
            out.append(fn)
        if len(out) >= max_functions:
            break
    return out


def _extract_modules_from_text(lines: list[str], *, max_modules: int = 8) -> list[str]:
    out: list[str] = []
    skip = {"U", "E", "TASK"}
    for line in lines:
        for mod in re.findall(r"\[([A-Za-z0-9_]+)\]", line):
            if mod in skip:
                continue
            if mod not in out:
                out.append(mod)
            if len(out) >= max_modules:
                return out
    return out


def _compact_event(event: dict[str, Any], *, max_excerpt_lines: int = 12, max_trace_lines: int = 8) -> dict[str, Any]:
    compact = dict(event)
    compact["raw_excerpt"] = list((event.get("raw_excerpt") or [])[:max_excerpt_lines])
    compact["trace_excerpt"] = list((event.get("trace_excerpt") or [])[:max_trace_lines])
    return compact


def _extract_trace_excerpt(all_lines: list[str], call_trace_line: int, *, max_frames: int = 12) -> list[str]:
    excerpt: list[str] = []
    started = False
    for idx in range(call_trace_line, min(len(all_lines), call_trace_line + 80)):
        line = all_lines[idx]
        stripped = line.strip()
        if not stripped:
            if started and excerpt:
                break
            continue
        if not started:
            if "Call Trace:" in stripped:
                started = True
            continue
        if stripped in {"<TASK>", "</TASK>"}:
            continue
        if re.search(r"^(RIP:|Code:|RSP:|RAX:|RDX:|RBP:|FS:|CS:|CR2:|PKRU:|Modules linked in:|---\[ end trace)", stripped):
            if excerpt:
                break
            continue
        if "+0x" not in stripped:
            if excerpt:
                break
            continue
        excerpt.append(stripped)
        if len(excerpt) >= max_frames:
            break
    return excerpt


def _scan_crash_events(path: Path, all_lines: list[str], *, max_events: int) -> list[dict[str, Any]]:
    compiled_rules = [(kind, re.compile(pat, re.IGNORECASE)) for kind, pat in _FATAL_RULES]
    hits: list[dict[str, Any]] = []
    for idx, line in enumerate(all_lines, start=1):
        kind = _find_match(line, compiled_rules)
        if not kind:
            continue
        hits.append({"kind": kind, "line": idx, "text": line})
    if not hits:
        return []

    clusters: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    cluster_gap = 20
    for hit in hits:
        if not current or hit["line"] - current[-1]["line"] <= cluster_gap:
            current.append(hit)
        else:
            clusters.append(current)
            current = [hit]
    if current:
        clusters.append(current)

    out: list[dict[str, Any]] = []
    for cluster in clusters[-max_events:]:
        headline = None
        rip = None
        call_trace = None
        for item in cluster:
            kind = str(item["kind"])
            if kind in _FATAL_EVENT_PRIORITY:
                if headline is None or _FATAL_EVENT_PRIORITY[kind] < _FATAL_EVENT_PRIORITY[str(headline['kind'])]:
                    headline = item
            if kind == "rip" and rip is None:
                rip = item
            if kind == "call-trace" and call_trace is None:
                call_trace = item
        if headline is None and rip is None and call_trace is None:
            continue
        anchor = headline or rip or call_trace
        start_line = cluster[0]["line"]
        end_line = cluster[-1]["line"]
        raw_excerpt = _make_context(all_lines, int(anchor["line"]), 3, 16)
        trace_excerpt = _extract_trace_excerpt(all_lines, int(call_trace["line"])) if call_trace is not None else []
        modules = _extract_modules_from_text(raw_excerpt + trace_excerpt)
        functions = _extract_functions_from_trace(trace_excerpt)
        event = {
            "event_kind": str((headline or call_trace or rip)["kind"]),
            "bundle_type": "fatal_with_trace" if (rip is not None or call_trace is not None) else "fatal_only",
            "start_line": start_line,
            "end_line": end_line,
            "headline": {
                "kind": headline["kind"],
                "line": headline["line"],
                "text": headline["text"],
            } if headline is not None else None,
            "rip": {
                "line": rip["line"],
                "text": rip["text"],
            } if rip is not None else None,
            "call_trace": {
                "line": call_trace["line"],
                "text": call_trace["text"],
            } if call_trace is not None else None,
            "trace_excerpt": trace_excerpt,
            "functions": functions,
            "modules": modules,
            "raw_excerpt": raw_excerpt,
        }
        out.append(_compact_event(event))
    return out


def _scan_error_events(all_lines: list[str], *, max_items: int) -> list[dict[str, Any]]:
    compiled_rules = [(kind, re.compile(pat, re.IGNORECASE)) for kind, pat in _ERROR_RULES]
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for idx, line in enumerate(all_lines, start=1):
        kind = _find_match(line, compiled_rules)
        if not kind:
            continue
        key = (kind, line.strip())
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "kind": kind,
            "line": idx,
            "text": line,
            "context": _make_context(all_lines, idx, 1, 3),
        })
        if len(out) >= max_items:
            break
    return out


def _scan_subsystem_evidence(all_lines: list[str], *, max_items: int = 8) -> dict[str, Any]:
    tags: list[str] = []
    evidence: list[dict[str, Any]] = []
    compiled = [(tag, re.compile(pat, re.IGNORECASE)) for tag, pat in _SUBSYSTEM_RULES]
    for idx, line in enumerate(all_lines, start=1):
        for tag, rx in compiled:
            if not rx.search(line):
                continue
            if tag not in tags:
                tags.append(tag)
            if len(evidence) < max_items:
                evidence.append({"tag": tag, "line": idx, "text": line})
            break
    return {
        "tags": tags[:8],
        "evidence": evidence[:max_items],
    }


def _derive_summary(crash_events: list[dict[str, Any]], error_events: list[dict[str, Any]], subsystem_evidence: dict[str, Any]) -> dict[str, Any]:
    primary = list(subsystem_evidence.get("tags") or [])[:4]
    dominant_failure_mode = None
    if crash_events:
        dominant_failure_mode = crash_events[0].get("event_kind")
    elif error_events:
        dominant_failure_mode = error_events[0].get("kind")
    return {
        "has_crash": bool(crash_events),
        "crash_event_count": len(crash_events),
        "error_event_count": len(error_events),
        "has_call_trace": any(bool(item.get("call_trace")) for item in crash_events),
        "primary_subsystems": primary,
        "dominant_failure_mode": dominant_failure_mode,
    }


def _tool_log_extract_evidence(args: dict[str, Any]) -> dict[str, Any]:
    path = _resolve_path(args.get("path", ""))
    profile = str(args.get("profile", "kernel"))
    if profile != "kernel":
        raise RuntimeError(f"unsupported log profile: {profile} (supported: kernel)")
    max_events = int(args.get("max_events", 4))
    max_error_events = int(args.get("max_error_events", 6))
    max_chars = int(args.get("max_chars", 12000))
    if max_events <= 0 or max_error_events <= 0 or max_chars <= 0:
        raise ValueError("invalid evidence extraction limits")

    all_lines = _read_lines(path)
    environment = _extract_essential(all_lines)
    crash_events = _scan_crash_events(path, all_lines, max_events=max_events)
    error_events = _scan_error_events(all_lines, max_items=max_error_events)
    subsystem_evidence = _scan_subsystem_evidence(all_lines, max_items=8)
    summary = _derive_summary(crash_events, error_events, subsystem_evidence)

    out = {
        "path": str(path),
        "profile": profile,
        "environment": environment,
        "crash_events": crash_events,
        "error_events": error_events,
        "subsystem_evidence": subsystem_evidence,
        "summary": summary,
    }
    text = str(out)
    if len(text) > max_chars:
        trimmed = dict(out)
        trimmed["crash_events"] = [
            _compact_event(item, max_excerpt_lines=6, max_trace_lines=4)
            for item in crash_events[:max_events]
        ]
        trimmed["error_events"] = error_events[:max_error_events]
        trimmed["subsystem_evidence"] = {
            "tags": list(subsystem_evidence.get("tags") or [])[:6],
            "evidence": list(subsystem_evidence.get("evidence") or [])[:4],
        }
        out = trimmed
    logger.info(
        "file_tools_v2.log_extract_evidence path=%s crash_events=%s error_events=%s subsystems=%s",
        path,
        len(out.get("crash_events") or []),
        len(out.get("error_events") or []),
        ",".join((out.get("subsystem_evidence") or {}).get("tags", [])[:6]),
    )
    return out


def _normalized_text(value: Any) -> str:
    text = str(value or "").strip()
    text = re.sub(r"0x[0-9a-fA-F]+", "0xADDR", text)
    text = re.sub(r"\b\d+\b", "N", text)
    return text


def _tool_log_extract_evidence_batch(args: dict[str, Any]) -> dict[str, Any]:
    raw_paths = args.get("paths")
    if not isinstance(raw_paths, list) or not raw_paths:
        raise ValueError("paths must be a non-empty list")
    profile = str(args.get("profile", "kernel"))
    if profile != "kernel":
        raise RuntimeError(f"unsupported log profile: {profile} (supported: kernel)")
    max_files = int(args.get("max_files", len(raw_paths)))
    max_events = int(args.get("max_events_per_file", 4))
    max_error_events = int(args.get("max_error_events_per_file", 6))
    max_chars = int(args.get("max_chars_per_file", 12000))
    if max_files <= 0 or max_events <= 0 or max_error_events <= 0 or max_chars <= 0:
        raise ValueError("invalid batch evidence extraction limits")

    files: list[dict[str, Any]] = []
    merged_subsystems: list[str] = []
    merged_functions: list[str] = []
    merged_failure_modes: list[str] = []
    errors: list[dict[str, Any]] = []
    env_map: dict[tuple[str, str], dict[str, Any]] = {}
    crash_map: dict[str, dict[str, Any]] = {}
    error_map: dict[tuple[str, str], dict[str, Any]] = {}
    crash_trace_sources: dict[str, dict[str, dict[str, Any]]] = {}

    for raw_path in raw_paths[:max_files]:
        path_text = str(raw_path)
        source_name = Path(path_text).name
        try:
            result = _tool_log_extract_evidence({
                "path": path_text,
                "profile": profile,
                "max_events": max_events,
                "max_error_events": max_error_events,
                "max_chars": max_chars,
            })
            files.append({"path": result.get("path"), "ok": True, "result": result})
            for tag in (result.get("subsystem_evidence") or {}).get("tags", []) or []:
                tag_text = str(tag).strip()
                if tag_text and tag_text not in merged_subsystems:
                    merged_subsystems.append(tag_text)
            env = result.get("environment") or {}
            for key in ("kernel_version", "cmdline", "dmi", "hostname"):
                value = env.get(key)
                if value in (None, "", [], {}):
                    continue
                bucket = env_map.setdefault((key, _normalized_text(value)), {"field": key, "value": value, "exists_in": []})
                if source_name not in bucket["exists_in"]:
                    bucket["exists_in"].append(source_name)
            for hint in env.get("driver_hints", []) or []:
                bucket = env_map.setdefault(("driver_hint", _normalized_text(hint)), {"field": "driver_hint", "value": hint, "exists_in": []})
                if source_name not in bucket["exists_in"]:
                    bucket["exists_in"].append(source_name)
            for event in result.get("crash_events", []) or []:
                headline = ((event.get("headline") or {}).get("text") or "")
                rip_text = ((event.get("rip") or {}).get("text") or "")
                functions = list(event.get("functions") or [])
                key = "|".join([
                    str(event.get("event_kind") or ""),
                    _normalized_text(headline),
                    _normalized_text(rip_text),
                    ",".join(functions[:4]),
                ])
                bucket = crash_map.setdefault(key, {
                    "event_kind": event.get("event_kind"),
                    "bundle_type": event.get("bundle_type"),
                    "headline": event.get("headline"),
                    "rip": event.get("rip"),
                    "call_trace": event.get("call_trace"),
                    "trace_excerpt": list(event.get("trace_excerpt") or [])[:6],
                    "functions": functions[:8],
                    "modules": list(event.get("modules") or [])[:8],
                    "exists_in": [],
                })
                trace_sources = crash_trace_sources.setdefault(key, {})
                trace_sources[source_name] = {
                    "trace_excerpt": list(event.get("trace_excerpt") or [])[:8],
                    "functions": functions[:8],
                }
                if source_name not in bucket["exists_in"]:
                    bucket["exists_in"].append(source_name)
                mode = str(event.get("event_kind") or "").strip()
                if mode and mode not in merged_failure_modes:
                    merged_failure_modes.append(mode)
                for fn in functions:
                    fn_text = str(fn).strip()
                    if fn_text and fn_text not in merged_functions:
                        merged_functions.append(fn_text)
            for event in result.get("error_events", []) or []:
                key = (str(event.get("kind") or ""), _normalized_text(event.get("text") or ""))
                bucket = error_map.setdefault(key, {
                    "kind": event.get("kind"),
                    "text": event.get("text"),
                    "context": list(event.get("context") or [])[:4],
                    "exists_in": [],
                })
                if source_name not in bucket["exists_in"]:
                    bucket["exists_in"].append(source_name)
        except Exception as exc:
            errors.append({"path": path_text, "error": str(exc)})
            files.append({"path": path_text, "ok": False, "error": str(exc)})

    merged_crash_events: list[dict[str, Any]] = []
    for key, item in list(crash_map.items())[:8]:
        sources = crash_trace_sources.get(key, {})
        common_functions: list[str] = []
        common_excerpt: list[str] = []
        if sources:
            func_sets = [set(v.get("functions") or []) for v in sources.values() if v.get("functions")]
            if func_sets:
                common_functions = [fn for fn in (next(iter(func_sets)).copy()) if all(fn in s for s in func_sets)]
            excerpt_lists = [list(v.get("trace_excerpt") or []) for v in sources.values() if v.get("trace_excerpt")]
            if excerpt_lists:
                shortest = min(len(x) for x in excerpt_lists)
                for idx in range(shortest):
                    candidate = excerpt_lists[0][idx]
                    if all(lst[idx] == candidate for lst in excerpt_lists[1:]):
                        common_excerpt.append(candidate)
                    else:
                        break
        trace_view = {
            "present_in": list(item.get("exists_in") or []),
            "shared_functions": common_functions[:8],
            "shared_excerpt": common_excerpt[:6],
            "per_source_excerpt": {
                source: list((payload.get("trace_excerpt") or [])[:6])
                for source, payload in sources.items()
                if payload.get("trace_excerpt")
            },
            "similarity": "high" if len(sources) >= 2 and common_excerpt else ("partial" if len(sources) >= 2 else "single"),
        }
        merged_item = dict(item)
        merged_item["trace"] = trace_view
        if trace_view["shared_functions"]:
            merged_item["functions"] = trace_view["shared_functions"]
        if trace_view["shared_excerpt"]:
            merged_item["trace_excerpt"] = trace_view["shared_excerpt"]
        merged_crash_events.append(merged_item)

    merged = {
        "environment": list(env_map.values())[:12],
        "crash_events": merged_crash_events,
        "error_events": list(error_map.values())[:12],
        "subsystem_tags": merged_subsystems[:8],
        "functions": merged_functions[:16],
        "failure_modes": merged_failure_modes[:8],
    }
    return {
        "profile": profile,
        "file_count": len(files),
        "ok_file_count": sum(1 for item in files if item.get("ok")),
        "merged": merged,
        "files": files,
        "errors": errors,
    }


def main() -> None:
    logging.basicConfig(
        level=getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    server = StdioMcpServer(name="file-tools-v2", version="0.1")
    server.add_tool(Tool(
        name="file_head",
        description="Read the first N lines of a text file within the allowed workspace roots.",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "lines": {"type": "integer", "minimum": 1},
                "max_chars": {"type": "integer", "minimum": 1},
            },
            "required": ["path"],
        },
        handler=_file_head,
    ))
    server.add_tool(Tool(
        name="file_tail",
        description="Read the last N lines of a text file within the allowed workspace roots.",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "lines": {"type": "integer", "minimum": 1},
                "max_chars": {"type": "integer", "minimum": 1},
            },
            "required": ["path"],
        },
        handler=_file_tail,
    ))
    server.add_tool(Tool(
        name="file_read_range",
        description="Read a specific inclusive line range from a text file within the allowed workspace roots.",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "start_line": {"type": "integer", "minimum": 1},
                "end_line": {"type": "integer", "minimum": 1},
                "max_chars": {"type": "integer", "minimum": 1},
            },
            "required": ["path", "start_line", "end_line"],
        },
        handler=_file_read_range,
    ))
    server.add_tool(Tool(
        name="file_grep",
        description="Regex search within a text file, returning line numbers and limited surrounding context.",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "pattern": {"type": "string"},
                "ignore_case": {"type": "boolean"},
                "context_before": {"type": "integer", "minimum": 0},
                "context_after": {"type": "integer", "minimum": 0},
                "max_matches": {"type": "integer", "minimum": 1},
                "max_chars": {"type": "integer", "minimum": 1},
            },
            "required": ["path", "pattern"],
        },
        handler=_file_grep,
    ))
    server.add_tool(Tool(
        name="log_extract_evidence",
        description="Extract workflow-facing kernel log evidence: environment facts, crash events, error events, subsystem evidence, and a derived summary.",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "profile": {"type": "string"},
                "max_events": {"type": "integer", "minimum": 1},
                "max_error_events": {"type": "integer", "minimum": 1},
                "max_chars": {"type": "integer", "minimum": 1},
            },
            "required": ["path"],
        },
        handler=_tool_log_extract_evidence,
    ))
    server.add_tool(Tool(
        name="log_extract_evidence_batch",
        description="Extract workflow-facing kernel log evidence for multiple files and return per-file results plus compact merged summaries.",
        input_schema={
            "type": "object",
            "properties": {
                "paths": {"type": "array", "items": {"type": "string"}, "minItems": 1},
                "profile": {"type": "string"},
                "max_files": {"type": "integer", "minimum": 1},
                "max_events_per_file": {"type": "integer", "minimum": 1},
                "max_error_events_per_file": {"type": "integer", "minimum": 1},
                "max_chars_per_file": {"type": "integer", "minimum": 1},
            },
            "required": ["paths"],
        },
        handler=_tool_log_extract_evidence_batch,
    ))
    server.run_forever()


if __name__ == "__main__":
    main()
