---
name: architect
description: >
  SAID/Phase 2 (Architect) — turns a refined `scope.md` (Phase 1 output)
  into a feature spec + append-only tasks log via three-pass authoring
  (gather → author → plan). The spec is a recreation contract: a fresh
  implementer reading the spec alone must be able to rebuild the feature
  within its scope. Triggered ONLY by the explicit command
  "/said:architect [<scope-path>] [project-type=web|server] [output-name=<custom>]".
  NOT for incremental updates to an already-architected feature — those use
  direct task append per `docs/features/template-tasks.md` discipline.
---

# Feature Architect — Phase 2 (Architect): Spec + Tasks Authoring

This skill turns Phase 1's refined `scope.md` into the two artifacts Phase 3 (Implement) consumes: a feature spec at `docs/features/<feature>.md` and an append-only tasks log at `docs/features/<feature>.tasks.md`. Phase 1 is the input boundary (read `said:scope-grill` / `said:scope-refine` outputs); Phase 3 is the output boundary (`/said:impl` consumes what this skill writes).

The skill itself is the orchestrator — there is NO separate agent. You — the main agent — drive three sequential passes (**gather** → **author** → **plan**) within ONE invocation.

## Core principle — the spec is a recreation contract

A feature spec is a **recreation contract**. A fresh implementer reading the spec alone — no tasks file, no working folder, no git log — must be able to rebuild the feature within its scope and arrive at functionally equivalent shape/behavior. The spec answers **WHAT**; HOW lives in the tasks file; cross-cutting lessons-learned live in ADRs.

This principle drives every authoring decision in Pass 2. If a paragraph describes HOW (file paths, function signatures, sequencing, folder-tree diagrams, past-tense work-log), it doesn't serve recreation and belongs in the tasks file by construction.

**Project-type duality.** Web-app projects (`docs/ux/` exists) get UI/UX Requirements + visual parity per piece; server-app projects drop UI/UX and expand API Integration. Auto-detected in Step 0 or overridden via `project-type=` flag.

## When this fires

The user invokes:

- `/said:architect` — default scope-path = `docs/working/<feature>/scope.md` for the most recent `<feature>` working dir.
- `/said:architect <scope-path>` — explicit scope.md path.
- `/said:architect <scope-path> project-type=web` — override auto-detection.
- `/said:architect <scope-path> output-name=<custom>` — override the default `<feature>` (derived from working-dir leaf) for output filenames. Useful for sub-phased umbrella specs (e.g., `output-name=<feature-id>-phaseB`).

If the operator's request is to **add a new task** to an already-architected feature ("add a task for X", "amend the tasks log") — redirect to `/said:add-task` (the canonical entry point for backlog additions).

If the operator's request is to **propagate new info** into an existing feature — BE handoff result, scope refinement, mid-implementation discovery, "process X and update spec + tasks", etc. — do NOT bounce. This is direct-edit work, not re-architecture. Proceed: read the source doc, list the deltas, apply surgical edits to spec + tasks per `docs/features/template-tasks.md` amendment carve-out (uncommitted task → amend in place + `### Deviations` note; committed task → append a new task ID). Report the diff. The 3-pass authoring flow below runs ONLY for INITIAL spec + tasks creation from a `scope.md`.

If `scope.md` doesn't exist or §D is non-empty — BLOCK. Phase 1 is incomplete. Redirect: "scope.md §D non-empty (Phase 1 incomplete). Resolve §D items via `/said:scope-refine` regenerate or hand-edit, then re-run `/said:architect`."

## Step 0 — Preflight

Resolve inputs and ground in calibration sources before the operator interaction starts:

1. **Resolve scope-path.**
   - Path given as arg → verify with `ls <path>`. If missing, BLOCK and ask operator.
   - No path given → list `docs/working/*/scope.md`; if exactly one, use it; if multiple or zero, ASK the operator which feature.
2. **Verify §D empty.** Read scope.md, locate `## §D`, confirm it's empty (or every item explicitly marked "defer to Phase 2 (Architect)" with reasoning). Otherwise BLOCK.
3. **Detect project type.** Bash check: `[ -d docs/ux ] && echo web || echo server`. Operator override (`project-type=...` flag) takes precedence.
4. **Derive feature name.** Take the leaf segment of the working dir (`docs/working/<feature>/scope.md` → `<feature>`). Confirm with operator only if ambiguous.
5. **Resolve output paths.**
   - Default spec: `docs/features/<feature>.md`. Default tasks: `docs/features/<feature>.tasks.md`.
   - For sub-phased features, operator may pass `output-name=<custom>` → `docs/features/<custom>.{md,tasks.md}`.
   - If either exists already, BLOCK and ask: "Spec exists at `<path>`. Overwrite, suffix `-2`, or abort?"
6. **Load calibration contracts** (parallel reads):
   - `docs/features/template.md` ★ — **the structural contract**. Its `^## ` headers are the spec section list, in order. Pass 2 iterates this list; the skill does NOT carry a parallel section recipe.
   - `docs/features/template-tasks.md` — tasks template (Pass 3 reads in full for authoring discipline).
   - Project's `CLAUDE.md` — for project-specific spec conventions, if any.

Don't load anything else upfront — the operator's clarifying answers in Pass 1 will reveal which additional ADRs / UX specs the scope.md cites.

## Pass 1 — Gather

> **Stance: extract structured information from scope.md and operator answers. Produce an intent ledger. Do NOT write the spec — that's Pass 2. The ledger is data; the spec is shape.**

Procedure:

1. **Batch global clarifying questions** (one batch, up front):
   - **AC form.** Gherkin (end-user behavior parameterized across inputs) vs bullets (shape-only / structural / refactor / data-layer-only). Mixed acceptable when pieces differ.
   - **Story type.** User Story (default — end-user-visible behavior) vs Developer Story (zero end-user behavior change — shape-only feature, refactor, infra).
   - **Task granularity.** Per-feature-dir default (one task per piece-of-scope). Override only when a single piece has 5+ unrelated AC clusters that can't land in one PR.

   Wait for `ANSWERS:` line before continuing.

2. **Extract the intent ledger from scope.md.** Walk scope.md once. Populate the ledger structure below. Each entry is a fact (data), not a spec sentence.

   ```
   Pieces of scope: [from §B Per-piece scope — one entry per piece]
   - <piece-name>: <one-line summary of what the piece commits to>

   Artifacts cited: [walk scope.md, pull every distinct path/anchor]
   - ADRs: [path1, path2, ...]
   - UX specs: [path1, path2, ...]
   - Upstream specs: [external spec paths — e.g. prototype/docs/specs/...]
   - Related features: [docs/features/<FEAT-ID>.md, ...]
   - Target code dir: [src/features/<dir>/, ...]

   Screens / surfaces touched: [from §B + §Visual contract]
   - <ScreenName>: <what changes / what it shows>

   Endpoints consumed / produced: [from §A wire captures + §Cross-cutting]
   - <METHOD> <path> — <purpose>

   Governing rules invoked: [frozen-rule anchors that govern shape]
   - <spec>#<rule> — <one-line why it applies>

   Constraints inherited: [from §C Cross-cutting + §E Resolved annex]
   - <one-line constraint>

   Explicit non-goals: [from §B Boundaries (Sacred / out-of-scope) + §C]
   - <one-line non-goal>

   Story type: <User Story | Developer Story>
   AC form: <Gherkin | bullets | mixed-per-piece>
   ```

3. **Pause for operator review.** Brief: "Intent ledger extracted. Pieces: `<n>`. Artifacts: `<n>`. Screens: `<n>`. Endpoints: `<n>`. Governing rules: `<n>`. Ready to author? Reply OK or flag missing/wrong entries."

## Pass 2 — Author

> **Stance: write the spec by running one procedure per template section, in template order. The intent ledger is the ONLY content source. The template is the structural contract — its sections, in its order, are what the spec carries. Anything not landing in a template section is HOW signal — picked up by Pass 3 (the tasks file).**

Procedure:

1. **Read `docs/features/template.md`.** Extract `^## ` headers in order. That ordered list IS the spec section list.
2. **For each section in template order, run its named procedure** (below). Procedures populate from the intent ledger.
3. **After all sections drafted, run the recreation-contract self-test.**
4. **Write spec to `docs/features/<feature>.md`** once the test passes.

### Section procedures

#### `## Context to load alongside this spec`

Take `Artifacts cited` from the intent ledger. Dedupe. Order: ADRs → UX specs → upstream specs → related features → target code dir → tasks-file pointer (`docs/features/<feature>.tasks.md`).

Output one bullet per artifact: `<path> — <≤8-word reason this artifact governs the feature>`. The single highest-leverage artifact (the one the implementer must read first) carries `★` after its path.

Cap: 12 bullets. If `Artifacts cited` exceeds 12, drop the lowest-leverage entries — they live in scope.md, which the implementer reads if they need deeper context.

No sub-section groupings ("Working docs", "Conventions", "Out-of-scope ADRs"). No `docs/working/` paths — working folder is transient operator workspace, not a durable spec citation.

Natural size: 6–12 lines.

#### `## What & Why`

Compose two paragraphs.

Paragraph 1 — Story (form per intent ledger):
- **User Story:** `As a [user], I want [goal] so that [benefit].` One sentence.
- **Developer Story** (when ledger Story type = Developer): `As [role], I want [shape outcome] so that [downstream consumer benefits].` Same form.

Paragraph 2 — Business Value: one paragraph (3–5 sentences) answering "why this matters now". If the feature inherits a substrate (prior phase, BE migration, upstream spec), that inheritance is 1–2 sentences inside this paragraph — never a separate Inheritance section.

Optional `**Explicit non-goals.**` inline list after the two paragraphs: ≤ 5 one-line bullets. Each names what is explicitly NOT in scope. Source: `Explicit non-goals` in the intent ledger.

Natural size: 8–15 lines.

#### `## Requirements`

Three sub-sections, each with its own procedure.

##### `### Functional Requirements`

For each entry in `Pieces of scope` (intent ledger), produce ONE outcome bullet:
- Present tense: "**When the feature is built, [observable end-state].**"
- Describes what a user/integrator observes — never what an implementer does.
- Cites governing ADR / UX-spec / external spec inline (anchor only — `lists.md #26`, not paraphrase).
- No file paths in bullet text. A fresh implementer derives files from the cited ADRs + existing codebase shape; the spec doesn't enumerate them.
- No past tense, no phase numbering, no `[x]` Done boxes. The spec is a forward contract; status lives in the tasks file.

Natural size: 4–8 bullets, one line each.

##### `### UI/UX Requirements` (web projects only — skip for server)

For each entry in `Screens / surfaces touched`, ONE bullet: `**<ScreenName>** — <what it shows> per <ux-spec>#<rule>`. Anchor only — never paraphrase the cited rule.

Natural size: 3–6 bullets.

##### `### API Integration`

For each entry in `Endpoints consumed / produced`, one line: `- **<METHOD> <path>** — <purpose>. Wire shape: <upstream spec>#<section>.`

If the feature introduces no new endpoints, state it in one line ("This feature introduces no new endpoints; consumes `<n>` from `<upstream spec>`"). Then optionally enumerate consumed endpoints, one per line.

No JSON envelope code samples. No Zod schema source. No `*.service.api.ts` excerpts. Those live in the upstream spec and the implementation; this section cites them.

Natural size: 3–8 lines.

##### `### Performance`

Up to 2 measurable bullets. Each cites a target (render time, bundle size, data volume cap). Omit the sub-section if none apply.

Natural size: 0–2 bullets.

#### `## Acceptance Criteria`

For each entry in `Pieces of scope`, ≤ 3 acceptance statements. Each is observable from outside the feature:
- User-visible behavior (user does X, sees Y)
- Integrator-visible API behavior (caller sends X, gets Y)
- Measurable system property (response time, render count, bundle delta)

Form per intent ledger AC form:
- **Gherkin scenarios** (`Given / When / Then`) when the feature parameterizes end-user behavior across multiple inputs. Cap: ≤ 3 scenarios per piece, ≤ 3 pieces gherkined.
- **Bullets** when shape-only / structural / refactor / data-layer-only. Cap: ≤ 5 outcome bullets per piece.
- **Mixed**: each piece picks its form; declare at section top.

Natural size: ≤ 15 lines total. Multi-piece features may go to 25 lines if Gherkin scenarios are essential.

#### `## Definition of Done`

Reference CLAUDE.md quality gates with a one-line pointer ("Standard repo quality gates per CLAUDE.md:"). List any feature-specific gates that go beyond the standard set (visual parity walk against a named reference, specific test path that must pass).

Natural size: 4–8 bullets.

#### `## Feature Tasks`

Placeholder for Pass 3. Write a one-line note: "Detailed task log: [`<feature>.tasks.md`](<feature>.tasks.md). Status table generated in Pass 3."

Pass 3 fills the table when tasks are planned.

#### `## Related`

4–6 bullets:
- 2–3 highest-leverage ADRs (already in Context-to-load — repeat for at-a-glance navigation).
- Upstream feature spec (if any).
- Downstream feature spec (if any planned).
- Tasks log pointer.

No `docs/working/` pointers.

Natural size: 4–6 bullets.

### Recreation-contract self-test

After all sections are drafted, read the draft as a cold implementer. Answer **yes** or **no** for each of the 5 questions below. Each question anchors to a verifiable property of the spec text — not a vibe.

1. **Screens / surfaces.** Can I list every screen / surface this feature creates or changes by name?
   *Verifiable:* every entry in `Screens / surfaces touched` (ledger) has a `**<ScreenName>**` mention in UI/UX Requirements (web) or Functional Requirements (server).
2. **Endpoints.** Can I list every endpoint consumed or produced?
   *Verifiable:* every entry in `Endpoints consumed / produced` (ledger) appears as `<METHOD> <path>` in API Integration.
3. **Governing rules.** Can I list every ADR / UX-spec rule that governs the shape?
   *Verifiable:* every entry in `Governing rules invoked` (ledger) appears as an inline anchor in Functional Requirements or UI/UX Requirements.
4. **Acceptance harness.** Can I write a test harness from the AC section alone?
   *Verifiable:* every AC statement has an observable verb (clicks, sees, returns, renders, equals, contains) — never an implementer-side verb (creates the file, refactors X, retires Y).
5. **End-state per piece.** For each entry in `Pieces of scope` (ledger), is there at least one Functional Requirement outcome bullet describing its end-state?
   *Verifiable:* ledger pieces count ≤ Functional Requirements bullet count.

If any question returns **no**, add ONE outcome bullet to the section that should carry the missing information. Re-run the test. Stop when all 5 return **yes**.

If after 3 iterations the test still fails on the same question, scope.md is insufficient — BLOCK and report to operator: "Recreation-contract test fails on Q`<n>` after 3 iterations. Specific gap: `<one-line gap>`. Need scope.md update before continuing."

### Write

After the test passes:
- Write the spec to `docs/features/<feature>.md`.
- Report line count to operator. If line count > 2× `template.md` line count, flag for operator review: "Spec is `<n>` lines (template is `<m>`). The recreation-contract test passed — the size reflects feature complexity. Confirm or flag any section for trim."

Pause for operator review. Brief: "Spec authored at `<path>` (`<n>` lines). Ready to plan tasks? Reply OK or flag any spec issues first."

## Pass 3 — Plan

> **Stance: decompose work into tasks. Each task = "what to build" + "how done is judged". ZERO implementation methodology. ZERO step-lists. Code samples only when the sample IS the load-bearing decision (a doc patch literal, an end-state folder layout). The spec is the contract; tasks are the implementation backlog. Phase 3 (Implement) reads tasks; Phase 2 (this skill) only WRITES them, never plans methodology.**

Procedure:

1. **Decompose per-feature-dir as default.** Generate one task per entry in `Pieces of scope` (intent ledger), plus any prep / retire / sweep tasks the spec mandates. Operator override to per-AC-cluster only when a single piece has 5+ unrelated AC clusters that can't land in one PR.
2. **Detect app-segment split (multi-app features only).** Scan the intent ledger's `Pieces of scope` + `Constraints inherited` for tier keywords. App-segment vocab is **project-scoped — derived from the literal `<APP>` segment in `docs/features/template-tasks.md` stencil** (e.g., stencil `# <FEAT><NN>-FE-<NN>` → vocab = `{FE}`). The middle literal between two placeholder segments is the accepted app token; multiple literal tokens across the template's example task IDs (summary table rows + task headings) extend the vocab set. If the stencil has no `<APP>` segment, the project is single-app.
   - **Single-app feature** (one tier only): emit single-app IDs in the project's shape (`<PREFIX><NN>-<NN>`, task counter 2-digit zero-padded). Default for projects whose template-tasks.md stencil has no `<APP>` segment, or for features that live entirely in one tier of a multi-app project.
   - **Multi-app feature** (touches 2+ tiers): emit per-tier multi-app IDs (`<PREFIX><NN>-<APP>-<NN>`, task counter 2-digit zero-padded). The `<APP>` token must match one of the literals derived from template-tasks.md. Decompose each piece-of-scope into per-app tasks; if the spec implies a tier not represented in template-tasks.md vocab, ASK operator (extend the template or pick an existing token).
   - **Heuristic:** if `Pieces of scope` cleanly split by tier (e.g., "Schema migration", "API endpoints", "Web screens"), multi-app. If they cross tiers per entry ("Entity X — full stack rewrite"), surface the ambiguity to operator before deciding.
3. **Generate file header.** Use a CONDENSED preamble: the four "CRITICAL: append-only" bullets (Never overwrite / When updating status / When adding tasks / Keep all detail) + a one-line pointer to `docs/features/template-tasks.md` for full authoring discipline + close-of-task review + a one-line pointer to the companion spec. Do NOT verbatim-copy the full template-tasks.md preamble — it's ~70 lines and would bloat every tasks file.
4. **Generate summary table.** One row per task: ID / Title / Status. All Status = `Todo` initially. **IDs follow the project's canonical shape** (`<PREFIX><NN>-<NN>` single-app, `<PREFIX><NN>-<APP>-<NN>` multi-app — feature segment collapses the dash; task counter is per-app, 2-digit zero-padded). Numbering: **per-app monotonic counter** — each `(feature, app)` pair starts at `01` independently (two apps' initial tasks both numbered `01`, not `01 + 02`).
5. **Classify screen shape per task.** From the intent ledger's `Screens / surfaces touched` (or the spec's UI/UX Requirements bullet for the matching piece), detect the screen shape. The conformance-checklist sections in step 8 are screen-shape-driven:

   | Screen shape | What it is |
   |---|---|
   | List-table | Entity table with filters / search / pagination |
   | Create / edit (default) | Form page — new entity or editing existing |
   | Per-section save | Inline edit, section-by-section save |
   | Embedded list in tab | Detail page with list-table embedded in a tab |
   | Bespoke layout | Timeline / kanban / dashboard / non-standard |
   | Data-layer-only | No own screens; selectors / badges / hooks |

   Detection hints: "list / filter / pagination / table" → List-table; "create / edit / form" → Create/edit; "tab + embedded list" → Embedded list in tab; "no own screens / data-layer / selectors / badges" → Data-layer-only. If ambiguous, ask the operator.

6. **Resolve source UX specs per screen-shape mapping** (web projects only — skip for server projects):

   | Screen shape | Specs to pull frozen rules from |
   |---|---|
   | List-table | `docs/ux/lists.md` + `docs/ux/shell.md` + `docs/ux/errors.md` |
   | Create / edit | `docs/ux/form.md` + `docs/ux/shell.md` + `docs/ux/fields.md` + `docs/ux/errors.md` |
   | Per-section save | + `docs/ux/form-inline.md` |
   | Embedded list in tab | + `docs/ux/form-table.md` |
   | Bespoke layout | + `docs/ux/form-custom.md` |
   | Data-layer-only | `docs/ux/errors.md` only |

   Server projects: fall back to `docs/qa/feature-ux-checklist.md` filtered by `applies-to`.

7. **Read source UX specs in parallel; extract applicable frozen rules.** For each resolved spec, read in full and pull every numbered/anchored frozen-rule entry (e.g., `<RULE-LABEL>`, `<RULE-LABEL>`, `<RULE-LABEL>`). Capture: rule number / verbatim one-line summary / source anchor. This list IS the per-task acceptance gate that step 8 pastes into the Frozen rules section.

8. **Generate per-task entries** strictly per `docs/features/template-tasks.md` section list — no new `###` headers permitted. Each entry's `## <task-id>: <Title>` heading uses the SAID-canonical shape decided in step 2 (`<PREFIX><NN>-NN` single-app or `<PREFIX><NN>-<APP>-NN` multi-app, 2-digit zero-padded). Canonical order: Status (date) / Priority / Refs / Problem [+ optional `### Root cause` for bugs] / Approach / Reading list / Acceptance / Fix (placeholder) / Deviations (placeholder) / Gotchas (placeholder) / Out of scope (optional, only if scope.md flagged something). The frozen-rule + wire-probe + visual-parity + cross-feature-contract content extracted in steps 5–7 folds into **Approach** (cite rule anchors inline) and **Acceptance** (observable bullets, one per concern) per the per-task authoring rules below.

Per-task authoring rules (HARD — violations require rework):

- **STRICT template adherence (HARD).** Use ONLY the section list in `docs/features/template-tasks.md`: Problem / Approach / Reading list / Acceptance / Fix / Deviations / Gotchas / Out of scope (+ optional `### Root cause` subsection under Problem for bugs). NEVER invent new `###` headers ("Frozen rules to satisfy", "Wire contract probes", "Visual parity reference", "Cross-feature contracts", "Spec changes", "Files modified", "Implementation notes", "Lessons learned", "Discovery" — all forbidden). Frozen-rule conformance / wire probes / visual parity / cross-feature contracts fold into Approach + Acceptance per the rules below. Task bloat dies here.
- **Status:** `Todo (YYYY-MM-DD)` with creation date.
- **Refs:** Write-set, not read-set. List ADR / UX-spec / feature-spec paths the task **creates or edits**. Read-set — specs the task consumes — lives in Reading list, NOT Refs. Empty unless the task itself produces a doc edit; mandatory when applicable.
- **Problem:** What needs to be solved + context. For bugs, add `### Root cause` subsection.
- **Approach:** "What to build" framing. Key decisions called out. **NO step-lists ("1. Do X. 2. Do Y.")** — methodology belongs to Phase 3 only. **NO function signatures, no detailed file lists, no implementation playbook.**
  - **Cite applicable frozen rules inline** when relevant — anchors only, no verbatim paraphrase. Example: "Reshape onto <PROJECT> list-table shape per `lists.md` #20, #23, #26 + `shell.md` #4, #7 + `errors.md` #1, #2." Implementer opens the cited specs per Reading list `(full read)`.
  - **Alternatives considered** subsection ONLY when a rejected option was reasonable to a cold reader. Skip otherwise.
  - **Code samples** ONLY when the sample IS the load-bearing decision (a `CLAUDE.md` patch literal, an end-state folder layout). Default to prose pointing at upstream ADR/UX-spec.
- **Reading list:** Per-task delta from spec's Context-to-load. Don't duplicate. Cite additional files / ADR-IDs / UX-spec-frozen-items the task specifically needs beyond the umbrella context. **Flag `(full read)` on UX specs whose frozen rules are cited in Approach** — implementer re-opens the source at Phase 3 (Implement) start, not CLAUDE.md summaries.
- **Acceptance:** Observable bullets — how "done" is judged. Cite spec / ADR / UX-spec anchors; never restate. Conformance content folds in as observable bullets, skip any that don't apply:
  - **Frozen-rule conformance** (when task touches UX-governed surfaces): cite spec + rule numbers, not verbatim text. Example: `- [ ] lists.md #20, #23, #26 + shell.md #4, #7 satisfied (per screen shape)`.
  - **Wire contract** (when task introduces or changes a `*.service.api.ts` method): one bullet per load-bearing endpoint. Example: `- [ ] GET /endpoint — Zod schema matches captured bytes (playwright)`.
  - **Visual parity** (when task migrates / reshapes a list-table or form screen): one bullet citing closest already-conformant reference. Example: `- [ ] Walked side-by-side with /tasks — zero visible diff`.
  - **Cross-feature contracts** (when intent ledger's `Constraints inherited` lists Sacred consumers): one bullet per public surface preserved. Example: `- [ ] <Entity>Cell public props preserved (consumed by features/<entity>/)`.
  - **Quality gates**: one umbrella bullet. Example: `- [ ] Quality gates green; no regression outside scope.`

  Typical task ends with 5–10 Acceptance bullets total — keep tight; skip every category that doesn't apply (data-layer-only task has no visual parity; refactor with no schema change has no wire contract).
- **Fix / Deviations / Gotchas:** HTML-comment placeholders only. Phase 3 close-of-task review fills them.

Write to `docs/features/<feature>.tasks.md`.

After tasks are written, return to the spec and replace the Pass-2 `## Feature Tasks` placeholder with the generated summary table.

## Step Final — Exit

Report to operator:

- Spec path: `docs/features/<feature>.md` (line count, KB).
- Tasks path: `docs/features/<feature>.tasks.md` (task count, KB).
- Recreation-contract test result: passed first run / iterated `<n>` times / blocked on `<gap>`.
- Spec/template ratio: `<spec lines>` / `<template lines>` = `<ratio>×`. Flag if > 2×.

Hard exit. The skill writes spec + tasks; that's the entire Phase 2 output. Implementation is Phase 3's job.

Suggested next step for the operator: "Phase 3 (Implement) starts here. Run `/said:impl <feature-id>` to drive every `Status: Todo` task in order (whole-feature mode), or `/said:impl <task-id>` for a single task. Each task closes through `/said:review-ux` at Phase C (web/UI features only)."

## Structural boundaries

These are positive boundaries of the skill's contract — not negative rules subsumed by the section procedures + recreation-contract test.

- **Phase 2 stops at writing spec + tasks.** The operator triggers Phase 3 via `/said:impl`. Never auto-invoke implementation, never spawn coding agents, never begin code edits.
- **Phase 2 is for INITIAL authoring only.** Adding a task to an existing feature → `/said:add-task` (direct append per `template-tasks.md`).
- **Spec and tasks are two files, never one.** Earned design decision (S01-1). Spec is the pre-implementation contract; tasks.md is the post-implementation history.
- **§D-empty preflight is non-negotiable.** Phase 1 incomplete = Phase 2 starts on bad input. BLOCK and redirect.
- **The recreation-contract test is the authoring gate.** Section procedures produce the right shape by construction; the test verifies. If a section grows large, re-run the procedure for that section — don't add caps or "no X" rules.
- **The operator owns clarifying-question answers.** AC form, story type, granularity overrides — never auto-resolve silently.
