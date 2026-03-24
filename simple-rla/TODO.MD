# TODO.MD

# File creation / modification plan derived from BLUE_PRINT.MD

This file translates the replacement-track blueprint into a staged implementation plan.

## Global constraints

- Do **not** modify `workflow_config.py`
- Do **not** modify `openai_fc.py`
- Do **not** modify `openai_responses.py`
- Do **not** treat `mcp_stdio_client.py` as part of the new runtime main path
- Do **not** design new modules around compatibility with the previous runloop path
- Old implementations may be used only as reference material

---

# Milestone 1 — Minimal runtime backbone

## Goal
Establish the minimum phase/step execution backbone for the new runtime.

This milestone proves that the new runtime can load a structured workflow, execute steps through a unified phase/step model, validate structured outputs, and complete phase-level orchestration without tool use.

## Success condition
The new runtime can:

- load a workflow from the new structured YAML format
- construct phases and steps from that workflow
- execute deterministic steps
- execute a no-tool `llm_step`
- parse and validate model output
- return a structured `StepResult`
- complete a phase through `workflow_runtime.py`

## Implementation focus
- workflow loading from the new structured YAML
- phase/step construction backbone
- deterministic and no-tool `llm_step` execution paths
- structured parse / validate / result flow
- phase-level orchestration through the new runtime

## Out of scope for Milestone 1
- Jira-specific phase logic
- MCP tool execution
- KB grounding
- issue analysis
- debug planning
- check execution
- evidence closure
- repair / trace / checkpoint features

## Status
- [x] accomplished

---

# Milestone 1.5 — Jira intake phase example

## Goal
Provide a concrete phase implementation example on top of the M1 runtime backbone by realizing a Jira intake phase.

This milestone demonstrates that the runtime backbone can support a real workflow phase that fetches ticket context and prepares initial case artifacts for downstream analysis.

## Success condition
A workflow can execute a Jira intake phase that:

- resolves the target Jira case
- fetches core Jira properties
- selects relevant attachments
- downloads selected attachments
- emits structured intake artifacts for downstream phases

## Implementation focus
- Jira ticket lookup as workflow entry
- Jira property fetch / normalization
- attachment selection
- attachment download
- structured intake artifact outputs
- concrete intake-phase realization in `runloop_agent/demo.yaml`

## Example realization
Reference the Jira intake phase in `runloop_agent/demo.yaml`, including steps such as:

- `find_jira`
- `grep_jira_properties`
- `select_jira_attachments`
- `download_jira_attachments`

## Out of scope for Milestone 1.5
- full issue analysis
- KB grounding
- root-cause proposal
- debug-plan generation
- check execution
- evidence closure

## Status
- [x] accomplished

---

# Milestone 2 — Tool-enabled, observable, and structured execution runtime

## Goal
Extend the M1 runtime backbone into a tool-enabled, observable, and structured execution runtime.

This milestone establishes the runtime capabilities needed for YAML-based execution to support tool use, structured intermediate artifacts, real-time observability, and dumpable execution state.

M2 is about strengthening the runtime execution model itself. It is not yet the milestone for full debug-loop semantics such as debug-plan generation, check execution, or evidence closure.

## Success condition
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

## Implementation focus
- unified runtime + MCP configuration contract
- new MCP client abstraction and stdio execution path
- tool discovery, registration, permission, and execution
- step-local tool-call loop
- structured tool-call / tool-result flow
- structured artifact/output contract for downstream execution
- dump support for execution-state inspection
- real-time output / streaming observability
- strengthening YAML-based workflow execution for analysis-oriented flows

## Out of scope for Milestone 2
- Jira-specific workflow semantics as a milestone goal
- full debug-plan generation
- formal `CODE_CHECK` / `DEVICE_CHECK` execution semantics
- evidence-closure / terminal-outcome classification
- bounded repair / trace / checkpoint features
- distributed execution
- multiple MCP transports

## Status
- [x] accomplished

---

## Create

### 1. `example.toml`
- [x] create a unified config file that replaces:
  - [x] `example.runtime.toml`
  - [x] `example.mcp.toml`
- [x] include:
  - [x] `[runtime]` defaults (`model`, `timeout_s`, `protocol_version`)
  - [x] `[openai]` settings (`api_key`, `base_url`)
  - [x] `[mcp]` settings (`artifacts_root`)
  - [x] `[mcp.servers.*]` server launch config

### 2. `mcp_client.py`
- [x] define the new runtime's MCP client abstraction
- [x] implement a new stdio JSON-RPC client path for MCP
- [x] support:
  - [x] launching configured MCP servers
  - [x] initialize/session setup
  - [x] `tools/list`
  - [x] `tools/call`
  - [x] timeout/error normalization
  - [x] `tool_name -> server/client` routing
- [x] do **not** depend on `mcp_stdio_client.py` as the primary implementation path

### 3. `tool_registry.py`
- [x] define tool metadata model
- [x] register tools discovered through `mcp_client.py`
- [x] support filtering by:
  - [x] `allowed_tools`
  - [x] `allowed_tool_families`
- [ ] infer/provide `family` when MCP server metadata does not include one
- [x] expose model-visible tool schema list

### 4. `tool_permission.py`
- [x] define permission checks for tool execution
- [x] enforce allowlist/family policy
- [ ] validate tool-call arguments against policy
- [x] prepare for side-effect restrictions

### 5. `tool_executor.py`
- [x] define single tool-call execution interface
- [x] validate permission before execution
- [x] invoke tools through `mcp_client.py`
- [x] normalize tool result
- [x] produce structured `StepToolCall`

### 6. `step_runner.py`
- [x] introduce step-local execution orchestration for M2+
- [x] support no-tool and tool-enabled execution paths
- [x] implement tool-call loop branch
- [x] call:
  - [x] `prompt_builder.py`
  - [x] `model_provider.py`
  - [x] `tool_executor.py`
  - [x] `output_parser.py`
  - [x] `step_validator.py`
- [ ] enforce:
  - [ ] `max_tool_calls`
  - [ ] max model turns with tools

---

## Modify

### 7. `runtime_config.py`
- [x] upgrade from runtime-only TOML loading to unified `example.toml`
- [x] load:
  - [x] runtime defaults
  - [x] openai settings
  - [x] MCP server settings
- [x] keep env vars able to override config values where appropriate

### 8. `step_factory.py`
- [x] add support for `llm_tool_step`

### 9. `llm_step.py`
- [x] add `LLMToolStep`
- [x] move shared execution flow toward `step_runner.py`
- [x] preserve no-tool `LLMStep` path while enabling tool loop execution

### 10. `prompt_builder.py`
- [x] include model-visible tool descriptions/schemas in step input
- [x] clearly express tool-use constraints in prompt contract

### 11. `schema_defs.py`
- [ ] add tool metadata schema
- [ ] add tool-call result schema
- [ ] add unified config schema notes if needed

### 12. `demo.yaml`
- [x] add a minimal workflow example containing one `llm_tool_step`
- [x] prefer a stable local-tool demo first (e.g. files/kb) before more complex external dependencies

### 13. `workflow_demo.py`
- [x] switch to the unified config path (`example.toml`)
- [x] initialize/close `mcp_client.py` for tool-enabled runs
- [x] add demo path for tool-enabled step execution
- [x] keep `--dump` working with tool-call results and conversation context

---

## Reuse guidance for M2

### Reuse directly
- [x] `mcp_servers/*`

### Reuse as reference only, not as new main path
- [x] `mcp_stdio_client.py`
- [x] `example.mcp.toml`
- [x] `example.runtime.toml`

---

## Out of scope for Milestone 2
- bounded repair loop
- trace persistence
- checkpoint persistence
- full artifact store / compaction layer
- distributed execution
- multiple MCP transports

---

# Milestone 2.1 — Analysis signal extraction and normalization

## Goal
Provide the first analysis-layer realization on top of the M2 runtime by converting raw case artifacts into structured semantic analysis inputs.

This milestone establishes the lower analysis substrate: signal extraction, scope anchoring, platform normalization, and retrieval-oriented context shaping.

## Success condition
A workflow can execute an analysis segment that:

- extracts structured log/signature evidence from raw attachments
- derives component scope for the case
- extracts compact observations from visible artifacts
- normalizes platform and topology context
- produces retrieval-oriented context for later grounding

## Implementation focus
- log/signature evidence extraction
- component scope anchoring
- observation extraction
- platform / topology normalization
- retrieval-context shaping
- structured analysis artifacts for downstream reasoning

## Example realization
Reference the early analysis steps in `runloop_agent/demo.yaml`, including:

- `extract_log_signatures`
- `extract_component_scope`
- `extract_observations`
- `extract_platform_context`
- `extract_retrieval_context`

## Out of scope for Milestone 2.1
- KB grounding
- issue-level summary synthesis
- root-cause proposal
- evidence-chain derivation
- debug-plan generation
- check execution
- evidence closure

## Status
- [x] accomplished

---

# Milestone 2.2 — Analysis grounding and hypothesis formation

## Goal
Extend the analysis layer from normalized semantic artifacts into grounded explanatory reasoning.

This milestone establishes the upper analysis substrate: concise case summarization, cross-layer conflict extraction, KB grounding, constrained root-cause proposal, and evidence-chain formation.

## Success condition
A workflow can execute an analysis segment that:

- summarizes the issue from structured analysis artifacts
- extracts explicit cross-layer contradictions and policy mismatches
- grounds the case against KB context
- proposes constrained root-cause hypotheses
- derives testable evidence chains from the primary hypothesis

## Implementation focus
- issue summary generation from prior analysis artifacts
- cross-layer conflict extraction
- KB grounding
- constrained root-cause proposal
- evidence-chain derivation
- hypothesis-oriented analysis outputs for later planning

## Example realization
Reference the upper analysis steps in `runloop_agent/demo.yaml`, including:

- `summarize_jira_issue`
- `extract_cross_layer_conflicts`
- `kb_ground_case`
- `propose_root_cause`
- `extract_evidence_chains`

## Out of scope for Milestone 2.2
- formal debug-plan generation
- `CODE_CHECK` / `DEVICE_CHECK` execution semantics
- evidence-based closure
- terminal outcome classification
- repair / trace / checkpoint features

## Status
- [x] accomplished

---

# Milestone 2.3 — Analysis handoff and structured phase output

## Goal
Provide explicit analysis-phase handoff packaging so downstream phases can consume a bounded structured artifact instead of uncontrolled upstream state.

This milestone establishes the phase-output boundary for the analysis layer.

## Success condition
A workflow can:

- collect key analysis outputs into a structured handoff artifact
- preserve the minimum downstream-useful analysis state
- expose a bounded phase-level output for later planning or execution phases

## Implementation focus
- structured bundling of analysis outputs
- phase-level handoff artifact design
- downstream-friendly bounded artifact packaging
- explicit analysis-phase output contract

## Example realization
Reference the handoff step in `runloop_agent/demo.yaml`, including:

- `summary_analysis_data`
- `artifact_bundle_step`
- `artifact:summary_analysis_data` as the analysis-phase handoff artifact

## Out of scope for Milestone 2.3
- debug-plan generation itself
- check execution realization
- evidence closure
- terminal outcome classification

## Status
- [x] accomplished

---

# Milestone 2.5 — Extra work completed beyond M2

## Goal
Record major capabilities that were completed on top of the M2 foundation, but were not part of the original M2 contract or the planned M2.1 / M2.2 / M2.3 analysis split.

## Status
- [x] accomplished

## Completed extras
- [x] model output robustness improvements in `output_parser.py`
  - [x] fenced JSON fallback
  - [x] first-JSON fallback
- [x] workflow observability improvements beyond the basic M2 contract
  - [x] real-time stream log support
  - [x] prompt dump support (`SIMPLE_RLA_DUMP_LLM_PROMPTS=1`)
  - [x] prompt observability metrics in `step_runner.py`
- [x] log evidence extraction improvements in `mcp_servers/file_tools_server_v2.py`
  - [x] call trace frame extraction
  - [x] dmesg timestamp normalization for trace merge/diff
  - [x] call-trace line index fix

## Notes / reminder
- The following original M2 items are still not clearly complete and should be re-checked before declaring full closure:
  - [ ] `tool_registry.py`: family inference when MCP metadata lacks `family`
  - [ ] `tool_permission.py`: argument-level tool-call policy validation
  - [ ] `step_runner.py`: explicit enforcement of `max_tool_calls`
  - [ ] `step_runner.py`: explicit enforcement of max model turns with tools
  - [ ] `schema_defs.py`: tool metadata / tool-call result schema coverage

---

# Milestone 3 — Repair, trace, checkpoint

## Goal
Make the new runtime debuggable and bounded when model output is invalid or unstable.

## Success condition
When a step produces invalid structured output:
- runtime can perform bounded repair
- trace records what happened
- step/phase/workflow dumps are persisted

---

## Create

### 1. `repair_controller.py`
- [ ] define repair-decision interface
- [ ] convert validation errors into repair instructions
- [ ] bound repair count
- [ ] tell `step_runner.py` whether to retry or terminate

### 2. `trace_store.py`
- [ ] define trace event structure
- [ ] implement JSONL trace writer
- [ ] support events for:
  - [ ] workflow start/end
  - [ ] phase start/end
  - [ ] step start/end
  - [ ] model turn
  - [ ] tool call
  - [ ] tool result
  - [ ] parse result
  - [ ] validation result
  - [ ] repair event
  - [ ] checkpoint event

### 3. `checkpoint_store.py`
- [ ] define checkpoint persistence interface
- [ ] save phase checkpoint
- [ ] save workflow checkpoint
- [ ] optionally save step dump
- [ ] use local JSON files in v1

---

## Modify

### 4. `step_runner.py`
- [ ] integrate `repair_controller.py`
- [ ] support bounded repair loop
- [ ] emit trace events at turn / parse / validation / repair points

### 5. `step_validator.py`
- [ ] classify validation failures into:
  - [ ] accepted
  - [ ] repairable
  - [ ] blocking

### 6. `workflow_runtime.py`
- [ ] add trace hook calls at workflow / phase / step boundaries
- [ ] trigger checkpoint persistence on phase completion
- [ ] trigger workflow checkpoint on finalize

### 7. `step.py`
- [ ] ensure `StepResult` / diagnostics can carry repair and usage metadata cleanly

### 8. `phase.py`
- [ ] ensure phase checkpoint metadata can carry trace/checkpoint references if needed

### 9. `workflow_demo.py`
- [ ] add a demo path that intentionally produces invalid output once and exercises repair

---

## Out of scope for Milestone 3
- artifact visibility engine
- artifact compaction engine
- full resume/recovery protocol

---

# Milestone 4 — Artifact selection and compaction
