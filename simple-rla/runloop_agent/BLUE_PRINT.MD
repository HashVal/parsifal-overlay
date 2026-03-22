# BLUE_PRINT.MD

# Structured Workflow Runtime Blueprint (Replacement Track)

This document describes the **new structured runtime direction** for `runloop_agent/`.

It is explicitly a **replacement-track design** for the previous runloop-style implementation.

## Non-goals / constraints

This blueprint assumes:

- **Do not modify `workflow_config.py`**
- **Do not modify `openai_fc.py`**
- **Do not modify `openai_responses.py`**
- **Do not treat `mcp_stdio_client.py` as part of the new runtime main path**
- **Do not design for compatibility with the previous runloop path**
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

Primary files:

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

Primary files:

- `mcp_client.py`
- `tool_registry.py`
- `tool_permission.py`
- `tool_executor.py`

Responsibilities:

- launch/connect MCP servers through a **new MCP stdio client**
- discover MCP tools
- maintain a structured tool catalog
- filter tools per step
- enforce tool permission boundaries
- execute tool calls requested by the model
- normalize tool results

### Important design note

The new runtime should reuse the existing `mcp_servers/*` server implementations, but **must not depend on `mcp_stdio_client.py` as its primary client path**. A new `mcp_client.py` should be implemented for the skeleton runtime.

---

### 2.4 Artifact & Checkpoint Plane

Primary files:

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

Primary files:

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

  mcp_client.py
  tool_registry.py
  tool_permission.py
  tool_executor.py

  artifact_store.py
  artifact_selector.py
  artifact_compactor.py
  checkpoint_store.py
  trace_store.py

  runtime_config.py
  example.toml

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
- tool metadata schema
- tool result schema
- phase handoff schema
- checkpoint serialization schema

This avoids scattering structural contracts across loaders, prompts, validators, and runtime code.

---

## 5.5 `runtime_config.py`

### Purpose
Load the new unified runtime configuration from `example.toml`.

### Responsibilities
The unified config should include:

- runtime defaults (`model`, `timeout_s`, protocol version)
- OpenAI-compatible model endpoint settings
- MCP server configuration (`mcp.servers.*`)

### Design rule
The new runtime should use a **single config entry point** (`example.toml`) instead of separate `example.runtime.toml` and `example.mcp.toml` files.

---

## 5.6 `model_provider.py`

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

## 5.7 `prompt_builder.py`

### Purpose
Build the LLM-visible prompt/messages for a step.

### Responsibilities
At minimum include:

- workflow id / phase id / step id
- current step objective
- selected input artifacts
- current attempt / transition source
- available tools (when tool-enabled)
- budget constraints
- output schema / output contract

### Design rule
Default to compact context. Large artifacts should be represented by summaries or references rather than dumped raw.

---

## 5.8 `llm_step.py`

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

## 5.9 `step_runner.py`

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

This module is the core replacement for the previous monolithic runloop-style flow, and M2 is the point where it becomes necessary.

---

## 5.10 `output_parser.py`

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

## 5.11 `step_validator.py`

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

## 5.12 `repair_controller.py`

### Purpose
Control bounded repair when output is invalid but fixable.

### Responsibilities
- transform validation errors into repair instructions
- limit repair count
- tell `step_runner.py` whether to retry or terminate

Repair should be first-class runtime behavior, not scattered conditional logic.

---

## 5.13 `mcp_client.py`

### Purpose
Provide the new runtime's MCP client.

### Responsibilities
- launch/connect MCP servers via **a newly implemented stdio client**
- initialize sessions
- fetch tool lists
- invoke tools
- handle timeout / transport / server errors
- normalize results
- maintain `tool_name -> server/client` routing

### Design rule
This file should be the new runtime's MCP entry point. It should **not** wrap or depend on `mcp_stdio_client.py` as the primary client path.

### Initial scope
A single transport such as stdio is sufficient in v1.

---

## 5.14 `tool_registry.py`

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
- infer/provide tool family when server metadata does not include one
- filter tools by `allowed_tools`
- filter tools by `allowed_tool_families`
- provide model-visible tool schemas

---

## 5.15 `tool_permission.py`

### Purpose
Enforce hard permission boundaries for tool use.

### Responsibilities
- check allowlist membership
- check tool family permissions
- validate parameters against step policy
- enforce side-effect restrictions if present

Visibility of a tool is not the same as permission to execute it.

---

## 5.16 `tool_executor.py`

### Purpose
Execute a single model-requested tool call.

### Responsibilities
1. resolve tool
2. validate permission
3. execute via `mcp_client.py`
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

## 5.17 `artifact_store.py`

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

## 5.18 `artifact_selector.py`

### Purpose
Decide which artifacts a step is allowed to see.

### Responsibilities
- select required artifacts
- choose compact vs full payload
- omit noisy or oversized artifacts
- hand references rather than raw body when appropriate

This is critical for controlling prompt growth and reducing context pollution.

---

## 5.19 `artifact_compactor.py`

### Purpose
Generate compact handoff material for downstream steps/phases.

### Responsibilities
- summarize large outputs
- preserve key structured fields
- convert raw results into compact downstream artifacts
- avoid feeding full oversized content into later model steps

---

## 5.20 `checkpoint_store.py`

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

## 5.21 `trace_store.py`

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

## 6. Kernel constraints and evolution

## 6.1 `step.py`

The replacement-track design continues to prefer **minimal changes** to `step.py` and `phase.py` unless a new milestone truly requires them.

For M1 and early M2 work, complexity should continue to be absorbed by new modules rather than by expanding the kernel contracts prematurely.

---

## 6.2 `phase.py`

The replacement-track design continues to prefer **minimal changes** to `phase.py` unless artifact/handoff policy or tool-enabled phase semantics force new contract fields.

---

## 6.3 `workflow_runtime.py`

Retain it as the workflow kernel and avoid embedding provider or MCP transport details.

### Suggested enhancements over time
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

Note that model/runtime defaults are expected to come from `example.toml`, not from every workflow step.

---

## 8. Recommended implementation milestones

## Milestone 1: pure LLM step

### Goal
Run a workflow containing a real `llm_step` without tools.

### Success condition
A workflow can execute:
- a deterministic step
- then an LLM step
- produce a structured `StepResult`
- complete a phase through `workflow_runtime.py`

### Status
Accomplished.

---

## Milestone 2: tool-enabled step

### Goal
Run a real `llm_tool_step` with MCP tools, using a **new MCP stdio client** and a **unified `example.toml` config**.

### Deliverables
- `example.toml`
- unified `runtime_config.py`
- `mcp_client.py`
- `tool_registry.py`
- `tool_permission.py`
- `tool_executor.py`
- `step_runner.py`
- `LLMToolStep` path inside `llm_step.py`

### Success condition
A step can:
- load runtime + MCP configuration from `example.toml`
- launch local MCP servers via the new `mcp_client.py`
- discover tools and build a filtered registry
- expose tool schemas to the model
- receive tool-call requests
- execute MCP tools
- feed tool results back to the model
- terminate with a valid structured output

### Scope notes
- Reuse `mcp_servers/*`
- Do **not** route M2 through `mcp_stdio_client.py`
- Do **not** keep `example.mcp.toml` / `example.runtime.toml` as the primary config path

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
