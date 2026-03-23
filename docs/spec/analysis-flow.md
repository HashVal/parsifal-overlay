# Analysis Flow Specification

## Purpose and Scope

This document defines the analysis-layer specification for `simple-rla`.

Its purpose is to describe how analysis-oriented reasoning should be structured inside the system, with particular focus on:

- responsibility boundaries between analysis steps
- visibility rules for artifacts and inputs
- the distinction between transport artifacts and semantic artifacts
- the expected layering of analysis outputs
- how later reasoning should consume earlier analysis results

This document does not define the full system loop by itself. In particular, it does not define the complete evidence-execution or terminal-outcome model of `simple-rla`.

Instead, it specifies the analysis portion of the system: the part that transforms raw case material into structured reasoning inputs that can support hypothesis formation, planning, and later evidence closure.

---

## Analysis-Layer Intent

The analysis layer exists to turn raw case material into structured, bounded, and reusable reasoning state.

It should not behave like a free-form summarization pass over all available context.

Instead, it should:

- progressively transform raw inputs into higher-level semantic artifacts
- keep each analysis step narrow in responsibility
- minimize unnecessary visibility of unrelated upstream artifacts
- reduce prompt pollution and repeated reasoning
- produce outputs that later stages can consume without reopening the entire upstream context

The intended result is an analysis stack that is:
- layered
- explicit
- artifact-driven
- bounded by responsibility

---

## Core Principles

### 1. Narrow responsibility per analysis step
Each analysis step should do one kind of reasoning work well.

It should not casually combine:
- observation extraction
- platform normalization
- KB retrieval shaping
- root-cause reasoning
- summary generation

When these responsibilities are mixed, prompt scope expands, outputs become less stable, and downstream reasoning becomes harder to interpret.

### 2. Prefer semantic artifacts over repeated raw-context reopening
Once a useful semantic artifact has been produced, later analysis steps should prefer consuming that artifact rather than reopening all original raw materials.

This improves:
- reasoning focus
- explainability
- boundary clarity
- reproducibility

### 3. Transport artifacts are not reasoning inputs by default
Artifacts that exist mainly to move data through the system should not automatically become visible to later LLM reasoning steps.

Examples include:
- attachment URL lists
- local artifact path bundles
- lookup helper artifacts
- other workflow plumbing outputs

These may be necessary for execution, but they are usually not meaningful analysis inputs.

### 4. Visibility must follow responsibility
An analysis step should only see the artifacts required for its own role.

If a step sees too much, it may:
- repeat earlier work
- leak across intended boundaries
- overfit irrelevant details
- generate unstable outputs
- bypass the intended reasoning stack

### 5. Layering matters more than step count
The exact number of steps may change across implementations.

What must remain stable is the semantic layering:
- raw case intake
- extracted signals / observations
- platform and context normalization
- retrieval shaping
- higher-level synthesis or hypothesis support

The system may realize this through different workflow layouts, but it must preserve the layered progression.

---

## Artifact Categories

The analysis layer should distinguish at least three broad categories of artifacts.

### 1. Transport Artifacts
These artifacts exist primarily to enable workflow execution.

Typical examples:
- lookup outputs
- attachment URL lists
- downloaded file path sets
- execution-only intermediate references

These artifacts are useful for orchestration, but should not be visible to LLM analysis steps by default.

### 2. Semantic Artifacts
These artifacts carry structured reasoning state that later analysis or synthesis steps may legitimately consume.

Typical examples:
- observations
- platform context
- retrieval context
- summaries
- grounded reasoning outputs

These are the main intended inputs to later reasoning.

### 3. Handoff Artifacts
These artifacts exist to carry selected structured state across a phase or layer boundary.

A handoff artifact should:
- preserve useful structured outputs
- avoid lossy free-form summarization when unnecessary
- expose only the state actually needed downstream

Handoff artifacts are especially important when moving from one reasoning layer to another, or from analysis into later planning / execution stages.

---

## Analysis Responsibilities

The analysis layer should be decomposed into a small set of stable responsibility types.

These responsibility types may be realized by one or more concrete workflow steps.

### 1. Observation Extraction
This responsibility turns raw case artifacts into structured observations and signal statements.

It should focus on:
- what happened
- where the visible failure appears
- which symptoms are primary
- which observations are likely noise

It should not:
- normalize platform context broadly
- do KB grounding
- jump directly to final root-cause claims

### 2. Platform / Context Normalization
This responsibility structures platform-specific context and related environment qualifiers.

It should focus on:
- platform naming
- topology and binding context where relevant
- environment qualifiers
- normalized context useful for later retrieval and reasoning

It should not:
- absorb the entire observation-extraction role
- become a broad RCA step
- replace explicit later synthesis

### 3. Retrieval Shaping
This responsibility prepares analysis outputs for retrieval or grounding.

It should focus on:
- extracting search-relevant context
- flattening useful signals into retrieval-friendly form
- preserving key qualifiers for KB matching

It should not:
- redo broad platform normalization
- replace higher-level reasoning
- consume unrelated transport artifacts

### 4. KB Grounding Support
This responsibility enriches case understanding with matched prior knowledge.

It should focus on:
- mapping current observations to relevant prior knowledge
- supplying grounded vocabulary and related references
- identifying historically relevant patterns or notes

It should not:
- be treated as proof
- replace current-case evidence
- collapse directly into final RCA

### 5. Higher-Level Synthesis
This responsibility integrates earlier semantic outputs into a more structured explanatory state.

Depending on the workflow, this may include:
- case summary
- root-cause proposal
- evidence-chain proposal
- hypothesis-support structure

This layer should consume curated semantic artifacts, not reopen every upstream raw input by default.

---

## Visibility Rules

The following rules are normative for the analysis layer.

### Rule 1: Raw transport artifacts must not be exposed by default
Later LLM analysis steps must not automatically see transport-only artifacts.

They may be surfaced only when a step explicitly requires them for its responsibility.

### Rule 2: A step must not consume unrelated upstream state
If a semantic artifact already exists for a responsibility, later steps should consume that artifact instead of reopening unrelated earlier inputs.

### Rule 3: Platform-specific inputs must remain scoped
Platform inventory or platform-specific normalization inputs should only be visible to steps that are actually responsible for platform/context normalization.

They should not leak into unrelated observation steps by default.

### Rule 4: KB grounding must consume structured context, not arbitrary raw context
Grounding should prefer structured retrieval context and normalized qualifiers rather than broad raw evidence reopening.

### Rule 5: Synthesis should consume prior semantic artifacts first
A synthesis step should primarily consume earlier semantic artifacts and grounding outputs.

It should not behave as a fresh all-context re-analysis unless the workflow explicitly requires that.

---

## Stage-Transition Expectations Inside Analysis

The analysis layer should preserve a meaningful sequence of semantic states.

The following expectations are required.

### From raw case inputs to observations
The system must transform raw issue/artifact material into structured observations or signals before attempting higher-level synthesis.

### From observations to normalized context
The system must separate observed symptoms from normalized platform/environment context where that distinction matters.

### From observations/context to retrieval shaping
The system must produce retrieval-friendly structured context before broad grounding is attempted.

### From grounding inputs to synthesis inputs
The system must make grounded, curated semantic artifacts available for later synthesis rather than relying on repeated raw-context ingestion.

### From analysis to later planning/execution layers
The analysis layer must produce artifacts that are suitable for later hypothesis, planning, or evidence-oriented stages without requiring the entire raw case to be reopened by default.

---

## What This Layer Must Prevent

The analysis layer exists partly to prevent common failure modes.

It must prevent:

### 1. Raw-context collapse
A later step should not casually re-ingest everything that came before just because that information exists.

### 2. Responsibility drift
A step should not silently expand from its intended purpose into adjacent reasoning roles.

### 3. Prompt pollution
Irrelevant transport details or unrelated upstream artifacts should not pollute later reasoning context.

### 4. Unstable broad prompts
Analysis should not rely on one large prompt attempting to do observation extraction, context normalization, retrieval shaping, and RCA simultaneously.

### 5. Lossy semantic handoff
Useful structured analysis results should not be discarded and replaced by vague prose summaries when a structured handoff is possible.

---

## Relationship to the Full System

This document defines only the analysis-layer contract.

Within the larger `simple-rla` system:

- `simple-rla.md`
  defines the top-level system specification

- `analysis-flow.md`
  defines how the analysis portion should be layered and bounded

- `core-loop.md`
  explains the broader reasoning-action-evidence loop

- later planning / execution specifications
  may define how hypotheses, debug plans, evidence packs, and decisions are represented more formally

The analysis layer should therefore be understood as a bounded subsystem within the larger loop, not as the complete system by itself.

---

## Example Realization Pattern

One possible realization of this analysis specification is a workflow where:

- raw case context is acquired first
- artifact access is prepared
- log signatures and observations are extracted
- platform context is normalized separately
- retrieval context is derived from curated semantic outputs
- KB grounding consumes structured context
- higher-level synthesis steps consume semantic artifacts rather than raw plumbing outputs

This example is illustrative rather than normative.

The normative part of this specification is the set of layering, visibility, and responsibility rules defined above.

---

## Conclusion

The purpose of the analysis layer is not to “do all reasoning at once.”

Its role is to progressively convert raw case material into structured semantic state under explicit visibility and responsibility boundaries.

A valid `simple-rla` analysis flow therefore must:
- separate responsibilities
- distinguish transport artifacts from semantic artifacts
- preserve useful structured outputs
- control visibility intentionally
- produce later-consumable reasoning state rather than broad unstructured prompt context

That is what makes the analysis portion of the system stable, composable, and useful inside a larger debugging loop.
