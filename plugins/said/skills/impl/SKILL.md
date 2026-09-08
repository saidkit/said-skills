---
name: impl
description: >
  SAID/Phase 3 (Implement) driver — drives a feature task from `Status: Todo`
  to `Status: Done` through three phases: Phase A (Classify + Inventory),
  Phase B (Implement rule-by-rule under test-first discipline), Phase C (Verify +
  close-of-task 5-step). Composes with `/said:review-ux` at Phase C close
  for features with a visual surface. Triggered ONLY by the explicit command
  "/said:impl <task-id|feature-id> [<task-id> ...]" — feature-id is
  auto-derived from the task-id prefix (regex captures `<PREFIX>` + `<NN>`
  → `<PREFIX>-<NN>`); a bare feature-id runs whole-feature mode (every
  `Status: Todo` task in order). Two SKILL-level fan-out forms
  `/said:impl <task-id> arm` and `/said:impl <task-id> close` let `said:said`
  build write-disjoint tasks concurrently (arms build, main decides).
  NOT for backlog additions — that's `/said:add-task`. NOT for spec
  authoring — that's `/said:architect`.
---

# Feature Impl — Phase 3 (Implement): Per-Task Driver

This skill drives a Phase 2-architected task from `Status: Todo` to `Status: Done` through three phases: Phase A classifies + inventories the work against the task's Acceptance checklist; Phase B implements rule-by-rule under test-first discipline; Phase C verifies via side-by-side walk + quality gates + `/said:review-ux` + close-of-task 5-step review. Phase 2 is the input boundary (this skill reads what `/said:architect` produced); commit + push are the output boundary (operator-triggered, never auto-driven).

The skill itself is the orchestrator — there is NO separate agent. You — the main agent — drive three sequential phases within ONE invocation. Each phase declares its stance up front so verification work and implementation don't blur. **Operator pauses at every phase boundary are mandatory in the interactive forms; no auto-progression.** (The `arm` fan-out form is the exception — it forces autonomy and returns every pause as an owed item; see **Fan-out forms**.)

**Single-pass goal.** Multiple "Pass 1 / Pass 2 / Pass 3" entries in a closed task's `### Fix` block = failure mode. The whole point of conformance-fold Acceptance (Phase 2 settlement) + 3-phase driver is to make every task close single-pass. If you find yourself thinking "I'll defer X to a Pass 2" mid-Phase B — STOP. Either widen Phase B to satisfy X now, or surface X as an operator decision (declare scope-creep, or split into a new task via `/said:add-task`).

**Surface duality.** A `web` surface runs the side-by-side playwright walk + `/said:review-ux` at Phase C; a non-visual surface (`cli`/`api`/`mcp`) drops visual parity and runs its declared Checkers' contract checks. `SAID.surface:` + `SAID.reviewers:` are read from the `## Lane` block (Step 0).

## When this fires

The user invokes:

- `/said:impl <task-id>` — single-task run; feature-id auto-derived (see Step 0).
- `/said:impl <task-id-1> <task-id-2> ...` — explicit batch; all task-ids must share one feature.
- `/said:impl <feature-id>` — whole-feature mode: drives every `Status: Todo` task in file order with operator pause between. Idempotent — re-running picks up at the next `Status: Todo` after closures.
- `/said:impl <task-id> arm` — **fan-out arm** (SKILL-level, issued only by `said:said`): Step 0 + Phase A + Phase B under forced autonomy — no operator pause, no log write, no commit — returning a close block (owed items included). See **Fan-out forms**.
- `/said:impl <task-id> close` — **fan-out close** (main): apply an arm's returned close block, then run Phase C. See **Fan-out forms**.

If a task ID doesn't resolve, batch task-ids don't share a feature, or a task is already `Status: Done` — BLOCK + redirect (`/said:add-task <feature-id>` for follow-ups, never amend closed tasks; `/said:architect` for new features).

If the operator's request is to plan or architect a NEW feature — this is the WRONG skill. Redirect to `/said:architect`. If to add a new task — redirect to `/said:add-task`.

## Step 0 — Preflight

Resolve inputs and ground in calibration sources before Phase A starts:

1. **Resolve mode + feature-id + tasks file** via SAID-canonical disambiguation:
   - **Normalize** each arg to UPPERCASE before matching (canonical grammar mandates uppercase in docs / tasks files; lets the operator type any case at the command line).
   - **Id shape** — from `SAID.id-shape:` on the `## Lane` block; no key → HALT (operator declares it), never assume the grammar. The regexes below match that declared shape.
   - Single arg matching `^[A-Z]+-\d+(-[A-Za-z0-9]+)*$` (e.g., `<FEAT>-NN`, or a suffixed per-lane feature-id such as `PROJ-01-BE` / `PROJ-02-BE-widgets`) AND a tasks file resolves (bare `<arg>.tasks.md` OR slug-suffixed `<arg>-*.tasks.md` via the resolver below) → **whole-feature mode**; build batch = every `Status: Todo` heading in file order. (The "AND a tasks file resolves" guard is load-bearing: a per-task id like `PROJ-01-FE-07` matches the shape but has no `PROJ-01-FE-07.tasks.md`, so it correctly falls through to the task regexes below.)
   - Args matching the canonical new-task regex `^([A-Z]+)(\d+)-.+$` → feature-id = `${1}-${2}` (dash collapsed inside the feature segment is re-inserted to produce the feature-id); **single-task or explicit batch mode**.
   - Legacy fallback (projects pre-migration): args matching `^([A-Z]+-\d+)-.+$` → feature-id is the leading captured segment. Post-migration projects won't trigger this path — their task IDs already match the canonical regex above.
   - **Trailing `arm` / `close` word** (fan-out forms, issued only by `said:said`): a single task-id followed by `arm` or `close` selects the fan-out form (see **Fan-out forms**) — `arm` builds under forced autonomy and returns a close block; `close` applies a returned block in main. A bare task-id (no trailing word) is the interactive single-task run above.
   - Resolve tasks file path from `SAID.task-log:` on the `## Lane` block; no key → HALT (operator declares it), never glob-guess. If the declared file is absent, scan its dir for a slug-suffixed `<feature-id>*.tasks.md` match (slug-suffixed convention, e.g., `TEST-01-tests.tasks.md` for feature `TEST-01`); if exactly one match, use it; if multiple matches, ASK the operator which to use. Symmetric with the companion-spec fallback in step 2.
   - Verify every task arg has a `## <task-id>:` heading in the resolved tasks file. All args in a batch must share one feature.
   - BLOCK + redirect on failure: missing tasks file (no glob match) → `/said:architect`; missing task heading → `/said:add-task`.
2. **Resolve companion spec path** from `SAID.feature-spec:` on the `## Lane` block; no key → HALT; sub-phased features use slug-suffixed names (e.g., `<feature-id>-phaseB.md`). If `<feature-id>.md` missing, scan `docs/features/<feature-id>*.md`; ask operator to confirm.
3. **Read task body in full.** Locate `## <task-id>:` in the tasks file and read the whole entry. Verify `Status:` is `Todo (YYYY-MM-DD)`; BLOCK on Done per "When this fires" redirect.
4. **Skim companion spec § Per-feature scope** for this task's piece. Don't full-read the spec — the task body's Reading list is canonical.
5. **Read `docs/features/template-tasks.md`** in full. Phase C's close-of-task 5-step review enforces it.
6. **Resolve surface + reviewers.** Read `SAID.surface:` (the medium; required — an omitted key HALTs, never a last-resort default) and `SAID.reviewers:` (the Checkers, a list read WHOLE) from the `## Lane` block. Read `SAID.code-review:` (scalar; `on` | `off`; absent → `on`).
7. **Skim project calibration.** Scan `docs/features/*.tasks.md` for the most recent closed task with a multi-pass `### Fix` block (failure mode this driver prevents) and the most recent single-pass close (target shape every task lands on). If the project has no closed tasks yet, skip — the rules below stand on their own.
8. **Resolve project quality-gate commands.** Skill never hardcodes language-specific commands. Resolution chain (first-match wins):
   - **Primary** — the `## Lane` `SAID.commands:` key (in `CLAUDE.md`): the umbrella target (`pre-commit`, `qa`, `check`, `all`).
   - **Secondary** — if `Makefile` present: prefer `make pre-commit`; fall back to `make qa` / `check` / `all`.
   - **Tertiary** — if `package.json` present (JS/TS only): scripts named `pre-commit` / `qa` / `check` / `validate`; invoke via `npm run` or `bun run` per lockfile.
   - **Quaternary** — operator-prompt: "What's this project's full quality-gate command + per-step typecheck + per-step test?" Cache for session; never persist to SKILL.md.
   - **Doc terminal — `SAID.surface: doc`.** The `SAID.commands:` value is a plugin-provided verb: `doc-gate` expands, run from the lane root as ONE Bash line, to `set -o pipefail; python3 <skill-dir>/../review-qa/doc-gate.py --repo-root . --tasks '<SAID.task-log glob for this feature>' --artifacts <SAID.code-mount> --banned <docs-root>/qa/banned-lexicon.txt <the lane's arguments after the verb> 2>&1 | tee <SAID.working>/doc-gate-<id>.log` — the engine is the `review-qa` skill's bundled script, reached by the sibling-skill path (skills are siblings under the plugin root). `<id>` = this task's id. Exit 2 is a **HALT**, never a verdict. For a `doc` lane `<typecheck>`, `<tests>` and `<lint>` ALL bind to this umbrella (it is fast and idempotent), so Phase B and Phase C run unchanged. The Secondary/Tertiary/Quaternary steps never apply to a `doc` lane.

   Cache placeholder bindings for Phase B / Phase C reference:
   - `<typecheck>` — fast verifier per-rule (e.g., `make typecheck`, `bunx tsc --noEmit`, `go vet ./...`).
   - `<tests>` — test command (e.g., `make test`, `bun run test:src`, `go test ./...`).
   - `<lint>` — lint command (e.g., `make lint`, `bunx biome lint`, `golangci-lint run`).
   - `<quality-gates-umbrella>` — full chain at Phase C close (e.g., `make pre-commit`).

9. **Resolve the lane's implementation rules — `## Earned rules`.** Run the bundled counter from the sibling skill: `python3 ${CLAUDE_SKILL_DIR}/../review-qa/earned-rules.py count <lane-root>/CLAUDE.md`, where `<lane-root>` is the directory holding the `CLAUDE.md` whose `## Lane` block Step 0 #1 read — the root every `SAID.<axis>:` path is relative to. The section is the lines from the anchored heading `^## Earned rules` (leading-words match; canonical form `## Earned rules (full context in linked ADR)`) to the next `^## ` heading or EOF; the rule count `N` is its `^- ` lines (indented sub-bullets do not count); a rule id is the first whole token matching `R-[A-Z]+-[A-Z0-9-]+` on a line — a line without one is applied but uncitable. Echo `N rules` and the ids. Never count or recall the rules yourself — the loaded section is the only source.
   - **No heading (the counter exits 3) → HALT, vocally:** *add a `## Earned rules` section to the lane's `CLAUDE.md` (one rule per `- ` line, an `R-*` id, a link to its ADR), then re-run.* Never proceed without it, never invent a rule. In the `arm` form the HALT is returned immediately as the close block — the arm builds nothing.
   - **Heading present, `N = 0` → proceed silently** (nothing earned yet is a valid state).
10. **Resolve the lane's `## Significant ADRs (skill-referenced)` table** — a shortname → this-lane's-ADR-file lookup, one row per shortname (the names a lane's rule lines or a task's `Refs:` cite). Absent table → the shortnames stay unbound; never a HALT.
11. **Re-anchor (standing, every unit).** Before each Phase B confirmation unit (Phase B step 4), re-read the `## Earned rules` section **from disk** — the section's text (the rule lines, for the briefing) and the counter (for `N` and the ids); the section, not the whole file — echo `N rules`, and write one briefing line per applicable rule: `<R-id or line text>: <rule> — applied how: <plan>` (one line per applicable rule, no elaboration). Name the ids applied, with the change site's `file:line`, in the unit's confirmation. The structural path and S-size tasks read the section once at Phase B entry; **every path** reads it once more at Phase C entry — the close-time read the `Rules applied:` line's `N` comes from.
12. **Standing reads — the procedure lives beside this file.** This spine carries the contract, Step 0, the phase stances, and the close; each phase's procedure is a reference file. **At Phase A start `Read ${CLAUDE_SKILL_DIR}/references/phase-a.md`; at Phase B start `Read ${CLAUDE_SKILL_DIR}/references/phase-b.md`; at Phase C start `Read ${CLAUDE_SKILL_DIR}/references/phase-c.md`; when Step 0 #1 selects the `arm` or `close` form, `Read ${CLAUDE_SKILL_DIR}/references/fan-out.md` before Phase A.** After a context compaction only this spine is re-attached (its first 5,000 tokens); these Reads are how the procedure comes back — never proceed into a phase from memory of it. If this spine itself is missing from context, `Read ${CLAUDE_SKILL_DIR}/SKILL.md` first.

Don't load source UX specs upfront — the task body's Reading list `(full read)` flag governs what to open at Phase A. Don't pull additional ADRs — Phase A's inventory surfaces task-specific needs.

## Phase A — Classify + Inventory

> **Stance: read the task. Classify it. Declare implementation discipline. Inventory current state against the Acceptance checklist with file:line evidence. Verification work, not coding. Report and STOP.**

Procedure: `Read ${CLAUDE_SKILL_DIR}/references/phase-a.md` (Step 0 #12) and follow it.

## Phase B — Implement

> **Stance: turn `[ ]` into `[x]` rule-by-rule. Test-first by default — the lane's red, and the `## Earned rules` briefing before every unit (Step 0 #11); declarative-test or no-test for declared structural carve-outs. One rule, one confirmation in chat. NO batching. NO "I'll defer X to a Pass 2" thinking. `<typecheck>` after every changed file.**

Procedure: `Read ${CLAUDE_SKILL_DIR}/references/phase-b.md` (Step 0 #12) and follow it — it carries Step 0.SC (the surface-contract load) and the **Anti-patterns**, which are standing for every phase, not only B (a mid-flight scope addition is classified, never silently folded, in any phase).

## Phase C — Verify and close

> **Stance: read the task body cold. Walk the migrated URL side-by-side with the reference URL. Run quality gates. Invoke `/said:review-ux` for a lane with an agent-form Checker. Run the close-of-task 5-step. Verify the close line, then flip Status. Hand off to operator for commit.**

Procedure: `Read ${CLAUDE_SKILL_DIR}/references/phase-c.md` (Step 0 #12) and follow it.

## Fan-out forms — `arm` and `close`

Two SKILL-level forms let `said:said` fan out a feature's write-disjoint tasks (arms build, main decides). Procedure: `Read ${CLAUDE_SKILL_DIR}/references/fan-out.md` when Step 0 #1 selects either form.

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
