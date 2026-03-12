#!/usr/bin/env python3
"""Local file/log MCP server (stdlib only).

Read-only tools for inspecting run-workspace files and extracting kernel-log signals.

Env:
- SIMPLE_RLA_WORKSPACE_DIR: preferred allowed root
- FILE_TOOLS_ROOT: optional fallback allowed root (single path)
- FILE_TOOLS_ROOTS: optional os.pathsep-separated allowlist roots
- FILE_TOOLS_MAX_FILE_BYTES: optional soft file size limit (default: 8 MiB)

Tools:
- file_head(path, lines?, max_chars?)
- file_tail(path, lines?, max_chars?)
- file_read_range(path, start_line, end_line, max_chars?)
- file_grep(path, pattern, ignore_case?, context_before?, context_after?, max_matches?, max_chars?)
- log_extract_signatures(path, profile?, context_before?, context_after?, max_signatures_per_kind?, max_total_signatures?, max_chars?)
- log_compare(left_path, right_path, profile?, context_lines?, max_signatures?, max_chars?)
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List

from .stdio_jsonrpc_server import StdioMcpServer, Tool


logger = logging.getLogger("simple_rla.file_tools")


_DEFAULT_MAX_FILE_BYTES = 8 * 1024 * 1024
_DEFAULT_HEAD_LINES = 80
_DEFAULT_TAIL_LINES = 200
_DEFAULT_MAX_CHARS = 12000
_DEFAULT_READ_RANGE_MAX_CHARS = 20000
_DEFAULT_GREP_MAX_MATCHES = 20
_DEFAULT_GREP_CONTEXT_BEFORE = 2
_DEFAULT_GREP_CONTEXT_AFTER = 4
_DEFAULT_LOG_CONTEXT_BEFORE = 2
_DEFAULT_LOG_CONTEXT_AFTER = 6
_DEFAULT_LOG_MAX_PER_KIND = 8
_DEFAULT_LOG_MAX_TOTAL = 32
_DEFAULT_COMPARE_CONTEXT = 6

_FATAL_RULES = [
    ("kernel-panic", r"kernel panic|not syncing"),
    ("oops", r"\bOops:"),
    ("bug", r"\bBUG:"),
    ("call-trace", r"\bCall Trace:"),
    ("rip", r"\bRIP:"),
    ("gpf", r"general protection fault"),
    ("null-deref", r"NULL pointer dereference|unable to handle kernel"),
    ("kernel-bug-at", r"kernel BUG at"),
]

_WARNING_RULES = [
    ("warning", r"\bWARNING:"),
    ("tainted", r"\bTainted:"),
    ("failed", r"\bfailed\b"),
    ("timeout", r"\btimeout\b"),
]

_SUBSYSTEM_RULES = [
    ("xe", r"\bxe\b"),
    ("drm", r"\bdrm\b"),
    ("i915", r"\bi915\b"),
    ("acpi", r"\bACPI\b"),
    ("pm", r"\bPM:\b|\bsuspend\b|\bresume\b"),
    ("guc", r"\bGuC\b|\bguc\b"),
    ("huc", r"\bHuC\b|\bhuc\b"),
    ("gsc", r"\bGSC\b|\bgsc\b"),
    ("pcie", r"\bPCIe\b|\bpcie\b"),
]


def _env_int(name: str, default: int) -> int:
    v = os.environ.get(name)
    if v is None:
        return default
    try:
        return int(v)
    except ValueError:
        return default


def _allowed_roots() -> list[Path]:
    roots: list[Path] = []
    for key in ("SIMPLE_RLA_WORKSPACE_DIR", "FILE_TOOLS_ROOT"):
        v = os.environ.get(key, "").strip()
        if v:
            roots.append(Path(v).resolve())
    extra = os.environ.get("FILE_TOOLS_ROOTS", "").strip()
    if extra:
        for part in extra.split(os.pathsep):
            part = part.strip()
            if part:
                roots.append(Path(part).resolve())
    uniq: list[Path] = []
    seen: set[str] = set()
    for r in roots:
        s = str(r)
        if s not in seen:
            uniq.append(r)
            seen.add(s)
    if not uniq:
        raise RuntimeError("no allowed file roots configured; set SIMPLE_RLA_WORKSPACE_DIR or FILE_TOOLS_ROOT")
    return uniq


def _resolve_path(path_arg: str) -> Path:
    if not isinstance(path_arg, str) or not path_arg.strip():
        raise ValueError("path is required")
    roots = _allowed_roots()
    raw = Path(path_arg.strip())
    candidates: list[Path] = []
    if raw.is_absolute():
        candidates.append(raw.resolve())
    else:
        for root in roots:
            candidates.append((root / raw).resolve())
    for cand in candidates:
        for root in roots:
            try:
                cand.relative_to(root)
                if not cand.exists():
                    raise FileNotFoundError(f"file not found: {cand}")
                if not cand.is_file():
                    raise RuntimeError(f"path is not a regular file: {cand}")
                max_bytes = _env_int("FILE_TOOLS_MAX_FILE_BYTES", _DEFAULT_MAX_FILE_BYTES)
                if cand.stat().st_size > max_bytes:
                    raise RuntimeError(f"file too large: {cand} ({cand.stat().st_size} bytes > {max_bytes})")
                return cand
            except ValueError:
                continue
    raise RuntimeError(f"path {path_arg!r} is outside allowed roots")


def _read_lines(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception as exc:
        raise RuntimeError(f"failed to read text file {path}: {exc}")


def _join_limited(lines: list[str], max_chars: int) -> tuple[str, bool]:
    text = "\n".join(lines)
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars], True


def _clip_list(lines: list[str], max_chars: int) -> list[str]:
    out: list[str] = []
    used = 0
    for line in lines:
        extra = len(line) + (1 if out else 0)
        if used + extra > max_chars:
            break
        out.append(line)
        used += extra
    return out


def _file_head(args: dict) -> dict:
    path = _resolve_path(args.get("path", ""))
    lines = int(args.get("lines", _DEFAULT_HEAD_LINES))
    max_chars = int(args.get("max_chars", _DEFAULT_MAX_CHARS))
    logger.info("file.request tool=file_head path=%s lines=%s max_chars=%s", path, lines, max_chars)
    if lines <= 0 or max_chars <= 0:
        raise ValueError("lines and max_chars must be > 0")
    all_lines = _read_lines(path)
    selected = all_lines[:lines]
    content, truncated = _join_limited(selected, max_chars)
    out = {
        "path": str(path),
        "start_line": 1,
        "end_line": len(selected),
        "truncated": truncated,
        "content": content,
    }
    logger.info("file.response tool=file_head path=%s start=%s end=%s truncated=%s chars=%s", path, out["start_line"], out["end_line"], out["truncated"], len(out["content"]))
    return out


def _file_tail(args: dict) -> dict:
    path = _resolve_path(args.get("path", ""))
    lines = int(args.get("lines", _DEFAULT_TAIL_LINES))
    max_chars = int(args.get("max_chars", 16000))
    logger.info("file.request tool=file_tail path=%s lines=%s max_chars=%s", path, lines, max_chars)
    if lines <= 0 or max_chars <= 0:
        raise ValueError("lines and max_chars must be > 0")
    all_lines = _read_lines(path)
    start_idx = max(0, len(all_lines) - lines)
    selected = all_lines[start_idx:]
    content, truncated = _join_limited(selected, max_chars)
    out = {
        "path": str(path),
        "start_line": start_idx + 1,
        "end_line": len(all_lines),
        "truncated": truncated,
        "content": content,
    }
    logger.info("file.response tool=file_tail path=%s start=%s end=%s truncated=%s chars=%s", path, out["start_line"], out["end_line"], out["truncated"], len(out["content"]))
    return out


def _file_read_range(args: dict) -> dict:
    path = _resolve_path(args.get("path", ""))
    start_line = int(args.get("start_line", 0))
    end_line = int(args.get("end_line", 0))
    max_chars = int(args.get("max_chars", _DEFAULT_READ_RANGE_MAX_CHARS))
    logger.info("file.request tool=file_read_range path=%s start=%s end=%s max_chars=%s", path, start_line, end_line, max_chars)
    if start_line < 1 or end_line < start_line or max_chars <= 0:
        raise ValueError("invalid line range or max_chars")
    all_lines = _read_lines(path)
    selected = all_lines[start_line - 1:end_line]
    content, truncated = _join_limited(selected, max_chars)
    out = {
        "path": str(path),
        "start_line": start_line,
        "end_line": min(end_line, len(all_lines)),
        "truncated": truncated,
        "content": content,
    }
    logger.info("file.response tool=file_read_range path=%s start=%s end=%s truncated=%s chars=%s", path, out["start_line"], out["end_line"], out["truncated"], len(out["content"]))
    return out


def _file_grep(args: dict) -> dict:
    path = _resolve_path(args.get("path", ""))
    pattern = args.get("pattern", "")
    if not isinstance(pattern, str) or not pattern:
        raise ValueError("pattern is required")
    ignore_case = bool(args.get("ignore_case", True))
    before = int(args.get("context_before", _DEFAULT_GREP_CONTEXT_BEFORE))
    after = int(args.get("context_after", _DEFAULT_GREP_CONTEXT_AFTER))
    max_matches = int(args.get("max_matches", _DEFAULT_GREP_MAX_MATCHES))
    max_chars = int(args.get("max_chars", 24000))
    logger.info("file.request tool=file_grep path=%s pattern=%s ignore_case=%s before=%s after=%s max_matches=%s max_chars=%s", path, pattern, ignore_case, before, after, max_matches, max_chars)
    if before < 0 or after < 0 or max_matches <= 0 or max_chars <= 0:
        raise ValueError("invalid grep limits")
    flags = re.IGNORECASE if ignore_case else 0
    try:
        rx = re.compile(pattern, flags)
    except re.error as exc:
        raise RuntimeError(f"invalid regex pattern: {exc}")
    all_lines = _read_lines(path)
    matches: list[dict[str, Any]] = []
    total = 0
    budget = max_chars
    for idx, line in enumerate(all_lines):
        if not rx.search(line):
            continue
        total += 1
        if len(matches) >= max_matches:
            continue
        cb = all_lines[max(0, idx - before):idx]
        ca = all_lines[idx + 1:idx + 1 + after]
        match_obj = {
            "line": idx + 1,
            "text": line,
            "context_before": cb,
            "context_after": ca,
        }
        rough = len(line) + sum(len(x) for x in cb) + sum(len(x) for x in ca)
        if matches and rough > budget:
            break
        matches.append(match_obj)
        budget -= rough
    truncated = total > len(matches)
    out = {
        "path": str(path),
        "pattern": pattern,
        "ignore_case": ignore_case,
        "match_count": total,
        "returned_matches": len(matches),
        "truncated": truncated,
        "matches": matches,
    }
    logger.info("file.response tool=file_grep path=%s pattern=%s match_count=%s returned=%s truncated=%s", path, pattern, out["match_count"], out["returned_matches"], out["truncated"])
    return out


def _sig_id(path: Path, kind: str, line_no: int, text: str) -> str:
    h = hashlib.sha1(f"{path}:{kind}:{line_no}:{text}".encode("utf-8")).hexdigest()[:10]
    return f"sig-{h}"


def _extract_signatures_from_lines(path: Path, all_lines: list[str], *, context_before: int, context_after: int, max_signatures_per_kind: int, max_total_signatures: int) -> dict:
    compiled_fatal = [(kind, re.compile(pat, re.IGNORECASE)) for kind, pat in _FATAL_RULES]
    compiled_warn = [(kind, re.compile(pat, re.IGNORECASE)) for kind, pat in _WARNING_RULES]
    compiled_subsys = [(tag, re.compile(pat, re.IGNORECASE)) for tag, pat in _SUBSYSTEM_RULES]
    signatures: list[dict[str, Any]] = []
    per_kind: dict[str, int] = {}
    subsystem_seen: set[str] = set()
    taint_seen = False

    def add_sig(kind: str, line_no: int, text: str, tags: list[str]) -> None:
        if len(signatures) >= max_total_signatures:
            return
        if per_kind.get(kind, 0) >= max_signatures_per_kind:
            return
        context = all_lines[max(0, line_no - 1 - context_before): min(len(all_lines), line_no + context_after)]
        signatures.append({
            "id": _sig_id(path, kind, line_no, text),
            "kind": kind,
            "line": line_no,
            "text": text,
            "tags": tags,
            "context": context,
        })
        per_kind[kind] = per_kind.get(kind, 0) + 1

    for idx, line in enumerate(all_lines, start=1):
        if "Tainted:" in line:
            taint_seen = True
        for kind, rx in compiled_fatal:
            if rx.search(line):
                add_sig(kind, idx, line, ["fatal", kind])
                break
        for kind, rx in compiled_warn:
            if rx.search(line):
                add_sig(kind, idx, line, ["warning", kind])
                break
        for tag, rx in compiled_subsys:
            if rx.search(line):
                subsystem_seen.add(tag)
                if per_kind.get("subsystem-hint", 0) < max_signatures_per_kind and len(signatures) < max_total_signatures:
                    add_sig("subsystem-hint", idx, line, [tag])
                break

    fatal_count = sum(1 for s in signatures if "fatal" in s.get("tags", []))
    warning_count = sum(1 for s in signatures if "warning" in s.get("tags", []))
    return {
        "summary": {
            "fatal_count": fatal_count,
            "warning_count": warning_count,
            "subsystem_hints": sorted(subsystem_seen),
            "taint_seen": taint_seen,
        },
        "signatures": signatures,
    }


def _log_extract_signatures(args: dict) -> dict:
    path = _resolve_path(args.get("path", ""))
    profile = str(args.get("profile", "kernel"))
    logger.info("file.request tool=log_extract_signatures path=%s profile=%s", path, profile)
    if profile != "kernel":
        raise RuntimeError(f"unsupported log profile: {profile} (supported: kernel)")
    before = int(args.get("context_before", _DEFAULT_LOG_CONTEXT_BEFORE))
    after = int(args.get("context_after", _DEFAULT_LOG_CONTEXT_AFTER))
    max_per_kind = int(args.get("max_signatures_per_kind", _DEFAULT_LOG_MAX_PER_KIND))
    max_total = int(args.get("max_total_signatures", _DEFAULT_LOG_MAX_TOTAL))
    max_chars = int(args.get("max_chars", 24000))
    if before < 0 or after < 0 or max_per_kind <= 0 or max_total <= 0 or max_chars <= 0:
        raise ValueError("invalid signature extraction limits")
    all_lines = _read_lines(path)
    result = _extract_signatures_from_lines(path, all_lines, context_before=before, context_after=after, max_signatures_per_kind=max_per_kind, max_total_signatures=max_total)
    trimmed: list[dict[str, Any]] = []
    used = 0
    for sig in result["signatures"]:
        rough = len(sig.get("text", "")) + sum(len(x) for x in sig.get("context", []))
        if trimmed and used + rough > max_chars:
            break
        trimmed.append(sig)
        used += rough
    out = {
        "path": str(path),
        "profile": profile,
        "summary": result["summary"],
        "truncated": len(trimmed) < len(result["signatures"]),
        "signatures": trimmed,
    }
    logger.info("file.response tool=log_extract_signatures path=%s profile=%s fatal=%s warning=%s subsystems=%s returned=%s truncated=%s", path, profile, out["summary"].get("fatal_count"), out["summary"].get("warning_count"), ",".join(out["summary"].get("subsystem_hints", [])[:6]), len(out["signatures"]), out["truncated"])
    return out


def _normalize_compare_line(line: str) -> str:
    line = re.sub(r"0x[0-9a-fA-F]+", "0xADDR", line)
    line = re.sub(r"\b\d+\b", "N", line)
    return line.strip()


def _log_compare(args: dict) -> dict:
    left_path = _resolve_path(args.get("left_path", ""))
    right_path = _resolve_path(args.get("right_path", ""))
    profile = str(args.get("profile", "kernel"))
    logger.info("file.request tool=log_compare left=%s right=%s profile=%s", left_path, right_path, profile)
    context_lines = int(args.get("context_lines", _DEFAULT_COMPARE_CONTEXT))
    max_signatures = int(args.get("max_signatures", 20))
    max_chars = int(args.get("max_chars", 24000))
    if profile != "kernel":
        raise RuntimeError(f"unsupported log profile: {profile} (supported: kernel)")
    if context_lines < 0 or max_signatures <= 0 or max_chars <= 0:
        raise ValueError("invalid compare limits")
    left_lines = _read_lines(left_path)
    right_lines = _read_lines(right_path)
    common_prefix = 0
    for l, r in zip(left_lines, right_lines):
        if _normalize_compare_line(l) != _normalize_compare_line(r):
            break
        common_prefix += 1
    left_extract = _extract_signatures_from_lines(left_path, left_lines, context_before=2, context_after=4, max_signatures_per_kind=max_signatures, max_total_signatures=max_signatures)
    right_extract = _extract_signatures_from_lines(right_path, right_lines, context_before=2, context_after=4, max_signatures_per_kind=max_signatures, max_total_signatures=max_signatures)
    left_key = {(s["kind"], s["text"]) for s in left_extract["signatures"]}
    right_key = {(s["kind"], s["text"]) for s in right_extract["signatures"]}
    left_only = [s for s in left_extract["signatures"] if (s["kind"], s["text"]) not in right_key][:max_signatures]
    right_only = [s for s in right_extract["signatures"] if (s["kind"], s["text"]) not in left_key][:max_signatures]
    shared = []
    seen_shared: set[tuple[str, str]] = set()
    for s in left_extract["signatures"]:
        key = (s["kind"], s["text"])
        if key in right_key and key not in seen_shared:
            item = {"kind": s["kind"]}
            if s["kind"] == "subsystem-hint" and s.get("tags"):
                item["tag"] = s["tags"][0]
            else:
                item["text"] = s["text"]
            shared.append(item)
            seen_shared.add(key)
    left_excerpt = left_lines[max(0, common_prefix - context_lines): min(len(left_lines), common_prefix + context_lines)]
    right_excerpt = right_lines[max(0, common_prefix - context_lines): min(len(right_lines), common_prefix + context_lines)]
    summary = "logs are identical after normalization through compared prefix"
    if left_only or right_only:
        left_sub = ", ".join(left_extract["summary"].get("subsystem_hints", [])[:3]) or "unknown"
        right_sub = ", ".join(right_extract["summary"].get("subsystem_hints", [])[:3]) or "unknown"
        summary = f"logs diverge after line {common_prefix}; left hints={left_sub}; right hints={right_sub}"
    result = {
        "left_path": str(left_path),
        "right_path": str(right_path),
        "profile": profile,
        "common_prefix_lines": common_prefix,
        "divergence": {
            "left_line": min(common_prefix + 1, len(left_lines)),
            "right_line": min(common_prefix + 1, len(right_lines)),
            "left_excerpt": _clip_list(left_excerpt, max_chars // 4),
            "right_excerpt": _clip_list(right_excerpt, max_chars // 4),
        },
        "left_only_signatures": [{"kind": s["kind"], "line": s["line"], "text": s["text"]} for s in left_only],
        "right_only_signatures": [{"kind": s["kind"], "line": s["line"], "text": s["text"]} for s in right_only],
        "shared_signatures": shared[:max_signatures],
        "summary": summary,
    }
    logger.info("file.response tool=log_compare left=%s right=%s prefix=%s left_only=%s right_only=%s shared=%s", left_path, right_path, result["common_prefix_lines"], len(result["left_only_signatures"]), len(result["right_only_signatures"]), len(result["shared_signatures"]))
    return result


def main() -> None:
    server = StdioMcpServer(name="file-tools", version="0.1")
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
        name="log_extract_signatures",
        description="Extract kernel-log panic/warning/subsystem signatures from a local text log file.",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "profile": {"type": "string"},
                "context_before": {"type": "integer", "minimum": 0},
                "context_after": {"type": "integer", "minimum": 0},
                "max_signatures_per_kind": {"type": "integer", "minimum": 1},
                "max_total_signatures": {"type": "integer", "minimum": 1},
                "max_chars": {"type": "integer", "minimum": 1},
            },
            "required": ["path"],
        },
        handler=_log_extract_signatures,
    ))
    server.add_tool(Tool(
        name="log_compare",
        description="Compare two kernel logs by normalized common prefix and extracted signatures.",
        input_schema={
            "type": "object",
            "properties": {
                "left_path": {"type": "string"},
                "right_path": {"type": "string"},
                "profile": {"type": "string"},
                "context_lines": {"type": "integer", "minimum": 0},
                "max_signatures": {"type": "integer", "minimum": 1},
                "max_chars": {"type": "integer", "minimum": 1},
            },
            "required": ["left_path", "right_path"],
        },
        handler=_log_compare,
    ))
    server.run_forever()


if __name__ == "__main__":
    main()
