# simple-rla

A minimal "runloop agent" + a few stdlib-only MCP servers.

Layout:

- `runloop_agent/`: OpenAI Responses-based runloop that can call MCP tools over stdio
- `mcp_servers/`: minimal MCP servers (currently: Jira)

Quick start:

```bash
cd parsifal/parsifal-overlay/simple-rla

# Configure Jira auth in runloop_agent/example.mcp.toml (or export env vars)
# Recommended default: bearer auth + /rest/api/latest
export OPENAI_API_KEY=...

python3 -m runloop_agent.responses_runloop \
  --config runloop_agent/example.mcp.toml \
  --model gpt-4.1-mini \
  --jira-key KERNEL-123
```

Jira auth notes:

- Recommended example config uses:
  - `JIRA_AUTH="bearer"`
  - `JIRA_TOKEN="..."`
  - `JIRA_API_PREFIX="/rest/api/latest"`
- A known-working alternative in some environments is:
  - `JIRA_AUTH="basic"`
  - `JIRA_USER="..."`
  - `JIRA_PASSWORD="..."`
- Do **not** assume `basic` should always use `JIRA_USER:JIRA_TOKEN`; that depends on the target Jira environment.
