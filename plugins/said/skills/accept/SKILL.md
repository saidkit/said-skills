---
name: accept
description: >
  SAID Phase 3.5 — Acceptance Criteria verification gate that runs between
  Phase 3 (`/said:impl` close) and Phase 4 (`/said:debrief` entry).
  Verifies the behavioral contract a feature/task committed to: did the
  `### Acceptance` items / spec § Acceptance Criteria actually pass? Read-only
  by contract; never edits code, specs, or tasks. Sibling skill
  `/said:review-qa` covers implementation hygiene (quality gates, `### Fix`
  integrity, Refs conformance) — this skill covers behavioral contract only.
  Triggered ONLY by the explicit command "/said:accept
  <task-id|feature-id> [--feature-only]". NOT for spec authoring (that's
  `/said:architect`, Phase 2). NOT for implementation (that's
  `/said:impl`, Phase 3). NOT for hygiene (that's `/said:review-qa`,
  sibling).
---

# Feature Accept — Behavioral Contract Verification Gate

This skill verifies that AC promises a feature/task made — bullet conditions OR Gherkin scenarios — actually pass post-implementation. Sits between Phase 3 close and Phase 4 entry as a parallel sibling to `/said:review-qa` (hygiene side).

**Read-only contract.** Never edits code, specs, or tasks. Surfaces verdicts; operator decides remediation path (re-open via `/said:impl`, or follow-up via `/said:add-task`).

**Single-pass goal.** Multiple `/said:accept` runs on the same task with shifting outcomes = drift. Phase A → operator-review → Phase B is the discipline that lands one PASS or one operator-decided fix-and-re-run.

## When this fires

The operator invokes:

- `/said:accept <task-id>` — **task-mode**: verifies just that task's `### Acceptance` items + that task's row in spec § Feature Tasks table-status alignment.
- `/said:accept <feature-id>` — **feature-mode (default)**: verifies spec § Acceptance Criteria + every Done task's `### Acceptance` + spec § Feature Tasks table-status sweep.
- `/said:accept <feature-id> --feature-only` — feature-mode without task sweep: spec § Acceptance Criteria only.

BLOCK + redirect if:

- Targeted task is `Status: Todo` / `Status: In progress` → redirect to `/said:impl`.
- Operator intent is hygiene verification (quality gates / `### Fix` integrity / `Refs:` conformance) → wrong skill, redirect to `/said:review-qa`.
- Operator intent is to author a new spec → redirect to `/said:architect`.

## Common compositions

After Phase 3 closes (all targeted tasks `Status: Done`):

```
/said:impl <task-id|feature-id>     # task / batch closes
/said:accept <task-id|feature-id>   # behavioral contract verified   ┐
/said:review-qa <task-id|feature-id># implementation hygiene cleared ┘ siblings, parallel
                                       # ↓ both green
/said:debrief <feature-id>          # Phase 4 entry allowed (preflight reads accept report)
```

## Step 0 — Preflight

1. **Resolve mode + inputs:**
   - Single arg matching project's task-id regex (`<FEAT><NN>-<APP>-<NN>` or `<FEAT><NN>-<NN>`) → task-mode. Derive feature-id from prefix; locate `## <task-id>:` anchor in `<feature>.tasks.md`.
   - Single arg matching `^[A-Z]+-\d+(-[A-Za-z0-9]+)*$` **and resolving to an existing `docs/features/<feature-id>.tasks.md`** (bare or slug-suffixed) → feature-mode (e.g., `<FEAT>-NN`, or a suffixed per-lane feature-id like `PROJ-01-BE`; task-mode above is matched first, so canonical task-ids are unaffected). Also resolve `docs/features/<feature-id>.md`. If the shape matches but no such feature log exists — e.g. a legacy task-id like `PROJ-01-FE-07` — it is not a feature: BLOCK + redirect to `/said:impl`, mirroring `impl` Step 0's tasks-file guard.
   - `--feature-only` flag → feature-mode without task sweep.
2. **Status check:**
   - Task-mode: the named task must be `Status: Done (YYYY-MM-DD)`. Otherwise BLOCK + redirect to `/said:impl`.
   - Feature-mode (default): every task with `Status: Todo` / `Status: In progress` listed; if any → BLOCK with the list; operator confirms in-scope vs out-of-scope or closes them first. (Backlog and N/A statuses pass — they're intentional non-gating per SAID convention.)
3. **Read spec + tasks file.** Spec read in full only in feature-mode (need § Acceptance Criteria + § Feature Tasks summary table). Tasks file read by-section (`## <task-id>:` anchors → `### Acceptance` blocks).
4. **Index probe artifacts.** Glob `docs/working/<feature-id>/` for recorded probes: `*-wire-*.json`, `*.png` screenshots, Playwright snapshot files. Build a `<task-id> → [artifact paths]` map for Phase A classification.

## Phase A — Parse + Classify (STOP for operator review)

> **Stance: read every AC item; classify each as mechanical / Playwright / manual. No execution yet. Emit plan + STOP.**

Procedure:

1. **Extract AC items.** For each in-scope task / feature-spec § Acceptance Criteria:
   - Detect form: bullet list (`- [ ]` / `- [x]` / `- [N/A — ...]`) OR Gherkin (lines containing `Given` / `When` / `Then` keywords; regex-permissive — no strict parser, no `Scenario:` header required) OR mixed.
   - Each bullet (or each Given/When/Then group in Gherkin) is one AC item.

2. **Classify each item:**
   - **Mechanical** — code/data assertion: file presence (`exists path/x`, `deleted`), grep result (`returns 0 results`, `N matches`), endpoint contract (`responds with shape Y`), schema validation, test count delta (`Tests 575 → 578`), ADR rule conformance (when the rule has a mechanical assertion).
   - **Playwright** — UI flow with a recorded probe artifact under `docs/working/<feature-id>/`. Evidence read, NOT re-executed (default; see Anti-patterns).
   - **Manual** — operator must eyeball; no mechanical assertion + no recorded probe. Subjective side-by-side walks ("zero visible diffs"), "operator confirms theme matches mock", production-build visual checks.

3. **Special cases:**
   - `[N/A — <reason>]` → classify as mechanical, auto-PASS with reason recorded verbatim. No re-litigation (task closure already approved the N/A).
   - `[x]` items → DO NOT auto-trust the check; still classify + verify the assertion. The `[x]` is a task-claim, not the verdict.

4. **Spec § Feature Tasks table-status alignment** (feature-mode + task-mode for that task's row): mechanical item per row — row's Status column equals task entry's `Status:` line.

5. **Emit plan** to `docs/working/<feature-id>/accept-<task-id-or-feature-id>.md`:

   ```
   ## Phase A plan — <id> (YYYY-MM-DD)

   | source | classification | item | evidence-source |
   |---|---|---|---|
   | <feat-id>.tasks.md:<line> (<task-id>) | mechanical | "<AC text — e.g., specific frozen-rule satisfied>" | grep <ux-spec path> |
   | <feat-id>.tasks.md:<line> (<task-id>) | playwright | "<AC text — e.g., probe confirms <observed shape>>" | docs/working/<feat-id>/<task-id>-wire-*.json |
   | <feat-id>.tasks.md:<line> (<task-id>) | manual | "<AC text — e.g., walked side-by-side with <reference> — zero visible differences>" | operator review |
   ```

6. **STOP for operator review.** Brief status: "Phase A complete. N items classified (M mechanical + P playwright + X manual). Plan at `docs/working/<feature-id>/accept-<id>.md`. Reply OK to execute (Phase B), or flag items to revise."

## Phase B — Execute

> **Stance: execute mechanicals; read recorded probes; surface manuals. One verdict per item. AC text IS the contract — don't interpret operator intent.**

For each approved item, in classification order (mechanical → playwright → manual):

1. **Mechanical.** Infer the assertion from AC text and execute via Bash / Read / grep. Examples:
   - "tsc + lint clean" → run `<typecheck>` + `<lint>` (resolved per project, same chain as `/said:impl` Step 0 #8).
   - "Tests 575 → 578" → run `<tests>`; parse count; verify ≥ 578.
   - "grep -rn IS_MOCK src/ returns 0" → re-run grep; verify count matches.
   - "File `<path>` deleted" → check `! [ -e <path> ]`.
   - "Spec §14 names `<path>`" → check file presence + structural match against spec.
   - ADR-rule conformance (when assertion is well-defined) → run the assertion.

2. **Playwright (recorded-evidence mode).** Read the probe artifact:
   - JSON wire probe → parse + compare assertion against captured bytes.
   - Screenshot / Playwright snapshot → PASS if AC bullet says "captured" / "probe confirms X" and the artifact exists. The probe IS the evidence.
   - **NEVER re-execute the probe** (settled default; risks flakiness, BE drift, dev-server unavailability). Operator override via `--re-execute=<task-id>` is deferred to v1.1; not implemented.

3. **Manual.** Emit checklist line with AC text verbatim + linked artifact path (if any). Verdict = `MANUAL-PENDING` pending operator inline mark (`PASS` / `FAIL` written by operator before final report).

4. **Evidence format** (one-line summary + embedded command for re-run):

   ```
   | source | verdict | evidence |
   |---|---|---|
   | <feat-id>.tasks.md:<line> | PASS | `grep -nE "#N\|#N\|#N" <ux-spec path>` → N matches |
   | <feat-id>.tasks.md:<line> | MANUAL-PENDING | operator: walk <route-under-test> vs <reference-route> |
   | <feat-id>.tasks.md:<line> | PASS | recorded probe: `docs/working/<feat-id>/<task-id>-wire-<topic>.json` (`<observed shape>` present) |
   ```

5. **Verbose evidence redirect.** If a mechanical execution produces > ~20 lines of stdout/stderr (full test runner output, large diff, deep grep dump), redirect the full output to `docs/working/<feature-id>/accept-<id>.full.md` under an anchor matching the AC item. Main report carries: `evidence: <one-line summary>; full output: accept-<id>.full.md § <anchor>`.

## Phase C — Report

Finalize `docs/working/<feature-id>/accept-<id>.md`:

```
## Accept verdict — <id> (YYYY-MM-DD)

- Items: <total> (<M> mechanical + <P> playwright + <X> manual)
- Mechanical: <pass>/<total-mechanical> PASS
- Playwright: <pass>/<total-playwright> PASS
- Manual: <pending> pending, <pass-confirmed>/<total-manual> PASS, <fail> FAIL
- Verdict: PASS | FAIL | MANUAL-PENDING
```

Aggregate verdict rules:

- **PASS** — every item PASS (including operator-confirmed manuals).
- **FAIL** — ≥1 item FAIL.
- **MANUAL-PENDING** — no FAIL but ≥1 manual unresolved.

Gate effect for `/said:debrief`:

- `/said:debrief` Step 0 preflight reads the most recent `accept-<feature-id>.md` (or per-task reports for tasks closed since the last feature-mode run).
- If verdict is FAIL → halt `/said:debrief` with redirect: "Resolve `/said:accept` failures first."
- If verdict is MANUAL-PENDING → surface to operator at debrief preflight; operator confirms inline before debrief proceeds.

## Anti-patterns

- **Don't run on `Status: Todo` / `Status: In progress` tasks.** BLOCK; redirect to `/said:impl`.
- **Don't auto-promote MANUAL-PENDING → PASS.** Operator marks inline. Auto-promotion defeats the gate.
- **Don't edit code, specs, or tasks.** Read-only by contract. Even when finding obvious typos. Fixes route through `/said:impl` (re-open task pre-commit) or `/said:add-task` (post-commit follow-up).
- **Don't re-execute recorded probes.** Recorded probes are evidence-at-task-close (settled default). Re-execution risks flakiness, BE migration drift, dev-server unavailability — failures here would be unrelated to AC drift. `--re-execute=<task-id>` override deferred to v1.1.
- **Don't synthesize Playwright scripts from AC text.** If an AC item could theoretically be automated (e.g., "kebab shows Disable / Enable / Remove") but no recorded probe exists, classify as manual. Auto-generating Playwright code from prose is error-prone and out of scope.
- **Don't re-litigate `[N/A — <reason>]` items.** Auto-PASS with reason recorded. Operator can spot abuse in the report and revisit individual N/As; the gate is not the place.
- **Don't extract task-IDs from prose.** Require explicit input. No `/said:accept "the recent stuff"` ambiguity.
- **Don't run hygiene checks.** `/said:review-qa` is the sibling for quality gates + Fix integrity + Refs conformance. This skill verifies behavioral contract only — strict scope separation.
- **Don't interpret AC text creatively.** If a bullet's assertion is ambiguous, mark it manual and let the operator resolve. Don't synthesize "what the spec really meant."
- **Don't run if both spec and tasks file are missing.** BLOCK with: "No spec or tasks file for `<id>`. Has the feature been architected?" — redirect to `/said:architect`.

## Anchors

- `docs/features/template.md` — spec target shape (§ Acceptance Criteria section).
- `docs/features/template-tasks.md` — task entry shape (`### Acceptance` section).
- `said:impl` — Phase 3 driver this skill follows (post-task-close).
- `said:debrief` — Phase 4 driver this skill gates (Phase 4 reads accept report).
- `said:review-qa` (when built) — hygiene sibling; runs in parallel.

## Re-read self-check (acceptance)

Before exiting Phase C:

- [ ] All 3 phases distinct in transcript (Preflight + Phase A + Phase B + Phase C).
- [ ] Phase A produced `accept-<id>.md` plan + STOPPED for operator review.
- [ ] Phase B is per-item: each finding has its own verdict line with evidence.
- [ ] No edits to source files, specs, or tasks — read-only confirmed.
- [ ] Verdict assigned per aggregate rules (PASS / FAIL / MANUAL-PENDING).
- [ ] If verbose evidence: redirected to `accept-<id>.full.md`; main report stays scannable.
- [ ] `[N/A — <reason>]` items auto-PASSed with reason verbatim in evidence column.
- [ ] Recorded probes read (not re-executed).
- [ ] Operator-pending manuals listed at top of report for visibility.
