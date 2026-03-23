# simple_rla requirement v2

This document defines the next-stage design target for `simple-rla` beyond the current v1 grounded planning prototype.

The goal of v2 is to move from:

> grounded case intake + artifact triage + provisional DEBUG_STEPS drafting

to:

> hypothesis-driven debugging + evidence execution + evidence-based correction

The central design change is:

> `DEBUG_STEPS` is no longer the effective endpoint.
> It becomes an intermediate planning artifact inside a longer evidence-closure chain.

---

## 1. Design intent

The current v1 chain is roughly:
- fetch Jira
- download artifacts
- extract signatures
- do lightweight KB grounding
- draft provisional DEBUG_STEPS
- stop

The v2 chain must be expanded into a full closed loop that can:
- form a possible failure reason/hypothesis
- generate DEBUG_STEPS from that hypothesis
- continue fetching device/code evidence after plan generation
- summarize the issue using new evidence
- terminate with an explicit final state

The target chain for v2 is:

1. `fetch_jira`
2. `download_artifacts`
3. `find_error_signature`
4. `think_with_knowledge_base`
5. `provide_possible_failure_reason`
6. `generate_debug_steps`
7. `device_evidence_fetch`
8. `code_evidence_fetch`
9. `summarize_issue_with_evidence`
10. `correct_rca / BLOCKED / HELP_NEEDED`

---

## 2. Four-stage grouping

For implementation, the ten steps should be grouped into four larger stages.

### Stage A — Case intake
Includes:
- Step 1 `fetch_jira`
- Step 2 `download_artifacts`

Primary output:
- case context
- artifact manifest
- local artifact paths

---

### Stage B — Grounded hypothesis formation
Includes:
- Step 3 `find_error_signature`
- Step 4 `think_with_knowledge_base`
- Step 5 `provide_possible_failure_reason`

Primary output:
- primary failure signature pack
- KB grounding pack
- main hypothesis / possible failure reason

---

### Stage C — Debug planning and evidence execution
Includes:
- Step 6 `generate_debug_steps`
- Step 7 `device_evidence_fetch`
- Step 8 `code_evidence_fetch`

Primary output:
- structured DEBUG_STEPS
- device evidence pack
- code evidence pack

---

### Stage D — Evidence closure
Includes:
- Step 9 `summarize_issue_with_evidence`
- Step 10 `correct_rca / BLOCKED / HELP_NEEDED`

Primary output:
- evidence-grounded issue summary
- final state label
- remaining gaps / blockers if unresolved

---

## 3. The 10 required steps

---

## Step 1 — `fetch_jira`

### Purpose
Obtain the minimal valid case framing from Jira.

### Input
- Jira key or search target

### Output
- issue summary
- platform/mode hints
- attachment list
- minimal framing for downstream use

### Allowed tools
- `jira_search`
- `jira_get`
- `jira_list_attachments`

### Must not do
- no deep RCA
- no broad artifact reading
- no KB grounding yet

### Exit condition
The run has enough case context to decide which artifacts should be downloaded.

---

## Step 2 — `download_artifacts`

### Purpose
Download only the artifacts required for first-pass triage.

### Input
- attachment metadata from Step 1

### Output
- local artifact paths
- artifact manifest for the run workspace

### Allowed tools
- `jira_fetch_attachment`

### Must not do
- no large in-context previews
- no KB analysis
- no final planning

### Exit condition
At least the key artifacts for first-pass signature extraction are present locally.

---

## Step 3 — `find_error_signature`

### Purpose
Extract the primary crash/failure signature and distinguish core signals from noise.

### Input
- downloaded artifacts

### Output
- primary fatal signature
- trace anchor
- dominant failure mode
- supporting errors
- shared-path vs mode-delta distinction when relevant

### Allowed tools
- `log_extract_signatures`
- `log_compare`
- limited targeted file reads if necessary

### Must not do
- no final DEBUG_STEPS yet
- no broad log reading without purpose
- no promotion of peripheral errors into the main line without causal support

### Exit condition
The run can state what the main crash surface is and which signal should anchor subsequent reasoning.

---

## Step 4 — `think_with_knowledge_base`

### Purpose
Use the KB as a grounding layer for the extracted signature and case context.

### Input
- primary crash/signature pack
- structured context

### Output
- matched KB objects
- focus areas
- recommended next reads
- grounded vocabulary for subsequent hypothesis formation

### Allowed tools
- prefer `kb_ground`
- optional `kb_search` / `kb_get` only when needed

### Must not do
- no broad KB exploration
- no final RCA
- KB must remain support, not authority

### Exit condition
The run has enough KB grounding to support one main possible failure reason.

---

## Step 5 — `provide_possible_failure_reason`

### Purpose
Explicitly produce a main hypothesis before planning.

### Input
- crash signature pack
- KB grounding pack
- case framing

### Output
- one main possible failure reason / mechanism hypothesis
- optional weaker alternatives
- evidence support and evidence gaps for the main hypothesis

### Allowed tools
- normally none; this is a reasoning/synthesis step

### Must not do
- do not skip directly to DEBUG_STEPS
- do not collapse crash point and root-cause origin into the same thing
- do not replace uncertainty with overconfident prose

### Exit condition
A single main hypothesis exists that can drive targeted debug steps.

---

## Step 6 — `generate_debug_steps`

### Purpose
Convert the main hypothesis into a concrete debugging plan.

### Input
- main hypothesis
- known evidence
- evidence gaps

### Output
- DEBUG_STEPS document/structure with:
  - problem framing
  - most likely direction
  - concrete next steps
  - unknowns
  - why this path first

### Allowed tools
- normally none; this is a planning step

### Required quality rules
- steps must be evidence-oriented, not topic-oriented
- strongest existing evidence must anchor the plan
- crash site alone must not dominate the plan when stronger upstream evidence exists
- peripheral errors must not enter top steps without causal support
- the plan must distinguish:
  - device evidence to fetch
  - code evidence to fetch

### Exit condition
A structured DEBUG_STEPS plan exists that can drive evidence collection.

---

## Step 7 — `device_evidence_fetch`

### Purpose
Execute the device-side portion of DEBUG_STEPS.

### Input
- DEBUG_STEPS device-side actions
- current hypothesis

### Output
- device evidence pack
- config comparison results
- binding/probe/resource-path observations

### Allowed tools
This phase requires stronger support than v1 currently has. In v2, it should support one or more of:
- targeted file/log reads over newly relevant artifacts
- environment/config inspection
- structured handling of user-provided device observations
- future device-side plugins or probes

### Must not do
- do not re-open the whole case broadly
- do not drift into unrelated subsystem checks

### Exit condition
The hypothesis has been updated with at least one meaningful device-side validation or falsification signal.

---

## Step 8 — `code_evidence_fetch`

### Purpose
Execute the code-side portion of DEBUG_STEPS.

### Input
- DEBUG_STEPS code-side actions
- crash signature
- current hypothesis

### Output
- code evidence pack
- caller-path evidence
- invariant/precondition evidence
- relation between code evidence and device/path evidence

### Allowed tools
This phase also needs stronger support than v1 currently has. In v2 it should support one or more of:
- targeted source reads
- code search
- function/caller tracing in source form
- KB code-note support
- future code-aware tooling

### Must not do
- do not remain at the crash site only
- do not ignore the system/resource path already identified by earlier evidence

### Exit condition
The run can describe which code path reaches the crash point and what precondition is most likely violated.

---

## Step 9 — `summarize_issue_with_evidence`

### Purpose
Perform a second-pass synthesis using the newly collected device and code evidence.

### Input
- main hypothesis
- device evidence pack
- code evidence pack
- unresolved unknowns

### Output
- evidence-grounded issue summary
- updated confidence statement
- refined explanation of the failure chain
- explicit remaining gaps

### Allowed tools
- normally none; this is a synthesis step

### Must not do
- do not merely repeat the provisional DEBUG_STEPS
- do not ignore new evidence that weakens the original hypothesis

### Exit condition
The run has an evidence-based summary strong enough for final state classification.

---

## Step 10 — `correct_rca / BLOCKED / HELP_NEEDED`

### Purpose
Produce the correct terminal state of the run.

### Input
- evidence-grounded issue summary
- confidence statement
- unresolved blockers/gaps

### Output
One of the following terminal states:
- `correct_rca`
- `BLOCKED`
- `HELP_NEEDED`

### Definitions
#### `correct_rca`
Use when:
- the main causal chain is supported by accumulated evidence
- the result is stronger than a provisional hypothesis
- the remaining unknowns are no longer critical to the main conclusion

#### `BLOCKED`
Use when:
- the next valuable step is known
- but the run lacks tools, permissions, environment access, or artifacts to continue

#### `HELP_NEEDED`
Use when:
- additional human input, experiment design, or domain interpretation is required
- or current evidence is not sufficient to confidently pick one causal direction

### Must not do
- do not label something `correct_rca` when only the crash surface is known
- do not collapse `BLOCKED` and `HELP_NEEDED`

### Exit condition
A final state label and supporting summary are produced.

---

## 4. Mandatory exit conditions / gates between steps

The v2 chain must not skip important intermediate products. These gates are required.

### Gate A — Step 1 -> Step 2
Must have:
- enough Jira context to identify which artifacts matter

### Gate B — Step 2 -> Step 3
Must have:
- local access to at least the key artifacts for first-pass analysis

### Gate C — Step 3 -> Step 4
Must have:
- a primary failure signature or equivalent high-value crash surface

### Gate D — Step 4 -> Step 5
Must have:
- at least one meaningful KB grounding result, or an explicit “weak/no KB grounding” note

### Gate E — Step 5 -> Step 6
Must have:
- one main possible failure reason / hypothesis

### Gate F — Step 6 -> Step 7 / Step 8
Must have:
- DEBUG_STEPS that clearly separate device-side evidence actions from code-side evidence actions

### Gate G — Step 7 / Step 8 -> Step 9
Must have:
- at least one real evidence update from either device-side or code-side follow-up

### Gate H — Step 9 -> Step 10
Must have:
- evidence-grounded summary
- confidence statement
- unresolved gap statement

---

## 5. What DEBUG_STEPS should mean in v2

In v2, `DEBUG_STEPS` is explicitly **not** the endpoint.

It must be treated as:
- an execution plan derived from a current hypothesis
- a plan that is meant to drive subsequent evidence collection
- an intermediate artifact that can later be corrected or superseded

So the mental model should be:

`signature -> KB grounding -> possible failure reason -> DEBUG_STEPS -> evidence execution -> evidence summary -> terminal state`

not:

`signature -> KB grounding -> DEBUG_STEPS -> stop`

---

## 6. What v2 must emphasize that v1 still misses

### 6.1 Explicit hypothesis phase
v2 must include Step 5 as a first-class phase.
This is the most important structural correction relative to v1.

### 6.2 Post-plan evidence execution
v2 must include:
- Step 7 `device_evidence_fetch`
- Step 8 `code_evidence_fetch`

Without these, DEBUG_STEPS will remain an endpoint artifact rather than a debugging tool.

### 6.3 Evidence-based closure
v2 must include:
- Step 9 `summarize_issue_with_evidence`
- Step 10 `correct_rca / BLOCKED / HELP_NEEDED`

Without this, the system cannot distinguish between:
- provisional understanding
- real evidence-supported correction
- blocked investigation
- need for human help

---

## 7. Implementation guidance for v2

A practical implementation order is:

### Batch 1
- introduce Step 5 `provide_possible_failure_reason`
- introduce Step 10 terminal-state classification

### Batch 2
- introduce Step 7 `device_evidence_fetch`
- introduce Step 8 `code_evidence_fetch`

### Batch 3
- introduce Step 9 evidence-integrated second-pass summary
- refine budgets, state machine, and output policies around the full ten-step flow

Reason:
- Batch 1 fixes the most important structural defect in current output quality
- Batch 2 makes DEBUG_STEPS operational
- Batch 3 closes the evidence loop

---

## 8. Naming note

This file is named `requirement_v2.md` because the next-stage need is larger than a prompt tweak or workflow adjustment. It is a design-level requirement document for the next generation of `simple-rla`.
