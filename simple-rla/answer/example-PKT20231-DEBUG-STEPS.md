# Example DEBUG_STEPS for PKT-20231

## Problem framing
On the RPL-S + BMG test platform, boot crashes in BIOS `integrated mode` and `hybrid mode` when the kernel command line forces an abnormal graphics-driver path:

- `modprobe.blacklist=i915`
- `xe.force_probe=*`

In this setup, BIOS exposes integrated-GPU-related PCIe/BAR resource context to the kernel, but the normal `i915` probe path for the RPL-S integrated GPU is disabled. The system is then pushed into a forced `xe` path, and the downstream failure surfaces as:

- `kernel BUG at drivers/gpu/drm/drm_gem.c:181!`
- `RIP: drm_gem_private_object_init+0xea/0xf0`

This should be treated as a likely wrong probe/binding/resource-path problem first, and only secondarily as a local GEM crash-site problem.

---

## Most likely direction
The most likely direction is:

> BIOS `integrated` / `hybrid` mode exposes integrated-GPU PCIe/BAR context; `i915` is disabled by `modprobe.blacklist=i915`; `xe` is force-enabled by `xe.force_probe=*`; therefore the system enters an abnormal probe/init path and later crashes in the downstream Xe/GEM initialization path.

So the first debugging priority is not “why `drm_gem_private_object_init` exists,” but:

1. why the system entered this path,
2. which GPU resource path was exposed,
3. which driver should have owned that path,
4. why `xe` ended up touching it,
5. and only then what invariant was violated before the BUG.

---

## Concrete DEBUG_STEPS

### 1. Lock in the strongest device-side comparison evidence
Validate and document the boot-behavior comparison between the failing and working kernel command-line configurations.

Required comparison:
- failing config:
  - `modprobe.blacklist=i915`
  - `xe.force_probe=*`
- working config:
  - remove both options and verify the system boots normally

Goal:
- establish that the failure is strongly coupled to driver-selection / forced-probe configuration, not just a generic Xe internal crash.

Expected evidence:
- device-side reproduction matrix showing:
  - BIOS mode
  - kernel command line
  - whether boot succeeds
  - whether BUG appears

---

### 2. Verify driver binding / probe ownership under failing vs working configs
Collect boot-time evidence showing which driver is expected to own the RPL-S integrated GPU and which driver actually attempts to probe it under the failing configuration.

Focus points:
- whether `i915` is prevented from binding because of blacklist
- whether `xe.force_probe=*` causes `xe` to probe a path that would not normally be entered
- which device/function is actually being bound or initialized in each configuration

Goal:
- prove that the crash is preceded by a probe/binding ownership change.

Expected evidence:
- boot log comparison for graphics-driver probe/bind messages
- driver/device ownership difference between failing and working command-line setups

---

### 3. Verify BIOS-exposed PCIe/BAR resource context in integrated vs hybrid mode
Inspect the failing setup from the device/resource point of view.

Questions to answer:
- in BIOS `integrated mode` and `hybrid mode`, what GPU-related PCIe/BAR resources are exposed to the kernel?
- are these resources tied to the RPL-S integrated GPU path?
- under the failing configuration, does `xe` end up interpreting or touching a resource context that does not match its expected ownership/model?

Goal:
- connect BIOS mode semantics to the later wrong probe/init path.

Expected evidence:
- resource/BAR visibility comparison across:
  - integrated mode
  - hybrid mode
  - working command-line config
  - failing command-line config

---

### 4. Trace the Xe caller path that reaches `drm_gem_private_object_init`
Once the probe/resource-path hypothesis is established, move to code evidence.

Inspect the Xe-side call chain that leads into:
- `drm_gem_private_object_init`

Focus on:
- which caller path is active in the failing configuration
- which object is being initialized
- whether that path is consistent with the expected device/resource ownership

Goal:
- identify the first Xe-side caller that turns the wrong resource/probe context into a concrete bad object/init path.

Expected evidence:
- code-path summary from Xe entry/caller path to the crash point
- candidate caller-side preconditions for safe `drm_gem_private_object_init`

---

### 5. Validate the violated precondition/invariant before the BUG site
Treat `drm_gem_private_object_init` as the crash endpoint, not the root-cause origin.

Inspect:
- object type / size / state / backing assumptions
- whether the caller-side object was valid for this path
- whether the object was created under resource assumptions that are only wrong because the system entered the abnormal `xe` path

Goal:
- show which invariant was violated immediately before the BUG and whether that violation is downstream of the driver-selection / BAR-path mismatch.

Expected evidence:
- a caller-side invariant checklist
- mapping from the wrong probe/resource path to the violated object/init assumption

---

## Unknowns
- whether the exposed PCIe/BAR context is directly incompatible with the forced `xe` path, or only becomes invalid later during object initialization
- whether the first semantic mistake happens at probe/bind time, resource interpretation time, or object-construction time
- which exact Xe caller path is the earliest trustworthy root-cause pivot before `drm_gem_private_object_init`
- how much of the observed failure is shared between `integrated mode` and `hybrid mode`, and how much is only an upstream trigger difference

---

## Why this path first
This path should be prioritized because the strongest currently known evidence is device-side and causal:

- with `modprobe.blacklist=i915` and `xe.force_probe=*`, the system crashes
- removing those options allows the system to boot normally

That comparison strongly suggests the primary debugging axis is:

- driver ownership
- forced probe behavior
- BIOS-exposed resource context

rather than starting from a narrow local interpretation of the GEM crash site alone.
