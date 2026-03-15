# BLUE_PRINT.MD

# Structured Workflow Runtime Blueprint (Replacement Track)

This document describes the **new structured runtime direction** for `runloop_agent/`.

It is explicitly a **replacement-track design** for the previous runloop-style implementation.

## Non-goals / constraints

This blueprint assumes:

- **Do not modify `workflow_config.py`**
- **Do not modify `openai_fc.py`**
- **Do not modify `openai_responses.py`**
- **Do not design for compatibility with them**
- Old files may serve as reference material only, but are **not part of the new runtime path**

The new design should stand on its own, using the current skeleton runtime (`step.py`, `phase.py`, `workflow_runtime.py`) as the kernel.

---

## 1. Goal

Build a new structured workflow runtime under `runloop_agent/` that can:

1. Execute workflows in `WorkflowSpec -> Phase -> Step` order
2. Drive selected steps via an LLM
3. Expose MCP tools to the LLM in a controlled way
4. Support step-local multi-turn tool-call loops
5. Validate structured outputs and run bounded repair
6. Support phase checkpoints and cross-phase handoff
7. Keep the runtime architecture **state-machine-driven**, not script-driven

This is not intended to become a giant all-in-one runner. It should remain modular and extensible.

---

## 2. Architectural layering

The new runtime should be split into five planes.

### 2.1 Workflow Kernel

Existing files:

- `step.py`
- `phase.py`
- `workflow_runtime.py`

Responsibilities:

- define Step / Phase / Workflow contracts
- maintain workflow state and transitions
- handle rerun / rollback / phase completion
- define checkpoint boundaries

This layer should remain provider-agnostic and tool-transport-agnostic.

---

### 2.2 Execution Plane

New files:

- `llm_step.py`
- `step_runner.py`
- `model_provider.py`
- `prompt_builder.py`
- `output_parser.py`
- `step_validator.py`
- `repair_controller.py`

Responsibilities:

- construct step-level model input
- call model APIs
- handle tool-call loops inside a step
- parse final model outputs
- validate outputs
- decide complete / repair / invalid / failed

This is the main replacement for the old runloop-style execution logic.

---

### 2.3 Tool Plane

New files:

- `tool_registry.py`
- `tool_executor.py`
- `tool_permission.py`
- `mcp_client.py`

Responsibilities:

- discover MCP tools
- maintain a structured tool catalog
- filter tools per step
- enforce tool permission boundaries
- execute tool calls requested by the model
- normalize tool results

---

### 2.4 Artifact & Checkpoint Plane

New files:

- `artifact_store.py`
- `artifact_selector.py`
- `artifact_compactor.py`
- `checkpoint_store.py`
- `trace_store.py`

Responsibilities:

- manage workflow artifacts structurally
- select which artifacts a step can actually see
- compact outputs for downstream handoff
- persist checkpoints and intermediate dumps
- store execution traces for debugging

---

### 2.5 Assembly Plane

New files:

- `workflow_loader.py`
- `phase_factory.py`
- `step_factory.py`
- `schema_defs.py`

Responsibilities:

- read YAML / config
- validate the workflow shape
- build `WorkflowSpec`
- map phase/step declarations to runtime objects

This plane replaces ad-hoc loader logic and should not depend on `workflow_config.py`.

---

## 3. Proposed directory shape

A target structure can look like this:

```text
runloop_agent/
  step.py
  phase.py
  workflow_runtime.py

  workflow_loader.py
  phase_factory.py
  step_factory.py
  schema_defs.py

  llm_step.py
  step_runner.py
  model_provider.py
  prompt_builder.py
  output_parser.py
  step_validator.py
  repair_controller.py

  tool_registry.py
  tool_executor.py
  tool_permission.py
  mcp_client.py

  artifact_store.py
  artifact_selector.py
  artifact_compactor.py
  checkpoint_store.py
  trace_store.py

  workflow_demo.py
  demo.yaml
```

The old files remain in the repository, but should not sit on the main path of the new architecture.

---

## 4. Core runtime model

The new runtime should be built around four core components:

1. `workflow_runtime.py`  
   Workflow / phase / step state machine kernel

2. `step_runner.py`  
   Step-local LLM execution loop

3. `tool_executor.py`  
   Controlled execution of model-requested tool calls

4. `artifact_store.py`  
   Structured management of outputs, handoff material, and context visibility

These four components form the actual replacement skeleton. Other modules are support modules around them.

---

## 5. Module blueprint

## 5.1 `workflow_loader.py`

### Purpose
Load the new workflow YAML and build `WorkflowSpec`.

### Responsibilities
- read YAML
- validate top-level workflow shape
- normalize phase/step config
- build `PhaseSpec` / `StepSpec`
- call factories to build runtime objects
- return `WorkflowSpec`

### Non-responsibilities
- not responsible for execution
- not responsible for model invocation
- not responsible for tool invocation
- not responsible for compatibility with old workflow config files

---

## 5.2 `phase_factory.py`

### Purpose
Construct phase instances from phase declarations.

### Responsibilities
- phase type registry
- instantiate phase classes
- attach phase-level policies
- build ordered step lists for a phase
- configure rollback anchors / step attempt policy / handoff policy

---

## 5.3 `step_factory.py`

### Purpose
Construct step instances from step declarations.

### Required step categories
At minimum, support:

- `deterministic_step`
- `llm_step`
- `llm_tool_step`

### Responsibilities
- map step type name -> Python class
- build `StepSpec`
- instantiate `BaseStep` subclasses

---

## 5.4 `schema_defs.py`

### Purpose
Centralize schema definitions.

### Responsibilities
At minimum:

- workflow YAML schema
- step config schema
- LLM step output schema
- tool result schema
- phase handoff schema
- checkpoint serialization schema

This avoids scattering structural contracts across loaders, prompts, validators, and runtime code.

---

## 5.5 `model_provider.py`

### Purpose
Provide the new runtime's own model invocation interface.

### Requirements
This module should define a **new** provider interface for the structured runtime. It should not mirror the shape of the old files just for compatibility.

### Responsibilities
- perform model generation calls
- support tool-enabled calls
- normalize provider outputs into new runtime-native objects
- hide provider-specific response shapes from upper layers

### Initial scope
First version can support a single provider only.

---

## 5.6 `prompt_builder.py`

### Purpose
Build the LLM-visible prompt/messages for a step.

### Responsibilities
At minimum include:

- workflow id / phase id / step id
- current step objective
- selected input artifacts
- current attempt / transition source
- available tools
- budget constraints
- output schema / output contract

### Design rule
Default to compact context. Large artifacts should be represented by summaries or references rather than dumped raw.

---

## 5.7 `llm_step.py`

### Purpose
Provide the new model-driven step implementations.

### Suggested step classes
- `LLMStep`: model-driven, no tools
- `LLMToolStep`: model-driven, tools enabled

### Responsibilities
- inherit from `BaseStep`
- delegate actual execution to `step_runner.py`
- remain declarative at the step class boundary

---

## 5.8 `step_runner.py`

### Purpose
Implement the full step-local LLM execution loop.

### Responsibilities
The loop should handle:

1. build prompt/messages
2. select tools for this step
3. call model
4. detect tool call requests
5. execute tools
6. feed tool results back into model context
7. obtain final model output
8. parse result
9. validate result
10. decide complete / repair / invalid / failed

### Minimum controls
- `max_model_turns`
- `max_tool_calls`
- `max_repair_turns`
- `timeout_seconds`

This module is the core replacement for the previous monolithic runloop-style flow.

---

## 5.9 `output_parser.py`

### Purpose
Parse final model output into a structured object.

### Responsibilities
- extract structured output from provider response
- support JSON / structured output / mixed text-with-JSON cases
- return parse diagnostics

### Suggested output
- `parsed_output`
- `raw_output`
- `parse_ok`
- `parse_errors`
- `diagnostics`

---

## 5.10 `step_validator.py`

### Purpose
Validate whether the parsed output is acceptable for this step.

### Validation layers
1. structure-level validation
   - schema validity
   - required fields
   - type correctness

2. semantic-level validation
   - required artifacts produced
   - required content fields present
   - any step-specific exit conditions met

### Suggested output
A validation decision object containing:

- `accepted`
- `repairable`
- `blocking`
- `validation_errors`
- `warnings`

---

## 5.11 `repair_controller.py`

### Purpose
Control bounded repair when output is invalid but fixable.

### Responsibilities
- transform validation errors into repair instructions
- limit repair count
- tell `step_runner.py` whether to retry or terminate

Repair should be first-class runtime behavior, not scattered conditional logic.

---

## 5.12 `mcp_client.py`

### Purpose
Provide the new runtime's MCP client.

### Responsibilities
- connect to MCP servers
- initialize sessions
- fetch tool lists
- invoke tools
- handle timeout / transport / server errors
- normalize results

### Initial scope
A single transport such as stdio is sufficient in v1.

---

## 5.13 `tool_registry.py`

### Purpose
Maintain the structured catalog of available tools.

### Tool metadata should include
- `name`
- `description`
- `input_schema`
- `family`
- `side_effect_level`
- `server_name`

### Responsibilities
- register tools from MCP discovery
- filter tools by `allowed_tools`
- filter tools by `allowed_tool_families`
- provide model-visible tool schemas

---

## 5.14 `tool_permission.py`

### Purpose
Enforce hard permission boundaries for tool use.

### Responsibilities
- check allowlist membership
- check tool family permissions
- validate parameters against step policy
- enforce side-effect restrictions if present

Visibility of a tool is not the same as permission to execute it.

---

## 5.15 `tool_executor.py`

### Purpose
Execute a single model-requested tool call.

### Responsibilities
1. resolve tool
2. validate permission
3. execute via MCP client
4. normalize result
5. produce a structured `StepToolCall`

### Suggested normalized fields
- `name`
- `arguments`
- `success`
- `output`
- `error`
- `latency_ms`

---

## 5.16 `artifact_store.py`

### Purpose
Provide structured artifact management instead of raw unrestricted dictionary passing.

### Artifact metadata should include
- `key`
- `value`
- `kind`
- `phase_id`
- `step_id`
- `producer`
- `is_compact`
- `visibility`
- `metadata`

### Responsibilities
- store artifacts
- retrieve artifacts
- list visible artifacts
- expose structured handoff surfaces

---

## 5.17 `artifact_selector.py`

### Purpose
Decide which artifacts a step is allowed to see.

### Responsibilities
- select required artifacts
- choose compact vs full payload
- omit noisy or oversized artifacts
- hand references rather than raw body when appropriate

This is critical for controlling prompt growth and reducing context pollution.

---

## 5.18 `artifact_compactor.py`

### Purpose
Generate compact handoff material for downstream steps/phases.

### Responsibilities
- summarize large outputs
- preserve key structured fields
- convert raw results into compact downstream artifacts
- avoid feeding full oversized content into later model steps

---

## 5.19 `checkpoint_store.py`

### Purpose
Persist checkpoints and dumps.

### V1 scope
It is sufficient to support:
- phase checkpoint save
- workflow checkpoint save
- optional step dump save
- local JSON files

No full distributed recovery is required initially.

---

## 5.20 `trace_store.py`

### Purpose
Persist execution traces for debugging and analysis.

### Recommended event types
- workflow start/end
- phase start/end
- step start/end
- model turn
- tool call
- tool result
- parse result
- validation result
- repair event
- checkpoint event

### Recommended format
JSONL for easy grep and post-processing.

---

## 6. Required enhancements to current kernel files

## 6.1 `step.py`

Keep the current contract direction, but extend `StepSpec` so step behavior is more declarative.

### Suggested additions to `StepSpec`
- `step_type`
- `instruction`
- `output_schema`
- `required_artifacts`
- `artifact_selection`
- `max_model_turns`
- `max_tool_calls`
- `repair_attempts`
- `timeout_seconds`
- `compact_policy`
- `metadata`

### Suggested additions to `StepContext`
- `run_id`
- model selection / provider settings
- selected tool specs
- dump / trace directory info
- richer transition metadata

### Suggested additions to `StepResult`
Either explicitly or via `diagnostics`, capture:
- raw model output
- final text
- validation report
- usage / token info
- elapsed time

---

## 6.2 `phase.py`

Preserve current phase-state-machine direction, but strengthen phase-level policy.

### Suggested additions to `PhaseSpec`
- `required_output_artifacts`
- `handoff_policy`
- `artifact_visibility`
- `phase_exit_policy`

This helps make phase boundaries explicit handoff/control boundaries instead of just step containers.

---

## 6.3 `workflow_runtime.py`

Retain it as the workflow kernel and avoid embedding provider or MCP details.

### Suggested enhancements
- introduce `run_id`
- integrate with artifact management instead of raw dictionary-only flow
- add trace hooks at workflow / phase / step boundaries
- save phase checkpoints automatically
- enforce global budget / failure policy

### Design rule
`workflow_runtime.py` should **not** become aware of provider raw responses, prompt layout details, or MCP transport internals.

---

## 7. Suggested workflow YAML direction

Since the new runtime is not required to be compatible with `workflow_config.py`, the new YAML can be designed around the new architecture.

## Example top-level shape

```yaml
workflow_id: demo_workflow
start_phase: evidence_collection
terminal_phases:
  - final_reasoning

phases:
  - id: evidence_collection
    type: standard_phase
    next_phase: kb_grounding
    max_rollbacks: 1
    max_step_attempts: 2
    steps:
      - id: fetch_case_context
        type: deterministic_step
        config: ...
      - id: inspect_artifacts
        type: llm_tool_step
        config: ...
```

## Example minimal `llm_step` / `llm_tool_step` config

```yaml
config:
  instruction: |
    Analyze the provided artifacts and produce structured output.
  model: gpt-5
  artifact_inputs:
    - jira_context
    - extracted_signatures
  allowed_tool_families:
    - kb
  allowed_tools:
    - kb_ground
  output_schema:
    type: object
    required: [summary, findings]
  max_model_turns: 6
  max_tool_calls: 4
  repair_attempts: 1
  timeout_seconds: 90
  compact_policy: summary_only
```

This is already enough for a structured runtime to make most execution decisions declaratively.

---

## 8. Recommended implementation milestones

## Milestone 1: pure LLM step

### Goal
Run a workflow containing a real `llm_step` without tools.

### Deliverables
- `workflow_loader.py`
- `step_factory.py`
- `model_provider.py`
- `prompt_builder.py`
- `llm_step.py`
- `step_runner.py`
- `output_parser.py`
- `step_validator.py`

### Success condition
A workflow can execute:
- a deterministic step
- then an LLM step
- produce a structured `StepResult`
- complete a phase through `workflow_runtime.py`

---

## Milestone 2: tool-enabled step

### Goal
Run a real `llm_tool_step` with MCP tools.

### Deliverables
- `mcp_client.py`
- `tool_registry.py`
- `tool_permission.py`
- `tool_executor.py`
- tool-call branch inside `step_runner.py`

### Success condition
A step can:
- call the model
- receive tool-call requests
- execute MCP tools
- feed tool results back to the model
- terminate with a valid structured output

---

## Milestone 3: repair, trace, checkpoint

### Goal
Make the runtime debuggable and bounded.

### Deliverables
- `repair_controller.py`
- `trace_store.py`
- `checkpoint_store.py`
- workflow kernel hook integration

### Success condition
When a model produces invalid structured output:
- the step can perform bounded repair
- traces capture what happened
- step/phase/workflow dumps are persisted

---

## Milestone 4: artifact selection and compaction

### Goal
Control context growth and improve phase handoff quality.

### Deliverables
- `artifact_store.py`
- `artifact_selector.py`
- `artifact_compactor.py`
- integration into `workflow_runtime.py` and step execution path

### Success condition
- steps only see selected artifacts
- phase handoff defaults to compact form
- oversized raw content is not blindly fed into downstream prompts

---

## 9. Final summary

This blueprint does **not** aim to wrap or preserve the previous runloop architecture.

Instead, it establishes a new structured runtime centered on:

- `workflow_runtime.py`
- `step_runner.py`
- `tool_executor.py`
- `artifact_store.py`

with the current skeleton contracts as the kernel.

Old implementations are inputs for learning, not dependencies for the new design.
