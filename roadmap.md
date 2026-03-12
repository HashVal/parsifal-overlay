# Roadmap: simple-rla → KB-aware DEBUG_STEPS generator

## Background

Current `simple-rla` can already:

- fetch Jira issues and comments
- list/fetch Jira attachments
- store per-run workspaces under `artifacts_root`
- persist per-iteration LLM dumps with `--dump`
- hold multi-turn tool-augmented conversations with an LLM

This is enough for a **Jira-aware RCA assistant**, but not yet enough for a **spec-aligned DEBUG_STEPS generator** as defined in `parsifal-doc`.

The target spec expects `DEBUG_STEPS` to be a structured, iterative debug plan with:

- normalized platform target
- kernel fingerprint
- KB hits
- explicit hypotheses
- code checks
- device checks
- budget and stop conditions

So the next milestone is not “add more chat”, but:

> turn `simple-rla` into a KB-aware structured plan generator for `DEBUG_STEPS`.

---

## Current capability vs. missing inputs

### Already available

- Jira issue metadata (`jira_get`, `jira_search`)
- Jira attachment discovery and download
- compact log previews from attachments
- run workspace layout (`meta.json`, `session.log`, `attachments/`, `dumps/`)
- multi-round LLM orchestration

### Missing or weak inputs

1. **KB retrieval / kb_hits**
   - no tool yet to search `parsifal-doc/kb/`
   - no way to ground hypotheses in prior patterns

2. **Platform normalization**
   - no extraction of `<soc>/<board>/<sku>` from Jira text/logs/comments

3. **Kernel fingerprint extraction**
   - no structured extraction of `repo`, `branch`, `commit`, `localversion`, `dtb`

4. **Evidence extraction from logs / attachments**
   - attachments can be downloaded, but not yet turned into structured signatures or evidence snippets

5. **Code-side context tools**
   - no code search / git inspection / repo-aware lookup yet
   - limits specificity of `code_check`

6. **Device-side execution context**
   - no ssh / serial / device command tool surface yet
   - limits realism of `device_check`

---

## Milestone strategy

We should build this in three layers:

1. **Grounding layer**: KB retrieval + target extraction + evidence extraction
2. **Planning layer**: generate a first valid `DEBUG_STEPS` artifact
3. **Execution layer**: add code/device toolchains to make next rounds stronger

---

# Milestone 0 — Stabilized Jira-driven RCA loop ✅

Already achieved in current branch:

- Jira auth aligned to target environment
- clearer Jira diagnostics
- compact Jira MCP outputs
- Jira attachment MCP tools
- per-run workspace
- integrated dump outputs

This milestone is the prerequisite for all following work.

---

# Milestone 1 — KB-aware grounding for DEBUG_STEPS

## Goal

Give the agent enough structured inputs to produce a **credible first-round DEBUG_STEPS** instead of a generic checklist.

## Scope

### 1. KB retrieval tool(s)

Add MCP/tooling support to search `parsifal-doc/kb/`.

Expected capability:
- keyword search by Jira summary / log signature / subsystem hints
- return top matching KB entries
- expose stable references like `kb/<subsystem>/<pattern_id>.md`

Minimum acceptable output:
- path
- title / frontmatter summary
- match reason / snippet

Why this matters:
- fills `inputs.kb_hits`
- grounds `hypotheses[*].why`
- prevents “blank-slate planning”

---

### 2. Platform normalization

Add logic to infer and normalize:

```text
platform = <soc>/<board>/<sku>
```

Input sources:
- Jira summary
- description preview
- comments
- attachment previews
- labels/components

Output:
- one or more normalized platform candidates
- confidence / source trace (optional but useful)

Why this matters:
- fills `target.platform`
- improves KB matching
- improves future bucketization

---

### 3. Kernel fingerprint extraction

Add structured extraction for:
- `repo`
- `branch`
- `commit`
- `localversion`
- `dtb`

Input sources:
- Jira text/comments
- attachment previews
- known kernel naming conventions in logs

Why this matters:
- fills `target.kernel`
- gives reproducibility to DEBUG_STEPS
- aligns with the spec’s emphasis on fingerprints rather than vague version labels

---

### 4. Log/evidence extraction

Add a lightweight evidence extractor over downloaded attachment previews.

Expected outputs:
- likely subsystem
- key error signature(s)
- a few short evidence lines/snippets
- candidate hypothesis cues

Why this matters:
- gives structure to `why` / `prove` / `disprove`
- improves debug plan specificity

---

## Deliverable for Milestone 1

A new internal data bundle (does not have to be final user-visible format yet) that can produce:

- `bug`
- `target`
- `inputs.kb_hits`
- initial evidence cues
- initial hypothesis seeds

This is the minimum viable grounding set for first-round `DEBUG_STEPS` generation.

---

# Milestone 2 — First-round DEBUG_STEPS generation

## Goal

Generate a first valid, spec-aligned `DEBUG_STEPS` artifact from Jira + KB + log inputs.

## Scope

### 1. Implement DEBUG_STEPS generator

The generator should emit all major fields expected by the spec/template:

- `debug_steps_id`
- `jira_key`
- `created_at`
- `round`
- `bug`
- `target`
- `inputs`
- `budget`
- `hypotheses`
- `code_check`
- `device_check`
- `stop_conditions`
- `notes`

The first version can remain conservative:
- `device_check.target` may default to `log-only`
- `risk` may default to `read-only`
- `code_check` may be heuristic if code tools are not yet available

---

### 2. Render human-readable DEBUG_STEPS artifact

Output should align with `parsifal-doc/templates/DEBUG_STEPS.md`:
- machine-friendly frontmatter
- human-friendly markdown body

This is important because the spec explicitly wants a dual-use artifact.

---

### 3. Optional validation step

Validate generated output against:
- `parsifal-doc/schemas/debug_steps.schema.json`

This can initially be best-effort, but should become standard quickly.

---

## Deliverable for Milestone 2

A command or tool path that can take a Jira issue and produce a valid first-round `DEBUG_STEPS` document in the run workspace.

For example:

```text
<run_workspace>/DEBUG_STEPS.md
```

Potentially also a JSON sidecar if needed.

---

# Milestone 3 — Better execution inputs for round 2+

## Goal

Make subsequent rounds of DEBUG_STEPS sharper and less generic by adding execution-side context.

## Scope

### 1. Code-side tools

Add tool support for:
- repo grep/search
- file reads/snippets
- git log / blame / path history
- maybe mapping subsystem ↔ paths

Why this matters:
- upgrades `code_check.actions` from generic to issue-specific
- helps prove/disprove hypotheses from code reality

---

### 2. Device-side tools

Add tool support for:
- ssh read-only commands
- serial log reads
- log collection
- maybe structured device probes

Why this matters:
- upgrades `device_check` from `log-only` to actual directed validation
- supports spec terminal states like `RESOLVED_RCA`

---

### 3. Stable evidence references

Introduce stable refs for:
- Jira comments
- attachments
- downloaded logs
- dump iterations
- code snippets

Why this matters:
- required for later `KEY_EVIDENCE`
- improves auditability and machine-readable JIRA comments

---

## Deliverable for Milestone 3

A round-2+ capable loop where DEBUG_STEPS can evolve based on actual code/device evidence instead of Jira text only.

---

# Milestone 4 — KEY_EVIDENCE and RCA convergence

## Goal

Close the loop from planning to evidence-backed RCA output.

## Scope

- generate `KEY_EVIDENCE.md`
- map claims → minimal evidence excerpts + refs
- decide terminal states:
  - `RESOLVED_RCA`
  - `NEED_MORE_INFO`
  - `BLOCKED`
- prepare JIRA comment output using `templates/jira-comment.txt`

This milestone depends on stable evidence refs and enough execution-side evidence.

---

# Priority order

## P0 (must-have before good DEBUG_STEPS)
1. KB retrieval
2. Platform normalization
3. Kernel fingerprint extraction
4. Log/evidence extraction

## P1 (needed for stronger plan quality)
5. First-round DEBUG_STEPS generator
6. Schema/template-aligned rendering
7. Validation against schema

## P2 (needed for iterative RCA strength)
8. Code-side tools
9. Device-side tools
10. Stable evidence reference system

## P3 (full workflow closure)
11. KEY_EVIDENCE generation
12. JIRA comment / state transition loop

---

# Recommended next implementation step

If we want the highest leverage next step, do this first:

## Next step recommendation

Build a **KB retrieval + target extraction layer** before writing the first DEBUG_STEPS generator.

Reason:
- without KB hits and normalized target/kernel info, generated DEBUG_STEPS will be shallow and generic
- with those inputs, even a simple generator can already produce useful first-round plans

Concretely, the next deliverable should be:

- one or more tools/modules that return:
  - `kb_hits`
  - normalized `platform`
  - structured `kernel fingerprint`
  - extracted evidence/signatures from Jira logs

Once this exists, generating `DEBUG_STEPS` becomes an integration task instead of a guessing task.

---

# Non-goals for the immediate next step

Do **not** do these first:

- add OAuth support to Jira
- redesign MCP transport
- make device execution autonomous before grounding inputs exist
- generate KEY_EVIDENCE before DEBUG_STEPS grounding is solid

---

# Success criteria

We can say the roadmap is on track when:

1. A Jira issue can be turned into a structured grounding bundle
2. That bundle can generate a valid first-round `DEBUG_STEPS`
3. The generated plan is specific enough to mention:
   - likely subsystem(s)
   - plausible hypotheses
   - concrete code checks
   - safe device/log checks
4. The plan clearly states stop conditions and next-round expectations
