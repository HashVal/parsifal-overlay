from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


PHASE_CASE_IDENTIFICATION = "case_identification"
PHASE_EVIDENCE_COLLECTION = "evidence_collection"
PHASE_ARTIFACT_INSPECTION = "artifact_inspection"
PHASE_KB_GROUNDING = "kb_grounding"
PHASE_POSSIBLE_FAILURE_REASON = "possible_failure_reason"
PHASE_DRAFT_DEBUG_STEPS = "draft_debug_steps"
PHASE_DONE = "done"

PHASE_ORDER = [
    PHASE_CASE_IDENTIFICATION,
    PHASE_EVIDENCE_COLLECTION,
    PHASE_ARTIFACT_INSPECTION,
    PHASE_KB_GROUNDING,
    PHASE_POSSIBLE_FAILURE_REASON,
    PHASE_DRAFT_DEBUG_STEPS,
    PHASE_DONE,
]

PHASE_TOOL_BUDGETS: dict[str, dict[str, int]] = {
    PHASE_CASE_IDENTIFICATION: {"jira": 2, "files": 0, "kb": 0},
    PHASE_EVIDENCE_COLLECTION: {"jira": 4, "files": 0, "kb": 0},
    PHASE_ARTIFACT_INSPECTION: {"jira": 1, "files": 4, "kb": 0},
    PHASE_KB_GROUNDING: {"jira": 0, "files": 0, "kb": 1},
    PHASE_POSSIBLE_FAILURE_REASON: {"jira": 0, "files": 0, "kb": 0},
    PHASE_DRAFT_DEBUG_STEPS: {"jira": 0, "files": 0, "kb": 0},
    PHASE_DONE: {"jira": 0, "files": 0, "kb": 0},
}


@dataclass
class PhaseState:
    phase: str = PHASE_CASE_IDENTIFICATION
    phase_index: int = 1
    entered_step: int = 1
    notes: list[str] = field(default_factory=list)
    kb_grounding_attempted: bool = False
    possible_failure_reason_ready: bool = False


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
    downloaded_text_attachment: bool,
    seen_failure_signal: bool,
    seen_kb: bool,
    step: int,
) -> tuple[PhaseState, bool]:
    cur = phase_state.phase
    nxt = cur
    kb_grounding_attempted = phase_state.kb_grounding_attempted
    possible_failure_reason_ready = phase_state.possible_failure_reason_ready
    if cur == PHASE_CASE_IDENTIFICATION and used_jira:
        nxt = PHASE_EVIDENCE_COLLECTION
    elif cur == PHASE_EVIDENCE_COLLECTION and (downloaded_text_attachment or used_files):
        nxt = PHASE_ARTIFACT_INSPECTION
    elif cur == PHASE_ARTIFACT_INSPECTION and seen_failure_signal:
        if seen_kb or kb_grounding_attempted:
            nxt = PHASE_POSSIBLE_FAILURE_REASON
        else:
            nxt = PHASE_KB_GROUNDING
    elif cur == PHASE_KB_GROUNDING:
        kb_grounding_attempted = True
        nxt = PHASE_POSSIBLE_FAILURE_REASON
    elif cur == PHASE_POSSIBLE_FAILURE_REASON and possible_failure_reason_ready:
        nxt = PHASE_DRAFT_DEBUG_STEPS
    if nxt == cur:
        return phase_state, False
    return PhaseState(
        phase=nxt,
        phase_index=PHASE_ORDER.index(nxt) + 1,
        entered_step=step,
        notes=list(phase_state.notes),
        kb_grounding_attempted=kb_grounding_attempted,
        possible_failure_reason_ready=possible_failure_reason_ready,
    ), True


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
    remaining_steps = max_steps - step
    if phase_state.phase == PHASE_ARTIFACT_INSPECTION:
        if seen_failure_signal and not seen_kb and not phase_state.kb_grounding_attempted and remaining_steps > 1:
            return False
    if phase_state.phase == PHASE_KB_GROUNDING and not phase_state.kb_grounding_attempted and remaining_steps > 0:
        return False
    if phase_state.phase == PHASE_POSSIBLE_FAILURE_REASON and not phase_state.possible_failure_reason_ready and remaining_steps > 0:
        return False
    if remaining_steps <= 1:
        return True
    budgets = PHASE_TOOL_BUDGETS.get(phase_state.phase, {})
    for family, budget in budgets.items():
        if budget > 0 and phase_usage.get(family, 0) >= budget:
            return True
    if seen_files and seen_failure_signal and (seen_kb or phase_state.kb_grounding_attempted) and phase_state.possible_failure_reason_ready:
        return True
    return False


FORCED_DRAFT_NUDGE = (
    "You now have enough evidence.\n\n"
    "Stop tool use unless one single targeted lookup is strictly required.\n"
    "Do not perform further broad evidence collection.\n"
    "Use the selected primary reason as a binding input. Do not replace it with a new explanation.\n\n"
    "Output ONLY in the following exact structure and exact section order.\n"
    "Do not add any preamble, title, explanation, or closing text.\n"
    "Do not include think tags or self-talk.\n\n"
    "Problem framing:\n"
    "- derive from primary reason title\n\n"
    "Most likely direction:\n"
    "- derive from primary reason chain\n\n"
    "Concrete DEBUG_STEPS:\n"
    "1. <short step covering a primary factor, max 20 words>\n"
    "2. <short step covering a primary factor, max 20 words>\n"
    "3. <short step covering a primary factor, max 20 words>\n"
    "4. <short step covering a primary factor, max 20 words>\n"
    "5. <short step covering a primary factor, max 20 words>\n\n"
    "Unknowns:\n"
    "- derive primarily from primary reason main gaps\n\n"
    "Why this path first:\n"
    "- justify from key support for the primary reason\n\n"
    "Rules:\n"
    "- no prose paragraphs\n"
    "- no extra sections\n"
    "- no title line\n"
    "- no markdown headers\n"
    "- no repeated punctuation\n"
    "- no markdown code blocks\n"
    "- no self-reflection\n"
    "- no explanation of the workflow\n"
    "- no phrases like 'The user has provided', 'Let me', or 'I will'\n"
    "- do not broaden into a generic crash template\n"
    "- ensure the concrete steps collectively cover the primary factors\n"
    "- if uncertain, keep the item short and concrete\n"
    "- prefer incomplete but useful bullets over long analysis"
)

KB_GROUNDING_NUDGE = (
    "You are in KB grounding phase.\n"
    "Before drafting or exiting, perform one lightweight KB grounding lookup now.\n"
    "Prefer kb_ground with the current case context and extracted failure signals.\n"
    "Do not perform broad KB search."
)
