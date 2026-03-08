---
debug_steps_id: "DS-YYYYMMDD-<jira_key>-R<round>"
jira_key: "PROJ-1234"
created_at: "YYYY-MM-DDTHH:MM:SSZ"
round: 1

bug:
  title: "<short title>"
  description_short: "<1-3 sentences, no walls of text>"

target:
  platform:
    - "<soc>/<board>/<sku>"
  device_id: "<optional: hostname/asset-id>"
  kernel:
    repo: "<git url or path>"
    branch: "<branch/tag>"
    commit: "<sha>"
    localversion: "<CONFIG_LOCALVERSION or build id>"
    dtb: "<dtb file name>"

inputs:
  jira_url: "<url>"
  test_artifacts:
    - "<path-or-url>"
  kb_hits:
    - "kb/<subsystem>/<pattern_id>.md"

budget:
  max_device_commands: 20
  max_code_reads: 30

hypotheses:
  - id: H1
    claim: "<one-sentence hypothesis>"
    confidence: 0.55
    why:
      - "sig:<signature>"
      - "kb:<pattern_id>"
    prove:
      - "<what evidence would strongly confirm>"
    disprove:
      - "<what evidence would falsify>"

code_check:
  - id: C1
    goal: "<what we want to learn>"
    repo: "kernel"
    actions:
      - "git grep -n '<string>'"
      - "git log -p -n 20 -- <path>"
    expect:
      - "<expected finding>"
    branches:
      - if: "found:<condition>"
        next: ["C2", "D1"]
      - if: "not_found"
        next: ["D1"]

device_check:
  - id: D1
    goal: "<what we want to learn>"
    target: "ssh|serial|log-only"
    risk: "read-only|low|medium|high"
    rollback:
      - "<rollback step if needed>"
    commands:
      - "dmesg -T | tail -n 300"
      - "uname -a"
    expect:
      - "<what you expect to see>"
    parse_hints:
      - "regex:<pattern>"
    branches:
      - if: "match:<condition>"
        next: ["D2"]
      - if: "no_match"
        next: ["C2"]

stop_conditions:
  - "evidence_count>=3 && top_hypothesis.confidence>=0.8"
  - "no_new_evidence_in_2_rounds -> NEED_MORE_INFO"
  - "risk_escalation_required -> BLOCKED"

notes:
  - "Keep steps minimal; prefer tests that disprove a hypothesis fast."
---

# DEBUG_STEPS

## Summary

- Scope: <platforms> + <kernel fingerprint>
- Goal: produce RCA + KeyEvidence or a precise NEED_MORE_INFO list

## Plan

### Code Check

Fill from frontmatter `code_check` in human-readable form if desired.

### Device Check

Fill from frontmatter `device_check` in human-readable form if desired.

## Expected Outputs

- Updated hypothesis ranking
- New KeyEvidence items (each with a stable ref)
- Next-round DEBUG_STEPS (if not converged)
