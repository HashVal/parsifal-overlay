# KB Design

This document collects the current high-level Knowledge Base (KB) design for Tristan in one place for review.

The intent is not to finalize all KB details in this file.
Instead, this file serves as a staging document that gathers the current design into four major sections:

1. KB role and boundaries
2. KB content taxonomy
3. KB tool contract
4. KB agent usage

If review later shows that these sections should be split into separate documents, they can be promoted out into dedicated files.

---

# 1. KB Role and Boundaries

## Purpose

The KB in Tristan is a prior-knowledge grounding and reference system.

Its role is not singular. In Tristan MVP, the KB serves two distinct usage modes:

### 1. Framing support
The KB may help agents normalize and frame raw case material, for example by supporting:

- platform normalization
- subsystem or taxonomy disambiguation
- signal classification
- compact domain-oriented contextualization of raw inputs

This usage mode is primarily associated with Intake.

### 2. Explanatory grounding
The KB may also help agents compare current-case signals with prior knowledge, constrain explanation space, and support re-planning.

This usage mode is primarily associated with Hypothesis.

These two usage modes must remain distinct.
Framing support is not explanatory reasoning, and explanatory grounding is not a substitute for current-case evidence.

The KB is not the canonical record of the current case.
The canonical record of the current case is `CaseState`.

## Non-goals

The KB is not:

- a current-case fact store
- an execution evidence ledger
- a workflow engine
- a root-cause oracle
- a cross-case search system in MVP
- a second hidden reasoning substrate

The KB may support reasoning, but it must not silently become an alternate state layer or an implicit external decision system.

## Relationship to `CaseState`

`CaseState` remains the canonical structured state of the current investigation.
The KB is external to `CaseState`.

Agents may query the KB, cite KB objects, and use KB material to shape reasoning, but KB objects must not be bulk-imported into `CaseState` as a new canonical layer.

KB-derived material may enter `CaseState` only in constrained ways, such as:

- cited references inside hypothesis rationale or plan rationale
- compact retrieval traces if explicitly retained for auditability
- agent-owned structured outputs that interpret KB results

KB results may influence state only through agent interpretation, not through raw retrieval inclusion.

KB results must not directly become:

- current-case facts
- execution results
- `decision`
- `finalized_explanation`

This boundary is essential to preserve Tristan’s layer separation between current-case observation, explanation, execution, and closure.

## Access and ownership summary

At a high level, current Tristan direction is:

- Intake may use KB in a narrow framing-oriented role
- Hypothesis is the primary KB consumer for explanatory grounding and re-planning
- Probe does not use KB in normal MVP flow
- Judge does not use KB in normal MVP flow

The detailed agent access policy is specified later in this document.
This section only establishes the high-level ownership shape.

## Scope model

KB retrieval in Tristan is scoped, not unconstrained global search.

Scope is a design-level retrieval and visibility concept.
It defines meaningful retrieval boundaries and access boundaries within the KB.
Different agents may search different scopes, and not all KB content is uniformly visible to all agents.

In current Tristan MVP, the relationship between `kind` and `scope` is intentionally simple:

- a **kind** is a semantic content category containing one or more KB documents
- a **scope** is a retrieval/access grouping containing one or more kinds

In other words:

- `kind = [doc1, doc2, ...]`
- `scope = [kind1, kind2, ...]`

This document currently assumes only this simple model.
More complex mappings are out of scope for current design work.

A preferred MVP direction is to partition KB content in a way that reflects these scopes clearly.
One possible implementation is a directory-per-scope layout, but this document does not define implementation.
The key design point is that scope is the retrieval/access unit, while kind remains the semantic content category.

Scope should therefore be treated as part of both:

- the retrieval contract
- the access policy

This is especially important for Tristan, because scoped retrieval helps preserve role boundaries, reduce irrelevant retrieval noise, and make KB behavior more reviewable.

---

# 2. KB Content Taxonomy

## Taxonomy purpose

KB content in Tristan should be organized into a small number of explicit semantic kinds.

These kinds are not just content buckets.
They define what sort of reusable knowledge an object contains, what kind of question it is meant to answer, and which agent roles may normally access it.

For Tristan MVP, the goal is not to create a maximal taxonomy.
The goal is to create a small, semantically clean taxonomy that supports:

- Intake framing and normalization
- Hypothesis grounding and re-planning
- clear role boundaries

A small clean taxonomy is better than a large mixed taxonomy.

## Framing-oriented vs explanation-oriented content

A core Tristan distinction is whether a KB object primarily answers:

- **framing-oriented questions** such as:
  - what this module/platform/domain/signal is
  - how this term should be normalized
  - what structural or hardware context applies

- **explanation-oriented questions** such as:
  - what kind of issue this may correspond to
  - what known problem family may be relevant
  - what prior failure knowledge may matter

Framing-oriented content is more suitable for Intake.
Explanation-oriented content is more suitable for Hypothesis.

This distinction is one of the main ways Tristan preserves the boundary between structuring raw material and explaining the case.

## Core MVP kinds

Current Tristan direction is to keep the core KB taxonomy minimal.
The current core MVP kinds are:

- `module_brief`
- `platform_info`
- `domain_knowledge`
- `known_issues`

A transitional staging kind may also exist:

- `staging_notes`

### `module_brief`

A `module_brief` is a compact description of a module or component.
It is primarily structural and framing-oriented.

It is intended to answer questions such as:

- what this module does
- what domain or subsystem it belongs to
- how it relates to nearby modules or framework pieces
- what stable framing should be used when this module appears in case material

This kind maps naturally to the currently available LLM-generated module summaries.

`module_brief` should remain compact and structural.
It should not turn into an issue-pattern or playbook object.

### `platform_info`

`platform_info` is the carrier for platform and hardware factual information.
It is framing-oriented and should remain close to actual platform facts.

It is intended to answer questions such as:

- what hardware/platform context applies
- what board/SKU/generation/hardware composition is present
- how platform-specific naming should be normalized
- what low-level platform context is relevant for framing the case

This kind maps naturally to currently available script-derived hardware information.

`platform_info` should remain factual and context-oriented.
It should not become a container for explanatory heuristics or planning advice.

### `domain_knowledge`

`domain_knowledge` is a higher-level overview of Linux kernel driver/framework knowledge above the module level.

It is intended to answer questions such as:

- which modules belong to the same domain
- what the domain boundary and structure look like
- what framework-level context is relevant
- what important chains, requirements, or constraints apply within the domain
- what limited domain-level operational or debugging context may matter

This kind is useful because the current and planned KB content includes more than isolated module summaries.
Some knowledge naturally lives at the domain level rather than the individual module level.

Examples of intended `domain_knowledge` shape include:

- an overview of the audio domain
- a summary of how a power-domain probe chain works
- key requirements or expectations around S3/S4/S0ix behavior

However, `domain_knowledge` is also the easiest kind to make too broad.
It may include limited domain-level operational or debugging context, but it must remain primarily structural and overview-oriented.
It must not become a generic dumping ground for:

- issue catalogs
- playbooks
- workaround collections
- full RCA narratives
- arbitrary mixed notes

Its purpose is to provide higher-level domain framing plus limited operational context, not to absorb all other KB semantics.

### `known_issues`

`known_issues` is a KB kind for known issue knowledge.

In current Tristan MVP, this kind is centered primarily on known issues outside normal module-level framing content, especially at layers such as:

- BIOS
- IFWI
- firmware
- hardware
- board/platform-adjacent low-level environment

It is intended to capture:

- known issue identity
- affected scope or layer
- triggering conditions
- observable symptoms or manifestations
- compact references or supporting notes

In current MVP, `known_issues` should not become a generic catch-all for:

- module-level summaries
- domain structural knowledge
- playbooks
- workaround catalogs
- prior RCA narratives

This kind may evolve later, but its current semantic center should remain narrow enough to avoid becoming a mixed-content bucket.

### `staging_notes`

`staging_notes` is a transitional content kind for KB material that has not yet been confidently categorized.

It exists for curation convenience, not as a stable semantic retrieval kind.
Its purpose is to hold material temporarily before it is moved into one of the core kinds.

`staging_notes` should not become a permanent miscellaneous bucket.
Content should be moved out of staging once its semantics are clear enough to classify.

In normal MVP flow, `staging_notes` should not be part of the default Intake-visible retrieval surface.
However, it may still be visible to Hypothesis as transitional content rather than as a fully stabilized semantic kind.

## Intake-visible vs Intake-hidden kinds

Current Tristan direction is that Intake should not be limited only by prose rules.
It should also be limited by KB kind or scope visibility.

### Intake-visible by default
- `module_brief`
- `platform_info`
- `domain_knowledge`

### Intake-hidden in normal MVP flow
- `known_issues`
- `staging_notes`

This split is intentionally conservative.
It protects the distinction between framing raw material and explaining the case.

## Hypothesis-visible kinds

The Hypothesis agent is the primary explanatory KB consumer in Tristan MVP.

Current working assumption:
- Hypothesis may read all normal KB document kinds in MVP, unless future restrictions become necessary.

That means Hypothesis may normally access:

- `module_brief`
- `platform_info`
- `domain_knowledge`
- `known_issues`

`staging_notes` remains different.
It is not part of the normal stable KB retrieval surface and should not be treated as a normal semantic kind for agent reasoning.

## Taxonomy design principle

The taxonomy should remain semantically clean.

That means:

- framing-oriented kinds should remain framing-oriented
- explanation-oriented kinds should remain explanation-oriented
- transitional staging content should remain transitional
- no kind should become a semantic junk drawer

This matters because clean retrieval depends not only on tool behavior, but also on object-kind purity.
If a kind becomes semantically mixed, scope-based retrieval and role-based visibility become much weaker.

## MVP conservatism

Tristan does not need a maximal KB taxonomy at the start.

For MVP, the taxonomy only needs to be rich enough to support:

- Intake framing and normalization
- Hypothesis grounding and re-planning
- clear role boundaries

It is acceptable for the first version of the taxonomy to remain incomplete, as long as its semantic distinctions are clean.

A small clean taxonomy is better than a large mixed one.

## Open questions

The following content-taxonomy questions remain open:

- whether `domain_knowledge` needs stronger internal constraints to avoid semantic sprawl
- whether some future signal-focused content class should be split out later
- whether `known_issues` should eventually be narrowed further or split into sub-kinds
- how strongly kind visibility should be enforced by tools versus documented as policy
- whether this combined document should later split into multiple dedicated KB design documents

---

# 3. KB Tool Contract

## MVP tool surface

The current preferred KB tool surface for Tristan MVP is intentionally small:

- `kb_search`
- `kb_get`

This is deliberate.
Tristan currently needs legible, controllable, reviewable KB use more than a richer retrieval abstraction.

The following are explicitly deferred in MVP:

- `kb_ground`
- any dedicated grounding agent
- any automatic harness-driven KB retrieval outside explicit agent reasoning

## Tooling goals

KB tooling in Tristan should support the following goals:

- scoped retrieval rather than unconstrained global search
- compact and reviewable results
- explicit visibility boundaries aligned with agent access policy
- stable references to KB objects
- separation between retrieval and reasoning

KB tools should help agents find and cite relevant prior knowledge.
They should not become a second reasoning layer.

## `kb_search`

### Purpose

`kb_search` is the primary KB discovery tool.

Its role is to find potentially relevant KB objects within one or more explicit scopes, using a query derived from structured current-case material.

It should support discovery, not conclusion.

### High-level contract

`kb_search` should search over explicit KB scopes rather than the entire KB by default.

Scope is part of the query contract.

A query should conceptually include:

- one or more scopes
- one or more search terms or structured query components
- an optional result limit

The exact wire schema may evolve, but the design-level contract is:

> search is explicit, scoped, and structure-aware

rather than:

> freeform full-KB search with unclear boundaries

### Query model

A full final query schema is not required at this stage, but the intended query model is already clear.

A query may contain ingredients such as:

- exact observable strings
- normalized platform labels
- normalized subsystem/domain labels
- compact symptom phrases
- other structured framing fields from `CaseState`

The tool may support either:
- a structured query object
- or a simpler query interface that still preserves scope explicitly

In either case, the design intent remains the same:
query construction belongs primarily to the agent side, while the tool provides retrieval mechanics and guardrails.

### Retrieval behavior

For MVP, `kb_search` should use a scoped, metadata-aware lexical retrieval model.

This means:

- scope filtering happens before broad retrieval
- metadata and stable object fields are preferred over naive body-only search
- alias expansion or equivalent lexical support may be used
- retrieval should remain explainable
- search should not depend on opaque semantic ranking as the primary mechanism in MVP

This design is compatible with simple implementations such as directory-scoped search with field-aware matching, but this document does not prescribe implementation.

The key design point is that retrieval should remain:
- scoped
- explainable
- reviewable
- aligned with KB object semantics

### Result format

`kb_search` results should be compact and structured.

Each hit should ideally include:

- object id
- object kind/scope
- title
- summary or compact snippet
- source reference/path
- matched terms or matched fields
- optional retrieval score or ordering hint

The result should help an agent answer:
- what matched
- why it matched
- what object this refers to

The result should not try to tell the agent what conclusion to draw.

### Visibility enforcement

`kb_search` should help enforce agent visibility boundaries.

This is especially important for Intake.

Examples of the intended design effect:

- Intake may search framing-oriented scopes such as `module_brief`, `platform_info`, and `domain_knowledge`
- Intake should not normally search `known_issues`
- Hypothesis may search all normal KB kinds, including `staging_notes`
- `staging_notes` remains transitional content even when visible

This enforcement should not rely only on agent self-restraint.
Tooling should be part of the boundary-preservation mechanism.

## `kb_get`

### Purpose

`kb_get` is the KB expansion tool.

Its role is to fetch one selected KB object in fuller form after search/discovery has identified it as potentially useful.

### High-level contract

Input:
- stable KB object reference, normally object id

Output:
- full object metadata
- full object content/body
- stable source reference/path

`kb_get` should retrieve and expose the selected object.
It should not add interpretation, summarization, or reasoning on top of the object unless such behavior is explicitly introduced in a future separate tool.

### Why `kb_get` matters

Separating `kb_search` from `kb_get` helps Tristan preserve:

- compact search results
- explicit object selection
- lower prompt noise
- clearer auditability of what was actually consulted

Without this split, retrieval easily turns into broad prompt stuffing.

## `staging_notes` handling

`staging_notes` is special.

It is not a normal fully stabilized semantic kind, but it may still be visible to Hypothesis.

Therefore tooling should treat it differently from core kinds in two ways:

1. Visibility:
   - not normally Intake-visible
   - Hypothesis-visible in normal flow

2. Semantics:
   - transitional content
   - lower stability than core kinds
   - not a reason to weaken the core taxonomy

This does not require a different tool.
It only requires that search and retrieval preserve kind/scope identity clearly so that agents know what kind of object they are consulting.

## Tool-level non-goals

KB tools should not:

- generate hypotheses on behalf of agents
- directly produce current-case facts
- directly produce execution truth
- directly produce closure judgments
- silently expand into cross-case search in MVP
- silently perform full-KB grounding when only scoped retrieval was requested

In other words, KB tools may support reasoning, but they must not absorb reasoning responsibility.

## Relationship to agent guides

The tool contract does not replace agent usage guidance.

Tooling defines:
- what can be searched
- how retrieval is scoped
- what results look like
- what visibility constraints are enforced

Agent guides define:
- when an agent should search
- how an agent should formulate queries
- how an agent may use KB results
- what an agent must not infer from KB results alone

This separation is intentional.

## Open questions

The following tool-contract questions remain open:

- the exact query schema for `kb_search`
- how much structure should be explicit in the request vs derived inside the tool
- how strongly visibility should be hard-enforced by tooling in MVP
- whether future lexical ranking improvements are needed
- when, if ever, a `kb_ground`-style tool should be introduced later

---

# 4. KB Agent Usage

## Agent access policy

### Intake agent

The Intake agent may use KB tools, but only in a narrow framing-oriented role.

Permitted purposes include:

- platform normalization
- subsystem or taxonomy disambiguation
- signal classification and framing support
- compact reference lookup needed to structure raw case material

The Intake agent must not use KB retrieval for:

- broad issue-pattern search
- hypothesis generation
- causal ranking
- probe selection or planning
- converting KB matches into current-case facts

In addition to semantic restrictions, Intake-visible KB content should be restricted to framing-oriented scopes or kinds.
Intake should not have normal access to explanation-oriented or planning-oriented KB objects.

The Intake agent must not imply explanatory alignment with prior patterns.

This restriction is intentional.
It preserves Intake as a structuring and normalization agent rather than an explanatory agent.

### Hypothesis agent

The Hypothesis agent is the primary KB consumer in Tristan MVP.

It may use KB tools to:

- retrieve relevant KB material across available scopes
- compare retained current-case material with prior knowledge
- support hypothesis generation, revision, elimination, and ordering
- support re-planning and rerun reasoning

Hypothesis may also inspect transitional staging content when available, but such content should be treated as lower-stability KB material rather than as a fully stabilized semantic kind.

The Hypothesis agent may use KB retrieval to expand or constrain explanation space, but it must not collapse explanation space solely by KB similarity without current-case support.

KB matches must not be treated as current-case facts, and KB similarity must not be treated as closure proof.

This is the natural home of KB in Tristan, because KB is primarily a source of prior explanatory and planning knowledge.

### Probe agent

The Probe agent does not use KB tools in normal MVP flow.

Its responsibility is to execute planned code-side or device-side checks and return current-case execution truth, blockers, and artifacts.

Any KB influence on Probe behavior should already have been absorbed upstream into framing, hypotheses, or plan design.

Probe must not become a second grounding or re-analysis stage.

If future narrow static lookup support is needed for execution ergonomics, it should be introduced as a separate dedicated mechanism rather than broad KB retrieval.

### Judge agent

The Judge agent does not use KB tools in normal MVP flow.

Its responsibility is to adjudicate closure based on retained case state, including facts, hypotheses, execution results, and decision conditions.

If retained state is insufficient for closure, Judge should request rerun or help rather than retrieve prior knowledge to compensate.

Judge must not use KB similarity or pattern resemblance as a substitute for current-case closure.

### Additional agents

No additional KB-consuming agent is required in current Tristan MVP.

In particular, Tristan MVP does not require:

- a dedicated KB agent
- a dedicated grounding agent
- automatic harness-driven KB retrieval outside explicit agent reasoning

KB access is therefore intentionally scoped to:

- Intake for narrow framing-oriented use
- Hypothesis for explanatory grounding and re-planning

and to no other agents in normal MVP flow.

## Query construction guidance

Query discipline belongs primarily to the agent side, not primarily to the tool side.

Allowed agents should construct KB queries from structured current-case material rather than broad freeform prose whenever possible.

Preferred query ingredients include:

- exact observable strings
- normalized platform or subsystem labels
- compact symptom phrases
- other structured framing fields already present in `CaseState`

The tool may support structure-aware retrieval, alias expansion, and fielded lexical matching, but the agent remains primarily responsible for query construction.

This is intentional.
It keeps problem formulation with the agent rather than silently moving it into the tool layer.

## How KB results may be used

Allowed agents may use KB hits to:

- support framing and normalization (Intake)
- support hypothesis formation, revision, and re-planning (Hypothesis)

KB hits should generally affect retained state only through agent-owned structured outputs, such as:

- intake framing outputs
- hypothesis rationale or support references
- plan rationale or support references
- compact retrieval traces if intentionally retained for auditability

KB hits may support or constrain reasoning, but they do not become current-case evidence merely by being retrieved.

## What KB results must not do

KB hits must not be treated as:

- current-case facts
- execution truth
- direct closure justification
- automatic workflow-transition authority

KB retrieval may support reasoning, but it must not silently replace observation, execution, or adjudication.

## Review status

Open questions still under review include:

- whether `domain_knowledge` needs stronger internal authoring constraints to prevent semantic sprawl
- whether `known_issues` should remain centered on BIOS/IFWI/hardware-adjacent layers or later split further
- how strongly kind/scope visibility should be hard-enforced by tooling versus documented as policy
- how `staging_notes` should be curated and reclassified over time
- how much KB influence should be compressed into plan items for Probe consumption
- whether this combined document should later split into multiple dedicated KB design documents
