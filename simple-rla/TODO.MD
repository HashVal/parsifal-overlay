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

# Milestone 3 — Check Execution runtime substrate

## Goal
Establish the technical substrate for the `Check Execution` phase.

This milestone provides the runtime-level capability needed to execute structured checks, realize them through MCP-backed tool paths, return structured execution results, and support evidence-producing execution for later phases.

M3 is about the execution substrate itself. It is not yet the milestone for concrete `CODE_CHECK` / `DEVICE_CHECK` workflow realizations.

## Success condition
The runtime can:

- represent check execution as a first-class phase capability
- support the two primary check item types:
  - `CODE_CHECK`
  - `DEVICE_CHECK`
- realize `CODE_CHECK` through MCP-backed code-side tool capabilities
- realize `DEVICE_CHECK` through MCP-backed device/runtime-side tool capabilities
- route checks through appropriate execution capability paths
- assemble execution-ready checks into invocation-ready MCP requests
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

---

## Create

### 1. Check execution data model / schema layer
- [ ] define the minimum execution-side data model for `CODE_CHECK` and `DEVICE_CHECK`
- [ ] define structured execution-result representation
- [ ] define structured evidence-return representation
- [ ] define check-level outcome/status representation
- [ ] define minimum linkage fields between:
  - [ ] check identity
  - [ ] check type
  - [ ] execution result
  - [ ] returned evidence

### 2. MCP-backed execution substrate
- [ ] define MCP-backed realization path for `CODE_CHECK`
- [ ] define MCP-backed realization path for `DEVICE_CHECK`
- [ ] define routing rules from check type to MCP tool surface
- [ ] define tool-result normalization rules for execution-phase use
- [ ] define minimum execution boundary between check object and MCP tool call

### 3. Execution request assembly layer
- [ ] define how execution-ready `CODE_CHECK` is transformed into invocation-ready MCP request data
- [ ] define how execution-ready `DEVICE_CHECK` is transformed into invocation-ready MCP request data
- [ ] define target shaping and parameter normalization before MCP tool call
- [ ] define how planning-only or non-executable fields are excluded from invocation payloads
- [ ] define how supporting capability needs are preserved during request assembly without changing primary check type

### 4. Evidence and result packaging layer
- [ ] define how executed checks emit structured evidence outputs
- [ ] define how execution results are packaged for downstream evidence closure
- [ ] preserve code-side and device-side evidence distinction
- [ ] preserve supporting execution metadata needed for later interpretation

---

## Modify

### 5. Runtime orchestration integration
- [ ] extend runtime/phase execution so `Check Execution` can exist as a first-class phase capability
- [ ] add execution-path support for structured check handling
- [ ] integrate MCP-backed check realization into the runtime execution path
- [ ] ensure execution results can flow back into workflow/phase artifacts cleanly

### 6. Step / phase / result interfaces
- [ ] ensure step/phase/result interfaces can carry structured check-execution state
- [ ] ensure runtime result objects can carry evidence outputs and execution outcomes
- [ ] ensure downstream phases can consume execution artifacts without reopening raw tool output

### 7. Minimal observability for execution substrate
- [ ] preserve enough diagnostics to inspect check execution behavior
- [ ] preserve enough metadata to understand which MCP capability path was used
- [ ] preserve enough runtime output to debug execution-result normalization failures if they occur

---

## Out of scope for Milestone 3
- concrete `CODE_CHECK` workflow steps
- concrete `DEVICE_CHECK` workflow steps
- demo-specific execution choreography
- debug-plan generation implementation
- evidence-closure implementation
- terminal outcome classification
- bounded repair / trace / checkpoint as the primary milestone goal
- full resume/recovery protocol

## Status
- [ ] planned

---

# Milestone 3.1 — Debug-plan interpretation and check assembly

## Goal
Provide the first concrete realization layer on top of the M3 `Check Execution` substrate by interpreting `DEBUG_STEPS` and assembling execution-ready check data.

This milestone bridges the gap between planning artifacts and execution objects. It does not yet execute checks, but it must transform debug-plan output into structured `CODE_CHECK` and `DEVICE_CHECK` inputs that later execution milestones can consume.

## Success condition
A workflow can:

- consume `DEBUG_STEPS` / `DEBUG_PLAN` as structured planning input
- interpret the planning artifact into execution-ready check objects
- distinguish and assemble:
  - `CODE_CHECK`
  - `DEVICE_CHECK`
- preserve hypothesis linkage and evidence-gap intent in assembled checks
- preserve execution-relevant fields such as:
  - target
  - purpose
  - evidence sought
  - expected interpretation
  - supporting capability needs where relevant
- emit a bounded structured check-assembly artifact for downstream execution milestones

---

## Create

### 1. Check-assembly data model
- [ ] define the minimum assembled-check representation for execution-ready `CODE_CHECK`
- [ ] define the minimum assembled-check representation for execution-ready `DEVICE_CHECK`
- [ ] define shared execution-facing fields required after debug-plan interpretation
- [ ] define the minimum linkage fields back to:
  - [ ] source `DEBUG_STEPS`
  - [ ] hypothesis context
  - [ ] evidence-gap intent

### 2. Debug-plan interpretation layer
- [ ] define how `DEBUG_STEPS` / `DEBUG_PLAN` is read as structured planning input
- [ ] define interpretation rules from planning semantics to execution-facing fields
- [ ] define how non-executable planning prose is excluded from assembled check data
- [ ] define how supporting capability needs are preserved without becoming peer check types

### 3. Check classification and assembly output
- [ ] define classification rules for separating assembled checks into:
  - [ ] `CODE_CHECK`
  - [ ] `DEVICE_CHECK`
- [ ] define the structured output artifact for assembled checks
- [ ] define how assembled checks are packaged for downstream execution milestones
- [ ] ensure the assembly output remains bounded and downstream-consumable

---

## Modify

### 4. Runtime / phase integration for assembly
- [ ] add runtime support for a phase/step that consumes `DEBUG_STEPS` and emits assembled checks
- [ ] ensure assembled-check artifacts can flow into later execution phases cleanly
- [ ] ensure assembly output can be preserved as structured workflow artifacts

### 5. Step / result interface support
- [ ] ensure step/result interfaces can carry assembled-check outputs cleanly
- [ ] ensure downstream phases can consume assembled checks without re-reading the original planning artifact
- [ ] ensure assembled-check output remains separate from execution-result output

### 6. Minimal diagnostics for interpretation/assembly
- [ ] preserve enough diagnostics to inspect how `DEBUG_STEPS` was interpreted
- [ ] preserve enough diagnostics to inspect why a check was classified as `CODE_CHECK` or `DEVICE_CHECK`
- [ ] preserve enough diagnostics to inspect assembly failures or dropped planning fields when needed

---

## Out of scope for Milestone 3.1
- executing `CODE_CHECK`
- executing `DEVICE_CHECK`
- MCP tool invocation
- real execution evidence return
- evidence evaluation or outcome classification
- revising the debug plan itself

## Status
- [ ] planned

---

# Milestone 3.2 — Device-check execution realization

## Goal
Provide the first concrete execution realization on top of the M3 `Check Execution` substrate by executing assembled `DEVICE_CHECK` items through MCP-backed device/runtime-side capabilities.

This milestone turns execution-ready `DEVICE_CHECK` objects into real device-side evidence-producing actions.

## Success condition
A workflow can:

- consume execution-ready `DEVICE_CHECK` inputs produced by earlier assembly steps
- resolve device/runtime-side execution targets for those checks
- invoke appropriate MCP-backed device/runtime-side capabilities
- return structured execution results for executed `DEVICE_CHECK` items
- return structured device-side evidence outputs
- classify each executed `DEVICE_CHECK` into check-level outcomes such as:
  - `COMPLETED`
  - `INCONCLUSIVE`
  - `BLOCKED`
  - `FAILED`
  - `DEFERRED`

---

## Create

### 1. Device-check execution target layer
- [ ] define how assembled `DEVICE_CHECK` targets are resolved into execution-ready device/runtime-side targets
- [ ] define the minimum target fields required for device-side execution
- [ ] define how missing, ambiguous, or non-resolvable targets are represented before invocation
- [ ] define how device/runtime context needed for execution is preserved during target resolution

### 2. MCP-backed device-check invocation layer
- [ ] define the MCP-backed execution path for `DEVICE_CHECK`
- [ ] define how device-side capability families are selected for a given `DEVICE_CHECK`
- [ ] define invocation rules from execution-ready `DEVICE_CHECK` data to device-side MCP tool requests
- [ ] define how supporting capability needs are carried into invocation without changing the primary `DEVICE_CHECK` type

### 3. Device execution-result normalization layer
- [ ] define how raw MCP device/runtime outputs are normalized into structured `DEVICE_CHECK` execution results
- [ ] define the minimum execution-result fields preserved after device-side execution
- [ ] define how execution diagnostics and invocation metadata are retained for later interpretation

### 4. Device evidence extraction layer
- [ ] define how structured device-side evidence is extracted from normalized execution results
- [ ] define the minimum evidence fields needed by later evidence-integration or closure milestones
- [ ] preserve device-side evidence distinction from future code-side evidence outputs

---

## Modify

### 5. Runtime / phase integration for `DEVICE_CHECK`
- [ ] add runtime support for executing assembled `DEVICE_CHECK` items as part of `Check Execution`
- [ ] ensure device-check execution outputs can flow into workflow/phase artifacts cleanly
- [ ] ensure device-check execution remains separable from future `CODE_CHECK` execution realization

### 6. Outcome application for real device-check runs
- [ ] apply check-level outcome semantics to real `DEVICE_CHECK` execution results
- [ ] define how `COMPLETED`, `INCONCLUSIVE`, `BLOCKED`, `FAILED`, and `DEFERRED` are determined for device-side execution
- [ ] ensure outcome determination remains tied to execution reality rather than later evidence evaluation

### 7. Minimal diagnostics for device-check realization
- [ ] preserve enough diagnostics to inspect target resolution for `DEVICE_CHECK`
- [ ] preserve enough diagnostics to inspect MCP capability selection for device-side execution
- [ ] preserve enough diagnostics to inspect normalization failures or evidence-extraction failures when needed

---

## Out of scope for Milestone 3.2
- `CODE_CHECK` execution realization
- combined code/device evidence integration
- debug-plan generation or revision
- evidence evaluation or terminal outcome classification
- full `Check Execution` phase completion across all check families

## Status
- [ ] planned

---

# Milestone 3.3 — Code-check execution realization

## Goal
Provide the second concrete execution realization on top of the M3 `Check Execution` substrate by executing assembled `CODE_CHECK` items through MCP-backed code-side capabilities.

This milestone turns execution-ready `CODE_CHECK` objects into real code-side evidence-producing actions.

## Success condition
A workflow can:

- consume execution-ready `CODE_CHECK` inputs produced by earlier assembly steps
- resolve code-side execution targets and execution scope for those checks
- invoke appropriate MCP-backed code-side capabilities
- return structured execution results for executed `CODE_CHECK` items
- return structured code-side evidence outputs
- classify each executed `CODE_CHECK` into check-level outcomes such as:
  - `COMPLETED`
  - `INCONCLUSIVE`
  - `BLOCKED`
  - `FAILED`
  - `DEFERRED`

---

## Create

### 1. Code-check execution target and scope layer
- [ ] define how assembled `CODE_CHECK` targets are resolved into execution-ready code-side targets
- [ ] define how execution scope is bounded for a given `CODE_CHECK`
- [ ] define the minimum target and scope fields required for code-side execution
- [ ] define how missing, ambiguous, or non-resolvable code-side targets are represented before invocation

### 2. MCP-backed code-check invocation layer
- [ ] define the MCP-backed execution path for `CODE_CHECK`
- [ ] define how code-side capability families are selected for a given `CODE_CHECK`
- [ ] define invocation rules from execution-ready `CODE_CHECK` data to code-side MCP tool requests
- [ ] define how supporting capability needs are carried into invocation without changing the primary `CODE_CHECK` type

### 3. Code execution-result normalization layer
- [ ] define how raw MCP code-side outputs are normalized into structured `CODE_CHECK` execution results
- [ ] define the minimum execution-result fields preserved after code-side execution
- [ ] define how execution diagnostics and invocation metadata are retained for later interpretation

### 4. Code evidence extraction layer
- [ ] define how structured code-side evidence is extracted from normalized execution results
- [ ] define the minimum evidence fields needed by later evidence-integration or closure milestones
- [ ] preserve code-side evidence distinction from device-side evidence outputs

---

## Modify

### 5. Runtime / phase integration for `CODE_CHECK`
- [ ] add runtime support for executing assembled `CODE_CHECK` items as part of `Check Execution`
- [ ] ensure code-check execution outputs can flow into workflow/phase artifacts cleanly
- [ ] ensure code-check execution remains separable from `DEVICE_CHECK` execution realization

### 6. Outcome application for real code-check runs
- [ ] apply check-level outcome semantics to real `CODE_CHECK` execution results
- [ ] define how `COMPLETED`, `INCONCLUSIVE`, `BLOCKED`, `FAILED`, and `DEFERRED` are determined for code-side execution
- [ ] ensure outcome determination remains tied to execution reality rather than later evidence evaluation

### 7. Minimal diagnostics for code-check realization
- [ ] preserve enough diagnostics to inspect target and scope resolution for `CODE_CHECK`
- [ ] preserve enough diagnostics to inspect MCP capability selection for code-side execution
- [ ] preserve enough diagnostics to inspect normalization failures or evidence-extraction failures when needed

---

## Out of scope for Milestone 3.3
- `DEVICE_CHECK` execution realization
- combined code/device evidence integration
- debug-plan generation or revision
- evidence evaluation or terminal outcome classification
- full `Check Execution` phase completion across all check families

## Status
- [ ] planned

---

# Milestone 3.4 — Structured check evidence integration

## Goal
Provide the integration layer on top of concrete `DEVICE_CHECK` and `CODE_CHECK` execution realizations by packaging their outputs into a unified structured evidence artifact for downstream phases.

This milestone does not evaluate evidence or determine final debug outcomes. It prepares executed-check outputs for later evidence-closure use.

## Success condition
A workflow can:

- consume structured outputs from executed `DEVICE_CHECK` items
- consume structured outputs from executed `CODE_CHECK` items
- preserve check identity, check type, execution outcome, and evidence linkage during integration
- package code-side and device-side evidence into a unified downstream-consumable structure
- preserve evidence distinction without collapsing all evidence into an untyped bundle
- emit a bounded structured check-evidence artifact for later evidence-closure phases

---

## Create

### 1. Integrated check-evidence data model
- [ ] define the unified structured artifact for integrated check evidence
- [ ] define how `CODE_CHECK` and `DEVICE_CHECK` outputs are represented within the same integration object
- [ ] define the minimum linkage fields preserved for each integrated check:
  - [ ] check identity
  - [ ] check type
  - [ ] execution outcome
  - [ ] returned evidence
- [ ] define how integrated evidence remains bounded and downstream-consumable

### 2. Code/device evidence integration layer
- [ ] define how structured code-side evidence is incorporated into the integrated artifact
- [ ] define how structured device-side evidence is incorporated into the integrated artifact
- [ ] define how evidence from multiple executed checks is merged without losing per-check traceability
- [ ] define how absent, partial, or inconclusive evidence is represented during integration

### 3. Downstream evidence-package output
- [ ] define the emitted artifact shape for downstream evidence-closure use
- [ ] define how integrated evidence is packaged without requiring direct reopening of raw execution outputs
- [ ] define the minimum metadata needed by later phases to interpret integrated evidence safely

---

## Modify

### 4. Runtime / phase integration for evidence packaging
- [ ] add runtime support for packaging executed check outputs into an integrated evidence artifact
- [ ] ensure integrated evidence artifacts can flow cleanly into later phases
- [ ] ensure evidence packaging remains separate from check execution itself

### 5. Step / result interface support for integrated evidence
- [ ] ensure step/result interfaces can carry integrated check-evidence artifacts cleanly
- [ ] ensure downstream phases can consume integrated evidence without re-reading raw per-check execution outputs
- [ ] ensure integrated evidence output remains separate from final evidence evaluation or terminal outcome objects

### 6. Minimal diagnostics for evidence integration
- [ ] preserve enough diagnostics to inspect how per-check evidence was integrated
- [ ] preserve enough diagnostics to inspect missing, partial, or dropped evidence during packaging
- [ ] preserve enough diagnostics to inspect linkage failures between execution results and integrated evidence if they occur

---

## Out of scope for Milestone 3.4
- execution of `DEVICE_CHECK`
- execution of `CODE_CHECK`
- debug-plan generation or revision
- evidence evaluation
- terminal outcome classification
- hypothesis confirmation or rejection
- `REFRAME` decision-making

## Status
- [ ] planned

---

# Milestone 4 — Artifact selection and compaction
