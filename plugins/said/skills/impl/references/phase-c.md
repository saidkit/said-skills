# impl — Phase C procedure (Verify and close)

Read from the spine (`SKILL.md` Contract rule 1) at the moment it names; every rule here is standing for the whole phase.

## Phase C — Verify and close

> **Stance: read the task body cold. Run the parity check `per profile.parity`. Run the quality gate `per profile.gate`. Invoke `/said:review-ux` for a lane with an agent-form Checker. Run the code-review `per profile.code-review`. Run the close-of-task 5-step. Verify the close line, then flip Status. Hand off to operator for commit. A task listed in an open fast-track run defers review-ux, the code review and the hand-off to the run's close (**Fast-track run** below).**

Procedure (first read the tasks log for an open fast-track run listing this task: if one does, follow **Fast-track run** below: it defers steps 3, 4 and 7 and adds one line to step 5's `### Fix`):

1. **Parity check — `per profile.parity`.** Run exactly what that slot describes for this lane's `SAID.surface:`; the slot also says when there is nothing to run.
   - **If the slot describes no check** -> close the parity bullet as the slot says and move on. Never invent one.
   - **If it describes one and the diff is non-empty** -> name which Acceptance bullet is unsatisfied -> RETURN TO PHASE B for that bullet. Don't paper over with "minor cosmetic".
   - **If it describes one and the diff is empty** -> flip the parity `[ ]` to `[x]`.

2. **Quality gate -- `per profile.gate`:**
   - Run `<quality-gates-umbrella>` as Step 0 #8 bound it (the profile's resolution: `SAID.commands:`, else a Makefile or package.json target). If the profile bound no umbrella but bound the parts, chain `<typecheck> && <tests> && <lint>`; if it left them unbound there is no lane command: say so in the close report, never invent one.
   - Then run every `docs/evaluation/<unit>/harness.sh` the task body names (its Reading list or Acceptance), in the order the task names them, one at a time, each after `cd` into its own directory. Named harnesses run whether or not a lane command is bound.
   - A task naming none runs the lane command only and the close report says so.
   - Never `board/gate_recompute.sh` at task close: the full recompute runs once at `review-qa`.
   - Per-merge build commands (e.g., `make build`) and project-specific test scoping are project conventions invoked via the resolved targets, not skill-driven literals. If any gate fails -> STOP and report; fix; rerun. Don't close on red.

3. **Invoke `/said:review-ux`** when `SAID.reviewers:` names an agent-form Checker (the list read WHOLE at Step 0 #6; an empty list means none). Pass the task-id; that skill owns the arm table — it resolves the arm from `SAID.reviewers:`, spawns the Checker against its loaded contract, and returns a structured PASS / FAIL / SOFT-FLAG report.
   - Any FAIL -> RETURN TO PHASE B for the failing rule.
   - SOFT-FLAGs only -> operator decides whether to address now or defer. Operator question: under a blanket autonomy grant it does not relax -- hold / return, never auto-decide (`phase-b.md`).

4. **Invoke generic code-review — `per profile.code-review`.** The slot gives this family's default and the key that overrides it (Step 0 #6). **When it resolves to off**, log `code-review SKIPPED — <the slot's reason>` in the close report and in `### Fix`; the lane's declared Checkers (step 3) still run. When it resolves to on -> spawn as below. Default: spawn a read-only code-review subagent via the Agent tool (use a dedicated code-reviewer agent if your harness provides one, else a `general-purpose` agent prompted for review; a faster model tier suffices for review iterations, consistent with `said:review-ux-agent`'s model choice). Prompt: task-id + spec path + task body + `git diff` of Phase B's changes + `CLAUDE.md` pointer. Focus: bugs / logic errors / security / race conditions / convention violations; confidence threshold ≥80 (the agent already enforces this).
   - **Skip cases** (with reason logged in chat — never silent): structural carve-out declared at Phase A (no review-worthy delta); OR operator explicit-override for trivial-surface tasks (one-line bug fix, doc-only edit, etc.); OR deferred to the close of an open fast-track run, logged by its `### Fix` line (**Fast-track run**).
   - **Critical findings** -> RETURN TO PHASE B for the issue.
   - **Soft findings** (≥80 confidence but not Critical) -> operator decides: address now or defer. Operator question: under a blanket autonomy grant it does not relax -- hold / return, never auto-decide (`phase-b.md`).
   - Single-reviewer is the SAID default; operator can spawn 2-3 parallel code-review subagents along distinct lenses (simplicity/DRY + bugs/correctness + conventions) if the surface warrants the heavier coverage.

5. **Run close-of-task 5-step review per `docs/features/template-tasks.md`** — leak scan / gotcha harvest / deviation check / fill `### Fix` / bloat scan. Two nuances:
   - **Leak-scan ADR/UX proposals** (forward-looking rules surfaced during implementation) promote directly to the destination ADR / `docs/ux/*.md` and cite the edited path in `Refs:`. If a rule needs more refinement before promotion, it stays in operator workspace as private process — never cited from task body.
   - **`### Fix`** is one verification line (`Tests N -> M; typecheck + lint clean.`) + the close line `Rules applied: <R-ids | none> (block: N)` (`none` is legitimate; `N` = the lane's `## Earned rules` count from the Phase C entry re-read, Contract rule 3). **Grammar:** the line starts at column 1 (a bullet or backtick is tolerated), ids are the bare `R-*` tokens, comma-separated, or the word `none`; `(block: N)` closes it; no prose after it. + optional one-liners for spec edits (plus, for a task in an open fast-track run, the deferral line, **Fast-track run**). NO file enumerations (git is canonical); NO test-output dumps; NO `**Files modified:**` blocks.

6. **Verify the close line, then flip Status.** Before the flip, run the same checker `review-qa` uses on the task being closed — `python3 ${CLAUDE_SKILL_DIR}/../review-qa/earned-rules.py check --claude-md <lane-root>/CLAUDE.md --task-file <tasks log> --task-id <task-id> --adr-date 2026-09-08` — and read its first word. **FAIL is a close blocker:** fix the `Rules applied:` line or the cited ids, re-run, and only then flip. WARN is recorded in `### Fix` and does not block. The verdict line goes into `### Fix` after the close line. A skill verifies its own mutation at the moment it makes it; `review-qa`'s own re-check is the second look, never the only gate. **Blocked-on question gate:** if the closing task carries a `**Blocked-on question:** <id>` marker, also run `python3 ${CLAUDE_SKILL_DIR}/../review-qa/hold-gate.py check --tasks <tasks log> --rulings <working dir>/rulings.md` (the feature's dir under the lane's `SAID.working:` key) and read its exit code (0 PASS, 1 HOLD, 2 config error) -- 1 or 2 is a close blocker (the lift line is the one in `phase-a.md` step 9; a task with no marker skips this). Then flip Status to `Done (YYYY-MM-DD)`. The ONLY mutations allowed at close:
   - `Status:` line.
   - `### Fix` body (from HTML-comment placeholder to filled).
   - `### Deviations` body (optional, only if departed from Approach).
   - `### Gotchas` body (optional, only if non-obvious learnings).
   - `Refs:` line (only if task created or edited an ADR / UX-spec / feature-spec — write-set discipline).
   - Acceptance bullets — flip `[ ]` to `[x]` (or `[N/A — reason]`).
   - Summary table row — Status column update.

   **NEVER invent new `###` headers when closing.** The template-tasks.md section list is exhaustive: Problem / Approach / Reading list / Acceptance / Fix / Deviations / Gotchas / Out of scope (+ optional `### Root cause` under Problem for bugs). Forbidden: `### Frozen rules to satisfy`, `### Wire contract probes`, `### Visual parity reference`, `### Cross-feature contracts`, `### Spec changes`, `### Files modified`, `### Implementation notes`, `### Lessons learned`, `### Discovery`, `### Pass N`. This skill is the last line of defense against ad-hoc section invention.

7. **Hand off to operator for commit.** Brief status: "Task `<task-id>` closed at `Status: Done (YYYY-MM-DD)`. Quality gate `per profile.gate` <green / unbound> (<lane command + the harnesses run | lane command only>). Parity `per profile.parity` <PASS / N/A>. `/said:review-ux` <PASS / SOFT-FLAGs deferred / N/A>. Code-review `per profile.code-review` <PASS / Soft-deferred / SKIPPED — reason>. Commit when ready; commit-msg per the lane's `SAID.id-shape:` convention. Next task in batch: <next-task-id or 'none — batch complete'>."

For batch runs (multiple task IDs): pause for operator `proceed` before re-entering Phase A on the next task. NO auto-progression across tasks.

## Fast-track run

A fast-track run is a `## Fast-track F<NN>` block in the tasks log whose `closed:` line is empty (opened by `/said:add-task <feature-id> fast-track "<task ids>"`, on the operator's words). Its listed set is the ids on its `tasks:` line plus every task carrying `**Fast-track:** F<NN>`. Read it at Phase C entry; never infer membership from a brief, a count or the task's own text.

- **A task in an open run's listed set:** steps 1, 2, 5 and 6 run as for any task (parity, the quality gate, the close-of-task 5-step, the close-line verification). Defer step 3 (review-ux), step 4 (code review) and step 7 (hand-off) to the run's close: the run's close runs them once over the listed set (the code review in groups the operator cuts), so this task never runs them itself. The close is driven by `/said:said`'s run close, or by the operator invoking the gates' `fast-track F<NN>` forms; never by `impl`. Add to `### Fix`, beside the other `### Fix` lines, never instead of them, the one line `fast-track F<NN>: review-ux, code review, review-qa, accept deferred to its close`, written from the block, never retyped (the run id copied from the block heading). Then flip Status to `Done (YYYY-MM-DD)`: no new status token.
- **Between tasks** the pause before the next task and the no-auto-progression rule still apply: in place of the step 7 brief, report one line, `<task-id> closed (Done); review-ux, code review, review-qa, accept deferred to fast-track F<NN>`, and wait for the operator's `proceed` as after any close (a routine pause: an autonomy grant relaxes it as it does for any task).
- **A task outside every open run takes the full chain**, steps 1-7, whatever other tasks of the feature do.
- **The lane's own earned rules at task close keep running** per task (a review or report a lane rule requires before a close); the run defers only the three Phase C steps named above (review-qa and accept are gates the run's close runs, not Phase C steps).
- A run is opened and closed only on the operator's words; this skill never opens, closes or extends one. A task found mid-flight under an open run is added through `/said:add-task`, which gives it the run's field.
