# Debug Agent Harness Data Model Sketch

## Overview

This document captures a harness-friendly data model sketch for a multi-stage debug agent targeting new hardware platform Linux kernel bring-up, adaptation, and stability debugging.

The model is organized into three layers:

1. **Canonical State**: the single structured source of truth for the case
2. **Agent Views**: stage-specific projections implementing progressive disclosure
3. **Patches**: restricted agent outputs merged by the harness under validation

Core goals:

- Preserve a single consistent case state
- Separate facts, inferences, hypotheses, execution, and decisions
- Support progressive disclosure per stage
- Enforce mechanical constraints through schema, ownership, and merge validation
- Make reruns incremental instead of restarting from scratch

---

## Design Principles

### 1. Canonical State is the source of truth

Canonical State stores:
- current structured case status
- confirmed facts
- anomalies and evidence
- hypotheses and plans
- execution results
- decisions and audit history

Canonical State should **not** become:
- a dumping ground for long free-form analysis
- a mutable blob everyone edits freely
- a storage layer for full raw logs or full documents

Large source materials should be stored as references, snippets, and digests where possible.

### 2. Views provide minimal sufficient context

Each agent should read a projected view of the state rather than the entire state.
This is the key mechanism for progressive disclosure.

### 3. Patches provide restricted writes

Agents do not directly mutate Canonical State.
They submit typed patches. The harness validates, merges, and advances the state machine.

### 4. Facts, inferences, hypotheses, and decisions must stay separate

- **Facts**: observed and source-traceable
- **Inferences**: derived intermediate judgments
- **Hypotheses**: competing explanations of root cause
- **Decisions**: control-flow and case closure outputs

Do not mix them.

---

# 1. Canonical State

Logical shape:

```yaml
CaseState:
  meta: Meta
  issue: IssueBundle
  artifacts: ArtifactIndex
  facts: FactLedger
  anomalies: AnomalySet
  kb: KnowledgeContext
  hypotheses: HypothesisTable
  evidence: EvidenceGraph
  plan: CheckPlan
  execution: ExecutionState
  decision: DecisionState
  history: HistoryLog
```

---

## 1.1 Meta

```yaml
Meta:
  case_id: string
  external_id: string|null
  status: enum
  loop_index: integer
  created_at: timestamp
  updated_at: timestamp
  owner_agent: enum|null
  schema_version: string
  tags: [string]
```

### Notes

- `status` is the core state machine field.
- `owner_agent` tells the harness which agent should run next.
- `schema_version` supports future migrations.

Typical `status` values:
- `NEW`
- `INTAKE_READY`
- `HYPOTHESES_READY`
- `PROBING`
- `JUDGING`
- `NEED_RERUN`
- `FINALIZED_STRONG`
- `FINALIZED_WEAK`
- `NEED_HELP`

---

## 1.2 IssueBundle

```yaml
IssueBundle:
  source: enum
  issue_id: string
  summary: string
  description: string
  comments: [CommentRef]
  labels: [string]
  priority: string|null
  reporter: string|null
  assignee: string|null
  created_at: timestamp|null
  updated_at: timestamp|null
```

### CommentRef

```yaml
CommentRef:
  comment_id: string
  author: string|null
  created_at: timestamp|null
  snippet: string
  artifact_ref: string|null
```

### Notes

IssueBundle keeps enough structured issue context for reasoning, but avoids storing very large raw text directly in state.

---

## 1.3 ArtifactIndex

This indexes raw and derived materials.

```yaml
ArtifactIndex:
  attachments: [ArtifactRef]
  normalized_logs: [ArtifactRef]
  derived_snippets: [SnippetRef]
  code_refs: [CodeRef]
```

### ArtifactRef

```yaml
ArtifactRef:
  artifact_id: string
  kind: enum
  name: string
  mime_type: string|null
  uri: string|null
  digest: string|null
  size_bytes: integer|null
  provenance: Provenance
```

### SnippetRef

```yaml
SnippetRef:
  snippet_id: string
  source_artifact_id: string
  start: string|null
  end: string|null
  text: string
  purpose: enum
```

### CodeRef

```yaml
CodeRef:
  ref_id: string
  repo: string|null
  file: string
  symbol: string|null
  commit: string|null
  line_range: string|null
  snippet: string|null
```

### Notes

Artifacts are indexed, not fully embedded. Canonical State stores references and targeted snippets, not giant payloads.

---

## 1.4 FactLedger

Facts are the system ground truth. Only source-traceable observations belong here.

```yaml
FactLedger:
  core: [Fact]
  platform: PlatformFacts
  software: SoftwareFacts
  runtime: RuntimeFacts
  environment: EnvironmentFacts
  missing: [MissingFact]
```

### Fact

```yaml
Fact:
  fact_id: string
  key: string
  value: any
  value_type: enum
  confidence: enum
  source_refs: [SourceRef]
  observed_in_loop: integer
  mutable: boolean
```

### SourceRef

```yaml
SourceRef:
  kind: enum
  ref_id: string
  locator: string|null
```

### PlatformFacts

```yaml
PlatformFacts:
  platform_name: Fact|null
  board_name: Fact|null
  soc: Fact|null
  boot_mode: Fact|null
  bios_version: Fact|null
  firmware_version: Fact|null
```

### SoftwareFacts

```yaml
SoftwareFacts:
  kernel_version: Fact|null
  kernel_branch: Fact|null
  config_flavor: Fact|null
  distro: Fact|null
  distro_version: Fact|null
  firmware_package_state: Fact|null
```

### RuntimeFacts

```yaml
RuntimeFacts:
  failure_stage: Fact|null
  repro_rate: Fact|null
  first_failure_time: Fact|null
  affected_subsystems: Fact|null
  observed_modules: Fact|null
```

### EnvironmentFacts

```yaml
EnvironmentFacts:
  test_case_name: Fact|null
  repro_steps_present: Fact|null
  known_good_baseline: Fact|null
  issue_regression_flag: Fact|null
```

### MissingFact

```yaml
MissingFact:
  key: string
  reason: string
  importance: enum
  suggested_source: enum
```

### Notes

`facts.missing` is important: it distinguishes “not present” from “not yet known”.

---

## 1.5 AnomalySet

This represents observed failure signals, not root cause conclusions.

```yaml
AnomalySet:
  items: [Anomaly]
  timeline_summary: TimelineSummary
```

### Anomaly

```yaml
Anomaly:
  anomaly_id: string
  category: enum
  message: string
  normalized_message: string|null
  source_refs: [SourceRef]
  stage: enum|null
  severity: enum
  earliest_rank: integer|null
  likely_primary: boolean
  related_subsystems: [string]
```

### TimelineSummary

```yaml
TimelineSummary:
  earliest_anomaly_id: string|null
  ordered_anomaly_ids: [string]
  notes: string|null
```

### Notes

This layer exists to keep anomaly observation separate from explanation.

---

## 1.6 KnowledgeContext

KB content should enter the system as structured prior knowledge, not as raw text dump.

```yaml
KnowledgeContext:
  searches: [KbSearchRecord]
  incidents: [KbIncident]
  decisive_checks: [KbCheckHint]
  false_positive_patterns: [KbPattern]
```

### KbSearchRecord

```yaml
KbSearchRecord:
  search_id: string
  query_signature: object
  returned_ids: [string]
  used_in_loop: integer
```

### KbIncident

```yaml
KbIncident:
  kb_id: string
  title: string
  relevance: number
  version_compatibility: enum
  summary: string
  source_ref: SourceRef|null
```

### KbCheckHint

```yaml
KbCheckHint:
  hint_id: string
  target_class: string
  subsystem: string|null
  description: string
  suggested_check_template: string
  source_ref: SourceRef|null
```

### KbPattern

```yaml
KbPattern:
  pattern_id: string
  description: string
  warning: string
```

---

## 1.7 HypothesisTable

This is the core reasoning structure.

```yaml
HypothesisTable:
  required_classes: [string]
  items: [Hypothesis]
  ranking_method: string|null
```

### Hypothesis

```yaml
Hypothesis:
  hypothesis_id: string
  class: enum
  statement: string
  scope: HypothesisScope
  confidence: number
  status: enum
  support_refs: [EvidenceRef]
  contradiction_refs: [EvidenceRef]
  missing_refs: [GapRef]
  discriminating_check_ids: [string]
  introduced_in_loop: integer
  updated_in_loop: integer
```

### HypothesisScope

```yaml
HypothesisScope:
  subsystem: string|null
  layer: enum|null
  component: string|null
```

### EvidenceRef

```yaml
EvidenceRef:
  evidence_id: string
  weight: number
```

### GapRef

```yaml
GapRef:
  gap_id: string
  description: string
  closure_requirement: enum
```

### Notes

Every hypothesis should point to:
- supporting evidence
- contradictory evidence
- missing evidence
- discriminating checks

Without all four, it tends to degrade into free-form storytelling.

---

## 1.8 EvidenceGraph

```yaml
EvidenceGraph:
  nodes: [EvidenceNode]
  edges: [EvidenceEdge]
```

### EvidenceNode

```yaml
EvidenceNode:
  evidence_id: string
  kind: enum
  text: string
  source_refs: [SourceRef]
  created_by: enum
```

### EvidenceEdge

```yaml
EvidenceEdge:
  from_id: string
  to_id: string
  relation: enum
  weight: number
```

### Notes

If a full graph is too heavy for v1, it can be simplified into a flat evidence list. But architecturally, graph representation is more faithful to real debugging evidence.

---

## 1.9 CheckPlan

CheckPlan is the execution contract for the Probe agent.

```yaml
CheckPlan:
  generated_in_loop: integer
  items: [CheckItem]
  strategy_summary: string|null
```

### CheckItem

```yaml
CheckItem:
  check_id: string
  target_hypothesis_id: string
  lane: enum
  priority: integer
  goal: string
  tool_action: string
  inputs: object
  expected_if_true: [string]
  expected_if_false: [string]
  fallback: [string]
  dependencies: [string]
  info_gain: enum
  estimated_cost: integer
  status: enum
```

### Notes

Each check item should define both positive and negative interpretation. This prevents one-sided evidence collection.

---

## 1.10 ExecutionState

```yaml
ExecutionState:
  results: [CheckResult]
  blockers: [Blocker]
  tool_usage: ToolUsage
```

### CheckResult

```yaml
CheckResult:
  check_id: string
  lane: enum
  outcome: enum
  raw_output_ref: string|null
  summary: string
  interpreted_result: string
  new_fact_ids: [string]
  new_evidence_ids: [string]
  hypothesis_impacts: [HypothesisImpact]
  confidence: enum
  completed_in_loop: integer
```

### HypothesisImpact

```yaml
HypothesisImpact:
  hypothesis_id: string
  delta: number
  rationale: string
```

### Blocker

```yaml
Blocker:
  blocker_id: string
  check_id: string|null
  type: enum
  detail: string
  requires_human: boolean
```

### ToolUsage

```yaml
ToolUsage:
  jira_fetches: integer
  jira_downloads: integer
  kb_queries: integer
  code_checks: integer
  device_checks: integer
  total_checks: integer
```

---

## 1.11 DecisionState

```yaml
DecisionState:
  current_verdict: enum|null
  closure_level: enum|null
  top_hypothesis_ids: [string]
  rationale: string|null
  unresolved_gaps: [string]
  rerun_focus: [string]
  do_not_repeat_check_ids: [string]
  help_request: HelpRequest|null
  finalized_root_cause: string|null
```

### HelpRequest

```yaml
HelpRequest:
  owner: enum|null
  reasons: [string]
  minimum_required_inputs: [string]
```

### Notes

Judge should write verdicts only into this section. Do not let closure state leak across unrelated fields.

---

## 1.12 HistoryLog

```yaml
HistoryLog:
  events: [HistoryEvent]
```

### HistoryEvent

```yaml
HistoryEvent:
  event_id: string
  loop_index: integer
  actor: enum
  event_type: string
  summary: string
  patch_ref: string|null
  timestamp: timestamp
```

### Notes

This provides auditability and supports postmortem analysis of why the system took a certain path.

---

# 2. Agent Views

Agent Views are the main implementation of progressive disclosure.
Each agent gets a projected slice of Canonical State rather than the full state.

---

## 2.1 IntakeView

```yaml
IntakeView:
  meta:
    case_id
    loop_index
    status
  issue:
    issue_id
    summary
    description
    comments
    labels
  artifacts:
    attachments
  prior_context:
    retained_facts_summary
    prior_missing_facts
```

### Purpose

- fetch and normalize source materials
- produce facts and anomalies
- identify missing critical information

### Deliberately hidden

- full hypothesis ranking
- long Judge narratives
- unrelated execution detail

---

## 2.2 HypothesisView

```yaml
HypothesisView:
  meta:
    case_id
    loop_index
  facts:
    fact_ledger
  anomalies:
    anomaly_set
  kb:
    incidents
    decisive_checks
    false_positive_patterns
  prior_execution_summary:
    recent_check_results
    unresolved_gaps
    blocked_summary
  selected_snippets:
    relevant_log_snippets
    relevant_issue_snippets
```

### Purpose

- generate competing root-cause hypotheses
- define discriminating checks
- construct check plan

### Deliberately hidden

- all raw logs in full
- irrelevant raw outputs
- all historical patches

---

## 2.3 ProbeView

Probe should receive the most constrained context.

```yaml
ProbeView:
  meta:
    case_id
    loop_index
    budget_remaining
  facts:
    relevant_facts
  active_hypotheses:
    hypothesis_ids
    class
    statement
    confidence
    target_scope
  plan:
    check_items
  execution_constraints:
    max_followup_checks
    allowed_tools
    do_not_repeat_check_ids
```

### Purpose

- execute planned checks
- optionally add tightly bounded follow-up checks

### Deliberately hidden

- long-form analytical prose
- full KB documents
- broad historical noise

---

## 2.4 JudgeView

```yaml
JudgeView:
  meta:
    case_id
    loop_index
    budget_status
  facts:
    updated_fact_summary
  hypotheses:
    current_table
  execution:
    recent_results
    blockers
  evidence:
    summarized_supports
    summarized_contradictions
  policy:
    closure_rules
    rerun_rules
```

### Purpose

- determine closure
- issue rerun/finalize/help decision
- update hypothesis states

### Deliberately hidden

- all raw attachments in full
- unrelated raw output blobs

---

# 3. Patch Model

Agents should not directly overwrite Canonical State.
They should submit typed patches that the harness validates and merges.

---

## 3.1 IntakePatch

```yaml
IntakePatch:
  patch_meta:
    actor: intake
    loop_index: integer
  issue_updates:
    comment_refs_added: [CommentRef]
    artifact_refs_added: [ArtifactRef]
  fact_additions: [Fact]
  anomaly_additions: [Anomaly]
  missing_fact_additions: [MissingFact]
  selected_snippet_additions: [SnippetRef]
  state_transition_request:
    from: NEW|NEED_RERUN
    to: INTAKE_READY
```

### Permissions

May add:
- facts
- anomalies
- snippets
- missing facts

May not add:
- hypothesis confidence changes
- final verdicts

---

## 3.2 HypothesisPatch

```yaml
HypothesisPatch:
  patch_meta:
    actor: hypothesis
    loop_index: integer
  kb_updates:
    searches_added: [KbSearchRecord]
    incidents_added: [KbIncident]
    decisive_checks_added: [KbCheckHint]
  hypothesis_replacements: [Hypothesis]
  evidence_additions: [EvidenceNode]
  evidence_edges_additions: [EvidenceEdge]
  check_plan_replacement:
    generated_in_loop: integer
    items: [CheckItem]
  state_transition_request:
    from: INTAKE_READY
    to: HYPOTHESES_READY
```

### Permissions

May write:
- hypotheses
- evidence
- check plan
- structured KB outputs

May not write:
- raw execution results
- final verdicts

---

## 3.3 ProbePatch

```yaml
ProbePatch:
  patch_meta:
    actor: probe
    loop_index: integer
  check_result_additions: [CheckResult]
  blocker_additions: [Blocker]
  fact_additions: [Fact]
  evidence_additions: [EvidenceNode]
  tool_usage_delta:
    jira_fetches: integer
    jira_downloads: integer
    kb_queries: integer
    code_checks: integer
    device_checks: integer
    total_checks: integer
  optional_followup_checks: [CheckItem]
  state_transition_request:
    from: HYPOTHESES_READY|PROBING
    to: PROBING|JUDGING
```

### Permissions

May write:
- check results
- blockers
- new facts from probes
- bounded follow-up checks

May not write:
- final verdicts
- arbitrary hypothesis deletion

---

## 3.4 JudgePatch

```yaml
JudgePatch:
  patch_meta:
    actor: judge
    loop_index: integer
  hypothesis_status_updates:
    - hypothesis_id: string
      confidence: number
      status: active|weakened|eliminated|confirmed
      reason: string
  decision_update:
    current_verdict: enum
    closure_level: enum
    top_hypothesis_ids: [string]
    rationale: string
    unresolved_gaps: [string]
    rerun_focus: [string]
    do_not_repeat_check_ids: [string]
    help_request: HelpRequest|null
    finalized_root_cause: string|null
  state_transition_request:
    from: JUDGING
    to: NEED_RERUN|FINALIZED_STRONG|FINALIZED_WEAK|NEED_HELP
```

### Permissions

May write:
- decision state
- hypothesis status/confidence updates

May not write:
- fabricated facts
- fabricated raw probe outputs

---

# 4. Harness Merge and Validation Rules

Patches should never be merged blindly.

---

## 4.1 Base validation

- `patch.actor` must match current `owner_agent`
- `patch.loop_index` must match current `loop_index`
- `state_transition_request` must be legal

---

## 4.2 Type validation

Examples:
- every `Fact` must contain `source_refs`
- every `Hypothesis` must contain support, contradiction, and missing evidence references
- every `CheckItem` must contain `expected_if_true` and `expected_if_false`
- finalized decision must contain `top_hypothesis_ids`

---

## 4.3 Permission validation

Examples:
- `IntakePatch` cannot contain `decision_update`
- `ProbePatch` cannot rewrite hypothesis status
- `JudgePatch` cannot add raw artifacts

---

## 4.4 Budget validation

Examples:
- merged `tool_usage_delta` cannot exceed budget
- optional follow-up checks cannot exceed configured limit

---

## 4.5 Consistency validation

Examples:
- every `decision.top_hypothesis_ids` entry must exist in `hypotheses.items`
- every `check_result.check_id` must exist in the plan or in allowed follow-up checks
- every `new_fact_ids` reference must resolve to facts added by the patch or existing state

---

# 5. MVP Recommendation

If implementing incrementally, start with a reduced model.

## 5.1 MVP Canonical State

```yaml
CaseState:
  meta
  issue
  facts
  anomalies
  hypotheses
  plan
  execution
  decision
  history
```

Can postpone for v2:
- full `ArtifactIndex`
- full `EvidenceGraph`
- richer `KnowledgeContext`

But reserve extension points for them.

---

## 5.2 MVP Views

Implement at least:
- `IntakeView`
- `HypothesisView`
- `ProbeView`
- `JudgeView`

Even simple field projection is much better than passing full state everywhere.

---

## 5.3 MVP Patches

Implement at least:
- `IntakePatch`
- `HypothesisPatch`
- `ProbePatch`
- `JudgePatch`

The most important thing early is to lock down who can write what.

---

# 6. Summary

This model can be summarized as:

- **Canonical State** solves global consistency
- **Agent Views** implement progressive disclosure
- **Typed Patches + Validators** enforce mechanical constraints

All three matter. If one is missing, the system tends to drift:

- without Canonical State: no consistent memory
- without Views: no real progressive disclosure
- without Patches and Validators: no real mechanical constraints

---

# 7. Suggested Next Step

Recommended implementation order:

1. reduce this sketch into an MVP field set
2. translate MVP fields into JSON Schema
3. define transition rules
4. only then finalize prompts

If prompts are written first and structure comes later, the system will almost certainly become brittle.
