# CaseState MVP Examples

This document provides small positive and negative examples for the MVP CaseState model.

Purpose:
- make the schema and semantics concrete
- provide quick fixtures for implementation review
- help compare actual agent output against intended model behavior

These examples are intentionally small rather than realistic in full operational detail.

---

## 1. Positive Example: `NEED_RERUN`

This example shows a valid rerun case:
- current best hypothesis exists
- rerun focus is present
- finalized explanation is null
- owner is `hypothesis`

```json
{
  "meta": {
    "case_id": "case-001",
    "external_id": "JIRA-1001",
    "status": "NEED_RERUN",
    "loop_index": 1,
    "created_at": "2026-04-02T00:30:00Z",
    "updated_at": "2026-04-02T01:00:00Z",
    "owner_agent": "hypothesis",
    "schema_version": "0.1.0",
    "run_config": {
      "max_loops": 3,
      "max_total_checks": 10,
      "max_code_checks": 4,
      "max_device_checks": 6,
      "max_kb_queries": 3
    },
    "tags": ["boot", "pcie", "platform-abc"]
  },
  "issue": {
    "source": "jira",
    "issue_id": "JIRA-1001",
    "summary": "Boot failure on platform abc",
    "description": "System fails during boot after BIOS update",
    "comments": [],
    "labels": ["boot", "regression"],
    "priority": "P2",
    "reporter": "tester",
    "assignee": null,
    "created_at": "2026-04-01T10:00:00Z",
    "updated_at": "2026-04-02T00:50:00Z"
  },
  "facts": {
    "platform": {
      "platform_name": {
        "fact_id": "F1",
        "key": "platform_name",
        "value": "platform-abc",
        "confidence": "high",
        "source_refs": [
          { "kind": "issue", "ref_id": "JIRA-1001", "locator": null }
        ],
        "observed_in_loop": 1
      },
      "board_name": null,
      "soc": null,
      "boot_mode": null,
      "bios_version": null,
      "firmware_version": null
    },
    "software": {
      "kernel_version": {
        "fact_id": "F2",
        "key": "kernel_version",
        "value": "6.8.0-custom",
        "confidence": "high",
        "source_refs": [
          { "kind": "log", "ref_id": "boot-log", "locator": "line 3" }
        ],
        "observed_in_loop": 1
      },
      "kernel_branch": null,
      "config_flavor": null,
      "distro": {
        "fact_id": "F3",
        "key": "distro",
        "value": "Ubuntu 24.04",
        "confidence": "medium",
        "source_refs": [
          { "kind": "issue", "ref_id": "JIRA-1001", "locator": null }
        ],
        "observed_in_loop": 1
      },
      "distro_version": null,
      "firmware_package_state": null
    },
    "runtime": {
      "failure_stage": {
        "fact_id": "F4",
        "key": "failure_stage",
        "value": "probe",
        "confidence": "medium",
        "source_refs": [
          { "kind": "log", "ref_id": "boot-log", "locator": "lines 90-130" }
        ],
        "observed_in_loop": 1
      },
      "repro_rate": null,
      "first_failure_time": null,
      "affected_subsystems": {
        "fact_id": "F5",
        "key": "affected_subsystems",
        "value": ["pcie", "nvme"],
        "confidence": "medium",
        "source_refs": [
          { "kind": "log", "ref_id": "boot-log", "locator": "lines 101-128" }
        ],
        "observed_in_loop": 1
      },
      "observed_modules": null
    },
    "environment": {
      "test_case_name": null,
      "repro_steps_present": null,
      "known_good_baseline": null,
      "issue_regression_flag": {
        "fact_id": "F6",
        "key": "issue_regression_flag",
        "value": true,
        "confidence": "medium",
        "source_refs": [
          { "kind": "comment", "ref_id": "comment-1", "locator": null }
        ],
        "observed_in_loop": 1
      }
    },
    "missing": [
      {
        "key": "bios_version",
        "reason": "Not present in logs or issue body",
        "importance": "critical",
        "suggested_source": "device_probe"
      }
    ]
  },
  "anomalies": {
    "items": [
      {
        "anomaly_id": "A1",
        "category": "link_down",
        "message": "PCIe link down",
        "normalized_message": "pcie link down",
        "source_refs": [
          { "kind": "log", "ref_id": "boot-log", "locator": "line 101" }
        ],
        "stage": "probe",
        "severity": "high",
        "earliest_rank": 1,
        "likely_primary": true,
        "related_subsystems": ["pcie"]
      }
    ],
    "timeline_summary": {
      "earliest_anomaly_id": "A1",
      "ordered_anomaly_ids": ["A1"],
      "notes": null
    }
  },
  "hypotheses": {
    "required_classes": [
      "kernel_bug",
      "firmware_bug",
      "bios_config_issue",
      "ubuntu_config_issue",
      "hardware_issue"
    ],
    "items": [
      {
        "hypothesis_id": "H1",
        "class": "bios_config_issue",
        "statement": "PCIe-related BIOS settings changed after BIOS update and caused downstream boot probe failure.",
        "scope": {
          "subsystem": "pcie",
          "layer": "bios",
          "component": null
        },
        "confidence": 0.62,
        "status": "active",
        "support_evidence": [
          {
            "evidence_id": "E1",
            "summary": "Issue started after BIOS update",
            "source_refs": [
              { "kind": "issue", "ref_id": "JIRA-1001", "locator": null }
            ],
            "weight": 0.7
          }
        ],
        "contradiction_evidence": [],
        "missing_gaps": [
          {
            "gap_id": "G1",
            "description": "Current BIOS settings are not captured from device",
            "closure_requirement": "must_have"
          }
        ],
        "discriminating_check_ids": ["C1"],
        "introduced_in_loop": 1,
        "updated_in_loop": 1
      }
    ]
  },
  "plan": {
    "generated_in_loop": 1,
    "items": [
      {
        "check_id": "C1",
        "target_hypothesis_id": "H1",
        "lane": "device",
        "priority": 1,
        "goal": "Capture current BIOS PCIe-related settings",
        "tool_action": "device.inspect_boot_fw_state",
        "inputs": {
          "subject": "current BIOS PCIe-related settings",
          "expected_artifact": "BIOS config dump"
        },
        "expected_if_true": [
          "Observed settings differ from known-good expectations"
        ],
        "expected_if_false": [
          "No relevant BIOS mismatch is found"
        ],
        "fallback": [
          "Request manual BIOS dump from validation"
        ],
        "dependencies": [],
        "info_gain": "high",
        "estimated_cost": 2,
        "status": "planned"
      }
    ],
    "strategy_summary": "Focus next loop on validating BIOS-side explanation before investing more in code-side regression analysis."
  },
  "execution": {
    "results": [],
    "blockers": [],
    "tool_usage": {
      "jira_fetches": 1,
      "jira_downloads": 1,
      "kb_queries": 1,
      "code_checks": 1,
      "device_checks": 0,
      "total_checks": 1
    }
  },
  "decision": {
    "current_verdict": "NEED_RERUN",
    "closure_level": "partial",
    "top_hypothesis_ids": ["H1"],
    "rationale": "Current evidence points most strongly to a BIOS configuration issue, but direct platform-side BIOS state is still missing.",
    "unresolved_gaps": [
      "Missing direct BIOS settings from target device"
    ],
    "rerun_focus": [
      "Capture BIOS PCIe-related settings from device"
    ],
    "do_not_repeat_check_ids": [],
    "help_request": null,
    "finalized_explanation": null
  },
  "history": {
    "events": [
      {
        "event_id": "EV1",
        "loop_index": 1,
        "actor": "judge",
        "event_type": "decision_recorded",
        "summary": "Case requires rerun with BIOS-focused follow-up",
        "patch_ref": null,
        "timestamp": "2026-04-02T01:00:00Z"
      }
    ]
  }
}
```

---

## 2. Positive Example: `FINALIZED_WEAK`

This example shows a weakly finalized case:
- closure level is weak
- finalized explanation is present
- rerun focus is empty
- no running checks remain

```json
{
  "meta": {
    "case_id": "case-002",
    "external_id": "JIRA-1002",
    "status": "FINALIZED_WEAK",
    "loop_index": 1,
    "created_at": "2026-04-02T00:30:00Z",
    "updated_at": "2026-04-02T01:20:00Z",
    "owner_agent": null,
    "schema_version": "0.1.0",
    "run_config": {
      "max_loops": 3,
      "max_total_checks": 10,
      "max_code_checks": 4,
      "max_device_checks": 6,
      "max_kb_queries": 3
    },
    "tags": ["firmware", "wifi", "platform-xyz"]
  },
  "issue": {
    "source": "jira",
    "issue_id": "JIRA-1002",
    "summary": "Wi-Fi probe failure on platform xyz",
    "description": "Wi-Fi device fails to initialize on first boot",
    "comments": [],
    "labels": ["wifi"],
    "priority": "P2",
    "reporter": "tester",
    "assignee": null,
    "created_at": "2026-04-01T12:00:00Z",
    "updated_at": "2026-04-02T01:10:00Z"
  },
  "facts": {
    "platform": {
      "platform_name": {
        "fact_id": "F10",
        "key": "platform_name",
        "value": "platform-xyz",
        "confidence": "high",
        "source_refs": [
          { "kind": "issue", "ref_id": "JIRA-1002", "locator": null }
        ],
        "observed_in_loop": 1
      },
      "board_name": null,
      "soc": null,
      "boot_mode": null,
      "bios_version": null,
      "firmware_version": null
    },
    "software": {
      "kernel_version": {
        "fact_id": "F11",
        "key": "kernel_version",
        "value": "6.8.0-custom",
        "confidence": "high",
        "source_refs": [
          { "kind": "log", "ref_id": "wifi-log", "locator": "line 2" }
        ],
        "observed_in_loop": 1
      },
      "kernel_branch": null,
      "config_flavor": null,
      "distro": null,
      "distro_version": null,
      "firmware_package_state": {
        "fact_id": "F12",
        "key": "firmware_package_state",
        "value": "missing",
        "confidence": "high",
        "source_refs": [
          { "kind": "tool_output", "ref_id": "check-firmware-files", "locator": null }
        ],
        "observed_in_loop": 1
      }
    },
    "runtime": {
      "failure_stage": {
        "fact_id": "F13",
        "key": "failure_stage",
        "value": "probe",
        "confidence": "medium",
        "source_refs": [
          { "kind": "log", "ref_id": "wifi-log", "locator": "lines 40-80" }
        ],
        "observed_in_loop": 1
      },
      "repro_rate": null,
      "first_failure_time": null,
      "affected_subsystems": {
        "fact_id": "F14",
        "key": "affected_subsystems",
        "value": ["wifi"],
        "confidence": "medium",
        "source_refs": [
          { "kind": "log", "ref_id": "wifi-log", "locator": "lines 40-80" }
        ],
        "observed_in_loop": 1
      },
      "observed_modules": null
    },
    "environment": {
      "test_case_name": null,
      "repro_steps_present": null,
      "known_good_baseline": null,
      "issue_regression_flag": null
    },
    "missing": []
  },
  "anomalies": {
    "items": [
      {
        "anomaly_id": "A10",
        "category": "missing_fw",
        "message": "firmware file not found",
        "normalized_message": "firmware file not found",
        "source_refs": [
          { "kind": "log", "ref_id": "wifi-log", "locator": "line 52" }
        ],
        "stage": "probe",
        "severity": "high",
        "earliest_rank": 1,
        "likely_primary": true,
        "related_subsystems": ["wifi"]
      }
    ],
    "timeline_summary": {
      "earliest_anomaly_id": "A10",
      "ordered_anomaly_ids": ["A10"],
      "notes": null
    }
  },
  "hypotheses": {
    "required_classes": [
      "kernel_bug",
      "firmware_bug",
      "bios_config_issue",
      "ubuntu_config_issue",
      "hardware_issue"
    ],
    "items": [
      {
        "hypothesis_id": "H10",
        "class": "ubuntu_config_issue",
        "statement": "Required Wi-Fi firmware package is missing from the root filesystem.",
        "scope": {
          "subsystem": "wifi",
          "layer": "distro_userspace",
          "component": "linux-firmware"
        },
        "confidence": 0.78,
        "status": "active",
        "support_evidence": [
          {
            "evidence_id": "E10",
            "summary": "Firmware file not found in log and package inspection confirms absence",
            "source_refs": [
              { "kind": "log", "ref_id": "wifi-log", "locator": "line 52" },
              { "kind": "tool_output", "ref_id": "check-firmware-files", "locator": null }
            ],
            "weight": 0.9
          }
        ],
        "contradiction_evidence": [],
        "missing_gaps": [],
        "discriminating_check_ids": ["C10"],
        "introduced_in_loop": 1,
        "updated_in_loop": 1
      }
    ]
  },
  "plan": {
    "generated_in_loop": 1,
    "items": [
      {
        "check_id": "C10",
        "target_hypothesis_id": "H10",
        "lane": "device",
        "priority": 1,
        "goal": "Verify whether required Wi-Fi firmware files are present on target rootfs",
        "tool_action": "device.collect_runtime_facts",
        "inputs": {
          "subject": "Wi-Fi firmware package presence",
          "target_host": "dut-1",
          "expected_artifact": "firmware file listing"
        },
        "expected_if_true": [
          "Firmware files are absent and hypothesis is strengthened"
        ],
        "expected_if_false": [
          "Firmware files are present and missing-package explanation is weakened"
        ],
        "fallback": [],
        "dependencies": [],
        "info_gain": "high",
        "estimated_cost": 1,
        "status": "done"
      }
    ],
    "strategy_summary": "Resolve whether failure is caused by missing firmware package before pursuing driver-level investigation."
  },
  "execution": {
    "results": [
      {
        "check_id": "C10",
        "lane": "device",
        "outcome": "positive",
        "raw_output_ref": "artifact-c10-output",
        "summary": "Required Wi-Fi firmware files are absent on target rootfs",
        "interpreted_result": "This strongly supports the Ubuntu configuration issue hypothesis.",
        "new_fact_ids": ["F12"],
        "hypothesis_impacts": [
          {
            "hypothesis_id": "H10",
            "delta": 0.4,
            "rationale": "Observed package absence directly matches expected failure mode."
          }
        ],
        "confidence": "high",
        "completed_in_loop": 1
      }
    ],
    "blockers": [],
    "tool_usage": {
      "jira_fetches": 1,
      "jira_downloads": 1,
      "kb_queries": 0,
      "code_checks": 0,
      "device_checks": 1,
      "total_checks": 1
    }
  },
  "decision": {
    "current_verdict": "FINALIZED_WEAK",
    "closure_level": "weak",
    "top_hypothesis_ids": ["H10"],
    "rationale": "Missing firmware package is the best current explanation and is strongly supported by both logs and direct file inspection, though no reinstall/confirmatory rerun was executed in this case.",
    "unresolved_gaps": [],
    "rerun_focus": [],
    "do_not_repeat_check_ids": ["C10"],
    "help_request": null,
    "finalized_explanation": "Most likely Wi-Fi initialization failure is caused by missing firmware files in the target Ubuntu root filesystem."
  },
  "history": {
    "events": [
      {
        "event_id": "EV10",
        "loop_index": 1,
        "actor": "judge",
        "event_type": "decision_recorded",
        "summary": "Case weakly finalized with missing-firmware explanation",
        "patch_ref": null,
        "timestamp": "2026-04-02T01:20:00Z"
      }
    ]
  }
}
```

---

## 3. Negative Example: invalid finalized state

This example is structurally plausible but semantically invalid.

Problems:
- finalized verdict but owner is not null
- finalized verdict but closure level is partial
- finalized verdict but rerun focus is non-empty
- finalized verdict but finalized explanation is null
- leading hypothesis points to an eliminated hypothesis
- running check still exists

```json
{
  "meta": {
    "case_id": "case-bad-001",
    "external_id": "JIRA-1999",
    "status": "FINALIZED_STRONG",
    "loop_index": 1,
    "created_at": "2026-04-02T00:30:00Z",
    "updated_at": "2026-04-02T01:30:00Z",
    "owner_agent": "judge",
    "schema_version": "0.1.0",
    "run_config": {
      "max_loops": 3,
      "max_total_checks": 10,
      "max_code_checks": 4,
      "max_device_checks": 6,
      "max_kb_queries": 3
    },
    "tags": ["bad-example"]
  },
  "issue": {
    "source": "jira",
    "issue_id": "JIRA-1999",
    "summary": "Example bad case",
    "description": "Bad semantic example",
    "comments": [],
    "labels": [],
    "priority": null,
    "reporter": null,
    "assignee": null,
    "created_at": null,
    "updated_at": null
  },
  "facts": {
    "platform": {
      "platform_name": null,
      "board_name": null,
      "soc": null,
      "boot_mode": null,
      "bios_version": null,
      "firmware_version": null
    },
    "software": {
      "kernel_version": null,
      "kernel_branch": null,
      "config_flavor": null,
      "distro": null,
      "distro_version": null,
      "firmware_package_state": null
    },
    "runtime": {
      "failure_stage": null,
      "repro_rate": null,
      "first_failure_time": null,
      "affected_subsystems": null,
      "observed_modules": null
    },
    "environment": {
      "test_case_name": null,
      "repro_steps_present": null,
      "known_good_baseline": null,
      "issue_regression_flag": null
    },
    "missing": []
  },
  "anomalies": {
    "items": [],
    "timeline_summary": {
      "earliest_anomaly_id": null,
      "ordered_anomaly_ids": [],
      "notes": null
    }
  },
  "hypotheses": {
    "required_classes": ["kernel_bug"],
    "items": [
      {
        "hypothesis_id": "Hbad",
        "class": "kernel_bug",
        "statement": "Bad example hypothesis",
        "scope": {
          "subsystem": null,
          "layer": null,
          "component": null
        },
        "confidence": 0.2,
        "status": "eliminated",
        "support_evidence": [],
        "contradiction_evidence": [],
        "missing_gaps": [],
        "discriminating_check_ids": ["Cbad"],
        "introduced_in_loop": 1,
        "updated_in_loop": 1
      }
    ]
  },
  "plan": {
    "generated_in_loop": 1,
    "items": [
      {
        "check_id": "Cbad",
        "target_hypothesis_id": "Hbad",
        "lane": "code",
        "priority": 1,
        "goal": "Bad example check",
        "tool_action": "code.inspect_driver_path",
        "inputs": {
          "subject": "example bad check"
        },
        "expected_if_true": [],
        "expected_if_false": [],
        "fallback": [],
        "dependencies": [],
        "info_gain": "low",
        "estimated_cost": 1,
        "status": "running"
      }
    ],
    "strategy_summary": null
  },
  "execution": {
    "results": [],
    "blockers": [],
    "tool_usage": {
      "jira_fetches": 0,
      "jira_downloads": 0,
      "kb_queries": 0,
      "code_checks": 0,
      "device_checks": 0,
      "total_checks": 0
    }
  },
  "decision": {
    "current_verdict": "FINALIZED_STRONG",
    "closure_level": "partial",
    "top_hypothesis_ids": ["Hbad"],
    "rationale": "This is intentionally inconsistent.",
    "unresolved_gaps": [],
    "rerun_focus": ["Do more analysis"],
    "do_not_repeat_check_ids": [],
    "help_request": null,
    "finalized_explanation": null
  },
  "history": {
    "events": []
  }
}
```

Expected semantic validator failures include:
- terminal state must imply `owner_agent = null`
- `FINALIZED_STRONG` must imply `closure_level = strong`
- finalized state must imply empty `rerun_focus`
- finalized state must imply non-null `finalized_explanation`
- finalized state must not coexist with running checks
- leading hypothesis must not be eliminated

---

## 4. Negative Example: invalid `NEED_HELP`

This example is structurally plausible but semantically invalid.

Problems:
- `NEED_HELP` but `help_request` is null
- `finalized_explanation` is non-null even though handoff is incomplete
- owner is not null in terminal state

```json
{
  "meta": {
    "case_id": "case-bad-002",
    "external_id": "JIRA-2000",
    "status": "NEED_HELP",
    "loop_index": 1,
    "created_at": "2026-04-02T00:30:00Z",
    "updated_at": "2026-04-02T01:40:00Z",
    "owner_agent": "judge",
    "schema_version": "0.1.0",
    "run_config": {
      "max_loops": 3,
      "max_total_checks": 10,
      "max_code_checks": 4,
      "max_device_checks": 6,
      "max_kb_queries": 3
    },
    "tags": ["bad-example"]
  },
  "issue": {
    "source": "jira",
    "issue_id": "JIRA-2000",
    "summary": "Example help failure",
    "description": "Bad NEED_HELP example",
    "comments": [],
    "labels": [],
    "priority": null,
    "reporter": null,
    "assignee": null,
    "created_at": null,
    "updated_at": null
  },
  "facts": {
    "platform": {
      "platform_name": null,
      "board_name": null,
      "soc": null,
      "boot_mode": null,
      "bios_version": null,
      "firmware_version": null
    },
    "software": {
      "kernel_version": null,
      "kernel_branch": null,
      "config_flavor": null,
      "distro": null,
      "distro_version": null,
      "firmware_package_state": null
    },
    "runtime": {
      "failure_stage": null,
      "repro_rate": null,
      "first_failure_time": null,
      "affected_subsystems": null,
      "observed_modules": null
    },
    "environment": {
      "test_case_name": null,
      "repro_steps_present": null,
      "known_good_baseline": null,
      "issue_regression_flag": null
    },
    "missing": []
  },
  "anomalies": {
    "items": [],
    "timeline_summary": {
      "earliest_anomaly_id": null,
      "ordered_anomaly_ids": [],
      "notes": null
    }
  },
  "hypotheses": {
    "required_classes": ["hardware_issue"],
    "items": [
      {
        "hypothesis_id": "Hhelp",
        "class": "hardware_issue",
        "statement": "Board-level instability may be causing intermittent link failure.",
        "scope": {
          "subsystem": "pcie",
          "layer": "hardware",
          "component": null
        },
        "confidence": 0.4,
        "status": "active",
        "support_evidence": [],
        "contradiction_evidence": [],
        "missing_gaps": [
          {
            "gap_id": "Ghelp",
            "description": "No board swap comparison available",
            "closure_requirement": "must_have"
          }
        ],
        "discriminating_check_ids": [],
        "introduced_in_loop": 1,
        "updated_in_loop": 1
      }
    ]
  },
  "plan": {
    "generated_in_loop": 1,
    "items": [],
    "strategy_summary": null
  },
  "execution": {
    "results": [],
    "blockers": [],
    "tool_usage": {
      "jira_fetches": 0,
      "jira_downloads": 0,
      "kb_queries": 0,
      "code_checks": 0,
      "device_checks": 0,
      "total_checks": 0
    }
  },
  "decision": {
    "current_verdict": "NEED_HELP",
    "closure_level": "partial",
    "top_hypothesis_ids": ["Hhelp"],
    "rationale": "Human validation is required.",
    "unresolved_gaps": ["Need board swap comparison"],
    "rerun_focus": [],
    "do_not_repeat_check_ids": [],
    "help_request": null,
    "finalized_explanation": "Possible board-level hardware instability"
  },
  "history": {
    "events": []
  }
}
```

Expected semantic validator failures include:
- terminal state must imply `owner_agent = null`
- `NEED_HELP` must imply non-null `help_request`
- MVP policy currently prefers `NEED_HELP -> finalized_explanation = null`

---

## 5. How to Use These Examples

Recommended use:
- validate positive examples against schema and semantic validator
- validate negative examples against schema first, then ensure semantic validator rejects them for the intended reasons
- use them as regression fixtures when evolving the harness

Suggested future additions:
- a positive `FINALIZED_STRONG` example
- a positive `NEED_HELP` example with a complete handoff packet
- an example with multiple competing hypotheses and mixed positive/negative checks
