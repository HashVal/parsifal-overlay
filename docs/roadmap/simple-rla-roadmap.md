# Simple RLA Roadmap

This document defines the milestone structure for `simple-rla`.

It captures the milestone goals, success conditions, and scope boundaries that were previously tracked in `simple-rla/TODO.MD`, but separates those definitions from day-to-day execution status.

---

## Milestone 1 — Pure LLM step

### Goal
Enable the new skeleton runtime to execute a real `llm_step` without tools.

### Success condition
A workflow can:
- load from a new structured YAML
- run a deterministic step
- run a no-tool `llm_step`
- parse and validate model output
- return a structured `StepResult`
- complete a phase through `workflow_runtime.py`

---

## Milestone 2 — Tool-enabled LLM step

### Goal
Enable `llm_tool_step` so the model can call MCP tools inside a step-local loop, using a new MCP stdio client and a unified `example.toml` config.

### Success condition
A step can:
- load runtime + MCP configuration from `example.toml`
- launch local MCP servers through the new `mcp_client.py`
- discover tool schemas
- request tool calls
- execute MCP tools
- receive tool results back into model context
- terminate with valid structured output

### Scope
This milestone includes:
- unified runtime and MCP config
- MCP client integration
- tool registry / permission / execution path
- tool-enabled step execution loop
- runtime wiring for tool-enabled workflow execution

This milestone does not include:
- bounded repair loop
- trace persistence
- checkpoint persistence
- full artifact store / compaction layer
- distributed execution
- multiple MCP transports

---

## Milestone 2.5 — Analysis work beyond M2

### Goal
Record the major analysis/runtime capabilities that were implemented on top of the M2 foundation, but were not part of the original M2 contract.

### Scope
This milestone captures extra completed work such as:
- analysis-oriented multi-step workflow extensions
- model output robustness improvements
- workflow observability improvements
- richer log evidence extraction support
- handoff artifact bundling support

This milestone exists to separate:
- the original M2 runtime goal
- the later analysis-driven expansions built on top of it

---

## Milestone 3 — Repair, trace, checkpoint

### Goal
Make the new runtime debuggable and bounded when model output is invalid or unstable.

### Success condition
When a step produces invalid structured output:
- runtime can perform bounded repair
- trace records what happened
- step/phase/workflow dumps are persisted

### Scope
This milestone is expected to cover:
- repair control
- trace event persistence
- checkpoint persistence
- validation classification for repairability
- workflow/runtime integration of repair and checkpoint hooks

---

## Milestone 4 — Artifact selection and compaction

### Goal
Define and implement the next-stage artifact management model for visibility, handoff, and compaction.

### Expected direction
This milestone is expected to cover:
- artifact visibility boundaries
- artifact selection for downstream reasoning
- artifact compaction / bundling rules
- handoff shaping between phases
- clearer separation between transport artifacts and semantic artifacts

---

## Notes

This roadmap document is intentionally definition-oriented.

It describes:
- what each milestone means
- what success looks like
- what belongs in scope

It does not try to serve as the live execution checklist.

For current implementation state, completed work, pending items, and follow-up checks, see:
- `docs/roadmap/simple-rla-status.md`
