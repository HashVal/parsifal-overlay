# Why Parsifal Overlay

## Introduction

`parsifal-overlay` starts from a practical engineering problem observed during platform enabling and kernel / OS upgrade work.

At first glance, this kind of work looks like a sequence of isolated bring-up and debugging tasks. In practice, it behaves more like a multiplicative system:

- number of platforms
- number of supported kernel versions
- number of active branches or kernel lines

As these dimensions grow, the total workload grows much faster than the visible number of issues.

At the same time, many failures are not fully unique. Their symptoms, evidence patterns, diagnostic methods, and likely fault classes often overlap across platforms and versions. This creates an opportunity: if repeated debugging structure can be captured and reused, a meaningful part of the work can be automated or at least heavily assisted.

`parsifal-overlay` is an attempt to build that system.

---

## The Original Insight

The initial idea behind `parsifal-overlay` was simple:

> a large portion of platform enabling work is repetitive in structure even when it is not identical in surface details.

A new platform, an upgraded kernel, or a branch-specific regression may present differently on the surface, but engineers often perform the same kinds of work:

- collect failure information
- extract meaningful signals from noisy artifacts
- look for similar patterns in prior knowledge
- analyze likely failure causes
- write down findings and next actions

This suggested that the workflow could be decomposed into explicit stages and executed by a mixed system of reasoning and tools.

The initial workflow was:

- Observe
- Extract
- Retrieve
- Analysis
- Generate

In this model:

- **Observe** collects raw failure context
- **Extract** identifies useful signals from logs or artifacts
- **Retrieve** pulls related knowledge from a knowledge base
- **Analysis** proposes likely explanations
- **Generate** produces a structured failure analysis report

This was the starting point of what later became `simple-rla`.

---

## Why the Original Workflow Was Not Enough

The original workflow was useful, but it had an important limitation.

A generated report can be helpful, but by itself it mostly demonstrates that the model can reorganize available information into a coherent document. It does not necessarily demonstrate strong reasoning, nor does it close the loop on whether the proposed explanation is actually correct.

In other words, a report-only system risks becoming:

- knowledge-assisted summarization
- artifact reformatting
- plausible explanation generation without evidence closure

That is not sufficient for real debugging work.

Real platform enabling and kernel debugging require more than a summary. They require a system that can:

- propose a concrete hypothesis
- decide what evidence is still missing
- actively collect that evidence
- reassess its own hypothesis using the new evidence
- stop when the hypothesis is confirmed, rejected, or blocked

This is the point where the design had to move beyond report generation.

---

## The Shift to ReAct

To address this limitation, the design evolved toward a ReAct-style loop:

- Reasoning
- Action
- Reasoning

This shift changed the role of the final stage.

Instead of treating `Generate` as the final production of a static report, the system should generate actionable debugging work:

- failure analysis
- `DEVICE_CHECK` items
- `CODE_CHECK` items

These checks are not decoration. They are the bridge between an initial hypothesis and evidence-based validation.

The intended loop becomes:

1. reason over the case, extracted signals, and knowledge base
2. propose a likely failure mechanism
3. generate concrete debugging checks
4. execute those checks against devices and code repositories
5. collect evidence
6. reason again using both the original case and newly collected evidence
7. either confirm the hypothesis, revise it, or stop with a blocked / human-needed outcome

This is the core transition in `parsifal-overlay`:

> from generating an analysis report  
> to running an evidence-seeking debugging loop

---

## What `DEBUG_STEPS` Really Means

In this design, `DEBUG_STEPS` is not just a prettier output format.

It is the first structured representation of the system’s next actions.

A useful `DEBUG_STEPS` artifact should contain at least three things:

- the current explanation or working hypothesis
- device-side checks needed to validate or reject that hypothesis
- code-side checks needed to validate or reject that hypothesis

This means `DEBUG_STEPS` is not the end of the workflow. It is an intermediate planning artifact inside a larger evidence loop.

That distinction matters.

If `DEBUG_STEPS` is treated as the final output, the system remains a reporting tool.  
If `DEBUG_STEPS` is treated as an execution plan, the system becomes a debugging agent.

---

## The Core Loop

At a high level, the core system loop should look like this:

1. **Case intake**
   - obtain Jira case context, attachments, and initial metadata

2. **Signal extraction**
   - extract meaningful signatures and observations from logs and artifacts

3. **Knowledge grounding**
   - retrieve relevant prior knowledge, patterns, platform facts, and references

4. **Hypothesis formation**
   - form one main explanation and possibly weaker alternatives

5. **Check generation**
   - generate `DEVICE_CHECK` and `CODE_CHECK` items tied to the current hypothesis

6. **Evidence execution**
   - run the checks through tools against devices and repositories

7. **Evidence evaluation**
   - compare the returned evidence against the hypothesis

8. **Decision**
   - confirm
   - revise and continue
   - stop as blocked
   - escalate to human review

9. **Summary and distillation**
   - summarize the final understanding
   - optionally draft a reusable KB entry from the resolved case

This loop is the real design center of `parsifal-overlay`.

---

## Why This Is Valuable

The technical value of this system is not just automation for its own sake.

Its real value is that it can convert repeated debugging practice into reusable structure.

Instead of treating each new case as a fully isolated incident, the system can learn to reuse:

- failure patterns
- evidence patterns
- diagnostic actions
- platform-specific qualifiers
- code-path associations
- recovery and workaround patterns

If done well, this reduces the effective cost of repeated work across platform and version combinations.

It also helps make implicit engineering experience more explicit. Many debugging decisions that currently live only in expert intuition can be turned into:

- structured checks
- evidence requirements
- reusable hypotheses
- knowledge base drafts

That is the beginning of a real knowledge flywheel.

---

## Beyond Single-Case Debugging

Once a system like this exists, its value is not limited to live issue handling.

It can also be used to process already resolved cases and turn them into reusable knowledge.

That suggests a second long-term use case:

- summarize resolved issues
- extract structured failure patterns and evidence patterns
- draft new KB entries
- attach platform/version qualifiers
- let humans review and merge them into the curated knowledge base

This matters because the best debugging system is not just a case solver. It is also a system that improves its future grounding material over time.

---

## Boundaries and Risks

The promise of this design is real, but so are the risks.

### 1. Evidence execution is harder than report generation
The main difficulty is often not reasoning itself, but reliable evidence collection:

- device connectivity may be unstable
- serial logs may be incomplete or noisy
- artifact quality may be poor
- repository state may vary by branch and version
- platform metadata may be missing or ambiguous

A reasoning system is only as strong as the evidence pipeline it can trust.

### 2. A plausible plan is not the same as an executable plan
A model can easily produce debugging steps that sound reasonable but are too vague, too broad, or not operationally grounded.

Checks must eventually become structured enough to support execution and evaluation.

### 3. ReAct loops can fail to converge
Without strong controls, the system may loop without adding meaningful new evidence.

This requires explicit limits, stop conditions, and blocked / human-needed states.

### 4. Automatic KB write-back can pollute the knowledge base
Resolved-case distillation is valuable, but it should not become uncontrolled automatic memory.

KB write-back should begin as draft generation with human review.

### 5. Platform and version qualifiers are essential
Many similar-looking failures do not share the same root cause across platforms, kernel versions, branches, or firmware states.

Any useful knowledge system in this domain must preserve those qualifiers.

---

## Design Direction

The long-term direction of `parsifal-overlay` is therefore not a generic chat agent and not merely a report generator.

It is a structured, tool-using, knowledge-grounded debugging system centered on:

- explicit hypotheses
- explicit checks
- explicit evidence
- explicit decision states
- bounded iterative reasoning
- human review where needed

In this view, the most important system object is not the report.

It is the evolving relationship between:

- a case
- a working hypothesis
- missing evidence
- planned checks
- collected evidence
- a decision about what to do next

That is the design center.

---

## Non-Goals

At least in its intended practical form, `parsifal-overlay` is not trying to be:

- an unrestricted autonomous agent
- a replacement for expert kernel engineers
- a fully automatic patch generation pipeline
- a system that assumes every case can be resolved without human intervention

Its purpose is narrower and more practical:

> reduce repeated debugging effort, improve evidence quality, and accelerate convergence on correct explanations.

---

## Conclusion

`parsifal-overlay` begins with a simple observation:

platform enabling work grows combinatorially, but debugging structure often does not.

That gap creates the opportunity for a system that combines:

- workflow orchestration
- knowledge retrieval
- structured reasoning
- tool-driven evidence collection
- iterative hypothesis refinement

The project started from a report-oriented reasoning flow.  
It now points toward a more useful goal:

> an evidence-seeking debugging system that can reason, act, re-evaluate, and help build a reusable body of engineering knowledge.
