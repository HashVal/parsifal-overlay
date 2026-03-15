# TODO.MD

# File creation / modification plan derived from BLUE_PRINT.MD

This file translates the replacement-track blueprint into a staged implementation plan.

## Global constraints

- Do **not** modify `workflow_config.py`
- Do **not** modify `openai_fc.py`
- Do **not** modify `openai_responses.py`
- Do **not** design new modules around compatibility with them
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

---

## Create

### 1. `workflow_loader.py`
- [ ] define YAML loading entrypoint
- [ ] validate top-level workflow shape
- [ ] normalize phase / step config
- [ ] build `WorkflowSpec`
- [ ] call `phase_factory.py` and `step_factory.py`

### 2. `phase_factory.py`
- [ ] define phase type registry
- [ ] support at least `standard_phase`
- [ ] build phase objects from normalized config
- [ ] inject phase-level attempt / rollback policy

### 3. `step_factory.py`
- [ ] define step type registry
- [ ] support at least:
  - [ ] `deterministic_step`
  - [ ] `llm_step`
- [ ] build `StepSpec`
- [ ] instantiate step objects

### 4. `schema_defs.py`
- [ ] define workflow YAML schema contract
- [ ] define step config schema contract
- [ ] define minimal structured LLM output schema contract

### 5. `model_provider.py`
- [ ] define provider-facing model invocation interface for the new runtime
- [ ] implement one minimal provider backend
- [ ] normalize provider result into new runtime-native response objects

### 6. `prompt_builder.py`
- [ ] define prompt/message assembly interface
- [ ] build step-visible prompt from:
  - [ ] workflow / phase / step identity
  - [ ] step instruction
  - [ ] selected artifacts
  - [ ] attempt / transition metadata
  - [ ] output contract
- [ ] default to compact context form

### 7. `llm_step.py`
- [ ] add `LLMStep`
- [ ] connect `LLMStep.run(...)` to `step_runner.py`
- [ ] keep `build_prompt(...)` delegating to `prompt_builder.py`

### 8. `step_runner.py`
- [ ] define step-local model execution loop for no-tool execution
- [ ] call `prompt_builder.py`
- [ ] call `model_provider.py`
- [ ] call `output_parser.py`
- [ ] call `step_validator.py`
- [ ] return structured step execution result to `llm_step.py`

### 9. `output_parser.py`
- [ ] parse structured model output
- [ ] support raw text / JSON extraction path
- [ ] return parse diagnostics

### 10. `step_validator.py`
- [ ] validate structure against step output schema
- [ ] validate minimal semantic completeness
- [ ] produce validation decision object

---

## Modify

### 11. `step.py`
- [ ] extend `StepSpec` with declarative fields needed for LLM steps
  - [ ] `step_type`
  - [ ] `instruction`
  - [ ] `output_schema`
  - [ ] `required_artifacts`
  - [ ] `artifact_selection`
  - [ ] `max_model_turns`
  - [ ] `max_tool_calls`
  - [ ] `repair_attempts`
  - [ ] `timeout_seconds`
  - [ ] `compact_policy`
- [ ] extend `StepContext` with richer runtime metadata
- [ ] extend `StepResult` / `diagnostics` shape for parse + validation data

### 12. `phase.py`
- [ ] add phase-spec fields needed by structured loader/runtime
  - [ ] `required_output_artifacts`
  - [ ] `handoff_policy`
  - [ ] `artifact_visibility`
  - [ ] `phase_exit_policy`

### 13. `workflow_runtime.py`
- [ ] introduce `run_id`
- [ ] keep kernel provider-agnostic
- [ ] add hook points for future trace / checkpoint integration
- [ ] preserve current phase-step state-machine role

### 14. `workflow_demo.py`
- [ ] reduce it to demo / harness role only
- [ ] wire it to the new `workflow_loader.py`
- [ ] add a minimal demo path for `llm_step`

### 15. `demo.yaml`
- [ ] add a minimal new-format workflow example containing:
  - [ ] one deterministic step
  - [ ] one no-tool `llm_step`

---

## Out of scope for Milestone 1
- MCP tool execution
- repair loop
- checkpoint persistence
- trace persistence
- artifact store / compaction engine

---

# Milestone 2 — Tool-enabled LLM step

## Goal
Enable `llm_tool_step` so the model can call MCP tools inside a step-local loop.

## Success condition
A step can:
- receive tool schemas
- request tool calls
- execute MCP tools
- receive tool results back into model context
- terminate with valid structured output

---

## Create

### 1. `mcp_client.py`
- [ ] define MCP client abstraction for the new runtime
- [ ] support one transport initially (recommended: stdio)
- [ ] implement:
  - [ ] server/session init
  - [ ] tool discovery
  - [ ] tool invocation
  - [ ] timeout/error normalization

### 2. `tool_registry.py`
- [ ] define tool metadata model
- [ ] register tools from MCP discovery
- [ ] support filtering by:
  - [ ] `allowed_tools`
  - [ ] `allowed_tool_families`
- [ ] expose model-visible tool schema list

### 3. `tool_permission.py`
- [ ] define permission checks for tool execution
- [ ] enforce allowlist/family policy
- [ ] validate tool-call arguments against policy
- [ ] prepare for side-effect restrictions

### 4. `tool_executor.py`
- [ ] define single tool-call execution interface
- [ ] validate permission before execution
- [ ] invoke tools through `mcp_client.py`
- [ ] normalize tool result
- [ ] produce structured `StepToolCall`

---

## Modify

### 5. `step_factory.py`
- [ ] add support for `llm_tool_step`

### 6. `llm_step.py`
- [ ] add `LLMToolStep`
- [ ] allow tool-enabled step specs

### 7. `prompt_builder.py`
- [ ] include model-visible tool descriptions/schemas in step input
- [ ] clearly express tool-use constraints in prompt contract

### 8. `step_runner.py`
- [ ] add tool-call loop branch
- [ ] detect tool-call requests from model output
- [ ] dispatch to `tool_executor.py`
- [ ] append tool results into step-local conversation/context
- [ ] enforce:
  - [ ] `max_tool_calls`
  - [ ] max model turns with tools

### 9. `schema_defs.py`
- [ ] add tool metadata schema
- [ ] add tool-call result schema

### 10. `demo.yaml`
- [ ] add a minimal workflow example containing one `llm_tool_step`

### 11. `workflow_demo.py`
- [ ] add demo path for tool-enabled step execution

---

## Out of scope for Milestone 2
- bounded repair loop
- trace persistence
- checkpoint persistence
- full artifact store / compaction layer

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
- multiple MCP transports
- multiple provider backends
- distributed execution

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
- [ ] old files remain outside the new runtime main path
