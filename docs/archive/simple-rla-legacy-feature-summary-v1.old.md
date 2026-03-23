# simple_rla feature summary v1

This document summarizes the current `simple-rla` implementation status as a v1 prototype: what it can do today, how complete each module is, what has already been validated in real runs, and what special hints/limitations matter when using or extending it.

---

## 1. Project positioning

`simple-rla` is currently a **grounded kernel-RCA runloop prototype**.

Its current strength is not “final RCA automation,” but the combination of:
- Jira case intake
- artifact download and workspace organization
- local log/file inspection
- lightweight KB grounding
- provisional DEBUG_STEPS generation
- iteration dumps and observability logs for debugging the runloop itself

The current system is best described as:

> a practical v1 for **case intake + artifact grounding + provisional debug-plan drafting**

It is **not yet** a full evidence-closure system that can reliably execute debug steps, fetch new device/code evidence, and converge to a corrected RCA.

---

## 2. What v1 can do today

### 2.1 Jira case access
Implemented and validated:
- `jira_search`
- `jira_get`
- `jira_list_attachments`
- `jira_fetch_attachment`
- `jira_comment`
- `jira_transitions`
- `jira_transition`

Current status:
- good enough for issue lookup and attachment-driven debugging
- auth semantics improved and documented
- compact Jira outputs already implemented to avoid runloop stdio blowups

Validated behavior:
- bearer auth works with `JIRA_TOKEN`
- basic auth works with `JIRA_USER:JIRA_PASSWORD`
- default API prefix is `/rest/api/latest`
- HTML login / auth failures are surfaced more clearly than before

Special hint:
- do **not** rely on `JIRA_USER:JIRA_TOKEN` for basic auth in this environment

---

### 2.2 Attachment handling
Implemented and validated:
- Jira attachments can be listed and downloaded as separate MCP tools
- downloaded attachments are stored under the per-run workspace
- text attachment previews are intentionally thinned for runloop use
- path policy prevents the model from arbitrarily placing downloads under `/tmp`

Current status:
- stable enough for runloop use
- much better than the earlier “large preview stuffed into context” design

Special hint:
- attachment tools are intentionally designed to dump files locally and return references, not to inline full content into model context

---

### 2.3 Local file/log inspection
Implemented and validated:
- `file_head`
- `file_tail`
- `file_read_range`
- `file_grep`
- `log_extract_signatures`
- `log_compare`

Current status:
- this is one of the most useful parts of v1
- read-only server with allowed-root enforcement
- good observability logs already added
- strong enough for artifact-first triage

Most important capability:
- `log_extract_signatures(profile="kernel")` can extract:
  - essential boot context
  - fatal clusters
  - primary crash headline
  - trace anchor
  - supporting errors
  - dominant failure mode

Known improvement already made:
- fatal clustering now preserves both:
  - crash headline
  - trace anchor

Special hint:
- raw file-tool outputs are useful for dumps/debugging, but too heavy for LLM context unless compacted first

---

### 2.4 Knowledge base grounding
Implemented and validated:
- KB source under `simple-rla/knowledge_base/`
- YAML-first authoring
- `kb_get`
- `kb_search`
- `kb_ground`
- lightweight platform taxonomy mapping in `kb_server.py`
- `PyYAML`-based loading (`yaml.safe_load`)

Current KB content includes:
- BIOS display mode note
- driver platform mapping notes (`xe`, `i915`)
- example issue/code/platform notes
- additional knowledge items added for current graphics cases

Current status:
- retrieval/grounding works
- `kb_ground` can already return useful matched objects for real cases
- still relatively small and manually curated

Validated real behavior:
- `kb_ground` can match issue patterns, platform notes, and code notes relevant to current Xe/GEM crash scenarios

Known limitations:
- ranking/noise is still imperfect
- query construction from runtime signals can still be improved
- some returned hits are useful but not always ideally prioritized

Special hint:
- KB is currently strongest as a **grounding layer**, not as an autonomous reasoning layer

---

### 2.5 Runloop orchestration
Implemented in practice:
- `fc_runloop.py` as the main working path for function-calling + MCP tools
- workflow-driven prompts via `workflow.yaml`
- phase/budget/repeat guards via `runloop_control.py`
- per-run workspace support
- incomplete dump capture on request-layer failures
- forced-draft mode for late-stage summarization

Current v1 phase model (as implemented today):
- case identification
- evidence collection
- artifact inspection
- KB grounding
- draft_debug_steps

Recent improvements already landed:
- text attachment preview slimming
- artifact-inspection to KB-grounding progression
- KB phase final-exit gate
- auto-run KB grounding from file signals
- LLM-facing compact views for `log_extract_signatures` and `kb_ground`

Current status:
- the runloop now works much more reliably than earlier iterations
- context blowups were reduced significantly by compacting file/KB tool outputs before sending them back to the model
- phase progression is now much more controllable than the original free-form loop

Still true:
- v1 still stops too early from the perspective of full debugging closure
- the current chain still ends around provisional DEBUG_STEPS drafting
- there is not yet a robust post-plan evidence-execution loop

---

## 3. Current module-by-module implementation status

### 3.1 `runloop_agent/fc_runloop.py`
Role:
- main orchestration loop for chat-completions + MCP tools

Status:
- **usable v1 core**

What it already does well:
- builds and maintains conversation history
- invokes MCP tools
- dumps iterations
- manages phase transitions
- auto-runs KB grounding when entering KB phase
- compacts large tool outputs before feeding them back to the model
- logs payload size for context debugging

Known limitations:
- still centered on “provisional DEBUG_STEPS as main output”
- no dedicated post-plan `device_evidence_fetch` or `code_evidence_fetch` phase yet
- still vulnerable to model quality issues in final synthesis

---

### 3.2 `runloop_agent/runloop_control.py`
Role:
- phase model, budgets, repeat guards, forced-draft rules

Status:
- **good control-plane prototype**

What is implemented:
- phase budgets by tool family
- anti-repeat guard
- KB-before-draft reservation logic
- forced-draft gating
- KB grounding exit guard

Known limitations:
- the current phase model is still shorter than the desired next-generation 10-step chain
- `provide_possible_failure_reason` is not yet an explicit phase
- post-DEBUG_STEPS evidence collection is not represented yet

---

### 3.3 `runloop_agent/workflow.yaml`
Role:
- workflow prompt and execution defaults

Status:
- **usable but transitional**

Current strengths:
- already improved compared with the original broad/loose prompt
- emphasizes phased work, lightweight KB grounding, and provisional DEBUG_STEPS

Known limitations:
- still optimized for the current shorter chain
- not yet rewritten around the newer 10-step closed-loop design

---

### 3.4 `mcp_servers/jira_server.py`
Role:
- Jira MCP surface

Status:
- **strong v1 module**

Strengths:
- compact outputs
- attachment dumping
- clearer diagnostics
- improved auth semantics

Known limitations:
- still only the intake/evidence source layer, not a reasoning layer

---

### 3.5 `mcp_servers/file_tools_server.py`
Role:
- local file/log inspection MCP surface

Status:
- **strong v1 module**

Strengths:
- highly useful in real runs
- read-only and workspace-bounded
- kernel log signature extraction now much more usable than early versions

Known limitations:
- raw outputs are rich but can still be semantically noisy for downstream planning unless compacted

---

### 3.6 `mcp_servers/kb_server.py`
Role:
- local KB retrieval/grounding server

Status:
- **functional v1 module**

Strengths:
- useful retrieval surface exists
- `kb_ground` works well enough to assist real cases
- standard YAML parsing is now in place

Known limitations:
- retrieval ranking still needs improvement
- KB content breadth is still limited
- missing imports/content bugs can still appear when new retrieval paths get exercised for the first time

---

## 4. Special hints for using v1

### 4.1 Treat v1 as a grounded planning system, not a final RCA engine
The best current use of v1 is:
- fetch the case
- ground on artifacts
- identify likely failure signatures
- bring in KB context
- produce a provisional debugging plan

It is not yet strong enough to be trusted as a one-shot corrected RCA generator.

---

### 4.2 Device-side comparison evidence is extremely valuable
If you already know facts like:
- removing `modprobe.blacklist=i915` and `xe.force_probe=*` makes the system boot normally

then that evidence should be treated as a primary clue.

This kind of evidence is more valuable than many generic boot-log errors and should shape the hypothesis and debug steps.

---

### 4.3 Crash site is not automatically root cause origin
Current v1 can identify crash sites well.
It is still easier for the system to reason from:
- `drm_gem_private_object_init`
- `kernel BUG at drm_gem.c:181`

than from a richer causal chain involving:
- BIOS mode
- resource/BAR exposure
- driver ownership
- forced probe path

When reviewing v1 output, always check whether it has mistaken:
- failure endpoint
for
- cause origin.

---

### 4.4 Keep raw evidence for humans, compact evidence for LLM context
This principle now appears in multiple places in v1 and should be preserved:
- raw attachments stay on disk
- raw file/KB tool output stays in dumps/logs
- LLM-facing payloads should remain compact

This is essential for keeping the runloop usable under a 16k context limit.

---

### 4.5 Current v1 output quality depends heavily on chain design
A better chain matters more than a prettier prompt.

The most important current architectural gap is that the system still effectively ends at:
- provisional DEBUG_STEPS

What it still lacks is a clean follow-up loop for:
- possible failure reason / hypothesis
- device evidence fetch
- code evidence fetch
- evidence-based correction
- final state classification

---

## 5. What v1 is missing

The most important missing capabilities are:

### 5.1 Explicit hypothesis phase
Current v1 has:
- signature extraction
- KB grounding
- DEBUG_STEPS drafting

But it does not yet have a dedicated:
- `provide_possible_failure_reason`

This is one of the main reasons draft quality can still be structurally wrong.

---

### 5.2 Post-plan evidence execution
Current v1 does not yet continue with:
- `device_evidence_fetch`
- `code_evidence_fetch`

This means `DEBUG_STEPS` is still treated too much like an endpoint rather than a plan for subsequent evidence collection.

---

### 5.3 Evidence-integrated correction phase
Current v1 has no robust second-pass synthesis step equivalent to:
- `summarize_issue_with_evidence`
- `correct_rca / BLOCKED / HELP_NEEDED`

So the system still lacks a clean “closure” stage.

---

## 6. Practical summary

### What v1 is good at
- Jira intake
- attachment download
- artifact-first log triage
- KB grounding
- provisional debug-plan drafting
- runloop observability and iteration debugging

### What v1 is not yet good at
- explicit mechanism-hypothesis generation
- collecting new device/code evidence after planning
- evidence-closure and corrected RCA convergence
- robust final-state classification

### Best label for current maturity
`simple_rla v1` is best described as:

> a grounded RCA planning prototype with strong artifact tooling and early KB integration, but without a full hypothesis-to-evidence-to-correction closure loop yet.
