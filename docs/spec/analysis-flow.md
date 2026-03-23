# ANALYSIS_FLOW.MD

## Purpose

This document reviews the current `runloop_agent/demo.yaml` analysis workflow and makes the step input/output boundaries explicit.

The main design rule is:

> Each step should consume only the artifacts required by its own responsibility.
> Transport artifacts and unrelated intermediate artifacts should not be visible to later LLM steps by default.

---

## High-Level Flow

```text
workflow.inputs
  ├─ jira_key
  └─ platform_inventory

jira_phase
  1. find_jira
  2. grep_jira_properties
  3. select_jira_attachments
  4. download_jira_attachments

analysis_phase
  5. extract_log_signatures      (tool: log_extract_evidence_batch)
  6. extract_observations
  7. extract_platform_context
  8. extract_retrieval_context
  9. summarize_jira_issue
  10. kb_ground_case
  11. propose_root_cause
```

---

## Step-by-Step IO and Visibility Review

### 1. `find_jira`
- Type: `tool_step`
- Input:
  - `workflow.inputs.jira_key`
- Output:
  - `jira_key_lookup`
- Visible to later LLM steps:
  - **No** by default
- Reason:
  - This is a lookup/validation artifact, not business evidence.

### 2. `grep_jira_properties`
- Type: `tool_step`
- Input:
  - `workflow.inputs.jira_key`
- Output:
  - `jira_properties`
- Visible to later LLM steps:
  - **Yes**, selectively
- Reason:
  - This is the main structured Jira evidence artifact.

### 3. `select_jira_attachments`
- Type: `tool_step`
- Input:
  - `workflow.inputs.jira_key`
- Output:
  - `jira_attachment_urls`
- Visible to later LLM steps:
  - **No**
- Reason:
  - Transport-only intermediate artifact.

### 4. `download_jira_attachments`
- Type: `tool_step`
- Input:
  - `workflow.inputs.jira_key`
  - `jira_attachment_urls`
- Output:
  - `artifact_attachments`
- Visible to later LLM steps:
  - **No**
- Reason:
  - Transport/local-path artifact only.

### 5. `extract_log_signatures`
- Actual tool: `log_extract_evidence_batch`
- Type: `tool_step`
- Input:
  - `artifact_attachments`
- Output:
  - `signature_logs`
- Visible to later LLM steps:
  - **Yes**, selectively
- Reason:
  - This is the main structured log evidence artifact.

### 6. `extract_observations`
- Type: `llm_step`
- Responsibility:
  - evidence extraction only
  - no platform normalization
  - no retrieval planning
  - no root-cause analysis
- Visible artifacts:
  - `jira_key`
  - `jira_properties`
  - `signature_logs`
- Not visible:
  - `platform_inventory`
  - `jira_attachment_urls`
  - `artifact_attachments`
  - `jira_key_lookup`
- Output:
  - `artifact:extract_observations`

### 7. `extract_platform_context`
- Type: `llm_step`
- Responsibility:
  - platform normalization only
  - this is the only analysis step that should normalize platform names
- Visible artifacts:
  - `jira_properties`
  - `signature_logs`
  - `platform_inventory`
- Not visible:
  - `artifact_attachments`
  - `jira_attachment_urls`
  - `jira_key_lookup`
  - `artifact:extract_observations`
- Output:
  - `artifact:extract_platform_context`

### 8. `extract_retrieval_context`
- Type: `llm_step`
- Responsibility:
  - flatten upstream results into retrieval-friendly fields
  - do not re-normalize platforms
- Visible artifacts:
  - `jira_properties`
  - `signature_logs`
  - `artifact:extract_observations`
  - `artifact:extract_platform_context`
- Not visible:
  - `platform_inventory`
  - `artifact_attachments`
  - `jira_attachment_urls`
  - `jira_key_lookup`
- Output:
  - `artifact:extract_retrieval_context`

### 9. `summarize_jira_issue`
- Type: `llm_step`
- Responsibility:
  - summarize the case from upstream extracted observations
  - do not re-read raw evidence if the observation artifact already exists
- Visible artifacts:
  - `artifact:extract_observations`
- Not visible:
  - `platform_inventory`
  - `signature_logs`
  - `artifact_attachments`
  - `jira_attachment_urls`
  - `jira_key_lookup`
- Output:
  - `artifact:summarize_jira_issue`

### 10. `kb_ground_case`
- Type: `tool_step`
- Input:
  - `artifact:extract_retrieval_context.platforms`
  - `artifact:extract_retrieval_context.subsystems`
  - `artifact:extract_retrieval_context.signals`
- Output:
  - `kb_grounding`
- Visible to later LLM steps:
  - **Yes**, selectively

### 11. `propose_root_cause`
- Type: `llm_step`
- Responsibility:
  - integrate observations + platform context + retrieval context + KB grounding
  - propose constrained root-cause hypotheses
- Visible artifacts:
  - `jira_properties`
  - `artifact:extract_observations`
  - `artifact:extract_platform_context`
  - `artifact:extract_retrieval_context`
  - `artifact:summarize_jira_issue`
  - `kb_grounding`
- Not visible:
  - `platform_inventory`
  - `artifact_attachments`
  - `jira_attachment_urls`
  - `jira_key_lookup`

---

## Transport Artifacts vs Semantic Artifacts

### Transport / plumbing artifacts
These should generally **not** be visible to LLM steps:
- `jira_key_lookup`
- `jira_attachment_urls`
- `artifact_attachments`
- `step:*` trace artifacts

### Semantic artifacts
These are valid step inputs when needed:
- `jira_properties`
- `signature_logs`
- `platform_inventory` (platform step only)
- `artifact:extract_observations`
- `artifact:extract_platform_context`
- `artifact:extract_retrieval_context`
- `artifact:summarize_jira_issue`
- `kb_grounding`

---

## Recommended Visibility Matrix

| Step | Should be visible |
|---|---|
| `extract_observations` | `jira_key`, `jira_properties`, `signature_logs` |
| `extract_platform_context` | `jira_properties`, `signature_logs`, `platform_inventory` |
| `extract_retrieval_context` | `jira_properties`, `signature_logs`, `artifact:extract_observations`, `artifact:extract_platform_context` |
| `summarize_jira_issue` | `artifact:extract_observations` |
| `propose_root_cause` | `jira_properties`, `artifact:extract_observations`, `artifact:extract_platform_context`, `artifact:extract_retrieval_context`, `artifact:summarize_jira_issue`, `kb_grounding` |

---

## Current Design Intent

The intended execution layering is:

```text
raw jira/log inputs
  -> structured log evidence
  -> observations
  -> platform normalization
  -> retrieval flattening
  -> KB grounding
  -> summary
  -> root cause hypotheses
```

This means:
- each step should consume the artifact layer directly below its own responsibility
- later steps should not casually re-open unrelated earlier inputs
- `platform_inventory` should not leak into observation extraction
- transport artifacts should not distract LLM steps

---

## Practical Rule

If a step can be accurately defined as a function:

```text
output = f(selected upstream artifacts)
```

then its `visible_artifacts` should contain only those selected upstream artifacts, not the whole global artifact state.
