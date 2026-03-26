#!/usr/bin/env python3
"""Atomic code-side MCP tools for simple-rla."""

from __future__ import annotations

import fnmatch
import logging
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from .stdio_jsonrpc_server import StdioMcpServer, Tool


logger = logging.getLogger("simple_rla.code_tools")

_SOURCE_EXTENSIONS = {
    ".c",
    ".cc",
    ".cpp",
    ".cxx",
    ".go",
    ".h",
    ".hh",
    ".hpp",
    ".hxx",
    ".java",
    ".js",
    ".jsx",
    ".py",
    ".rs",
    ".swift",
    ".ts",
    ".tsx",
}

_LANGUAGE_EXTENSIONS = {
    "c": {".c", ".h"},
    "cpp": {".cc", ".cpp", ".cxx", ".hh", ".hpp", ".hxx"},
    "go": {".go"},
    "java": {".java"},
    "javascript": {".js", ".jsx"},
    "python": {".py"},
    "rust": {".rs"},
    "swift": {".swift"},
    "typescript": {".ts", ".tsx"},
}


@dataclass(frozen=True)
class CodeToolScope:
    repo: str | None
    repo_path: Path
    ref: str
    path_filters: tuple[str, ...] = ()
    language: str | None = None


def _run_git_bytes(repo_path: Path, args: list[str]) -> bytes:
    proc = subprocess.run(
        ["git", "-C", str(repo_path), *args],
        capture_output=True,
    )
    if proc.returncode != 0:
        stderr = (proc.stderr or b"").decode("utf-8", errors="replace").strip()
        raise RuntimeError(stderr or f"git command failed: {' '.join(args)}")
    return proc.stdout or b""


def _run_git_text(repo_path: Path, args: list[str]) -> str:
    return _run_git_bytes(repo_path, args).decode("utf-8", errors="replace").strip()


def _as_bool(value: Any, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if not text:
        return default
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"invalid boolean value: {value!r}")


def _normalize_path_filters(value: Any) -> tuple[str, ...]:
    if value in (None, ""):
        return ()
    if not isinstance(value, list):
        raise ValueError("path_filters must be a list")
    out: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if text:
            out.append(text)
    return tuple(out)


def _normalize_repo_rel_path(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError("file_path is required")
    path = PurePosixPath(text)
    if path.is_absolute():
        raise ValueError("file_path must be repo-relative")
    if ".." in path.parts:
        raise ValueError("file_path must not contain parent traversal")
    normalized = path.as_posix()
    if normalized in {"", "."}:
        raise ValueError("file_path is required")
    return normalized


def _resolve_scope(args: dict[str, Any]) -> CodeToolScope:
    repo_path_text = str(args.get("repo_path") or "").strip()
    if not repo_path_text:
        raise ValueError("repo_path is required")
    repo_path = Path(repo_path_text).expanduser().resolve()
    if not repo_path.exists() or not repo_path.is_dir():
        raise ValueError(f"repo_path does not exist: {repo_path}")

    git_root = _run_git_text(repo_path, ["rev-parse", "--show-toplevel"])
    if Path(git_root).resolve() != repo_path:
        raise ValueError("repo_path must point to the repo/worktree root")

    ref = str(args.get("ref") or "").strip()
    if not ref:
        raise ValueError("ref is required")
    _run_git_text(repo_path, ["rev-parse", "--verify", f"{ref}^{{commit}}"])

    repo = str(args.get("repo") or "").strip() or None
    path_filters = _normalize_path_filters(args.get("path_filters"))
    language = str(args.get("language") or "").strip().lower() or None
    return CodeToolScope(
        repo=repo,
        repo_path=repo_path,
        ref=ref,
        path_filters=path_filters,
        language=language,
    )


def _path_matches_filters(path: str, filters: tuple[str, ...]) -> bool:
    if not filters:
        return True
    for pattern in filters:
        if fnmatch.fnmatchcase(path, pattern):
            return True
        normalized = pattern.rstrip("/")
        if normalized and (path == normalized or path.startswith(normalized + "/")):
            return True
    return False


def _language_allows_path(path: str, language: str | None) -> bool:
    suffix = Path(path).suffix.lower()
    if language:
        allowed = _LANGUAGE_EXTENSIONS.get(language)
        if allowed is None:
            return True
        return suffix in allowed
    return True


def _is_source_path(path: str, language: str | None) -> bool:
    suffix = Path(path).suffix.lower()
    if language:
        allowed = _LANGUAGE_EXTENSIONS.get(language)
        if allowed is None:
            return suffix in _SOURCE_EXTENSIONS
        return suffix in allowed
    return suffix in _SOURCE_EXTENSIONS


def _list_scoped_files(scope: CodeToolScope, *, source_only: bool = False) -> list[str]:
    raw = _run_git_text(scope.repo_path, ["ls-tree", "-r", "--name-only", scope.ref])
    files = [line.strip() for line in raw.splitlines() if line.strip()]
    out: list[str] = []
    for path in files:
        if not _path_matches_filters(path, scope.path_filters):
            continue
        if not _language_allows_path(path, scope.language):
            continue
        if source_only and not _is_source_path(path, scope.language):
            continue
        out.append(path)
    return out


def _read_blob_text(scope: CodeToolScope, file_path: str) -> str:
    raw = _run_git_bytes(scope.repo_path, ["show", f"{scope.ref}:{file_path}"])
    if b"\x00" in raw:
        raise ValueError(f"binary file is not supported: {file_path}")
    return raw.decode("utf-8", errors="replace")


def _read_blob_lines(scope: CodeToolScope, file_path: str) -> list[str]:
    return _read_blob_text(scope, file_path).splitlines()


def _build_provenance(scope: CodeToolScope) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "repo_path": str(scope.repo_path),
        "ref": scope.ref,
    }
    if scope.repo:
        payload["repo"] = scope.repo
    if scope.path_filters:
        payload["path_filters"] = list(scope.path_filters)
    if scope.language:
        payload["language"] = scope.language
    return payload


def _symbol_patterns(symbol: str) -> list[tuple[str, re.Pattern[str]]]:
    escaped = re.escape(symbol)
    patterns: list[tuple[str, str]] = [
        ("function", rf"^\s*def\s+{escaped}\b"),
        ("class", rf"^\s*class\s+{escaped}\b"),
        ("function", rf"^\s*(?:pub\s+)?(?:async\s+)?fn\s+{escaped}\b"),
        ("function", rf"^\s*func\s+{escaped}\b"),
        ("function", rf"^\s*(?:export\s+)?(?:async\s+)?function\s+{escaped}\b"),
        ("function", rf"^\s*(?:export\s+)?(?:const|let|var)\s+{escaped}\s*=\s*(?:async\s*)?(?:function\b|\()"),
        ("function", rf"^\s*(?:[\w:<>\[\]\*&]+\s+)+{escaped}\s*\([^;]*\)\s*\{{"),
        ("type", rf"^\s*(?:type|interface|struct|enum)\s+{escaped}\b"),
    ]
    return [(kind, re.compile(pattern)) for kind, pattern in patterns]


def _find_symbol_matches(scope: CodeToolScope, symbol: str, *, max_results: int) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    patterns = _symbol_patterns(symbol)
    for file_path in _list_scoped_files(scope, source_only=True):
        lines = _read_blob_lines(scope, file_path)
        for line_number, line_text in enumerate(lines, start=1):
            stripped = line_text.strip()
            if not stripped:
                continue
            for kind, rx in patterns:
                if rx.search(line_text):
                    matches.append(
                        {
                            "symbol": symbol,
                            "kind": kind,
                            "file_path": file_path,
                            "line_number": line_number,
                            "definition_text": line_text,
                        }
                    )
                    break
            if len(matches) >= max_results:
                return matches
    return matches


def _tool_code_search_text(args: dict[str, Any]) -> dict[str, Any]:
    scope = _resolve_scope(args)
    query = str(args.get("query") or "").strip()
    if not query:
        raise ValueError("query is required")
    mode = str(args.get("mode") or "literal").strip().lower()
    if mode not in {"literal", "regex"}:
        raise ValueError("mode must be 'literal' or 'regex'")
    ignore_case = _as_bool(args.get("ignore_case"), default=False)
    max_results = int(args.get("max_results", 20))
    if max_results <= 0:
        raise ValueError("max_results must be > 0")

    flags = re.IGNORECASE if ignore_case else 0
    pattern = re.compile(re.escape(query) if mode == "literal" else query, flags)

    matches: list[dict[str, Any]] = []
    truncated = False
    for file_path in _list_scoped_files(scope, source_only=False):
        lines = _read_blob_lines(scope, file_path)
        for line_number, line_text in enumerate(lines, start=1):
            spans = [
                {
                    "start_col": match.start() + 1,
                    "end_col": match.end(),
                }
                for match in pattern.finditer(line_text)
            ]
            if not spans:
                continue
            matches.append(
                {
                    "file_path": file_path,
                    "line_number": line_number,
                    "line_text": line_text,
                    "match_spans": spans,
                }
            )
            if len(matches) >= max_results:
                truncated = True
                break
        if truncated:
            break

    logger.info("code_search_text repo=%s ref=%s query=%s matches=%d", scope.repo_path, scope.ref, query, len(matches))
    return {
        "query": query,
        "mode": mode,
        "ignore_case": ignore_case,
        "matches": matches[:max_results],
        "match_count": len(matches[:max_results]),
        "truncated": truncated,
        "provenance": _build_provenance(scope),
    }


def _tool_code_read_file_range(args: dict[str, Any]) -> dict[str, Any]:
    scope = _resolve_scope(args)
    file_path = _normalize_repo_rel_path(args.get("file_path"))
    start_line = int(args.get("start_line", 0))
    end_line = int(args.get("end_line", 0))
    if start_line <= 0 or end_line <= 0:
        raise ValueError("start_line and end_line must be positive integers")
    if end_line < start_line:
        raise ValueError("end_line must be >= start_line")
    if not _path_matches_filters(file_path, scope.path_filters):
        raise ValueError(f"file_path is outside the active path_filters: {file_path}")
    if scope.language and not _language_allows_path(file_path, scope.language):
        raise ValueError(f"file_path does not match language filter {scope.language!r}: {file_path}")

    lines = _read_blob_lines(scope, file_path)
    if end_line > len(lines):
        raise ValueError(f"requested range exceeds file length ({len(lines)} lines)")

    selected = [
        {"line_number": line_number, "text": lines[line_number - 1]}
        for line_number in range(start_line, end_line + 1)
    ]
    return {
        "file_path": file_path,
        "start_line": start_line,
        "end_line": end_line,
        "line_count": len(lines),
        "lines": selected,
        "provenance": _build_provenance(scope),
    }


def _tool_code_read_symbol_context(args: dict[str, Any]) -> dict[str, Any]:
    scope = _resolve_scope(args)
    symbol = str(args.get("symbol") or "").strip()
    if not symbol:
        raise ValueError("symbol is required")
    max_results = int(args.get("max_results", 5))
    context_before = int(args.get("context_before", 3))
    context_after = int(args.get("context_after", 6))
    if max_results <= 0 or context_before < 0 or context_after < 0:
        raise ValueError("invalid symbol context limits")

    matches = _find_symbol_matches(scope, symbol, max_results=max_results)
    contextual_matches: list[dict[str, Any]] = []
    for match in matches:
        lines = _read_blob_lines(scope, match["file_path"])
        start_line = max(1, int(match["line_number"]) - context_before)
        end_line = min(len(lines), int(match["line_number"]) + context_after)
        contextual_matches.append(
            {
                **match,
                "context_start_line": start_line,
                "context_end_line": end_line,
                "context_lines": [
                    {"line_number": line_number, "text": lines[line_number - 1]}
                    for line_number in range(start_line, end_line + 1)
                ],
            }
        )

    return {
        "symbol": symbol,
        "matches": contextual_matches,
        "match_count": len(contextual_matches),
        "provenance": _build_provenance(scope),
    }


def _tool_code_check_symbol_exists(args: dict[str, Any]) -> dict[str, Any]:
    scope = _resolve_scope(args)
    symbol = str(args.get("symbol") or "").strip()
    if not symbol:
        raise ValueError("symbol is required")
    max_results = int(args.get("max_results", 10))
    if max_results <= 0:
        raise ValueError("max_results must be > 0")
    matches = _find_symbol_matches(scope, symbol, max_results=max_results)
    return {
        "symbol": symbol,
        "exists": bool(matches),
        "matches": matches,
        "match_count": len(matches),
        "provenance": _build_provenance(scope),
    }


def main() -> None:
    server = StdioMcpServer(name="simple-rla-code-tools", version="0.1")
    shared_properties = {
        "repo": {"type": "string", "description": "Logical repo alias for traceability."},
        "repo_path": {"type": "string", "description": "Absolute path to the local repo/worktree root."},
        "ref": {"type": "string", "description": "Git ref or commit to inspect."},
        "path_filters": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Optional repo-relative glob filters that bound the search scope.",
        },
        "language": {"type": "string", "description": "Optional language hint used to filter candidate files."},
    }
    server.add_tool(Tool(
        name="code_search_text",
        description="Search repo text under a resolved local code scope without inferring conclusions.",
        input_schema={
            "type": "object",
            "properties": {
                **shared_properties,
                "query": {"type": "string"},
                "mode": {"type": "string", "enum": ["literal", "regex"]},
                "ignore_case": {"type": "boolean"},
                "max_results": {"type": "integer", "minimum": 1},
            },
            "required": ["repo_path", "ref", "query"],
        },
        handler=_tool_code_search_text,
    ))
    server.add_tool(Tool(
        name="code_read_file_range",
        description="Read an exact repo-relative file span at a specific ref.",
        input_schema={
            "type": "object",
            "properties": {
                **shared_properties,
                "file_path": {"type": "string"},
                "start_line": {"type": "integer", "minimum": 1},
                "end_line": {"type": "integer", "minimum": 1},
            },
            "required": ["repo_path", "ref", "file_path", "start_line", "end_line"],
        },
        handler=_tool_code_read_file_range,
    ))
    server.add_tool(Tool(
        name="code_read_symbol_context",
        description="Return local definition context for a symbol under a resolved repo scope.",
        input_schema={
            "type": "object",
            "properties": {
                **shared_properties,
                "symbol": {"type": "string"},
                "context_before": {"type": "integer", "minimum": 0},
                "context_after": {"type": "integer", "minimum": 0},
                "max_results": {"type": "integer", "minimum": 1},
            },
            "required": ["repo_path", "ref", "symbol"],
        },
        handler=_tool_code_read_symbol_context,
    ))
    server.add_tool(Tool(
        name="code_check_symbol_exists",
        description="Check whether a symbol definition exists under a resolved repo scope.",
        input_schema={
            "type": "object",
            "properties": {
                **shared_properties,
                "symbol": {"type": "string"},
                "max_results": {"type": "integer", "minimum": 1},
            },
            "required": ["repo_path", "ref", "symbol"],
        },
        handler=_tool_code_check_symbol_exists,
    ))
    server.run_forever()


if __name__ == "__main__":
    main()
