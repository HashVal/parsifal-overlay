# Core Loop

## Purpose

This document describes the core reasoning-action-evidence loop that defines the intended behavior of `parsifal-overlay`.

It is not a workflow YAML reference, a runtime implementation note, or a milestone checklist. Its purpose is to explain the high-level loop that the system is designed to execute when handling a debugging case.

In particular, this document explains:

- why a closed loop is needed
- how reasoning and action should interact
- what role `DEBUG_STEPS` plays in the system
- how evidence should affect future reasoning
- when the loop should continue, stop, or escalate

---

## Why a Loop Is Needed

A single-pass analysis pipeline is useful, but it is not enough for real debugging work.

A model can summarize case information, extract plausible observations, retrieve related knowledge, and produce a reasonable-looking analysis report. But that alone does not establish whether the proposed explanation is actually correct.

The central problem is that debugging is not only about interpretation. It is also about evidence acquisition.

In many cases:

- the initial case description is incomplete
- logs provide only partial visibility
- symptoms are compatible with multiple possible causes
- platform- or branch-specific qualifiers matter
- the next useful step is not more summarization, but new evidence

For that reason, `parsifal-overlay` is not intended to end at analysis generation. It is intended to operate as a loop:

- reason about the current evidence
- decide what evidence is missing
- act to collect that evidence
- reason again using the new evidence
- either converge, revise, or stop

This is the design shift from a report-oriented workflow to an evidence-seeking debugging system.

---

## The Core Loop at a Glance

At a high level, the intended loop is:

```text
Case Intake
  -> Signal Extraction
  -> Knowledge Grounding
  -> Hypothesis Formation
  -> Check Generation
  -> Evidence Execution
  -> Evidence Evaluation
  -> Decision
      -> Confirm
      -> Revise and continue
      -> Blocked / Human-needed
```

This loop is not merely a sequence of workflow phases. It is a decision structure.

The key property is that the result of each cycle must affect the next step:
- what to check next
- whether the current explanation still holds
- whether the run should continue at all

---

## Loop Stages

### 1. Case Intake

The loop begins with the minimum case framing needed to start reasoning.

This typically includes:
- Jira or issue context
- attachments and available artifacts
- platform and environment hints
- basic case metadata

The purpose of this stage is not deep analysis. It is to establish enough context to know what evidence is available and where the first useful signals may come from.

Typical outputs include:
- normalized case context
- artifact manifest
- initial platform clues
- attachment selection for first-pass triage

---

### 2. Signal Extraction

Once the case inputs are available, the next task is to extract useful signals from them.

This stage should identify:
- dominant failure signatures
- trace anchors
- repeated observations
- symptoms likely to matter
- noise that should not dominate later reasoning

The purpose here is not final RCA. It is to reduce raw case artifacts into structured evidence that can support hypothesis formation.

Typical outputs include:
- observations
- error signatures
- evidence snippets
- failure-mode hints
- conflict or inconsistency candidates

---

### 3. Knowledge Grounding

Signal extraction alone is not enough. The system also needs prior knowledge to interpret what the extracted signals may mean.

This stage should provide:
- matching prior patterns
- platform notes
- RCA references
- terminology normalization
- guidance about what kinds of checks are usually useful next

The KB is not treated as authority in itself. It is a grounding layer that helps constrain reasoning and connect the current case to accumulated engineering knowledge.

Typical outputs include:
- retrieval context
- matched knowledge objects
- platform-specific qualifiers
- grounded vocabulary and prior-art references

---

### 4. Hypothesis Formation

Once evidence and grounding are both available, the system should form an explicit working hypothesis.

This is a crucial step.

A debugging loop cannot function well if the current explanation remains implicit. The system must be able to say:
- what it currently believes
- why it believes it
- what evidence supports that belief
- what evidence is still missing
- what weaker alternatives still remain plausible

The goal is not to prove the final answer immediately. The goal is to make the current explanatory state explicit enough that the next checks can be generated with purpose.

Typical outputs include:
- a primary hypothesis
- weaker alternative hypotheses
- current confidence
- supporting evidence
- unresolved evidence gaps

---

### 5. Check Generation

Once a working hypothesis exists, the system should generate checks that can validate, weaken, or reject it.

This is where `DEBUG_STEPS` becomes important.

In this design, `DEBUG_STEPS` is not the endpoint of the workflow. It is a planning artifact that translates a hypothesis into actions.

These actions should typically be divided into:
- `DEVICE_CHECK`
- `CODE_CHECK`

This distinction matters because the system must gather evidence from two different realities:
- the running system or device state
- the repository / code / branch state

Checks should not be generic advice. They should be tied to a specific hypothesis and a specific evidence need.

A good check should imply:
- why this check exists
- what evidence it seeks
- what outcomes would support or weaken the current hypothesis

Typical outputs include:
- structured debugging plan
- device-side evidence requests
- code-side evidence requests
- expected evidence interpretation hints

---

### 6. Evidence Execution

This stage performs the actions requested by the current plan.

For `DEVICE_CHECK`, this may involve:
- querying system state
- reading logs
- checking driver/module/device facts
- inspecting boot or runtime behavior
- gathering serial or SSH-accessible evidence

For `CODE_CHECK`, this may involve:
- searching source code
- checking branch-specific code paths
- locating symbols, commits, diffs, or references
- verifying whether a suspected mechanism exists in the codebase

This stage is one of the hardest parts of the system.

Reasoning can only be as good as the evidence that returns from the action layer. If the evidence pipeline is weak, noisy, or poorly structured, the loop degrades.

Typical outputs include:
- device evidence pack
- code evidence pack
- execution metadata
- failed checks / blocked actions
- newly collected observations

---

### 7. Evidence Evaluation

Once new evidence is available, the system must reassess the current hypothesis.

This is the point where action becomes meaningful. If evidence is collected but does not affect reasoning, the loop is fake.

The evaluation step should ask:
- does the new evidence support the current hypothesis?
- does it contradict the hypothesis?
- does it only partially support it?
- does it rule out one alternative but not confirm the main one?
- does it reveal a new direction that was previously hidden?

This stage should update the system’s explanatory state rather than simply append more notes.

Typical outputs include:
- hypothesis strengthened
- hypothesis weakened
- hypothesis rejected
- confidence updated
- next evidence gaps identified

---

### 8. Decision

The end of each loop cycle is a decision point.

The system should not continue by default. It should continue only when there is a meaningful reason to continue.

The decision stage must determine whether the run should:
- conclude with a sufficiently supported explanation
- revise the current hypothesis and begin another cycle
- stop because the run is blocked
- stop because human review or manual action is required
- stop because the loop budget has been exhausted

This stage turns the loop into a bounded engineering process rather than an open-ended agent wander.

Typical outputs include:
- final conclusion
- next-iteration request
- blocked state
- human-needed state
- stop reason

---

## What Makes This a Real Loop

A workflow does not become a real debugging loop merely because it has multiple phases.

The loop becomes real only when three conditions hold.

### 1. The hypothesis is explicit
The system must be able to state what it currently believes and why.

Without an explicit hypothesis, later checks become disconnected from purpose.

### 2. Checks are hypothesis-linked
The system must generate actions because a particular uncertainty exists.

If checks are not tied to a hypothesis or evidence gap, they become generic exploration rather than debugging.

### 3. Evidence changes the next decision
Collected evidence must be able to alter:
- confidence
- hypothesis ranking
- next checks
- termination decision

If action does not affect the next reasoning step, then the loop is only theatrical.

---

## Loop Exit Conditions

The loop should stop under clear conditions.

### Confirmed
The primary hypothesis is sufficiently supported by the available evidence.

### Sufficiently likely
The evidence does not amount to formal proof, but it is strong enough to justify a conclusion and recommended next actions.

### Rejected and replaced
The current hypothesis has been invalidated, and the system should move into another cycle using a new working explanation.

### Blocked
The required evidence cannot be obtained automatically, or a critical dependency is unavailable.

### Human-needed
The case requires expert judgment, privileged action, lab intervention, or a non-automatable decision.

### Exhausted
The loop has reached a configured limit, or the expected value of another cycle is too low.

These outcomes are all valid. A blocked or human-needed result is not a design failure. It is a correct bounded outcome when automation should stop.

---

## `DEBUG_STEPS` in the Core Loop

`DEBUG_STEPS` deserves special emphasis because it is easy to misunderstand.

In this design:

- `DEBUG_STEPS` is not the final goal
- `DEBUG_STEPS` is not just a formatted report section
- `DEBUG_STEPS` is the bridge between reasoning and action

Its role is to turn:
- a working hypothesis
- a set of evidence gaps
- and a current case context

into:
- concrete device-side checks
- concrete code-side checks
- an actionable evidence plan

If `DEBUG_STEPS` is treated as the endpoint, the system remains a report generator.
If `DEBUG_STEPS` is treated as a live execution plan, the system becomes a debugging loop.

---

## Non-Goals

The core loop is not intended to imply:

- unrestricted autonomous tool use
- unlimited iteration until some answer appears
- guaranteed automatic resolution of every case
- direct replacement of expert engineering judgment
- fully automatic KB write-back without review
- patch generation as the primary loop objective

The purpose of the loop is narrower and more practical:
- improve evidence quality
- reduce repeated debugging labor
- increase the chance of converging on the right explanation
- stop safely when automation is no longer the right tool

---

## Relationship to Other Documents

This document should be read together with nearby design documents.

- `why-parsifal-overlay.md`
  explains why the project exists and what problem motivates it

- `core-loop.md`
  explains how the intended reasoning-action-evidence loop operates

- `system-objects.md`
  should explain the key conceptual objects inside the loop

- `artifact-strategy.md`
  should explain how loop state is represented, separated, and handed off

Together, these documents describe:
- why the system exists
- how it works at a high level
- what concepts it relies on
- how its reasoning state should be organized

---

## Conclusion

The core of `parsifal-overlay` is not a report and not a static workflow.

Its core is a bounded loop that connects:
- case understanding
- signal extraction
- knowledge grounding
- explicit hypothesis formation
- targeted action
- evidence collection
- evidence-based revision
- conclusion or escalation

This is what turns the system from a document-producing pipeline into an evidence-seeking debugging system.
