---
name: add-task
description: >
  SAID/Phase 2 (Architect) — appends a new task entry to an existing
  feature's append-only tasks log. Distills `/said:architect` Pass 3
  authoring into a standalone single-pass skill, intended for tasks
  discovered mid-implementation: bugs surfaced by code review or runtime,
  scope-creep additions, follow-ups from close-of-task leak scans.
  Emits task IDs in the project's canonical shape — single-lane
  `<PREFIX><NN>-<NN>` or per-lane `<PREFIX><NN>-<LANE>-<NN>` (2-digit
  zero-padded task counter) via `lane=` flag. The id template is `SAID.id-shape:`;
  the legal lane set is the declared `SAID.lanes:` registry (LOAD-WHOLE), read at
  Step 0 — never derived from example IDs.
  Triggered ONLY by the explicit command "/said:add-task <feature-id>
  [bug] [short] [auto] [lane=<LANE>] [priority=High|Medium|Low]", or its
  fast-track forms "/said:add-task <feature-id> fast-track "<task ids>""
  (open a run) and "/said:add-task <feature-id> fast-track F<NN> closed"
  (record a run's close). NOT for INITIAL spec
  + tasks creation — that's `/said:architect`. NOT for implementation
  — that's `/said:impl`.
---

# Feature Add Task — Phase 2 (Architect): Append a Task

This skill appends a new task entry to an existing `<feature>.tasks.md` file. It exists because tasks routinely surface mid-implementation — bugs caught at runtime, scope-creep additions, follow-ups from close-of-task leak scans — and the discipline for authoring them deserves enforcement (template-tasks.md authoring rules, no step-lists in Approach, code samples only when load-bearing, condensed Refs discipline). Manual append-only editing technically works, but loses the enforcement.

This skill is the **add** half of Phase 2's task lifecycle. The **execute** half (implementing a task per Phase 3 close-of-task review discipline) is `/said:impl` — invoked separately by the operator once the task is in the backlog.

**Boundary.** This skill REQUIRES an existing tasks file. If the feature has no tasks file yet, it's an INITIAL Phase 2 case — redirect to `/said:architect`.

**Main context only — the one writer of the append-only log.** This skill appends to a shared append-only file and its Step 1 needs the operator, so it runs in the main context. Inside a subagent or a fan-out arm there is no operator and no second writer is allowed (one log, one writer): a task discovered there is returned as an **owed item** for main to append via this skill — never appended from the arm.

## When this fires

The user invokes:

- `/said:add-task <feature-id>` — single-lane task; interactive Q&A; default Priority=Medium; non-bug shape. Emits the project's single-lane shape `<PREFIX><NN>-<NN>` (2-digit zero-padded).
- `/said:add-task <feature-id> lane=<LANE>` — per-lane task; emits `<PREFIX><NN>-<LANE>-<NN>` (2-digit zero-padded). The `<LANE>` token must be a declared lane in the `SAID.lanes:` registry (LOAD-WHOLE the registry at Step 0); rejects any undeclared token.
- `/said:add-task <feature-id> bug` — adds `### Root cause` subsection per template-tasks.md bug-task discipline; auto-Priority=High.
- `/said:add-task <feature-id> priority=High` — explicit priority.
- `/said:add-task <feature-id> short` — minimal-shape task. Q&A trims to Title + Problem (+ Root cause for bugs); Approach + Acceptance prefilled from the loaded rule registry; operator edits or accepts defaults. Suitable for routine bug fixes / polish.
- `/said:add-task <feature-id> auto` — skill runs the default flow but stops ONLY when operator input or decision is required (Step 1 Q&A input). It gains NO spec-write: a Step 3 Gap/Contradicts is recorded-and-stopped (redirect to `/said:architect` propagate-new-info), never auto-written.
- Composition `short auto bug` — typical routine-bug workflow: trimmed Q&A, usually Covered for bugs (no Gap flag), no spec-write path.
- `/said:add-task <feature-id> fast-track "<task ids>"` -- open a fast-track run over the listed tasks; appends a `## Fast-track F<NN>` block, no task entry (see **Fast-track runs**).
- `/said:add-task <feature-id> fast-track F<NN> closed` -- record run `F<NN>`'s close: writes its `closed:` line (see **Fast-track runs**).

Flags compose: `/said:add-task <feature-id> bug lane=<LANE> priority=High` is valid. Operator may type `<feature-id>` in any case; the skill normalizes to UPPERCASE (canonical grammar requires uppercase IDs in docs / tasks files; lowercase is reserved for commit-msg scopes only). Symmetric with `/said:impl`.

If `docs/features/<feature-id>.tasks.md` doesn't exist, this is the WRONG skill. Redirect: "No tasks file at `docs/features/<feature-id>.tasks.md` — this is an INITIAL Phase 2 case. Use `/said:architect` to author the spec + initial tasks log first."

If the operator's request is to MODIFY an existing task (rename, fix typo, update Status) -- this is the WRONG skill. Tasks are append-only per `template-tasks.md`. Redirect: "Existing task modification violates the append-only discipline. Status updates are one exception -- change only the Status: line and add `### Fix` per close-of-task review; the `closed:` line of a fast-track block is the other (the `fast-track F<NN> closed` form). For substantive changes, append a new task ID."

## Step 0 — Preflight

Resolve inputs and ground in existing context:

1. **Normalize `<feature-id>` arg to UPPERCASE.** Operator may type any case; the skill uppercases the prefix (e.g., `<feat>-NN` -> `<FEAT>-NN`) to match docs / tasks file conventions. Symmetric with `/said:impl`.
2. **Resolve tasks file path** from `SAID.task-log:` on the `## Lane` block; no key -> HALT (operator declares it), never glob-guess. If the declared file is absent, scan `docs/features/` for files matching `<feature-id>*.tasks.md` (slug-suffixed convention, e.g., `TEST-01-tests.tasks.md` for feature `TEST-01`); if exactly one match, use it; if multiple matches, ASK the operator which to use. BLOCK only if zero glob matches (per "When this fires" redirect rule above). Symmetric with the companion-spec fallback in step 3.
3. **Resolve companion spec path** from `SAID.feature-spec:` on the `## Lane` block; no key -> HALT. Sub-phased features may use slug-suffixed naming (e.g., `<feature-id>-phaseB.md` for the spec alongside `<feature-id>.tasks.md` for the tasks). If `<feature-id>.md` is missing, scan `docs/features/` for files matching `<feature-id>*.md` and ASK the operator which is the companion spec. Otherwise default.
4. **Parse flags.**
   - `bug` -> adds `### Root cause` subsection + auto-Priority=High (operator override via `priority=` wins).
   - `lane=<LANE>` -> per-lane mode. Validation happens at step 7 after the `SAID.lanes:` registry is LOAD-WHOLEd; if `<LANE>` is not a declared lane, BLOCK with "Lane `<LANE>` not in the `SAID.lanes:` registry. Declared: <lane-list>." Absent -> single-lane mode.
   - `priority=<High|Medium|Low>` -> explicit; defaults to Medium for non-bugs, High for bugs.
   - `short` -> minimal-shape task; Step 1 trims Q&A to Title + Problem (+ Root cause for bugs); Step 3 unchanged.
   - `auto` -> skill stops only for required operator input/decision. Step 3 Gap/Contradicts is recorded-and-stopped (redirect to `/said:architect` propagate-new-info), never auto-written. Step 1 Q&A retains its default stop.
5. **Read existing tasks file in full.** Compute the next task ID from the lane's `## Lane` `SAID.id-shape:` key (declaration-first, as `flow` / `impl` resolve it); the canonical grammar (feature `<PREFIX>-<NN>`; task IDs collapse the dash inside the feature segment) is the **key-absent FALLBACK**:
   - **Compute task prefix:** strip the dash from `<feature-id>` (e.g., `<FEAT>-NN` -> `<FEAT>NN`).
   - **Single-lane mode (no `lane=` flag):** scan for headings matching `^## <PREFIX>-(\d+):`. Take max NN; new ID = `<PREFIX>-<NN+1>` zero-padded to 2 digits. If no prior single-lane entries exist, start at `01`.
   - **Per-lane mode (`lane=<LANE>`):** scan for headings matching `^## <PREFIX>-<LANE>-(\d+):` (filtered to THIS lane only). Take max NN; new ID = `<PREFIX>-<LANE>-<NN+1>` zero-padded to 2 digits. **Per-lane counter** — each `(feature, lane)` pair has its own monotonic stream, starting at `01` independently.
   - **A `## Fast-track F<NN>` heading never enters the task counter**: it matches no task heading regex.
   - **Legacy IDs do NOT contribute.** Any task heading not matching the canonical regex (e.g., pre-migration entries in projects that haven't run a one-time task-id migration) is excluded from the counter scan. Append-only — never fill gaps from deleted tasks.
6. **Skim companion spec — capture coverage anchors.** Identify which section(s) govern the new task's scope (Per-piece scope / Acceptance Criteria / Implementation pointers / Boundaries — whichever the spec uses). Capture 1–2 lines per relevant section for Step 3 classification. Don't full-read.
7. **Read `docs/features/template-tasks.md`** in full — for authoring discipline AND the id-shape stencil. **LOAD-WHOLE the `SAID.lanes:` registry** (one key line of `TOKEN=root` pairs in the multi-lane root's `## Lane` block; take its rows from `python3 ${CLAUDE_SKILL_DIR}/../board/said_status.py --registry --root <root>`, `<root>` being the directory whose `CLAUDE.md` declares the registry, never by reading the bracket line by eye) and echo its token+count before use; it is the source of the legal lane set; never parse example task IDs to derive it. If it prints `refused:`, HALT with that reason and point the operator at `/said:setup`; never fall back to reading the line or to a glob. Validate the step-4 `lane=` flag now against the declared lanes: if `<LANE>` is not declared, BLOCK per step 4. If the project declares a single lane (no `SAID.lanes:` registry), reject any `lane=` flag.
8. **For a surface-governed task (a screen/UI shape), run Step 0.SC, then classify + resolve from the LOADED registry — never inline** (a structural / data-layer / non-surface task skips it). Classify the task's screen shape; resolve its rule bundle + stencils by filtering the loaded registry (taxonomy/routing/stencils live there). Ambiguous `applies-to` -> ASK in Step 1's batch prompt; never guess or fall back to an inline list.

## Step 0.SC — Load the surface contract (SC-STUB v3)

Run this ONLY when about to reason over a surface-shape rule — the shape vocabulary is the loaded registry's own `applies-to` values, never a list recalled without it. A structural, data-layer, or non-surface task skips it entirely. Then, only if this lane ships a rule registry:

1. Registry path = key-grep `SAID.docs-root:` (scalar) on the `## Lane` block + `/ux/feature-ux-rules.md`. No `SAID.docs-root:` key -> HALT.
2. Registry absent -> bearing-gated: a **surface-bearing** lane (`SAID.surface: <medium>`) FAILs with a named redirect (ship the surface contract) — it cannot proceed with a hollow gate; a `SAID.surface: none` lane SKIPs (proceed without one, never HALT, never invent a rule).
3. Present -> LOAD it WHOLE; echo its `SC-HEADER` `token, N rules`. Missing/malformed sentinel -> HALT. Never grep a single row.
4. Reason over the LOADED registry only; cite rule ids. Never restate or re-derive a mapping from memory.

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
Derived from: feature <feature-id>, lane=<lane-token> (declared in the `SAID.lanes:` registry; declared set = {<lane-set>}), prior counter <max-NN> -> next <new-NN>.

[If task-id is wrong — flag in your reply and skill recomputes before write.]

Detected shape: <the task's shape, from the loaded registry's vocabulary>. Rules in scope: <the registry's routed rule ids for that shape> (skill resolved these from the loaded registry at Step 0.SC).

Reply with answers below (any format; terse OK):

Title: [short imperative title]
Problem: [what needs solving + context, 1-3 sentences; no methodology]
[bug-only] Root cause: [where the bug originates; cite file:line if applicable]
Approach: [what to build, key decisions, no step-lists, no function signatures — skill will append rule-anchor citations from detected UX specs]
Alternatives considered: [optional — only if a rejected option was reasonable]
Reading list: [task-specific files beyond spec's Context-to-load — skill will flag (full read) on UX specs sourced]
Acceptance bullets (skill prefills; strip categories that don't apply):
  - [ ] <spec> #N, #M satisfied (per screen shape)
  - [ ] <endpoint-contract bullet — only for a surface with a wire probe>
  - [ ] <surface-appropriate acceptance bullet — e.g. a recorded UI probe for a visual surface>
  - [ ] <ComponentName> public props preserved (consumed by <ConsumerFeature>)
  - [ ] Quality gates green; no regression outside scope.
Refs: [ADR/UX-spec/feature-spec paths this task CREATES or EDITS; empty otherwise]
Blocked-on question: [<id> | none -- an operator question this task depends on; explicit, never inferred]
Priority: [High|Medium|Low; default Medium / High for bugs]
```

If screen shape was ambiguous in Step 0, ask the operator to pick one before showing the conformance bullet preview. Wait for `ANSWERS:` (or equivalent reply) before authoring.

## Step 2 — Apply hard authoring rules

Before writing, validate the answers against template-tasks.md discipline. Rewrite operator content where it violates:

- **STRICT template adherence (HARD).** Use ONLY the section list in `docs/features/template-tasks.md`: Problem / Approach / Reading list / Acceptance / Fix / Deviations / Gotchas / Out of scope (+ optional `### Root cause` subsection under Problem for bugs). NEVER invent new `###` headers ("Frozen rules to satisfy", "Wire contract probes", "Visual parity reference", "Cross-feature contracts", "Spec changes", "Files modified", "Implementation notes", "Lessons learned", "Discovery" — all forbidden). Frozen-rule conformance / wire probes / visual parity / cross-feature contracts fold into Approach + Acceptance per the rules below. Task bloat dies here.
- **Approach: no step-lists.** "1. Do X. 2. Do Y." -> rewrite as "what-to-build" framing with key decisions called out. If the operator's Approach reads as imperative numbered steps, contract to declarative end-state prose.
- **Approach: cite frozen-rule anchors inline** when the task touches surface-governed shapes. Use the rule ids the loaded registry routed at Step 0.SC. Example: "Reshape per the routed rules — cite ids (e.g. `<ux-spec> #NN, #MM`)." Anchors only — no verbatim paraphrase. Implementer opens the source via Reading list `(full read)`.
- **Approach: no implementation-detail leakage — but name the write-target.** Function signatures, exhaustive file enumerations, code samples that aren't load-bearing -> cut and cite the upstream ADR/UX-spec/spec section. **Do name the unit(s) / file(s) the task edits** — its write-target — as a key decision: a task-level fan-out derives each task's write-set from `Refs:` ∪ the files under the lane's mounts that the Approach names, so a what-to-build that names no target cannot be partitioned and falls to the serial set. Naming the write-target is not enumerating every touched file. A code sample is load-bearing only when the sample ITSELF carries a decision the prose can't (e.g., end-state folder layout for a data-layer-only feature; a literal doc-patch wording).
- **Alternatives considered: only when reasonable.** If the operator listed an alternative that no cold reader would have picked, drop it (per template's bloat-scan rule).
- **Reading list: per-task DELTA only.** If the operator cited files already in the spec's Context-to-load, cut the duplicates — the spec covers the umbrella; the task cites only what's specifically additional. **Flag `(full read)` on UX specs whose anchors are cited in Approach** — implementer re-opens the source at Phase 3 (Implement) start, not CLAUDE.md summaries.
- **Acceptance: observable bullets, conformance content folds in.** Cite spec / ADR / UX-spec anchors; never restate. Skip every category that doesn't apply:
  - Frozen-rule conformance (when task touches surface-governed shapes): `- [ ] <ux-spec> #NN, #MM satisfied (per the loaded registry)`.
  - Wire contract (when a task changes a wire method): `- [ ] GET /endpoint — response schema matches captured bytes (per the surface's wire probe)`.
  - Surface parity (visual surface only): `- [ ] recorded UI probe matches the reference — zero diff`.
  - Cross-feature contracts (when spec's Boundaries lists Sacred consumers): `- [ ] <Entity>Cell public props preserved (consumed by features/<entity>/)`.
  - Quality gates umbrella bullet.
  
  Typical task ends with 5–10 Acceptance bullets total. Bug tasks may be even leaner (Problem + Fix + Gotchas per template-tasks.md "depth varies").
- **Refs: empty by default.** Only fill if the task creates or edits an ADR / UX-spec / feature-spec. Reading list ≠ Refs. Refs is the write-set; Reading list (+ Approach citations) is the read-set.
- **Blocked-on question (optional field).** When the operator's answer names an operator question this task depends on (`Blocked-on question: <id>`), place `**Blocked-on question:** <id>` as a field after `**Refs:**` (a field, never a `###` section); `none` -> omit it. The id is engine-minted (a resolved §D id, else `Q-<n>`), explicit and never inferred from prose. A blocked task is held until it is lifted (`template-tasks.md`). The hold is lifted by one line in the log's `## Lifted holds` section, `- <id> lifted-by: user@WR-<seconds> -- "<verbatim quote>" -- <date> [supersedes: <prior>]`, that cites the operator's answer as a ruling recorded with the `ruled` skill in the work's `rulings.md` (example: `- Q-1 lifted-by: user@WR-1790160000 -- "use the Postgres advisory lock" -- 2026-09-23`). `user` is a fixed role word (the role of the cited answer); the person's name belongs to the ruling.
- **Fast-track field.** When the feature has an open run (a `## Fast-track F<NN>` block with an empty `closed:`), the new task joins it: place `**Fast-track:** F<NN>` after `**Refs:**` (after `**Blocked-on question:**` when both are present), a field, never a `###` section. A feature with no open run gets no field.
- **Status: `Todo (YYYY-MM-DD)`** with today's creation date.
- **Fix / Deviations / Gotchas: HTML-comment placeholders.** Phase 3 close-of-task review fills them.

If a §D-class question surfaces during Q&A — an operator question the skill cannot silently resolve (cross-cutting choice, contract conflict, sequencing ambiguity) — STOP authoring. Surface the question explicitly; wait for the operator's answer; then proceed. Do not bake guesses into the new task.

## Step 3 — Spec coverage gate (read-only — classify + flag, never write)

Classify the new task vs the companion spec (anchors from Step 0 step 6). This gate **detects and flags**; it does **not** write spec content — authoring a spec edit is `/said:architect`'s charter, not this skill's (a task-appender never writes a sibling-owned artifact; ADR-SAID-S01 charter boundary).

- **Covered** — spec already mandates this requirement -> proceed to Step 4. No flag.
- **Gap** — spec silent or partial on the new task's requirement -> **record a `### Gotchas` flag** on the new task (`Spec GAP vs <spec-path> § <section>: <one-line>. Propagate via /said:architect propagate-new-info before impl.`) and **STOP**, redirecting the operator to `/said:architect <spec-path>` (propagate-new-info branch) to author the spec edit. Do not draft or write the edit here.
- **Contradicts** — task Approach diverges from a stated spec rule -> **record the `### Gotchas` flag** and **STOP** with the redirect; the operator resolves via `/said:architect` propagate-new-info (surgical bullet rewrite) or re-architecture (`/said:architect <scope-path> output-name=<feature-id>-v2`) for a fundamental scope shift. Never reconcile by editing the spec here.

**Mode note.** `auto` does not change this: a Gap/Contradicts is an owed architect action — recorded-and-stopped, never auto-written (the spec-write capability is removed; charter boundary). `bug` tasks default to Covered (bug = code/spec divergence, not a new requirement); the gate still runs to catch the rare spec-silent case, flagging it the same way.

## Step 4 — Append (the tasks log only)

**Write the task (this skill writes the tasks log only — never the spec):**

1. Append task block + summary table row (canonical shape per Step 0 step 5).
2. `Refs:` reflects what this skill wrote — a task-appender never edits the spec, so `Refs:` is empty unless the task itself is a doc-editing task that creates/edits an ADR. Not future intentions.

Use the canonical section order from template-tasks.md:

```
## <new-task-id>: <Title>
# project-canonical shape — see `docs/features/template-tasks.md` stencil

**Status:** Todo (YYYY-MM-DD)
**Priority:** <High|Medium|Low>
**Refs:** <paths or empty>
[optional] **Blocked-on question:** <id>
[optional] **Fast-track:** F<NN>

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

## Fast-track runs

A fast-track run defers a named set of tasks' per-task Deliver gates (review-ux, the code review, review-qa, accept) to one close over the set. Its switch is a recorded, operator-confirmed skip of per-task gates, the same class `debrief` records as a Gate-skip line: the block records the operator's words; there is no transcript check and no ruling lookup. Both forms run in the main context only, like every write to the log. Of the preflight, the fast-track forms run Step 0 items 1-3 and 5 (feature id, tasks file, companion spec, and item 5's read of the log in full, without its task-id computation); they parse no other flag and read no lane registry. Task ids given to the open form are normalized to UPPERCASE, as the feature id is.

**Open: `fast-track "<task ids>"`.** Skip Steps 1-3 (no task entry is authored). Append, after a `---` separator:

```
## Fast-track F01
feature: PROJ-01
opened: 2026-01-15, HEAD 1a2b3c4
operator: "fast-track 03 and 04, one close for both" (2026-01-15; ruling WR-1790160000)
tasks: PROJ-01-03, PROJ-01-04
closed:
```

- The fields are `feature:`, `opened:`, `operator:`, `tasks:` and `closed:`, in that order. `opened:` is the date and the HEAD the run opened on (`<date>, HEAD <sha>`, read with `git rev-parse --short HEAD`; the sha is the base the run's code review diffs from). There is no `dirty` at open: work already uncommitted at open falls inside the run's diff and is reviewed with it. When HEAD cannot be read (not a git tree, no commit yet), refuse the open and write nothing. `operator:` is the operator's words quoted with their date, typed in any session and relayed verbatim; append `; ruling <id>` only when a ruling id exists. `closed:` is empty at open.
- Run ids are `F01`, `F02` per feature: next = the highest `## Fast-track F<NN>` in the log + 1, two digits, never gap-filled.
- Refuse, write nothing and name the reason when: a run of the feature is already open (a block with an empty `closed:`); an id is already listed in a run (its `tasks:` line or a task's `**Fast-track:**` field); an id has no `## <id>:` heading in the log; an id is already at `Status: Done`. An id listed in a closed run is never listed again: work on it after its close is a new task.
- Only the operator's words open a run. A worker or subagent proposes a run in one line and opens nothing. Off is never implied by a count or by every task being Done: a run ends only with its close.

**Membership.** A run's listed set is the ids on its `tasks:` line plus every task carrying `**Fast-track:** F<NN>`. The `tasks:` line is never rewritten; a task added while the run is open joins through its own field (Step 2).

**Close: `fast-track F<NN> closed`.** Refuse when the log has no `## Fast-track F<NN>` block, and when the run's `closed:` is already filled. Then, before reading any report, refuse when any task in the run's listed set is not `Status: Done`: name the ids and write nothing. The required reports are `review-qa-<feature>-F<NN>.md`, `accept-<feature>-F<NN>.md`, and one `review-<checker>-<feature>-F<NN>.md` for each Checker in `SAID.reviewers:` (read WHOLE) that `review-ux` runs, an agent-form Checker; a lane whose list has none (empty, or only an oracle Checker the reviewer gate recomputes) requires the two, and a `doc-editorial` Checker on a lane whose `SAID.mounts:` is `none` is not required (it runs as N/A and writes no file). Read each in the feature's working folder: a missing required report refuses, and a report reads PASS only when its verdict line says PASS (`Verdict:` in a gate report, the `verdict:` header in a Checker verdict; MANUAL-PENDING is not PASS). The form refuses unless every named report reads PASS. On PASS, write the one `closed:` line in place, the only edit to the block:

```
closed: 2026-01-16, HEAD 1a2b3c4, reports review-qa-PROJ-01-F01.md, accept-PROJ-01-F01.md
```

Record the date, HEAD, plus `dirty` after the sha when the tree has uncommitted changes (`HEAD 1a2b3c4 dirty`), and the names of exactly the reports read. The gates that wrote the reports stay read-only; this skill is the log's one writer.

## Step Final — Exit

For a fast-track form, report the run id and either the ids listed (open) or the `closed:` line written (close), or the refusal and its reason; nothing else below applies to it. When a fast-track reply says what the close will need, name exactly the close form's required report set above; an oracle Checker such as `cli-gate` writes none.

Report to operator:

- New task ID + title.
- Tasks file path + new total task count.
- Summary table updated (yes/no).

**Auto-mode addendum to report** (when `auto` was set):
- Step 3 outcome: Covered / Gap (flagged + stopped) / Contradicts (flagged + stopped) — any Gap/Contradicts names the `/said:architect propagate-new-info` action owed before `/said:impl`.

Hard exit. Do NOT begin implementation. Do NOT spawn coding agents. Phase 3 implementation is the operator's separate call — the new task is now in the backlog; the operator picks when to work it.

Suggested next step: "Task `<new-task-id>` appended. Run `/said:impl <new-task-id>` to drive Phase 3 — feature-id auto-derived from the task-id prefix."

## Anti-patterns

- **Don't auto-resolve clarifying questions.** If the operator's answers leave gaps that would force a guess on substance (Approach, Acceptance), ASK rather than fill.
- **Don't write step-lists in `### Approach`.** The single most violatable rule, inherited from `/said:architect` Pass 3. Methodology belongs to Phase 3.
- **Don't include code samples that aren't load-bearing.** Same rule as `/said:architect` Pass 3.
- **Don't duplicate spec's Context-to-load in Reading list.** Per-task delta only.
- **Don't begin implementation.** This skill writes the task entry; that's the entire output. NEVER spawn coding agents; NEVER invoke `/said:impl` automatically (the operator triggers it after this skill exits); NEVER begin code edits.
- **Don't run on features without an existing tasks file.** Redirect to `/said:architect` for INITIAL spec + tasks creation.
- **Don't modify or reorder existing tasks.** Append-only per `template-tasks.md`. The exceptions (per template-tasks.md) are Status updates with `### Fix`, which are close-of-task review territory, not this skill, and the `closed:` line of a fast-track block, which only the `fast-track F<NN> closed` form writes.
- **Don't fill task-ID gaps.** Per-lane monotonic counter — the highest existing NN for THIS `(feature, lane)` pair gets `+1` regardless of deleted-task gaps below. Append-only matches git-log sequencing.
- **Don't cross-pollinate counters across lanes.** Each `(feature, lane)` pair has its own independent counter — the next ID for lane-A doesn't increment based on lane-B's counter. Different lanes own different task streams.
- **Don't mix legacy IDs into the counter scan.** Task headings not matching the canonical regex live in a separate namespace; the canonical counter starts fresh at `01` regardless of how many legacy entries exist. After migration (if applicable), all IDs share the canonical shape and this anti-pattern dissolves.
- **Don't bypass `Refs:` discipline.** Refs is for ADR/UX/spec EDITS the task creates, NOT for everything the task READS. Reading is captured in Reading list.
- **Don't conflate bug tasks with planned tasks.** Bug tasks have `### Root cause`; planned tasks don't. The `bug` flag is the explicit signal — never auto-detect via problem-text keyword scanning (false positives corrupt the calibration target).
- **Don't invent new `###` sections in task entries.** `docs/features/template-tasks.md` is the exhaustive section list: Problem / Approach / Reading list / Acceptance / Fix / Deviations / Gotchas / Out of scope (+ optional `### Root cause` under Problem for bugs). Forbidden: `### Frozen rules to satisfy`, `### Wire contract probes`, `### Visual parity reference`, `### Cross-feature contracts`, `### Spec changes`, `### Files modified`, `### Implementation notes`, `### Lessons learned`, `### Discovery`, `### Pass N` — all fold into Approach + Acceptance.
- **Don't skip the Step 3 spec coverage gate.** Even for trivial tasks, classify before appending. Silent skip = spec drift.
- **Don't write spec content.** This skill classifies coverage and flags a Gap/Contradicts; the spec edit itself is `/said:architect`'s propagate-new-info branch (charter boundary). A task-appender that writes a sibling-owned spec is the drift this corrects.
