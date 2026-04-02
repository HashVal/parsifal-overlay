# Tristan Per-Agent Patch Contract (Draft)

This document is a draft contract for per-agent patch/update behavior in the Tristan MVP workflow.

It sits between:
- the ownership model in `agent-profiles.md`
- the eventual per-agent patch JSON schema

Goal:
- make agent update authority concrete
- define patch style before formal JSON shape
- define what is append/replace/derived/harness-reflected
- reduce ambiguity before formalizing patch schemas

This is still a review draft.

---

## 1. Shared Patch Principles

### 1.1 Agents do not rewrite the whole CaseState

All patches are partial updates against a canonical `CaseState`.
Agents do not submit full-state replacement objects.

MVP intent:
- patches should be scoped
- patches should be layer-aware
- patches should be mergeable
- patches should not bypass ownership boundaries

---

### 1.2 Patch semantics are not uniform across all sections

Different sections use different update styles.

Examples:
- `execution.results` is naturally append-oriented
- `decision` is naturally replace-oriented as a current-state summary
- `hypotheses` and `plan` are usually full-section replacement in MVP
- `plan.items[*].status` may be harness-reflected rather than agent-owned

This means patch contract must explicitly state merge style per layer.

---

### 1.3 Harness remains the final merge authority

Agents propose patches.
Harness validates:
- actor ownership
- reference integrity
- semantic consistency
- state-machine legality

Harness then merges or rejects.

---

## 2. Patch Contract Table

| Patch | Actor | Primary purpose | Allowed updates | Forbidden updates | Typical merge style | State transition role |
|---|---|---|---|---|---|---|
| `IntakePatch` | Intake | ingest raw case material into structured observations | `issue`, `facts`, `anomalies`, `history` | `hypotheses`, `plan`, `execution`, `decision` | append/merge into observational layers | may advance `NEW -> INTAKE_READY` |
| `HypothesisPatch` | Hypothesis | construct competing hypotheses and current plan | `hypotheses`, `plan`, `history` | `execution`, `decision`, direct observational fact fabrication | usually replace `hypotheses` and `plan` as current analytical output | may advance `INTAKE_READY -> HYPOTHESES_READY`; may refresh rerun analytical state |
| `ProbePatch` | Probe | execute plan and report outcomes | `execution`, execution-derived `facts`, `history` | final `plan.items[*].status`, direct `decision`, direct hypothesis standing updates | append results/blockers/facts; harness reflects lifecycle state | may contribute evidence for readiness toward `JUDGING`, but does not need to request that transition by default |
| `JudgePatch` | Judge | determine closure / rerun / help | `decision`, `history` | raw `facts`, raw `anomalies`, raw `execution`, formal hypothesis table rewrite in MVP | replace current `decision` snapshot | may advance `JUDGING -> FINALIZED_* / NEED_RERUN / NEED_HELP` |

---

## 3. Merge Style by Layer

This section defines the intended update style of each major CaseState layer.

### 3.1 `issue`

Primary updater:
- Intake

Merge style:
- merge/replace specific issue fields as structured issue understanding improves

MVP note:
- issue is not expected to churn frequently after initial intake
- later updates are mostly comment/attachment-driven refinement

---

### 3.2 `facts`

Primary updaters:
- Intake
- Probe (execution-derived facts only)

Merge style:
- MVP rule: keyed merge / upsert into the proper fact slots of the current-state facts layer
- facts are not treated as append-only event lists
- whole-facts replacement is not the default patch style

Rationale:
- facts represent the current accepted observational basis of the case
- keeping facts as a current-state layer is cleaner than accumulating conflicting or superseded facts in place
- historical evolution should be preserved through history/audit trail rather than by turning facts into an event log

Semantic constraint:
- Hypothesis and Judge do not directly introduce observational facts in MVP

---

### 3.3 `anomalies`

Primary updater:
- Intake

Merge style:
- append or merge anomaly items and timeline interpretation

MVP note:
- Probe may observe runtime outputs, but anomaly-layer curation remains Intake-oriented unless future design expands anomaly ownership

---

### 3.4 `hypotheses`

Primary updater:
- Hypothesis

Merge style:
- MVP rule: whole replacement of the current hypothesis table as the latest analytical state

Rationale:
- hypothesis generation is holistic
- partial in-place mutation is harder to reason about early on
- replacement is simpler than incremental adjudication in MVP

MVP constraint:
- Judge does not directly rewrite formal hypothesis standing in current MVP ownership model

---

### 3.5 `plan`

Primary updater:
- Hypothesis

Merge style:
- MVP rule: whole replacement of the current plan as the latest analytical execution contract

Special rule:
- `plan.items[*].status` is a harness-reflected lifecycle overlay, not part of the Hypothesis-owned analytical truth
- new plan replacement should not be treated as requiring fine-grained inheritance of prior agent-owned status

Rationale:
- the plan is part of the current analytical contract
- lifecycle reflection should not create a second agent-owned truth source
- keeping plan replacement holistic is simpler and more coherent than incremental mutation in MVP

---

### 3.6 `execution`

Primary updater:
- Probe

Merge style:
- append new execution results
- append new blockers
- merge or increment tool-usage accounting

Semantic note:
- execution is a realized-outcomes layer, not a planning layer

---

### 3.7 `decision`

Primary updater:
- Judge

Merge style:
- replace the current decision snapshot

Rationale:
- decision is a current closure summary, not an append-only log
- historical decisions should be preserved via `history`, not stacked inside `decision`

---

### 3.8 `history`

Primary updaters:
- all agents
- harness

Merge style:
- append-only

Rationale:
- history should serve as audit trail
- agents may append events relevant to their actions
- harness may append merge/transition events

---

## 4. Draft Patch Profiles

This section describes the intended content shape of each patch before formal JSON schema is written.

---

## 4.1 IntakePatch

### Purpose
Turn raw issue material into structured observational state.

### Expected content categories
- issue updates
- fact additions or fact merges
- anomaly additions or anomaly merges
- missing-fact additions
- history additions
- optional state-transition request

### Intended patch style
- observational patch
- additive/merge-oriented
- not holistic rewrite of analytical or decision layers

### Should not contain
- hypothesis generation
- execution result records
- decision verdicts

---

## 4.2 HypothesisPatch

### Purpose
Produce the current explanatory model and current executable plan.

### Expected content categories
- hypothesis table replacement
- plan replacement
- history additions
- optional state-transition request

### Intended patch style
- analytical patch
- replace-oriented for `hypotheses`
- replace-oriented for `plan`

### Should not contain
- raw execution results
- decision verdicts
- newly fabricated observational facts

---

## 4.3 ProbePatch

### Purpose
Report executed checks and their outcomes.

### Expected content categories
- execution result additions
- blocker additions
- execution-derived fact additions
- tool-usage delta or merged usage update
- history additions
- optional execution-state hints if needed by harness
- optional readiness hints; state-transition request is not expected by default in MVP

### Intended patch style
- execution patch
- append-oriented for results/blockers
- additive/merge-oriented for derived facts
- no formal ownership of final plan lifecycle projection

### Should not contain
- direct decision verdicts
- formal hypothesis table rewrite
- final ownership of `plan.items[*].status`

---

## 4.4 JudgePatch

### Purpose
Decide closure and control next workflow step.

### Expected content categories
- decision replacement
- history additions
- optional state-transition request

### Intended patch style
- adjudication patch
- replace-oriented for `decision`

### Should not contain
- raw fact fabrication
- raw anomaly fabrication
- raw execution result creation
- formal hypothesis table rewrite in MVP

---

## 5. Harness-Reflected vs Agent-Owned Fields

This distinction is important.

### 5.1 Agent-owned fields

Examples:
- Intake-owned observational additions
- Hypothesis-owned current `hypotheses` and current `plan`
- Probe-owned execution records
- Judge-owned current `decision`

These fields are directly proposed by agent patches.

---

### 5.2 Harness-reflected fields

These are fields whose final state may be derived from agent patches and validator rules rather than directly owned by one patch type.

Current MVP example:
- `plan.items[*].status`

MVP meaning:
- Probe reports execution outcomes and blockers
- harness reflects those into plan lifecycle state

This avoids dual truth sources.

---

## 6. State Transition Intent

Patch contracts may include state transition intent, but agents do not have unilateral authority to force transitions.

Meaning:
- an agent may propose that the case is ready for the next state
- harness validates whether the transition is legal and sufficiently supported

Examples:
- IntakePatch may propose `NEW -> INTAKE_READY`
- HypothesisPatch may propose `INTAKE_READY -> HYPOTHESES_READY`
- JudgePatch may propose `JUDGING -> NEED_RERUN`

This keeps transitions explicit without making agents absolute controllers.

---

## 7. Draft Review Questions

These are the main patch-contract questions still worth reviewing before writing formal JSON patch schemas.

### Q1. Should `facts` updates be represented as append-only additions, keyed upserts, or partition replacements?
Current MVP answer:
- keyed merge / upsert
- facts are maintained as a current-state observational layer
- avoid append-only fact accumulation in the current facts view
- avoid whole-facts replacement in MVP

### Q2. Should `issue` updates be patch-like field updates or whole issue replacement?
Current leaning:
- patch-like field updates
- especially for comments/attachments-derived refinements

### Q3. Should HypothesisPatch fully replace both `hypotheses` and `plan` every time?
Current MVP answer:
- yes
- `hypotheses` is treated as a holistic analytical state and should be whole-replaced
- `plan` is treated as a holistic analytical execution contract and should also be whole-replaced
- `plan.items[*].status` remains harness-reflected lifecycle state rather than Hypothesis-owned analytical state

### Q4. Should ProbePatch include explicit execution-state hints for harness lifecycle reflection?
Current MVP answer:
- yes, optionally
- hints are allowed as a narrow mechanical aid for harness lifecycle reflection
- hints do not constitute final ownership of plan status

### Q5. Should JudgePatch ever carry hypothesis-standing hints even if it does not formally rewrite the table?
Current leaning:
- probably not in MVP
- decision should be the current adjudication layer

---

## 8. Intended Next Step

After review of this contract draft and the first full JSON patch draft set, the next step should be:
- tighten any remaining cross-document ambiguities
- optionally formalize the patch drafts into JSON schema
- optionally split out harness merge/validation rules and per-agent view schemas

Those later artifacts should directly inherit:
- the ownership boundaries from `agent-profiles.md`
- the merge-style decisions from this document
- the concrete patch shapes from `patch-json.md`
