# runloop_agent (Workflow Skeleton Runtime)

This directory contains the **Phase -> Step** workflow runtime skeleton used by `workflow_demo.py`.

It is intended to be:
- deterministic and inspectable (tool outputs are stored under a run workspace)
- MCP-first for I/O (Jira, file/log inspection, KB)
- small enough to embed (stdlib-only, except `PyYAML` for loading workflow YAML)

## Entry Point

Run a workflow from a YAML spec using the unified TOML config:

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

Notes:
- `--initial-artifact jira_key=...` provides the `jira_key` used by `${workflow.inputs.jira_key}` bindings.
- Jira auth/env is provided to the Jira MCP server via `example.toml` (`[mcp.servers.jira.env]`).

## Workflow YAML Shape (Current)

This runtime currently expects a small YAML shape:

- `workflow_id` (optional)
- `start_phase` (optional)
- `terminal_phases` (optional)
- `phases` (required list)
  - each phase:
    - `id` (required)
    - `type` (currently only `standard_phase`)
    - `next_phase` (optional)
    - `max_rollbacks` / `max_step_attempts` (optional)
    - `steps` (required list)
      - each step:
        - `id` (required)
        - `type` (one of `tool_step`, `llm_step`, `llm_tool_step`, `deterministic_step`)
        - `config` (optional mapping, stored as step metadata)

Tool-step argument bindings support:
- `${workflow.inputs.<key>}`: look up `<key>` from visible inputs
- `${artifacts.<key>}`: look up `<key>` from current global artifacts
- `{"$repeat": "<binding>", "template": ...}`: list expansion (see `tool_step.py`)

## MCP Servers

The demo config `example.toml` wires these stdlib MCP servers:
- Jira: `mcp_servers.jira_mcp_server_v2`
- Files/logs: `mcp_servers.file_tools_server_v2`
- KB: `mcp_servers.kb_server`

## Legacy

An older runloop-based implementation (Responses/ChatCompletions runloop + configs + docs) was archived under `runloop_agent/legacy/`.
It is not used by `workflow_demo.py`.

