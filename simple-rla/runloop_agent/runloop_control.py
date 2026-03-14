from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


PHASE_CASE_IDENTIFICATION = "case_identification"
PHASE_EVIDENCE_COLLECTION = "evidence_collection"
PHASE_ARTIFACT_INSPECTION = "artifact_inspection"
PHASE_KB_GROUNDING = "kb_grounding"
PHASE_DRAFT_DEBUG_STEPS = "draft_debug_steps"
PHASE_DONE = "done"

PHASE_ORDER = [
    PHASE_CASE_IDENTIFICATION,
    PHASE_EVIDENCE_COLLECTION,
    PHASE_ARTIFACT_INSPECTION,
    PHASE_KB_GROUNDING,
    PHASE_DRAFT_DEBUG_STEPS,
    PHASE_DONE,
]

PHASE_TOOL_BUDGETS: dict[str, dict[str, int]] = {
    PHASE_CASE_IDENTIFICATION: {"jira": 2, "files": 0, "kb": 0},
    PHASE_EVIDENCE_COLLECTION: {"jira": 4, "files": 0, "kb": 0},
    PHASE_ARTIFACT_INSPECTION: {"jira": 1, "files": 4, "kb": 0},
    PHASE_KB_GROUNDING: {"jira": 0, "files": 1, "kb": 2},
    PHASE_DRAFT_DEBUG_STEPS: {"jira": 0, "files": 1, "kb": 1},
    PHASE_DONE: {"jira": 0, "files": 0, "kb": 0},
}


@dataclass
class PhaseState:
    phase: str = PHASE_CASE_IDENTIFICATION
    phase_index: int = 1
    entered_step: int = 1
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ToolCallRecord:
    phase: str
    step: int
    family: str
    tool_name: str
    normalized_args: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class GuardResult:
    allowed: bool
    reason: str = ""
    message: str = ""


def tool_family(tool_name: str) -> str:
    name = (tool_name or "").lower()
    if name.startswith("jira__") or name.startswith("jira_"):
        return "jira"
    if name.startswith("files__") or name.startswith("file_") or name.startswith("log_"):
        return "files"
    if name.startswith("kb__") or name.startswith("kb_"):
        return "kb"
    return "other"


def normalize_tool_args(tool_name: str, args: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    name = (tool_name or "").lower()
    core_keys_map = {
        "jira__jira_get": ["key"],
        "jira__jira_list_attachments": ["key"],
        "jira__jira_fetch_attachment": ["key", "attachment_id"],
        "kb__kb_get": ["id"],
        "kb__kb_search": ["query", "platforms", "subsystems", "modes"],
        "kb__kb_ground": ["context", "signals", "hints", "limits"],
        "files__file_head": ["path", "lines"],
        "files__file_tail": ["path", "lines"],
        "files__file_read_range": ["path", "start_line", "end_line"],
        "files__file_grep": ["path", "pattern", "ignore_case", "context_before", "context_after"],
        "files__log_extract_signatures": ["path", "profile"],
        "files__log_compare": ["left_path", "right_path", "profile"],
    }
    keys = core_keys_map.get(name)
    if keys is None:
        keys = sorted(args.keys())
    out: list[tuple[str, str]] = []
    for key in keys:
        if key in args:
            try:
                val = json.dumps(args[key], sort_keys=True, ensure_ascii=False)
            except TypeError:
                val = repr(args[key])
            out.append((key, val))
    return tuple(out)


def check_budget(phase: str, phase_usage: dict[str, int], family: str) -> GuardResult:
    if family == "other":
        return GuardResult(True)
    budget = PHASE_TOOL_BUDGETS.get(phase, {}).get(family, 0)
    used = phase_usage.get(family, 0)
    if used >= budget:
        return GuardResult(
            False,
            reason="budget_exhausted",
            message=(
                f"tool budget guard:\n"
                f"Tool family '{family}' budget is exhausted in phase '{phase}'.\n"
                f"Move forward with current evidence or record unknowns."
            ),
        )
    return GuardResult(True)


def check_repeat_guard(
    phase: str,
    step: int,
    family: str,
    tool_name: str,
    args: dict[str, Any],
    history: list[ToolCallRecord],
) -> GuardResult:
    if family == "other":
        return GuardResult(True)
    normalized = normalize_tool_args(tool_name, args)
    current = ToolCallRecord(phase=phase, step=step, family=family, tool_name=tool_name, normalized_args=normalized)

    for prev in reversed(history):
        if prev.phase != current.phase:
            continue
        if prev.tool_name == current.tool_name and prev.normalized_args == current.normalized_args:
            return GuardResult(
                False,
                reason="exact_repeat",
                message=(
                    "anti-repeat guard:\n"
                    "Repeated tool call blocked in current phase.\n"
                    "Reason: the same tool with equivalent arguments was already used.\n"
                    "Use the existing evidence, perform a more targeted follow-up, or record unknowns."
                ),
            )
        if prev.tool_name == current.tool_name:
            prev_map = dict(prev.normalized_args)
            cur_map = dict(current.normalized_args)
            same_target_keys = ["key", "id", "path", "left_path", "right_path", "query"]
            for target_key in same_target_keys:
                if target_key in prev_map and target_key in cur_map and prev_map[target_key] == cur_map[target_key]:
                    if current.tool_name in {
                        "jira__jira_get",
                        "jira__jira_list_attachments",
                        "kb__kb_get",
                        "kb__kb_search",
                        "files__file_head",
                        "files__file_tail",
                        "files__log_extract_signatures",
                    }:
                        return GuardResult(
                            False,
                            reason="near_repeat",
                            message=(
                                "anti-repeat guard:\n"
                                "Repeated broad read blocked in current phase.\n"
                                "Reason: a near-equivalent read was already performed on the same target.\n"
                                "Use the existing evidence, perform a more targeted follow-up, or record unknowns."
                            ),
                        )
    return GuardResult(True)


def record_tool_use(phase_usage: dict[str, int], family: str) -> None:
    if family == "other":
        return
    phase_usage[family] = phase_usage.get(family, 0) + 1


def record_call(
    history: list[ToolCallRecord],
    phase: str,
    step: int,
    family: str,
    tool_name: str,
    args: dict[str, Any],
) -> None:
    history.append(
        ToolCallRecord(
            phase=phase,
            step=step,
            family=family,
            tool_name=tool_name,
            normalized_args=normalize_tool_args(tool_name, args),
        )
    )


def advance_phase(
    phase_state: PhaseState,
    *,
    used_jira: bool,
    used_files: bool,
    used_kb: bool,
    step: int,
) -> tuple[PhaseState, bool]:
    cur = phase_state.phase
    nxt = cur
    if cur == PHASE_CASE_IDENTIFICATION and used_jira:
        nxt = PHASE_EVIDENCE_COLLECTION
    elif cur == PHASE_EVIDENCE_COLLECTION and used_files:
        nxt = PHASE_ARTIFACT_INSPECTION
    elif cur == PHASE_ARTIFACT_INSPECTION and used_kb:
        nxt = PHASE_KB_GROUNDING
    elif cur == PHASE_KB_GROUNDING:
        nxt = PHASE_DRAFT_DEBUG_STEPS
    if nxt == cur:
        return phase_state, False
    return PhaseState(phase=nxt, phase_index=PHASE_ORDER.index(nxt) + 1, entered_step=step, notes=list(phase_state.notes)), True


def should_force_draft(
    phase_state: PhaseState,
    phase_usage: dict[str, int],
    step: int,
    max_steps: int,
    *,
    seen_files: bool,
    seen_kb: bool,
    seen_failure_signal: bool,
) -> bool:
    if phase_state.phase in {PHASE_DRAFT_DEBUG_STEPS, PHASE_DONE}:
        return False
    if step >= max_steps - 2:
        return True
    budgets = PHASE_TOOL_BUDGETS.get(phase_state.phase, {})
    for family, budget in budgets.items():
        if budget > 0 and phase_usage.get(family, 0) >= budget:
            return True
    if seen_files and (seen_kb or seen_failure_signal):
        return True
    return False


FORCED_DRAFT_NUDGE = (
    "You now have enough evidence for a minimal useful provisional DEBUG_STEPS draft.\n"
    "Do not perform further broad evidence collection.\n"
    "Produce the draft now with:\n"
    "- problem framing\n"
    "- most likely direction\n"
    "- 3-5 concrete debug steps\n"
    "- unknowns\n"
    "- why this path first"
)
