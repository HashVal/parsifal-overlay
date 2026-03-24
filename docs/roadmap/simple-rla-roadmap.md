# Simple RLA Roadmap

This document defines the milestone structure for `simple-rla`.

It captures milestone goals, success conditions, and scope boundaries in a roadmap-oriented form.

Use this document to understand:
- what the planned milestone tree looks like
- what each milestone is intended to establish
- how milestone boundaries relate to each other

Use `simple-rla/TODO.MD` for implementation-oriented checklist tracking and `docs/roadmap/simple-rla-status.md` for current execution status.

---

## Milestone 1 — Minimal runtime backbone

### Goal
Establish the minimum phase/step execution backbone for the new runtime.

This milestone proves that the new runtime can load a structured workflow, execute steps through a unified phase/step model, validate structured outputs, and complete phase-level orchestration without tool use.

### Success condition
The new runtime can:
- load a workflow from the new structured YAML format
- construct phases and steps from that workflow
- execute deterministic steps
- execute a no-tool `llm_step`
- parse and validate model output
- return a structured `StepResult`
- complete a phase through `workflow_runtime.py`

### Scope
This milestone establishes the runtime backbone only:
- workflow loading from the new structured YAML
- phase/step construction backbone
- deterministic and no-tool `llm_step` execution paths
- structured parse / validate / result flow
- phase-level orchestration through the new runtime

### Out of scope
- Jira-specific phase logic
- MCP tool execution
- KB grounding
- issue analysis
- debug planning
- check execution
- evidence closure
- repair / trace / checkpoint features

---

## Milestone 1.5 — Jira intake phase example

### Goal
Provide a concrete phase implementation example on top of the M1 runtime backbone by realizing a Jira intake phase.

This milestone demonstrates that the runtime backbone can support a real workflow phase that fetches ticket context and prepares initial case artifacts for downstream analysis.

### Success condition
A workflow can execute a Jira intake phase that:
- resolves the target Jira case
- fetches core Jira properties
- selects relevant attachments
- downloads selected attachments
- emits structured intake artifacts for downstream phases

### Scope
This milestone focuses on the Jira/case-intake portion of the workflow:
- Jira ticket lookup as workflow entry
- Jira property fetch / normalization
- attachment selection
- attachment download
- structured intake artifact outputs
- concrete intake-phase realization in `runloop_agent/demo.yaml`

### Example realization
Reference the Jira intake phase in `runloop_agent/demo.yaml`, including steps such as:
- `find_jira`
- `grep_jira_properties`
- `select_jira_attachments`
- `download_jira_attachments`

### Out of scope
- full issue analysis
- KB grounding
- root-cause proposal
- debug-plan generation
- check execution
- evidence closure

---

## Milestone 2 — Tool-enabled, observable, and structured execution runtime

### Goal
Extend the M1 runtime backbone into a tool-enabled, observable, and structured execution runtime.

This milestone establishes the runtime capabilities needed for YAML-based execution to support tool use, structured intermediate artifacts, real-time observability, and dumpable execution state.

M2 is about strengthening the runtime execution model itself. It is not yet the milestone for full debug-loop semantics such as debug-plan generation, check execution, or evidence closure.

### Success condition
The runtime can:
- load unified runtime and MCP configuration
- initialize and manage MCP-based tool access through the new client path
- discover and expose model-visible tool schemas
- execute tool calls inside a step-local loop
- enforce tool-use permission boundaries
- feed tool results back into model context
- emit structured step outputs and structured downstream artifacts
- support YAML-defined execution with stronger artifact/output discipline
- support execution dumps for workflow / step inspection
- support real-time output / stream visibility for LLM steps
- terminate with valid structured step output

### Scope
This milestone includes:
- unified runtime + MCP configuration contract
- new MCP client abstraction and stdio execution path
- tool discovery, registration, permission, and execution
- step-local tool-call loop
- structured tool-call / tool-result flow
- structured artifact/output contract for downstream execution
- dump support for execution-state inspection
- real-time output / streaming observability
- strengthening YAML-based workflow execution for analysis-oriented flows

### Out of scope
- Jira-specific workflow semantics as a milestone goal
- full debug-plan generation
- formal `CODE_CHECK` / `DEVICE_CHECK` execution semantics
- evidence-closure / terminal-outcome classification
- bounded repair / trace / checkpoint features
- distributed execution
- multiple MCP transports

---

## Milestone 2.1 — Analysis signal extraction and normalization

### Goal
Provide the first analysis-layer realization on top of the M2 runtime by converting raw case artifacts into structured semantic analysis inputs.

This milestone establishes the lower analysis substrate: signal extraction, scope anchoring, platform normalization, and retrieval-oriented context shaping.

### Success condition
A workflow can execute an analysis segment that:
- extracts structured log/signature evidence from raw attachments
- derives component scope for the case
- extracts compact observations from visible artifacts
- normalizes platform and topology context
- produces retrieval-oriented context for later grounding

### Scope
This milestone focuses on lower-layer analysis preparation:
- log/signature evidence extraction
- component scope anchoring
- observation extraction
- platform / topology normalization
- retrieval-context shaping
- structured analysis artifacts for downstream reasoning

### Example realization
Reference the early analysis steps in `runloop_agent/demo.yaml`, including:
- `extract_log_signatures`
- `extract_component_scope`
- `extract_observations`
- `extract_platform_context`
- `extract_retrieval_context`

### Out of scope
- KB grounding
- issue-level summary synthesis
- root-cause proposal
- evidence-chain derivation
- debug-plan generation
- check execution
- evidence closure

---

## Milestone 2.2 — Analysis grounding and hypothesis formation

### Goal
Extend the analysis layer from normalized semantic artifacts into grounded explanatory reasoning.

This milestone establishes the upper analysis substrate: concise case summarization, cross-layer conflict extraction, KB grounding, constrained root-cause proposal, and evidence-chain formation.

### Success condition
A workflow can execute an analysis segment that:
- summarizes the issue from structured analysis artifacts
- extracts explicit cross-layer contradictions and policy mismatches
- grounds the case against KB context
- proposes constrained root-cause hypotheses
- derives testable evidence chains from the primary hypothesis

### Scope
This milestone focuses on upper-layer analysis reasoning:
- issue summary generation from prior analysis artifacts
- cross-layer conflict extraction
- KB grounding
- constrained root-cause proposal
- evidence-chain derivation
- hypothesis-oriented analysis outputs for later planning

### Example realization
Reference the upper analysis steps in `runloop_agent/demo.yaml`, including:
- `summarize_jira_issue`
- `extract_cross_layer_conflicts`
- `kb_ground_case`
- `propose_root_cause`
- `extract_evidence_chains`

### Out of scope
- formal debug-plan generation
- `CODE_CHECK` / `DEVICE_CHECK` execution semantics
- evidence-based closure
- terminal outcome classification
- repair / trace / checkpoint features

---

## Milestone 2.3 — Analysis handoff and structured phase output

### Goal
Provide explicit analysis-phase handoff packaging so downstream phases can consume a bounded structured artifact instead of uncontrolled upstream state.

This milestone establishes the phase-output boundary for the analysis layer.

### Success condition
A workflow can:
- collect key analysis outputs into a structured handoff artifact
- preserve the minimum downstream-useful analysis state
- expose a bounded phase-level output for later planning or execution phases

### Scope
This milestone focuses on analysis-phase output discipline:
- structured bundling of analysis outputs
- phase-level handoff artifact design
- downstream-friendly bounded artifact packaging
- explicit analysis-phase output contract

### Example realization
Reference the handoff step in `runloop_agent/demo.yaml`, including:
- `summary_analysis_data`
- `artifact_bundle_step`
- `artifact:summary_analysis_data` as the analysis-phase handoff artifact

### Out of scope
- debug-plan generation itself
- check execution realization
- evidence closure
- terminal outcome classification

---

## Milestone 2.5 — Extra work completed beyond M2

### Goal
Record major capabilities that were completed on top of the M2 foundation, but were not part of the original M2 contract or the planned M2.1 / M2.2 / M2.3 analysis split.

### Scope
This milestone captures extra completed work such as:
- model output robustness improvements
- workflow observability improvements beyond the basic M2 contract
- richer log evidence extraction support
- other completed runtime/analysis improvements that do not fit cleanly into the main planned milestone tree

### Notes
This milestone exists to separate:
- the original M2 runtime goal
- the planned M2.1 / M2.2 / M2.3 analysis split
- additional completed work beyond those planned boundaries

---

## Milestone 3 — Check Execution runtime substrate

### Goal
Establish the technical substrate for the `Check Execution` phase.

This milestone provides the runtime-level capability needed to execute structured checks, realize them through MCP-backed tool paths, return structured execution results, and support evidence-producing execution for later phases.

M3 is about the execution substrate itself. It is not yet the milestone for concrete `CODE_CHECK` / `DEVICE_CHECK` workflow realizations.

### Success condition
The runtime can:
- represent check execution as a first-class phase capability
- support the two primary check item types:
  - `CODE_CHECK`
  - `DEVICE_CHECK`
- realize `CODE_CHECK` through MCP-backed code-side tool capabilities
- realize `DEVICE_CHECK` through MCP-backed device/runtime-side tool capabilities
- route checks through appropriate execution capability paths
- execute checks through a structured execution contract
- normalize MCP tool results into structured execution results
- return structured evidence outputs from executed checks
- represent check-level execution outcomes such as:
  - `COMPLETED`
  - `INCONCLUSIVE`
  - `BLOCKED`
  - `FAILED`
  - `DEFERRED`
- preserve traceable linkage between:
  - check identity
  - check type
  - execution result
  - returned evidence

### Scope
This milestone is intended to establish:
- the technical runtime boundary for `Check Execution`
- the minimum object model for executable checks
- MCP-backed execution affordances for `CODE_CHECK` and `DEVICE_CHECK`
- structured execution-state representation
- structured evidence packaging for later closure/evaluation
- runtime-level support for future check-execution phase implementations

### Out of scope
- concrete `CODE_CHECK` workflow steps
- concrete `DEVICE_CHECK` workflow steps
- demo-specific execution choreography
- debug-plan generation implementation
- evidence-closure implementation
- terminal outcome classification
- bounded repair / trace / checkpoint as the primary milestone goal
- full resume/recovery protocol
