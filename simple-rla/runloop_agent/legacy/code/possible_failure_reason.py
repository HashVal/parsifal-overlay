from __future__ import annotations

import json
from typing import Any

from runloop_agent.workspace import RunWorkspace


ALLOWED_CONFIDENCE = {"high", "medium", "low"}
MAX_REASONS = 3


class PossibleFailureReasonValidationError(ValueError):
    pass


def build_step5_input(
    *,
    jira_key: str,
    jira_context: dict[str, Any] | None,
    signature_pack: dict[str, Any] | None,
    kb_pack: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "case_context": {
            "case_id": jira_key,
            "jira_context": jira_context or {},
        },
        "signature_pack": signature_pack or {},
        "kb_pack": kb_pack or {},
        "task": {
            "goal": "Generate no more than 3 ranked possible failure reasons.",
            "constraints": [
                "Use only the provided Jira context, artifact signatures, and KB grounding.",
                "Each possible failure reason must be a complete mechanism candidate, not a fragment.",
                "Rank by confidence.",
                "Return JSON only.",
            ],
        },
    }


def _require_dict(obj: Any, name: str) -> dict[str, Any]:
    if not isinstance(obj, dict):
        raise PossibleFailureReasonValidationError(f"{name} must be an object")
    return obj


def _require_list(obj: Any, name: str) -> list[Any]:
    if not isinstance(obj, list):
        raise PossibleFailureReasonValidationError(f"{name} must be a list")
    return obj


def _require_str(obj: Any, name: str) -> str:
    if not isinstance(obj, str) or not obj.strip():
        raise PossibleFailureReasonValidationError(f"{name} must be a non-empty string")
    return obj.strip()


def _normalize_str_list(obj: Any, name: str, *, allow_empty: bool = True, max_items: int | None = None) -> list[str]:
    items = _require_list(obj, name)
    out: list[str] = []
    for idx, item in enumerate(items):
        if not isinstance(item, str):
            raise PossibleFailureReasonValidationError(f"{name}[{idx}] must be a string")
        text = item.strip()
        if text:
            out.append(text)
    if not allow_empty and not out:
        raise PossibleFailureReasonValidationError(f"{name} must not be empty")
    if max_items is not None:
        return out[:max_items]
    return out


def _normalize_possible_rate(value: Any) -> float:
    if not isinstance(value, (int, float)):
        raise PossibleFailureReasonValidationError("possible_rate must be a number")
    rate = float(value)
    if rate < 0.0 or rate > 1.0:
        raise PossibleFailureReasonValidationError("possible_rate must be within [0.0, 1.0]")
    return rate


def extract_possible_failure_reason_json_text(raw_text: str) -> str:
    text = (raw_text or "").strip()
    if not text:
        raise PossibleFailureReasonValidationError("invalid JSON: empty model output")

    # Fast path: already valid JSON object text.
    if text.startswith("{") and text.endswith("}"):
        return text

    # Try fenced/tag-wrapped JSON first.
    tag_pairs = [
        ("<POSSIBLE_FAILURE_REASON_JSON>", "</POSSIBLE_FAILURE_REASON_JSON>"),
        ("```json", "```"),
        ("```", "```"),
    ]
    for start_tag, end_tag in tag_pairs:
        start = text.find(start_tag)
        if start == -1:
            continue
        start += len(start_tag)
        end = text.find(end_tag, start)
        if end == -1:
            continue
        candidate = text[start:end].strip()
        if candidate.startswith("{") and candidate.endswith("}"):
            return candidate

    # Fallback: extract the first balanced top-level JSON object.
    start = text.find("{")
    if start == -1:
        raise PossibleFailureReasonValidationError("invalid JSON: no JSON object found in model output")

    depth = 0
    in_string = False
    escape = False
    for idx in range(start, len(text)):
        ch = text[idx]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : idx + 1]

    raise PossibleFailureReasonValidationError("invalid JSON: unterminated JSON object in model output")


def _coerce_json_object(raw_text: str) -> dict[str, Any]:
    extracted = extract_possible_failure_reason_json_text(raw_text)
    try:
        data = json.loads(extracted)
    except Exception as exc:
        raise PossibleFailureReasonValidationError(f"invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise PossibleFailureReasonValidationError("top-level result must be a JSON object")
    return data


def _alias_first(obj: dict[str, Any], keys: list[str], default: Any = None) -> Any:
    for key in keys:
        if key in obj and obj[key] is not None:
            return obj[key]
    return default


def _ensure_listish(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def _normalize_case_context_aliases(case_context: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_id": _alias_first(case_context, ["case_id"]),
        "platforms": _ensure_listish(_alias_first(case_context, ["platforms", "platform"])),
        "modes": _ensure_listish(_alias_first(case_context, ["modes", "mode"])),
        "drivers_involved": _ensure_listish(_alias_first(case_context, ["drivers_involved", "drivers", "driver"])),
    }


def _normalize_reason_aliases(obj: dict[str, Any]) -> dict[str, Any]:
    out = dict(obj)
    if "title" not in out:
        alt = _alias_first(out, ["reason", "name"])
        if alt is not None:
            out["title"] = alt
    if "reason_chain" not in out:
        alt = _alias_first(out, ["reason_chain", "chain", "mechanism", "failure_reason", "description", "reason"])
        if alt is not None:
            out["reason_chain"] = alt
    return out


def validate_possible_failure_reason(raw: str | dict[str, Any]) -> dict[str, Any]:
    data = _coerce_json_object(raw) if isinstance(raw, str) else _require_dict(raw, "top-level")

    case_context = _normalize_case_context_aliases(_require_dict(data.get("case_context"), "case_context"))
    case_id = _require_str(case_context.get("case_id"), "case_context.case_id")
    platforms = _normalize_str_list(case_context.get("platforms", []), "case_context.platforms", max_items=8)
    modes = _normalize_str_list(case_context.get("modes", []), "case_context.modes", max_items=8)
    drivers_involved = _normalize_str_list(case_context.get("drivers_involved", []), "case_context.drivers_involved", max_items=8)

    reasons = _require_list(data.get("possible_failure_reasons"), "possible_failure_reasons")
    if not reasons:
        raise PossibleFailureReasonValidationError("possible_failure_reasons must contain at least 1 item")
    if len(reasons) > MAX_REASONS:
        raise PossibleFailureReasonValidationError("possible_failure_reasons must contain no more than 3 items")

    normalized_reasons: list[dict[str, Any]] = []
    seen_ranks: set[int] = set()
    for idx, item in enumerate(reasons):
        obj = _normalize_reason_aliases(_require_dict(item, f"possible_failure_reasons[{idx}]"))
        rank = obj.get("rank")
        if not isinstance(rank, int):
            raise PossibleFailureReasonValidationError(f"possible_failure_reasons[{idx}].rank must be an integer")
        if rank < 1 or rank > MAX_REASONS:
            raise PossibleFailureReasonValidationError(f"possible_failure_reasons[{idx}].rank must be within [1, 3]")
        if rank in seen_ranks:
            raise PossibleFailureReasonValidationError("possible_failure_reasons ranks must be unique")
        seen_ranks.add(rank)

        confidence = _require_str(obj.get("confidence"), f"possible_failure_reasons[{idx}].confidence").lower()
        if confidence not in ALLOWED_CONFIDENCE:
            raise PossibleFailureReasonValidationError(
                f"possible_failure_reasons[{idx}].confidence must be one of {sorted(ALLOWED_CONFIDENCE)}"
            )

        normalized_reason = {
            "rank": rank,
            "confidence": confidence,
            "possible_rate": _normalize_possible_rate(obj.get("possible_rate")),
            "title": _require_str(obj.get("title"), f"possible_failure_reasons[{idx}].title"),
            "reason_chain": _require_str(obj.get("reason_chain"), f"possible_failure_reasons[{idx}].reason_chain"),
            "factors": _normalize_str_list(obj.get("factors"), f"possible_failure_reasons[{idx}].factors", allow_empty=False, max_items=5),
            "supporting_evidence": _normalize_supporting_evidence(obj.get("supporting_evidence"), idx),
            "unknowns": _normalize_str_list(obj.get("unknowns", []), f"possible_failure_reasons[{idx}].unknowns", max_items=3),
        }
        normalized_reasons.append(normalized_reason)

    normalized_reasons.sort(key=lambda item: item["rank"])
    expected_ranks = list(range(1, len(normalized_reasons) + 1))
    actual_ranks = [item["rank"] for item in normalized_reasons]
    if actual_ranks != expected_ranks:
        raise PossibleFailureReasonValidationError(
            f"possible_failure_reasons ranks must be contiguous starting at 1; got {actual_ranks}"
        )

    selection_hint = _require_dict(data.get("selection_hint"), "selection_hint")
    primary_rank = selection_hint.get("primary_rank")
    if primary_rank != 1:
        raise PossibleFailureReasonValidationError("selection_hint.primary_rank must be 1")
    debug_steps_should_focus_on = selection_hint.get("debug_steps_should_focus_on")
    if debug_steps_should_focus_on != 1:
        raise PossibleFailureReasonValidationError("selection_hint.debug_steps_should_focus_on must be 1")
    include_alternatives_if_primary_is_weak = selection_hint.get("include_alternatives_if_primary_is_weak")
    if not isinstance(include_alternatives_if_primary_is_weak, bool):
        raise PossibleFailureReasonValidationError(
            "selection_hint.include_alternatives_if_primary_is_weak must be a boolean"
        )

    return {
        "case_context": {
            "case_id": case_id,
            "platforms": platforms,
            "modes": modes,
            "drivers_involved": drivers_involved,
        },
        "possible_failure_reasons": normalized_reasons,
        "selection_hint": {
            "primary_rank": 1,
            "debug_steps_should_focus_on": 1,
            "include_alternatives_if_primary_is_weak": include_alternatives_if_primary_is_weak,
        },
    }


def _normalize_supporting_evidence(value: Any, idx: int) -> dict[str, list[str]]:
    obj = _require_dict(value, f"possible_failure_reasons[{idx}].supporting_evidence")
    return {
        "jira": _normalize_str_list(obj.get("jira", []), f"possible_failure_reasons[{idx}].supporting_evidence.jira", max_items=2),
        "signature": _normalize_str_list(obj.get("signature", []), f"possible_failure_reasons[{idx}].supporting_evidence.signature", max_items=2),
        "kb": _normalize_str_list(obj.get("kb", []), f"possible_failure_reasons[{idx}].supporting_evidence.kb", max_items=2),
    }


def compact_possible_failure_reason(data: dict[str, Any]) -> dict[str, Any]:
    normalized = validate_possible_failure_reason(data)
    reasons = normalized["possible_failure_reasons"]
    primary = reasons[0]
    alternatives = reasons[1:]
    key_support = []
    for bucket in ("jira", "signature", "kb"):
        values = primary["supporting_evidence"].get(bucket, [])
        if values:
            key_support.append(values[0])
    key_support = key_support[:3]

    return {
        "primary_reason": {
            "title": primary["title"],
            "confidence": primary["confidence"],
            "possible_rate": primary["possible_rate"],
            "reason_chain": primary["reason_chain"],
            "factors": primary["factors"][:4],
            "key_support": key_support,
            "main_gaps": primary["unknowns"][:3],
        },
        "alternatives": [
            {
                "title": item["title"],
                "confidence": item["confidence"],
                "possible_rate": item["possible_rate"],
            }
            for item in alternatives[:2]
        ],
        "debug_focus": {
            "focus_order": [
                "device evidence",
                "probe/binding/resource path",
                "code path / caller invariant",
            ],
            "avoid": [
                "treating crash site as root-cause origin",
                "promoting peripheral errors into top debug steps",
            ],
        },
    }


def render_possible_failure_reason_markdown(data: dict[str, Any]) -> str:
    normalized = validate_possible_failure_reason(data)
    lines: list[str] = []
    lines.append("# Possible Failure Reasons")
    lines.append("")
    lines.append("## Case Context")
    lines.append("")
    ctx = normalized["case_context"]
    lines.append(f"- Case ID: `{ctx['case_id']}`")
    lines.append(f"- Platforms: {', '.join(ctx['platforms']) if ctx['platforms'] else '(unknown)'}")
    lines.append(f"- Modes: {', '.join(ctx['modes']) if ctx['modes'] else '(unknown)'}")
    lines.append(f"- Drivers involved: {', '.join(ctx['drivers_involved']) if ctx['drivers_involved'] else '(unknown)'}")
    lines.append("")
    lines.append("## Ranked Reasons")
    lines.append("")

    for item in normalized["possible_failure_reasons"]:
        lines.append(f"### Rank {item['rank']}: {item['title']}")
        lines.append("")
        lines.append(f"- Confidence: `{item['confidence']}`")
        lines.append(f"- Possible rate: `{item['possible_rate']:.3f}`")
        lines.append(f"- Reason chain: {item['reason_chain']}")
        lines.append("- Factors:")
        for factor in item["factors"]:
            lines.append(f"  - {factor}")
        lines.append("- Supporting evidence:")
        lines.append("  - Jira:")
        for evidence in item["supporting_evidence"]["jira"]:
            lines.append(f"    - {evidence}")
        lines.append("  - Signature:")
        for evidence in item["supporting_evidence"]["signature"]:
            lines.append(f"    - {evidence}")
        lines.append("  - KB:")
        for evidence in item["supporting_evidence"]["kb"]:
            lines.append(f"    - {evidence}")
        lines.append("- Unknowns:")
        if item["unknowns"]:
            for unknown in item["unknowns"]:
                lines.append(f"  - {unknown}")
        else:
            lines.append("  - (none)")
        lines.append("")

    sel = normalized["selection_hint"]
    lines.append("## Selection Hint")
    lines.append("")
    lines.append(f"- Primary rank: `{sel['primary_rank']}`")
    lines.append(f"- DEBUG_STEPS should focus on: `{sel['debug_steps_should_focus_on']}`")
    lines.append(f"- Include alternatives if primary is weak: `{str(sel['include_alternatives_if_primary_is_weak']).lower()}`")
    lines.append("")
    return "\n".join(lines)


def write_possible_failure_reason_artifacts(
    ws: RunWorkspace,
    data: dict[str, Any],
    compact_data: dict[str, Any],
) -> dict[str, str]:
    ws.root.mkdir(parents=True, exist_ok=True)
    full_path = ws.root / "step5_possible_failure_reason.json"
    compact_path = ws.root / "step5_possible_failure_reason.compact.json"
    md_path = ws.root / "step5_possible_failure_reason.md"
    full_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    compact_path.write_text(json.dumps(compact_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_possible_failure_reason_markdown(data), encoding="utf-8")
    return {
        "json": str(full_path),
        "compact_json": str(compact_path),
        "markdown": str(md_path),
    }
