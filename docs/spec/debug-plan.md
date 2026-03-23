# Debug Plan Specification

## Purpose and Scope

This document defines the specification for the debug-plan layer in `simple-rla`.

Its purpose is to specify how the system should represent, structure, and use a debugging plan after analysis and before evidence-based closure.

In particular, this document defines:

- what `DEBUG_STEPS` means in the system
- what a valid debug plan must contain
- how a plan relates to hypotheses and evidence gaps
- how checks inside the plan should be interpreted
- how plan execution relates to capability domains and tool calls
- how returned evidence should map back to the plan

This document is not a tool catalog, not a workflow YAML reference, and not an execution implementation guide.

---

## Role in the Full System

The debug-plan layer sits between analysis and evidence execution.

Its role is to convert structured analysis outputs into an actionable, evidence-oriented plan that can drive later execution and evaluation.

In the full system, the intended relationship is:

```text
analysis outputs
  -> debug plan
  -> evidence execution
  -> evidence evaluation
  -> outcome / next iteration
```

This means the debug plan is:

- downstream of observations, grounding, and hypothesis formation
- upstream of device-side and code-side evidence collection
- a required bridge between reasoning and action
- a revisable intermediate object rather than a terminal output

---

## Debug Plan Semantics

`DEBUG_STEPS` must be treated as a planning artifact, not as the final product of the system.

Its purpose is to express:

- the system’s current working explanation
- the evidence that is already known
- the evidence that is still missing
- the checks that should be executed next
- how those checks may affect the current explanatory state

`DEBUG_STEPS` must not be treated as:

- a static report appendix
- a substitute for evidence execution
- a free-form brainstorming note
- an unconstrained list of arbitrary actions
- the terminal result of `simple-rla`

A valid debug plan must remain tightly linked to:
- the active hypothesis
- the current evidence gaps
- the current case context
- the intended next reasoning cycle

---

## Inputs to Debug Plan Generation

A debug plan should be generated from structured analysis outputs rather than from broad raw-context reopening.

Typical upstream inputs may include:
- structured observations
- platform/context normalization outputs
- retrieval context
- KB grounding outputs
- root-cause proposals or working hypotheses
- evidence-chain outputs
- confidence and uncertainty statements

The debug-plan layer should prefer curated semantic inputs over raw case artifacts wherever possible.

This preserves:
- responsibility boundaries
- analysis-layer discipline
- explainability of plan generation
- stability of downstream execution

---

## Required Debug Plan Output

The debug-plan phase must produce one primary planning artifact.

The primary planning artifact is semantically a `DEBUG_PLAN`, and may be exposed externally as `DEBUG_STEPS`.

A valid output must include the following conceptual components.

### 1. Plan Context

The plan must identify the explanatory context in which it was generated.

This should include:
- case reference or equivalent run context
- active hypothesis
- optional alternative hypotheses still worth tracking
- source analysis context sufficient to explain why the plan exists

The purpose of this section is to ensure that later execution and evidence evaluation know what explanatory state the plan belongs to.

---

### 2. Current Problem Framing

The plan must express the current understanding of the issue in a way that supports action.

This should include:
- current best explanation
- key known supporting evidence
- key unresolved evidence gaps
- relevant qualifiers such as platform, branch, topology, or environment constraints where needed

This section should remain concise and action-oriented.

It must not become a substitute for the full analysis report.

---

### 3. Check Sets

The plan must define the next checks to be performed.

The current `simple-rla` model defines exactly two primary check collections in the debug plan:
- `CODE_CHECK[]`
- `DEVICE_CHECK[]`

These are the only primary check item types at the planning and execution boundary in the current model.

A plan may also depend on supporting information sources or capability domains beyond device/code execution, such as:
- KB lookups
- artifact/log extraction
- issue metadata or case-context retrieval
- environment/config inspection

These supporting capability domains are not additional peer check types. They exist only to support the realization, interpretation, or targeting of a `CODE_CHECK` or `DEVICE_CHECK`.

---

### 4. Plan-Level Execution Guidance

The plan should include enough structure for later execution and evaluation layers to understand:

- which checks are highest priority
- which checks are prerequisites for others
- what kinds of blockers are already known
- what kinds of outcomes would justify stopping
- what kinds of outcomes would force revision

This guidance exists to support bounded execution rather than endless expansion.
It expresses execution-oriented guidance, not realized execution state.

---

### 5. Output Boundaries

The debug-plan output must not be treated as:
- final RCA
- a pure prose note
- direct tool-call encoding
- an unstructured to-do list

It is an intermediate planning object whose purpose is to drive evidence collection and support later evaluation.

---

## Check Semantics

A `Check` is a hypothesis-linked debugging action object.

A valid check must not be just a generic recommendation. It must be connected to a specific explanatory purpose.

Each check should make clear:

- why this check exists
- what uncertainty or evidence gap it addresses
- what evidence it seeks
- how the returned evidence may affect the active hypothesis
- what capability domain(s) are required to execute it

A valid check should be understandable even before it is mapped to concrete tools.

This is because a check is a planning object, not a tool call.

---

## Primary Check Classes

### `DEVICE_CHECK`

A `DEVICE_CHECK` is used when the required evidence must be gathered from a running system, device state, deployment environment, or closely related runtime context.

Typical targets may include:
- logs
- runtime state
- driver/module state
- topology or binding state
- environment or configuration state
- device-accessible diagnostics

The purpose of a device check is not “inspect the device” in the abstract. It is to obtain evidence that can validate, weaken, or reject an active hypothesis.

---

### `CODE_CHECK`

A `CODE_CHECK` is used when the required evidence must be gathered from source code, code history, branch state, symbol/caller relationships, invariants, or other repository-derived information.

Typical targets may include:
- source paths
- function relationships
- branch-specific differences
- commit presence/absence
- code-path preconditions
- interface or resource assumptions

The purpose of a code check is not “inspect the codebase” in the abstract. It is to obtain evidence that can validate, weaken, or reject an active hypothesis.

---

## Supporting Capability Domains

Not every plan dependency should be modeled as a primary check class.

Some checks may require supporting capability domains such as:
- `kb`
- `artifact-log`
- `case-context`
- `environment`

These supporting capability domains exist because some useful next actions may require:
- retrieving additional KB context
- extracting additional structure from artifacts/logs
- re-reading issue metadata or attachment metadata
- inspecting environment/config facts

These domains should be treated as supporting evidence sources or execution capabilities, not as a replacement for the primary debug-plan structure.

The plan should therefore be able to express:
- the primary check class
- the supporting capability domains required for execution or interpretation

---

## Check Quality Requirements

A valid debug plan must satisfy the following quality requirements.

### 1. Checks must be hypothesis-linked
Every check must connect back to:
- the active hypothesis
- an alternative hypothesis
- or a specific unresolved evidence gap

Checks without explanatory linkage are not valid plan objects.

### 2. Checks must be evidence-oriented
A check must seek evidence, not merely name a topic area.

For example, “inspect display pipeline” is too vague by itself.
A valid check must imply what evidence is expected and why it matters.

### 3. Checks must remain bounded
A check must not expand into unrestricted exploration of a subsystem without a hypothesis-linked reason.

### 4. Checks must distinguish support from contradiction
A check should make clear which types of outcomes would:
- support the current hypothesis
- weaken it
- or redirect the investigation

### 5. The plan must separate execution channels when relevant
Where both device-side and code-side evidence are important, the plan must keep them explicitly separated.

This allows later execution and evidence evaluation to remain interpretable.

---

## Relationship Between Checks and Tool Calls

A check is not the same as a tool call.

### Check
A check is a planning-layer object that expresses:
- intent
- hypothesis linkage
- evidence need
- expected interpretation

### Tool Call
A tool call is an execution-layer realization of some or all of that check.

One check may map to:
- one tool call
- multiple tool calls
- a sequence of tool calls across different capability domains
- a blocked execution path if required capabilities are unavailable

For example:
- a KB lookup may provide supporting context needed before a device check can be interpreted
- a log-extraction call may provide structure required before a code check becomes meaningful
- a case-context lookup may refine the target of later device/code checks

This distinction is mandatory.
The debug-plan layer defines the checks.
The execution layer realizes them through concrete tool use.

---

## Evidence Mapping and Plan Feedback

Returned evidence must remain traceable to the plan that requested it.

The system must be able to answer:
- which check produced this evidence
- which hypothesis or evidence gap that check was associated with
- whether the result supports, weakens, or leaves unresolved the active explanation
- whether the check is now closed, inconclusive, blocked, or requires follow-up

Without this mapping, the plan cannot participate in a real loop.

The debug-plan object must therefore support later feedback from execution and evaluation.

---

## Plan Revision Semantics

A debug plan is revisable.

A plan may need to be revised when:
- new evidence weakens the active hypothesis
- a higher-priority evidence gap emerges
- a check returns contradictory evidence
- a capability domain is unavailable
- an execution path is blocked
- a supporting KB or artifact result changes interpretation of the next best action

A plan should therefore not be treated as immutable truth.
It is a temporary control object tied to a particular explanatory state.

---

## Terminal Relationship

A debug plan is not a terminal object.

It exists to support movement toward:
- evidence collection
- evidence-based synthesis
- explicit outcome classification
- or a justified next iteration

The plan must therefore feed into later states such as:
- refined hypothesis
- updated evidence state
- blocked state
- human-needed state
- final outcome classification

If a plan is generated but never connected to evidence execution and outcome evaluation, the system has not completed the intended loop.

---

## Non-Goals

This specification does not require the debug plan to be:

- a fully provider-specific tool schema
- a direct encoding of runtime API calls
- a free-form natural-language note
- a final user-facing report
- an unrestricted autonomous command list
- a guarantee that all checks are executable in every environment

The purpose of the debug-plan layer is narrower:
- formalize the bridge between analysis and action
- ensure checks are hypothesis-linked
- make evidence needs explicit
- support bounded execution
- enable evidence to map back into reasoning

---

## Relationship to Other Specifications

This document should be read together with:

- `simple-rla.md`
  for the top-level system specification

- `analysis-flow.md`
  for the analysis-layer boundary and visibility rules

- design documents such as `core-loop.md`
  for the higher-level reasoning-action-evidence model

- future execution or decision specifications
  for the formal treatment of execution control and terminal states

Together, these documents define:
- what the system is
- how the analysis layer works
- how a plan is formed
- how execution and evaluation are expected to use that plan

---

## Conclusion

The debug-plan layer is the bridge between understanding and action.

Its purpose is not merely to produce `DEBUG_STEPS` as text. Its purpose is to create a structured, hypothesis-linked, evidence-oriented planning object that can:

- drive device-side and code-side evidence collection
- incorporate supporting capability domains such as KB or artifact tools
- remain interpretable during execution
- accept evidence feedback
- support bounded iteration toward a final outcome

That is what makes `DEBUG_STEPS` a real system object rather than a formatted report section.
