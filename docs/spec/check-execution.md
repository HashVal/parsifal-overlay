# Check Execution Specification

## Purpose and Scope

This document defines the specification for the check-execution layer in `simple-rla`.

Its purpose is to specify how the system should consume a debug plan, execute its checks through available capability domains, and return structured evidence and execution results for later evaluation.

In particular, this document defines:

- what the check-execution layer is responsible for
- what inputs it consumes from the debug-plan layer
- how the current primary check item types are interpreted
- how checks relate to capability domains and tool-call realization
- what outputs check execution must produce
- how execution results should be mapped back to checks
- what kinds of execution outcomes must be represented

This document is not a provider-specific tool schema, not a workflow YAML reference, and not an implementation guide for any particular runtime.

---

## Role in the Full System

The check-execution layer sits between debug planning and evidence-based evaluation.

Its purpose is to transform planned checks into actual evidence-producing actions.

In the full system, the intended relationship is:

```text
analysis outputs
  -> debug plan
  -> check execution
  -> evidence evaluation
  -> outcome / next iteration
```

This means the check-execution layer is:

- downstream of `DEBUG_PLAN` / `DEBUG_STEPS`
- upstream of evidence-based synthesis and outcome classification
- responsible for realizing checks through execution
- responsible for preserving traceability between execution results and plan structure

The check-execution layer is not itself the final reasoning or decision layer.
Its primary purpose is to acquire and package evidence under the control of the current plan.

---

## Execution Semantics

A planned `Check` is not complete until it has either:

- produced usable evidence
- failed in a meaningful way
- become blocked
- or been judged inconclusive for the current iteration

The purpose of check execution is therefore not mechanical plan replay.
Its purpose is to realize checks as bounded evidence-seeking actions.

This means check execution must:

- operate under the explanatory context of the current debug plan
- preserve linkage between each execution result and its originating check
- record execution outcomes in a form usable by later evidence evaluation
- avoid drifting into unrelated exploration outside the plan’s scope

Check execution must not be treated as:
- an unrestricted autonomous investigation layer
- a replacement for later evidence interpretation
- a free-form tool-usage phase with no check-level discipline

---

## Inputs to Check Execution

The primary input to check execution is a valid debug-plan artifact.

This artifact may be exposed externally as `DEBUG_STEPS`, but semantically it is a structured `DEBUG_PLAN`.

At minimum, check execution must consume from that plan:

- active hypothesis context
- current problem framing
- one or more defined checks
- check priorities where available
- relevant prerequisites and blockers where available
- declared capability-domain needs where available

Check execution may also consume supporting runtime context needed to realize the plan, such as:

- environment availability
- tool availability
- repository or artifact access state
- device reachability state
- permission constraints

These supporting inputs are execution-enabling context, not substitutes for the plan itself.

---

## Current Primary Check Item Types

The current `simple-rla` model defines exactly two primary check item types:

- `CODE_CHECK`
- `DEVICE_CHECK`

These are the only primary check item types defined at the planning and execution boundary in the current model.

This means:

- a debug plan must express its executable checks through these two types
- check execution must preserve these two types during realization
- later evidence evaluation must be able to interpret returned evidence in relation to these two types

Other execution-side dependencies or information sources must not be treated as additional peer check item types in the current model.

---

## Check Type Classification Rule

A check must be classified by its primary evidence-acquisition surface.

### `CODE_CHECK`
A check is a `CODE_CHECK` when its main validation path depends on source-code-side evidence.

Typical examples include:
- inspecting source paths or call relationships
- checking branch-specific behavior or commit presence
- validating code-path assumptions
- examining interface invariants or implementation preconditions

A check remains a `CODE_CHECK` even if execution also uses supporting capability domains such as KB lookup, artifact extraction, or case-context retrieval.

### `DEVICE_CHECK`
A check is a `DEVICE_CHECK` when its main validation path depends on device-side, runtime-side, or environment-observation evidence.

Typical examples include:
- inspecting logs
- checking runtime state
- validating topology or binding state
- inspecting deployment/configuration facts
- collecting device-observable diagnostics

A check remains a `DEVICE_CHECK` even if execution also uses supporting capability domains such as KB lookup, artifact extraction, or case-context retrieval.

The classification rule is based on the primary evidence surface, not on every auxiliary action used during execution.

---

## Required Check-Execution Output

The check-execution phase must produce one primary execution artifact.

This artifact should contain the realized execution state of the checks selected for the current iteration.

A valid output must include:

### 1. Execution Context
This section identifies:
- which plan is being executed
- which checks were selected for execution
- what execution environment constraints were relevant
- what capability domains were actually used

### 2. Check Execution Results
For each executed or attempted check, the output must preserve:
- the originating check identity
- the check type (`CODE_CHECK` or `DEVICE_CHECK`)
- the execution status
- the evidence returned, if any
- execution notes relevant to later evaluation
- any blockers or failures encountered

### 3. Evidence Pack
The execution output must package returned evidence in a form suitable for later synthesis.

At minimum, this may include:
- code-side evidence
- device-side evidence
- supporting evidence derived through auxiliary capability domains where relevant

### 4. Unexecuted / Deferred Checks
If some checks were not executed, the output should preserve:
- which checks were deferred
- their check type
- why they were deferred
- whether the reason was prioritization, blocking, missing capability, or dependency ordering

### 5. Execution Summary
The output should provide a compact summary of:
- what was executed
- what evidence was obtained
- what remained blocked or inconclusive
- what follow-up execution appears most likely to matter

This summary is not the final reasoning output.
It exists to support later evidence evaluation.

---

## Check Selection and Execution Discipline

Not every check in a plan must always be executed immediately.

The check-execution layer may need to select, order, or defer checks based on:

- priority
- prerequisites
- capability availability
- runtime cost
- blocking conditions
- evidence value for the active hypothesis

This means the execution layer is allowed to be selective, but not arbitrary.

A valid execution choice must remain explainable in terms of the current plan.

Check execution must therefore preserve:

- why a check was executed now
- why a check was deferred
- why a check could not be executed
- what effect this had on the available evidence state

This discipline is necessary to keep the loop bounded and interpretable.

---

## Supporting Capability Domains and Tool Realization

The current model defines exactly two primary check item types, but execution may depend on supporting capability domains.

Typical supporting capability domains may include:
- `kb`
- `artifact-log`
- `case-context`
- `environment`

These supporting capability domains are not additional check item types.

They exist only to support the realization, interpretation, or targeting of a `CODE_CHECK` or `DEVICE_CHECK`.

For example:
- a KB lookup may refine what a `DEVICE_CHECK` is actually trying to validate
- an artifact/log extraction step may provide structure needed before a `CODE_CHECK` can be executed meaningfully
- case-context retrieval may clarify which target should be used in a `DEVICE_CHECK`
- environment inspection may explain why a `CODE_CHECK` or `DEVICE_CHECK` is blocked

Concrete tool calls are runtime realizations of these capability domains.

This means:
- `CODE_CHECK` and `DEVICE_CHECK` are planning/execution-boundary object types
- supporting capability domains are execution-enabling categories
- tool calls are runtime realizations

This distinction must remain explicit.

---

## Execution Outcomes

Each check selected for current execution handling must result in an explicit execution outcome.

At minimum, the following execution outcomes must be representable.

### `COMPLETED`
The check was executed and produced usable evidence.

### `INCONCLUSIVE`
The check was executed, but the returned result did not materially resolve the targeted uncertainty.

### `BLOCKED`
The check could not be meaningfully executed because required access, tools, permissions, artifacts, or runtime conditions were unavailable.

### `FAILED`
The check execution itself failed in a way that is operationally meaningful, such as execution error, malformed target, tool failure, or other runtime problem.

`FAILED` indicates that an execution attempt occurred but did not complete successfully.
`BLOCKED` indicates that meaningful execution could not proceed because required conditions were unavailable.

### `DEFERRED`
The check was not executed in the current iteration, but remains part of the active plan.

These execution outcomes are not equivalent to final system outcomes.
They are check-level execution states.

---

## Evidence Traceability Requirements

Returned evidence must remain traceable to the check that produced it.

The system must be able to answer:

- which check produced this evidence
- whether that check was a `CODE_CHECK` or `DEVICE_CHECK`
- what hypothesis or evidence gap that check addressed
- which supporting capability domains were used
- whether the evidence supports, weakens, or leaves unresolved the intended line of reasoning
- whether the result should close, revise, or preserve the corresponding check

The check-execution layer does not make the final reasoning judgment by itself.

However, it must return enough structured state for later evidence evaluation to do so.

Without traceability, execution results cannot be reliably integrated back into the loop.

---

## Boundaries of Check Execution

The check-execution layer must remain bounded by the current plan.

It must not:

- invent unrelated new investigative branches without justification
- replace evidence evaluation with its own final RCA claims
- silently reopen broad raw context when the plan does not require it
- treat supporting capability domains as new peer check item types
- treat tool availability as permission for unrestricted exploration
- collapse all execution detail into a single unstructured note

The purpose of this layer is operational realization of the current plan, not uncontrolled investigation.

If new information suggests the current plan is no longer appropriate, that should feed into plan revision or later evaluation rather than silent execution drift.

---

## Relationship to Plan Revision

Check execution may expose the need for plan revision.

Examples include:
- repeated blocking on high-priority checks
- contradictory evidence from early checks
- discovery that a prerequisite assumption in the plan is false
- newly surfaced environment constraints
- supporting KB/artifact results that materially change the next best action

The check-execution layer should therefore preserve enough execution state to support later plan revision.

However, plan revision remains conceptually distinct from check execution itself.

Execution realizes the current plan.
Revision changes the plan.

---

## Relationship to Later Evaluation

The primary downstream consumer of check-execution output is the later evidence-evaluation layer.

That later layer should be able to use execution outputs to determine:

- whether the active hypothesis remains supported
- whether alternative hypotheses should be promoted
- whether enough evidence exists for closure
- whether the run is blocked
- whether human intervention is needed
- whether another iteration of planning/execution is justified

For that reason, check execution must return:

- structured evidence
- structured execution statuses
- preserved linkage to checks
- preserved linkage to hypothesis/evidence-gap context
- preserved distinction between `CODE_CHECK` and `DEVICE_CHECK`

The better this handoff is, the more stable the later closure layer becomes.

---

## Non-Goals

This specification does not require the check-execution layer to be:

- a full autonomous agent policy
- a direct definition of provider-specific tool APIs
- a final reasoning or decision layer
- a user-facing report generator
- a guarantee that all planned checks are executable in every run

Its role is narrower:

- consume the current debug plan
- realize selected `CODE_CHECK` and `DEVICE_CHECK` items through available capability domains
- acquire and package evidence
- preserve execution outcomes
- hand structured state to later evaluation

---

## Relationship to Other Specifications

This document should be read together with:

- `simple-rla.md`
  for the top-level system structure

- `analysis-flow.md`
  for the analysis-layer constraints

- `debug-plan.md`
  for the semantics and output structure of the debug-plan layer

- future closure / decision specifications
  for evidence-based synthesis and final outcome handling

Together, these documents define the path from:
- issue analysis
- to debug planning
- to check execution
- to evidence-based closure

---

## Conclusion

The check-execution layer exists to turn planned `CODE_CHECK` and `DEVICE_CHECK` items into traceable evidence-producing actions.

It is not merely a tool-usage phase, and it is not the final reasoning layer.

Its purpose is to consume the current `DEBUG_PLAN`, realize its checks through available capability domains, preserve explicit execution outcomes, and return structured evidence that can support later evaluation, revision, and outcome classification.

That is what makes the system a true reasoning-action-evidence loop rather than a one-shot planning workflow.
