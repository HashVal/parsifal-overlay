# Tristan Debug Agent MVP Spec

This directory contains the Tristan MVP specification set for a structured multi-stage debug agent focused on new hardware platform Linux kernel bring-up, adaptation, and stability debugging.

The goal of this spec set is not to define every future capability up front.
The goal is to make the MVP:
- reviewable
- mechanically constrained
- progressively disclosed
- easy to compare against a real implementation

---

## Files in This Directory

### `README.md`
Directory guide and reading map.

Use this to understand:
- what each document in this directory is for
- what order to read them in
- what has already been settled versus what remains open

This is the directory index and navigation layer.

---

### `data-model.md`
High-level data model sketch.

Use this to understand the architectural intent:
- canonical `CaseState`
- agent views
- patches
- separation of facts, hypotheses, plan, execution, and decision

This is the conceptual starting point.

---

### `data-model-schema.md`
MVP JSON Schema for the `CaseState` object.

Use this to understand:
- what fields exist
- how the `CaseState` is structured
- which fields are required
- which constraints are structural rather than semantic

This is the structural contract.

---

### `data-model-semantics.md`
Semantic companion document for the schema.

Use this to understand:
- what fields mean
- what common ambiguities were identified during review
- what rules should be enforced by harness logic rather than plain JSON Schema
- how to interpret cross-field consistency

This is the meaning and policy layer.

---

### `mvp-semantic-validator-checklist.md`
Implementation-oriented validator checklist.

Use this when building the harness-side semantic validator.
It translates the semantics document into a concrete validation checklist.

This is the validation layer.

---

### `case-state-examples.md`
Small positive and negative `CaseState` examples.

Use this to:
- compare implementation output against intended shape
- create regression fixtures
- test schema + semantic validation behavior

This is the examples and fixture layer.

---

### `agent-profiles.md`
Per-agent responsibility and ownership model for the four core agents.

Use this to understand:
- what Intake / Hypothesis / Probe / Judge each do
- what each agent should read
- what each agent may update
- where ownership boundaries sit before formal patch schema

This is the agent-boundary layer.

---

### `patch-contract.md`
Per-agent patch contract and merge-style document.

Use this to understand:
- what each patch type is allowed to touch
- which layers are append / merge / replace / harness-reflected
- the intended update style before full schema formalization

This is the patch-policy layer.

---

### `patch-json.md`
Concrete JSON-shape document for the four per-agent patch types.

Use this to understand:
- the common patch envelope
- what `IntakePatch`, `HypothesisPatch`, `ProbePatch`, and `JudgePatch` look like
- how the ownership model is intended to land at interface shape level

This is the patch-shape layer.

---

## Recommended Reading Order

If you are new to the spec:

1. `data-model.md`
2. `data-model-schema.md`
3. `data-model-semantics.md`
4. `mvp-semantic-validator-checklist.md`
5. `case-state-examples.md`

Why this order:
- first understand the architecture
- then understand the structure
- then understand the meaning
- then understand validation
- then look at concrete examples

---

## Spec Philosophy

This MVP spec follows a few strong principles.

### 1. Separate layers
Do not mix:
- facts
- hypotheses
- plan
- execution
- decision

Each layer exists for a different purpose and should remain auditable.

### 2. Prefer self-consistent MVP over premature abstraction
If a future design is elegant but makes MVP harder to review or validate, MVP should prefer the more explicit and self-contained choice.

Examples:
- inline evidence items instead of a full evidence graph
- explicit semantic validator rules instead of hiding everything in prompt behavior

### 3. Structural constraints and semantic constraints are different
JSON Schema is necessary but not sufficient.

- Schema enforces shape
- semantics defines meaning
- validator rules enforce cross-field logic

### 4. Progressive disclosure matters
The long-term harness design assumes:
- one canonical case state
- different views for different agents
- restricted write paths per agent

This MVP spec does not yet fully encode all view/patch schemas, but it is designed to support them.

---

## Current MVP Scope

The MVP currently focuses on:
- the `CaseState` model and its semantics
- agent ownership and read/write boundaries
- per-agent patch contract and first patch-shape drafts

It includes:
- `meta`
- `issue`
- `facts`
- `anomalies`
- `hypotheses`
- `plan`
- `execution`
- `decision`
- `history`
- agent profile documentation
- patch contract documentation
- patch JSON draft documentation

It does **not yet** fully formalize:
- full evidence graph model
- per-agent view schemas
- final JSON Schema for per-agent patches
- harness merge/validation rules as a standalone spec
- fully enumerated tool registry
- per-tool input sub-schemas
- cross-case linkage

These are expected future extensions, not MVP requirements.

---

## Recommended Reading Order

If you are new to the full current spec set, the recommended order is:

1. `data-model.md`
2. `data-model-schema.md`
3. `data-model-semantics.md`
4. `mvp-semantic-validator-checklist.md`
5. `case-state-examples.md`
6. `agent-profiles.md`
7. `patch-contract.md`
8. `patch-json.md`

Why this order:
- first understand the architecture
- then understand the structure
- then understand the meaning
- then understand validation
- then look at concrete examples
- then read ownership and patch behavior
- then read patch contract and patch shapes

---

## Recommended Implementation Order

If implementing from scratch, the recommended order is:

1. implement JSON Schema validation for `CaseState`
2. implement semantic validator rules from the checklist
3. wire up canonical `CaseState` production and persistence
4. compare live agent outputs against the examples
5. implement agent ownership boundaries and patch contracts
6. only then formalize patch schemas and harness merge logic

This ordering reduces drift and prevents prompt-only workflow logic from becoming the de facto contract.

---

## Current Review Status

At the time this README was updated, the following have already been reviewed and substantially tightened:
- `meta`
- `facts`
- `hypotheses`
- `plan`
- `execution`
- `decision`
- cross-field semantic rules
- four-agent ownership model
- per-agent patch contract
- first draft of per-agent patch JSON shapes

---

## TODO

Likely next work after this stage:
- do another cross-document consistency pass
- formalize patch JSON documents into schema if the current set feels stable enough
- write standalone harness merge/validation rules
- write per-agent view schemas if view construction needs to become explicit
