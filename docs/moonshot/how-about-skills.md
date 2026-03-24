# How about skills?

This document captures a moonshot-style design discussion about whether `simple-rla` should introduce a notion similar to skills, and if so, where such a concept should live in the architecture.

It is intentionally exploratory rather than normative. The goal is to preserve the full line of reasoning, not just a compressed note.

---

# Core conclusion

A `skill` should not be treated as identical to a `workflow`.

A better framing is:

- **skill** = a reusable domain strategy package / troubleshooting handbook / playbook
- **workflow** = a concrete execution arrangement for the current case
- **`DEBUG_PLAN`** = the bounded plan object for the current case
- **assembled checks** = execution-ready `CODE_CHECK` / `DEVICE_CHECK`

So:

> A workflow can be one concrete realization of a skill, but a skill should not be collapsed into a single workflow.

---

# What a skill really is

A useful way to think about a skill is:

> a predefined but flexible promptized playbook

This intuition is mostly correct, but it needs one refinement: a skill is not just a prompt.

A skill is better understood as:

- a prompt
- plus task boundaries
- plus operational constraints
- plus reusable domain tactics
- plus output expectations

In other words:

> **skill = prompt + policy + playbook + reusable domain strategy**

This is why a skill feels similar to:

- a troubleshooting handbook
- a developer guide
- an SOP / playbook
- a reusable operational manual

But unlike a single prompt, a skill usually also carries:

- when it applies
- when it should not apply
- what input assumptions it expects
- what sequence of actions is usually effective
- which pitfalls to avoid
- what form of output or artifact is expected

---

# A skill is not the same as a workflow

The distinction matters because a skill generally lives at a broader and more reusable level than a workflow.

A single skill may support many workflows.

For example, a hypothetical `hibernate-resume-mismatch` skill could support:

- a workflow that first compares `BIOS-e820`, then compares `/proc/iomem`, then performs external-device A/B testing
- a workflow that first validates the resume chain, then verifies image signature, then inspects ACPI data relocation
- a workflow specialized for a specific vendor platform or firmware environment

This means:

> **one skill can inform multiple workflows**

while a workflow is usually much more case-bound and orchestration-bound.

A workflow is sensitive to:

- what artifacts are currently available
- what tools are currently permitted
- what phase the system is in
- what hypothesis is currently active
- what the current case constraints and evidence gaps are

So:

- **skill** is closer to a reusable strategy layer
- **workflow** is closer to a concrete execution layer

A more precise statement is:

> A workflow is often an operationalization of a skill, but a skill should not be reduced to a workflow template too early.

---

# Where skills should live in `simple-rla`

The strongest design conclusion from the discussion is:

> Skills should first be introduced at the **planning layer**, not as runtime primitives.

The recommended priority order is:

1. **planning layer**
2. **assembly layer**
3. workflow generation layer
4. only much later, if ever, runtime primitive layer

This means a skill should first influence:

- how the problem is framed
- how evidence gaps are prioritized
- what kinds of checks are recommended
- which anti-patterns are avoided
- what should trigger reframing

rather than directly becoming:

- a phase object
- a step object
- a runtime execution primitive
- a new top-level orchestration entity

A concise way to say this is:

> **a skill should first function as a handbook in the system’s mind, not as a new runtime part.**

This matters because the existing architecture already has meaningful structure:

- runtime backbone
- analysis
- planning
- check assembly
- check execution
- evidence integration

Injecting skills too early into the runtime layer would risk blurring the boundaries between:

- phase
- workflow
- check
- skill
- execution primitive

That would destabilize the architecture instead of helping it.

---

# Skills belong most naturally in planning

From first principles, the strongest capability of a skill is not tool invocation but problem framing.

A skill is best at supplying:

- common hypothesis families
- common evidence-gap heuristics
- common check patterns
- common ordering heuristics
- common failure modes and anti-patterns
- typical `REFRAME` triggers

These are exactly the things that a planning layer most needs.

So the most natural first landing spot is:

- **`DEBUG_PLAN` generation**
- and secondarily, **M3.1 check assembly**

That means a skill should first shape:

- what directions the current case should investigate
- which evidence gaps should be filled first
- which `CODE_CHECK` and `DEVICE_CHECK` patterns are relevant
- which paths are high-yield versus wasteful

In the current `simple-rla` architecture, this is far more valuable than immediately making skills part of execution runtime semantics.

---

# Skill grounding as a parallel to KB grounding

One of the most important ideas in the discussion is that `DEBUG_PLAN` generation could include something analogous to `kb_ground_case`, but aimed at skills instead of factual knowledge.

This can be expressed cleanly as:

- `kb_ground_case` = **fact grounding**
- `skill_grounding` = **strategy grounding**

These two grounding modes answer different questions.

## KB grounding answers:

> What does the outside world know about this problem?

This includes:

- facts
- known behaviors
- prior cases
- formal knowledge
- subsystem understanding
- explanatory context

## Skill grounding answers:

> When facing this kind of problem, how should the system investigate it?

This includes:

- recommended troubleshooting directions
- high-yield checks
- expected evidence forms
- common anti-patterns
- likely reframing conditions
- reusable debugging heuristics

This means skill grounding is not a replacement for KB grounding.

Instead:

> **KB grounding provides problem knowledge; skill grounding provides strategy knowledge.**

These two should be treated as complementary.

---

# A future `DEBUG_PLAN` should likely be synthesized from multiple sources

The discussion suggests a more powerful planning pipeline for `simple-rla`:

```text
case evidence
  + kb grounding
  + skill grounding
  + current hypotheses
    -> DEBUG_PLAN
    -> check assembly
    -> execution
    -> evidence integration
```

This is important because without skill grounding, planning tends to depend too heavily on ad hoc reasoning from local context alone.

That leads to:

- unstable debug quality
- repeated reinvention of common troubleshooting moves
- loss of mature domain strategies
- uneven check recommendation quality

Skill grounding provides a systematic way to preserve and retrieve debugging know-how.

---

# What skill grounding should output

Another major conclusion is that skill grounding should **not** directly output the final `DEBUG_PLAN`.

Instead, it should output:

> **plan-shaping inputs**

This preserves the distinction between:

- reusable strategy priors
- current-case bounded planning

A strong candidate structure for `skill_grounding` output is:

- `matched_skills`
- `recommended_directions`
- `recommended_check_templates`
- `evidence_expectations`
- `reframe_triggers`
- `anti_patterns`

Each of these plays a different role.

## 1. `matched_skills`
These identify which skills are most relevant to the current case, together with relevance and rationale.

Example role:
- identify that a case resembles `hibernate-resume-mismatch`
- identify that it also resembles `acpi-memory-map-drift`
- preserve strategy candidates without yet committing to a final plan

## 2. `recommended_directions`
These represent preferred investigative axes, such as:

- compare save environment vs resume environment
- verify memory-map stability
- isolate topology-dependent effects

These are not yet checks and not yet workflow steps. They are planning directions.

## 3. `recommended_check_templates`
These are one of the most important outputs.

They should not yet be fully assembled execution objects.

Instead they should function as reusable templates, such as:

- compare `BIOS-e820` before and after resume
- compare `/proc/iomem`
- inspect swsusp mismatch checks in code

This preserves a clean boundary with M3.1 assembly.

## 4. `evidence_expectations`
This is a crucial category.

A skill does not only say what to do; it also says what evidence patterns would be meaningful.

Examples include expectations such as:

- shifted ACPI data region supports firmware resume-path instability
- image signature found but restore rejected supports environment mismatch
- absence of image signature weakens restore-environment explanations and redirects attention to the resume chain

This helps `DEBUG_PLAN` stay evidence-sensitive.

## 5. `reframe_triggers`
These define when the current strategy should be downgraded or redirected.

For example:

- if `BIOS-e820` is stable, deprioritize memory-map drift
- if image signature is absent, return to resume-chain analysis

These are not final decisions. They are structured cues for plan revision.

## 6. `anti_patterns`
These prevent common mistakes, such as:

- overfitting early to a noisy post-resume driver warning
- confusing image-not-found with image-found-but-restore-rejected

These are exactly the kind of domain lessons a skill can preserve far better than a workflow alone.

---

# Why skill grounding should not directly produce the final plan

If `skill_grounding` directly outputs ordered steps or execution-ready checks, it begins to collapse into either:

- a workflow template
- or a hidden `DEBUG_PLAN`

That would blur critical boundaries.

The better relationship is:

- `skill_grounding` retrieves strategic priors and recommended structures
- `DEBUG_PLAN` synthesizes those priors with the actual case context, hypotheses, and evidence gaps
- M3.1 then assembles that bounded plan into execution-ready `CODE_CHECK` and `DEVICE_CHECK`

This preserves a useful layering:

- strategy retrieval
- plan synthesis
- execution assembly
- execution realization
- evidence integration

---

# Why this likely matters for `simple-rla`

This does not look like an optional decorative feature.

The current architecture already has clear shape in these areas:

- runtime substrate
- analysis
- planning
- check assembly
- check execution
- evidence integration

What is still missing as a first-class idea is:

> **how domain experience is systematically injected into planning**

Without that layer, the system risks relying too much on per-case improvisation.

That means:

- mature troubleshooting strategies are not preserved well
- high-yield check patterns are rediscovered repeatedly
- planning quality remains uneven across domains
- domain-specific debugging know-how is hard to accumulate

Skills, especially when used through a `skill_grounding` step, are a natural answer to that missing layer.

---

# The most important distilled idea

A concise statement of the moonshot idea is:

> `simple-rla` should eventually consider introducing a `skill grounding` layer, analogous to KB grounding but aimed at reusable debugging strategy packages rather than factual knowledge.
>
> Skills should not initially be treated as workflows or runtime primitives.
> Instead, they should act as domain-specific planning priors that shape `DEBUG_PLAN`, recommend `CODE_CHECK` / `DEVICE_CHECK` templates, define evidence expectations, and provide reframing triggers and anti-pattern guidance.

---

# Final summary

The discussion converged on the following high-level position:

1. A skill is not a workflow.
2. A skill is best understood as a reusable domain strategy package or playbook.
3. In `simple-rla`, skills should first be introduced at the planning layer, then secondarily at the assembly layer.
4. `DEBUG_PLAN` generation is a natural place for skill influence.
5. A future `skill_grounding` step could play a role analogous to `kb_ground_case`, but for strategy knowledge rather than factual knowledge.
6. The output of `skill_grounding` should be structured plan-shaping inputs, not the final `DEBUG_PLAN` itself.
7. This direction appears genuinely needed, because it addresses how domain debugging experience can become a first-class reusable planning resource inside `simple-rla`.

At the current stage, the idea is mature enough to preserve as a moonshot direction, while still early enough that no formal schema or runtime commitment needs to be made yet.
