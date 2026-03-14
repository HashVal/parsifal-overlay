# KB MCP Tools Design Notes

This document records the current design direction for KB-facing MCP tools in `simple-rla`.

Current decision status:
- KB authoring/source format: YAML-first
- KB source layout: `simple-rla/knowledge_base/`
- Current approved direction for tool surface: **Option B**
  - Aggregation is allowed
  - Over-reasoning is not

In other words:

> `kb_ground` may aggregate and organize KB context for a case, but it should not become a black-box reasoning engine that directly decides final root cause.

---

## Tool surface direction

The current preferred direction is:

- `kb_search`
- `kb_get`
- `kb_ground`

However, the first concretely discussed tool is `kb_ground`.
This tool is intended to sit between raw case evidence and downstream planning / grounding consumers.

Its role is:
- accept structured case context and signals
- perform constrained KB retrieval
- organize lightweight matched KB context
- return a grounding-oriented package

Its role is **not**:
- produce final root cause conclusions
- replace the agent's reasoning
- directly generate final `DEBUG_STEPS`

---

## Design principle for `kb_ground`

Approved principle:

> aggregation can be done; reasoning should not go too far.

Practical interpretation:

- the tool may group and rank relevant KB objects
- the tool may expose matched signals and focus areas
- the tool may suggest which KB objects are worth reading next
- the tool should not present itself as the final decider of truth

---

## `kb_ground` input schema (draft)

The current draft input structure is:

```json
{
  "context": { ... },
  "signals": [ ... ],
  "hints": { ... },
  "limits": { ... }
}
```

This is intentionally **structured-context first, free-text second**.

### Why

`kb_ground` is meant to consume already-extracted case context/signals, not raw logs or long unstructured dumps.

---

## 1) `context`

`context` describes the current case at a lightweight structured level.

Draft shape:

```json
{
  "case_id": "PKT-20231",
  "title": "Kernel panic when enabling Integrated or Hybrid mode on BMG platform",
  "summary": "Kernel BUG at drm_gem.c:181 during Xe initialization",
  "platforms": ["BMG"],
  "subsystems": ["xe", "drm", "gem"],
  "modes": ["hybrid", "integrated"],
  "environment": {
    "kernel_version": "6.14-intel",
    "cmdline": [
      "xe.force_probe=*",
      "modprobe.blacklist=i915",
      "xe.max_vfs=7"
    ]
  }
}
```

### Notes

- `case_id`: optional but useful for traceability
- `title`: lightweight framing from Jira or equivalent source
- `summary`: short case abstraction, not a long narrative
- `platforms`: structured array, even if a single platform
- `subsystems`: structured array
- `modes`: structured array
- `environment`: keep small and high-signal only

---

## 2) `signals`

`signals` are the core input to `kb_ground`.

Draft shape:

```json
[
  { "type": "log_pattern", "value": "kernel BUG at drivers/gpu/drm/drm_gem.c:181!" },
  { "type": "function", "value": "drm_gem_private_object_init" },
  { "type": "function", "value": "xe_lrc_create" },
  { "type": "function", "value": "xe_bo_create_pin_map_novm" },
  { "type": "file", "value": "drivers/gpu/drm/drm_gem.c" },
  { "type": "module", "value": "xe" },
  { "type": "config", "value": "xe.force_probe=*" }
]
```

### Rationale

`kb_ground` should consume structured evidence directly rather than forcing the model to restate it as natural-language search queries.

### Proposed `signal.type` values (initial draft)

- `log_pattern`
- `symptom`
- `function`
- `file`
- `module`
- `config`
- `platform`
- `mode`
- `component`

### Guidance

- `signals` should be the main retrieval driver
- a typical call should provide around 2-8 useful signals
- avoid sending large raw excerpts as signal values

---

## 3) `hints`

`hints` provide weak caller preferences.
They are not meant to dominate the retrieval process.

Draft shape:

```json
{
  "preferred_kinds": ["issue_pattern", "rca", "code_note", "platform_note"],
  "exclude_ids": ["rca-pkt-20231-current"],
  "focus": [
    "shared hybrid/integrated failure path",
    "gem object initialization"
  ]
}
```

### Notes

- `preferred_kinds`: optional bias toward KB object kinds
- `exclude_ids`: useful to avoid returning the current case object when inappropriate
- `focus`: lightweight natural-language hints; should not override structured evidence

---

## 4) `limits`

`limits` control output thickness.
This is important to avoid producing over-large grounding payloads.

Draft shape:

```json
{
  "max_total_hits": 6,
  "max_hits_per_kind": 2,
  "include_kinds": ["issue_pattern", "rca", "platform_note", "code_note"],
  "include_snippets": true
}
```

### Notes

- `max_total_hits`: cap total returned KB objects
- `max_hits_per_kind`: prevent a single kind from dominating the result
- `include_kinds`: optional explicit allowlist
- `include_snippets`: whether lightweight text evidence should be returned

---

## Complete example input

```json
{
  "context": {
    "case_id": "PKT-20231",
    "title": "Kernel panic when enabling Integrated or Hybrid mode on BMG platform",
    "summary": "Kernel BUG at drm_gem.c:181 during Xe initialization",
    "platforms": ["BMG"],
    "subsystems": ["xe", "drm", "gem"],
    "modes": ["hybrid", "integrated"],
    "environment": {
      "kernel_version": "6.14-intel",
      "cmdline": [
        "xe.force_probe=*",
        "modprobe.blacklist=i915",
        "xe.max_vfs=7"
      ]
    }
  },
  "signals": [
    { "type": "log_pattern", "value": "kernel BUG at drivers/gpu/drm/drm_gem.c:181!" },
    { "type": "function", "value": "drm_gem_private_object_init" },
    { "type": "function", "value": "xe_lrc_create" },
    { "type": "function", "value": "xe_bo_create_pin_map_novm" },
    { "type": "file", "value": "drivers/gpu/drm/drm_gem.c" },
    { "type": "module", "value": "xe" },
    { "type": "config", "value": "xe.force_probe=*" }
  ],
  "hints": {
    "preferred_kinds": ["issue_pattern", "rca", "code_note", "platform_note"],
    "focus": [
      "shared hybrid/integrated failure path",
      "gem object initialization"
    ]
  },
  "limits": {
    "max_total_hits": 6,
    "max_hits_per_kind": 2,
    "include_snippets": true
  }
}
```

---

## What `kb_ground` should do with this input

The intended behavior is:

1. use `context.platforms`, `context.subsystems`, `context.modes` as structured retrieval constraints
2. use `signals` as the main matching/ranking material
3. use `hints` only as weak bias
4. obey `limits` strictly
5. return a lightweight grounding package rather than a final diagnosis

---

## What `kb_ground` should not do

The tool should **not**:

- infer and declare the final root cause as if it were authoritative
- replace the model's reasoning layer
- emit overly thick full-document payloads
- consume raw logs as its primary input format

---

## `kb_ground` output schema (draft)

The current recommended output direction is a **lightweight grounding package**.

It should be:
- structured
- typed
- explainable
- suitable for downstream planning
- small enough to avoid blowing up context

It should **not** be:
- a final RCA verdict
- a black-box reasoning result
- a full dump of KB document bodies

### Draft top-level shape

```json
{
  "query_context": { ... },
  "matched_objects": { ... },
  "focus_areas": [ ... ],
  "open_questions": [ ... ],
  "recommended_next_reads": [ ... ]
}
```

---

## 1) `query_context`

`query_context` should echo the normalized context/signals actually used by the tool.
This improves explainability and makes debugging retrieval decisions easier.

Draft shape:

```json
{
  "case_id": "PKT-20231",
  "platforms": ["BMG"],
  "subsystems": ["xe", "drm", "gem"],
  "modes": ["hybrid", "integrated"],
  "signals": [
    { "type": "log_pattern", "value": "kernel BUG at drivers/gpu/drm/drm_gem.c:181!" },
    { "type": "function", "value": "drm_gem_private_object_init" },
    { "type": "function", "value": "xe_lrc_create" }
  ]
}
```

### Notes

- This is not merely input echo; it may contain normalized/filtered signals actually used for retrieval.
- Useful for debugging ranking behavior and grounding quality.

---

## 2) `matched_objects`

`matched_objects` should return grouped KB hits by kind.
This is one of the main advantages of the `kb_ground` direction: the server may present a type-balanced set of relevant hits.

Draft shape:

```json
{
  "issue_patterns": [ ... ],
  "rcas": [ ... ],
  "platform_notes": [ ... ],
  "code_notes": [ ... ],
  "playbooks": [ ... ],
  "workarounds": [ ... ]
}
```

Each hit should stay lightweight.

### Draft hit shape

```json
{
  "id": "issue-pattern-bmg-xe-gem-private-object-init",
  "kind": "issue_pattern",
  "title": "BMG Xe GEM private object initialization BUG during LRC creation",
  "score": 0.93,
  "matched_signals": [
    "kernel BUG at drivers/gpu/drm/drm_gem.c:181!",
    "drm_gem_private_object_init",
    "xe_lrc_create"
  ],
  "summary": "On BMG platforms ...",
  "snippets": [
    "...kernel BUG in drm_gem_private_object_init...",
    "...call trace containing xe_lrc_create..."
  ],
  "refs": [
    { "type": "jira", "value": "PKT-20231" },
    { "type": "code", "value": "drivers/gpu/drm/drm_gem.c:181" }
  ]
}
```

### Notes

- `score` is retrieval-side relevance, not truth confidence.
- `matched_signals` should explain why the object was selected.
- `summary` should be short and high-signal.
- `snippets` should stay lightweight and optional.
- `refs` should be short references, not full document payloads.

### Required vs optional fields for a matched hit

Current recommended split:

#### Required
- `id`
- `kind`
- `title`
- `matched_signals`
- `summary`

#### Optional
- `score`
- `snippets`
- `refs`

### Rationale

The required set is intended to form the minimum viable grounding hit:
- `id`: stable identity and future retrieval target
- `kind`: self-describing type information
- `title`: fast human/model recognition
- `matched_signals`: explain why the object was selected
- `summary`: provide minimum useful semantics without forcing an immediate full fetch

The optional set is useful but not required for the first workable version:
- `score`: helpful for ranking/debugging, but not strictly required if ordering is already stable
- `snippets`: helpful evidence preview, but may be omitted to keep payloads small
- `refs`: helpful for traceability, but not required for minimal usability

---

## 3) `focus_areas`

`focus_areas` are lightweight retrieval-derived areas worth paying attention to.
They are not meant to be a final diagnosis.

Draft shape:

```json
[
  "drm_gem_private_object_init invariants",
  "Xe LRC creation path",
  "shared Hybrid/Integrated initialization path"
]
```

### Notes

- These should be phrased as investigation focus areas, not authoritative conclusions.
- They may be derived from overlap between matched signals and matched KB object themes.

---

## 4) `open_questions`

`open_questions` should expose unresolved areas surfaced by the matched KB context.
This helps downstream planning and DEBUG_STEPS generation.

Draft shape:

```json
[
  "Is the GEM object malformed before drm_gem_private_object_init is called?",
  "Does tile or GT fusion state influence object setup in both modes?"
]
```

### Notes

- These should stay explicitly uncertain.
- They are useful for planning next checks without pretending the KB already answered everything.

---

## 5) `recommended_next_reads`

`recommended_next_reads` should point to the next KB objects worth expanding via future tools like `kb_get`.

Draft shape:

```json
[
  "issue-pattern-bmg-xe-gem-private-object-init",
  "code-note-drm-gem-private-object-init-example"
]
```

### Notes

- These are IDs, not heavy inline content.
- This field supports a lightweight-search / detailed-get workflow.

---

## Complete example output

```json
{
  "query_context": {
    "case_id": "PKT-20231",
    "platforms": ["BMG"],
    "subsystems": ["xe", "drm", "gem"],
    "modes": ["hybrid", "integrated"],
    "signals": [
      { "type": "log_pattern", "value": "kernel BUG at drivers/gpu/drm/drm_gem.c:181!" },
      { "type": "function", "value": "drm_gem_private_object_init" },
      { "type": "function", "value": "xe_lrc_create" }
    ]
  },
  "matched_objects": {
    "issue_patterns": [
      {
        "id": "issue-pattern-bmg-xe-gem-private-object-init",
        "kind": "issue_pattern",
        "title": "BMG Xe GEM private object initialization BUG during LRC creation",
        "score": 0.93,
        "matched_signals": [
          "kernel BUG at drivers/gpu/drm/drm_gem.c:181!",
          "drm_gem_private_object_init",
          "xe_lrc_create"
        ],
        "summary": "On BMG platforms, Hybrid or Integrated mode may trigger a kernel BUG in drm_gem_private_object_init during Xe bring-up.",
        "snippets": [
          "...kernel BUG in drm_gem_private_object_init...",
          "...call trace containing xe_lrc_create..."
        ],
        "refs": [
          { "type": "jira", "value": "PKT-20231" },
          { "type": "code", "value": "drivers/gpu/drm/drm_gem.c:181" }
        ]
      }
    ],
    "rcas": [
      {
        "id": "rca-pkt-20231-example",
        "kind": "rca",
        "title": "PKT-20231 BMG Hybrid/Integrated boot panic during Xe initialization",
        "score": 0.88,
        "matched_signals": [
          "BMG",
          "hybrid",
          "integrated"
        ],
        "summary": "Concrete case instance showing the same drm_gem_private_object_init BUG signature during boot.",
        "snippets": [
          "...Hybrid and Integrated dmesg both hit the same BUG..."
        ],
        "refs": [
          { "type": "jira", "value": "PKT-20231" }
        ]
      }
    ],
    "platform_notes": [
      {
        "id": "platform-note-bmg-hybrid-integrated-modes-example",
        "kind": "platform_note",
        "title": "BMG Hybrid and Integrated mode terminology reference",
        "score": 0.72,
        "matched_signals": ["BMG", "hybrid", "integrated"],
        "summary": "Defines mode terminology and reminds the reader not to confuse mode-specific symptoms with mode-specific root cause.",
        "snippets": [],
        "refs": []
      }
    ],
    "code_notes": [
      {
        "id": "code-note-drm-gem-private-object-init-example",
        "kind": "code_note",
        "title": "drm_gem_private_object_init semantic note",
        "score": 0.9,
        "matched_signals": ["drm_gem_private_object_init"],
        "summary": "Explains why this function is a choke point where caller-side invariant violations may surface.",
        "snippets": [
          "...inspect both the direct caller and object construction path..."
        ],
        "refs": [
          { "type": "code", "value": "drivers/gpu/drm/drm_gem.c" }
        ]
      }
    ],
    "playbooks": [],
    "workarounds": []
  },
  "focus_areas": [
    "drm_gem_private_object_init invariants",
    "Xe LRC creation path",
    "shared Hybrid/Integrated initialization path"
  ],
  "open_questions": [
    "Is the GEM object malformed before drm_gem_private_object_init is called?",
    "Does tile or GT fusion state influence object setup in both modes?"
  ],
  "recommended_next_reads": [
    "issue-pattern-bmg-xe-gem-private-object-init",
    "code-note-drm-gem-private-object-init-example"
  ]
}
```

---

## Output behavior principles

The output should:
- stay lightweight
- preserve type separation
- explain why hits were selected
- help downstream planning
- make follow-up `kb_get`-style retrieval possible

The output should not:
- claim final authoritative truth
- emit long full-text KB entries
- collapse into a black-box root cause generator

---

## Type-balance strategy for `kb_ground` (current recommendation)

The current recommended balance policy is:

> type balance is a target mix, not a hard quota.

This means `kb_ground` should try to return a useful spread of KB kinds, but it should never force low-quality objects into the result just to fill a bucket.

### Practical principles

1. **soft target, not hard quota**
   - the tool should prefer a balanced result shape
   - the tool should not require every kind to appear

2. **quality-gated selection**
   - a kind should participate in balanced selection only if it has sufficiently relevant candidates
   - if a bucket has no strong hit, it should be treated as empty for that request

3. **lightweight platform taxonomy should be applied during matching**
   - generic platform notes should remain retrievable from specific platform contexts
   - for example, a case carrying `BMG` should still be able to match KB objects tagged with `generic_x86_platforms`
   - this mapping should stay lightweight and explicit rather than turning into a large hidden ontology in the first implementation

4. **empty buckets are normal**
   - `matched_objects.issue_patterns`, `matched_objects.rcas`, etc. may legitimately be empty arrays
   - an empty bucket is better than filling the result with weak or misleading hits

5. **unused quota should flow to stronger kinds**
   - if one kind has no acceptable hit, remaining budget may be used by other kinds with stronger matches

6. **coverage gaps should be surfaced**
   - the tool should be able to expose when some expected knowledge kinds are missing for the current case/domain
   - this is useful both for the model and for future KB growth

3. **empty buckets are normal**
   - `matched_objects.issue_patterns`, `matched_objects.rcas`, etc. may legitimately be empty arrays
   - an empty bucket is better than filling the result with weak or misleading hits

4. **unused quota should flow to stronger kinds**
   - if one kind has no acceptable hit, remaining budget may be used by other kinds with stronger matches

5. **coverage gaps should be surfaced**
   - the tool should be able to expose when some expected knowledge kinds are missing for the current case/domain
   - this is useful both for the model and for future KB growth

### Recommended default priority tiers

- Tier 1 (core): `issue_pattern`, `rca`
- Tier 2 (strong support): `code_note`, `platform_note`
- Tier 3 (conditional support): `playbook`, `workaround`

### Dynamic biasing examples

- if signals include strong function/file evidence, prefer adding `code_note`
- if platform/mode semantics are important, prefer adding `platform_note`
- if strong pattern matches exist, ensure at least one `issue_pattern` is considered
- if strong historical case matches exist, ensure at least one `rca` is considered

### Example: sparse domain coverage

If a query is in a domain where KB coverage is weak (for example, no relevant `issue_pattern` or `rca` exists), the correct behavior is:

- return empty arrays for those kinds
- avoid filling them with weak unrelated hits
- optionally surface the gap in a coverage-oriented output field

Example conceptual shape:

```json
{
  "matched_objects": {
    "issue_patterns": [],
    "rcas": [],
    "platform_notes": [],
    "code_notes": [ ... ],
    "playbooks": [ ... ],
    "workarounds": []
  },
  "coverage": {
    "matched_kinds": ["code_note", "playbook"],
    "missing_kinds": ["issue_pattern", "rca", "platform_note"],
    "notes": [
      "No sufficiently relevant issue_pattern matched current signals.",
      "No sufficiently relevant RCA matched the current subsystem/platform combination."
    ]
  }
}
```

### Summary of the policy

The intended balance strategy is:
- quality-first
- diversity-aware
- soft-targeted
- gap-aware

---

## Current open questions (not yet finalized)

The following points remain open for later discussion/implementation:

- whether `kb_search` and `kb_get` should be implemented first or alongside `kb_ground`
- ranking strategy details (keyword/BM25 vs hybrid retrieval)
- exact `coverage` field shape and whether it should be part of the first version
- how `kb_ground` should map into a future `grounding_bundle.kb_grounding`
