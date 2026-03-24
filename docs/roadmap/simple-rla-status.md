# Simple RLA Status

This document tracks the current execution status of `simple-rla` milestones.

Unlike `docs/roadmap/simple-rla-roadmap.md`, which defines milestone intent and scope, this file focuses on what is currently done, what remains as follow-up, and where the project currently sits in the milestone tree.

---

## Current overall status

`simple-rla` has completed:
- Milestone 1
- Milestone 1.5
- Milestone 2
- Milestone 2.1
- Milestone 2.2
- Milestone 2.3
- Milestone 2.5

The current structure should be read as:
- M1 established the minimum runtime backbone
- M1.5 proved the backbone with a Jira intake phase example
- M2 established a tool-enabled, observable, and structured execution runtime
- M2.1 / M2.2 / M2.3 realized the current analysis phase as a layered workflow
- M2.5 records additional completed work beyond the original M2 contract and the planned M2.x split

The project has not yet entered a completed M3 state.

The current M3 definition is now centered on `Check Execution` runtime substrate work rather than the older repair/trace/checkpoint framing.

---

## Milestone 1 — Minimal runtime backbone

### Status
- DONE

### Notes
- The new runtime established the minimum workflow-loading and phase/step execution backbone.
- No-tool `llm_step` execution was proven on top of the new structured workflow model.

---

## Milestone 1.5 — Jira intake phase example

### Status
- DONE

### Notes
- A concrete Jira intake phase was realized on top of the M1 runtime backbone.
- The workflow can fetch Jira properties, select relevant attachments, download them, and emit structured intake artifacts for downstream phases.

---

## Milestone 2 — Tool-enabled, observable, and structured execution runtime

### Status
- DONE (core milestone)
- FOLLOW-UP ITEMS REMAIN

### Done
- unified config via `example.toml`
- MCP client path established through `mcp_client.py`
- tool registry / permission / executor path wired into runtime
- tool-enabled step execution path implemented
- structured runtime outputs and downstream artifact flow strengthened
- execution dump support added
- real-time stream output and prompt observability support added
- runtime/demo path updated to support tool-enabled execution

### Follow-up
- verify `tool_registry.py` family inference when MCP metadata does not include `family`
- verify `tool_permission.py` argument-level policy validation
- verify explicit enforcement of `max_tool_calls`
- verify explicit enforcement of max model turns with tools
- review whether `schema_defs.py` should more clearly carry tool metadata / tool-call result schema coverage

### Notes
- These follow-up items do not overturn the M2 milestone result.
- They are remaining completeness / hardening checks around the already achieved core runtime capability.

---

## Milestone 2.1 — Analysis signal extraction and normalization

### Status
- DONE

### Done
- structured log/signature extraction from raw attachments
- component scope extraction
- compact observation extraction
- platform / topology normalization
- retrieval-context shaping for later grounding

### Notes
- This milestone established the lower analysis substrate for the current workflow.

---

## Milestone 2.2 — Analysis grounding and hypothesis formation

### Status
- DONE

### Done
- issue summary generation from prior analysis artifacts
- cross-layer conflict extraction
- KB grounding
- constrained root-cause proposal
- evidence-chain derivation from the primary hypothesis

### Notes
- This milestone established the upper analysis substrate for the current workflow.
- It remains upstream of formal debug-plan generation and execution semantics.

---

## Milestone 2.3 — Analysis handoff and structured phase output

### Status
- DONE

### Done
- analysis-phase handoff packaging via `artifact_bundle_step`
- `artifact:summary_analysis_data` as a bounded downstream artifact
- structured phase-output discipline for later planning/execution phases

### Notes
- This milestone made the analysis phase end with an explicit handoff object rather than only loose step outputs.

---

## Milestone 2.5 — Extra work completed beyond M2

### Status
- DONE

### Completed work beyond planned milestone boundaries
- model output robustness improvements in `output_parser.py`
  - fenced JSON fallback
  - first-JSON fallback
- workflow observability improvements beyond the basic M2 contract
  - real-time stream log support
  - prompt dump support (`SIMPLE_RLA_DUMP_LLM_PROMPTS=1`)
  - prompt observability metrics in `step_runner.py`
- log evidence extraction improvements in `mcp_servers/file_tools_server_v2.py`
  - call trace frame extraction
  - dmesg timestamp normalization for trace merge/diff
  - call-trace line index fix

### Notes
- M2.5 is used to keep these completed extras visible without distorting the planned milestone tree.

---

## Milestone 3 — Check Execution runtime substrate

### Status
- NOT STARTED

### Planned direction
- establish `Check Execution` as a first-class runtime phase capability
- support `CODE_CHECK` and `DEVICE_CHECK` as the two primary check item types
- realize both check types through MCP-backed execution paths
- define structured execution-result and evidence-return models
- define check-level outcome semantics for downstream closure/evaluation

### Notes
- M3 is now framed as execution substrate work, not as the old repair/trace/checkpoint milestone.
- Concrete `CODE_CHECK` / `DEVICE_CHECK` workflow realizations are deferred to future M3.x milestones.
