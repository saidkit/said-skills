# impl — Phase C procedure (Verify and close)

Read from the spine (`SKILL.md` Contract rule 1) at the moment it names; every rule here is standing for the whole phase.

## Phase C — Verify and close

> **Stance: read the task body cold. Run the parity check `per profile.parity`. Run the quality gate `per profile.gate`. Invoke `/said:review-ux` for a lane with an agent-form Checker. Run the code-review `per profile.code-review`. Run the close-of-task 5-step. Verify the close line, then flip Status. Hand off to operator for commit.**

Procedure:

1. **Parity check — `per profile.parity`.** Run exactly what that slot describes for this lane's `SAID.surface:`; the slot also says when there is nothing to run.
   - **If the slot describes no check** → close the parity bullet as the slot says and move on. Never invent one.
   - **If it describes one and the diff is non-empty** → name which Acceptance bullet is unsatisfied → RETURN TO PHASE B for that bullet. Don't paper over with "minor cosmetic".
   - **If it describes one and the diff is empty** → flip the parity `[ ]` to `[x]`.

2. **Quality gate — `per profile.gate`:** run `<quality-gates-umbrella>` as Step 0 #8 bound it. If the profile bound no umbrella but bound the parts, chain `<typecheck> && <tests> && <lint>`; if the profile leaves them unbound there is no gate to run — say so in the close report and never invent one. Per-merge build commands (e.g., `make build`) and project-specific test scoping (e.g., a parity suite under one module for one project) are project conventions invoked via the resolved targets — not skill-driven literals. If any gate fails → STOP and report; fix; rerun. Don't close on red.

3. **Invoke `/said:review-ux`** when `SAID.reviewers:` names an agent-form Checker (the list read WHOLE at Step 0 #6; an empty list means none). Pass the task-id; that skill owns the arm table — it resolves the arm from `SAID.reviewers:`, spawns the Checker against its loaded contract, and returns a structured PASS / FAIL / SOFT-FLAG report.
   - Any FAIL → RETURN TO PHASE B for the failing rule.
   - SOFT-FLAGs only → operator decides whether to address now or defer.

4. **Invoke generic code-review — `per profile.code-review`.** The slot gives this family's default and the key that overrides it (Step 0 #6). **When it resolves to off**, log `code-review SKIPPED — <the slot's reason>` in the close report and in `### Fix`; the lane's declared Checkers (step 3) still run. When it resolves to on → spawn as below. Default: spawn a read-only code-review subagent via the Agent tool (use a dedicated code-reviewer agent if your harness provides one, else a `general-purpose` agent prompted for review; a faster model tier suffices for review iterations, consistent with `said:review-ux-agent`'s model choice). Prompt: task-id + spec path + task body + `git diff` of Phase B's changes + `CLAUDE.md` pointer. Focus: bugs / logic errors / security / race conditions / convention violations; confidence threshold ≥80 (the agent already enforces this).
   - **Skip cases** (with reason logged in chat — never silent): structural carve-out declared at Phase A (no review-worthy delta); OR operator explicit-override for trivial-surface tasks (one-line bug fix, doc-only edit, etc.).
   - **Critical findings** → RETURN TO PHASE B for the issue.
   - **Soft findings** (≥80 confidence but not Critical) → operator decides: address now or defer.
   - Single-reviewer is the SAID default; operator can spawn 2-3 parallel code-review subagents along distinct lenses (simplicity/DRY + bugs/correctness + conventions) if the surface warrants the heavier coverage.

5. **Run close-of-task 5-step review per `docs/features/template-tasks.md`** — leak scan / gotcha harvest / deviation check / fill `### Fix` / bloat scan. Two nuances:
   - **Leak-scan ADR/UX proposals** (forward-looking rules surfaced during implementation) promote directly to the destination ADR / `docs/ux/*.md` and cite the edited path in `Refs:`. If a rule needs more refinement before promotion, it stays in operator workspace as private process — never cited from task body.
   - **`### Fix`** is one verification line (`Tests N → M; typecheck + lint clean.`) + the close line `Rules applied: <R-ids | none> (block: N)` (`none` is legitimate; `N` = the lane's `## Earned rules` count from the Phase C entry re-read, Contract rule 3). **Grammar:** the line starts at column 1 (a bullet or backtick is tolerated), ids are the bare `R-*` tokens, comma-separated, or the word `none`; `(block: N)` closes it; no prose after it. + optional one-liners for spec edits. NO file enumerations (git is canonical); NO test-output dumps; NO `**Files modified:**` blocks.

6. **Verify the close line, then flip Status.** Before the flip, run the same checker `review-qa` uses on the task being closed — `python3 ${CLAUDE_SKILL_DIR}/../review-qa/earned-rules.py check --claude-md <lane-root>/CLAUDE.md --task-file <tasks log> --task-id <task-id> --adr-date 2026-09-08` — and read its first word. **FAIL is a close blocker:** fix the `Rules applied:` line or the cited ids, re-run, and only then flip. WARN is recorded in `### Fix` and does not block. The verdict line goes into `### Fix` after the close line. A skill verifies its own mutation at the moment it makes it; `review-qa`'s R-QA-08 is the second look, never the only gate. Then flip Status to `Done (YYYY-MM-DD)`. The ONLY mutations allowed at close:
   - `Status:` line.
   - `### Fix` body (from HTML-comment placeholder to filled).
   - `### Deviations` body (optional, only if departed from Approach).
   - `### Gotchas` body (optional, only if non-obvious learnings).
   - `Refs:` line (only if task created or edited an ADR / UX-spec / feature-spec — write-set discipline).
   - Acceptance bullets — flip `[ ]` to `[x]` (or `[N/A — reason]`).
   - Summary table row — Status column update.

   **NEVER invent new `###` headers when closing.** The template-tasks.md section list is exhaustive: Problem / Approach / Reading list / Acceptance / Fix / Deviations / Gotchas / Out of scope (+ optional `### Root cause` under Problem for bugs). Forbidden: `### Frozen rules to satisfy`, `### Wire contract probes`, `### Visual parity reference`, `### Cross-feature contracts`, `### Spec changes`, `### Files modified`, `### Implementation notes`, `### Lessons learned`, `### Discovery`, `### Pass N`. This skill is the last line of defense against ad-hoc section invention.

7. **Hand off to operator for commit.** Brief status: "Task `<task-id>` closed at `Status: Done (YYYY-MM-DD)`. Quality gate `per profile.gate` <green / unbound>. Parity `per profile.parity` <PASS / N/A>. `/said:review-ux` <PASS / SOFT-FLAGs deferred / N/A>. Code-review `per profile.code-review` <PASS / Soft-deferred / SKIPPED — reason>. Commit when ready; commit-msg per the lane's `SAID.id-shape:` convention. Next task in batch: <next-task-id or 'none — batch complete'>."

For batch runs (multiple task IDs): pause for operator `proceed` before re-entering Phase A on the next task. NO auto-progression across tasks.
