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
- [ ] create a unified config file that replaces:
  - [ ] `example.runtime.toml`
  - [ ] `example.mcp.toml`
- [ ] include:
  - [ ] `[runtime]` defaults (`model`, `timeout_s`, `protocol_version`)
  - [ ] `[openai]` settings (`api_key`, `base_url`)
  - [ ] `[mcp]` settings (`artifacts_root`)
  - [ ] `[mcp.servers.*]` server launch config

### 2. `mcp_client.py`
- [ ] define the new runtime's MCP client abstraction
- [ ] implement a new stdio JSON-RPC client path for MCP
- [ ] support:
  - [ ] launching configured MCP servers
  - [ ] initialize/session setup
  - [ ] `tools/list`
  - [ ] `tools/call`
  - [ ] timeout/error normalization
  - [ ] `tool_name -> server/client` routing
- [ ] do **not** depend on `mcp_stdio_client.py` as the primary implementation path

### 3. `tool_registry.py`
- [ ] define tool metadata model
- [ ] register tools discovered through `mcp_client.py`
- [ ] support filtering by:
  - [ ] `allowed_tools`
  - [ ] `allowed_tool_families`
- [ ] infer/provide `family` when MCP server metadata does not include one
- [ ] expose model-visible tool schema list

### 4. `tool_permission.py`
- [ ] define permission checks for tool execution
- [ ] enforce allowlist/family policy
- [ ] validate tool-call arguments against policy
- [ ] prepare for side-effect restrictions

### 5. `tool_executor.py`
- [ ] define single tool-call execution interface
- [ ] validate permission before execution
- [ ] invoke tools through `mcp_client.py`
- [ ] normalize tool result
- [ ] produce structured `StepToolCall`

### 6. `step_runner.py`
- [ ] introduce step-local execution orchestration for M2+
- [ ] support no-tool and tool-enabled execution paths
- [ ] implement tool-call loop branch
- [ ] call:
  - [ ] `prompt_builder.py`
  - [ ] `model_provider.py`
  - [ ] `tool_executor.py`
  - [ ] `output_parser.py`
  - [ ] `step_validator.py`
- [ ] enforce:
  - [ ] `max_tool_calls`
  - [ ] max model turns with tools

---

## Modify

### 7. `runtime_config.py`
- [ ] upgrade from runtime-only TOML loading to unified `example.toml`
- [ ] load:
  - [ ] runtime defaults
  - [ ] openai settings
  - [ ] MCP server settings
- [ ] keep env vars able to override config values where appropriate

### 8. `step_factory.py`
- [ ] add support for `llm_tool_step`

### 9. `llm_step.py`
- [ ] add `LLMToolStep`
- [ ] move shared execution flow toward `step_runner.py`
- [ ] preserve no-tool `LLMStep` path while enabling tool loop execution

### 10. `prompt_builder.py`
- [ ] include model-visible tool descriptions/schemas in step input
- [ ] clearly express tool-use constraints in prompt contract

### 11. `schema_defs.py`
- [ ] add tool metadata schema
- [ ] add tool-call result schema
- [ ] add unified config schema notes if needed

### 12. `demo.yaml`
- [ ] add a minimal workflow example containing one `llm_tool_step`
- [ ] prefer a stable local-tool demo first (e.g. files/kb) before more complex external dependencies

### 13. `workflow_demo.py`
- [ ] switch to the unified config path (`example.toml`)
- [ ] initialize/close `mcp_client.py` for tool-enabled runs
- [ ] add demo path for tool-enabled step execution
- [ ] keep `--dump` working with tool-call results and conversation context

---

## Reuse guidance for M2

### Reuse directly
- [ ] `mcp_servers/*`

### Reuse as reference only, not as new main path
- [ ] `mcp_stdio_client.py`
- [ ] `example.mcp.toml`
- [ ] `example.runtime.toml`

---

## Out of scope for Milestone 2
- bounded repair loop
- trace persistence
- checkpoint persistence
- full artifact store / compaction layer
- distributed execution
- multiple MCP transports

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

## Goal
Introduce structured artifact management so downstream steps do not receive uncontrolled raw context.

## Success condition
- steps only see selected artifacts
- handoff defaults to compact form
- oversized raw payloads are not blindly passed forward

---

## Create

### 1. `artifact_store.py`
- [ ] define artifact metadata structure
- [ ] support store/get/list operations
- [ ] represent producer step/phase and compact/full status

### 2. `artifact_selector.py`
- [ ] define artifact selection policy per step
- [ ] select required artifacts only
- [ ] choose full vs compact vs reference exposure

### 3. `artifact_compactor.py`
- [ ] define compact-output generation policy
- [ ] summarize large outputs
- [ ] preserve key structured fields for downstream use

---

## Modify

### 4. `workflow_runtime.py`
- [ ] replace raw dictionary-only artifact handling with artifact management hooks
- [ ] integrate compact handoff at phase boundary

### 5. `step_runner.py`
- [ ] consume selected artifacts instead of blindly using full global artifact surface

### 6. `prompt_builder.py`
- [ ] rely on selected/compacted artifact input rather than raw unrestricted input

### 7. `step.py`
- [ ] align `StepContext` artifact fields with structured artifact metadata

### 8. `phase.py`
- [ ] align checkpoint / handoff logic with compact artifact model

### 9. `schema_defs.py`
- [ ] add artifact metadata schema
- [ ] add compact handoff schema

### 10. `demo.yaml`
- [ ] add a demo showing cross-phase compact artifact handoff

### 11. `workflow_demo.py`
- [ ] add a demo path that proves later steps/phases see only selected compact artifacts

---

## Deferred after Milestone 4
- full resume/recovery protocol
- advanced policy DSL
- multiple provider backends

---

# Final checklist after all milestones

## Runtime shape
- [ ] workflow kernel remains provider/tool agnostic
- [ ] execution plane owns LLM step behavior
- [ ] tool plane owns tool execution behavior
- [ ] artifact plane owns visibility/handoff behavior
- [ ] assembly plane owns YAML/spec loading behavior

## Replacement-track integrity
- [ ] no new dependency on `workflow_config.py`
- [ ] no new dependency on `openai_fc.py`
- [ ] no new dependency on `openai_responses.py`
- [ ] `mcp_stdio_client.py` remains outside the new runtime main path
- [ ] old files remain outside the new runtime main path
