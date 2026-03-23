# Parsifal Overlay Docs

This directory is the repo-level documentation source for `parsifal-overlay`.

It is intended to collect the long-lived documents that describe:

- why the project exists
- what problems it tries to solve
- how the system is designed
- what the implementation status looks like
- how engineering work is expected to evolve

In other words, `docs/` is where repo-level design, specification, planning, and process documents should live.

Project-local usage notes and subsystem-specific implementation details may still live closer to code, but the long-term documentation center of gravity should move here.

---

## Purpose

The purpose of this directory is to separate different kinds of documentation that would otherwise become mixed together inside project subdirectories.

In particular, `docs/` should carry material such as:

- design narratives
- architecture and specification documents
- implementation plans
- roadmap and milestone tracking
- documentation/process conventions
- archived historical design material

This helps keep a clear boundary between:

- **repo-level documents**
- **subproject entry documents**
- **subsystem implementation notes**
- **historical reference material**

---

## Documentation Layers

The documentation in `parsifal-overlay` should be read as a layered system.

### Design
Design documents explain:

- why a system exists
- what engineering problem it is trying to solve
- what the core design direction is
- why the design evolved from one form to another

These are not strict contracts. They are high-level technical narratives and rationale.

Examples:
- `docs/design/why-parsifal-overlay.md`
- `docs/design/why-parsifal-overlay_zh.md`

### Spec
Spec documents explain:

- what the system is supposed to do
- what the main objects, constraints, and interfaces are
- what shape a workflow, artifact, or loop should have

These should be more stable and more precise than design narratives.

Future examples may include:
- workflow model
- artifact model
- analysis-flow contract
- tool/runtime contract

### Roadmap / Status
Roadmap and status documents explain:

- what has been completed
- what remains incomplete
- what milestone a project is currently in
- what work is expected next

These documents are used to track execution progress, not just design intent.

### Process
Process documents explain:

- how documentation is organized
- how multi-language docs are named
- which document types are authoritative
- when docs should be updated together with code

These documents exist to reduce drift and ambiguity over time.

### Archive
Archive documents preserve:

- older plans
- deprecated design directions
- legacy implementation notes
- historical material that may still be useful as reference

Archive material is not the current default path unless stated otherwise.

---

## Current Document Index

This section lists the documents that are currently important to understanding the repository, including some files that still live under project subdirectories.

### Repo-level design docs
- `docs/design/why-parsifal-overlay.md`  
  High-level design narrative in English. Explains the problem context, original workflow idea, transition to ReAct-style looping, and long-term design direction.

- `docs/design/why-parsifal-overlay_zh.md`  
  Chinese version of the same high-level design narrative.

### Project entry docs
- `simple-rla/README.md`  
  Entry document for the current `simple-rla` subproject. Describes what it is, where the main runtime path is, and how the repository is currently organized from the subproject point of view.

- `simple-rla/runloop_agent/README.md`  
  Runtime-local notes for the workflow skeleton, YAML shape, step types, and entrypoint behavior.

### Planning / status docs
- `docs/roadmap/simple-rla-roadmap.md`  
  Milestone definition document for `simple-rla`, including M1, M2, M2.5, and later milestone intent/scope.

- `docs/roadmap/simple-rla-status.md`  
  Current implementation status document for `simple-rla`, including DONE, follow-up items, and future TODO milestones.

- `simple-rla/TODO.MD`  
  Original source document from which roadmap/status structure was extracted. Kept temporarily as a source/reference during the documentation transition.

### Design-target and flow docs
- `docs/spec/simple-rla.md`  
  Describes the current higher-level design target for `simple-rla`, especially the transition from report generation toward evidence-driven debugging.

- `docs/spec/analysis-flow.md`  
  Reviews step boundaries, artifact visibility, and analysis-layer responsibilities. Useful for understanding how analysis steps should be separated.

### Historical / legacy docs
- `docs/archive/simple-rla-legacy-README.old.md`  
  Notes for the archived older implementation path.

- `docs/archive/simple-rla-legacy-feature-summary-v1.old.md`  
  Summary of features and shape of the older implementation.

---

## Reading Guides

Different readers usually have different questions. The following reading paths are recommended.

### If you are new to the project
Start with:

1. `docs/design/why-parsifal-overlay.md`
2. `simple-rla/README.md`
3. `docs/roadmap/simple-rla-status.md`

This path gives you:
- the motivation
- the current implementation entrypoint
- the current execution status

### If you want to understand the current implementation
Start with:

1. `simple-rla/README.md`
2. `simple-rla/runloop_agent/README.md`
3. `simple-rla/runloop_agent/demo.yaml`

This path gives you:
- the current runtime path
- the workflow skeleton model
- the actual current workflow definition

### If you want to understand the design direction
Start with:

1. `docs/design/why-parsifal-overlay.md`
2. `docs/spec/simple-rla.md`
3. `docs/spec/analysis-flow.md`

This path gives you:
- the problem framing
- the intended future direction
- the analysis-layer design constraints

### If you want to review project status
Start with:

1. `docs/roadmap/simple-rla-roadmap.md`
2. `docs/roadmap/simple-rla-status.md`
3. `simple-rla/README.md`

This path gives you:
- milestone definitions
- current completion state
- current project layout and main path

---

## Conventions

### Repo-level vs local documentation
As a rule of thumb:

- repo-level, long-lived, cross-project documents should live under `docs/`
- subproject entry and usage documents should remain near the relevant code
- subsystem-specific notes may stay under the subsystem directory

This means `docs/` should become the main home for:
- design
- spec
- roadmap
- process
- archive

while local `README.md` files continue to document:
- project entrypoints
- runtime usage
- subsystem-local details

### Bilingual naming
The repository uses the following naming convention for bilingual documents:

- English default: `name.md`
- Chinese version: `name_zh.md`

The two versions should keep the same document scope and roughly the same section structure, but the Chinese version does not need to be a strict sentence-by-sentence translation.

### Current vs historical material
Unless explicitly noted otherwise:

- documents under `docs/` and active project directories describe the current intended path
- documents under `legacy/` or future `archive/` directories should be treated as historical reference

---

## Current Gaps in the Documentation Layout

The documentation structure is still in transition.

At the moment, some important design and status documents still live under `simple-rla/` rather than under `docs/`.

That is acceptable during the transition, but over time the repo should move toward a cleaner split:

- `docs/` for repo-level and long-lived documents
- subproject directories for local implementation and usage notes

Likely next steps include:

- further filling `docs/spec/`
- further filling `docs/roadmap/`
- adding initial process/governance documents under `docs/process/`
- deciding when to retire or replace transition-source documents still kept under `simple-rla/`

---

## Near-Term Documentation Work

The current likely next steps for documentation organization are:

- establish a first `docs/spec/` document
- establish a first `docs/roadmap/` document
- define a repo-level architecture index
- clarify which existing `simple-rla` documents should eventually migrate into `docs/`
- keep bilingual design docs aligned as the narrative evolves

---

## Summary

`docs/` is intended to be the long-term documentation home for `parsifal-overlay`.

Its role is not to replace project-local READMEs, but to give the repository a stable place for:

- design intent
- architecture and specification
- plans and milestones
- process conventions
- historical continuity

As the repository evolves, this directory should become the main entry point for understanding the project at the repo level.
