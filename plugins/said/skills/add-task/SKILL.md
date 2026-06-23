---
name: add-task
description: >
  SAID/Phase 2 (Architect) — appends a new task entry to an existing
  feature's append-only tasks log. Distills `/said:architect` Pass 3
  authoring into a standalone single-pass skill, intended for tasks
  discovered mid-implementation: bugs surfaced by code review or runtime,
  scope-creep additions, follow-ups from close-of-task leak scans.
  Emits task IDs in the project's canonical shape — single-app
  `<PREFIX><NN>-<NN>` or multi-app `<PREFIX><NN>-<APP>-<NN>` (2-digit
  zero-padded task counter) via `app=` flag. App-segment vocab and concrete shape derive from
  `docs/features/template-tasks.md` stencil; skill reads it at Step 0.
  Triggered ONLY by the explicit command "/said:add-task <feature-id>
  [bug] [short] [auto] [app=<APP>] [priority=High|Medium|Low]". NOT for INITIAL spec
  + tasks creation — that's `/said:architect`. NOT for implementation
  — that's `/said:impl`.
---

# Feature Add Task — Phase 2 (Architect): Append a Task

This skill appends a new task entry to an existing `<feature>.tasks.md` file. It exists because tasks routinely surface mid-implementation — bugs caught at runtime, scope-creep additions, follow-ups from close-of-task leak scans — and the discipline for authoring them deserves enforcement (template-tasks.md authoring rules, no step-lists in Approach, code samples only when load-bearing, condensed Refs discipline). Manual append-only editing technically works, but loses the enforcement.

This skill is the **add** half of Phase 2's task lifecycle. The **execute** half (implementing a task per Phase 3 close-of-task review discipline) is `/said:impl` — invoked separately by the operator once the task is in the backlog.

**Boundary.** This skill REQUIRES an existing tasks file. If the feature has no tasks file yet, it's an INITIAL Phase 2 case — redirect to `/said:architect`.

## When this fires

The user invokes:

- `/said:add-task <feature-id>` — single-app task; interactive Q&A; default Priority=Medium; non-bug shape. Emits the project's single-app shape `<PREFIX><NN>-<NN>` (2-digit zero-padded).
- `/said:add-task <feature-id> app=<APP>` — multi-app task; emits `<PREFIX><NN>-<APP>-<NN>` (2-digit zero-padded). The `<APP>` token must match the literal app-segment in `docs/features/template-tasks.md` stencil. Skill derives accepted vocab at Step 0; rejects any other token.
- `/said:add-task <feature-id> bug` — adds `### Root cause` subsection per template-tasks.md bug-task discipline; auto-Priority=High.
- `/said:add-task <feature-id> priority=High` — explicit priority.
- `/said:add-task <feature-id> short` — minimal-shape task. Q&A trims to Title + Problem (+ Root cause for bugs); Approach + Acceptance prefilled from detected screen-shape; operator edits or accepts defaults. Suitable for routine bug fixes / polish.
- `/said:add-task <feature-id> auto` — skill runs the default flow but stops ONLY when operator input or decision is required (Step 1 Q&A input, Step 3 Contradicts, Step 4.5 failures). Step 3 Gap proposed edits auto-approve and write with a `### Gotchas` trail recording the auto-approved edits for post-write verification.
- Composition `short auto bug` — typical routine-bug workflow: trimmed Q&A, no Step 3 Gap confirmations (usually Covered for bugs), Step 4.5 skipped (no spec edit).

Flags compose: `/said:add-task <feature-id> bug app=<APP> priority=High` is valid. Operator may type `<feature-id>` in any case; the skill normalizes to UPPERCASE (canonical grammar requires uppercase IDs in docs / tasks files; lowercase is reserved for commit-msg scopes only). Symmetric with `/said:impl`.

If `docs/features/<feature-id>.tasks.md` doesn't exist, this is the WRONG skill. Redirect: "No tasks file at `docs/features/<feature-id>.tasks.md` — this is an INITIAL Phase 2 case. Use `/said:architect` to author the spec + initial tasks log first."

If the operator's request is to MODIFY an existing task (rename, fix typo, update Status) — this is the WRONG skill. Tasks are append-only per `template-tasks.md`. Redirect: "Existing task modification violates the append-only discipline. Status updates are the one exception — change only the Status: line and add `### Fix` per close-of-task review. For substantive changes, append a new task ID."

## Step 0 — Preflight

Resolve inputs and ground in existing context:

1. **Normalize `<feature-id>` arg to UPPERCASE.** Operator may type any case; the skill uppercases the prefix (e.g., `<feat>-NN` → `<FEAT>-NN`) to match docs / tasks file conventions. Symmetric with `/said:impl`.
2. **Resolve tasks file path.** Conventionally `docs/features/<feature-id>.tasks.md`. If missing, scan `docs/features/` for files matching `<feature-id>*.tasks.md` (slug-suffixed convention, e.g., `TEST-01-tests.tasks.md` for feature `TEST-01`); if exactly one match, use it; if multiple matches, ASK the operator which to use. BLOCK only if zero glob matches (per "When this fires" redirect rule above). Symmetric with the companion-spec fallback in step 3.
3. **Resolve companion spec path.** Conventionally `docs/features/<feature-id>.md`. Sub-phased features may use slug-suffixed naming (e.g., `<feature-id>-phaseB.md` for the spec alongside `<feature-id>.tasks.md` for the tasks). If `<feature-id>.md` is missing, scan `docs/features/` for files matching `<feature-id>*.md` and ASK the operator which is the companion spec. Otherwise default.
4. **Parse flags.**
   - `bug` → adds `### Root cause` subsection + auto-Priority=High (operator override via `priority=` wins).
   - `app=<APP>` → multi-app mode. Vocab validation happens at step 7 after `docs/features/template-tasks.md` is read; if `<APP>` doesn't match the literal app-segment in the project's stencil, BLOCK with "Token `<APP>` not in project vocab (derived from `docs/features/template-tasks.md`). Accepted: <derived-list>." Absent → single-app mode.
   - `priority=<High|Medium|Low>` → explicit; defaults to Medium for non-bugs, High for bugs.
   - `short` → minimal-shape task; Step 1 trims Q&A to Title + Problem (+ Root cause for bugs); Step 3 / Step 4.5 unchanged.
   - `auto` → skill stops only for required operator input/decision. Step 3 Gap auto-approves all proposed edits (writes them + `### Gotchas` trail). Step 1 Q&A, Step 3 Contradicts, Step 4.5 failures retain their default stops.
5. **Read existing tasks file in full.** Compute the next task ID per the project's canonical grammar (feature `<PREFIX>-<NN>`; task IDs collapse the dash inside the feature segment):
   - **Compute task prefix:** strip the dash from `<feature-id>` (e.g., `<FEAT>-NN` → `<FEAT>NN`).
   - **Single-app mode (no `app=` flag):** scan for headings matching `^## <PREFIX>-(\d+):`. Take max NN; new ID = `<PREFIX>-<NN+1>` zero-padded to 2 digits. If no prior single-app entries exist, start at `01`.
   - **Multi-app mode (`app=<APP>`):** scan for headings matching `^## <PREFIX>-<APP>-(\d+):` (filtered to THIS app only). Take max NN; new ID = `<PREFIX>-<APP>-<NN+1>` zero-padded to 2 digits. **Per-app counter** — each `(feature, app)` pair has its own monotonic stream, starting at `01` independently.
   - **Legacy IDs do NOT contribute.** Any task heading not matching the canonical regex (e.g., pre-migration entries in projects that haven't run a one-time task-id migration) is excluded from the counter scan. Append-only — never fill gaps from deleted tasks.
6. **Skim companion spec — capture coverage anchors.** Identify which section(s) govern the new task's scope (Per-piece scope / Acceptance Criteria / Implementation pointers / Boundaries — whichever the spec uses). Capture 1–2 lines per relevant section for Step 3 classification. Don't full-read.
7. **Read `docs/features/template-tasks.md`** in full — for authoring discipline AND task-ID stencil. Extract accepted app-segment vocab from the stencil: parse the canonical heading + example task IDs (e.g., `# <FEAT><NN>-FE-<NN> Task Log` → middle literal segment `FE` → vocab = `{FE}`). The middle literal between two placeholder segments is the accepted app token. Validate the step-4 `app=` flag now: if outside the derived set, BLOCK per step 4. If the stencil has no `<APP>` segment, the project is single-app — reject any `app=` flag.
8. **Classify screen shape** (web projects only — skip for server). Detect the new task's screen shape from the closest companion spec § Per-feature scope subsection (or from operator-provided context if the new task doesn't map cleanly to a scope piece):

   | Screen shape | What it is |
   |---|---|
   | List-table | Entity table with filters / search / pagination |
   | Create / edit (default) | Form page — new entity or editing existing |
   | Per-section save | Inline edit, section-by-section save |
   | Embedded list in tab | Detail page with list-table embedded in a tab |
   | Bespoke layout | Timeline / kanban / dashboard / non-standard |
   | Data-layer-only | No own screens; selectors / badges / hooks |

   If ambiguous, ASK the operator in Step 1's batch prompt — don't guess.

9. **Resolve source UX specs + extract frozen rules** (web projects only). Per screen shape:

   | Screen shape | Specs to pull frozen rules from |
   |---|---|
   | List-table | `docs/ux/lists.md` + `docs/ux/shell.md` + `docs/ux/errors.md` |
   | Create / edit | `docs/ux/form.md` + `docs/ux/shell.md` + `docs/ux/fields.md` + `docs/ux/errors.md` |
   | Per-section save | + `docs/ux/form-inline.md` |
   | Embedded list in tab | + `docs/ux/form-table.md` |
   | Bespoke layout | + `docs/ux/form-custom.md` |
   | Data-layer-only | `docs/ux/errors.md` only |

   Read in parallel; extract applicable frozen-rule anchors (rule numbers only, no verbatim paraphrase). Server projects: fall back to `docs/qa/feature-ux-checklist.md` filtered by `applies-to`.

## Step 1 — Single-batch interactive Q&A

> **Stance: enforce template-tasks.md authoring discipline. Operator answers populate the task body; the skill applies hard rules at write-time. No step-lists in Approach, code samples only when load-bearing, Refs only for ADR/UX/spec edits.**

Ask one batch (operator can answer terse, in any structured format). If the request is a bug, include the Root cause prompt; otherwise omit. Pre-fill the screen-shape detection + applicable frozen-rule anchors + conformance bullets from Step 0; operator confirms or edits.

**Mode dispatch.**

- **Default / `bug`** — full interactive batch (prompt below).
- **`short`** — trimmed batch. Required fields: Title + Problem (+ Root cause if `bug`). Approach + Acceptance prefilled from screen-shape detection.
- **`auto`** — Step 1 unchanged (Q&A is REQUIRED input; auto only affects later gates).

Suggested batch prompt:

```
Authoring <new-task-id> (project-canonical shape per `docs/features/template-tasks.md`).
Derived from: feature <feature-id>, app=<app-token> (literal from template-tasks.md stencil; accepted vocab = {<derived-set>}), prior counter <max-NN> → next <new-NN>.

[If task-id is wrong — flag in your reply and skill recomputes before write.]

Detected screen shape: <list-table | create-edit | data-layer-only | ...> (from spec § Per-feature scope). UX specs in scope: <lists.md, shell.md, errors.md>. Applicable frozen-rule anchors: <#20, #23, #26 + #4, #7 + #1, #2> (skill extracted from Step 0).

Reply with answers below (any format; terse OK):

Title: [short imperative title]
Problem: [what needs solving + context, 1-3 sentences; no methodology]
[bug-only] Root cause: [where the bug originates; cite file:line if applicable]
Approach: [what to build, key decisions, no step-lists, no function signatures — skill will append rule-anchor citations from detected UX specs]
Alternatives considered: [optional — only if a rejected option was reasonable]
Reading list: [task-specific files beyond spec's Context-to-load — skill will flag (full read) on UX specs sourced]
Acceptance bullets (skill prefills; strip categories that don't apply):
  - [ ] <spec> #N, #M satisfied (per screen shape)
  - [ ] GET <endpoint> — Zod schema matches captured bytes (playwright)
  - [ ] Walked side-by-side with <reference URL> — zero visible diff
  - [ ] <ComponentName> public props preserved (consumed by <ConsumerFeature>)
  - [ ] Quality gates green; no regression outside scope.
Refs: [ADR/UX-spec/feature-spec paths this task CREATES or EDITS; empty otherwise]
Priority: [High|Medium|Low; default Medium / High for bugs]
```

If screen shape was ambiguous in Step 0, ask the operator to pick one before showing the conformance bullet preview. Wait for `ANSWERS:` (or equivalent reply) before authoring.

## Step 2 — Apply hard authoring rules

Before writing, validate the answers against template-tasks.md discipline. Rewrite operator content where it violates:

- **STRICT template adherence (HARD).** Use ONLY the section list in `docs/features/template-tasks.md`: Problem / Approach / Reading list / Acceptance / Fix / Deviations / Gotchas / Out of scope (+ optional `### Root cause` subsection under Problem for bugs). NEVER invent new `###` headers ("Frozen rules to satisfy", "Wire contract probes", "Visual parity reference", "Cross-feature contracts", "Spec changes", "Files modified", "Implementation notes", "Lessons learned", "Discovery" — all forbidden). Frozen-rule conformance / wire probes / visual parity / cross-feature contracts fold into Approach + Acceptance per the rules below. Task bloat dies here.
- **Approach: no step-lists.** "1. Do X. 2. Do Y." → rewrite as "what-to-build" framing with key decisions called out. If the operator's Approach reads as imperative numbered steps, contract to declarative end-state prose.
- **Approach: cite frozen-rule anchors inline** when the task touches UX-governed surfaces. Use Step 0's extracted anchors. Example: "Reshape Sheet → Dialog per `lists.md` #20 (Sheet form needs ≥2 fields) + `form.md` #16 (RBAC affordance gating)." Anchors only — no verbatim paraphrase. Implementer opens the source via Reading list `(full read)`.
- **Approach: no implementation-detail leakage.** Function signatures, file enumerations, code samples that aren't load-bearing → cut and cite the upstream ADR/UX-spec/spec section. A code sample is load-bearing only when the sample ITSELF carries a decision the prose can't (e.g., end-state folder layout for a data-layer-only feature; a literal doc-patch wording).
- **Alternatives considered: only when reasonable.** If the operator listed an alternative that no cold reader would have picked, drop it (per template's bloat-scan rule).
- **Reading list: per-task DELTA only.** If the operator cited files already in the spec's Context-to-load, cut the duplicates — the spec covers the umbrella; the task cites only what's specifically additional. **Flag `(full read)` on UX specs whose anchors are cited in Approach** — implementer re-opens the source at Phase 3 (Implement) start, not CLAUDE.md summaries.
- **Acceptance: observable bullets, conformance content folds in.** Cite spec / ADR / UX-spec anchors; never restate. Skip every category that doesn't apply:
  - Frozen-rule conformance (when task touches UX-governed surfaces): `- [ ] lists.md #20, #23 + form.md #16 satisfied (per screen shape)`.
  - Wire contract (when task adds/changes a `*.service.api.ts` method): `- [ ] GET /endpoint — Zod schema matches captured bytes (playwright)`.
  - Visual parity (when task migrates / reshapes a list-table or form screen): `- [ ] Walked side-by-side with /tasks — zero visible diff`.
  - Cross-feature contracts (when spec's Boundaries lists Sacred consumers): `- [ ] DictionaryCell public props preserved (consumed by features/estimate/)`.
  - Quality gates umbrella bullet.
  
  Typical task ends with 5–10 Acceptance bullets total. Bug tasks may be even leaner (Problem + Fix + Gotchas per template-tasks.md "depth varies").
- **Refs: empty by default.** Only fill if the task creates or edits an ADR / UX-spec / feature-spec. Reading list ≠ Refs. Refs is the write-set; Reading list (+ Approach citations) is the read-set.
- **Status: `Todo (YYYY-MM-DD)`** with today's creation date.
- **Fix / Deviations / Gotchas: HTML-comment placeholders.** Phase 3 close-of-task review fills them.

If a §D-class question surfaces during Q&A — an operator decision the skill cannot silently resolve (cross-cutting choice, contract conflict, sequencing ambiguity) — STOP authoring. Surface the question explicitly; wait for operator decision; then proceed. Do not bake guesses into the new task.

## Step 3 — Spec coverage gate

**Mode-aware gate behavior.**

- **Default / `bug` / `short`** — existing flow (operator confirms each Gap edit; 3-option prompt on Contradicts).
- **`auto`** — auto-resolves clear gates; stops only when decision required:
  - **Covered** → proceed silently to Step 4 (clear).
  - **Gap** → write each proposed spec edit as drafted (no per-edit prompt — skill's proposals are the default); add `### Gotchas` line on the new task: `Auto-mode approved <N> spec edit(s) at <spec-section list>. Operator verify post-write.`
  - **Contradicts** → STOP and surface the 3-option prompt (decision REQUIRED — auto does not override).

Classify the new task vs companion spec (anchors from Step 0 step 6):

- **Covered** — spec already mandates this requirement → proceed to Step 4. No spec edit.
- **Gap** — spec silent or partial → propose requirement-level spec edit (below).
- **Contradicts** — task Approach diverges from a stated spec rule → BLOCK with three options:
  - **(a) Revise the task** — the contradiction is task-shape; reword Approach / Acceptance to align with the existing spec.
  - **(b) Direct-edit the spec** via `/said:architect` propagate-new-info branch — if the contradiction resolves to a surgical bullet rewrite (e.g., spec says "displays X" but the new task implements "displays Y" for a justified reason).
  - **(c) Re-architect** via `/said:architect <scope-path> output-name=<feature-id>-v2` — rare; only when the contradiction reflects a fundamental scope shift requiring full re-author.

**Propose spec edit (Gap only):**

1. **Extract REQUIREMENT from task's Problem + Approach.** Strip implementation: file paths, function signatures, code samples, step-lists, library names. Spec = WHAT (observable behavior, shape, constraint); task = HOW.
2. **Match spec's section style.** Edits land in template-conforming sections only: **Functional Requirements bullet** / **UI/UX Requirements bullet** / **API Integration line** / **Acceptance Criteria statement** (Gherkin or bullet, per spec's AC mode) / **Known limitations bullet**. Never introduce a new top-level section — if the proposed edit doesn't fit any of the above, the spec needs re-architecture (BLOCK and redirect to `/said:architect` propagate-new-info branch).
3. **Surface proposed edits.** If the gap affects ONE spec section, surface as single batch. If it affects ≥ 2 sections (common: Functional Requirements gains a bullet AND Acceptance Criteria gains a matching statement), surface as a numbered list and confirm each independently:

   ```
   Spec coverage: GAP — <spec-path>.
     Edit 1 / <section>:  + <draft>
     Edit 2 / <section>:  + <draft>
     [...]
   Confirm each (y / revise N: <new text> / no: <N> — log as deliberate skip per edit).
   ```

   **Hard cap: ≤ 4 sections affected.** If > 4, BLOCK with redirect: "Multi-section spec change exceeds `/said:add-task` scope (`<n>` sections needed). Apply via `/said:architect` propagate-new-info branch directly."

4. **Response per edit:**
   - `y` → record for Step 4 atomic write.
   - `revise N: <new text>` → use operator's text for edit N.
   - `no: <N>` → skip edit N; add Gotchas bullet `Spec edit N not applied per operator decision <YYYY-MM-DD>.`

`bug` tasks default to Covered (bug = code/spec divergence, not new requirement); gate still runs to catch the rare case where spec was silent on affected behavior.

## Step 4 — Append + apply confirmed spec edit

**Write order (spec first if Step 3 confirmed, then task):**

1. If Step 3 confirmed: open spec, insert requirement under named section, save. Surface diff.
2. Append task block + summary table row (canonical shape per Step 0 step 5).
3. `Refs:` reflects what skill wrote — spec path if edited, empty if not. Not future intentions.

Use the canonical section order from template-tasks.md:

```
## <new-task-id>: <Title>
# project-canonical shape — see `docs/features/template-tasks.md` stencil

- **Status:** Todo (YYYY-MM-DD)
- **Priority:** <High|Medium|Low>
- **Refs:** <paths or empty>

### Problem
<problem text>

[bug-only]
### Root cause
<root-cause text>

### Approach
<approach text>
[optional]
#### Alternatives considered
<bulleted alternatives>

### Reading list
<bulleted task-specific deltas>

### Acceptance
<observable bullets>

### Fix
<!-- Filled at close. Single verification line. -->

### Deviations
<!-- Optional. -->

### Gotchas
<!-- Optional. -->
```

Insert a `---` separator before the new task block (matching the calibration target's task-separator pattern).

## Step 4.5 — Recreation-contract self-test (only when Step 3 confirmed a spec edit)

After spec + task are written, re-run the 5-question recreation-contract test from `/said:architect` Pass 2 § Recreation-contract self-test against the updated spec. Common failure modes after a single-task edit:

| Failed question | Cause | Fix |
|---|---|---|
| Q1 Screens | edit removed a `**<ScreenName>**` mention | Restore mention |
| Q3 Governing rules | edit removed an ADR / UX-spec inline anchor | Restore citation |
| Q4 Acceptance harness | Functional Requirements gained a bullet without matching Acceptance | Add Acceptance bullet for the new requirement |
| Q5 End-state per piece | new piece-of-scope without Functional Requirement bullet (rare for add-task) | Add Functional Requirement bullet |

If any question fails, surface to operator. Allow:

- **revise** — re-edit the spec; re-run test.
- **skip** — proceed; add `### Gotchas` line on the new task: `Spec recreation-test failed on Q<N> per operator decision <YYYY-MM-DD>; <one-line reason>.` Commit-msg notes the skip.

Skip Step 4.5 entirely when Step 3 was Covered (no spec edit ran).

## Step Final — Exit

Report to operator:

- New task ID + title.
- Tasks file path + new total task count.
- Summary table updated (yes/no).

**Auto-mode addendum to report** (when `auto` was set):
- Step 3 outcome: Covered / Gap with <N> auto-approved spec edits / Contradicts (resolved per operator choice).
- Recommend operator review auto-approved spec edits before `/said:impl <new-task-id>`.

Hard exit. Do NOT begin implementation. Do NOT spawn coding agents. Phase 3 implementation is a separate operator decision — the new task is now in the backlog; the operator picks when to work it.

Suggested next step: "Task `<new-task-id>` appended. Run `/said:impl <new-task-id>` to drive Phase 3 — feature-id auto-derived from the task-id prefix."

## Anti-patterns

- **Don't auto-resolve clarifying questions.** If the operator's answers leave gaps that would force a guess on substance (Approach, Acceptance), ASK rather than fill.
- **Don't write step-lists in `### Approach`.** The single most violatable rule, inherited from `/said:architect` Pass 3. Methodology belongs to Phase 3.
- **Don't include code samples that aren't load-bearing.** Same rule as `/said:architect` Pass 3.
- **Don't duplicate spec's Context-to-load in Reading list.** Per-task delta only.
- **Don't begin implementation.** This skill writes the task entry; that's the entire output. NEVER spawn coding agents; NEVER invoke `/said:impl` automatically (the operator triggers it after this skill exits); NEVER begin code edits.
- **Don't run on features without an existing tasks file.** Redirect to `/said:architect` for INITIAL spec + tasks creation.
- **Don't modify or reorder existing tasks.** Append-only per `template-tasks.md`. The only exception (per template-tasks.md) is Status updates with `### Fix` — that's close-of-task review territory, not this skill.
- **Don't fill task-ID gaps.** Per-app monotonic counter — the highest existing NN for THIS `(feature, app)` pair gets `+1` regardless of deleted-task gaps below. Append-only matches git-log sequencing.
- **Don't cross-pollinate counters across apps.** Each `(feature, app)` pair has its own independent counter — the next ID for app-A doesn't increment based on app-B's counter. Different apps own different bug/feature streams.
- **Don't mix legacy IDs into the counter scan.** Task headings not matching the canonical regex live in a separate namespace; the canonical counter starts fresh at `01` regardless of how many legacy entries exist. After migration (if applicable), all IDs share the canonical shape and this anti-pattern dissolves.
- **Don't bypass `Refs:` discipline.** Refs is for ADR/UX/spec EDITS the task creates, NOT for everything the task READS. Reading is captured in Reading list.
- **Don't conflate bug tasks with planned tasks.** Bug tasks have `### Root cause`; planned tasks don't. The `bug` flag is the explicit signal — never auto-detect via problem-text keyword scanning (false positives corrupt the calibration target).
- **Don't invent new `###` sections in task entries.** `docs/features/template-tasks.md` is the exhaustive section list: Problem / Approach / Reading list / Acceptance / Fix / Deviations / Gotchas / Out of scope (+ optional `### Root cause` under Problem for bugs). Forbidden: `### Frozen rules to satisfy`, `### Wire contract probes`, `### Visual parity reference`, `### Cross-feature contracts`, `### Spec changes`, `### Files modified`, `### Implementation notes`, `### Lessons learned`, `### Discovery`, `### Pass N` — all fold into Approach + Acceptance.
- **Don't skip the Step 3 spec coverage gate.** Even for trivial tasks, classify before appending. Silent skip = spec drift.
- **Don't leak implementation into proposed spec edits.** Spec = WHAT (behavior, shape, constraint). Task = HOW (paths, signatures, code, step-lists). Strip the latter before surfacing to operator.
- **Don't reverse spec/task write order.** Spec edit FIRST in Step 4, then task. Reversed = task references a spec line that doesn't exist yet.
