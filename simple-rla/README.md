# simple-rla

A minimal "runloop agent" + a few stdlib-only MCP servers.

Layout:

- `runloop_agent/`: OpenAI Responses-based runloop that can call MCP tools over stdio
- `mcp_servers/`: minimal MCP servers (currently: Jira)

Quick start:

```bash
cd parsifal/parsifal-overlay/simple-rla

# Configure Jira auth in runloop_agent/example.mcp.toml (or export env vars)
export OPENAI_API_KEY=...

python3 -m runloop_agent.responses_runloop \
  --config runloop_agent/example.mcp.toml \
  --model gpt-4.1-mini \
  --jira-key KERNEL-123
```
