# Simple RLA Status

This document tracks the current execution status of `simple-rla` milestones.

Unlike `docs/roadmap/simple-rla-roadmap.md`, which defines milestone intent and scope, this file focuses on what is currently done, what still needs follow-up, and what remains ahead.

---

## Current overall status

`simple-rla` is currently in an “M2 complete, M2.5 completed beyond original scope” state.

The core M2 runtime goal has been reached in practice:
- unified config via `example.toml`
- MCP-based tool execution through the new runtime path
- `llm_tool_step` support
- tool schema discovery and execution loop
- tool-enabled workflow execution with structured outputs

Additional work beyond the original M2 scope has also been completed and is tracked as M2.5.

---

## Milestone 1

### Status
- DONE

### Notes
- Pure `llm_step` execution path was established as the initial skeleton runtime baseline.

---

## Milestone 2

### Status
- DONE (core milestone)
- FOLLOW-UP ITEMS REMAIN

### Done
- unified config via `example.toml`
- MCP client path established through `mcp_client.py`
- tool registry / permission / executor path wired into runtime
- tool-enabled step execution path implemented
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

## Milestone 2.5

### Status
- DONE

### Completed work beyond original M2 scope
- analysis-oriented multi-step workflow in `runloop_agent/demo.yaml`
- component scope extraction
- platform context normalization
- cross-layer conflict extraction
- root cause proposal
- evidence chain derivation
- handoff artifact bundling support
- model output robustness improvements in `output_parser.py`
- workflow observability improvements
- richer log evidence extraction support

### Notes
- M2.5 is used to make clear that these items are real completed work, but were not part of the original M2 definition.

---

## Milestone 3

### Status
- TODO

### Planned work
- repair controller
- trace store
- checkpoint store
- bounded repair loop
- validation failure classification
- trace / checkpoint integration into runtime boundaries

---

## Milestone 4

### Status
- TODO

### Planned work
- artifact visibility model refinement
- artifact selection rules
- compaction / bundling strategy
- handoff shaping between phases

---

## Current priorities

The current near-term priorities are:
- continue organizing repo-level documentation under `docs/`
- clarify which documents are repo-level vs local to `simple-rla`
- preserve the distinction between milestone definition and milestone execution status

---

## Source note

This file was derived from the milestone/status portions of the former `simple-rla/TODO.MD`, but intentionally reorganizes them into a status-focused document.
