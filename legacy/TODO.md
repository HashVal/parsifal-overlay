# TODO - Parsifal Overlay

## 1) Skill: skills/parsifal-rca/SKILL.md (the cycle playbook)

Requirement:

- Provide an explicit, repeatable cycle that produces the two artifacts in this repo:
  - `DEBUG_STEPS.md` (round 1)
  - `KEY_EVIDENCE.md`
- Force the agent to follow the templates:
  - Use `parsifal_render` for file generation (avoid freehand markdown drift).
  - Require evidence refs to point to persisted artifacts.
- Define minimal input contract for a run (what the user must provide):
  - bug title + `description_short`
  - `platform=<soc>/<board>/<sku>`
  - kernel fingerprint fields (`repo/branch/commit/localversion/dtb`)
  - log paths or URLs (at least one)

Acceptance:

- Given one issue description and one log path, the agent produces both markdown files matching template structure.

## 2) Tool: parsifal_render (nanobot/agent/tools/parsifal_render.py)

Requirement:

- Render structured data into:
  - `DEBUG_STEPS.md` using `templates/DEBUG_STEPS.md`
  - `KEY_EVIDENCE.md` using `templates/KEY_EVIDENCE.md`
  - JIRA comment body using `templates/jira-comment.txt`
- Handle ID and timestamp generation consistently:
  - `debug_steps_id`: `DS-YYYYMMDD-<jira_key>-R<round>`
  - `evidence_id`: `EV-YYYYMMDD-<jira_key>-R<round>-<n>`
- Keep rendering deterministic:
  - stable key ordering
  - stable indentation
  - no "creative" sections outside the templates

Acceptance:

- Feeding it the example data produces markdown files that diff cleanly (no random ordering) and preserve required frontmatter keys.

## 3) Tool: parsifal_artifacts (nanobot/agent/tools/parsifal_artifacts.py)

Requirement:

- Create a stable artifacts directory for a run (suggested layout):
  - `parsifal/artifacts/<jira_key-or-local-id>/<timestamp>/...`
- Provide helper actions for:
  - creating run dirs
  - writing raw command output (stdout/stderr) to files
  - returning stable `ref` strings that can be embedded into `KEY_EVIDENCE.md`
- For MVP, support "log-only" collection (no SSH required):
  - ingest existing log files and copy/snapshot them into the run artifacts folder

Acceptance:

- For one run, every `supports[].ref` in `KEY_EVIDENCE.md` points to an artifact that exists on disk.

## 4) Tool: parsifal_validate (nanobot/agent/tools/parsifal_validate.py)

Requirement:

- Validate outputs before the cycle is considered complete.
- Minimal validation (must-have):
  - frontmatter parses
  - required keys exist (as per templates)
- Preferred validation:
  - validate JSON blocks (if used) against `schemas/*.schema.json`
  - reject missing/empty required fields (`jira_key`, `target.platform`, etc.)

Acceptance:

- Running validation on `examples/*` returns OK.
- Running validation on a broken/missing-field file returns a clear actionable error.

## 5) Domain Modules: nanobot/parsifal_rca/ (hard logic used by tools)

Requirement:

Implement minimal shared logic so tools don’t duplicate policy:

- `templates.py`
  - locate template files under `parsifal/kernel-rca-bot/templates/`
  - render helpers + ID/timestamp helpers
- `artifacts.py`
  - artifact path policy + `ref` formatting helpers
- (Optional but useful even in MVP) `fingerprint.py`
  - normalize `platform=<soc>/<board>/<sku>`
  - normalize kernel fingerprint fields (strip/validate)

Acceptance:

- `parsifal_render` and `parsifal_artifacts` share the same path/id rules.

## 6) Glue: register Parsifal tools in nanobot (nanobot/agent/loop.py)

Requirement:

- Update nanobot tool registration so the agent can call:
  - `parsifal_render`
  - `parsifal_artifacts`
  - `parsifal_validate`
- Keep tool outputs short and structured (avoid tool spam in context).

Acceptance:

- In a nanobot chat, the model can successfully call the tools and receive results.

## 7) Glue: minimal config hooks (nanobot/config/schema.py)

Requirement:

- Add config fields required to run the MVP without hardcoding:
  - `parsifal.spec_root` (points to `/home/node/.openclaw/workspace/parsifal/kernel-rca-bot`)
  - `parsifal.artifacts_root` (points to `/home/node/.openclaw/workspace/parsifal/artifacts`)
- Default to sensible workspace-relative paths.

Acceptance:

- A fresh workspace can run one cycle without editing code paths.

## 8) CLI entry point (manual cycle runner)

Requirement:

- Add a CLI command that triggers one cycle using the skill + tools.
- Suggested interface:
  - `nanobot parsifal cycle --input <issue.yaml|issue.md> --out <dir>`
- For MVP, the input can be minimal and local (no JIRA).

Acceptance:

- One command produces a run directory containing:
  - `DEBUG_STEPS.md`
  - `KEY_EVIDENCE.md`
  - `jira-comment.txt` (or printed to stdout)
  - `artifacts/` with referenced raw logs

===============DONE ABOVE, TODO BELOW====================
