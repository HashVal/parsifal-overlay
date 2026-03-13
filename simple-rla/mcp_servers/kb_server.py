#!/usr/bin/env python3
"""Local KB MCP server for simple-rla.

MVP goals:
- YAML-first source of truth under simple-rla/knowledge_base/
- zero extra runtime deps
- tools: kb_get, kb_search, kb_ground
- aggregation yes, over-reasoning no

Note:
This first version uses a lightweight line-oriented YAML subset parser tailored to
our current example files. It is intentionally conservative and should be evolved
or replaced by a proper YAML parser when the runtime environment allows it.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any

from .stdio_jsonrpc_server import StdioMcpServer, Tool


logger = logging.getLogger("simple_rla.kb")

_KIND_DIRS = {
    "issue_pattern": "issue_patterns",
    "rca": "rca",
    "platform_note": "platform_notes",
    "code_note": "code_notes",
    "playbook": "playbooks",
    "workaround": "workarounds",
}

_OUTPUT_KIND_BUCKETS = {
    "issue_pattern": "issue_patterns",
    "rca": "rcas",
    "platform_note": "platform_notes",
    "code_note": "code_notes",
    "playbook": "playbooks",
    "workaround": "workarounds",
}

_PLATFORM_TAXONOMY = {
    "bmg": ["generic_x86_platforms"],
    "mtl": ["generic_x86_platforms"],
    "arl": ["generic_x86_platforms"],
    "lnl": ["generic_x86_platforms"],
    "ptl": ["generic_x86_platforms"],
    "rpl": ["generic_x86_platforms"],
    "adl": ["generic_x86_platforms"],
    "tgl": ["generic_x86_platforms"],
}


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _kb_root() -> Path:
    return _project_root() / "knowledge_base"


def _line_indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _strip_comment(line: str) -> str:
    return line.rstrip("\n")


def _parse_scalar(value: str) -> Any:
    value = value.strip()
    if value == "null":
        return None
    if value == "true":
        return True
    if value == "false":
        return False
    if value.startswith('"') and value.endswith('"') and len(value) >= 2:
        return value[1:-1]
    if value.startswith("'") and value.endswith("'") and len(value) >= 2:
        return value[1:-1]
    if re.fullmatch(r"-?\d+", value):
        try:
            return int(value)
        except ValueError:
            return value
    if re.fullmatch(r"-?\d+\.\d+", value):
        try:
            return float(value)
        except ValueError:
            return value
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        parts = [p.strip() for p in inner.split(",")]
        return [_parse_scalar(p) for p in parts]
    return value


def _next_significant(lines: list[str], idx: int) -> tuple[int, str] | tuple[None, None]:
    n = len(lines)
    j = idx
    while j < n:
        raw = _strip_comment(lines[j])
        if raw.strip() and not raw.lstrip().startswith("#"):
            return j, raw
        j += 1
    return None, None


def _parse_block(lines: list[str], start: int, indent: int) -> tuple[Any, int]:
    idx, first = _next_significant(lines, start)
    if idx is None:
        return {}, len(lines)
    if _line_indent(first) < indent:
        return {}, idx
    if first.strip().startswith("- "):
        return _parse_list(lines, idx, indent)
    return _parse_mapping(lines, idx, indent)


def _parse_list(lines: list[str], start: int, indent: int) -> tuple[list[Any], int]:
    items: list[Any] = []
    i = start
    n = len(lines)
    while i < n:
        raw = _strip_comment(lines[i])
        if not raw.strip() or raw.lstrip().startswith("#"):
            i += 1
            continue
        cur_indent = _line_indent(raw)
        if cur_indent < indent:
            break
        stripped = raw.strip()
        if not stripped.startswith("- "):
            break
        item_text = stripped[2:].strip()
        if not item_text:
            item, ni = _parse_block(lines, i + 1, indent + 2)
            items.append(item)
            i = ni
            continue
        if ":" in item_text and not item_text.startswith(('"', "'")):
            key, rest = item_text.split(":", 1)
            obj: dict[str, Any] = {}
            key = key.strip()
            rest = rest.strip()
            if rest:
                obj[key] = _parse_scalar(rest)
                i += 1
            else:
                val, ni = _parse_block(lines, i + 1, indent + 4)
                obj[key] = val
                i = ni
            while i < n:
                peek = _strip_comment(lines[i])
                if not peek.strip() or peek.lstrip().startswith("#"):
                    i += 1
                    continue
                pindent = _line_indent(peek)
                if pindent < indent + 2:
                    break
                pstrip = peek.strip()
                if pindent == indent and pstrip.startswith("- "):
                    break
                if pindent == indent + 2 and ":" in pstrip and not pstrip.startswith("- "):
                    k, rest2 = pstrip.split(":", 1)
                    k = k.strip()
                    rest2 = rest2.strip()
                    if rest2 in ("|", ">"):
                        text, ni = _parse_multiline(lines, i + 1, indent + 4, folded=(rest2 == ">"))
                        obj[k] = text
                        i = ni
                    elif rest2:
                        obj[k] = _parse_scalar(rest2)
                        i += 1
                    else:
                        val2, ni = _parse_block(lines, i + 1, indent + 4)
                        obj[k] = val2
                        i = ni
                    continue
                break
            items.append(obj)
            continue
        items.append(_parse_scalar(item_text))
        i += 1
    return items, i


def _parse_multiline(lines: list[str], start: int, indent: int, *, folded: bool) -> tuple[str, int]:
    out: list[str] = []
    i = start
    n = len(lines)
    while i < n:
        raw = _strip_comment(lines[i])
        if not raw.strip():
            out.append("")
            i += 1
            continue
        cur_indent = _line_indent(raw)
        if cur_indent < indent:
            break
        out.append(raw[indent:])
        i += 1
    if folded:
        text = " ".join(part for part in out if part != "").strip()
    else:
        text = "\n".join(out).rstrip()
    return text, i


def _parse_mapping(lines: list[str], start: int, indent: int) -> tuple[dict[str, Any], int]:
    data: dict[str, Any] = {}
    i = start
    n = len(lines)
    while i < n:
        raw = _strip_comment(lines[i])
        if not raw.strip() or raw.lstrip().startswith("#"):
            i += 1
            continue
        cur_indent = _line_indent(raw)
        if cur_indent < indent:
            break
        if cur_indent > indent:
            break
        stripped = raw.strip()
        if ":" not in stripped:
            i += 1
            continue
        key, rest = stripped.split(":", 1)
        key = key.strip()
        rest = rest.strip()
        if rest in ("|", ">"):
            text, ni = _parse_multiline(lines, i + 1, indent + 2, folded=(rest == ">"))
            data[key] = text
            i = ni
        elif rest:
            data[key] = _parse_scalar(rest)
            i += 1
        else:
            val, ni = _parse_block(lines, i + 1, indent + 2)
            data[key] = val
            i = ni
    return data, i


def _parse_yaml_subset(text: str) -> dict[str, Any]:
    lines = text.splitlines()
    data, _ = _parse_mapping(lines, 0, 0)
    if not isinstance(data, dict):
        raise RuntimeError("top-level YAML content is not a mapping")
    return data


def _load_kb_objects() -> list[dict[str, Any]]:
    root = _kb_root()
    objects: list[dict[str, Any]] = []
    if not root.exists():
        return objects
    for kind, rel_dir in _KIND_DIRS.items():
        d = root / rel_dir
        if not d.exists():
            continue
        for path in sorted(d.glob("*.yaml")):
            obj = _parse_yaml_subset(path.read_text(encoding="utf-8"))
            obj["__path"] = str(path.relative_to(_project_root()))
            obj.setdefault("kind", kind)
            if obj.get("kind") != kind:
                logger.warning("kb.kind_mismatch path=%s declared=%s expected=%s", path, obj.get("kind"), kind)
            for field in ("id", "kind", "title", "summary"):
                if not obj.get(field):
                    raise RuntimeError(f"KB object missing required field {field}: {path}")
            objects.append(obj)
    logger.info("kb.loaded root=%s objects=%s", root, len(objects))
    return objects


_KB_OBJECTS = _load_kb_objects()
_KB_BY_ID = {obj["id"]: obj for obj in _KB_OBJECTS}


def _lower_values(values: list[Any]) -> set[str]:
    out: set[str] = set()
    for v in values or []:
        if isinstance(v, str) and v.strip():
            out.add(v.strip().lower())
    return out


def _expand_platforms(values: list[Any]) -> set[str]:
    base = _lower_values(values)
    expanded = set(base)
    for val in list(base):
        expanded.update(_PLATFORM_TAXONOMY.get(val, []))
    return expanded


def _text_blob(obj: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("title", "summary", "content"):
        v = obj.get(key)
        if isinstance(v, str):
            parts.append(v)
    for key in ("tags", "platforms", "subsystems", "modes", "symptoms"):
        v = obj.get(key)
        if isinstance(v, list):
            parts.extend(str(x) for x in v)
    sigs = obj.get("signals")
    if isinstance(sigs, list):
        for sig in sigs:
            if isinstance(sig, dict):
                parts.append(str(sig.get("type", "")))
                parts.append(str(sig.get("value", "")))
    return "\n".join(parts).lower()


def _object_refs(obj: dict[str, Any]) -> list[dict[str, Any]]:
    refs = obj.get("refs")
    if not isinstance(refs, list):
        return []
    out: list[dict[str, Any]] = []
    for ref in refs:
        if isinstance(ref, dict) and ref.get("type") and ref.get("value"):
            out.append({"type": str(ref["type"]), "value": str(ref["value"])})
    return out[:4]


def _matched_signals(obj: dict[str, Any], signals: list[dict[str, str]]) -> list[str]:
    blob = _text_blob(obj)
    matched: list[str] = []
    for sig in signals:
        val = str(sig.get("value") or "").strip()
        if not val:
            continue
        if val.lower() in blob:
            matched.append(val)
    return matched[:6]


def _score_object(obj: dict[str, Any], *, query_terms: list[str], kinds: set[str], platforms: set[str], subsystems: set[str], modes: set[str], signals: list[dict[str, str]]) -> tuple[float, list[str]]:
    score = 0.0
    if kinds and str(obj.get("kind")) not in kinds:
        return 0.0, []

    obj_platforms = _expand_platforms(obj.get("platforms") or [])
    obj_subsystems = _lower_values(obj.get("subsystems") or [])
    obj_modes = _lower_values(obj.get("modes") or [])

    score += 4.0 * len(platforms & obj_platforms)
    score += 3.0 * len(subsystems & obj_subsystems)
    score += 2.0 * len(modes & obj_modes)

    blob = _text_blob(obj)
    for term in query_terms:
        if term and term in blob:
            score += 1.5

    matched = _matched_signals(obj, signals)
    score += 5.0 * len(matched)

    title = str(obj.get("title") or "").lower()
    for term in query_terms:
        if term and term in title:
            score += 2.0

    return score, matched


def _make_hit(obj: dict[str, Any], matched_signals: list[str], score: float, *, include_snippets: bool = True, include_score: bool = True, include_refs: bool = True) -> dict[str, Any]:
    hit = {
        "id": obj["id"],
        "kind": obj["kind"],
        "title": obj["title"],
        "matched_signals": matched_signals,
        "summary": str(obj.get("summary") or ""),
    }
    if include_score:
        hit["score"] = round(score, 3)
    if include_snippets:
        snippets = []
        content = str(obj.get("content") or "").strip()
        if content:
            first = content.splitlines()[0].strip()
            if first:
                snippets.append(first[:220])
        hit["snippets"] = snippets[:2]
    if include_refs:
        hit["refs"] = _object_refs(obj)
    return hit


def _kb_get(args: dict) -> dict:
    obj_id = str(args.get("id") or "").strip()
    if not obj_id:
        raise ValueError("id is required")
    obj = _KB_BY_ID.get(obj_id)
    if obj is None:
        raise RuntimeError(f"kb object not found: {obj_id}")
    out = {k: v for k, v in obj.items() if not k.startswith("__")}
    out["source_path"] = obj.get("__path")
    logger.info("kb.response tool=kb_get id=%s kind=%s", obj_id, out.get("kind"))
    return out


def _kb_search(args: dict) -> dict:
    query = str(args.get("query") or "").strip()
    kinds = {str(x) for x in (args.get("kinds") or []) if str(x).strip()}
    platforms = _expand_platforms(args.get("platforms") or [])
    subsystems = _lower_values(args.get("subsystems") or [])
    modes = _lower_values(args.get("modes") or [])
    limit = int(args.get("limit", 8))
    include_snippets = bool(args.get("include_snippets", True))
    include_score = bool(args.get("include_score", True))
    include_refs = bool(args.get("include_refs", True))
    query_terms = [t.lower() for t in re.split(r"\s+", query) if t.strip()]
    pseudo_signals = [{"type": "query", "value": t} for t in query_terms]

    scored: list[tuple[float, dict[str, Any], list[str]]] = []
    for obj in _KB_OBJECTS:
        score, matched = _score_object(
            obj,
            query_terms=query_terms,
            kinds=kinds,
            platforms=platforms,
            subsystems=subsystems,
            modes=modes,
            signals=pseudo_signals,
        )
        if score <= 0:
            continue
        scored.append((score, obj, matched))
    scored.sort(key=lambda x: (-x[0], x[1]["id"]))
    hits = [_make_hit(obj, matched, score, include_snippets=include_snippets, include_score=include_score, include_refs=include_refs) for score, obj, matched in scored[:limit]]
    logger.info("kb.response tool=kb_search query=%s hits=%s", query, len(hits))
    return {"query": query, "count": len(hits), "hits": hits}


def _focus_areas(hits_by_bucket: dict[str, list[dict[str, Any]]]) -> list[str]:
    focus: list[str] = []
    for bucket in ("issue_patterns", "code_notes", "platform_notes"):
        for hit in hits_by_bucket.get(bucket, [])[:1]:
            summary = str(hit.get("summary") or "").strip()
            if summary:
                focus.append(summary[:140])
    return focus[:4]


def _open_questions(context: dict[str, Any], signals: list[dict[str, str]], hits_by_bucket: dict[str, list[dict[str, Any]]], coverage: dict[str, Any]) -> list[str]:
    questions: list[str] = []
    sig_values = [str(s.get("value") or "") for s in signals]
    if any("drm_gem_private_object_init" in s for s in sig_values):
        questions.append("Is the object state already invalid before drm_gem_private_object_init is called?")
    if len(context.get("modes") or []) > 1:
        questions.append("What shared initialization path is common across the reported modes?")
    if coverage.get("missing_kinds"):
        questions.append("Does the KB have a coverage gap for this domain that limits confidence?")
    return questions[:4]


def _recommend_next_reads(hits_by_bucket: dict[str, list[dict[str, Any]]]) -> list[str]:
    picks: list[str] = []
    for bucket in ("issue_patterns", "rcas", "code_notes", "platform_notes"):
        for hit in hits_by_bucket.get(bucket, [])[:1]:
            picks.append(hit["id"])
    return picks[:4]


def _kb_ground(args: dict) -> dict:
    context = args.get("context") or {}
    signals = args.get("signals") or []
    hints = args.get("hints") or {}
    limits = args.get("limits") or {}
    if not isinstance(context, dict):
        raise ValueError("context must be an object")
    if not isinstance(signals, list) or not signals:
        raise ValueError("signals must be a non-empty array")

    preferred_kinds = [str(x) for x in (hints.get("preferred_kinds") or []) if str(x).strip()]
    include_kinds = [str(x) for x in (limits.get("include_kinds") or preferred_kinds or list(_KIND_DIRS.keys()))]
    include_kinds_set = set(include_kinds)
    exclude_ids = {str(x) for x in (hints.get("exclude_ids") or []) if str(x).strip()}

    max_total_hits = int(limits.get("max_total_hits", 6))
    max_hits_per_kind = int(limits.get("max_hits_per_kind", 2))
    include_snippets = bool(limits.get("include_snippets", True))

    query_terms: list[str] = []
    for field in ("title", "summary"):
        val = context.get(field)
        if isinstance(val, str):
            query_terms.extend(t.lower() for t in re.split(r"\s+", val) if t.strip())
    query_terms.extend(str(sig.get("value") or "").lower() for sig in signals if str(sig.get("value") or "").strip())

    platforms = _expand_platforms(context.get("platforms") or [])
    subsystems = _lower_values(context.get("subsystems") or [])
    modes = _lower_values(context.get("modes") or [])

    candidates_by_kind: dict[str, list[tuple[float, dict[str, Any], list[str]]]] = {k: [] for k in _KIND_DIRS}
    min_score = 3.0
    for obj in _KB_OBJECTS:
        if obj["id"] in exclude_ids:
            continue
        score, matched = _score_object(
            obj,
            query_terms=query_terms,
            kinds=include_kinds_set,
            platforms=platforms,
            subsystems=subsystems,
            modes=modes,
            signals=signals,
        )
        if score < min_score:
            continue
        candidates_by_kind[obj["kind"]].append((score, obj, matched))

    for kind in candidates_by_kind:
        candidates_by_kind[kind].sort(key=lambda x: (-x[0], x[1]["id"]))

    selected: list[tuple[str, float, dict[str, Any], list[str]]] = []

    def take_one(kind: str) -> None:
        if len(selected) >= max_total_hits:
            return
        bucket = candidates_by_kind.get(kind, [])
        already = sum(1 for k, *_ in selected if k == kind)
        if already >= max_hits_per_kind:
            return
        if not bucket:
            return
        score, obj, matched = bucket.pop(0)
        selected.append((kind, score, obj, matched))

    # Tier 1
    for kind in ("issue_pattern", "rca"):
        take_one(kind)

    # Dynamic bias
    signal_types = {str(sig.get("type") or "") for sig in signals}
    if "function" in signal_types or "file" in signal_types:
        take_one("code_note")
    if len(modes) > 1 or platforms:
        take_one("platform_note")

    # Fill remaining by strongest candidates, respecting per-kind caps
    leftovers: list[tuple[str, float, dict[str, Any], list[str]]] = []
    for kind, bucket in candidates_by_kind.items():
        for score, obj, matched in bucket:
            leftovers.append((kind, score, obj, matched))
    leftovers.sort(key=lambda x: (-x[1], x[2]["id"]))
    for kind, score, obj, matched in leftovers:
        if len(selected) >= max_total_hits:
            break
        if sum(1 for k, *_ in selected if k == kind) >= max_hits_per_kind:
            continue
        if any(obj["id"] == s_obj["id"] for _, _, s_obj, _ in selected):
            continue
        selected.append((kind, score, obj, matched))

    hits_by_bucket: dict[str, list[dict[str, Any]]] = {bucket: [] for bucket in _OUTPUT_KIND_BUCKETS.values()}
    matched_kinds: list[str] = []
    for kind, score, obj, matched in selected:
        bucket = _OUTPUT_KIND_BUCKETS[kind]
        hit = _make_hit(obj, matched, score, include_snippets=include_snippets, include_score=True, include_refs=True)
        hits_by_bucket[bucket].append(hit)
        if kind not in matched_kinds:
            matched_kinds.append(kind)

    missing_kinds = [kind for kind in include_kinds if kind not in matched_kinds]
    coverage = {
        "matched_kinds": matched_kinds,
        "missing_kinds": missing_kinds,
        "notes": [],
    }
    for kind in missing_kinds[:4]:
        coverage["notes"].append(f"No sufficiently relevant {kind} matched current signals/context.")

    out = {
        "query_context": {
            "case_id": context.get("case_id"),
            "platforms": context.get("platforms", []),
            "subsystems": context.get("subsystems", []),
            "modes": context.get("modes", []),
            "signals": signals,
        },
        "matched_objects": hits_by_bucket,
        "focus_areas": _focus_areas(hits_by_bucket),
        "open_questions": _open_questions(context, signals, hits_by_bucket, coverage),
        "recommended_next_reads": _recommend_next_reads(hits_by_bucket),
        "coverage": coverage,
    }
    logger.info("kb.response tool=kb_ground case=%s matched=%s missing=%s", context.get("case_id"), len(selected), len(missing_kinds))
    return out


def main() -> None:
    logging.basicConfig(
        level=getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    server = StdioMcpServer(name="kb-tools", version="0.1")
    server.add_tool(Tool(
        name="kb_get",
        description="Get a single KB object by id from the local knowledge base.",
        input_schema={
            "type": "object",
            "properties": {
                "id": {"type": "string"},
            },
            "required": ["id"],
        },
        handler=_kb_get,
    ))
    server.add_tool(Tool(
        name="kb_search",
        description="Search the local knowledge base using text query plus optional structured filters.",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "kinds": {"type": "array", "items": {"type": "string"}},
                "platforms": {"type": "array", "items": {"type": "string"}},
                "subsystems": {"type": "array", "items": {"type": "string"}},
                "modes": {"type": "array", "items": {"type": "string"}},
                "limit": {"type": "integer", "minimum": 1},
                "include_snippets": {"type": "boolean"},
                "include_score": {"type": "boolean"},
                "include_refs": {"type": "boolean"},
            },
            "required": ["query"],
        },
        handler=_kb_search,
    ))
    server.add_tool(Tool(
        name="kb_ground",
        description="Build a lightweight KB grounding package for a case using structured context and signals.",
        input_schema={
            "type": "object",
            "properties": {
                "context": {"type": "object"},
                "signals": {"type": "array", "items": {"type": "object"}},
                "hints": {"type": "object"},
                "limits": {"type": "object"},
            },
            "required": ["signals"],
        },
        handler=_kb_ground,
    ))
    server.run_forever()


if __name__ == "__main__":
    main()
