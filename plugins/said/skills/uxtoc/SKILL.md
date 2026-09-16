---
name: uxtoc
description: >
  SAID/Phase 2 (Architect) - descriptive table-of-contents
  for spec artifacts. Reads a scope.md, feature spec, unit spec, or
  feature working dir and emits a hierarchical outline (units -> containers
  -> elements, each element's attributes flattened to short nested bullets),
  driven by the lane grammar. Purely descriptive - no
  evaluation, no rule comparison, no gap flagging, no recommendations.
  Multi-unit features render one outline section per unit.
  Used at two positions: EARLY on a thin scope.md or unit stub to seed
  a design, or LATE on an authored spec to inspect it - same emit -> spot ->
  edit -> re-run loop (the design-seed use is detailed in the body). On a
  dir: unit-home lane that loop runs on the durable per-unit file; the
  feature toc.md there is a thin index, not the edit surface. Triggered ONLY by the
  explicit command "/said:uxtoc <path> [output=<file-or-dir>]". Default
  output is inline (chat); operator passes output= to write a file. NOT a
  spec generator - it mirrors what a spec (however thin) already states and
  never invents content. NOT build/runtime evaluation - that's
  said:review-ux (runtime) / said:review-qa.
---

# UX TOC

Read-only. Emits a structured outline of what a SAID spec artifact actually says - at element granularity, with each element expanded into its attributes per the loaded grammar's per-container schema (title, type, render, operator, variant, label, target, permission, ... - whatever the grammar names for that container).

Purpose: a tight feedback loop for spec authoring, at two positions in the chain. **Design-seed (early)** - run it on a thin `scope.md` or a unit stub; the outline mirrors what the stub states so far, so the containers / elements / attributes it does not yet mention are simply absent from the outline, and you fill them in against it. **Inspect (late)** - run it on an authored spec to read back exactly what it commits to. Same loop both ways: emit -> spot a missing attribute or wrong shape -> edit the spec -> re-run `/said:uxtoc`. No review-and-fix loop - the TOC carries no judgment, only what the spec says.

**On a `dir:` unit-home lane, the emit-against surface is the durable, not the feature `toc.md`.** There the design lives in the durable per-unit files `<unit-home>/<ID>.md` (already in the mirrored container/element/attribute shape), and those durables are what the accept-time gate reads - so to inspect or seed one unit, run uxtoc on its durable and edit the durable directly. uxtoc's feature-level `toc.md` on a `dir:` lane is a THIN INDEX (front matter + a per-unit pointer line, no bodies - see Pass 3), a manifest / navigation surface, NOT the attribute-level inspection surface. The emit -> spot -> edit loop above is the durable's; an `inline` lane keeps that loop on the `toc.md` itself (there the toc IS the design).

uxtoc supports your authoring loop by **mirroring** the spec; it does not **generate** the spec for you. The design comes from you - uxtoc reflects whatever the spec states, however thin, so you can see the holes and fill them in.

## When this fires

The operator invokes:

- `/said:uxtoc <path>` - outline to chat.
- `/said:uxtoc <path> output=<file-or-dir>` - write to that path. If a directory, the file is named `toc.md` inside it. If a file path, that exact file is written (prompt overwrite / suffix `-2` / abort if it exists).

`<path>` resolves to one of (the `docs/...` roots below come from `SAID.docs-root:` / `SAID.working:` on the `## Lane` block; no key -> HALT):

- a **unit spec** - one unit, at the grammar's `unit-home` (an inline `### <unit> <ID>` sub-section, or a file under the declared `dir:` unit-home).
- `docs/features/<FEAT-ID>.md` - feature spec; outline scope + every unit the spec references (inline `### <unit>` sub-sections AND, where `unit-home` is a `dir:`, the linked unit files).
- `docs/working/<feature>/scope.md` - scope only.
- `docs/working/<feature>/` - directory; glob `scope.md` + any linked unit files + any inline `### <unit>` sub-sections in sibling spec files.

## Out of scope

- No evaluation against ADRs or `docs/ux/*` frozen rules.
- No "should have X" recommendations.
- No proposing missing elements.
- No source-code reading - spec docs only.
- No mutation of the input spec.

## Pass 1 - Resolve + classify

1. Resolve `<path>`. If missing, abort with the path that wasn't found.
2. Classify: `unit` | `feature-spec` | `scope` | `dir`.
3. Ground in the template + the lane grammar (one parallel-Read batch):
   - `docs/features/template.md` - feature-spec shape (its unit sub-sections are the unit-spec shape). If the lane keeps durable per-unit specs under a `dir:` unit-home, read one as a shape exemplar.
   - The **lane grammar** - resolved from `SAID.docs-root:` + `/ux/feature-ux-grammar.md`, the SC-HEADER section selected by the lane's `SAID.surface:`; LOADed WHOLE + its `token,count` echoed. It declares the `unit` word uxtoc emits, the `containers` (in emit order), the per-container attribute schema, and the `## Machine-readable` attribute set. **On a surface-bearing lane the grammar is REQUIRED**: an absent grammar, or no section for the lane's surface, HALTs with a named redirect (author `docs/ux/feature-ux-grammar.md`, or set the feature `Surface: none`). The HALT is **surface-gated, never version-gated**: a lane that predates the grammar requirement HALTs loud with that redirect until it adopts a grammar (or declares `Surface: none`), rather than silently skipping the outline - there is no version escape hatch, because a silent skip is exactly the unverified-but-green gap the grammar requirement closes. A `Surface: none` feature skips the grammar (no outline to certify).
   - The **element-projection RULE** - `${CLAUDE_SKILL_DIR}/element-projection.md`, LOADed WHOLE + its VERIFY-TOKEN echoed (`UXP-R-1`): the medium-agnostic projection rule (a keyed item under a grammar container is one element; a key in the grammar's attribute set is an attribute group, not an element). Load it whole, never re-derive it from memory.

4. **Durable-spec shift-left (a `dir:` unit-home lane only).** When the grammar's `unit-home` is `dir:<path>`, as you resolve the units to mirror, WARN (advisory - surfaced to the operator, never a gate, never blocking the emit) when (a) a mirrored unit resolves to no `<unit-home>/<ID>.md` (a missing durable spec), or (b) a durable `*.md` present under `<unit-home>` has no matching `## <unit> <ID>` outline section (an orphan). This surfaces early, at emit, the class of mismatch the accept-time completeness check gates later - uxtoc already holds the paths, so it is the cheapest place to catch it. These are ADVISORY approximations, deliberately NOT the identical set the gate enforces (uxtoc keys off the outline headers it sees at emit; the gate keys off DECLARED units - a header carrying a grammar container): so the missing-durable warn (a) is BROADER than the gate (a bare sketch header draws it though the gate will not fail that header), while the orphan warn (b) is NARROWER (it fires only when no `## <unit> <ID>` header matches at all, so a durable under a prose/retirement header may pass uxtoc yet FAIL the gate). The point is to surface the class cheaply at emit, not to mirror the gate exactly. Medium-agnostic (resolved from the grammar's `unit-home` + `unit`); an `inline` unit-home has no durable dir and emits no such warning.

## Pass 2 - Extract

For each artifact in scope, walk in this order and capture only what the spec actually states:

**Per unit** (the grammar's `unit`):
- the unit `<ID>`, its title, and any unit-level specs the grammar's walk order names (e.g. a route, a permission gate, a layout, an invocation string) - only those the grammar declares, only where the spec states them.
- then walk the grammar's `containers` in their declared emit order; under each container, capture every element (a keyed line `- <key>:`) and, nested beneath it, only the attributes the grammar's per-container schema names for that container.

**Per scope.md**: Section A purpose, Section B target shape (units listed), Section C constraints - one-line gloss each.

**Section C constraint filter - surface-only.** Keep only constraints that shape the surface:
- Affordance gating / RBAC variance.
- Layout / responsive shape / composition.
- Presentation rules (a specific component required, placement, empty-state semantics).
- State / shareable-contract shape (e.g. a URL-state contract).
- Loading / error / empty rendering semantics.

Drop: file-naming conventions, codebase organization (which dir an entity lives under), scope boundaries (out-of-scope notes - those belong in Section B or in the scope.md's own out-of-scope section, not Section C of the TOC), tech-stack picks, build-tooling.

Do not invent. If the spec is silent on a sub-attribute (e.g., an element declares no `align`), omit the line entirely - do not write "align: not specified".

**Explicit-empty rule.** When the spec explicitly says a slot is empty with a reason (e.g. "no header actions in Phase 1 - create flow is Phase 2"), preserve it as `<slot>: none - <reason>`. Silent-empty (slot not mentioned) still drops per the rule above; explicit-empty is informative and survives.

**Key-collision warn (across a unit's containers).** DESIGNED is `(unit, key)`, so one field name keying two of a unit's containers collapses to one element - silently un-gating one. When a key would collide across two containers of one unit, WARN (advisory) and apply the qualify convention from the element-projection RULE (append the container name, e.g. `<key>-<container>`) so both stay distinct DESIGNED elements; never silently collapse. A genuinely unique key raises no warning.

**Owned-by reference warn (off-grammar ownership handoff).** When an explicit-empty reason declares the slot's content owned by another component (`<container>: none - owned by <component>`), WARN (advisory) that off-grammar ownership is ungatable: content genuinely reused across units belongs in its OWN standalone `## <unit> <ID>` section, gated once there, which the embedding unit references (it does not redeclare); single-use content is enumerated inline. Never leave an off-grammar `owned by` escape as the only record of a container's content. An ordinary explicit-empty (`none - <reason>` without an ownership handoff) raises no such warning.

## Pass 3 - Emit

**The emit is grammar-driven.** The unit header word is the grammar's `unit`; where a body is emitted (an inline lane's outline, below), under each unit walk the grammar's `containers` in their declared emit order, and under each container emit one keyed element with its attributes per the grammar's per-container schema. Renaming a container (or the unit) in the grammar changes the emit with no skill edit. (On a `dir:` unit-home lane no body is emitted into the toc at all - see the medium switch below.) There is NO `toc-checksum:` line - the outline is not sealed (the operator hand-edits it freely). Machine-written front-matter lines are stamped: `grammar:` (the section token, cross-checked at accept - an absent stamp FAILs), `last-revised:` (the feature-id, provenance, non-gating), and - on a `dir:` unit-home lane - a sealed `units: <ID1>;<ID2>;... (count: N)` line naming EVERY unit emitted, in emit order (`count` = the number of ids, so the line is unbluffable, exactly like the grammar's `count=`). The accept-time durable-spec check reads the DECLARED unit set from this line rather than inferring it from prose, so it must list every unit you emit - including one whose containers are all explicitly emptied (`none - <reason>`).

**The unit-home decides the outline body (the only medium switch).** An `inline` (or absent) unit-home has no durable per-unit files, so the `toc.md` IS the design substrate: emit the FULL outline (walk each unit's containers + elements + attributes, below). A `dir:<path>` unit-home keeps the design in durable per-unit files `<unit-home>/<ID>.md`, and the completeness gate parses those durables directly as the source of truth - so the `toc.md` on a `dir:` lane is a THIN INDEX, never a second body copy: emit the machine-written front matter (`grammar:`, `last-revised:`, and the sealed `units:` line) plus ONE `## <unit> <ID> - <title> -> <unit-home>/<ID>.md` header-with-pointer line per emitted unit, and NO container bodies. The `## <unit> <ID>` header level is kept (the gate cross-checks those headers against the sealed `units:` line; the `-> <unit-home>/<ID>.md` pointer is navigation, appended after the title). A full body in the toc would duplicate the durable and drift + bloat - the durable is the one place the body lives. Resolve the unit-home from the grammar (`unit-home`), never a hardcoded medium.

**The skill carries no surface vocabulary.** The concrete containers, their emit order, each container's attribute schema, and a worked example live in the loaded grammar (`## Containers` + `## Unit-spec stencil`) - the emit walks whatever that grammar declares. The generic shapes:

**Inline unit-home (full outline - the toc IS the design):**

```
# TOC: <feature or unit-set name>
Source: <input path>
grammar: <the grammar section token, e.g. UXG-CLI-1>
last-revised: <feature-id>
units: <ID>;<ID>;<ID> (count: 3)

## Scope  (only if scope.md is in input)
- Section A Purpose - <gloss>
- Section B Units: <ID>, <ID>, ...
- Section C Constraints:
  - <constraint> - <gloss>

## <unit> <ID> - <title>
- <unit-level spec>: <value>          (each unit-level spec the grammar's walk order names - e.g. a route, permission, layout, invocation - only if the grammar declares it and the spec states it)
- <Container>:                        (each container the grammar declares, in its emit order)
  - <element-key>:                    (one keyed line per element under the container)
    - <attribute>: <value>            (each attribute the grammar's per-container schema names for this container; omit any the spec is silent on)
  OR (explicit-empty):  <Container>: none - <reason>

## <unit> <next-ID> - ...
```

For a multi-unit feature input, repeat the `## <unit>` section per unit in the order the feature spec references them.

**`dir:` unit-home (thin index - the durable is the design):**

```
# TOC: <feature or unit-set name>
Source: <input path>
grammar: <the grammar section token>
last-revised: <feature-id>
units: <ID>;<ID>;<ID> (count: 3)

## Scope  (only if scope.md is in input)
- Section A Purpose - <gloss>
- ...

## <unit> <ID> - <title> -> <unit-home>/<ID>.md
## <unit> <next-ID> - <title> -> <unit-home>/<next-ID>.md
```

One header-with-pointer line per emitted unit, in reference order; NO container bodies (they live in the durable `<unit-home>/<ID>.md`). An emptied unit is still emitted as its header line (so the sealed `units:` count matches).

If `output=<path>`:
- Directory -> write `<path>/toc.md`. **Write-safety:** if `<path>/toc.md` already exists AND differs from a fresh emit, do NOT overwrite silently - prompt (overwrite / abort), protecting the operator's hand-edited substrate.
- File path -> write that path. If the file exists, ask: overwrite, suffix `-2`, or abort.
- **Stamps (machine-written front-matter).** Every written `toc.md` carries a `grammar: <token>` line (the grammar section's token, cross-checked by the completeness accept-check - an absent stamp FAILs) and a `last-revised: <feature-id>` line (provenance, non-gating). On a `dir:` unit-home lane it ALSO carries a sealed `units: <ID1>;<ID2>;... (count: N)` line naming every emitted unit (the accept-time durable-spec check reads the DECLARED set from it; absent on a `dir:` lane -> FAIL; `count` mismatch -> FAIL). No `toc-checksum:` line - the outline is not sealed; the operator hand-edits it freely.
- After write, print the resolved path to chat and a one-line summary (N units, M containers).

If `output=` omitted: print to chat only.

## Glossing discipline

- 2-3 words per gloss. Drop articles. Verb-led for actions ("save changes", "delete entry"), noun-led for data ("user email", "created date").
- **Verbatim tokens.** When the spec uses interpolation syntax (`${entity.var}`, `:paramName`, `{{var}}`), preserve the token exactly. Don't paraphrase `${user.email}` to "user email". Applies to routes (`/users/:userId`), titles (`Entity #${id}`), field labels, action labels.
- **Source-wording first.** Use the spec's own wording when concise; paraphrase only when the spec phrasing is long-form.
- Never editorialize ("clearly named", "needs work", "could be better").
- **Omit absent attributes.** Silence in the source becomes silence in the TOC.

## Fast-iteration discipline

The skill is designed for rapid spec editing - emit -> spot -> edit -> re-emit. To keep diffs meaningful between runs:

- **Deterministic ordering.** Units in spec-reference order. Within a unit: unit-level specs -> containers in the grammar's emit order. Within a container: elements in declaration order, and each element's attributes in the grammar's schema order.
- **No timestamps, no run metadata.** Header is just `# TOC: <name>` + `Source: <path>` - nothing else that changes between runs.
- **No recommendations.** Re-running after an edit should show only structural diffs from the spec change, never a different verdict on the same content.
- **Stable attribute names.** Use the canonical attribute names the grammar's schema declares (`title` not `header`, `render` not `renderer` or `cell`, `target` not `action` or `link`). Same name across all elements.

## Composition note - a design-seed loop by analogy (optional)

A *composition* of skills, outside `uxtoc` (adds no `uxtoc` behavior):
1. **Mirror exemplars** - run `uxtoc` on reference units for their outlines.
2. **Ideate by analogy** - draft a new unit's spec from them with a separate ideation skill, **outside** `uxtoc`.
3. **Mirror the draft** - run `uxtoc` on it to inspect.

Name no specific ideation skill as a dependency; `uxtoc` still only mirrors a spec (never generates, ranks, or evaluates).
