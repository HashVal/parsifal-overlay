# Parsifal Runloop Agent (Python 3.11)

This is a minimal "runloop agent" skeleton that can talk to one or more MCP servers over stdio.

Goals:

- Show how a runloop agent discovers MCP tools (`tools/list`) and calls them (`tools/call`).
- Keep tool outputs out of the LLM context: store full request/response under an artifacts dir and return a short summary + `ref`.
- Provide a tiny demo cycle using MCP tools.
  - Jira tools (pure stdlib MCP server): `jira_search`, `jira_get`, `jira_comment`.
  - (Optional) Parsifal overlay tools: `parsifal_artifacts`, `parsifal_render`, `parsifal_validate`.

This code intentionally avoids third-party deps (stdlib only) so it's easy to embed.

Current Jira MCP tools:

- `jira_search`
- `jira_get`
- `jira_comment`
- `jira_transitions`
- `jira_transition`
- `jira_list_attachments`
- `jira_fetch_attachment`

Current local file/log MCP tools:

- `file_head`
- `file_tail`
- `file_read_range`
- `file_grep`
- `log_extract_signatures`
- `log_compare`

Current KB MCP tools (MVP skeleton):

- `kb_get`
- `kb_search`
- `kb_ground`

## Step 5 possible failure reason artifacts

The current `fc_runloop.py` now inserts an explicit Step 5 `provide_possible_failure_reason` phase after KB grounding and before provisional DEBUG_STEPS drafting.

This phase:
- consumes only previously prepared structured inputs:
  - Jira context
  - compacted artifact/signature pack
  - compacted KB grounding pack
- does not introduce new MCP tool calls by default
- generates at most 3 ranked possible failure reasons
- validates the generated JSON shape
- allows one repair retry if the first output is structurally invalid

Artifacts written into the run workspace root:

```text
step5_possible_failure_reason.json
step5_possible_failure_reason.md
step5_possible_failure_reason.compact.json
```

Artifact roles:
- `step5_possible_failure_reason.json`
  - full machine-readable artifact for dumps, tests, and downstream inspection
- `step5_possible_failure_reason.md`
  - human-readable rendering of the same Step 5 result
- `step5_possible_failure_reason.compact.json`
  - compact LLM-facing artifact intended to be the primary input for subsequent DEBUG_STEPS drafting

Compact-consumption policy:
- the later DEBUG_STEPS phase should prefer the compact Step 5 artifact over re-consuming broad raw Jira/signature/KB payloads
- this is intended to reduce context growth and preserve a hypothesis-first drafting path

## Workflow Configuration

The agent behavior is defined in `workflow.yaml` (configurable via `--workflow`):

```yaml
name: kernel_rca
version: "1.0"

llm:
  system_prompt: |
    You are a kernel RCA runloop agent...
  initial_message_template: |
    Start RCA for Jira issue {jira_key}...
  default_message: "List available tools..."
  temperature: 0.2
  tool_choice: auto

execution:
  max_steps: 12
  request_timeout_s: 300

tools:
  on_error: continue  # continue|abort
  include_traceback: false
```

Variable substitution in `initial_message_template`: `{jira_key}` is replaced with the value from `--jira-key`.

## Quick Start (demo cycle)

1) Install dependency (only PyYAML is required for workflow):

```bash
pip install pyyaml
```

2) Create configs (`example.mcp.toml` + `workflow.yaml` already provided).

1) Create a config TOML:

- `parsifal/parsifal-overlay/simple-rla/runloop_agent/example.mcp.toml`

2) Run the OpenAI Responses runloop (talks to MCP tools). Use `--dump` to save each round context:

Option A (module mode; recommended):

```bash
cd parsifal/parsifal-overlay/simple-rla
export OPENAI_API_KEY=...

python3 -m runloop_agent.responses_runloop \
  --config runloop_agent/example.mcp.toml \
  --model gpt-4.1-mini \
  --jira-key KERNEL-123 \
  --max-steps 16 \
  --log-level DEBUG \
  --dump
```

Option B (script mode; works from inside `runloop_agent/`). Use `--dump` to save each round context to `./dumps/<timestamp>/`.

If your OpenAI gateway does not support `/v1/responses` (HTTP 404), use `fc_runloop.py` instead (it calls `/v1/chat/completions`).
Also ensure `OPENAI_BASE_URL` includes `/v1` when using an OpenAI-compatible gateway (e.g. `http://host:3001/v1`).

```bash
cd parsifal/parsifal-overlay/simple-rla/runloop_agent
export OPENAI_API_KEY=...

python3 responses_runloop.py \
  --config example.mcp.toml \
  --model gpt-4.1-mini \
  --jira-key KERNEL-123 \
  --max-steps 16 \
  --log-level DEBUG
```

Optional: Parsifal overlay demo (requires `mcp` package installed for the overlay server; not needed for Jira-only demo):

```bash
cd parsifal/parsifal-overlay/simple-rla
python3 -m runloop_agent.demo_parsifal_cycle \
  --config runloop_agent/example.mcp.toml \
  --log /path/to/some.log
```

Notes:

- The Parsifal overlay MCP server (`parsifal/parsifal-overlay/mcp_server.py`) currently depends on the `mcp` Python package.
- This runloop agent is just the client side; you can swap in other MCP servers (JIRA, DEVICE_EXEC, CODE_SCAN) by adding them to the config.

## Config Format

This runloop expects a TOML file (parsed via `tomllib`).

Example (bearer auth style):

```toml
[client]
name = "kernel-rca-runloop"
version = "0.1"
protocol_version = "2024-11-05"
artifacts_root = "../../artifacts/runloop"

[mcp_servers.jira]
command = "python3"
args = ["-m", "mcp_servers.jira_server"]

[mcp_servers.jira.env]
JIRA_BASE_URL = ""
JIRA_API_PREFIX = ""
JIRA_AUTH = ""
JIRA_TOKEN = ""
JIRA_VERIFY_SSL = ""

[mcp_servers.files]
command = "python3"
args = ["-m", "mcp_servers.file_tools_server"]

[mcp_servers.files.env]
FILE_TOOLS_ROOT = "../../artifacts/runloop"
FILE_TOOLS_MAX_FILE_BYTES = "8388608"

[mcp_servers.kb]
command = "python3"
args = ["-m", "mcp_servers.kb_server"]
```

Alternative (basic auth style):

```toml
[mcp_servers.jira.env]
JIRA_BASE_URL = ""
JIRA_API_PREFIX = ""
JIRA_AUTH = ""
JIRA_USER = ""
JIRA_PASSWORD = ""
JIRA_VERIFY_SSL = ""
```

Notes:

- For Jira Cloud, you may want `JIRA_API_PREFIX="/rest/api/3"`.
- If you don't want secrets in the TOML, leave them empty and export them in your shell; the runloop inherits `os.environ`.
- Jira auth failures are diagnosed more explicitly: `401`, HTML login/SSO pages, and non-JSON responses are reported with clearer hints.

## MCP Contract Expectations

This client speaks JSON-RPC 2.0 over newline-delimited stdio.

It uses:

- `initialize`
- `tools/list`
- `tools/call`

Tool results are expected to be MCP-style content blocks; this client extracts `text` blocks and returns `text`.

## Run workspace and dump layout

Each run now creates a dedicated workspace directory under the configured `artifacts_root`.

Layout:

```text
<artifacts_root>/runs/<jira_key-or-adhoc>/<timestamp>/
  meta.json
  session.log
  attachments/
  dumps/
    meta.json
    iteration_001.json
    iteration_002.json
```

Notes:

- `meta.json` stores run-level metadata such as model, workflow, jira key, workspace path, and whether dump mode is enabled.
- `session.log` stores the run log in addition to stderr output.
- `attachments/` is the default location for Jira attachment downloads during that run.
- `dumps/` is only populated when `--dump` is enabled.

## --dump behavior

`--dump` already existed; it now writes into the current run workspace instead of creating a separate timestamped dump tree under the current working directory.

When enabled, each LLM iteration is stored as:

```text
dumps/iteration_001.json
dumps/iteration_002.json
```

Each iteration dump contains at least:

- `iteration`
- `timestamp`
- `model`
- `system_prompt`
- `user_prompt`
- `llm_response`
- `tool_calls`
- `tool_results`

Mode-specific raw fields (`messages`, `input_items`, `response`, etc.) are still preserved for debugging.

## Local file/log tools

The local file/log MCP server exposes a small read-only inspection surface for artifacts saved into the run workspace.

Tools:

- `file_head(path, lines?, max_chars?)`
- `file_tail(path, lines?, max_chars?)`
- `file_read_range(path, start_line, end_line, max_chars?)`
- `file_grep(path, pattern, ignore_case?, context_before?, context_after?, max_matches?, max_chars?)`
- `log_extract_signatures(path, profile="kernel", ...)`
- `log_compare(left_path, right_path, profile="kernel", ...)`

Behavior notes:

- The server is read-only.
- By default it only reads files under the current run workspace (`SIMPLE_RLA_WORKSPACE_DIR`).
- `FILE_TOOLS_ROOT` is provided in `example.mcp.toml` as a fallback for manual/ad-hoc runs.
- Outputs are clipped to avoid flooding the model context.
- The file/log MCP server now emits request/response summary logs for observability (tool name, path, counts, truncation, compare summary).
- `log_extract_signatures` is rule-based and now returns layered output for kernel logs: `essential`, `fatal`, `errors`, `subsystem_hints`, and `summary`.
- `log_compare` is RCA-oriented: it compares normalized common prefix plus layered fatal/error signatures, not a raw full diff.

## KB tools

The KB MCP server reads YAML-backed KB objects from:

```text
simple-rla/knowledge_base/
```

Current MVP tools:

- `kb_get(id)`
  - fetch one KB object by stable id
- `kb_search(query, ...)`
  - perform lightweight keyword/metadata retrieval over local KB objects
- `kb_ground(context, signals, hints?, limits?)`
  - build a lightweight grounding package for the current case
  - aggregation is allowed; over-reasoning is intentionally avoided

Design notes:

- The current KB source of truth is YAML-first and human-maintained.
- The current `kb_ground` contract is designed around structured context/signals, not raw long-form logs.
- `kb_ground` returns lightweight matched objects grouped by kind and may surface coverage gaps when some expected kinds have no sufficiently relevant hits.
- `kb_tools.md` under `mcp_servers/` records the current design notes for KB tool inputs/outputs and balance policy.

## Jira attachments

The Jira MCP server now exposes two attachment-focused tools:

- `jira_list_attachments(key)`
  - returns a lightweight list of attachments on an issue
  - includes fields such as `id`, `filename`, `mime_type`, `size`, `created`, `author`

- `jira_fetch_attachment(key, attachment_id)`
  - downloads one attachment using the same Jira auth config
  - saves it into the current run workspace attachments directory
  - returns a compact result with:
    - `saved_path`
    - `size`
    - `mime_type`
    - `binary`
    - `preview`

Design note:

- Attachment contents are **not** returned in full to the model.
- This avoids overloading MCP stdio messages and keeps large logs out of the LLM context.
- The attachment save path is runtime-controlled and defaults to the current run workspace attachments directory.
