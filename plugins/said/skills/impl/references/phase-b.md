# impl — Phase B procedure (Implement) + Step 0.SC + the anti-patterns

Read from the spine (`SKILL.md` Contract rule 1) at the moment it names; every rule here is standing for the whole phase.

## Phase B — Implement

> **Stance: turn `[ ]` into `[x]` rule-by-rule. Test-first by default — the red is `per profile.red`, and the `## Earned rules` briefing comes before every unit (Contract rule 3); declarative-test or no-test for a carve-out `per profile.carve-out`, declared. One rule, one confirmation in chat. NO batching. NO "I'll defer X to a Pass 2" thinking. `<typecheck>` after every changed file.**

## Step 0.SC — Load the surface contract (SC-STUB v3)

Run this ONLY when about to reason over a surface-shape rule — the shape vocabulary is the loaded registry's own `applies-to` values, never a list recalled without it. A structural, data-layer, or non-surface task skips it entirely. Then, only if this lane ships a rule registry:

1. Registry path = key-grep `SAID.docs-root:` (scalar) on the `## Lane` block + `/ux/feature-ux-rules.md`. No `SAID.docs-root:` key -> HALT.
2. Registry absent -> bearing-gated: a **surface-bearing** lane (`SAID.surface: <medium>`) FAILs with a named redirect (ship the surface contract) — it cannot proceed with a hollow gate; a `SAID.surface: none` lane SKIPs (proceed without one, never HALT, never invent a rule).
3. Present -> LOAD it WHOLE; echo its `SC-HEADER` `token, N rules`. Missing/malformed sentinel -> HALT. Never grep a single row.
4. Reason over the LOADED registry only; cite rule ids. Never restate or re-derive a mapping from memory.

Procedure:

1. **For a surface-governed task, order rules by blast radius per the loaded registry** (Step 0.SC) — cheapest first (a non-surface task skips it). The bundle + ordering come from the loaded registry (cross-cutting rules first -> entity-shape deepest -> wire-contract reshape -> visual-parity last), not hardcoded `docs/ux/*.md` filenames.
   - Wire-contract reshape — response-schema rewrite per Phase A captured bytes.
   - Parity gaps — DEFERRED to the Phase C check `per profile.parity`; don't pre-tune.

2. **Test-first path (default):** for each unit, pre-commit the red `per profile.red` — implement until green, refactor. Where tests live and what may be mocked are the lane's `## Earned rules`: apply the ids briefed for this unit (Contract rule 3), never a convention recalled from memory.

3. **Structural path (carve-out only, `per profile.carve-out`):** skip the red phase — change the source, run `<typecheck>` + `<tests>` to verify no regression (skip either where the profile leaves it unbound); read the `## Earned rules` section once at Phase B entry and again at close. New behavior REQUIRES the test-first path; if a structural carve-out turns out to need new behavior mid-flight, ESCALATE to operator and re-declare discipline.

4. **After each rule satisfied** — confirm in chat: file:line of change + which Acceptance `[ ]` bullet flips to `[x]` + `<typecheck>` result + the `R-*` ids applied (from this unit's briefing) with the change site's `file:line`. Wait for operator's `next` (or equivalent) before starting the next rule. **NO batching multiple rules into one confirmation.** The discipline collapses immediately if you do.

5. **Tag changed callsites `per profile.tag`** — the slot says whether this family tags at all, and what carries no tag.

6. **Operator can pause anywhere** to course-correct. Treat any operator interjection as a STOP — finish the current `<typecheck>`, report state, wait for direction. The operator has full context the skill doesn't.

Phase B continues until all Acceptance `[ ]` bullets except the parity bullet are flipped. Parity bullets close in Phase C `per profile.parity`.

## Anti-patterns

- **Don't merge with `/said:add-task`.** Add-task creates the backlog entry; this skill implements an existing entry. Separate skills, separate phases of the per-task lifecycle.
- **Don't subsume `/said:review-ux`.** The UX gate is deliberately separate; this skill INVOKES it at Phase C, doesn't replace it. The split exists because "implementation agent declares done, QA agent rubber-stamps" is the regression-shipping pattern the separation guards against.
- **Don't batch rules in Phase B.** "I'll satisfy three rules at once in one commit" = discipline collapse. One rule, one confirmation, one chat message. The agent's tendency to bulk-edit is the failure mode this discipline exists to prevent.
- **Reference comments, where the profile tags at all: `// <task-id>` only.** NOT `// <task-id>: <anything>` — the suffix is what produced the prose problem.
- **Don't auto-progress phase boundaries.** Operator pauses at Phase A -> Phase B and Phase B -> Phase C are mandatory in the interactive forms. If the operator reply is silent or ambiguous, ASK rather than proceed. (The `arm` fan-out form has no operator to pause for — it runs A->B under forced autonomy and returns owed items; **Fan-out forms**.)
- **Don't run on `Status: Done` tasks.** BLOCK; for follow-ups on COMMITTED Done tasks (`git log --all --grep <task-id>` non-empty), redirect to `/said:add-task`. Pre-commit Done tasks MAY be amended in place per template-tasks.md pre-commit carve-out — operator gate via mid-flight rule below.
- **Don't silently fold mid-flight scope additions.** When operator's message during any phase introduces a requirement not in the task's Approach, STOP and classify before proceeding:
   - **Within scope** (Approach implicitly covers it) -> proceed.
   - **Scope-creep, task uncommitted** (`git log --all --grep <task-id>` empty) -> propose in-place amendment to Approach + Acceptance + `### Deviations` note documenting the late fold-in; re-run `/said:add-task` Step 3 spec coverage gate for the new requirement; operator confirms before write.
   - **Scope-creep, task committed** -> redirect operator to `/said:add-task <feature-id>` for the new requirement. Current task stays as shipped.
  Never silently fold; never silently split. The classification IS the discipline.
- **Don't invent new `###` headers when closing tasks.** The section list in template-tasks.md is exhaustive. Any new header is a regression to the multi-pass drift the conformance-fold settlement retired.
- **Don't extend or wrap a generic multi-pass feature-development skill.** Those produce the multi-pass churn this driver escapes. `/said:impl` supersedes them for SAID-architected features (any feature with `docs/features/<feature>.tasks.md`); a generic feature skill stays available for non-SAID one-off feature work.
- **Don't make test-first optional.** Test-first is the default discipline. Structural carve-out (folder moves / import retargeting / doc edits) is rare; declare it explicitly at Phase A with one-sentence justification. Silently skipping the red on a test-fit task is the discipline-collapse failure mode.
- **Don't silently skip Phase C code-review.** It runs `per profile.code-review`; skip ONLY as that slot allows, or when a structural carve-out was declared at Phase A, or on an operator override — always with the reason logged in chat, never silently. Quality gates + `/said:review-ux` together do NOT catch deep logic / security / race-condition bugs — those need a dedicated code-review subagent.
- **Don't spawn fan-out arms from inside this skill.** Fan-out is spawned at SKILL level by `said:said` via the Workflow tool, one arm per write-disjoint task — never from inside impl (`ADR-SAID-S09`). The real platform constraints (recorded in `ADR-SAID-S09`): the **Workflow tool exists only in the main context** (a subagent cannot fan out), and a subagent has **no operator** (`AskUserQuestion` is removed — pauses return as data). Nested subagents ARE permitted (three layers by default), so "cannot spawn" is not the reason; arms simply **never run Phase C** — the umbrella gate needs a quiescent tree, a review-FAIL loop inside an arm has no operator or bound, and the gate decision is main's. The `arm` / `close` forms (**Fan-out forms**) are that fan-out, defined.
- **Don't bypass `Refs:` write-set discipline.** Refs is for ADR / UX-spec / feature-spec paths the task **creates or edits**. Reading list is the read-set. Refs is not for citing everything relevant.
- **Don't commit.** Commit is operator-triggered. The skill writes the task close + reports state; operator runs `git add` + `git commit` with the right commit-msg prefix per project convention.
- **Don't load source UX specs upfront in Step 0.** The task body's Reading list `(full read)` flag governs what to open at Phase A. Pre-loading specs the task doesn't cite is context bloat.
