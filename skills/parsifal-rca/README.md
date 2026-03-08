# Parsifal RCA Skill

This skill drives a single RCA cycle using the Parsifal spec templates.
It is designed to generate round-1 DEBUG_STEPS and KEY_EVIDENCE for one issue.

## What it produces

- DEBUG_STEPS.md (round 1)
- KEY_EVIDENCE.md
- Optional draft JIRA comment body (based on jira-comment.txt)

## Required tools (MCP)

- mcp_parsifal_parsifal_render
- mcp_parsifal_parsifal_artifacts
- mcp_parsifal_parsifal_validate (recommended)

## Inputs you must provide

- bug title + description_short
- platform = <soc>/<board>/<sku>
- kernel fingerprint: repo, branch, commit, localversion, dtb
- at least one log path or URL

## Spec references

- /home/node/.openclaw/workspace/parsifal/kernel-rca-bot/templates
- /home/node/.openclaw/workspace/parsifal/kernel-rca-bot/examples
