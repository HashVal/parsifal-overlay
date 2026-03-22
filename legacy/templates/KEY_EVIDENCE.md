---
evidence_id: "EV-YYYYMMDD-<jira_key>-R<round>-<n>"
jira_key: "PROJ-1234"
created_at: "YYYY-MM-DDTHH:MM:SSZ"

bug:
  title: "<short title>"
  description_short: "<1-3 sentences>"

target:
  platform:
    - "<soc>/<board>/<sku>"
  device_id: "<optional>"
  kernel:
    repo: "<git url or path>"
    branch: "<branch/tag>"
    commit: "<sha>"
    localversion: "<localversion/build id>"
    dtb: "<dtb file name>"

rca:
  one_line: "<current best root cause>"
  scope: "<what is affected: platforms/kernels/subsystems>"

confidence:
  value: 0.0
  rationale:
    - "+0.3 signature matches KB pattern"
    - "+0.3 device check directly confirms"
    - "+0.3 code path closes the loop"
    - "-0.2 conflicting evidence"

claims:
  - id: H1
    claim: "<hypothesis / conclusion point>"
    supports:
      - type: device_check
        ref: "artifacts/device/<device_id>/<timestamp>/cmd_D1.txt"
        excerpt: "<minimal excerpt>"
        collected_at: "YYYY-MM-DDTHH:MM:SSZ"
      - type: code_snippet
        ref: "repo:<url>@<sha>:<path>#L<line>"
        excerpt: "<minimal excerpt>"
        collected_at: "YYYY-MM-DDTHH:MM:SSZ"

next_actions:
  - "<if not resolved, the most valuable next check>"
---

# KEY_EVIDENCE

## RCA

<Repeat rca.one_line>

## Key Evidence

Keep excerpts minimal. Every item must have a stable `ref` pointing to the raw artifact.
