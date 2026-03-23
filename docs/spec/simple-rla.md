# Simple RLA Specification

## Purpose and Scope

This document defines the top-level system specification for `simple-rla`.

Its purpose is to describe the intended structure, boundaries, and required behaviors of the system at a level above individual workflow YAML files or runtime implementation details.

In particular, this document specifies:

- what problem shape `simple-rla` is designed to handle
- what the system is expected to produce
- what the core processing stages are
- what intermediate states must exist
- what role `DEBUG_STEPS` plays in the system
- what terminal outcomes the system must be able to produce
- what the system is explicitly not trying to be

This document is a system-level specification, not a milestone checklist and not an implementation guide.

---

## System Intent

`simple-rla` is intended to be a structured debugging system for issue-driven investigation over case context, local artifacts, prior knowledge, and actively collected evidence.

Its defining shift is:

> from grounded issue analysis plus provisional debug-plan drafting  
> to hypothesis-driven debugging with evidence execution and explicit outcome classification

The key design consequence of this shift is:

> `DEBUG_STEPS` is not the terminal product of the system.  
> It is an intermediate planning artifact inside a larger evidence-seeking loop.

The system is therefore expected to support not only analysis generation, but also:
- explicit hypothesis formation
- evidence-oriented debug planning
- device-side and code-side evidence execution
- evidence-based re-evaluation
- explicit terminal outcome classification

---

## Core Processing Model

At a high level, `simple-rla` should operate as a bounded reasoning-action-evidence loop.

A simplified view of the intended model is:

```text
Case Intake
  -> Signal Extraction
  -> Knowledge Grounding
  -> Hypothesis Formation
  -> Debug Plan Generation
  -> Evidence Execution
  -> Evidence-Based Synthesis
  -> Terminal Outcome
```

This model is normative at the system level.

Specific workflows may realize this structure through different numbers of phases or steps, but they must preserve the same essential properties:
- the system must not stop at a provisional plan
- the system must form an explicit working hypothesis
- the system must be able to execute evidence-seeking actions
- the system must be able to revise or conclude based on returned evidence

---

## Processing Stages

### Stage A — Case Intake

The system must begin by obtaining sufficient case framing to decide what materials matter.

This stage is responsible for:
- retrieving case context
- identifying available artifacts
- collecting basic platform or environment hints
- selecting the first-pass artifacts needed for analysis

Primary outputs:
- case context
- artifact manifest
- local artifact paths or equivalent artifact access references

This stage must not:
- perform deep RCA
- substitute broad speculation for missing evidence
- skip directly to planning

---

### Stage B — Analysis and Hypothesis Formation

The system must transform raw case material into a grounded working explanation.

This stage is responsible for:
- extracting meaningful signals from artifacts
- identifying observations that matter
- grounding those observations with knowledge-base context
- producing an explicit working hypothesis

Primary outputs:
- signal / observation pack
- knowledge grounding context
- one primary hypothesis
- optional weaker alternatives
- evidence support and unresolved evidence gaps

This stage must not:
- collapse provisional reasoning into final RCA
- treat KB matches as proof
- skip explicit hypothesis formation

---

### Stage C — Debug Planning and Evidence Execution

The system must turn the working hypothesis into an evidence-oriented plan and then execute that plan.

This stage is responsible for:
- generating `DEBUG_STEPS`
- separating device-side and code-side evidence needs
- executing relevant evidence collection actions
- returning evidence in a form that can affect later reasoning

Primary outputs:
- structured debug plan
- device evidence pack
- code evidence pack
- failed / blocked evidence actions if relevant

This stage must not:
- treat planning as the endpoint
- generate purely topic-oriented advice without evidence purpose
- perform broad unrelated exploration detached from the active hypothesis

---

### Stage D — Evidence Closure and Outcome Classification

The system must perform a second-pass synthesis using newly collected evidence and then produce an explicit terminal outcome.

This stage is responsible for:
- integrating newly collected evidence with the active hypothesis
- revising or strengthening the explanatory state
- producing an evidence-grounded issue summary
- classifying the run into a terminal state

Primary outputs:
- evidence-grounded summary
- refined explanatory state
- explicit terminal outcome
- remaining blockers or gaps if unresolved

This stage must not:
- merely restate the provisional debug plan
- ignore new evidence that weakens the current hypothesis
- emit a final state without an evidence-based justification

---

## Required Structural Properties

The following structural properties are mandatory for `simple-rla`.

### 1. Explicit Hypothesis Formation
The system must produce an explicit working hypothesis before generating a debug plan.

A debugging plan without an explicit hypothesis is underspecified and cannot be meaningfully validated by later evidence.

### 2. `DEBUG_STEPS` as an Intermediate Artifact
`DEBUG_STEPS` must be treated as a planning artifact, not as the terminal output of the system.

Its purpose is to connect the current hypothesis to subsequent evidence collection.

### 3. Post-Plan Evidence Execution
The system must include evidence execution after plan generation.

At minimum, this must support:
- device-side evidence collection
- code-side evidence collection

Without this property, the system remains a planning/reporting tool rather than a debugging loop.

### 4. Evidence-Based Closure
The system must perform a second-pass synthesis using newly collected evidence before terminal classification.

A final state must not be emitted solely from pre-plan reasoning if later evidence was available but ignored.

### 5. Explicit Terminal Outcomes
The system must classify the run into an explicit terminal outcome rather than stopping at an untyped narrative summary.

---

## Required Intermediate States

The system must not skip certain intermediate states.

At minimum, the following states must exist before later transitions occur.

### Before hypothesis formation
The system must have:
- sufficient case context
- enough artifact access for first-pass analysis
- at least one meaningful signal or observation set

### Before debug-plan generation
The system must have:
- an explicit working hypothesis
- some supporting evidence
- some explicit evidence gaps or open uncertainties

### Before evidence execution
The system must have:
- a debug plan that separates device-side and code-side evidence actions where relevant
- actionable next checks rather than only high-level advice

### Before terminal classification
The system must have:
- an evidence-grounded synthesis
- an explicit confidence or support level
- an explicit statement of remaining blockers or uncertainty

These states may be realized by different artifacts or workflow structures, but they must exist semantically.

---

## Role of `DEBUG_STEPS`

`DEBUG_STEPS` is a required system object, but its semantics must be tightly constrained.

`DEBUG_STEPS` must be understood as:
- an execution-oriented plan derived from a current hypothesis
- a bridge between reasoning and evidence collection
- a revisable intermediate artifact
- a structure that should separate different evidence channels when needed

`DEBUG_STEPS` must not be treated as:
- the endpoint of the system
- a substitute for evidence execution
- a purely narrative report section with no action semantics

In the intended model, the system evolves through a chain closer to:

`case -> signals/observations -> grounding -> hypothesis -> DEBUG_STEPS -> evidence execution -> evidence-based synthesis -> terminal outcome`

and not:

`case -> analysis -> DEBUG_STEPS -> stop`

---

## Terminal Outcomes

`simple-rla` must be able to produce explicit terminal outcomes.

At minimum, the system must distinguish between the following result types.

### `correct_rca`
Use when:
- the main causal chain is sufficiently supported by accumulated evidence
- the explanation is stronger than a provisional hypothesis
- remaining unknowns do not invalidate the main conclusion

### `BLOCKED`
Use when:
- the next valuable step is known
- but the run cannot continue because of missing tools, permissions, environment access, device reachability, or required artifacts

### `HELP_NEEDED`
Use when:
- additional human judgment, experiment design, or domain interpretation is required
- or the current evidence is insufficient to confidently choose one explanatory direction

These terminal outcomes must remain distinct.

In particular:
- `correct_rca` must not be used for crash-surface-only understanding
- `BLOCKED` must not be collapsed into `HELP_NEEDED`
- `HELP_NEEDED` must not be used when the real issue is simple lack of access

---

## Non-Goals

`simple-rla` is not intended to be:

- an unrestricted autonomous agent
- a pure report generator
- a system that assumes every case can be resolved automatically
- a system that treats KB matches as evidence by themselves
- a patch generation pipeline by default
- a system that emits final conclusions without evidence closure

Its purpose is narrower and more practical:
- reduce repeated debugging effort
- improve evidence quality
- make hypotheses explicit
- drive useful next checks
- classify outcomes clearly
- stop safely when automation should no longer continue

---

## Notes on Realization

This specification does not require one exact workflow shape.

Different concrete workflows may realize the same system properties through:
- different numbers of phases
- different numbers of steps
- different tool choices
- different artifact layouts

However, such variations are acceptable only if the core structure remains intact:
- explicit hypothesis formation
- intermediate debug-plan semantics
- post-plan evidence execution
- evidence-based closure
- explicit terminal outcome classification

---

## Appendix: Example Realization Pattern

One valid realization pattern is a ten-step flow of the following form:

1. fetch case context
2. acquire relevant artifacts
3. extract primary failure signals
4. ground interpretation with the knowledge base
5. form an explicit possible failure reason / hypothesis
6. generate `DEBUG_STEPS`
7. execute device-side evidence collection
8. execute code-side evidence collection
9. synthesize the issue again using new evidence
10. classify the run into `correct_rca`, `BLOCKED`, or `HELP_NEEDED`

This appendix is illustrative, not the definition itself.

The normative definition is the system structure described in the sections above.
