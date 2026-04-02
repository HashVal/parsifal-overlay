# Debug Agent Harness JSON Schema Draft (MVP)

This document translates the data model sketch into a reviewable JSON Schema draft.

Goal of this phase:
- define the MVP `CaseState` schema first
- keep it strict enough to enforce discipline
- avoid over-modeling v1 with every optional advanced structure
- make field semantics and review surface clear

Schema target: JSON Schema 2020-12

---

## Design Scope

This MVP schema includes:
- `meta`
- `issue`
- `facts`
- `anomalies`
- `hypotheses`
- `plan`
- `execution`
- `decision`
- `history`

This MVP schema intentionally does **not yet** fully model:
- full `ArtifactIndex`
- full `KnowledgeContext`
- full `EvidenceGraph`
- per-agent `View` schemas
- patch schemas

Those should be added after the core `CaseState` stabilizes.

---

## Full Schema Draft

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://example.local/schemas/debug-agent/case-state-mvp.schema.json",
  "title": "Debug Agent CaseState MVP",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "meta",
    "issue",
    "facts",
    "anomalies",
    "hypotheses",
    "plan",
    "execution",
    "decision",
    "history"
  ],
  "properties": {
    "meta": { "$ref": "#/$defs/Meta" },
    "issue": { "$ref": "#/$defs/IssueBundle" },
    "facts": { "$ref": "#/$defs/FactLedger" },
    "anomalies": { "$ref": "#/$defs/AnomalySet" },
    "hypotheses": { "$ref": "#/$defs/HypothesisTable" },
    "plan": { "$ref": "#/$defs/CheckPlan" },
    "execution": { "$ref": "#/$defs/ExecutionState" },
    "decision": { "$ref": "#/$defs/DecisionState" },
    "history": { "$ref": "#/$defs/HistoryLog" }
  },
  "$defs": {
    "Status": {
      "type": "string",
      "enum": [
        "NEW",
        "INTAKE_READY",
        "HYPOTHESES_READY",
        "PROBING",
        "JUDGING",
        "NEED_RERUN",
        "FINALIZED_STRONG",
        "FINALIZED_WEAK",
        "NEED_HELP"
      ]
    },
    "AgentName": {
      "type": ["string", "null"],
      "enum": ["intake", "hypothesis", "probe", "judge", null]
    },
    "ConfidenceLabel": {
      "type": "string",
      "enum": ["high", "medium", "low"]
    },
    "SourceKind": {
      "type": "string",
      "enum": ["issue", "comment", "log", "snippet", "tool_output", "manual"]
    },
    "FailureStage": {
      "type": ["string", "null"],
      "enum": ["boot", "probe", "runtime", "suspend_resume", "shutdown", "stress", null]
    },
    "HypothesisClass": {
      "type": "string",
      "enum": [
        "kernel_bug",
        "firmware_bug",
        "bios_config_issue",
        "ubuntu_config_issue",
        "hardware_issue",
        "other"
      ]
    },
    "HypothesisStatus": {
      "type": "string",
      "enum": ["active", "weakened", "eliminated", "confirmed"]
    },
    "CheckLane": {
      "type": "string",
      "enum": ["code", "device"]
    },
    "CheckStatus": {
      "type": "string",
      "enum": ["planned", "running", "done", "skipped", "blocked"]
    },
    "CheckOutcome": {
      "type": "string",
      "enum": ["positive", "negative", "inconclusive", "blocked"]
    },
    "BlockerType": {
      "type": "string",
      "enum": [
        "permission_denied",
        "target_unreachable",
        "missing_artifact",
        "unsupported_tool",
        "nondeterministic_result",
        "timeout",
        "unknown"
      ]
    },
    "DecisionVerdict": {
      "type": ["string", "null"],
      "enum": ["FINALIZED_STRONG", "FINALIZED_WEAK", "NEED_RERUN", "NEED_HELP", null]
    },
    "ClosureLevel": {
      "type": ["string", "null"],
      "enum": ["none", "partial", "weak", "strong", null]
    },
    "HelpOwner": {
      "type": ["string", "null"],
      "enum": [
        "bios_engineer",
        "fw_engineer",
        "kernel_maintainer",
        "validation",
        "hardware_team",
        "distro_owner",
        "human_user",
        null
      ]
    },
    "InfoGain": {
      "type": "string",
      "enum": ["high", "medium", "low"]
    },
    "MissingImportance": {
      "type": "string",
      "enum": ["critical", "useful", "optional"]
    },
    "SuggestedSource": {
      "type": "string",
      "enum": ["jira_comment", "device_probe", "code_probe", "human"]
    },
    "AnomalyCategory": {
      "type": "string",
      "enum": [
        "timeout",
        "crash",
        "warning",
        "probe_fail",
        "link_down",
        "oops",
        "lockup",
        "missing_fw",
        "config_mismatch",
        "unknown"
      ]
    },
    "Severity": {
      "type": "string",
      "enum": ["critical", "high", "medium", "low"]
    },
    "RunConfig": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "max_loops",
        "max_total_checks",
        "max_code_checks",
        "max_device_checks",
        "max_kb_queries"
      ],
      "properties": {
        "max_loops": { "type": "integer", "minimum": 1 },
        "max_total_checks": { "type": "integer", "minimum": 0 },
        "max_code_checks": { "type": "integer", "minimum": 0 },
        "max_device_checks": { "type": "integer", "minimum": 0 },
        "max_kb_queries": { "type": "integer", "minimum": 0 }
      }
    },
    "Meta": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "case_id",
        "external_id",
        "status",
        "loop_index",
        "created_at",
        "updated_at",
        "owner_agent",
        "schema_version",
        "run_config",
        "tags"
      ],
      "properties": {
        "case_id": { "type": "string", "minLength": 1 },
        "external_id": { "type": ["string", "null"] },
        "status": { "$ref": "#/$defs/Status" },
        "loop_index": { "type": "integer", "minimum": 0 },
        "created_at": { "type": "string", "format": "date-time" },
        "updated_at": { "type": "string", "format": "date-time" },
        "owner_agent": { "$ref": "#/$defs/AgentName" },
        "schema_version": { "type": "string", "minLength": 1 },
        "run_config": { "$ref": "#/$defs/RunConfig" },
        "tags": {
          "type": "array",
          "items": { "type": "string" },
          "uniqueItems": true
        }
      }
    },
    "CommentRef": {
      "type": "object",
      "additionalProperties": false,
      "required": ["comment_id", "author", "created_at", "snippet", "artifact_ref"],
      "properties": {
        "comment_id": { "type": "string", "minLength": 1 },
        "author": { "type": ["string", "null"] },
        "created_at": { "type": ["string", "null"], "format": "date-time" },
        "snippet": { "type": "string" },
        "artifact_ref": { "type": ["string", "null"] }
      }
    },
    "IssueBundle": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "source",
        "issue_id",
        "summary",
        "description",
        "comments",
        "labels",
        "priority",
        "reporter",
        "assignee",
        "created_at",
        "updated_at"
      ],
      "properties": {
        "source": {
          "type": "string",
          "enum": ["jira", "manual", "imported"]
        },
        "issue_id": { "type": "string", "minLength": 1 },
        "summary": { "type": "string" },
        "description": { "type": "string" },
        "comments": {
          "type": "array",
          "items": { "$ref": "#/$defs/CommentRef" }
        },
        "labels": {
          "type": "array",
          "items": { "type": "string" },
          "uniqueItems": true
        },
        "priority": { "type": ["string", "null"] },
        "reporter": { "type": ["string", "null"] },
        "assignee": { "type": ["string", "null"] },
        "created_at": { "type": ["string", "null"], "format": "date-time" },
        "updated_at": { "type": ["string", "null"], "format": "date-time" }
      }
    },
    "SourceRef": {
      "type": "object",
      "additionalProperties": false,
      "required": ["kind", "ref_id", "locator"],
      "properties": {
        "kind": { "$ref": "#/$defs/SourceKind" },
        "ref_id": { "type": "string", "minLength": 1 },
        "locator": { "type": ["string", "null"] }
      }
    },
    "Fact": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "fact_id",
        "key",
        "value",
        "confidence",
        "source_refs",
        "observed_in_loop"
      ],
      "properties": {
        "fact_id": { "type": "string", "minLength": 1 },
        "key": { "type": "string", "minLength": 1 },
        "value": {},
        "confidence": { "$ref": "#/$defs/ConfidenceLabel" },
        "source_refs": {
          "type": "array",
          "items": { "$ref": "#/$defs/SourceRef" },
          "minItems": 1
        },
        "observed_in_loop": { "type": "integer", "minimum": 0 }
      }
    },
    "MissingFact": {
      "type": "object",
      "additionalProperties": false,
      "required": ["key", "reason", "importance", "suggested_source"],
      "properties": {
        "key": { "type": "string", "minLength": 1 },
        "reason": { "type": "string", "minLength": 1 },
        "importance": { "$ref": "#/$defs/MissingImportance" },
        "suggested_source": { "$ref": "#/$defs/SuggestedSource" }
      }
    },
    "PlatformFacts": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "platform_name",
        "board_name",
        "soc",
        "boot_mode",
        "bios_version",
        "firmware_version"
      ],
      "properties": {
        "platform_name": { "anyOf": [{ "$ref": "#/$defs/Fact" }, { "type": "null" }] },
        "board_name": { "anyOf": [{ "$ref": "#/$defs/Fact" }, { "type": "null" }] },
        "soc": { "anyOf": [{ "$ref": "#/$defs/Fact" }, { "type": "null" }] },
        "boot_mode": { "anyOf": [{ "$ref": "#/$defs/Fact" }, { "type": "null" }] },
        "bios_version": { "anyOf": [{ "$ref": "#/$defs/Fact" }, { "type": "null" }] },
        "firmware_version": { "anyOf": [{ "$ref": "#/$defs/Fact" }, { "type": "null" }] }
      }
    },
    "SoftwareFacts": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "kernel_version",
        "kernel_branch",
        "config_flavor",
        "distro",
        "distro_version",
        "firmware_package_state"
      ],
      "properties": {
        "kernel_version": { "anyOf": [{ "$ref": "#/$defs/Fact" }, { "type": "null" }] },
        "kernel_branch": { "anyOf": [{ "$ref": "#/$defs/Fact" }, { "type": "null" }] },
        "config_flavor": { "anyOf": [{ "$ref": "#/$defs/Fact" }, { "type": "null" }] },
        "distro": { "anyOf": [{ "$ref": "#/$defs/Fact" }, { "type": "null" }] },
        "distro_version": { "anyOf": [{ "$ref": "#/$defs/Fact" }, { "type": "null" }] },
        "firmware_package_state": { "anyOf": [{ "$ref": "#/$defs/Fact" }, { "type": "null" }] }
      }
    },
    "RuntimeFacts": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "failure_stage",
        "repro_rate",
        "first_failure_time",
        "affected_subsystems",
        "observed_modules"
      ],
      "properties": {
        "failure_stage": { "anyOf": [{ "$ref": "#/$defs/Fact" }, { "type": "null" }] },
        "repro_rate": { "anyOf": [{ "$ref": "#/$defs/Fact" }, { "type": "null" }] },
        "first_failure_time": { "anyOf": [{ "$ref": "#/$defs/Fact" }, { "type": "null" }] },
        "affected_subsystems": { "anyOf": [{ "$ref": "#/$defs/Fact" }, { "type": "null" }] },
        "observed_modules": { "anyOf": [{ "$ref": "#/$defs/Fact" }, { "type": "null" }] }
      }
    },
    "EnvironmentFacts": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "test_case_name",
        "repro_steps_present",
        "known_good_baseline",
        "issue_regression_flag"
      ],
      "properties": {
        "test_case_name": { "anyOf": [{ "$ref": "#/$defs/Fact" }, { "type": "null" }] },
        "repro_steps_present": { "anyOf": [{ "$ref": "#/$defs/Fact" }, { "type": "null" }] },
        "known_good_baseline": { "anyOf": [{ "$ref": "#/$defs/Fact" }, { "type": "null" }] },
        "issue_regression_flag": { "anyOf": [{ "$ref": "#/$defs/Fact" }, { "type": "null" }] }
      }
    },
    "FactLedger": {
      "type": "object",
      "additionalProperties": false,
      "required": ["platform", "software", "runtime", "environment", "missing"],
      "properties": {
        "platform": { "$ref": "#/$defs/PlatformFacts" },
        "software": { "$ref": "#/$defs/SoftwareFacts" },
        "runtime": { "$ref": "#/$defs/RuntimeFacts" },
        "environment": { "$ref": "#/$defs/EnvironmentFacts" },
        "missing": {
          "type": "array",
          "items": { "$ref": "#/$defs/MissingFact" }
        }
      }
    },
    "Anomaly": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "anomaly_id",
        "category",
        "message",
        "normalized_message",
        "source_refs",
        "stage",
        "severity",
        "earliest_rank",
        "likely_primary",
        "related_subsystems"
      ],
      "properties": {
        "anomaly_id": { "type": "string", "minLength": 1 },
        "category": { "$ref": "#/$defs/AnomalyCategory" },
        "message": { "type": "string", "minLength": 1 },
        "normalized_message": { "type": ["string", "null"] },
        "source_refs": {
          "type": "array",
          "items": { "$ref": "#/$defs/SourceRef" },
          "minItems": 1
        },
        "stage": { "$ref": "#/$defs/FailureStage" },
        "severity": { "$ref": "#/$defs/Severity" },
        "earliest_rank": { "type": ["integer", "null"], "minimum": 1 },
        "likely_primary": { "type": "boolean" },
        "related_subsystems": {
          "type": "array",
          "items": { "type": "string" },
          "uniqueItems": true
        }
      }
    },
    "TimelineSummary": {
      "type": "object",
      "additionalProperties": false,
      "required": ["earliest_anomaly_id", "ordered_anomaly_ids", "notes"],
      "properties": {
        "earliest_anomaly_id": { "type": ["string", "null"] },
        "ordered_anomaly_ids": {
          "type": "array",
          "items": { "type": "string" }
        },
        "notes": { "type": ["string", "null"] }
      }
    },
    "AnomalySet": {
      "type": "object",
      "additionalProperties": false,
      "required": ["items", "timeline_summary"],
      "properties": {
        "items": {
          "type": "array",
          "items": { "$ref": "#/$defs/Anomaly" }
        },
        "timeline_summary": { "$ref": "#/$defs/TimelineSummary" }
      }
    },
    "EvidenceItem": {
      "type": "object",
      "additionalProperties": false,
      "required": ["evidence_id", "summary", "source_refs", "weight"],
      "properties": {
        "evidence_id": { "type": "string", "minLength": 1 },
        "summary": { "type": "string", "minLength": 1 },
        "source_refs": {
          "type": "array",
          "items": { "$ref": "#/$defs/SourceRef" },
          "minItems": 1
        },
        "weight": { "type": "number", "minimum": 0, "maximum": 1 }
      }
    },
    "GapItem": {
      "type": "object",
      "additionalProperties": false,
      "required": ["gap_id", "description", "closure_requirement"],
      "properties": {
        "gap_id": { "type": "string", "minLength": 1 },
        "description": { "type": "string", "minLength": 1 },
        "closure_requirement": {
          "type": "string",
          "enum": ["must_have", "strong_should_have", "optional"]
        }
      }
    },
    "HypothesisScope": {
      "type": "object",
      "additionalProperties": false,
      "required": ["subsystem", "layer", "component"],
      "properties": {
        "subsystem": { "type": ["string", "null"] },
        "layer": {
          "type": ["string", "null"],
          "enum": [
            "hardware",
            "bios",
            "firmware",
            "kernel_core",
            "kernel_driver",
            "distro_userspace",
            null
          ]
        },
        "component": { "type": ["string", "null"] }
      }
    },
    "Hypothesis": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "hypothesis_id",
        "class",
        "statement",
        "scope",
        "confidence",
        "status",
        "support_evidence",
        "contradiction_evidence",
        "missing_gaps",
        "discriminating_check_ids",
        "introduced_in_loop",
        "updated_in_loop"
      ],
      "properties": {
        "hypothesis_id": { "type": "string", "minLength": 1 },
        "class": { "$ref": "#/$defs/HypothesisClass" },
        "statement": { "type": "string", "minLength": 1 },
        "scope": { "$ref": "#/$defs/HypothesisScope" },
        "confidence": { "type": "number", "minimum": 0, "maximum": 1 },
        "status": { "$ref": "#/$defs/HypothesisStatus" },
        "support_evidence": {
          "type": "array",
          "items": { "$ref": "#/$defs/EvidenceItem" }
        },
        "contradiction_evidence": {
          "type": "array",
          "items": { "$ref": "#/$defs/EvidenceItem" }
        },
        "missing_gaps": {
          "type": "array",
          "items": { "$ref": "#/$defs/GapItem" }
        },
        "discriminating_check_ids": {
          "type": "array",
          "items": { "type": "string" },
          "uniqueItems": true
        },
        "introduced_in_loop": { "type": "integer", "minimum": 0 },
        "updated_in_loop": { "type": "integer", "minimum": 0 }
      }
    },
    "HypothesisTable": {
      "type": "object",
      "additionalProperties": false,
      "required": ["required_classes", "items"],
      "properties": {
        "required_classes": {
          "type": "array",
          "items": { "$ref": "#/$defs/HypothesisClass" },
          "uniqueItems": true,
          "minItems": 1
        },
        "items": {
          "type": "array",
          "items": { "$ref": "#/$defs/Hypothesis" }
        }
      }
    },
    "CheckItem": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "check_id",
        "target_hypothesis_id",
        "lane",
        "priority",
        "goal",
        "tool_action",
        "inputs",
        "expected_if_true",
        "expected_if_false",
        "fallback",
        "dependencies",
        "info_gain",
        "estimated_cost",
        "status"
      ],
      "properties": {
        "check_id": { "type": "string", "minLength": 1 },
        "target_hypothesis_id": { "type": "string", "minLength": 1 },
        "lane": { "$ref": "#/$defs/CheckLane" },
        "priority": { "type": "integer", "minimum": 1 },
        "goal": { "type": "string", "minLength": 1 },
        "tool_action": { "type": "string", "minLength": 1 },
        "inputs": {
          "type": "object",
          "required": ["subject"],
          "properties": {
            "subject": { "type": "string", "minLength": 1 },
            "command_hint": { "type": ["string", "null"] },
            "target_path": { "type": ["string", "null"] },
            "target_host": { "type": ["string", "null"] },
            "expected_artifact": { "type": ["string", "null"] }
          },
          "additionalProperties": true,
          "maxProperties": 16
        },
        "expected_if_true": {
          "type": "array",
          "items": { "type": "string" }
        },
        "expected_if_false": {
          "type": "array",
          "items": { "type": "string" }
        },
        "fallback": {
          "type": "array",
          "items": { "type": "string" }
        },
        "dependencies": {
          "type": "array",
          "items": { "type": "string" },
          "uniqueItems": true
        },
        "info_gain": { "$ref": "#/$defs/InfoGain" },
        "estimated_cost": { "type": "integer", "minimum": 0 },
        "status": { "$ref": "#/$defs/CheckStatus" }
      }
    },
    "CheckPlan": {
      "type": "object",
      "additionalProperties": false,
      "required": ["generated_in_loop", "items", "strategy_summary"],
      "properties": {
        "generated_in_loop": { "type": "integer", "minimum": 0 },
        "items": {
          "type": "array",
          "items": { "$ref": "#/$defs/CheckItem" }
        },
        "strategy_summary": { "type": ["string", "null"] }
      }
    },
    "HypothesisImpact": {
      "type": "object",
      "additionalProperties": false,
      "required": ["hypothesis_id", "delta", "rationale"],
      "properties": {
        "hypothesis_id": { "type": "string", "minLength": 1 },
        "delta": { "type": "number", "minimum": -1, "maximum": 1 },
        "rationale": { "type": "string", "minLength": 1 }
      }
    },
    "CheckResult": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "check_id",
        "lane",
        "outcome",
        "raw_output_ref",
        "summary",
        "interpreted_result",
        "new_fact_ids",
        "hypothesis_impacts",
        "confidence",
        "completed_in_loop"
      ],
      "properties": {
        "check_id": { "type": "string", "minLength": 1 },
        "lane": { "$ref": "#/$defs/CheckLane" },
        "outcome": { "$ref": "#/$defs/CheckOutcome" },
        "raw_output_ref": { "type": ["string", "null"] },
        "summary": { "type": "string", "minLength": 1 },
        "interpreted_result": { "type": "string", "minLength": 1 },
        "new_fact_ids": {
          "type": "array",
          "items": { "type": "string" },
          "uniqueItems": true
        },
        "hypothesis_impacts": {
          "type": "array",
          "items": { "$ref": "#/$defs/HypothesisImpact" }
        },
        "confidence": { "$ref": "#/$defs/ConfidenceLabel" },
        "completed_in_loop": { "type": "integer", "minimum": 0 }
      }
    },
    "Blocker": {
      "type": "object",
      "additionalProperties": false,
      "required": ["blocker_id", "check_id", "type", "detail", "requires_human"],
      "properties": {
        "blocker_id": { "type": "string", "minLength": 1 },
        "check_id": { "type": ["string", "null"] },
        "type": { "$ref": "#/$defs/BlockerType" },
        "detail": { "type": "string", "minLength": 1 },
        "requires_human": { "type": "boolean" }
      }
    },
    "ToolUsage": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "jira_fetches",
        "jira_downloads",
        "kb_queries",
        "code_checks",
        "device_checks",
        "total_checks"
      ],
      "properties": {
        "jira_fetches": { "type": "integer", "minimum": 0 },
        "jira_downloads": { "type": "integer", "minimum": 0 },
        "kb_queries": { "type": "integer", "minimum": 0 },
        "code_checks": { "type": "integer", "minimum": 0 },
        "device_checks": { "type": "integer", "minimum": 0 },
        "total_checks": { "type": "integer", "minimum": 0 }
      }
    },
    "ExecutionState": {
      "type": "object",
      "additionalProperties": false,
      "required": ["results", "blockers", "tool_usage"],
      "properties": {
        "results": {
          "type": "array",
          "items": { "$ref": "#/$defs/CheckResult" }
        },
        "blockers": {
          "type": "array",
          "items": { "$ref": "#/$defs/Blocker" }
        },
        "tool_usage": { "$ref": "#/$defs/ToolUsage" }
      }
    },
    "HelpRequest": {
      "type": "object",
      "additionalProperties": false,
      "required": ["owner", "reasons", "minimum_required_inputs"],
      "properties": {
        "owner": { "$ref": "#/$defs/HelpOwner" },
        "reasons": {
          "type": "array",
          "items": { "type": "string" }
        },
        "minimum_required_inputs": {
          "type": "array",
          "items": { "type": "string" }
        }
      }
    },
    "DecisionState": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "current_verdict",
        "closure_level",
        "top_hypothesis_ids",
        "rationale",
        "unresolved_gaps",
        "rerun_focus",
        "do_not_repeat_check_ids",
        "help_request",
        "finalized_explanation"
      ],
      "properties": {
        "current_verdict": { "$ref": "#/$defs/DecisionVerdict" },
        "closure_level": { "$ref": "#/$defs/ClosureLevel" },
        "top_hypothesis_ids": {
          "type": "array",
          "items": { "type": "string" },
          "uniqueItems": true
        },
        "rationale": { "type": ["string", "null"] },
        "unresolved_gaps": {
          "type": "array",
          "items": { "type": "string" }
        },
        "rerun_focus": {
          "type": "array",
          "items": { "type": "string" }
        },
        "do_not_repeat_check_ids": {
          "type": "array",
          "items": { "type": "string" },
          "uniqueItems": true
        },
        "help_request": {
          "anyOf": [{ "$ref": "#/$defs/HelpRequest" }, { "type": "null" }]
        },
        "finalized_explanation": { "type": ["string", "null"] }
      }
    },
    "HistoryEvent": {
      "type": "object",
      "additionalProperties": false,
      "required": ["event_id", "loop_index", "actor", "event_type", "summary", "patch_ref", "timestamp"],
      "properties": {
        "event_id": { "type": "string", "minLength": 1 },
        "loop_index": { "type": "integer", "minimum": 0 },
        "actor": {
          "type": "string",
          "enum": ["harness", "intake", "hypothesis", "probe", "judge"]
        },
        "event_type": { "type": "string", "minLength": 1 },
        "summary": { "type": "string", "minLength": 1 },
        "patch_ref": { "type": ["string", "null"] },
        "timestamp": { "type": "string", "format": "date-time" }
      }
    },
    "HistoryLog": {
      "type": "object",
      "additionalProperties": false,
      "required": ["events"],
      "properties": {
        "events": {
          "type": "array",
          "items": { "$ref": "#/$defs/HistoryEvent" }
        }
      }
    }
  }
}
```

---

## Review Notes

### Good enough for MVP

This draft already enforces several important constraints:
- state is sectioned
- facts require sources
- hypotheses must include support/contradiction/missing evidence fields
- checks must define positive and negative expectation
- decision state is centralized
- history is explicit

### Intentionally still missing

This draft still does **not** enforce some higher-order rules at pure schema level, for example:
- `decision.top_hypothesis_ids` must exist in `hypotheses.items`
- `check_result.check_id` must exist in `plan.items`
- `meta.owner_agent` must match legal next actor for current `status`
- finalized verdict must require non-empty `top_hypothesis_ids`
- certain status/verdict combinations should be forbidden

Those should be implemented in a **semantic validator** or transition validator, not only JSON Schema.

### Important review questions

When reviewing this schema, I suggest we go field block by field block in this order:
1. `meta`
2. `facts`
3. `hypotheses`
4. `plan`
5. `execution`
6. `decision`
7. cross-field semantic rules

That order is best because:
- `meta` defines state machine ground rules
- `facts` defines the floor truth
- `hypotheses` defines reasoning discipline
- `plan/execution` define the probe contract
- `decision` defines closure

---

## Suggested Next Step

Next review pass should likely do one of these:

1. tighten this MVP schema block by block
2. add semantic validation rules alongside schema
3. define `Patch` schemas next

Recommended immediate next step: **review `meta` and `facts` first before touching the rest**.
