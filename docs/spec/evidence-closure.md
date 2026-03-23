# Evidence Closure Specification

## Purpose and Scope

This document defines the specification for the evidence-closure layer in `simple-rla`.

Its purpose is to specify how the system should consume check-execution results, interpret returned evidence, update the current explanatory state, and produce an evidence-based outcome classification.

In particular, this document defines:

- what the evidence-closure layer is responsible for
- what inputs it consumes from the check-execution layer
- how execution results should be interpreted against the current hypothesis and evidence gaps
- how checks should be closed, preserved, or superseded
- what outcome classifications must be supported
- when the system should terminate and when it should re-enter a new reasoning-action cycle

This document is not a replacement for the analysis layer, not a provider-specific runtime policy, and not a generic user-facing summary guide.

---

## Role in the Full System

The evidence-closure layer sits after check execution and before either terminal resolution or a new reasoning-action iteration.

Its role is to convert execution results into a grounded closure state for the current iteration.

In the full system, the intended relationship is:

```text
analysis outputs
  -> debug plan
  -> check execution
  -> evidence closure
  -> terminal outcome
     or
     re-enter reasoning-action loop
```

This means the evidence-closure layer is:

- downstream of `DEBUG_PLAN` and check-execution output
- responsible for evaluating whether the current iteration has meaningfully resolved, blocked, or destabilized the active debugging direction
- responsible for classifying the run into an explicit outcome state
- responsible for determining whether the system should terminate or re-enter a new reasoning-action cycle

The evidence-closure layer is not a broad re-analysis layer.
Its purpose is to evaluate the current iteration under explicit evidence and plan context.

---

## Closure Semantics

Evidence closure exists to answer a bounded but critical question:

> Given the current debug plan, the executed checks, and the evidence returned, what is now justified?

This requires more than summarizing execution results.

The evidence-closure layer must:

- interpret returned evidence against the active hypothesis
- determine whether key evidence gaps have been closed
- determine whether executed checks have been resolved, contradicted, blocked, or left open
- update the explanatory state of the current iteration
- classify the result into an explicit outcome

Evidence closure must not be treated as:
- a fresh unconstrained analysis pass over the entire raw case
- a replacement for debug planning
- a silent continuation of execution
- an untyped narrative summary with no outcome semantics

The purpose of closure is to produce an evidence-grounded judgment for the current iteration.

---

## Inputs to Evidence Closure

The primary inputs to the evidence-closure layer are:

- the current `DEBUG_PLAN`
- check-execution output
- structured evidence returned by executed `CODE_CHECK` and `DEVICE_CHECK` items
- execution outcomes such as `COMPLETED`, `INCONCLUSIVE`, `BLOCKED`, `FAILED`, and `DEFERRED`
- the current active hypothesis and any still-relevant alternatives
- the current evidence-gap context carried from earlier phases

Where relevant, the closure layer may also consume compact supporting context needed for interpretation, such as:
- supporting capability-domain outputs
- execution-environment constraints
- runtime notes explaining blocked or failed checks

However, evidence closure should primarily consume the structured outputs of earlier phases rather than reopening broad raw case context by default.

---

## Required Evidence-Closure Work

The evidence-closure layer must complete the following kinds of work.

### 1. Evidence Evaluation
The layer must interpret returned evidence in relation to:
- the active hypothesis
- relevant alternative hypotheses
- the evidence gaps that motivated the executed checks

This includes determining whether evidence:
- supports the active explanation
- weakens it
- contradicts it
- or leaves it materially unresolved

### 2. Hypothesis-State Update
The layer must update the current explanatory state.

At minimum, it should be able to determine whether the active hypothesis is:
- sufficiently supported
- strengthened but not yet sufficient
- weakened
- contradicted
- or still unresolved

### 3. Check Closure
The layer must determine, for each relevant check, whether it is now:
- closed by supporting evidence
- closed by contradiction
- blocked
- inconclusive
- deferred to later iteration
- or no longer relevant because the explanatory frame has changed

### 4. Evidence-Gap Re-evaluation
The layer must determine:
- which evidence gaps have been closed
- which remain open
- which newly emerged gaps now matter
- whether the remaining open gaps are still decision-critical

### 5. Outcome Classification
The layer must classify the current iteration into an explicit outcome state.

This classification is the main output of evidence closure.

---

## Required Evidence-Closure Output

The evidence-closure phase must produce one primary closure artifact.

This artifact must express the closure state of the current iteration in a structured form.

A valid output must include:

### 1. Closure Context
This section identifies:
- which debug plan was being closed
- which checks materially informed the closure judgment
- which hypothesis context was active during closure

### 2. Hypothesis Update
This section records:
- the updated state of the active hypothesis
- whether any alternative hypothesis has become more plausible
- whether the prior explanatory frame remains valid for continued iteration

### 3. Check Closure State
This section records:
- which `CODE_CHECK` items are closed, blocked, inconclusive, deferred, or no longer relevant
- which `DEVICE_CHECK` items are closed, blocked, inconclusive, deferred, or no longer relevant

### 4. Evidence-Gap State
This section records:
- which previously open evidence gaps are now closed
- which still remain open
- which newly observed gaps now matter

### 5. Outcome Classification
This section records:
- the explicit outcome classification for the current iteration
- the rationale for that classification
- the evidence basis for that classification
- whether the system should terminate or re-enter a new reasoning-action cycle

### 6. Handoff Basis
If the current iteration does not terminate, the output must preserve enough structured state to support the next iteration.

This may include:
- the updated explanatory frame
- surviving or newly emerged evidence gaps
- checks that should not be repeated
- reasons the next iteration should differ from the current one

---

## Outcome Model

The evidence-closure layer must support the following outcome classifications.

### `correct_rca`
Use this outcome when:
- the main causal explanation is sufficiently supported by accumulated evidence
- remaining uncertainty does not invalidate the main conclusion
- the current iteration has produced enough grounding to justify closure

This is a terminal outcome.

---

### `BLOCKED`
Use this outcome when:
- the next valuable action is known
- but meaningful progress cannot continue because of missing access, permissions, tools, artifacts, reachability, or other external constraints

`BLOCKED` means the system still has directional clarity, but cannot proceed operationally.

This is a terminal outcome for the current run.

---

### `HELP_NEEDED`
Use this outcome when:
- further progress requires human judgment, experiment design, domain interpretation, or decision authority
- or the available evidence does not support a stable automated continuation path

`HELP_NEEDED` does not mean “execution failed.”
It means the system cannot responsibly continue toward closure on its own.

`HELP_NEEDED` should be used when autonomous continuation should not proceed without human intervention.

This is a terminal outcome for the current run.

---

### `REFRAME`
Use this outcome when:
- the current debug direction is no longer sufficiently supported
- the current explanatory frame has been materially weakened, contradicted, or exhausted
- the system should not merely continue the same line of planning and execution
- but the case is not blocked and does not yet require human takeover

`REFRAME` means the system should re-enter a new reasoning-action cycle under a meaningfully revised explanatory frame.

It is not:
- simple continuation
- raw retry
- plan extension under the same unchanged direction
- or a terminal resolution

It specifically indicates that the next iteration should revisit reasoning, hypothesis framing, or planning assumptions before further execution proceeds.

This is the only non-terminal outcome in the current model.

---

## Meaning of `REFRAME`

`REFRAME` exists to represent a specific non-terminal state:

> The current iteration has produced enough evidence to show that the existing debugging direction should not simply be extended, but not enough to justify terminal closure.

Typical conditions for `REFRAME` may include:
- key checks materially weaken the active hypothesis
- early checks invalidate a major planning assumption
- the current evidence suggests a different explanatory direction is more promising
- continuing the same debug plan would mostly repeat low-value work
- the case remains actionable, but under a different reasoning frame

A `REFRAME` outcome should trigger:
- renewed reasoning over the updated evidence state
- refreshed or replaced hypothesis framing
- a newly generated debug plan for the next iteration

`REFRAME` should be used when the system can still autonomously proceed under a revised explanatory frame.

A `REFRAME` outcome should not trigger:
- blind continuation of the current plan
- immediate terminal classification
- arbitrary execution without renewed planning

---

## Terminal vs Non-Terminal Semantics

The evidence-closure layer must distinguish terminal and non-terminal outcomes.

### Terminal outcomes
- `correct_rca`
- `BLOCKED`
- `HELP_NEEDED`

These end the current run.

### Non-terminal outcome
- `REFRAME`

This does not end the case.
It ends the current iteration and requires a new reasoning-action cycle.

This distinction must remain explicit.

In particular:
- `REFRAME` must not be collapsed into `HELP_NEEDED`
- `REFRAME` must not be treated as ordinary continuation
- `BLOCKED` must not be used when the real issue is directional invalidation rather than external constraint

---

## Closure Discipline and Boundaries

The evidence-closure layer must remain bounded by the current iteration’s plan and execution results.

It must not:
- silently perform a fresh broad investigation of the case
- execute new checks as part of closure itself
- replace evidence-based judgment with unsupported intuition
- collapse all unresolved states into `HELP_NEEDED`
- treat `REFRAME` as a generic fallback for uncertainty

The purpose of this layer is to produce structured closure, not to restart the system inside the same phase.

If a new reasoning-action cycle is needed, closure should express that explicitly through the outcome model.

---

## Relationship to Re-Entry into the Loop

When the outcome is `REFRAME`, the system should re-enter the reasoning-action loop with updated context.

This re-entry should be informed by:
- the updated hypothesis state
- closed and still-open evidence gaps
- checks that proved low-value or invalid
- evidence that changed the explanatory frame
- any constraints observed during execution

The purpose of re-entry is not to replay the same loop unchanged.

It is to begin a new iteration under a revised frame.

---

## Relationship to Earlier and Later Phases

The evidence-closure layer depends on earlier phases being well-formed.

It assumes:
- analysis produced structured reasoning artifacts
- debug planning produced a valid `DEBUG_PLAN`
- check execution preserved structured evidence and check traceability

In turn, evidence closure provides:
- terminal outcome classification when closure is justified
- or a structured basis for renewed reasoning when `REFRAME` is returned

This makes evidence closure the phase that converts evidence into either:
- justified termination
- or justified loop renewal

---

## Non-Goals

This specification does not require the evidence-closure layer to be:

- a replacement for the analysis layer
- a hidden second execution layer
- a generic prose summary step
- a provider-specific runtime policy
- a guarantee that every case reaches terminal resolution in one iteration

Its purpose is narrower:

- interpret execution results against the current explanatory frame
- update hypothesis and check states
- classify the current iteration into an explicit outcome
- decide whether to terminate or re-enter the loop

---

## Relationship to Other Specifications

This document should be read together with:

- `simple-rla.md`
  for the top-level system structure and terminal outcomes

- `analysis-flow.md`
  for the analysis-layer constraints

- `debug-plan.md`
  for the semantics of `DEBUG_PLAN` / `DEBUG_STEPS`

- `check-execution.md`
  for the execution-layer inputs, outputs, and check states

Together, these documents define the path from:
- issue analysis
- to debug planning
- to check execution
- to evidence closure
- to either terminal resolution or re-entry through `REFRAME`

---

## Conclusion

The evidence-closure layer exists to convert executed checks and returned evidence into an explicit closure state for the current iteration.

Its purpose is not merely to summarize what happened.
Its purpose is to determine what is now justified.

That means:
- evaluating evidence against the current hypothesis
- updating hypothesis and check states
- re-evaluating evidence gaps
- classifying the iteration into `correct_rca`, `BLOCKED`, `HELP_NEEDED`, or `REFRAME`

That is what allows `simple-rla` to behave as a true multi-iteration reasoning-action-evidence system rather than a one-shot workflow.
