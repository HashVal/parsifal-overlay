# Tristan Debug Agent Profiles (Draft)

This document is a draft profile spec for the four core agents in the Tristan MVP workflow.

Goal:
- define what each agent is responsible for
- define how each agent relates to `CaseState`
- define which parts of `CaseState` each agent should read
- define which parts of `CaseState` each agent should be allowed to update

This is still a review draft.
It is intentionally written before formal per-agent patch schemas, so responsibilities and boundaries can be reviewed first.

---

## 1. Shared Design Principle

All four agents operate against the same conceptual `CaseState`, but they should not be treated as having equal authority over the entire object.

MVP design intent:
- one canonical `CaseState`
- different agents read different slices with different emphasis
- each agent updates only the layer it owns
- cross-layer consistency is enforced by harness validation

This means:
- no agent should treat the entire case state as its free-form notebook
- no agent should silently rewrite another agent's layer of truth

---

## 2. Agent Overview

The four core agents are:

1. **Intake Agent**
2. **Hypothesis Agent**
3. **Probe Agent**
4. **Judge Agent**

High-level workflow:

```text
NEW -> Intake -> INTAKE_READY
INTAKE_READY -> Hypothesis -> HYPOTHESES_READY
HYPOTHESES_READY / PROBING -> Probe -> JUDGING
JUDGING -> Judge -> FINALIZED_* | NEED_RERUN | NEED_HELP
NEED_RERUN -> Hypothesis (MVP default)
```

---

## 3. Intake Agent

### 3.1 Primary responsibility

The Intake Agent is responsible for turning raw case material into an initial structured case basis.

Its job is to answer:
- What is this issue about?
- What source materials exist?
- What basic facts can already be extracted?
- What anomalies are visible?
- What critical information is still missing?

It is not responsible for making final diagnostic judgments.

---

### 3.2 Core tasks

Typical Intake tasks:
- read issue summary/description/comments
- identify relevant attachments/logs
- extract basic structured facts
- extract anomaly candidates
- establish earliest anomaly ordering where possible
- record explicit missing information

---

### 3.3 CaseState relationship

The Intake Agent is the primary writer for the early observational layers.

It should mainly populate:
- `issue`
- `facts`
- `anomalies`
- selected `history`

In MVP, `facts` should be treated as a current-state observational layer and updated via keyed merge / upsert rather than append-only accumulation.

---

### 3.4 What Intake should view

Intake should primarily read:
- `meta`
- `issue`
- existing `facts`
- existing `anomalies`
- `history` summary

In MVP rerun mode, Intake may also inspect:
- existing `decision.unresolved_gaps`
- selected prior `execution` summary

But Intake should not require full hypothesis/deep decision context to do its job.

---

### 3.5 What Intake may update

Intake may update:
- `issue`
- `facts`
- `anomalies`
- `history`

Intake should not directly update:
- `hypotheses`
- `plan`
- `execution`
- `decision`

---

### 3.6 What Intake must not do

Intake must not:
- finalize the case
- assign final root-cause conclusions
- silently convert hypotheses into facts
- rewrite execution outcomes

---

## 4. Hypothesis Agent

### 4.1 Primary responsibility

The Hypothesis Agent is responsible for constructing the competing explanation space and producing a discriminative plan.

Its job is to answer:
- What are the leading explanations?
- What supports each explanation?
- What weakens each explanation?
- What gaps remain?
- What checks best discriminate between these explanations?

---

### 4.2 Core tasks

Typical Hypothesis tasks:
- read facts and anomalies
- construct multiple candidate hypotheses
- ensure required hypothesis classes are considered
- define support evidence, contradiction evidence, and missing gaps
- produce discriminating checks
- produce prioritized plan items

---

### 4.3 CaseState relationship

The Hypothesis Agent owns the explanatory and planning layers.

It should mainly populate:
- `hypotheses`
- `plan`
- selected `history`

In MVP, both `hypotheses` and `plan` are treated as holistic analytical outputs of the current reasoning pass rather than incrementally patched structures.

It may also rely on semantic interpretation of:
- `facts`
- `anomalies`
- selected `execution` summaries from prior loops
- `decision.unresolved_gaps` / `decision.rerun_focus`

---

### 4.4 What Hypothesis should view

Hypothesis should primarily read:
- `meta`
- `issue`
- `facts`
- `anomalies`
- prior `execution.results` summaries
- prior `execution.blockers` summaries
- prior `decision`
- `history` summary

Hypothesis should default to summary-level prior execution context rather than full raw execution detail.
It may request selected detailed execution context when summary-level information is insufficient for hypothesis reconstruction or replanning.

This is the agent that needs the broadest analytical view before planning, but it should still follow a summary-first, detail-on-demand model.

---

### 4.5 What Hypothesis may update

Hypothesis may update:
- `hypotheses`
- `plan`
- `history`

Hypothesis should not directly update:
- `facts` as if they were newly observed
- `execution`
- `decision`

If Hypothesis wants something added to facts, that should only happen through future execution or explicit re-intake logic, not by silently reclassifying inference as fact.

---

### 4.6 What Hypothesis must not do

Hypothesis must not:
- treat a single explanation as truth by default
- write unsupported conclusions into facts
- mark checks as done without execution
- finalize or escalate directly

---

## 5. Probe Agent

### 5.1 Primary responsibility

The Probe Agent is responsible for executing the current plan and returning structured execution outcomes.

Its job is to answer:
- Which checks were actually executed?
- What did they observe?
- What was blocked?
- Which new facts were produced?
- How do results shift current hypotheses?

---

### 5.2 Core tasks

Typical Probe tasks:
- read planned checks
- execute code-side or device-side checks
- record outputs and interpretations
- record blockers
- record new facts produced by execution
- record hypothesis impacts
- update tool usage

---

### 5.3 CaseState relationship

Probe owns the execution layer.

It should mainly populate:
- `execution`
- execution-derived additions to `facts`
- selected `history`

Execution-derived facts should merge into the current facts view as keyed observational updates rather than accumulate as append-only fact history.

It does not own final `plan.items[*].status` updates in MVP.
Instead, it reports execution results, blockers, and any necessary execution-state hints, and harness logic reflects those into plan status.

---

### 5.4 What Probe should view

Probe should primarily read:
- `meta`
- `facts`
- `hypotheses`
- `plan`
- selected `decision.do_not_repeat_check_ids`
- selected prior `execution` summaries for continuity

Probe should read only the subset of prior execution context directly relevant to the current planned checks.
It should not default to broad historical execution detail or full narrative reasoning history if the plan is already well-formed.

---

### 5.5 What Probe may update

Probe may update:
- `execution`
- execution-derived `facts`
- `history`

Probe should not directly update:
- `plan.items[*].status` as a final owner
- `hypotheses.confidence`
- `decision`

Probe may describe hypothesis impacts, but it should not own the final adjudication of hypothesis status.

---

### 5.6 What Probe must not do

Probe must not:
- rewrite the hypothesis table as if it were the judge
- silently drop plan items without blocker/result context
- declare final closure
- treat command failure as equivalent to diagnostic negative result without proper execution semantics

---

## 6. Judge Agent

### 6.1 Primary responsibility

The Judge Agent is responsible for closure and workflow control decisions.

Its job is to answer:
- Do the current facts, hypotheses, and execution results close the case strongly, weakly, or not at all?
- Is another loop required?
- Is human help required?
- What should not be repeated?
- What is the current best finalized explanation, if any?

---

### 6.2 Core tasks

Typical Judge tasks:
- read current hypotheses and execution results
- determine closure level
- determine verdict
- rank leading hypotheses
- record unresolved gaps
- define rerun focus if needed
- define help request if needed
- define finalized explanation if applicable

---

### 6.3 CaseState relationship

Judge owns the decision layer.

It should mainly populate:
- `decision`
- selected `history`

In MVP, Judge does not directly own formal updates to `hypotheses.items[*].status` or `hypotheses.items[*].confidence`.
Its adjudication is expressed through the `decision` layer.
A future richer patch model may allow explicit hypothesis-standing updates, but that is not part of current MVP ownership.

---

### 6.4 What Judge should view

Judge should primarily read:
- `meta`
- `facts`
- `hypotheses`
- `plan`
- structured `execution` summary
- `history` summary

Judge should default to the full structured execution summary view.
It may drill down into selected detailed execution records when closure cannot be determined from summary-level state alone.

Judge is the agent that needs the strongest whole-case closure view, but it should still avoid defaulting to full raw execution history.

---

### 6.5 What Judge may update

Judge may update:
- `decision`
- `history`

Judge should not directly update:
- raw facts
- raw anomalies
- raw execution results

Judge may interpret them, but should not fabricate them.

---

### 6.6 What Judge must not do

Judge must not:
- silently invent new evidence in rationale
- finalize a case while active execution is still running
- declare `NEED_HELP` without explicit handoff detail
- declare rerun without explicit rerun focus

---

## 7. View Matrix (Draft)

This is the draft read/update matrix for MVP.

| Agent | Primary purpose | Main read scope | Main update scope |
|---|---|---|---|
| Intake | Structure raw issue into facts/anomalies | `meta`, `issue`, existing `facts`, existing `anomalies`, `history` summary | `issue`, `facts`, `anomalies`, `history` |
| Hypothesis | Build competing explanations and plan | `meta`, `issue`, `facts`, `anomalies`, prior `execution`, prior `decision`, `history` | `hypotheses`, `plan`, `history` |
| Probe | Execute checks and return results | `meta`, `facts`, `hypotheses`, `plan`, selected prior `decision`, selected prior `execution` | `execution`, execution-derived `facts`, `history` |
| Judge | Decide closure / rerun / help | `meta`, `facts`, `hypotheses`, `plan`, `execution`, `history` | `decision`, `history` |

---

## 8. Ownership Rules (Draft)

These are draft ownership rules for review.

### Rule O1
Observational truth should enter the system mainly through:
- Intake
- Probe

### Rule O2
Explanatory structures should enter the system mainly through:
- Hypothesis

### Rule O3
Workflow closure should be owned by:
- Judge

### Rule O4
No agent should silently rewrite another layer's core truth.

Examples:
- Hypothesis should not rewrite facts as if newly observed
- Probe should not directly finalize the case
- Judge should not invent raw check outputs

---

## 9. Open Questions for Review

These are the main questions still worth reviewing before formalizing per-agent patch schemas.

### Q1. Should Intake participate in rerun at all in MVP?
Current MVP answer:
- default rerun owner is `hypothesis`
- Intake does not re-enter the rerun main path by default
- Intake re-enters only when new raw case material appears, or when the missing/incorrect layer is observational rather than explanatory

### Q2. Should Probe be allowed to update `plan.items[*].status` directly?
Current MVP answer:
- no, not as final owner
- Probe reports execution outcomes, blockers, and any needed execution-state hints
- harness reflects those outcomes into `plan.items[*].status`
- `plan` remains a whole-replaced analytical contract from Hypothesis, while `status` remains a separate harness-reflected lifecycle overlay

### Q3. Should Judge directly update hypothesis status in MVP?
Current MVP answer:
- no
- Judge expresses adjudication through `decision`
- formal hypothesis updates remain with Hypothesis in the next loop
- richer hypothesis adjudication can be added later if ownership is intentionally expanded

### Q4. How much prior execution detail should Hypothesis and Probe see?
Current MVP answer:
- all agents should be summary-first by default
- Hypothesis may request selected detailed execution context when summary-level information is insufficient
- Probe should read only the subset of prior execution context directly relevant to current planned checks
- Judge should default to full structured execution summary and only drill down into selected detail when needed for closure
- no agent should default to full raw execution history

---

## 10. Intended Next Step

After review of this draft, the next natural artifact is:
- a formal per-agent patch/update schema

That patch schema should be derived from this ownership model rather than invented independently.
