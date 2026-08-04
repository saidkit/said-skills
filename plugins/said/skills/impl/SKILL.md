---
name: impl
description: >
  SAID/Phase 3 (Implement) driver — drives a feature task from `Status: Todo`
  to `Status: Done` through three phases: Phase A (Classify + Inventory),
  Phase B (Implement rule-by-rule under TDD discipline), Phase C (Verify +
  close-of-task 5-step). Composes with `/said:review-ux` at Phase C close
  for web/UI features. Triggered ONLY by the explicit command
  "/said:impl <task-id|feature-id> [<task-id> ...]" — feature-id is
  auto-derived from the task-id prefix (regex captures `<PREFIX>` + `<NN>`
  → `<PREFIX>-<NN>`); a bare feature-id runs whole-feature mode (every
  `Status: Todo` task in order).
  NOT for backlog additions — that's `/said:add-task`. NOT for spec
  authoring — that's `/said:architect`.
---

# Feature Impl — Phase 3 (Implement): Per-Task Driver

This skill drives a Phase 2-architected task from `Status: Todo` to `Status: Done` through three phases: Phase A classifies + inventories the work against the task's Acceptance checklist; Phase B implements rule-by-rule under TDD discipline; Phase C verifies via side-by-side walk + quality gates + `/said:review-ux` + close-of-task 5-step review. Phase 2 is the input boundary (this skill reads what `/said:architect` produced); commit + push are the output boundary (operator-triggered, never auto-driven).

The skill itself is the orchestrator — there is NO separate agent. You — the main agent — drive three sequential phases within ONE invocation. Each phase declares its stance up front so verification work and implementation don't blur. **Operator pauses at every phase boundary are mandatory; no auto-progression.**

**Single-pass goal.** Multiple "Pass 1 / Pass 2 / Pass 3" entries in a closed task's `### Fix` block = failure mode. The whole point of conformance-fold Acceptance (Phase 2 settlement) + 3-phase driver is to make every task close single-pass. If you find yourself thinking "I'll defer X to a Pass 2" mid-Phase B — STOP. Either widen Phase B to satisfy X now, or surface X as an operator decision (declare scope-creep, or split into a new task via `/said:add-task`).

**Project-type duality.** Web-app projects (`docs/ux/` exists) run side-by-side playwright walk + `/said:review-ux` at Phase C; server-app projects drop visual parity + fall back to `docs/qa/feature-ux-checklist.md` filtered by `applies-to`. Auto-detected in Step 0.

## When this fires

The user invokes:

- `/said:impl <task-id>` — single-task run; feature-id auto-derived (see Step 0).
- `/said:impl <task-id-1> <task-id-2> ...` — explicit batch; all task-ids must share one feature.
- `/said:impl <feature-id>` — whole-feature mode: drives every `Status: Todo` task in file order with operator pause between. Idempotent — re-running picks up at the next `Status: Todo` after closures.

If a task ID doesn't resolve, batch task-ids don't share a feature, or a task is already `Status: Done` — BLOCK + redirect (`/said:add-task <feature-id>` for follow-ups, never amend closed tasks; `/said:architect` for new features).

If the operator's request is to plan or architect a NEW feature — this is the WRONG skill. Redirect to `/said:architect`. If to add a new task — redirect to `/said:add-task`.

## Common compositions (upstream → this skill)

Two canonical operator flows feed tasks into `/said:impl`:

**A — Planned feature** (Phase 1 → 2 → 3):

```
/said:scope-refine docs/working/<feature>/handoff.md
/said:architect docs/working/<feature>/scope.md
/said:impl <task-id>
```

(Use `/said:scope-grill` instead of `/said:scope-refine` for thin-idea ideation without a handoff doc.)

**B — Ad-hoc bug fix** (Triage → Append → Drive):

```
/said:triage <bug>
/said:add-task <feature-id> bug
/said:impl <task-id>
```

(Skip `/said:triage` when root cause is already known.)

No one-shot wrapper exists by design. Mandatory operator pauses at each phase boundary are the discipline that prevents the multi-pass churn the 3-phase driver replaces.

## Step 0 — Preflight

Resolve inputs and ground in calibration sources before Phase A starts:

1. **Resolve mode + feature-id + tasks file** via SAID-canonical disambiguation:
   - **Normalize** each arg to UPPERCASE before matching (canonical grammar mandates uppercase in docs / tasks files; lets the operator type any case at the command line).
   - Single arg matching `^[A-Z]+-\d+(-[A-Za-z0-9]+)*$` (e.g., `<FEAT>-NN`, or a suffixed per-lane feature-id such as `INIT-28-BE` / `INIT-02-BE-divisions`) AND a tasks file resolves (bare `<arg>.tasks.md` OR slug-suffixed `<arg>-*.tasks.md` via the resolver below) → **whole-feature mode**; build batch = every `Status: Todo` heading in file order. (The "AND a tasks file resolves" guard is load-bearing: a per-task id like `INIT-28-FE-16` matches the shape but has no `INIT-28-FE-16.tasks.md`, so it correctly falls through to the task regexes below.)
   - Args matching the canonical new-task regex `^([A-Z]+)(\d+)-.+$` → feature-id = `${1}-${2}` (dash collapsed inside the feature segment is re-inserted to produce the feature-id); **single-task or explicit batch mode**.
   - Legacy fallback (projects pre-migration): args matching `^([A-Z]+-\d+)-.+$` → feature-id is the leading captured segment. Post-migration projects won't trigger this path — their task IDs already match the canonical regex above.
   - Resolve tasks file path. Conventionally `docs/features/<feature-id>.tasks.md`. If missing, scan `docs/features/` for files matching `<feature-id>*.tasks.md` (slug-suffixed convention, e.g., `TEST-01-tests.tasks.md` for feature `TEST-01`); if exactly one match, use it; if multiple matches, ASK the operator which to use. Symmetric with the companion-spec fallback in step 2.
   - Verify every task arg has a `## <task-id>:` heading in the resolved tasks file. All args in a batch must share one feature.
   - BLOCK + redirect on failure: missing tasks file (no glob match) → `/said:architect`; missing task heading → `/said:add-task`.
2. **Resolve companion spec path.** Conventionally `docs/features/<feature-id>.md`; sub-phased features use slug-suffixed names (e.g., `<feature-id>-phaseB.md`). If `<feature-id>.md` missing, scan `docs/features/<feature-id>*.md`; ask operator to confirm.
3. **Read task body in full.** Locate `## <task-id>:` in the tasks file and read the whole entry. Verify `Status:` is `Todo (YYYY-MM-DD)`; BLOCK on Done per "When this fires" redirect.
4. **Skim companion spec § Per-feature scope** for this task's piece. Don't full-read the spec — the task body's Reading list is canonical.
5. **Read `docs/features/template-tasks.md`** in full. Phase C's close-of-task 5-step review enforces it.
6. **Detect project type.** `[ -d docs/ux ] && echo web || echo server`. Auto-detected.
7. **Skim project calibration.** Scan `docs/features/*.tasks.md` for the most recent closed task with a multi-pass `### Fix` block (failure mode this driver prevents) and the most recent single-pass close (target shape every task lands on). If the project has no closed tasks yet, skip — the rules below stand on their own.
8. **Resolve project quality-gate commands.** Skill never hardcodes language-specific commands. Resolution chain (first-match wins):
   - **Primary** — `CLAUDE.md` § Development Commands table: identify umbrella target (`pre-commit`, `qa`, `check`, `all`).
   - **Secondary** — if `Makefile` present: prefer `make pre-commit`; fall back to `make qa` / `check` / `all`.
   - **Tertiary** — if `package.json` present (JS/TS only): scripts named `pre-commit` / `qa` / `check` / `validate`; invoke via `npm run` or `bun run` per lockfile.
   - **Quaternary** — operator-prompt: "What's this project's full quality-gate command + per-step typecheck + per-step test?" Cache for session; never persist to SKILL.md.

   Cache placeholder bindings for Phase B / Phase C reference:
   - `<typecheck>` — fast verifier per-rule (e.g., `make typecheck`, `bunx tsc --noEmit`, `go vet ./...`).
   - `<tests>` — test command (e.g., `make test`, `bun run test:src`, `go test ./...`).
   - `<lint>` — lint command (e.g., `make lint`, `bunx biome lint`, `golangci-lint run`).
   - `<quality-gates-umbrella>` — full chain at Phase C close (e.g., `make pre-commit`).

Don't load source UX specs upfront — the task body's Reading list `(full read)` flag governs what to open at Phase A. Don't pull additional ADRs — Phase A's inventory surfaces task-specific needs.

## Phase A — Classify + Inventory

> **Stance: read the task. Classify it. Declare implementation discipline. Inventory current state against the Acceptance checklist with file:line evidence. Verification work, not coding. Report and STOP.**

Procedure:

1. **Classify task size as S / M / L** per the defaults below:
   - **S** (≤~50 LOC, bug fix or polish, single screen, ≤2 rule-anchors cited in Approach): skip the inventory table; declare classification + discipline; produce a one-paragraph plan; STOP for operator OK; jump to Phase B.
   - **M** (~50–300 LOC, single screen-shape, 3–6 rule-anchors): full inventory.
   - **L** (~300+ LOC, multi-screen or multiple rule clusters): full inventory; flag any pieces that should split into separate task IDs (escalate to operator if so — that's an `/said:add-task` decision).

2. **Declare discipline** in one sentence:
   - **TDD (default)** — red-green-refactor: stubs → failing tests → green → refactor. No mocks (mock services are production code under `IS_MOCK` per the service-adapter-ADR; NEVER `vi.mock()`).
   - **Structural — declarative-test/no-test (carve-out)** — pure folder moves / import retargeting / doc edits where there's no new behavior to test. Justify the carve-out in one sentence. Never silently skip TDD.

3. **If S — output classification + discipline + plan paragraph. STOP. Skip steps 4–6.**

4. **Read in parallel** — every Reading-list UX spec flagged `(full read)`, AND every current-implementation file under the entity's feature dir cited in Reading list (or implied by Approach — e.g., `features/<entity>/` if the task migrates that entity). UX specs ground the rule anchors; current-impl files ground the "Evidence" column in step 6. Cite each in the inventory output with one-line anchor (e.g., "Read `lists.md` — rules #20, #23, #26 in scope per task Approach"; "Read `features/<entity>/screens/Browser.tsx:1-120` — current shape baseline").

5. **Run wire-contract probes** for every endpoint cited in the task's Acceptance:
   - Web project with playwright available: navigate the dev server route via `mcp__playwright__browser_navigate`; capture network via `mcp__playwright__browser_network_requests`. Save response payload to `docs/working/<feature-id>/<task-id>-wire-<endpoint-slug>.json`.
   - Otherwise: `curl -H "Authorization: Bearer <dev-bypass-JWT>" <endpoint>`; capture stdout to the same path.
   - For each captured response, note drift between captured bytes and the FE schema in the task body's Approach. **Drift = blocker; surface in inventory.**
   - If the dev server is down, ASK the operator to start it (`make dev` or equivalent) before re-running Phase A.

6. **Inventory table.** One row per `[ ]` Acceptance bullet, **plus one row per file named in the companion spec's §Implementation pointers (or equivalent file list)**. If a spec-named file doesn't exist on disk, the row's `Work` column reads `CREATE`. Phase A cannot complete with a spec-named file unaccounted-for — silently skipping a mandated component is the slip vector this rule closes. Columns: Bullet / Currently satisfied? (yes / no / partial) / file:line evidence / Work to satisfy.

   Example shape:

   | Acceptance bullet | Satisfied? | Evidence | Work |
   |---|---|---|---|
   | `lists.md` #20, #23, #26 satisfied | no | `features/<entity>/screens/Browser.tsx:42` mounts inline `<Input>`; needs `<TableGlobalSearch>` per #26 | Replace inline state with `useTableQueryParams`; mount `<DataTableToolbar>` |
   | GET `/<entity>/terms` — Zod schema matches captured bytes | no | Captured `{data, pageCount, totalCount}`; FE schema expects `{items, total, page, limit}` | Rewrite `<entity>TermListResponseSchema` to wire shape |
   | Walked side-by-side with `/tasks` — zero visible diff | no | Not walked | Phase C playwright walk |
   | Spec §14 names `features/<entity>/components/<entity>-users-table.tsx` | no | Not on disk | CREATE |
   | Spec §14 names `features/<entity>/components/<entity>-users-table-columns.tsx` | no | Not on disk | CREATE |

7. **STOP for operator review.** Brief status: "Phase A complete. Inventory above; <N> bullets unsatisfied, <M> with wire drift flagged. Reply OK to proceed to Phase B (Implement), or flag anything to revise first."

8. **Escalation path — Approach unsatisfiable.** If the inventory reveals the task's Approach is structurally unable to satisfy Acceptance (wire shape differs from client schema in ways the task didn't anticipate; an Acceptance bullet has no work that can satisfy it without violating a Boundary; a cited rule conflicts with another cited rule), do NOT proceed to Phase B. Surface the gap to operator with one-line diagnosis + recommended re-spec path: `/said:architect <scope-path> output-name=<feature-id>-v2` for re-architecture, or `/said:add-task <feature-id>` if the gap is a follow-up scope. Proceeding against an unsatisfiable Approach is how Pass 1 / Pass 2 / Pass 3 drift begins.

## Phase B — Implement

> **Stance: turn `[ ]` into `[x]` rule-by-rule. TDD red-green-refactor by default; declarative-test or no-test for declared structural carve-outs. One rule, one confirmation in chat. NO batching. NO "I'll defer X to a Pass 2" thinking. `<typecheck>` after every changed file.**

Procedure:

1. **Order rules by blast radius** (cheapest first, highest cross-cut leverage first):
   - `errors.md` rules — `parseResponse` wrap, `silentError` meta, `RouteSlot`. Cheapest to satisfy; biggest blast radius if missing.
   - `shell.md` rules — `PageHeader` band, AppShell `SidebarInset min-w-0`.
   - `lists.md` / `form.md` / `fields.md` rules — entity-shape rules; deepest change.
   - Wire-contract reshape — Zod schema rewrite per captured bytes from Phase A probes.
   - Visual-parity gaps — DEFERRED to Phase C side-by-side walk; don't pre-tune.

2. **TDD path (default):** for each rule, write the failing test first (red), implement until green, refactor. Tests live next to source per the feature-structure-ADR; co-location is non-negotiable. **NEVER `vi.mock()`** — mock services are runtime-selected production code under `IS_MOCK`, not test mocks. Mocking the data layer for a test is the discipline-collapse failure mode.

3. **Structural path (carve-out only):** skip the red phase — change the source, run `<typecheck>` + `<tests>` to verify no regression. New behavior REQUIRES TDD path; if a structural carve-out turns out to need new behavior mid-flight, ESCALATE to operator and re-declare discipline.

4. **After each rule satisfied** — confirm in chat: file:line of change + which Acceptance `[ ]` bullet flips to `[x]` + `<typecheck>` result. Wait for operator's `next` (or equivalent) before starting the next rule. **NO batching multiple rules into one confirmation.** The discipline collapses immediately if you do.

5. **Tag every changed callsite:** `// <task-id>` (no suffix).

6. **Operator can pause anywhere** to course-correct. Treat any operator interjection as a STOP — finish the current `<typecheck>`, report state, wait for direction. The operator has full context the skill doesn't.

Phase B continues until all Acceptance `[ ]` bullets except visual-parity are flipped. Visual-parity bullets close in Phase C.

## Phase C — Verify and close

> **Stance: read the task body cold. Walk the migrated URL side-by-side with the reference URL. Run quality gates. Invoke `/said:review-ux` for web/UI features. Run the close-of-task 5-step. Flip Status. Hand off to operator for commit.**

Procedure:

1. **Side-by-side playwright walk** (web project + UI surface only):
   - Migrated URL (e.g., `/<entity>`) vs reference URL (from task's Acceptance bullet, e.g., `/tasks`).
   - Enumerate every visible difference: toolbar / header / sheet / pagination / empty-state / chip styles / spacing.
   - **If diff non-empty** → which Acceptance bullet is unsatisfied → RETURN TO PHASE B for that bullet. Don't paper over with "minor cosmetic" — every visible diff is the visual-parity bullet's scope.
   - **If diff empty** → flip the visual-parity `[ ]` to `[x]`.

2. **Quality gates:** run `<quality-gates-umbrella>` (resolved in Step 0 #8 — typically `make pre-commit` or equivalent). If the project lacks an umbrella target, chain `<typecheck> && <tests> && <lint>` plus any project-defined dead-code check. Per-merge build commands (e.g., `make build`) and project-specific test scoping (e.g., parity tests under `src/engine/` for <PROJECT>) are project conventions invoked via the resolved targets — not skill-driven literals. If any gate fails → STOP and report; fix; rerun. Don't close on red.

3. **Invoke `/said:review-ux`** if web/UI feature with UI changes. Pass the task-id; the skill spawns `said:review-ux-agent` against `docs/qa/feature-ux-checklist.md` filtered by screen shape; returns structured PASS / FAIL / SOFT-FLAG report.
   - Any FAIL → RETURN TO PHASE B for the failing rule.
   - SOFT-FLAGs only → operator decides whether to address now or defer.

4. **Invoke generic code-review — CRITICAL for code quality.** Default: spawn a read-only code-review subagent via the Agent tool (use a dedicated code-reviewer agent if your harness provides one, else a `general-purpose` agent prompted for review; a faster model tier suffices for review iterations, consistent with `said:review-ux-agent`'s model choice). Prompt: task-id + spec path + task body + `git diff` of Phase B's changes + `CLAUDE.md` pointer. Focus: bugs / logic errors / security / race conditions / convention violations; confidence threshold ≥80 (the agent already enforces this).
   - **Skip cases** (with reason logged in chat — never silent): structural carve-out declared at Phase A (no review-worthy delta); OR operator explicit-override for trivial-surface tasks (one-line bug fix, doc-only edit, etc.).
   - **Critical findings** → RETURN TO PHASE B for the issue.
   - **Soft findings** (≥80 confidence but not Critical) → operator decides: address now or defer.
   - Single-reviewer is the SAID default; operator can spawn 2-3 parallel code-review subagents along distinct lenses (simplicity/DRY + bugs/correctness + conventions) if the surface warrants the heavier coverage.

5. **Run close-of-task 5-step review per `docs/features/template-tasks.md`** — leak scan / gotcha harvest / deviation check / fill `### Fix` / bloat scan. Two nuances:
   - **Leak-scan ADR/UX proposals** (forward-looking rules surfaced during implementation) promote directly to the destination ADR / `docs/ux/*.md` and cite the edited path in `Refs:`. If a rule needs more refinement before promotion, it stays in operator workspace as private process — never cited from task body.
   - **`### Fix`** is one verification line (`Tests N → M; typecheck + lint clean.`) + optional one-liners for spec edits. NO file enumerations (git is canonical); NO test-output dumps; NO `**Files modified:**` blocks.

6. **Flip Status** to `Done (YYYY-MM-DD)`. The ONLY mutations allowed at close:
   - `Status:` line.
   - `### Fix` body (from HTML-comment placeholder to filled).
   - `### Deviations` body (optional, only if departed from Approach).
   - `### Gotchas` body (optional, only if non-obvious learnings).
   - `Refs:` line (only if task created or edited an ADR / UX-spec / feature-spec — write-set discipline).
   - Acceptance bullets — flip `[ ]` to `[x]` (or `[N/A — reason]`).
   - Summary table row — Status column update.

   **NEVER invent new `###` headers when closing.** The template-tasks.md section list is exhaustive: Problem / Approach / Reading list / Acceptance / Fix / Deviations / Gotchas / Out of scope (+ optional `### Root cause` under Problem for bugs). Forbidden: `### Frozen rules to satisfy`, `### Wire contract probes`, `### Visual parity reference`, `### Cross-feature contracts`, `### Spec changes`, `### Files modified`, `### Implementation notes`, `### Lessons learned`, `### Discovery`, `### Pass N`. This skill is the last line of defense against ad-hoc section invention.

7. **Hand off to operator for commit.** Brief status: "Task `<task-id>` closed at `Status: Done (YYYY-MM-DD)`. Quality gates green. `/said:review-ux` <PASS / SOFT-FLAGs deferred / N/A non-UI>. Code-review <PASS / Soft-deferred / SKIPPED — reason>. Commit when ready; commit-msg per repo convention (e.g., `SE-NN`). Next task in batch: <next-task-id or 'none — batch complete'>."

For batch runs (multiple task IDs): pause for operator `proceed` before re-entering Phase A on the next task. NO auto-progression across tasks.

## Step Final — Exit

Report:

- Task ID closed; `Status: Done (YYYY-MM-DD)`.
- Phase A inventory: <N> bullets satisfied at start / <M> at close.
- Phase B rules implemented: <list>.
- Phase C: side-by-side walk PASS/N/A; quality gates PASS; `/said:review-ux` <PASS / SOFT-FLAGs / N/A>; code-review <PASS / Soft-deferred / SKIPPED — reason>.
- `### Fix` / `### Deviations` / `### Gotchas` summary (one-line each).
- `Refs:` filled? (yes — paths / no).
- ADR / UX-spec edits made? (yes — paths / no).
- Next task in batch (or batch complete).

Hard exit. Implementation is done; commit is operator-triggered. Do NOT commit. Do NOT push. Do NOT mark batch complete until all tasks closed.

## Anti-patterns

- **Don't merge with `/said:add-task`.** Add-task creates the backlog entry; this skill implements an existing entry. Separate skills, separate phases of the per-task lifecycle.
- **Don't subsume `/said:review-ux`.** The UX gate is deliberately separate; this skill INVOKES it at Phase C, doesn't replace it. The split exists because "implementation agent declares done, QA agent rubber-stamps" is the regression-shipping pattern the separation guards against.
- **Don't batch rules in Phase B.** "I'll satisfy errors.md #1 + #2 + #5 in one commit" = discipline collapse. One rule, one confirmation, one chat message. The agent's tendency to bulk-edit is the failure mode this discipline exists to prevent.
- **Reference comments: `// <task-id>` only.** NOT `// <task-id>: <anything>` — the suffix is what produced the prose problem.
- **Don't auto-progress phase boundaries.** Operator pauses at Phase A → Phase B and Phase B → Phase C are mandatory. If the operator reply is silent or ambiguous, ASK rather than proceed.
- **Don't run on `Status: Done` tasks.** BLOCK; for follow-ups on COMMITTED Done tasks (`git log --all --grep <task-id>` non-empty), redirect to `/said:add-task`. Pre-commit Done tasks MAY be amended in place per template-tasks.md pre-commit carve-out — operator gate via mid-flight rule below.
- **Don't silently fold mid-flight scope additions.** When operator's message during any phase introduces a requirement not in the task's Approach, STOP and classify before proceeding:
   - **Within scope** (Approach implicitly covers it) → proceed.
   - **Scope-creep, task uncommitted** (`git log --all --grep <task-id>` empty) → propose in-place amendment to Approach + Acceptance + `### Deviations` note documenting the late fold-in; re-run `/said:add-task` Step 3 spec coverage gate for the new requirement; operator confirms before write.
   - **Scope-creep, task committed** → redirect operator to `/said:add-task <feature-id>` for the new requirement. Current task stays as shipped.
  Never silently fold; never silently split. The classification IS the discipline.
- **Don't invent new `###` headers when closing tasks.** The section list in template-tasks.md is exhaustive. Any new header is a regression to the multi-pass drift the conformance-fold settlement retired.
- **Don't extend or wrap a generic multi-pass feature-development skill.** Those produce the multi-pass churn this driver escapes. `/said:impl` supersedes them for SAID-architected features (any feature with `docs/features/<feature>.tasks.md`); a generic feature skill stays available for non-SAID one-off feature work.
- **Don't make TDD optional.** TDD is the default discipline. Structural carve-out (folder moves / import retargeting / doc edits) is rare; declare it explicitly at Phase A with one-sentence justification. Silently skipping TDD on a TDD-fit task is the discipline-collapse failure mode.
- **Don't silently skip Phase C code-review.** It's CRITICAL for code quality and runs by default. Skip ONLY when structural carve-out was declared at Phase A OR the operator explicit-overrides for trivial-surface tasks with reason logged in chat. Quality gates + `/said:review-ux` together do NOT catch deep logic / security / race-condition bugs — those need a dedicated code-review subagent.
- **Don't auto-spawn implementation agents from inside this skill.** Claude Code constraint: no nested subagent spawning. If an `--autonomous` mode is ever built (deferred), fan-out happens at SKILL level only.
- **Don't bypass `Refs:` write-set discipline.** Refs is for ADR / UX-spec / feature-spec paths the task **creates or edits**. Reading list is the read-set. Refs is not for citing everything relevant.
- **Don't commit.** Commit is operator-triggered. The skill writes the task close + reports state; operator runs `git add` + `git commit` with the right commit-msg prefix per project convention.
- **Don't load source UX specs upfront in Step 0.** The task body's Reading list `(full read)` flag governs what to open at Phase A. Pre-loading specs the task doesn't cite is context bloat.
