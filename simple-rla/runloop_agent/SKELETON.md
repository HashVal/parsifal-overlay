# Workflow Skeleton YAML Format

This document describes the **current input shape** expected by the new workflow skeleton demo runtime:

- `step.py`
- `phase.py`
- `workflow_runtime.py`
- `workflow_demo.py`

It is **not** the final workflow DSL specification.
It documents the YAML structure that is currently supported by the demo loader and runtime skeleton.

---

## Scope

This YAML format is used by:

```bash
python3 simple-rla/runloop_agent/workflow_demo.py --config <path-to-yaml>
```

The current loader builds:

- a `WorkflowSpec`
- one or more demo `BasePhase` instances
- one or more demo `BaseStep` instances

from a small declarative YAML file.

---

## Top-level structure

The YAML file must be a mapping.

Supported top-level fields:

| Field | Required | Type | Meaning |
|---|---|---|---|
| `workflow_id` | no | string | Workflow identifier. Defaults to `demo_workflow` if omitted. |
| `start_phase` | no | string | Phase id to start from. Defaults to the first phase in `phases`. |
| `terminal_phases` | no | list[string] | Phase ids allowed to terminate the workflow. Defaults to the last phase if omitted. |
| `phases` | yes | list[phase] | Ordered phase definitions. Must be non-empty. |

---

## Phase object format

Each item under `phases` must be a mapping.

Supported phase fields:

| Field | Required | Type | Meaning |
|---|---|---|---|
| `id` | yes | string | Unique phase identifier. |
| `type` | yes | string | Phase type name used by the Python registry. |
| `next_phase` | no | string | Next phase id. If omitted, this phase is treated as having no declared successor. |
| `max_rollbacks` | no | integer | Maximum allowed rollback count inside this phase. Defaults to `0`. |
| `max_step_attempts` | no | integer | Maximum allowed attempts per step inside this phase. Defaults to `1`. |
| `terminal` | no | boolean | Currently semantic only in the demo YAML. Runtime termination is controlled by `terminal_phases`, not this field. |
| `steps` | yes | list[step] | Ordered step definitions for this phase. Must be non-empty. |

### Notes

- `type` is resolved by the demo phase registry in `workflow_demo.py`.
- In the current implementation, the only supported phase type is `demo_phase`.
- `next_phase` is interpreted by the phase instance and used by `WorkflowRuntime.resolve_phase_transition(...)`.

---

## Step object format

Each item under `steps` must be a mapping.

Supported step fields:

| Field | Required | Type | Meaning |
|---|---|---|---|
| `id` | yes | string | Unique step identifier within the phase. |
| `type` | yes | string | Step type name used by the Python registry. |
| `config` | no | mapping | Reserved per-step configuration payload. Passed into the step spec metadata. |

### Notes

- Step behavior is defined by the Python step registry, not fully by YAML.
- The current loader only uses `id`, `type`, and optional `config`.
- `config` is a hook for future step-specific parameters. In the current demo it is mostly a reserved field.

---

## Currently supported demo phase types

### `demo_phase`

Implemented in `workflow_demo.py` as `DemoPhase`.

Behavior:

- builds a list of demo steps from the phase `steps` array
- uses `next_phase` as the next phase pointer
- considers the phase complete when:
  - all steps have produced results
  - all step results are `exit_ready == true`

---

## Currently supported demo step types

### `echo_step`

Purpose:

- verify normal step execution
- verify artifact creation
- verify downstream artifact visibility

Behavior:

- returns `COMPLETED`
- writes a small artifact containing:
  - `step_id`
  - `phase_id`
  - `attempt`
  - visible input keys

---

### `incomplete_once_step`

Purpose:

- verify `rerun_same_step` behavior
- verify that phase-local rerun does not rerun the previous step

Behavior:

- first execution returns `INCOMPLETE`
- second execution returns `COMPLETED`

---

### `artifact_report_step`

Purpose:

- verify cross-phase artifact handoff
- verify that the later phase can consume artifacts produced earlier

Behavior:

- reads the currently visible artifact keys
- returns a summary artifact with:
  - `artifact_keys`
  - `artifact_count`

---

## Loader behavior summary

`workflow_demo.py` currently performs the following steps:

1. read YAML with `yaml.safe_load(...)`
2. validate top-level shape
3. resolve phase entries via a small phase registry
4. resolve step entries via a small step registry
5. build a `WorkflowSpec`
6. execute it through `WorkflowRuntime`

This is intentionally a **small loader**, not a full DSL engine.

---

## Runtime expectations

The YAML is only one part of the system.
The runtime behavior is determined by the combination of:

- YAML structure
- demo phase registry
- demo step registry
- `WorkflowRuntime`
- `BasePhase` / `BaseStep` contracts

The workflow runtime currently handles:

- step execution
- step exit validation
- rerun of the current step
- phase completion checks
- phase transitions
- terminal phase completion
- global artifact handoff
- workflow-level logging

---

## What this YAML does **not** define today

This format does **not** currently define:

- full prompt contents for real LLM-driven steps
- tool schemas or real MCP tool bindings
- provider/model configuration
- checkpoint persistence backends
- workflow resume/recovery semantics
- a stable general-purpose workflow DSL
- compatibility with the old `workflow.yaml`

So this file should be understood as:

> a schema for the current workflow skeleton demo input

not:

> the final production workflow specification

---

## CLI usage

Basic usage:

```bash
python3 simple-rla/runloop_agent/workflow_demo.py \
  --config simple-rla/runloop_agent/demo.yaml \
  --log-level INFO
```

With initial artifacts:

```bash
python3 simple-rla/runloop_agent/workflow_demo.py \
  --config simple-rla/runloop_agent/demo.yaml \
  --initial-artifact jira_key=PKT-20231 \
  --log-level INFO
```

Supported CLI flags:

| Flag | Meaning |
|---|---|
| `--config` | Path to the demo YAML file |
| `--initial-artifact key=value` | Inject an initial artifact into workflow global artifacts; may be repeated |
| `--log-level` | Logging level for demo/runtime output |

---

## Design intent

This skeleton YAML exists to validate the new runtime architecture:

- `WorkflowSpec -> PhaseSpec -> StepSpec`
- phase-local rerun / rollback control
- phase-exit-check
- checkpoint / compact handoff direction
- terminal-phase-controlled completion

It is deliberately small so the runtime contracts can be tested before designing a richer workflow syntax.

---

## Future extension direction

Likely future areas:

- richer phase registries
- richer step registries
- step-specific config schema
- explicit rollback anchor declarations in YAML
- compact / checkpoint policy fields
- stable workflow syntax beyond the current demo loader

Until then, keep this file aligned with the **actual supported demo loader behavior** instead of trying to describe a future format that is not implemented yet.
