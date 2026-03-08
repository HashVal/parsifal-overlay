---
name: parsifal-rca
description: Run one Parsifal RCA cycle and generate DEBUG_STEPS.md + KEY_EVIDENCE.md from the spec templates.
---

# Parsifal RCA (Cycle Playbook)

## Triggers

- parsifal rca
- kernel rca cycle
- generate DEBUG_STEPS / KEY_EVIDENCE
- run one rca cycle

## Use Cases

- Create round-1 DEBUG_STEPS and KEY_EVIDENCE for a single issue.
- Produce a draft JIRA comment body (optional for MVP).
- Validate that outputs conform to the spec templates.

## Inputs

Required:

- bug title
- description_short
- platform = <soc>/<board>/<sku>
- kernel fingerprint: repo, branch, commit, localversion, dtb
- at least one log path or URL

Optional:

- jira_key and jira_url
- device_id
- kb_hits (paths to KB entries)

## Outputs

- DEBUG_STEPS.md (round 1)
- KEY_EVIDENCE.md
- Optional: jira-comment.txt body

## Workflow

1. Validate required inputs; ask only for missing fields.
2. Create a run directory with mcp_parsifal_parsifal_artifacts.
3. Persist provided logs into artifacts and capture refs.
4. Call mcp_parsifal_parsifal_render to generate:
   - DEBUG_STEPS.md using templates/DEBUG_STEPS.md
   - KEY_EVIDENCE.md using templates/KEY_EVIDENCE.md
5. Ensure all evidence refs in KEY_EVIDENCE.md point to real artifacts.
6. Run mcp_parsifal_parsifal_validate; if it fails, fix inputs and re-render.

## Tooling Rules

- Always use mcp_parsifal_parsifal_render for file generation; do not handwrite templates.
- Always use mcp_parsifal_parsifal_artifacts for any raw log or command output.
- MVP scope is log-only: do not run SSH/serial commands in this skill.

## Acceptance

- Given one issue description and one log, the two markdown files match template structure.
- Required frontmatter keys exist and are non-empty.
- Every supports[].ref points to a file that exists on disk.

## References

- Spec root: /home/node/.openclaw/workspace/parsifal/kernel-rca-bot
- Templates: /home/node/.openclaw/workspace/parsifal/kernel-rca-bot/templates
