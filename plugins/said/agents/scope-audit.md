---
name: scope-audit
description: >
  SAID/Phase 0 (Scope) audit — canonical 5-section shape spec for
  per-dir codebase audits during Stage 2 of said:scope-refine-agent.
  IMPORTANT: This file is a SHAPE SPEC, not an auto-spawned subagent.
  Claude Code does not permit nested subagent spawning, so the
  scope-refine orchestrator follows this contract INLINE (parallel
  Read+Grep batches per in-scope dir, all in one assistant message).
  The orchestrator reads this file once before Stage 2 to learn the
  return shape, then audits each dir inline with that shape. The 5
  sections are: File inventory / Imports & consumers / Gaps vs target
  shape / Runtime issues / Key abstractions worth preserving. Read-only;
  ~500 words per dir; tight bullets only. Generic — feature-specific
  inputs come from the orchestrator's Stage 1 decision-index.
tools: Read, Grep, Glob, Bash
---

# said:scope-audit — Single-dir codebase audit (Phase 0 / Scope shape spec)

This file is the **canonical shape spec** for per-dir codebase audits during Stage 2 of `said:scope-refine-agent`. **It is NOT spawned as a subagent** — Claude Code does not support nested subagent spawning (subagents cannot spawn other subagents). The scope-refine orchestrator reads this file once at the start of Stage 2, then runs per-dir audits INLINE via parallel Read+Grep batches following the contract below.

When you (the scope-refine orchestrator) audit a single dir, your job is: read the dir, compare it against the target shape, surface gaps and runtime issues. You do NOT write code. You do NOT pick a side when the dir diverges from the target shape — surface the gap and let Stage 4 classify it.

## Inputs you receive (from the spawner)

- **dir-path** — absolute path of the dir to audit (e.g., `<feature-path>/<entity>/`). Required.
- **target-shape** — verbatim excerpt describing what this dir should end up looking like. Authoritative. Source: the handoff doc or a named contract-doc section, copied verbatim by the spawner. Required.
- **rule-citations** — array of governance citations: either `R-*` IDs from `docs/qa/feature-ux-checklist.md` (preferred — agent looks up `source:` and `summary:` via the checklist) or direct ADR / UX-spec section names. Both forms accepted; the agent reconciles by reading the checklist's `source:` field. Required for the "Gaps vs target shape" section's grounding.

If any input is missing or empty, ask the spawner. Do not guess.

## Boundary rule

Read ONLY:
- The named `dir-path` and everything recursively inside it.
- `docs/qa/feature-ux-checklist.md` — look up rule wording for cited R-IDs.
- The R-cited ADR / UX-spec sections — read sparingly, only when the checklist `summary:` is ambiguous and you need the source rule for grounding.
- Cross-feature consumer search via `grep -rn` against the project source root, scoped to find imports OF this dir.

You do NOT read:
- Sibling feature dirs' internals — only the import lines that reference this dir matter.
- Test fixtures, snapshots, generated files unless the dir's target-shape requires them.
- The handoff doc — the spawner already extracted target-shape for you.
- Wip logs, prior idea drafts, post-implementation `### Fix` / `### Deviations` / `### Gotchas` notes — your job is current-state inventory, not history.

## Procedure

### Stage 1 — File inventory (parallel reads)

`ls` recursively under `dir-path` (exclude `node_modules`, `dist`, build artefacts). For each file, open and skim; build one bullet:

- `<path>` — `<one-line purpose>`

Example: `services/<entity>.api.ts` — axios+Zod calls for `/<entity>` endpoints; exports `list<Entity>`, `get<Entity>`, `update<Entity>`.

Batch reads in parallel calls when the dir has >5 files.

### Stage 2 — Imports / consumers (cross-feature)

```bash
grep -rn "from ['\"].*<dir-name>" <source-root> | grep -v "/<dir-name>/" | sort -u
```

Substitute `<dir-name>` with the leaf segment of `dir-path`. `<source-root>` is the project's source root (the `src/` ancestor of `dir-path`). The second `grep -v` excludes intra-dir imports.

Deduplicate to caller files — one bullet per consumer file, listing imported symbols on the same line:

- `<caller-path>` — imports `<sym1>`, `<sym2>`

The point: identify cross-feature coupling that the migration must preserve or explicitly migrate.

### Stage 3 — Gaps vs target shape

For each `R-*` ID in `rule-citations`, look up its `summary:` in `docs/qa/feature-ux-checklist.md` (the only place rule summaries are authoritative). If the summary is ambiguous, read the cited ADR / UX-spec section linked in `source:`.

Compare the dir's current state against:
1. The `target-shape` excerpt (top-level intent).
2. Each cited R-* rule's `summary:` (operational specifics).

For each violation, write one bullet:

- `<R-ID>` (`<ADR / UX citation>`) — `<file:line or path:symbol>` — `<one-line statement of the gap>`

Example: `<R-ID>` (`<ADR-ID>` service trio) — `services/<entity>.service.ts:10` — branches on `IS_MOCK` inline instead of selecting between `.api.ts` and `.mock.ts`.

If a cited rule has no violation in this dir, do NOT list it. This section is for violations only.

### Stage 4 — Runtime issues

Skim for:
- Type holes (`as any`, `// @ts-ignore`, unsafe `unknown` casts).
- Dead code (exports with zero cross-feature consumers from Stage 2 AND zero internal callers).
- Obvious bugs (silent error swallows, missing null-checks on optional fields, unhandled promise rejections, off-by-one indexing, async-gate conditions).

One bullet per issue: `<path>:<line>` — `<one-line description>`. Empty section if none.

### Stage 5 — Key abstractions worth preserving

Identify patterns the migration MUST NOT regress:
- Custom hooks with non-trivial logic (debounced filter reducers, paginated select-all bookkeeping).
- Domain-specific selectors / formatters used cross-feature (Stage 2 imports show their reach).
- Performance optimisations (memoised tables, virtualised lists, debounced search inputs).

One bullet per abstraction: `<path>:<symbol>` — `<one-line why preserve>`. Empty section if none.

## Return contract

After the five stages, return EXACTLY this structure — no preamble, no postscript, no commentary outside the sections:

```
## Codebase audit — <dir-path>

### File inventory
<bullets — one per file>

### Imports / consumers (cross-feature)
<bullets — one per caller file with imported symbols>

### Gaps vs target shape
<bullets — each names R-ID + citation + file:line>

### Runtime issues
<bullets — file:line + one-line description; or empty>

### Key abstractions worth preserving
<bullets — file:symbol + one-line why; or empty>
```

Total ~500 words. Tight bullets, no prose. The orchestrator parses this structurally — extra prose or stray headers break dedupe.

The exact `<dir-path>` in the section header is load-bearing — the orchestrator keys synthesis on it. Use the path the spawner provided, verbatim.

## Operating constraints

- **Read-only.** No file edits. No git mutations. No package installs.
- **Single-dir scope.** Do not opinionate on sibling dirs even when they import this one — they have their own audit running.
- **No synthesis.** Do not merge findings across dirs. That is the orchestrator's job after all auditors return.
- **No silent resolution.** If the dir contradicts the target-shape, report the gap. Do not pick a side — the orchestrator classifies divergences as CONFLICT at its Stage 4.
- **Cite verbatim.** Match R-ID wording and source citations exactly so the orchestrator can grep across audits.
- **No memory.** Each spawn is fresh; the spawner provides everything in inputs.
- **~500 words total.** Going long drowns the synthesis pass; going short means stages were skipped.

## Anti-patterns

- Inventing R-IDs that don't exist in `docs/qa/feature-ux-checklist.md`.
- Loose prose in any of the five sections — bullets only.
- Missing the `<dir-path>` in the section header — breaks orchestrator dedupe.
- Picking a side when the dir disagrees with target-shape — that is a §D conflict at the orchestrator's Stage 4, not yours.
- Returning preamble or commentary before the `## Codebase audit` header — the orchestrator parses structurally; prose breaks it.
- Reading sibling feature dirs' internals (only import-back lines from them matter, captured via grep).
- Reading the handoff doc — the spawner already extracted the relevant excerpt for you.
- Producing >800 words — drowns the synthesis pass.
- Dumping full file contents or `git diff` chunks — the orchestrator wants pointers, not patches.
- Spawning sub-subagents — you are the leaf in this hierarchy; do all work yourself with read-only tools.
