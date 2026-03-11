# Parsifal Runloop Agent (Python 3.11)

This is a minimal "runloop agent" skeleton that can talk to one or more MCP servers over stdio.

Goals:

- Show how a runloop agent discovers MCP tools (`tools/list`) and calls them (`tools/call`).
- Keep tool outputs out of the LLM context: store full request/response under an artifacts dir and return a short summary + `ref`.
- Provide a tiny demo cycle using MCP tools.
  - Jira tools (pure stdlib MCP server): `jira_search`, `jira_get`, `jira_comment`.
  - (Optional) Parsifal overlay tools: `parsifal_artifacts`, `parsifal_render`, `parsifal_validate`.

This code intentionally avoids third-party deps (stdlib only) so it's easy to embed.

## Quick Start (demo cycle)

1) Create a config TOML:

- `parsifal/parsifal-overlay/simple-rla/runloop_agent/example.mcp.toml`

2) Run the OpenAI Responses runloop (talks to MCP tools):

```bash
cd parsifal/parsifal-overlay/simple-rla
export OPENAI_API_KEY=...   # required

python3 -m runloop_agent.responses_runloop \
  --config runloop_agent/example.mcp.toml \
  --model gpt-4.1-mini \
  --jira-key KERNEL-123 \
  --max-steps 16
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

Example (private Jira, basic auth):

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
JIRA_BASE_URL = "https://jira.devtools.mycompany.com"
JIRA_API_PREFIX = "/rest/api/2"
JIRA_AUTH = "basic"
JIRA_USER = "YOUR_USER"
JIRA_TOKEN = "YOUR_TOKEN"
JIRA_VERIFY_SSL = "true"
```

Notes:

- For Jira Cloud, you probably want `JIRA_API_PREFIX="/rest/api/3"`.
- If you don't want secrets in the TOML, remove `JIRA_USER`/`JIRA_TOKEN` from the TOML and export them in your shell; the runloop inherits `os.environ`.

## MCP Contract Expectations

This client speaks JSON-RPC 2.0 over newline-delimited stdio.

It uses:

- `initialize`
- `tools/list`
- `tools/call`

Tool results are expected to be MCP-style content blocks; this client extracts `text` blocks and returns `text`.
