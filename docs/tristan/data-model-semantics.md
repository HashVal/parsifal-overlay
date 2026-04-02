# Debug Agent Data Model Semantics (MVP)

This document is the semantic companion to `data-model.md` and `data-model-schema.md`.

It exists because JSON Schema can define structure, required fields, and local field constraints, but it cannot fully express:

- state-machine intent
- allowed interpretations of fields
- cross-field meaning
- prohibited ambiguous usage
- validator rules that are semantic rather than structural

This document records:

1. semantics already agreed for MVP
2. semantics that are intentionally left open
3. known ambiguity points discovered during review
4. rules that should be enforced by harness logic or semantic validators rather than pure JSON Schema

The goal is to reduce drift, prevent future misreadings, and make reviewable intent explicit.

---

## 1. General Principles

### 1.1 Facts, hypotheses, execution, and decisions are different layers

These layers must not be mixed.

- **Facts** are source-traceable observations or extracted case metadata.
- **Hypotheses** are competing explanations for the failure.
- **Plan** is the structured set of checks intended to discriminate between hypotheses.
- **Execution** is what actually happened when checks were run.
- **Decision** is the closure/rerun/help outcome.

A field should not silently cross layers. Example:
- a hypothesis conclusion must not be written into `facts`
- a plan item must not silently contain final reasoning prose
- a decision must not silently introduce new raw facts

---

### 1.2 MVP favors self-consistency over future abstraction

When a design choice conflicts between:
- being elegant for future graph-based reasoning
- being self-contained and reviewable in MVP

MVP should prefer the latter.

This is why the current schema uses inline hypothesis evidence items instead of references into a full evidence graph.

---

### 1.3 Semantics should be explicit when schema alone is insufficient

If a field can be structurally valid but semantically misleading, this document should define the intended meaning.

---

## 2. Meta Semantics

### 2.1 `meta.status`

`meta.status` is the current state-machine state of the case.

It is not merely a descriptive phase label.
It should be interpreted as the current workflow control state.

Current MVP states:
- `NEW`
- `INTAKE_READY`
- `HYPOTHESES_READY`
- `PROBING`
- `JUDGING`
- `NEED_RERUN`
- `FINALIZED_STRONG`
- `FINALIZED_WEAK`
- `NEED_HELP`

Known ambiguity:
- `status` currently mixes workflow states and terminal outcomes in one enum.
- This is accepted for MVP simplicity.
- A later design may split this into separate fields such as `phase` and `case_outcome`.

---

### 2.2 `meta.owner_agent`

`owner_agent` indicates which agent should act next.

This is not a decorative field. It should be treated as a control-plane field.

Semantic rule:
- `owner_agent` must be consistent with `status`
- this should be enforced by semantic validation or harness logic
- this is not fully expressible in plain schema in a clean way

Illustrative mapping for MVP:
- `NEW` -> `intake`
- `INTAKE_READY` -> `hypothesis`
- `HYPOTHESES_READY` -> `probe`
- `PROBING` -> `probe`
- `JUDGING` -> `judge`
- `NEED_RERUN` -> `hypothesis`
- `FINALIZED_STRONG` -> `null`
- `FINALIZED_WEAK` -> `null`
- `NEED_HELP` -> `null`

MVP decision:
- `NEED_RERUN` is owned by `hypothesis`
- rerun is treated as re-analysis/re-planning on top of retained state, not full re-intake by default

---

### 2.3 `meta.loop_index`

`loop_index` identifies the current rerun/analysis cycle.

MVP note:
- current planning assumes one main loop for initial implementation
- however the field is retained because rerun is a core conceptual feature of the design

Semantic meaning:
- `0` may be used before first actual agent pass
- first meaningful agent-generated artifacts are typically associated with loop `1`

Known ambiguity:
- whether the case should start at loop `0` or `1` at creation time
- this should be chosen consistently by implementation

---

### 2.4 `meta.run_config`

`run_config` defines the configured resource and control limits for this case.

It is part of the case control plane, not an execution result.

Examples:
- `max_loops`
- `max_total_checks`
- `max_code_checks`
- `max_device_checks`
- `max_kb_queries`

Semantic rule:
- these are case-level run constraints
- they define what the harness allows, not what agents have already used
- actual usage belongs in execution/tool usage fields

---

### 2.5 `meta.tags`

`tags` are lightweight descriptive labels.

MVP semantics:
- tags are informational and organizational
- tags are not authoritative reasoning fields
- tags should not carry long prose, uncertain diagnosis, or free-form conclusions

Known ambiguity:
- tag normalization rules are not yet fully enforced in schema
- a later tightening may restrict tags to lowercase kebab-case

For MVP:
- keep tags simple and short
- avoid embedding speculative diagnosis in tags

---

## 3. Facts Semantics

### 3.1 Facts are source-traceable observations, not root-cause claims

A `Fact` must represent something grounded in an issue, comment, log, or tool result.

Examples of acceptable facts:
- kernel version observed in boot log
- BIOS version reported in issue comment
- failure stage inferred from runtime context summary if traceable to source
- observed affected subsystem summary if traceable to anomaly/log extraction

Examples of unacceptable facts:
- "root cause is BIOS misconfiguration"
- "NVMe timeout is definitely downstream of PCIe"
- "kernel bug is unlikely"

These belong in hypotheses or decision, not facts.

---

### 3.2 `Fact.confidence` means extraction reliability, not hypothesis probability

This is a critical semantic distinction.

`Fact.confidence` describes how reliable the extraction or identification of the fact is.
It does **not** describe the likelihood that a root-cause theory is correct.

Example:
- a platform name pulled from a noisy issue description may have `medium` confidence
- this does not mean the platform is "half true"
- it means the extraction is less reliable than a directly logged platform identifier

Known ambiguity:
- because the word `confidence` is shared with hypotheses, implementers may confuse the two
- this document explicitly distinguishes them

---

### 3.3 `Fact.source_refs` are mandatory because facts must be auditable

Every fact must answer:
- where did this come from?

If a fact cannot be traced back to a source, it should not be written into the facts layer.

This is one of the core anti-drift constraints in the design.

---

### 3.4 `Fact.observed_in_loop`

This records when a fact entered the case state.

It does not necessarily mean the real-world phenomenon first occurred in that loop.
It means the system observed or recorded the fact in that loop.

Known ambiguity:
- users may misread this as the event timestamp or first real occurrence
- it is not that
- it is case-state observation timing, not physical-world timing

---

### 3.5 Fact partition semantics

The current MVP fact partitions are:
- `platform`
- `software`
- `runtime`
- `environment`
- `missing`

These are organizational partitions, not strict ontological truth classes.

Meaning:
- `platform`: board/SOC/boot/BIOS/firmware identity facts
- `software`: kernel/distro/config/package facts
- `runtime`: runtime failure behavior and observed operational context
- `environment`: test/repro/baseline/regression context
- `missing`: explicit information gaps

Known ambiguity:
- some runtime summaries (e.g. `affected_subsystems`) are already derived summaries rather than fully raw observations
- this is accepted in MVP as long as they remain source-traceable

---

### 3.6 `facts.missing`

Missing facts are not failures of schema completeness; they are explicit state.

Meaning:
- the system knows the information is absent and considers it relevant

`MissingFact.suggested_source` meaning:
- this is not the current source of the fact
- it is the recommended source or acquisition channel for filling the gap

Known ambiguity:
- the field name may be read as current source rather than suggested acquisition source
- renaming may be considered later if confusion persists

---

## 4. Hypothesis Semantics

### 4.1 Hypotheses are competing explanations, not decorated conclusions

A hypothesis is a candidate explanation for the failure.
Multiple hypotheses should coexist until evidence meaningfully weakens or confirms them.

This is a core design rule.

The hypothesis table must not silently degrade into:
- one real conclusion plus a few token alternatives
- multiple restatements of the same idea with different wording

---

### 4.2 `HypothesisTable.required_classes`

`required_classes` is the policy floor for hypothesis generation.

Meaning:
- it represents the minimum categories the harness expects the system to consider
- it is not intended as a free-form per-case self-declared subset

Example intent in this project:
- kernel bug
- firmware bug
- BIOS config issue
- Ubuntu/distro config issue
- hardware issue

Known ambiguity:
- because this is stored in the case state, it could be misread as a dynamic result of analysis
- for MVP it should be interpreted as a required consideration set, not as a model-generated output of what is actually present

---

### 4.3 `Hypothesis.confidence`

This is hypothesis confidence, unlike fact confidence.

Meaning:
- relative confidence in the current explanatory hypothesis given current evidence

It is acceptable for multiple hypotheses to have non-trivial confidence simultaneously.
This field should not be treated as a probability distribution that must sum to 1 unless a later version explicitly chooses that interpretation.

Known ambiguity:
- implementers may mistakenly normalize all hypothesis confidences to sum to 1
- MVP does not require that

---

### 4.4 `support_evidence` and `contradiction_evidence`

These are inline evidence items for MVP self-consistency.

Meaning:
- `support_evidence`: observations or derived evidence that support the hypothesis
- `contradiction_evidence`: observations or evidence that weaken the hypothesis

MVP choice rationale:
- earlier designs considered storing only references to a global evidence graph
- that was judged too abstract for MVP because the full evidence layer is not yet formalized
- inline evidence keeps the case state self-contained and reviewable

Known ambiguity:
- contradiction evidence is not the same as total refutation
- a hypothesis may retain contradiction evidence and still remain active

---

### 4.5 `missing_gaps`

These are information gaps that materially affect closure of the hypothesis.

Meaning:
- these are not yet evidence items
- they describe what is missing to assess or close the hypothesis

`closure_requirement` meaning:
- `must_have`: required for acceptable closure in current reasoning policy
- `strong_should_have`: highly desirable and materially improves confidence
- `optional`: useful but not required for current closure

Known ambiguity:
- a missing gap does not necessarily imply the hypothesis is weak; it may simply indicate incomplete closure

---

### 4.6 `scope`

`scope` localizes the hypothesis in terms of:
- subsystem
- layer
- component

Purpose:
- prevent hypotheses from becoming vague and omnidirectional
- force the model to specify where the hypothesis sits in the system

MVP rule:
- all fields may be null if not yet known
- null is preferable to fabricated specificity

Known ambiguity:
- subsystem/component boundaries may not be stable in every case
- this is acceptable in MVP as long as null is used honestly

---

### 4.7 Loop tracking in hypotheses

`introduced_in_loop` and `updated_in_loop` indicate case-state lifecycle of the hypothesis.

They do not mean:
- first real-world emergence of the root cause
- ground-truth event timing

They mean:
- when the hypothesis entered the case model
- when it was most recently updated in the case model

---

## 5. Plan Semantics

### 5.1 A plan is an execution contract, not just a next-steps memo

A `CheckPlan` should be interpretable by a probe agent and by human reviewers.
It should make explicit what each check is trying to discriminate.

A plan item should not be a vague suggestion such as:
- "look at BIOS"
- "check the code"

It should identify:
- target hypothesis
- lane
- goal
- action
- object of inspection
- expected meaning of positive vs negative outcomes

---

### 5.2 `target_hypothesis_id`

This defines which hypothesis a check is primarily intended to discriminate.

Meaning:
- every check must have a principal diagnostic target
- a check may incidentally affect other hypotheses, but one target must still be named

This field exists to prevent information gathering from drifting into unscoped exploration.

---

### 5.3 `lane`

Current MVP semantics:
- `code`: repository / source / code-path side checks
- `device`: target-device / runtime / remote-environment side checks

Current MVP decision:
- only `code` and `device` are allowed in schema
- earlier broader ideas such as `mixed` are intentionally excluded from the MVP operating model

Rationale:
- the current execution model assumes the agent can access the repo via CLI and access the target device via SSH/CLI
- more granular lane modeling is intentionally deferred

---

### 5.4 `priority`

`priority` defines execution priority within the plan.

MVP semantic rule:
- smaller number = higher priority
- `1` is the highest priority

This field should be interpreted as execution ordering guidance, not as confidence or importance in the abstract.

Known ambiguity:
- without explicit definition, some systems interpret larger numbers as higher priority
- this document resolves that ambiguity for MVP

Implementation note:
- stable ordering may later be defined as `(priority, check_id)` if needed

---

### 5.5 `tool_action`

`tool_action` is the registered harness/tool action name to execute.

It is not intended to be free-form English prose.

Examples of intended style:
- `code.inspect_driver_path`
- `device.inspect_boot_fw_state`
- `device.collect_runtime_facts`

Known ambiguity:
- schema currently permits any non-empty string
- this is accepted temporarily for MVP flexibility
- harness/tool registry validation should enforce actual allowed action names

---

### 5.6 `inputs`

`inputs` contains execution parameters for the check.

It must not become a hidden prompt or reasoning dump.

MVP rule:
- `inputs` should describe execution parameters only
- it should explain what is being checked directly and operationally
- `inputs.subject` is required and identifies the direct inspection target of the check

Current MVP common fields:
- `subject`: required, what this check is directly checking
- `command_hint`: optional execution hint
- `target_path`: optional path or code location target
- `target_host`: optional device/host target identifier
- `expected_artifact`: optional expected output or observation target

Review direction established during discussion:
- inputs should be constrained enough to make the checked object explicit
- they should not silently absorb large amounts of prose reasoning

Known ambiguity:
- schema does not yet fully define per-tool input subschemas
- additionalProperties are still allowed for MVP flexibility
- this remains a planned future improvement

---

### 5.7 `expected_if_true` and `expected_if_false`

These fields describe what the check result would mean under positive vs negative support of the targeted hypothesis.

Purpose:
- force the planner to think in discriminative terms
- prevent one-sided evidence collection

Semantic rule:
- these fields are interpretations of expected diagnostic meaning, not exact raw command outputs

Known ambiguity:
- these are still natural-language descriptions and can vary in quality
- later validator or linting rules may enforce minimum clarity

---

### 5.8 `fallback`

`fallback` is a fallback strategy note, not a fully structured substitute check.

Meaning:
- if the primary check cannot be executed or yields insufficient information, these notes indicate fallback direction

It should not be interpreted as:
- an automatically schedulable check item
- a hidden second plan

Known ambiguity:
- because fallback is stored as free text, it may drift into weak prose
- a later model may replace this with structured fallback check references

---

### 5.9 `dependencies`

`dependencies` are check-level dependencies.

Meaning:
- these indicate prerequisite checks that must complete before this check should be considered ready
- they are not prose dependency descriptions

Known ambiguity:
- current schema does not yet validate that dependency ids exist in the same plan
- this should be enforced by semantic validation

---

### 5.10 `info_gain`

`info_gain` is a coarse estimate of expected diagnostic discrimination value.

Meaning:
- `high`: likely to materially separate major competing hypotheses
- `medium`: useful narrowing but not likely decisive alone
- `low`: supplementary or confirmatory, limited discrimination value

This is not a guarantee. It is planning metadata.

---

### 5.11 `estimated_cost`

`estimated_cost` is a relative execution cost score.

It does not represent exact:
- wall-clock time
- token cost
- monetary cost

MVP interpretation:
- it is a coarse relative cost used for comparing plan items
- smaller generally means cheaper, but no universal cross-project scale is assumed

Known ambiguity:
- if implementations treat this as a precise runtime estimate, behavior will drift
- this document explicitly defines it as relative only

---

### 5.12 `CheckItem.status`

This is the plan-side state of the check.

Examples:
- `planned`
- `running`
- `done`
- `skipped`
- `blocked`

Semantic rule:
- plan status should remain consistent with execution records
- a `done` check should normally have a corresponding execution result
- a `blocked` check should normally have a corresponding blocker or blocked result context

This consistency should be enforced by semantic validation rather than pure schema.

---

## 6. Execution Semantics

### 6.1 Execution is what actually happened, not what was intended

The plan states intended checks.
Execution records the realized outcomes.

This distinction is essential.

---

### 6.2 `CheckResult.outcome`

Outcome meanings:
- `positive`: the check executed and produced a result that positively supports the targeted diagnostic direction
- `negative`: the check executed and produced a result that does not support or weakens the targeted diagnostic direction
- `inconclusive`: the check executed but did not provide decisive diagnostic value
- `blocked`: the check could not complete meaningfully due to execution constraints

Reason for current wording:
- earlier outcome labels such as `success` / `fail` were found to be ambiguous
- they could be misread as command execution success/failure rather than diagnostic meaning
- `positive` / `negative` better reflects the diagnostic interpretation of the check result

Known ambiguity:
- `negative` is not necessarily total falsification of a hypothesis
- it means the result is not supportive of the targeted hypothesis or weakens it relative to expectation

Operational note:
- low-level command/tool execution failure should normally surface through `blocked`, blocker records, raw output context, or execution detail rather than overloading `negative`

---

### 6.3 `summary` vs `interpreted_result`

`summary` should describe the observed result concisely.
`interpreted_result` should describe the diagnostic meaning of the result.

Example:
- summary: "ASPM forced enabled in BIOS"
- interpreted_result: "This increases confidence in the BIOS config issue hypothesis"

This separation is intentional and should be preserved.

---

### 6.4 `hypothesis_impacts`

This field records how a check result influences hypotheses.

`delta` meaning:
- positive values strengthen the hypothesis
- negative values weaken the hypothesis
- zero means no meaningful effect

Known ambiguity:
- current schema allows values from `-1` to `1`, but this should not be interpreted as a strict probability update mechanism
- it is a relative directional impact score for MVP

---

### 6.5 `CheckResult.confidence`

`CheckResult.confidence` describes confidence in the interpretation of the check result.

It is not the same as:
- overall hypothesis confidence
- fact extraction confidence

Example intent:
- `high`: result is clear and interpretation is reliable
- `medium`: result is usable but interpretation depends on some contextual reasoning
- `low`: result is noisy, partial, or weakly diagnostic

Known ambiguity:
- because the same word `confidence` appears in facts, hypotheses, and execution, implementations must keep the meanings separated by layer

---

### 6.6 `tool_usage`

This is actual observed resource usage for the case.

Meaning:
- this is the consumed side of the resource model
- it should be interpreted relative to `meta.run_config`

`tool_usage` and `run_config` must not be conflated.

Current MVP interpretation:
- `code_checks` and `device_checks` count executed checks by lane
- `total_checks` should be interpreted as the total number of executed probe checks in the current accounting model

Known ambiguity:
- if an implementation wants `total_checks` to include non-probe operations such as jira/kb activity, it must redefine this consistently at harness level
- current preferred interpretation is that `total_checks` is the total probe-check count, not every tool action of any kind

---

### 6.7 `new_fact_ids`

`new_fact_ids` identifies facts that were introduced into the facts layer as a result of this check.

Meaning:
- these are facts produced or confirmed by this execution result
- they should refer to fact objects that exist in the case state after merge

MVP note:
- earlier draft designs also included `new_evidence_ids`
- that field was removed because the current MVP does not maintain a separate global evidence store

---

### 6.8 `Blocker`

A blocker represents an execution obstacle.

Meaning:
- a blocker is not the same as hypothesis contradiction
- it is an operational impediment to obtaining evidence

Examples:
- device unreachable
- unsupported tool
- missing required artifact
- timeout while probing

---

## 7. Decision Semantics

### 7.1 Decision is the closure layer

Decision fields express what the system currently concludes about process closure.
They should not be used as a hidden storage area for new facts or plan details.

---

### 7.2 `current_verdict`

MVP verdict meanings:
- `FINALIZED_STRONG`: hypothesis closure is strong enough for confident case completion
- `FINALIZED_WEAK`: best current explanation is acceptable for weak closure, but residual uncertainty remains
- `NEED_RERUN`: current evidence does not sufficiently close the case and another reasoning/probing cycle is needed
- `NEED_HELP`: required information or action cannot be obtained within the current autonomous workflow

Known ambiguity:
- schema alone does not define exactly what qualifies as strong vs weak closure
- this must be governed by implementation policy or later validator logic

---

### 7.3 `top_hypothesis_ids`

These identify the leading hypotheses at decision time.

Semantic rule:
- for finalized states, this field should normally not be empty
- ids should correspond to existing hypotheses in the case state
- this is an ordered list, not just an unordered set
- earlier entries represent higher current diagnostic priority

This should be enforced by semantic validation.

---

### 7.4 `rationale`

`rationale` is the decision-layer explanation for the current verdict.

Meaning:
- it summarizes why the workflow is stopping, rerunning, escalating, or accepting closure
- it should be grounded in existing facts, hypothesis state, and execution results

MVP rule:
- `rationale` must not introduce new major conclusions that do not appear elsewhere in the structured state
- it is a summary layer, not a hidden extra reasoning layer

Known ambiguity:
- because `rationale` is free-form text, it can easily drift into unsupported narrative if not reviewed or semantically validated

---

### 7.5 `help_request`

`help_request` is used when human or specialized external intervention is needed.

Meaning:
- this captures ownership and minimum required input for escalation
- it should not be populated casually when the system simply prefers not to continue

Known ambiguity:
- schema allows `help_request` to be null even when verdict is `NEED_HELP`
- semantic validation should tighten this relationship

---

### 7.6 `finalized_explanation`

This is the human-readable finalized explanation when closure has been reached.

Meaning:
- this should reflect the final decision layer
- it should not appear early merely because a hypothesis currently leads
- it is intentionally named `finalized_explanation` rather than `finalized_root_cause`

Rationale for naming:
- in weak closure cases, the system may only have the best currently accepted explanation rather than a fully proven absolute root cause
- the term `explanation` better fits both strong and weak finalized outcomes

Known ambiguity:
- schema currently does not force it to be non-null for finalized verdicts
- this should be enforced semantically if required by workflow policy

---

## 8. Cross-Field Rules That Schema Alone Does Not Fully Enforce

The following are semantic-validator or harness rules rather than pure schema rules.
For MVP clarity, they are grouped by category and marked as either:
- **MUST**: invalid if violated
- **SHOULD**: strongly expected, but may be implementation-policy dependent in edge cases

### 8.1 State-machine invariants

1. **MUST**: `meta.owner_agent` must be legal for `meta.status`
2. **MUST**: terminal states (`FINALIZED_STRONG`, `FINALIZED_WEAK`, `NEED_HELP`) must imply `meta.owner_agent = null`
3. **MUST**: `meta.status = NEED_RERUN` must imply `meta.owner_agent = hypothesis` in MVP

### 8.2 Reference integrity rules

4. **MUST**: `decision.top_hypothesis_ids[*]` must exist in `hypotheses.items`
5. **MUST**: `plan.items[*].target_hypothesis_id` must exist in `hypotheses.items`
6. **MUST**: `plan.items[*].dependencies[*]` must refer to existing check ids in the same effective plan
7. **MUST**: `execution.results[*].check_id` must exist in the current effective plan or accepted follow-up additions
8. **MUST**: `execution.blockers[*].check_id`, if non-null, must exist in the current effective plan or accepted follow-up additions
9. **MUST**: `execution.results[*].new_fact_ids[*]` must resolve to fact objects present in case state after merge

### 8.3 Lifecycle consistency rules

10. **MUST**: `CheckItem.status = done` must imply a corresponding execution result exists
11. **MUST**: `CheckItem.status = blocked` must imply a blocker record or blocked execution result exists
12. **MUST**: `execution.results[*].outcome = blocked` must imply a corresponding blocker record exists
13. **MUST**: finalized states must not coexist with `CheckItem.status = running`
14. **MUST**: `decision.current_verdict = NEED_RERUN` must imply non-empty `rerun_focus`
15. **MUST**: `decision.current_verdict = NEED_HELP` must imply non-null `help_request`
16. **MUST**: `decision.current_verdict = NEED_HELP` must imply non-null `help_request.owner`
17. **MUST**: `decision.current_verdict = NEED_HELP` must imply non-empty `help_request.reasons`
18. **MUST**: `decision.current_verdict = NEED_HELP` must imply non-empty `help_request.minimum_required_inputs`

### 8.4 Decision consistency rules

19. **MUST**: `decision.current_verdict = FINALIZED_STRONG` must imply `closure_level = strong`
20. **MUST**: `decision.current_verdict = FINALIZED_WEAK` must imply `closure_level = weak`
21. **MUST**: `decision.current_verdict = NEED_RERUN` must imply `closure_level = none` or `partial`
22. **MUST**: `decision.current_verdict = NEED_HELP` must not imply `closure_level = strong`
23. **MUST**: finalized states must imply non-empty `decision.top_hypothesis_ids`
24. **MUST**: finalized states must imply non-null `decision.finalized_explanation`
25. **MUST**: finalized states must imply empty `decision.rerun_focus`
26. **MUST**: `decision.current_verdict = NEED_RERUN` must imply `decision.finalized_explanation = null`
27. **SHOULD**: `decision.current_verdict = NEED_HELP` should imply `decision.finalized_explanation = null` in MVP unless implementation explicitly allows best-current explanation text for handoff
28. **MUST**: the first entry of `decision.top_hypothesis_ids` must not refer to a hypothesis whose status is `eliminated`

### 8.5 Semantic discipline rules

29. **MUST**: facts must not encode final root-cause claims
30. **MUST**: `decision.rationale` must not introduce new major conclusions absent from facts, hypotheses, or execution state
31. **SHOULD**: `decision.rerun_focus` should describe concrete next-loop focus rather than vague requests for more analysis

---

## 9. Known Deferred Topics

These were discussed or implied during review but intentionally deferred from MVP:

### 9.1 Global evidence graph
- not included in MVP schema
- inline evidence is used instead for self-consistency

### 9.2 Cross-case linkage
- fields such as `related_case_ids` were discussed
- deferred because they would imply cross-ticket search/linking steps beyond MVP

### 9.3 Fully enumerated tool-action taxonomy
- desired eventually
- deferred until tool surface stabilizes

### 9.4 Per-tool input sub-schemas
- desirable for stronger mechanical constraints
- deferred from MVP because tool contracts are still evolving

### 9.5 Separate `phase` and `case_outcome`
- a cleaner future modeling option
- current MVP keeps a single `status` for simplicity

---

## 10. Review Guidance

When reviewing future schema changes, use this checklist:

1. Does the change blur fact vs hypothesis vs decision layers?
2. Does it increase MVP self-consistency or only future elegance?
3. Does it remove ambiguity or introduce new hidden ambiguity?
4. Is the rule structural (schema) or semantic (validator/doc)?
5. If a field is free-form text, is its allowed meaning clearly bounded?

If these questions are not answered, the model will drift even if the schema still validates.
