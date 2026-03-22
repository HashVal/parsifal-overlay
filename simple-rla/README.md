# simple-rla

Structured workflow runtime skeleton + a few stdlib-only MCP servers.

Layout:

- `runloop_agent/`: workflow runtime + `workflow_demo.py` entrypoint (Phase -> Step)
- `mcp_servers/`: stdlib MCP servers (Jira v2 + file/log inspection v2 + KB)
- `knowledge_base/`: YAML-first local KB objects (issue patterns, RCA objects, platform notes, code notes, playbooks, workarounds)

Quick start (`workflow_demo.py`):

```bash
cd parsifal/parsifal-overlay/simple-rla

# Install deps (PyYAML only)
pip install -r requirements.txt

export OPENAI_API_KEY=...

# Configure MCP servers + runtime in runloop_agent/example.toml
# (Jira auth is required if the demo workflow uses Jira tools.)

python3 runloop_agent/workflow_demo.py \
  --config runloop_agent/demo.yaml \
  --config-file runloop_agent/example.toml \
  --initial-artifact jira_key=KERNEL-123 \
  --platform-inventory runloop_agent/platform_inventory.yaml \
  --log-level INFO \
  --dump
```

Legacy note: an older runloop-based implementation (Responses/ChatCompletions runloop + configs) was moved under `runloop_agent/legacy/` and is no longer the default path.
