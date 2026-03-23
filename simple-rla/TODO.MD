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

# Milestone 1 — Pure LLM step

## Goal
Enable the new skeleton runtime to execute a real `llm_step` without tools.

## Success condition
A workflow can:
- load from a new structured YAML
- run a deterministic step
- run a no-tool `llm_step`
- parse and validate model output
- return a structured `StepResult`
- complete a phase through `workflow_runtime.py`

## Status
- [x] accomplished

---

# Milestone 2 — Tool-enabled LLM step

## Goal
Enable `llm_tool_step` so the model can call MCP tools inside a step-local loop, using a **new MCP stdio client** and a **unified `example.toml` config**.

## Success condition
A step can:
- load runtime + MCP configuration from `example.toml`
- launch local MCP servers through the new `mcp_client.py`
- discover tool schemas
- request tool calls
- execute MCP tools
- receive tool results back into model context
- terminate with valid structured output

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

# Milestone 2.5 — Extra work completed beyond M2

## Goal
Record major analysis/runtime capabilities that were completed on top of the M2 foundation, but were not part of the original M2 contract.

## Status
- [x] accomplished

## Completed extras
- [x] analysis-oriented multi-step workflow in `runloop_agent/demo.yaml`
  - [x] `extract_component_scope`
  - [x] `extract_platform_context`
  - [x] `extract_cross_layer_conflicts`
  - [x] `propose_root_cause`
  - [x] `extract_evidence_chains`
- [x] model output robustness improvements in `output_parser.py`
  - [x] fenced JSON fallback
  - [x] first-JSON fallback
- [x] workflow observability improvements
  - [x] real-time stream log support
  - [x] prompt dump support (`SIMPLE_RLA_DUMP_LLM_PROMPTS=1`)
  - [x] prompt observability metrics in `step_runner.py`
- [x] log evidence extraction improvements in `mcp_servers/file_tools_server_v2.py`
  - [x] call trace frame extraction
  - [x] dmesg timestamp normalization for trace merge/diff
  - [x] call-trace line index fix
- [x] handoff artifact bundling support
  - [x] `artifact_bundle_step`
  - [x] `artifact:summary_analysis_data` as phase handoff bundle

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
