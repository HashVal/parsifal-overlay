# Parsifal Overlay Setup

This note explains how to wire Parsifal skills and tools into nanobot.

## Skills Setup

Nanobot loads skills from the workspace path:

- Skills directory: `<workspace>/skills/<skill-name>/SKILL.md`

Two ways to make the skill visible:

1) Set nanobot workspace to the OpenClaw workspace
   - Set `agents.defaults.workspace` to `/home/node/.openclaw/workspace` in nanobot config
   - Then nanobot will discover:
     - `/home/node/.openclaw/workspace/parsifal/parsifal-overlay/skills/parsifal-rca/SKILL.md`

2) Copy or symlink the skill into nanobot default workspace
   - Default workspace: `~/.nanobot/workspace`
   - Ensure this exists:
     - `~/.nanobot/workspace/skills/parsifal-rca/SKILL.md`

## Tools Setup (MCP External Registration)

Tools are exposed via an MCP server so nanobot can register them without code changes.

### 1) Run MCP server (stdio)

Command:

```
python3 /home/node/.openclaw/workspace/parsifal/parsifal-overlay/mcp_server.py
```

### 2) Configure nanobot to connect

Add to `~/.nanobot/config.json` (or copy `nanobot-mcp.json` from this repo):

```json
{
  "tools": {
    "mcpServers": {
      "parsifal": {
        "type": "stdio",
        "command": "python3",
        "args": ["/home/node/.openclaw/workspace/parsifal/parsifal-overlay/mcp_server.py"],
        "toolTimeout": 30
      }
    }
  }
}
```

### 3) Tool names inside nanobot

MCP tools are auto-prefixed:

- `mcp_parsifal_parsifal_render`
- `mcp_parsifal_parsifal_artifacts`
- `mcp_parsifal_parsifal_validate`

## Minimal Config Hooks

Add config entries so paths are not hardcoded:

- `parsifal.spec_root` -> `/home/node/.openclaw/workspace/parsifal/kernel-rca-bot`
- `parsifal.artifacts_root` -> `/home/node/.openclaw/workspace/parsifal/artifacts`

## Runtime Use

Once the above is wired:

- In a nanobot chat, say: "run parsifal rca cycle"
- The agent should read `SKILL.md`, create artifacts, render outputs, and validate

## parsifal_artifacts Usage Example

Example tool calls (log-only MVP):

```json
{
  "action": "init_run_dir",
  "issue_id": "KERNEL-0001"
}
```

```json
{
  "action": "ingest_log",
  "issue_id": "KERNEL-0001",
  "log_path": "/home/node/logs/boot.log",
  "log_name": "boot.log"
}
```

```json
{
  "action": "write_text",
  "issue_id": "KERNEL-0001",
  "filename": "cmd_dmesg.txt",
  "content": "<raw dmesg output>"
}
```

Returned refs look like:

- `artifacts/KERNEL-0001/20260308T123456Z/boot.log`
- `artifacts/KERNEL-0001/20260308T123456Z/cmd_dmesg.txt`

## References

- Spec repo: `/home/node/.openclaw/workspace/parsifal/kernel-rca-bot`
- Skill: `/home/node/.openclaw/workspace/parsifal/parsifal-overlay/skills/parsifal-rca/SKILL.md`
