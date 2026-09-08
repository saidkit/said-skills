# impl — Phase C procedure (Verify and close)

Read from the spine (`SKILL.md` Step 0 #12) at the moment it names; every rule here is standing for the whole phase.

## Phase C — Verify and close

> **Stance: read the task body cold. Walk the migrated URL side-by-side with the reference URL. Run quality gates. Invoke `/said:review-ux` for a lane with an agent-form Checker. Run the close-of-task 5-step. Verify the close line, then flip Status. Hand off to operator for commit.**

Procedure:

1. **Side-by-side playwright walk** (visual surface only):
   - Migrated URL (e.g., `/<entity>`) vs reference URL (from task's Acceptance bullet, e.g., `/tasks`).
   - Enumerate every visible difference: toolbar / header / sheet / pagination / empty-state / chip styles / spacing.
   - **If diff non-empty** → which Acceptance bullet is unsatisfied → RETURN TO PHASE B for that bullet. Don't paper over with "minor cosmetic" — every visible diff is the visual-parity bullet's scope.
   - **If diff empty** → flip the visual-parity `[ ]` to `[x]`.

2. **Quality gates:** run `<quality-gates-umbrella>` (resolved in Step 0 #8 — typically `make pre-commit` or equivalent). If the project lacks an umbrella target, chain `<typecheck> && <tests> && <lint>` plus any project-defined dead-code check. Per-merge build commands (e.g., `make build`) and project-specific test scoping (e.g., a parity suite under one module for one project) are project conventions invoked via the resolved targets — not skill-driven literals. If any gate fails → STOP and report; fix; rerun. Don't close on red.

3. **Invoke `/said:review-ux`** when the lane declares an agent-form Checker for its medium in `SAID.reviewers:` — `web-ux` (a `web` surface with UI changes) runs the web arm, `doc-editorial` (a `doc` surface) runs the doc arm. Pass the task-id; the skill resolves the arm from `SAID.reviewers:`, spawns the surface's reviewer against its loaded contract (the UX checklist filtered by screen shape, or the QA checklist's editorial rows), and returns a structured PASS / FAIL / SOFT-FLAG report.
   - Any FAIL → RETURN TO PHASE B for the failing rule.
   - SOFT-FLAGs only → operator decides whether to address now or defer.

4. **Invoke generic code-review — CRITICAL for code quality.** **Skip when the lane declares `SAID.code-review: off`** (Step 0 #6): log `code-review SKIPPED — lane declares SAID.code-review: off` in the close report and in `### Fix`; the lane's declared Checkers (step 3) still run. `on` or absent → spawn as below. Default: spawn a read-only code-review subagent via the Agent tool (use a dedicated code-reviewer agent if your harness provides one, else a `general-purpose` agent prompted for review; a faster model tier suffices for review iterations, consistent with `said:review-ux-agent`'s model choice). Prompt: task-id + spec path + task body + `git diff` of Phase B's changes + `CLAUDE.md` pointer. Focus: bugs / logic errors / security / race conditions / convention violations; confidence threshold ≥80 (the agent already enforces this).
   - **Skip cases** (with reason logged in chat — never silent): structural carve-out declared at Phase A (no review-worthy delta); OR operator explicit-override for trivial-surface tasks (one-line bug fix, doc-only edit, etc.).
   - **Critical findings** → RETURN TO PHASE B for the issue.
   - **Soft findings** (≥80 confidence but not Critical) → operator decides: address now or defer.
   - Single-reviewer is the SAID default; operator can spawn 2-3 parallel code-review subagents along distinct lenses (simplicity/DRY + bugs/correctness + conventions) if the surface warrants the heavier coverage.

5. **Run close-of-task 5-step review per `docs/features/template-tasks.md`** — leak scan / gotcha harvest / deviation check / fill `### Fix` / bloat scan. Two nuances:
   - **Leak-scan ADR/UX proposals** (forward-looking rules surfaced during implementation) promote directly to the destination ADR / `docs/ux/*.md` and cite the edited path in `Refs:`. If a rule needs more refinement before promotion, it stays in operator workspace as private process — never cited from task body.
   - **`### Fix`** is one verification line (`Tests N → M; typecheck + lint clean.`) + the close line `Rules applied: <R-ids | none> (block: N)` (`none` is legitimate; `N` = the lane's `## Earned rules` count from the Phase C entry re-read, Step 0 #11). **Grammar:** the line starts at column 1 (a bullet or backtick is tolerated), ids are the bare `R-*` tokens, comma-separated, or the word `none`; `(block: N)` closes it; no prose after it. + optional one-liners for spec edits. NO file enumerations (git is canonical); NO test-output dumps; NO `**Files modified:**` blocks.

6. **Verify the close line, then flip Status.** Before the flip, run the same checker `review-qa` uses on the task being closed — `python3 ${CLAUDE_SKILL_DIR}/../review-qa/earned-rules.py check --claude-md <lane-root>/CLAUDE.md --task-file <tasks log> --task-id <task-id> --adr-date 2026-09-08` — and read its first word. **FAIL is a close blocker:** fix the `Rules applied:` line or the cited ids, re-run, and only then flip. WARN is recorded in `### Fix` and does not block. The verdict line goes into `### Fix` after the close line. A skill verifies its own mutation at the moment it makes it; `review-qa`'s R-QA-08 is the second look, never the only gate. Then flip Status to `Done (YYYY-MM-DD)`. The ONLY mutations allowed at close:
   - `Status:` line.
   - `### Fix` body (from HTML-comment placeholder to filled).
   - `### Deviations` body (optional, only if departed from Approach).
   - `### Gotchas` body (optional, only if non-obvious learnings).
   - `Refs:` line (only if task created or edited an ADR / UX-spec / feature-spec — write-set discipline).
   - Acceptance bullets — flip `[ ]` to `[x]` (or `[N/A — reason]`).
   - Summary table row — Status column update.

   **NEVER invent new `###` headers when closing.** The template-tasks.md section list is exhaustive: Problem / Approach / Reading list / Acceptance / Fix / Deviations / Gotchas / Out of scope (+ optional `### Root cause` under Problem for bugs). Forbidden: `### Frozen rules to satisfy`, `### Wire contract probes`, `### Visual parity reference`, `### Cross-feature contracts`, `### Spec changes`, `### Files modified`, `### Implementation notes`, `### Lessons learned`, `### Discovery`, `### Pass N`. This skill is the last line of defense against ad-hoc section invention.

7. **Hand off to operator for commit.** Brief status: "Task `<task-id>` closed at `Status: Done (YYYY-MM-DD)`. Quality gates green. `/said:review-ux` <PASS / SOFT-FLAGs deferred / N/A non-UI>. Code-review <PASS / Soft-deferred / SKIPPED — reason>. Commit when ready; commit-msg per the lane's `SAID.id-shape:` convention. Next task in batch: <next-task-id or 'none — batch complete'>."

For batch runs (multiple task IDs): pause for operator `proceed` before re-entering Phase A on the next task. NO auto-progression across tasks.
