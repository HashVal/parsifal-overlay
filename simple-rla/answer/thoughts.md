# Thoughts on What DEBUG_STEPS Should Contain

This note summarizes what a useful `DEBUG_STEPS` document should emphasize, what it should avoid, and what should be treated as primary evidence when generating a provisional debugging plan.

---

## 1. DEBUG_STEPS is for debugging, not for writing a pretty RCA story
A common failure mode is to produce something that sounds like an RCA summary but does not actually help the next debugging action.

A good `DEBUG_STEPS` document should answer:
- what is the strongest current hypothesis?
- what evidence already supports it?
- what evidence is still missing?
- what are the next concrete actions to validate or falsify it?

A bad `DEBUG_STEPS` document often does this instead:
- starts from the crash function only
- lists plausible-sounding technical topics
- mixes strong and weak clues without ranking them
- fails to convert current evidence into targeted next steps

So the first principle is:

> `DEBUG_STEPS` should be organized around validation of the best current debugging hypothesis, not around writing a complete explanation.

---

## 2. What DEBUG_STEPS should contain

### 2.1 A clear problem framing
The framing should capture:
- the platform/test setup
- the trigger condition
- the driver/configuration conditions
- the failure surface

It should not only say where the crash happened.

Example of good framing:
- on a specific platform combination,
- under a specific BIOS mode,
- with specific kernel command-line parameters,
- the system enters a failing path and eventually crashes at a known point.

This is much more useful than simply saying:
- "kernel BUG at drm_gem.c:181"

because the latter only describes the endpoint.

---

### 2.2 A most-likely direction that is causal, not merely local
The “most likely direction” should identify the most plausible causal chain currently supported by evidence.

That direction should usually answer:
- what upstream condition forced the system into the failing path?
- what ownership / resource / probe mismatch is suspected?
- why the crash point is likely downstream rather than the true beginning?

A good direction often looks like:
- BIOS/resource exposure -> driver-selection constraint -> forced binding/probe path -> downstream crash

rather than:
- some function crashed, therefore that function is the root cause.

---

### 2.3 Concrete steps that are evidence-oriented
A good debug step should help obtain one of these:
- stronger device evidence
- stronger probe/binding evidence
- stronger resource-path evidence
- stronger code-path evidence
- stronger invariant evidence

A good step is not just a topic. It has a purpose.

For example:
- compare failing vs working kernel command-line behavior
- identify which driver owns the target device in each configuration
- verify what PCIe/BAR resources are exposed under the failing BIOS mode
- trace the caller path into the crash point
- validate the precondition violated before the BUG

Each step should have an implicit or explicit “what this proves” behind it.

---

### 2.4 Explicit unknowns
Unknowns are not a weakness. They are necessary.

A strong `DEBUG_STEPS` document should say what is still unresolved, for example:
- whether the wrong resource path begins at probe time or later
- whether a BAR/resource mismatch is primary or only contributory
- which caller-side precondition fails first

Unknowns help avoid two bad outcomes:
- pretending the RCA is already complete
- sending the debugger into unbounded open-ended searching

---

### 2.5 A “why this path first” section grounded in the strongest current evidence
This section is important because it communicates prioritization.

The best version of this section usually points to:
- the strongest comparison evidence already available
- the strongest mode/configuration delta already observed
- the strongest evidence that a given hypothesis is more valuable than competing ones

For example, if removing certain kernel command-line options makes the system boot normally, that should be elevated as primary guidance, not buried as a side note.

---

## 3. What DEBUG_STEPS should NOT contain

### 3.1 It should not confuse crash location with root-cause origin
This is one of the most common problems.

If the current evidence shows:
- a BUG in `drm_gem_private_object_init`

you still should not assume the right first step is “debug `drm_gem_private_object_init` itself.”

The crash function may only be:
- the first assertion site
- the first place a violated precondition becomes visible
- the last stage of a wrong upstream path

So:

> crash endpoint != root-cause origin

This distinction should be kept explicit.

---

### 3.2 It should not promote peripheral errors into top debug steps without causal support
Boot logs often contain many warnings/errors.
Examples include:
- ACPI errors
- USB probe errors
- PCI assignment noise
- module verification warnings

These should not automatically become top-level debug steps unless there is direct evidence they explain the fatal path.

Otherwise the plan becomes noisy and loses rank ordering.

---

### 3.3 It should not become a broad research to-do list
A weak `DEBUG_STEPS` document often says things like:
- compare all logs
- inspect everything around the subsystem
- search the KB more
- read more files

This is too broad.

A good debugging plan should narrow, not widen.

The purpose is to define the next highest-value checks, not to enumerate all theoretically related activities.

---

### 3.4 It should not ignore strong device-side evidence
If the investigator already knows a very important comparison result, such as:
- remove `modprobe.blacklist=i915` and `xe.force_probe=*` -> boot succeeds

then the `DEBUG_STEPS` must be reorganized around that fact.

Ignoring this kind of evidence leads to plans that are technically literate but operationally weak.

---

## 4. What should be treated as primary evidence
When available, the following types of evidence should be prioritized.

### 4.1 Device-side comparison evidence
This is often the highest-value evidence.

Examples:
- failing vs working kernel command line
- BIOS mode A vs BIOS mode B
- failure disappears when a force-probe or blacklist option is removed

Why it matters:
- it directly constrains causality
- it often reveals what changed the system path
- it is much stronger than a generic crash signature alone

---

### 4.2 Probe / binding / ownership evidence
This is the next most important layer when the failure likely involves device ownership.

Examples:
- which driver should normally bind
- which driver actually attempts to bind
- whether a normal path was disabled
- whether a forced path was taken instead

This layer is critical in mixed-platform / mixed-driver graphics debugging.

---

### 4.3 Resource-path evidence
This includes:
- PCIe resource exposure
- BAR visibility / assignment
- BIOS-exposed hardware mode differences
- whether the observed resource path matches the expected driver path

This is especially important when BIOS mode and driver forcing interact.

---

### 4.4 Code-path evidence
Code evidence is still necessary, but it should usually come after the system-path hypothesis is framed.

Useful code evidence includes:
- the caller path into the crash function
- the object type/state assumptions before the crash point
- the first invariant likely violated

Code evidence becomes most valuable when it is used to validate the higher-level system hypothesis, not when it is treated in isolation.

---

## 5. What should be treated as secondary evidence
These may still matter, but should not be promoted too early:
- unrelated boot noise
- weakly correlated warnings
- general subsystem tags with no causal tie to the fatal path
- broad “maybe this matters” signals

Secondary evidence should only be promoted if later analysis ties it directly to the main failure chain.

---

## 6. A good priority order for DEBUG_STEPS generation
For debugging-oriented plans, a strong default order is:

1. **device evidence**
   - what exact configuration/mode difference changes the outcome?

2. **probe/binding/ownership evidence**
   - which driver should own the device, and which driver actually does?

3. **resource-path evidence**
   - what device/BAR/resource context is exposed under the failing setup?

4. **code-path evidence**
   - which path reaches the crash point and under what preconditions?

5. **crash-site invariant validation**
   - what assumption is violated immediately before the BUG?

This order helps keep the plan causal and testable.

---

## 7. Practical guidance for generated DEBUG_STEPS
If a model is generating provisional `DEBUG_STEPS`, it should follow these practical rules:

- use the strongest existing comparison evidence as the anchor
- prefer shared fatal-path analysis over broad symptom collection
- treat BIOS mode / driver forcing / blacklist options as first-class evidence when they change system behavior
- narrow the next steps to the smallest set of high-value validations
- keep unknowns explicit
- avoid turning every observed error into a top-5 action item

---

## 8. Summary
A good `DEBUG_STEPS` document should:
- start from the strongest causal evidence already available
- identify the most plausible system-level failure path
- convert that path into concrete validation steps
- separate primary and secondary evidence
- use code evidence to validate the hypothesis, not replace it

A weak `DEBUG_STEPS` document usually fails because it:
- starts at the crash site only
- ignores configuration comparisons
- mixes noise with core evidence
- produces a broad technical checklist instead of a debugging plan

The practical rule is:

> Start from the strongest device-side comparison evidence, move through probe/binding and resource-path validation, and only then drill into the crash-site code path.
