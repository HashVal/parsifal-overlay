# REMINDER.md

This note records the current working understanding of `M3` and `M3.x` inside `simple-rla/runloop_agent`.

It is not a formal spec. It is a local implementation reminder to keep milestone boundaries stable while the execution path is still under construction.

---

# Core principle

`M3` is the **Check Execution runtime substrate**.

`M3.x` are the **realization layers built on top of that substrate**.

This distinction must remain clear.

Do not collapse substrate, check-description formalization, concrete realization, and evidence integration into one layer.

---

# Current intended milestone split

## M3 — Check Execution runtime substrate

### Responsibility
Provide the technical substrate required to execute structured checks.

This includes:

- atomic execution capabilities
- MCP-backed execution surfaces
- typed execution-side inputs/outputs
- execution request substrate
- code-side / device-side capability families
- evidence-producing tool primitives
- runtime-level validation of execution-side prerequisites

### What M3 should contain

For code-side execution, M3 should contain things like:

- repo registry / repo validation
- resolved code scope
- atomic code MCP tools
- tool-family registration
- startup-time substrate validation

For device-side execution, M3 should analogously contain:

- atomic device MCP tools
- resolved device/runtime target substrate
- capability-family registration
- startup/runtime validation of required execution surfaces

### What M3 should NOT contain

M3 should not directly perform:

- high-level check planning
- `DEBUG_PLAN` interpretation
- free-form natural-language check understanding
- check-level conclusion making
- hypothesis revision
- closure logic

M3 provides the building blocks. It does not decide how a language-level check description should be realized.

---

## M3.1 — Debug-plan interpretation and check assembly

### Responsibility
Convert `DEBUG_PLAN` / debug intent into **formalized check descriptions** that later execution realizations can consume.

This is the boundary layer between planning and execution.

### M3.1 should do

- interpret debug-plan intent
- assemble `CODE_CHECK` / `DEVICE_CHECK`
- bind execution-relevant scope information
- resolve repo / device target mapping
- resolve ref / path filter / language / target-scope style constraints
- express expected evidence intent in a more formal way
- output bounded, execution-ready check descriptions

### M3.1 should NOT do

- directly execute MCP tools
- behave like a free-form execution agent
- redo high-level debug planning
- decide closure / terminal outcomes

### Important reminder

If check descriptions remain too loose or too prose-like, M3.2 / M3.3 will bloat into small planning agents.

Therefore, M3.1 must be the layer that tightens language-level intent into structured or semi-structured execution-facing descriptions.

---

## M3.2 — Device-check execution realization

### Responsibility
Translate a **formalized `DEVICE_CHECK` description** into a concrete device-side tool-call program over the M3 substrate.

### M3.2 should do

- choose relevant atomic device tools
- bind parameters for device/runtime-side execution
- determine invocation ordering
- run device-side tool calls
- collect structured execution outputs
- extract device-side evidence primitives
- normalize device-check execution results

### M3.2 should NOT do

- re-plan the case
- reinterpret the whole `DEBUG_PLAN`
- invent new high-level strategy
- perform evidence closure or root-cause judgment

---

## M3.3 — Code-check execution realization

### Responsibility
Translate a **formalized `CODE_CHECK` description** into a concrete code-side tool-call program over the M3 substrate.

### M3.3 should do

- consume formalized code-check descriptions from M3.1
- use resolved repo/ref/scope information
- select relevant atomic code tools
- bind parameters for code-side execution
- determine invocation ordering
- run code-side tool calls
- collect structured execution outputs
- extract code-side evidence primitives
- normalize code-check execution results

### M3.3 should NOT do

- re-plan the case
- act like a free-form code-debugging agent
- decide whether the hypothesis is correct
- perform closure semantics

### Practical reminder

The current repo-backed MCP code substrate exists to support this layer.

Atomic code tools are correct for M3.

The logic that converts formalized `CODE_CHECK` descriptions into tool-call programs belongs in M3.3, not in M3.

---

## M3.4 — Structured check evidence integration

### Responsibility
Package outputs from executed `DEVICE_CHECK` and `CODE_CHECK` runs into a unified structured evidence artifact for downstream closure.

### M3.4 should do

- preserve traceability from evidence back to executed checks
- preserve typed distinction between code-side and device-side evidence
- integrate multiple check outputs into one structured package
- produce a downstream-consumable evidence object

### M3.4 should NOT do

- execute checks
- revise debug plans
- confirm or reject the hypothesis
- assign terminal closure outcomes
- decide `REFRAME`
- collapse into evidence evaluation

### Important reminder

Evidence integration is not closure.

Do not let M3.4 silently absorb closure semantics.

---

# Atomic-tool principle

For both code-side and device-side execution:

- M3 should expose **atomic MCP tools**
- M3.2 / M3.3 should realize checks by composing those atomic tools

Avoid prematurely creating high-level black-box tools such as:

- `run_device_check(...)`
- `run_code_check(...)`

unless there is a strong reason and the boundary remains explicit.

The current preferred direction is:

- atomic capability surface in M3
- description-to-tool-program realization in M3.2 / M3.3

This keeps substrate and realization cleanly separated.

---

# Do not do

The following boundary violations should be treated as explicit anti-patterns.

## Do not let M3 become a hidden realization layer

Do not put the following into M3:

- high-level natural-language check interpretation
- free-form translation from vague check prose to tool-call plans
- check-level reasoning about what to do next
- hypothesis revision
- closure-like judgment

If M3 starts doing these things, it is no longer acting as substrate.

## Do not let M3.1 collapse into execution

Do not let M3.1:

- directly execute MCP tools
- behave like a runtime-side action agent
- bypass formalization and emit loosely specified checks
- mix planning formalization with low-level execution details

M3.1 should formalize execution intent, not realize it.

## Do not let M3.2 / M3.3 become replanning agents

Do not let M3.2 / M3.3:

- reinterpret the full case from scratch
- reopen broad upstream planning context unless strictly necessary
- invent new high-level debug strategy
- replace M3.1 by doing free-form check understanding
- smuggle closure semantics into execution outputs

M3.2 / M3.3 should realize already-formalized check descriptions into tool-call programs.

## Do not let M3.4 become closure

Do not let M3.4:

- confirm or reject the root-cause hypothesis
- assign terminal outcomes
- decide `REFRAME`
- turn evidence packaging into evaluation
- silently absorb closure semantics because evidence already “looks persuasive”

M3.4 integrates evidence. It does not interpret the case to final judgment.

---

# Relation to mechanized constraints

This milestone split should be protected as an implementation discipline, not left as vague prose.

In particular:

- M3 should not silently absorb M3.2 / M3.3 logic
- M3.2 / M3.3 should not silently absorb M3.1 planning/formalization work
- M3.4 should not silently absorb closure logic

Whenever possible, prefer:

- typed objects
- explicit contracts
- validated boundaries
- clear provenance
- bounded execution context

over ad hoc free-form passing of intent.

---

# Relation to progressive disclosure

This split is also important for staged disclosure.

Roughly:

- M3 provides the capability surface
- M3.1 provides bounded formalized check descriptions
- M3.2 / M3.3 operate within those bounded descriptions and do not need the entire upstream planning space
- M3.4 consumes structured evidence rather than raw execution sprawl

This helps prevent the execution layers from becoming overloaded with planning context.

---

# Current practical reading of recent code changes

Recent code-side substrate changes should be interpreted as:

- **M3 code-side substrate landing**
- and partially as **M3.3 prerequisite infrastructure**

They should NOT be read as “M3.3 is complete”.

The presence of:

- repo registry
- resolved code scope
- atomic code MCP tools
- code tool family
- startup validation
- tests

means the substrate is becoming real.

It does not yet mean that full `CODE_CHECK` execution realization, runtime integration, or check-level outcome application are complete.

---

# Short version

- **M3** = atomic execution substrate
- **M3.1** = formalize check descriptions from debug-plan intent
- **M3.2** = realize formalized `DEVICE_CHECK` descriptions via atomic device tools
- **M3.3** = realize formalized `CODE_CHECK` descriptions via atomic code tools
- **M3.4** = integrate structured evidence, not closure

Keep these boundaries stable.
