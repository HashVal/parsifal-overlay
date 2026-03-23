# System Objects

## Purpose

This document defines the main conceptual objects used by `parsifal-overlay`.

Its purpose is not to define concrete schemas or workflow YAML syntax. Instead, it provides a shared object model for design discussions, implementation planning, and future specification work.

In particular, this document aims to clarify:

- what kinds of objects the system actually reasons about
- what kinds of objects exist only to organize execution
- what kinds of objects exist only to carry state between steps
- which concepts are easy to confuse and should be kept distinct

This document should be read as a conceptual model, not as a final interface contract.

---

## Why System Objects Matter

A debugging system quickly becomes confusing if its internal concepts are left implicit.

Without a clear object model, it becomes easy to blur important distinctions such as:

- case context vs workflow state
- signal vs observation
- hypothesis vs root cause
- check vs step
- evidence vs knowledge
- decision vs conclusion
- object vs artifact

These distinctions matter because `parsifal-overlay` is not only a workflow engine. It is also a reasoning system, an evidence collection system, and a knowledge-grounded debugging system.

To keep design and implementation aligned, the system needs a shared vocabulary.

---

## Object Layers

The objects in `parsifal-overlay` can be understood in three layers:

### 1. Domain / Reasoning Objects
These are the objects the system actually reasons about during debugging:
- `Case`
- `Signal`
- `Observation`
- `KnowledgeObject`
- `Hypothesis`
- `Check`
- `Evidence`
- `Decision`

### 2. Execution / Orchestration Objects
These are the objects used to organize and run the workflow:
- `Workflow`
- `Phase`
- `Step`
- `Run`
- `Iteration`

### 3. Representation / Transport Objects
These are the objects used to store, carry, and expose system state:
- `Artifact`
- `HandoffBundle`
- `VisibilityBoundary`

The first layer describes what the system is trying to understand.
The second layer describes how the system executes work.
The third layer describes how state is represented and passed around.

---

## Domain / Reasoning Objects

### Case

A `Case` is the external problem instance the system is trying to handle.

Typical sources include:
- Jira issues
- bug reports
- test failure reports
- externally provided debugging tasks

A case usually contains or points to:
- issue summary and description
- attachments
- platform hints
- reported symptoms
- branch or version context
- environment clues

A case is the entry object of the system. It is the source problem, not the explanation.

---

### Signal

A `Signal` is a localized piece of evidence or anomaly extracted from raw material.

Typical examples include:
- an error signature
- a call trace anchor
- a suspicious timeout line
- a version mismatch clue
- a platform-specific error marker

A signal is usually:
- narrow
- local
- directly tied to raw inputs
- useful because it suggests where attention should go

A signal is not yet a full structured statement about the case. It is closer to a meaningful evidence point.

---

### Observation

An `Observation` is a structured statement derived from one or more signals and other raw inputs.

Typical examples include:
- the failure occurs during a specific initialization phase
- the regression appears only on a particular branch
- multiple logs point to the same subsystem boundary
- the visible symptoms are inconsistent across environments

An observation is more structured than a signal. A useful mental model is:

- a signal is a point
- an observation is a statement built from points

Observations are often the immediate input to hypothesis formation.

---

### KnowledgeObject

A `KnowledgeObject` is a unit of structured prior knowledge retrieved from the knowledge base.

Examples include:
- issue patterns
- platform notes
- RCA notes
- playbooks
- workaround references
- code notes

A knowledge object is not current-case evidence. It is external grounding material.

Its role is to provide:
- terminology normalization
- historical patterns
- platform-specific qualifiers
- possible failure mechanisms
- hints about useful next checks

Knowledge objects must remain distinct from evidence collected from the current case.

---

### Hypothesis

A `Hypothesis` is the system’s current working explanation of the case.

It is not final truth. It is the current best explanation that is useful enough to guide further action.

A hypothesis should make explicit:
- what the system currently believes
- why it believes that
- what evidence supports it
- what evidence is still missing
- which alternatives remain alive
- how confident the system currently is

A hypothesis is one of the central objects of the entire loop. Without it, checks lose purpose and evidence cannot be evaluated against anything explicit.

A hypothesis should be distinguished from a root cause:
- a hypothesis is provisional
- a root cause is a later, more settled explanatory result

---

### Check

A `Check` is a debugging action generated to validate, weaken, or reject a hypothesis.

Checks are the main action objects in the system.

At minimum, the system distinguishes:
- `DEVICE_CHECK`
- `CODE_CHECK`

A check should not be mere generic advice. It should be linked to:
- a specific hypothesis
- a specific uncertainty
- a specific evidence need

A useful check implies:
- why it exists
- what evidence it seeks
- how outcomes should affect the current hypothesis

Checks are conceptually different from workflow steps. A check belongs to the reasoning domain; a step belongs to execution structure.

---

### Evidence

`Evidence` is the material returned from checks or other evidence-gathering actions.

Typical examples include:
- fresh runtime logs
- device state facts
- module or driver status
- code-path findings
- branch-specific code differences
- commit, symbol, or reference results

Evidence is what allows a hypothesis to be strengthened, weakened, rejected, or revised.

Evidence should be distinguished from observations:
- evidence is material gathered or cited
- observation is a structured statement made from evidence and signals

One observation may be supported by multiple pieces of evidence. One piece of evidence may support multiple observations or hypotheses.

---

### Decision

A `Decision` is the loop-level outcome at the end of an iteration.

It expresses what the system should do next, rather than merely what it currently believes.

Typical decisions include:
- confirm
- revise
- blocked
- human-needed
- exhausted

A decision is different from a narrative conclusion. A conclusion is part of human-facing output; a decision is part of control flow.

This object is what keeps the loop bounded.

---

## Execution / Orchestration Objects

### Workflow

A `Workflow` is the top-level execution structure that defines how a case is processed.

It specifies:
- which phases exist
- how they are ordered
- where execution begins
- how execution transitions between stages

A workflow is not itself a debugging concept. It is the structure that organizes the processing of debugging concepts.

---

### Phase

A `Phase` is a grouping unit inside a workflow.

It clusters related steps into a larger execution stage, such as:
- intake
- analysis
- evidence execution
- summarization
- closure

A phase helps organize execution boundaries, but it should not be confused with reasoning objects such as hypotheses or evidence.

---

### Step

A `Step` is the smallest execution unit in the current workflow model.

A step typically:
- consumes visible inputs or artifacts
- performs one kind of work
- emits new artifacts or state updates

Examples include:
- a tool step
- an LLM step
- an LLM tool step
- a deterministic step

A step is not the same as a check:
- a step is an execution unit
- a check is a debugging action object produced or consumed within that execution

---

### Run

A `Run` is a concrete execution instance of a workflow against a case.

A run includes:
- one case context
- one workflow path
- one artifact set
- one execution history

Multiple runs may exist for the same case under different configurations or at different times.

---

### Iteration

An `Iteration` is one reasoning-action-evidence cycle within a run.

It should not be assumed to equal:
- one step
- one phase
- one artifact

An iteration is a logical loop unit, not necessarily a direct runtime unit.

This distinction matters because the conceptual debugging loop may span multiple phases and steps.

---

## Representation / Transport Objects

### Artifact

An `Artifact` is a structured representation of some system state that is stored, passed between steps, or made visible to later execution.

Artifacts may represent:
- observations
- hypotheses
- evidence packs
- summaries
- handoff bundles
- intermediate structured outputs

An artifact is not itself a domain object. It is the representation of one or more domain objects in workflow-executable form.

This distinction is important:
- object = semantic concept
- artifact = carried representation

---

### HandoffBundle

A `HandoffBundle` is a special artifact used to move selected structured state from one phase or layer to another.

Its purpose is to:
- preserve important outputs without lossy summarization
- control which information is carried forward
- make phase boundaries explicit

A handoff bundle is especially useful when downstream reasoning should consume curated structured outputs rather than reopen all raw upstream context.

---

### VisibilityBoundary

A `VisibilityBoundary` is the rule or mechanism that determines which artifacts are visible to which later steps.

This object exists because not every downstream step should see every upstream result.

Visibility boundaries help enforce:
- responsibility separation
- context hygiene
- reduced prompt pollution
- explicit handoff design

Visibility is not a domain concept, but it strongly shapes the quality of reasoning.

---

## Relationships Between Objects

At a high level, the object flow looks like this:

```text
Case
  -> Signals
  -> Observations
  + KnowledgeObjects
  -> Hypothesis
  -> Checks
  -> Evidence
  -> Decision
```

These domain objects are then organized by execution objects:

```text
Workflow
  -> Phases
  -> Steps
  -> Artifacts
  -> Run
  -> Iterations
```

A more complete view is:

- a `Case` provides the source problem
- `Signals` are extracted from raw case material
- `Observations` structure those signals into usable statements
- `KnowledgeObjects` ground interpretation with prior knowledge
- a `Hypothesis` provides the current explanation
- `Checks` are generated from the hypothesis and its evidence gaps
- `Evidence` returns from executing those checks
- a `Decision` determines the next loop action
- `Artifacts` carry these states across workflow execution
- `Workflow`, `Phase`, and `Step` organize how this all runs
- `Run` and `Iteration` locate the process in time and execution history

---

## First-Class vs Supporting Objects

Not all objects are equally central.

### First-class loop objects
These define the core debugging loop:
- `Hypothesis`
- `Check`
- `Evidence`
- `Decision`

These are the objects that make the system a real reasoning-action-evidence system rather than a pure report generator.

### Supporting reasoning objects
These provide the materials from which loop state is formed:
- `Case`
- `Signal`
- `Observation`
- `KnowledgeObject`

### Execution objects
These organize the processing of the system:
- `Workflow`
- `Phase`
- `Step`
- `Run`
- `Iteration`

### Representation objects
These carry structured state across the workflow:
- `Artifact`
- `HandoffBundle`
- `VisibilityBoundary`

---

## Important Distinctions

### Case vs Run
- `Case` is the external problem instance
- `Run` is one execution instance handling that case

### Signal vs Observation
- `Signal` is a localized evidence point
- `Observation` is a structured statement built from one or more signals

### KnowledgeObject vs Evidence
- `KnowledgeObject` comes from the KB
- `Evidence` comes from the current case or active checks

### Hypothesis vs Root Cause
- `Hypothesis` is provisional and loop-active
- `Root cause` is a later, more settled explanatory result

### Check vs Step
- `Check` is a debugging action object
- `Step` is an execution unit in the workflow engine

### Phase vs Iteration
- `Phase` is an execution grouping
- `Iteration` is a logical loop cycle

### Object vs Artifact
- an `Object` is a semantic concept
- an `Artifact` is its workflow-visible representation

### Decision vs Conclusion
- `Decision` controls what happens next
- `Conclusion` communicates what has been learned

---

## Relationship to Other Documents

This document should be read alongside:

- `why-parsifal-overlay.md`
  for the motivation and high-level problem framing

- `core-loop.md`
  for the intended reasoning-action-evidence loop

- `system-objects.md`
  for the conceptual object model described here

- `artifact-strategy.md`
  for how these objects should be represented, exposed, and handed off in workflow form

Together, these documents describe:
- why the system exists
- how the loop works
- what the system is actually operating on
- how state should move between execution stages

---

## Conclusion

`parsifal-overlay` needs more than a workflow. It needs a stable conceptual model.

The system is not only executing steps. It is operating on a set of connected objects:
- cases
- signals
- observations
- knowledge objects
- hypotheses
- checks
- evidence
- decisions

These are then organized by workflows, phases, steps, runs, and artifacts.

A clear object model makes it possible to keep reasoning, execution, and representation distinct while still connecting them into one coherent debugging system.
