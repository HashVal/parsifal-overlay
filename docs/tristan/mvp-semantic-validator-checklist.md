# MVP Semantic Validator Checklist

This checklist turns the semantic rules from `data-model-semantics.md` into an implementation-oriented validator checklist.

Use it as a harness-side validation layer after JSON Schema validation succeeds.

JSON Schema answers:
- Is the object structurally well-formed?

This checklist answers:
- Is the object logically valid for the debug-agent workflow?

---

## 1. State-Machine Validation

### V1. Owner/status compatibility
- [ ] `meta.owner_agent` is valid for `meta.status`

Expected MVP mapping:
- `NEW` -> `intake`
- `INTAKE_READY` -> `hypothesis`
- `HYPOTHESES_READY` -> `probe`
- `PROBING` -> `probe`
- `JUDGING` -> `judge`
- `NEED_RERUN` -> `hypothesis`
- `FINALIZED_STRONG` -> `null`
- `FINALIZED_WEAK` -> `null`
- `NEED_HELP` -> `null`

### V2. Terminal ownership
- [ ] terminal states imply `owner_agent = null`

---

## 2. Reference Integrity Validation

### V3. Decision hypothesis ids resolve
- [ ] every `decision.top_hypothesis_ids[*]` exists in `hypotheses.items[*].hypothesis_id`

### V4. Plan target hypothesis ids resolve
- [ ] every `plan.items[*].target_hypothesis_id` exists in `hypotheses.items[*].hypothesis_id`

### V5. Plan dependency ids resolve
- [ ] every `plan.items[*].dependencies[*]` exists as a valid check id in the same effective plan

### V6. Execution result check ids resolve
- [ ] every `execution.results[*].check_id` exists in the effective plan (including accepted follow-up checks if supported)

### V7. Blocker check ids resolve
- [ ] every non-null `execution.blockers[*].check_id` exists in the effective plan

### V8. New fact ids resolve
- [ ] every `execution.results[*].new_fact_ids[*]` exists in the facts layer after merge

---

## 3. Plan / Execution Lifecycle Validation

### V9. Done checks have results
- [ ] every `plan.items[*]` with `status = done` has a corresponding execution result

### V10. Blocked checks are justified
- [ ] every `plan.items[*]` with `status = blocked` has either:
  - a blocker record, or
  - an execution result with `outcome = blocked`

### V11. Blocked outcomes have blocker detail
- [ ] every `execution.results[*]` with `outcome = blocked` has a corresponding blocker record

### V12. Finalized states have no running checks
- [ ] if verdict is finalized, no check in the plan has `status = running`

---

## 4. Decision Validation

### V13. FINALIZED_STRONG closure consistency
- [ ] `current_verdict = FINALIZED_STRONG` implies `closure_level = strong`

### V14. FINALIZED_WEAK closure consistency
- [ ] `current_verdict = FINALIZED_WEAK` implies `closure_level = weak`

### V15. NEED_RERUN closure consistency
- [ ] `current_verdict = NEED_RERUN` implies `closure_level in {none, partial}`

### V16. NEED_HELP closure consistency
- [ ] `current_verdict = NEED_HELP` does not imply `closure_level = strong`

### V17. Finalized states require leading hypotheses
- [ ] finalized states imply non-empty `top_hypothesis_ids`

### V18. Finalized states require finalized explanation
- [ ] finalized states imply non-null `finalized_explanation`

### V19. Finalized states clear rerun focus
- [ ] finalized states imply empty `rerun_focus`

### V20. NEED_RERUN requires rerun focus
- [ ] `current_verdict = NEED_RERUN` implies non-empty `rerun_focus`

### V21. NEED_RERUN must not finalize explanation
- [ ] `current_verdict = NEED_RERUN` implies `finalized_explanation = null`

### V22. NEED_HELP requires help request
- [ ] `current_verdict = NEED_HELP` implies non-null `help_request`
- [ ] `help_request.owner` is non-null
- [ ] `help_request.reasons` is non-empty
- [ ] `help_request.minimum_required_inputs` is non-empty

### V23. Leading hypothesis cannot be eliminated
- [ ] if `top_hypothesis_ids` is non-empty, the first hypothesis is not in `status = eliminated`

---

## 5. Semantic Discipline Validation

### V24. Facts do not contain final conclusions
- [ ] facts layer does not encode final root-cause claims

### V25. Rationale does not invent new major conclusions
- [ ] `decision.rationale` does not introduce major conclusions absent from facts, hypotheses, or execution

### V26. Rerun focus is concrete enough
- [ ] `decision.rerun_focus` is not vague filler such as:
  - "look deeper"
  - "more analysis needed"
  - "check more things"

---

## 6. Recommended Validation Order

For implementation, apply validation in this order:

1. JSON Schema validation
2. State-machine validation
3. Reference integrity validation
4. Lifecycle validation
5. Decision validation
6. Semantic-discipline linting

Why this order:
- structure first
- then workflow control correctness
- then references
- then execution/decision consistency
- finally soft semantic quality checks

---

## 7. Suggested Severity Model

Recommended severity levels:

### Hard errors (reject merge)
Use for:
- owner/status mismatch
- unresolved hypothesis/check/fact references
- finalized verdict without top hypothesis
- finalized verdict without finalized explanation
- rerun without rerun focus
- blocked result without blocker detail

### Soft errors / warnings
Use for:
- vague rerun focus text
- rationale suspiciously introducing new conclusions
- low-quality fallback or weak summaries

This split keeps the MVP validator strict where workflow integrity matters and softer where judgment quality is still partly textual.
