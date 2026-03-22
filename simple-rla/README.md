# simple-rla

A minimal "runloop agent" + a few stdlib-only MCP servers.

Layout:

- `runloop_agent/`: OpenAI Responses-based runloop that can call MCP tools over stdio
- `mcp_servers/`: minimal MCP servers (currently: Jira + local file/log inspection + KB skeleton)
- `knowledge_base/`: YAML-first local KB source of truth for issue patterns, RCA objects, platform notes, code notes, playbooks, and workarounds

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

Jira auth notes:

- Example config fields are intentionally left blank in templates:
  - `JIRA_AUTH=""`
  - `JIRA_TOKEN=""`
  - `JIRA_API_PREFIX=""`
- Another supported pattern is:
  - `JIRA_AUTH=""`
  - `JIRA_USER=""`
  - `JIRA_PASSWORD=""`
- Prefer exporting secrets from your shell or CI environment instead of committing them to TOML files.

Recent Jira auth updates:

- Default Jira API prefix is now aligned to `/rest/api/latest` in runtime logic when configured that way.
- `jira_server.py` now prefers `JIRA_PASSWORD` for `basic` auth.
- `JIRA_TOKEN` is still accepted as a fallback secret in `basic` mode for compatibility.
- Jira auth failures now produce clearer diagnostics for `401`, HTML login/SSO pages, and non-JSON responses.
- Jira attachment support is now exposed as dedicated MCP tools:
  - `jira_list_attachments`
  - `jira_fetch_attachment`
- Attachments are downloaded into the current run workspace attachments directory and returned as compact metadata + preview, rather than sending full file contents back through the model context.
- Each run now creates its own workspace/output directory under `artifacts_root`, and `--dump` writes iteration files into that run workspace instead of a standalone `cwd/dumps/...` tree.
- A new local file/log MCP server is available for run-workspace artifacts, exposing:
  - `file_head`
  - `file_tail`
  - `file_read_range`
  - `file_grep`
  - `log_extract_signatures`
  - `log_compare`
- These tools are read-only and are intended to let the agent inspect downloaded logs (for example `dmesg` attachments) without relying only on truncated attachment previews.
- A new KB MCP server skeleton is also available, exposing:
  - `kb_get`
  - `kb_search`
  - `kb_ground`
- The KB source of truth currently lives under `simple-rla/knowledge_base/` and is designed to be YAML-first and human-maintained.
- Current KB design notes are documented in `mcp_servers/kb_tools.md`.
- `kb_ground` is intended to build a lightweight grounding package for a case: aggregation is allowed, but over-reasoning is intentionally avoided.
- KB matching now also includes a lightweight platform taxonomy step so generic platform notes (for example `generic_x86_platforms`) can still be matched from more specific case platform labels (for example `BMG`).
- The current fc-based runloop now includes an explicit Step 5 `provide_possible_failure_reason` phase between KB grounding and provisional DEBUG_STEPS drafting.
- Step 5 writes three run-workspace artifacts:
  - `step5_possible_failure_reason.json`
  - `step5_possible_failure_reason.md`
  - `step5_possible_failure_reason.compact.json`
- The full JSON/Markdown artifacts are intended for dumps, review, and human inspection.
- The compact JSON artifact is intended as the primary LLM-facing input to the subsequent DEBUG_STEPS drafting phase.
