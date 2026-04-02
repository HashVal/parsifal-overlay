# Tristan Patch JSON Draft (MVP)

This document is a draft JSON-shape specification for per-agent patches in the Tristan MVP workflow.

This document follows:
- `data-model-schema.md`
- `data-model-semantics.md`
- `agent-profiles.md`
- `patch-contract.md`

It is intentionally written in two phases:
1. define a common patch envelope
2. define concrete patch JSON drafts per agent

This draft currently includes:
- common patch envelope
- `IntakePatch`
- `JudgePatch`
- `HypothesisPatch`
- `ProbePatch`

This completes the first draft set of the four MVP per-agent patch shapes.

---

## 1. Common Patch Envelope

All agent patches should share a common outer structure.

### Draft shape

```json
{
  "patch_id": "...",
  "patch_type": "...",
  "actor": "...",
  "generated_at": "2026-04-02T13:00:00Z",
  "base_case_id": "...",
  "base_status": "...",
  "base_loop_index": 0,
  "state_transition_request": {
    "from": "...",
    "to": "..."
  },
  "payload": {
    "...": "..."
  }
}
```

---

### 1.1 `patch_id`

Purpose:
- provides a stable patch identity for audit, history linkage, merge diagnostics, and patch-level traceability

---

### 1.2 `patch_type`

Purpose:
- identifies the patch contract type

Examples:
- `intake_patch`
- `hypothesis_patch`
- `probe_patch`
- `judge_patch`

---

### 1.3 `actor`

Purpose:
- explicitly identifies the acting agent

Expected values in MVP:
- `intake`
- `hypothesis`
- `probe`
- `judge`

This is intentionally explicit even if it overlaps with `patch_type`.

---

### 1.4 `generated_at`

Purpose:
- records when the patch was produced

This supports auditability, stale-patch detection, merge diagnostics, and history linkage.

---

### 1.5 `base_case_id`

Purpose:
- identifies the target case the patch is intended for

---

### 1.6 `base_status`

Purpose:
- states the case status the agent expected when producing the patch

This supports harness-side validation of legal transitions and stale/ill-timed patches.

---

### 1.7 `base_loop_index`

Purpose:
- states the loop index the patch was generated against

This supports loop-aware validation and prevents accidental cross-loop patch confusion.

---

### 1.8 `state_transition_request`

Purpose:
- allows the patch to propose a state transition
- does not imply unilateral authority to force that transition

MVP rule:
- harness validates whether the requested transition is legal and supported

This field may be `null` if no transition is being proposed.

---

### 1.9 `payload`

Purpose:
- contains the patch-specific update content

This keeps all patch types structurally aligned at the top level.

---

## 2. Shared Patch Notes

### 2.1 Patches are partial, not full CaseState replacements

No patch should contain a full `CaseState` replacement.

### 2.2 Patch merge style depends on owned layer

Examples:
- Intake uses merge/upsert style for observational layers
- Judge uses replace style for decision layer

### 2.3 History additions are append-only

Any patch that adds history should do so as append-only event additions.

---

## 3. IntakePatch (Draft)

### 3.1 Purpose

`IntakePatch` turns raw case material into structured observational state.

It may update:
- `issue`
- `facts`
- `anomalies`
- `history`

It must not update:
- `hypotheses`
- `plan`
- `execution`
- `decision`

---

### 3.2 Draft shape

```json
{
  "patch_id": "P1",
  "patch_type": "intake_patch",
  "actor": "intake",
  "generated_at": "2026-04-02T00:30:00Z",
  "base_case_id": "case-001",
  "base_status": "NEW",
  "base_loop_index": 0,
  "state_transition_request": {
    "from": "NEW",
    "to": "INTAKE_READY"
  },
  "payload": {
    "issue_updates": {
      "summary_overwrite": "...",
      "description_overwrite": "...",
      "comments_append": [],
      "labels_merge": []
    },
    "fact_upserts": [
      {
        "partition": "software",
        "slot": "kernel_version",
        "fact": {
          "fact_id": "F1",
          "key": "kernel_version",
          "value": "6.8.0-custom",
          "confidence": "high",
          "source_refs": [
            {
              "kind": "log",
              "ref_id": "boot-log",
              "locator": "line 3"
            }
          ],
          "observed_in_loop": 1
        }
      }
    ],
    "anomaly_updates": {
      "items_append": [
        {
          "anomaly_id": "A1",
          "category": "link_down",
          "message": "PCIe link down",
          "normalized_message": "pcie link down",
          "source_refs": [
            {
              "kind": "log",
              "ref_id": "boot-log",
              "locator": "line 101"
            }
          ],
          "stage": "probe",
          "severity": "high",
          "earliest_rank": 1,
          "likely_primary": true,
          "related_subsystems": ["pcie"]
        }
      ],
      "timeline_summary_replacement": {
        "earliest_anomaly_id": "A1",
        "ordered_anomaly_ids": ["A1"],
        "notes": null
      }
    },
    "missing_upserts": [
      {
        "key": "bios_settings_capture",
        "description": "Direct BIOS settings snapshot is not present in the intake material",
        "priority": 1
      }
    ],
    "history_additions": [
      {
        "event_id": "EV1",
        "loop_index": 1,
        "actor": "intake",
        "event_type": "intake_completed",
        "summary": "Initial issue material converted into structured facts and anomalies",
        "patch_ref": null,
        "timestamp": "2026-04-02T00:30:00Z"
      }
    ]
  }
}
```

---

### 3.3 Field intent

#### `issue_updates`
Explicit issue-layer update contract.

Current MVP shape:
- `summary_overwrite`
- `description_overwrite`
- `comments_append`
- `labels_merge`

This makes overwrite, append, and merge semantics explicit rather than implied.

#### `fact_upserts`
Keyed observational current-state updates.

Each fact upsert identifies:
- partition
- slot
- full fact object for that slot

This reflects the current MVP rule that facts are keyed current-state values, not append-only fact history.

#### `anomaly_updates`
Anomaly additions plus explicit timeline summary replacement.

Current MVP shape:
- `items_append`
- `timeline_summary_replacement`

This keeps anomaly items append-oriented while treating the timeline summary as a current-state sub-object.

#### `missing_upserts`
Structured current-state updates for missing observational inputs.

This allows Intake to explicitly record missing required material rather than forcing later agents to rediscover the same gaps.

#### `history_additions`
Append-only history entries.

---

## 4. JudgePatch (Draft)

### 4.1 Purpose

`JudgePatch` expresses closure and next-step control decisions.

It may update:
- `decision`
- `history`

It must not update:
- raw `facts`
- raw `anomalies`
- raw `execution`
- formal `hypotheses` table in MVP

---

### 4.2 Draft shape

```json
{
  "patch_id": "P2",
  "patch_type": "judge_patch",
  "actor": "judge",
  "generated_at": "2026-04-02T01:00:00Z",
  "base_case_id": "case-001",
  "base_status": "JUDGING",
  "base_loop_index": 1,
  "state_transition_request": {
    "from": "JUDGING",
    "to": "NEED_RERUN"
  },
  "payload": {
    "decision_replacement": {
      "current_verdict": "NEED_RERUN",
      "closure_level": "partial",
      "top_hypothesis_ids": ["H1"],
      "rationale": "Current evidence points most strongly to a BIOS configuration issue, but direct BIOS-state validation is still missing.",
      "unresolved_gaps": [
        "No direct BIOS settings captured from target device"
      ],
      "rerun_focus": [
        "Capture BIOS PCIe-related settings from device"
      ],
      "do_not_repeat_check_ids": ["C2"],
      "help_request": null,
      "finalized_explanation": null
    },
    "history_additions": [
      {
        "event_id": "EV2",
        "loop_index": 1,
        "actor": "judge",
        "event_type": "decision_recorded",
        "summary": "Case set to NEED_RERUN with BIOS-focused rerun direction",
        "patch_ref": null,
        "timestamp": "2026-04-02T01:00:00Z"
      }
    ]
  }
}
```

---

### 4.3 Field intent

#### `decision_replacement`
Whole replacement of the current decision snapshot.

This follows the MVP contract:
- decision is current adjudication state
- history preserves earlier decision events
- decision itself is not append-stacked
- `decision_replacement` is adjudication output, not hypothesis-table mutation
- `top_hypothesis_ids` must reference hypothesis ids that already exist in the current CaseState
- `do_not_repeat_check_ids` must reference relevant existing check ids from the current or immediately prior planning/execution context
- `rationale` must justify the verdict using existing structured state and must not introduce new major analytical conclusions absent from facts, hypotheses, or execution

#### `history_additions`
Append-only decision/audit events.

---

## 5. HypothesisPatch (Draft)

### 5.1 Purpose

`HypothesisPatch` produces the current explanatory state and the current analytical execution contract.

It may update:
- `hypotheses`
- `plan`
- `history`

It must not update:
- raw `facts`
- raw `anomalies`
- raw `execution`
- `decision`
- final `plan.items[*].status`

---

### 5.2 Draft shape

```json
{
  "patch_id": "P3",
  "patch_type": "hypothesis_patch",
  "actor": "hypothesis",
  "generated_at": "2026-04-02T01:30:00Z",
  "base_case_id": "case-001",
  "base_status": "INTAKE_READY",
  "base_loop_index": 1,
  "state_transition_request": {
    "from": "INTAKE_READY",
    "to": "HYPOTHESES_READY"
  },
  "payload": {
    "hypotheses_replacement": {
      "items": [
        {
          "hypothesis_id": "H1",
          "statement": "PCIe training fails due to BIOS ASPM configuration on the new board revision.",
          "status": "active",
          "confidence": "medium",
          "support_evidence": [
            {
              "kind": "fact",
              "ref_id": "F1",
              "summary": "Boot log indicates repeated PCIe link training failure before NVMe probe"
            }
          ],
          "contradiction_evidence": [],
          "missing_gaps": [
            {
              "key": "bios_aspm_vs_alt_cause_disambiguation",
              "description": "Missing discriminative evidence that separates BIOS ASPM misconfiguration from other board-level PCIe training causes",
              "priority": 1
            }
          ],
          "discriminating_check_ids": ["C1", "C2"]
        }
      ]
    },
    "plan_replacement": {
      "items": [
        {
          "check_id": "C1",
          "title": "Capture BIOS PCIe ASPM settings",
          "target_hypothesis_id": "H1",
          "lane": "device",
          "priority": 1,
          "goal": "Verify whether BIOS ASPM settings differ from known-good configuration",
          "tool_action": "collect_bios_settings",
          "inputs": {
            "subject": "target device BIOS PCIe configuration",
            "target_host": "dut-01",
            "expected_artifact": "bios-settings.txt"
          },
          "expected_if_true": "ASPM-related setting mismatch or forced state is observed",
          "expected_if_false": "BIOS ASPM settings match known-good expectations",
          "fallback": "Capture full firmware setup export if targeted BIOS query is unavailable",
          "dependencies": [],
          "info_gain": "high",
          "estimated_cost": "medium"
        },
        {
          "check_id": "C2",
          "title": "Boot with ASPM disabled in BIOS",
          "target_hypothesis_id": "H1",
          "lane": "device",
          "priority": 2,
          "goal": "Test whether disabling ASPM eliminates the PCIe training failure",
          "tool_action": "run_boot_test",
          "inputs": {
            "subject": "boot behavior with BIOS ASPM disabled",
            "target_host": "dut-01"
          },
          "expected_if_true": "Failure disappears or moves later in boot",
          "expected_if_false": "Failure signature is unchanged",
          "fallback": "Collect side-by-side boot logs with current and modified BIOS settings",
          "dependencies": ["C1"],
          "info_gain": "high",
          "estimated_cost": "high"
        }
      ]
    },
    "history_additions": [
      {
        "event_id": "EV3",
        "loop_index": 1,
        "actor": "hypothesis",
        "event_type": "hypotheses_refreshed",
        "summary": "Generated current hypothesis set and BIOS-focused validation plan",
        "patch_ref": "P3",
        "timestamp": "2026-04-02T01:30:00Z"
      }
    ]
  }
}
```

---

### 5.3 Field intent

#### `hypotheses_replacement`
Whole replacement of the current hypothesis table.

Current MVP shape:
- `hypotheses_replacement.items`

This follows the MVP contract:
- hypotheses are treated as a holistic analytical state
- partial in-place mutation is intentionally avoided in MVP
- the replacement should represent the current competing explanation set for the case
- hypothesis statements and evidence summaries must be grounded in existing facts, anomalies, and execution context
- HypothesisPatch must not introduce new observational facts that are absent from structured state
- `missing_gaps` is an explanatory gap structure relative to evaluating hypotheses, not a duplicate intake-level missing-material registry

#### `plan_replacement`
Whole replacement of the current analytical execution contract.

This follows the MVP contract:
- plan is generated together with the current hypothesis state
- partial plan mutation is intentionally avoided in MVP
- `plan.items[*].status` is not Hypothesis-owned lifecycle truth; it is a harness-reflected overlay
- plan items in HypothesisPatch should omit final lifecycle status fields
- new plan replacement should not rely on fine-grained inheritance of prior agent-owned status

#### `history_additions`
Append-only analytical/audit events.

---

## 6. ProbePatch (Draft)

### 6.1 Purpose

`ProbePatch` reports realized execution outcomes and execution-derived observational updates.

It may update:
- `execution`
- execution-derived `facts`
- `history`

It must not update:
- `hypotheses`
- `plan` as analytical contract
- `decision`
- final `plan.items[*].status`

---

### 6.2 Draft shape

```json
{
  "patch_id": "P4",
  "patch_type": "probe_patch",
  "actor": "probe",
  "generated_at": "2026-04-02T02:00:00Z",
  "base_case_id": "case-001",
  "base_status": "HYPOTHESES_READY",
  "base_loop_index": 1,
  "state_transition_request": null,
  "payload": {
    "execution_result_additions": [
      {
        "result_id": "R1",
        "check_id": "C1",
        "outcome": "positive",
        "summary": "BIOS capture shows ASPM forced to L1.2 on the failing board while known-good board uses Auto.",
        "interpreted_result": "This supports H1 by exposing a BIOS-level difference consistent with early PCIe training instability.",
        "artifact_refs": [
          {
            "kind": "file",
            "ref_id": "bios-settings-txt",
            "locator": "/artifacts/case-001/bios-settings.txt"
          }
        ],
        "new_fact_ids": ["F2"],
        "confidence": "high"
      }
    ],
    "blocker_additions": [
      {
        "blocker_id": "B1",
        "check_id": "C2",
        "kind": "manual_step_required",
        "summary": "BIOS setting change requires physical operator access not available in current run window.",
        "details": "The DUT is remote-only for this run; no out-of-band BIOS control path is available.",
        "retryable": true
      }
    ],
    "fact_upserts": [
      {
        "partition": "platform",
        "slot": "bios_version",
        "fact": {
          "fact_id": "F2",
          "key": "bios_version",
          "value": "1.0.7-custom",
          "confidence": "high",
          "source_refs": [
            {
              "kind": "file",
              "ref_id": "bios-settings-txt",
              "locator": "line 1"
            }
          ],
          "observed_in_loop": 1
        }
      }
    ],
    "tool_usage_delta": {
      "checks_touched": 2,
      "tool_calls": 1,
      "device_interactions": 1
    },
    "execution_state_hints": {
      "completed_check_ids": ["C1"],
      "blocked_check_ids": ["C2"]
    },
    "history_additions": [
      {
        "event_id": "EV4",
        "loop_index": 1,
        "actor": "probe",
        "event_type": "execution_reported",
        "summary": "Captured BIOS settings, produced one positive result, and recorded one retryable blocker",
        "patch_ref": "P4",
        "timestamp": "2026-04-02T02:00:00Z"
      }
    ]
  }
}
```

---

### 6.3 Field intent

#### `execution_result_additions`
Append-only execution results for realized checks.

This follows the MVP contract:
- Probe reports realized outcomes, not planning intent
- each result should carry its own stable `result_id`
- results must reference relevant existing `check_id` values
- `new_fact_ids` may reference fact objects introduced through the same patch's `fact_upserts`
- `interpreted_result` may describe the local significance of the observed outcome relative to the executed check or targeted hypothesis
- Probe must not use `interpreted_result` to perform whole-case adjudication, rerun recommendation, or hypothesis-table mutation by prose

#### `blocker_additions`
Append-only blocker records for checks that could not be completed as intended.

This follows the MVP contract:
- each blocker should carry its own stable `blocker_id`
- blockers describe execution constraints or execution-time failure modes
- blockers do not directly adjudicate the case or rewrite the plan

#### `fact_upserts`
Execution-derived keyed observational updates.

This follows the MVP contract:
- Probe may add or refine observational facts that were directly produced by execution
- these updates merge into the current facts view rather than forming append-only fact history

#### `tool_usage_delta`
Incremental tool-usage accounting contributed by this execution patch.

Current MVP intent:
- represent per-patch delta rather than whole execution-layer replacement
- use concrete per-patch counters such as `checks_touched` rather than ambiguous aggregate-style names

#### `execution_state_hints`
Optional execution-derived lifecycle hints for harness reflection.

This follows the MVP contract:
- Probe does not own final `plan.items[*].status`
- Probe may still provide a narrow execution-state summary to help harness reflect lifecycle state mechanically
- hints must be mechanically derivable from execution results and blockers in the same patch
- hints must not introduce lifecycle claims unsupported by execution records
- harness may ignore these hints entirely

#### `history_additions`
Append-only execution/audit events.

---

## 7. Current Review Questions for These Patch Types

### Q1. Should `issue_updates.summary_overwrite` and `issue_updates.description_overwrite` be allowed in MVP?
Current MVP answer:
- yes
- Intake may overwrite the structured current issue summary/description while still using append/merge semantics for comments and labels

### Q2. Should `anomaly_updates.timeline_summary_replacement` be treated as full replacement of the anomaly timeline summary?
Current MVP answer:
- yes
- the timeline summary behaves like a small current-state sub-object rather than an append-only list

### Q3. Should IntakePatch include structured missing-input updates?
Current MVP answer:
- yes
- Intake should be able to record missing observational material explicitly through `missing_upserts`

### Q4. Should `JudgePatch` ever contain optional advisory hypothesis-standing hints in MVP?
Current MVP answer:
- no
- Judge should express adjudication through `decision`, not through hypothesis rewrite hints
- `top_hypothesis_ids` is a reference/selection field, not a covert hypothesis mutation channel

### Q5. Should `HypothesisPatch` fully replace both `hypotheses` and `plan` in MVP?
Current MVP answer:
- yes
- `hypotheses` is a holistic explanatory state and should be whole-replaced
- `plan` is a holistic analytical execution contract and should also be whole-replaced
- `plan.items[*].status` remains harness-reflected lifecycle state rather than Hypothesis-owned analytical state

### Q6. Should `ProbePatch` include explicit execution-state hints even though Probe does not own final `plan.items[*].status`?
Current MVP answer:
- yes, optionally
- hints are allowed as a narrow mechanical aid for harness lifecycle reflection
- hints do not constitute final status ownership

### Q7. Should `ProbePatch` represent tool usage as delta or replacement?
Current MVP answer:
- delta
- ProbePatch should contribute incremental accounting, not overwrite aggregate usage state

---

## 8. Intended Next Step

After review of the full first draft set, the next step should be to tighten any remaining ambiguities and then decide whether to split out:
- formal JSON schema for patches
- harness merge/validation rules
- per-agent view schemas
