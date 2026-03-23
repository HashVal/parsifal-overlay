# simple-rla

`simple-rla` is a structured debugging / RCA workflow prototype for Jira cases, local logs, and a local YAML-first knowledge base.

The current main path is built around:

- `runloop_agent/` as the workflow runtime
- `mcp_servers/` as the tool execution layer
- `knowledge_base/` as the grounding layer

It is no longer just a one-shot DEBUG_STEPS generator. The current runtime can already execute tool-enabled workflow steps and run a multi-step analysis flow over Jira + logs + KB artifacts.

---

## What This Repo Contains

This repository currently has five main parts:

- `runloop_agent/`  
  The current workflow runtime and execution entrypoint. This is the main implementation path.

- `mcp_servers/`  
  Stdlib-based MCP servers used by the workflow for Jira access, file/log inspection, and KB access.

- `knowledge_base/`  
  Local YAML-first knowledge objects used for grounding, retrieval, and analysis support.

- `answer/`  
  Example outputs and thinking notes. These are reference artifacts, not runtime inputs.

- `legacy/`  
  Archived older implementation and historical material. This is not the default execution path.

---

## Current Status

The repository is currently in an “M2 complete, M2.5 exploratory analysis” state.

### Milestone 2
The tool-enabled workflow runtime goal has been reached in practice:

- unified config via `example.toml`
- MCP-based tool execution through the new runtime path
- `llm_tool_step` support
- tool schema discovery and tool execution loop
- structured workflow execution with dump support

### Milestone 2.5
On top of the M2 runtime foundation, additional analysis-oriented workflow work has also been implemented, including:

- component scope extraction
- platform context normalization
- cross-layer conflict extraction
- root cause proposal
- evidence chain derivation
- handoff artifact bundling for downstream phases

See `TODO.MD` for the current milestone checklist and implementation status.

---

## Main Runtime Path

If you want to understand or run the current implementation, start here:

- Workflow entrypoint: `runloop_agent/workflow_demo.py`
- Main workflow definition: `runloop_agent/demo.yaml`
- Unified runtime config: `runloop_agent/example.toml`
- Platform inventory: `runloop_agent/platform_inventory.yaml`

Minimal example:

```bash
cd parsifal/parsifal-overlay/simple-rla

pip install -r requirements.txt
export OPENAI_API_KEY=...

python3 runloop_agent/workflow_demo.py \
  --config runloop_agent/demo.yaml \
  --config-file runloop_agent/example.toml \
  --initial-artifact jira_key=KERNEL-123 \
  --platform-inventory runloop_agent/platform_inventory.yaml \
  --log-level INFO \
  --dump
```

Optional debugging aids:

- enable prompt dump:
  ```bash
  export SIMPLE_RLA_DUMP_LLM_PROMPTS=1
  ```
- enable real-time output:
  ```bash
  --enable-real-time-output
  ```

Notes:
- `jira_key` is provided through `--initial-artifact jira_key=...`
- Jira credentials and MCP server config are read from `runloop_agent/example.toml`
- `--dump` writes run artifacts and step outputs for inspection

---

## Repository Layout

### `runloop_agent/`
The current runtime skeleton and workflow engine.

This directory contains:

- YAML workflow loading
- phase/step execution runtime
- `llm_step` / `llm_tool_step` / tool-step orchestration
- MCP client integration
- model calling and output parsing
- workflow dump support

Most active development currently happens here.

Key files:

- `runloop_agent/demo.yaml`
- `runloop_agent/workflow_demo.py`
- `runloop_agent/step_runner.py`
- `runloop_agent/output_parser.py`
- `runloop_agent/step_factory.py`
- `runloop_agent/platform_inventory.yaml`

---

### `mcp_servers/`
The tool layer used by the workflow runtime.

This includes:

- Jira MCP servers
- file/log evidence extraction tools
- KB access server
- JSON-RPC stdio server support

Important files:

- `mcp_servers/file_tools_server_v2.py`
- `mcp_servers/jira_mcp_server_v2.py`
- `mcp_servers/kb_server.py`

These are runtime backends for workflow steps, not standalone end-user applications.

---

### `knowledge_base/`
The local knowledge base used for grounding.

It is organized into topic-oriented YAML content such as:

- platform notes
- issue patterns
- RCA notes
- code notes
- playbooks
- workarounds

This directory is intended to provide grounding and retrieval support for workflow reasoning. It is not a generic document dump.

---

### `answer/`
Reference output and thought artifacts.

Examples include:

- example DEBUG_STEPS outputs
- free-form notes/thoughts

These files are useful for understanding the intended output style, but they are not the runtime’s primary logic.

---

### `legacy/`
Archived historical implementation and older design artifacts.

This directory should be treated as reference material only unless you are explicitly investigating the previous approach.

---

## Documents and Their Roles

The repository currently has several important documents with different purposes.

### `TODO.MD`
The current milestone checklist and implementation status.

Use this file to understand:
- which milestone goals are complete
- which sub-items remain unfinished
- which capabilities were implemented beyond the original milestone scope

### `requirement_v2.md`
The next-stage design target.

This file describes the intended direction beyond the current prototype, especially around:
- DEBUG_STEPS as an intermediate artifact
- device/code evidence execution
- evidence-driven RCA correction

It is a design target, not a statement of what is already implemented.

### `ANALYSIS_FLOW.MD`
A review of workflow step boundaries and artifact visibility.

This file is useful when thinking about:
- which step should see which artifacts
- how to separate transport artifacts from semantic artifacts
- how to keep LLM steps narrow and responsibility-specific

Depending on current workflow evolution, parts of it may lag behind the latest `runloop_agent/demo.yaml`.

### `runloop_agent/README.md`
Runtime-specific notes for the workflow skeleton.

Use this when you want:
- YAML shape expectations
- supported step types
- entrypoint details
- runtime-focused quickstart information

### `legacy/README.md`
Historical notes for the archived implementation.

---

## Current Workflow Shape

The current workflow is organized around two major parts:

### `jira_phase`
This phase handles:
- Jira lookup
- Jira property extraction
- attachment selection
- attachment download

It is primarily a case-intake and artifact-acquisition phase.

### `analysis_phase`
This phase currently handles:
- log signature extraction
- component scope extraction
- observation extraction
- platform context normalization
- retrieval context generation
- KB grounding
- issue summarization
- root cause proposal
- evidence chain generation
- final analysis handoff bundling

This means the runtime is already beyond a trivial one-step planner. It is operating as a multi-step, artifact-driven analysis flow.

---

## Knowledge Base and MCP Servers

The current runtime depends on both tool execution and knowledge grounding.

### MCP servers
The demo config wires local MCP servers for:
- Jira access
- file/log analysis
- KB lookup

These are the runtime’s execution backends.

### Knowledge base
The local KB under `knowledge_base/` provides:
- normalized platform knowledge
- issue pattern references
- RCA guidance
- workaround/playbook references

The intended model is:
- tools gather evidence
- KB grounds vocabulary and prior patterns
- workflow steps integrate both into structured outputs

---

## Notes and Caveats

A few practical caveats are worth calling out.

- The current provider path still depends on the `Responses`-style client in `runloop_agent/openai_responses.py`
- Real-time stream output is useful for observability, but it should not be treated as the authoritative final result
- Some workflow analysis steps are still evolving, and not all exploratory steps proved stable across smaller models
- `legacy/` is archived and should not be treated as the default runtime path
- Some design documents may lag behind the latest `demo.yaml` implementation

---

## Recommended Reading Order

If you are new to this repository, read in this order:

1. `README.md`
2. `runloop_agent/README.md`
3. `TODO.MD`
4. `runloop_agent/demo.yaml`
5. `requirement_v2.md`

If you are working on workflow step boundaries, also read:

6. `ANALYSIS_FLOW.MD`

If you are working on tool behavior:

7. `mcp_servers/file_tools_server_v2.py`
8. `runloop_agent/step_runner.py`

---

## Legacy Note

An older implementation path has been archived under `legacy/` and `runloop_agent/legacy/`.

Those materials are still useful as reference, but the default path for current development is the `runloop_agent/` runtime plus `mcp_servers/`.
