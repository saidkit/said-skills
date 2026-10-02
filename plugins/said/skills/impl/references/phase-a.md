# impl — Phase A procedure (Classify + Inventory)

Read from the spine (`SKILL.md` Contract rule 1) at the moment it names; every rule here is standing for the whole phase.

## Common compositions (upstream -> this skill)

Two canonical operator flows feed tasks into `/said:impl`:

**A — Planned feature** (Phase 1 -> 2 -> 3):

```
/said:scope-refine docs/working/<feature>/handoff.md
/said:architect docs/working/<feature>/scope.md
/said:impl <task-id>
```

(Use `/said:scope-grill` instead of `/said:scope-refine` for thin-idea ideation without a handoff doc.)

**B — Ad-hoc bug fix** (Triage -> Append -> Drive):

```
/said:triage <bug>
/said:add-task <feature-id> bug
/said:impl <task-id>
```

(Skip `/said:triage` when root cause is already known.)

No one-shot wrapper exists for the interactive forms by design. Mandatory operator pauses at each phase boundary are the discipline that prevents the multi-pass churn the 3-phase driver replaces. (The `arm` fan-out form forces autonomy — a subagent has no operator — so it returns every operator question to main instead; **Fan-out forms**.)

## Phase A — Classify + Inventory

> **Stance: read the task. Classify it. Declare implementation discipline. Inventory current state against the Acceptance checklist with file:line evidence. Verification work, not coding. Report and STOP.**

Procedure:

1. **Classify task size as S / M / L** per the defaults below:
   - **S** (≤~50 LOC, bug fix or polish, single screen, ≤2 rule-anchors cited in Approach): skip the inventory table; declare classification + discipline; produce a one-paragraph plan; STOP for operator OK; jump to Phase B.
   - **M** (~50–300 LOC, single screen-shape, 3–6 rule-anchors): full inventory.
   - **L** (~300+ LOC, multi-screen or multiple rule clusters): full inventory; flag any pieces that should split into separate task IDs (escalate to operator if so — that's an `/said:add-task` decision).

2. **Declare discipline** in one sentence:
   - **Test-first (default)** — the red is a checkable pre-commitment that fails before the work, `per profile.red`; green = it passes / is checked with `file:line` evidence; then refactor. How tests are placed and what may be mocked comes from the lane's `## Earned rules` (Step 0 #9), never from a remembered convention.
   - **Structural — declarative-test/no-test (carve-out)** — only for work the loaded profile's `carve-out` slot admits, `per profile.carve-out`. Justify the carve-out in one sentence. Never silently skip test-first, and never widen the slot.

3. **If S — output classification + discipline + plan paragraph. STOP. Skip steps 4–6.**

4. **Read in parallel** — every Reading-list UX spec flagged `(full read)`, AND every current-implementation file under the entity's feature dir cited in Reading list (or implied by Approach — e.g., `features/<entity>/` if the task migrates that entity). UX specs ground the rule anchors; current-impl files ground the "Evidence" column in step 6. Cite each in the inventory output with one-line anchor (e.g., "Read the routed rule spec — its rules in scope per task Approach"; "Read `<screen file>:1-120` — current shape baseline").

5. **Run the lane's wire-capture rule, if it declares one.** A lane whose tasks cite endpoints states its capture procedure as an `R-*` line in its `## Earned rules` (Step 0 #9) — the command, the auth, where the captured payload lands (`docs/working/<feature-id>/<task-id>-wire-<endpoint-slug>.json` is the conventional path). Run that rule for every endpoint cited in the task's Acceptance; note drift between captured bytes and the client schema in the task body's Approach. **Drift = blocker; surface in inventory.** No such rule -> no probe; the wire bullet is judged at Phase C by the lane's declared Checker.

6. **Inventory table.** One row per `[ ]` Acceptance bullet, **plus one row per file named in the companion spec's §Implementation pointers (or equivalent file list)**. If a spec-named file doesn't exist on disk, the row's `Work` column reads `CREATE`. Phase A cannot complete with a spec-named file unaccounted-for — silently skipping a mandated component is the slip vector this rule closes. Columns: Bullet / Currently satisfied? (yes / no / partial) / file:line evidence / Work to satisfy.

   Example shape:

   | Acceptance bullet | Satisfied? | Evidence | Work |
   |---|---|---|---|
   | `<ux-spec>` #NN, #MM satisfied (from loaded registry) | no | `<screen file>:42` mounts an inline control; needs the rule's component per #MM | Replace inline state with the lane's list-state hook; mount the lane's toolbar component |
   | GET `/<entity>/terms` — response schema matches captured bytes | no | Captured `{data, pageCount, totalCount}`; client schema expects `{items, total, page, limit}` | Rewrite the list-response schema to the wire shape |
   | Surface-parity: matches the reference | no | Not checked | Phase C parity check `per profile.parity` |
   | Spec §14 names `features/<entity>/components/<entity>-users-table` | no | Not on disk | CREATE |
   | Spec §14 names `features/<entity>/components/<entity>-users-table-columns` | no | Not on disk | CREATE |

7. **STOP for operator review.** Brief status: "Phase A complete. Inventory above; <N> bullets unsatisfied, <M> with wire drift flagged. Reply OK to proceed to Phase B (Implement), or flag anything to revise first."

8. **Escalation path — Approach unsatisfiable.** If the inventory reveals the task's Approach is structurally unable to satisfy Acceptance (wire shape differs from client schema in ways the task didn't anticipate; an Acceptance bullet has no work that can satisfy it without violating a Boundary; a cited rule conflicts with another cited rule), do NOT proceed to Phase B. Surface the gap to operator with one-line diagnosis + recommended re-spec path: `/said:architect <scope-path> output-name=<feature-id>-v2` for re-architecture, or `/said:add-task <feature-id>` if the gap is a follow-up scope. Proceeding against an unsatisfiable Approach is how Pass 1 / Pass 2 / Pass 3 drift begins. This is an **operator question**: under a blanket autonomy grant it does not relax -- classify it owed and hold / return, never auto-decide (`phase-b.md`, "Operator questions do not relax under a blanket grant").

9. **Blocked-on question at start.** If the task carries a `**Blocked-on question:** <id>` marker with no lift record in `## Lifted holds`, do NOT proceed to Phase B: it is a task-blocking operator question (`phase-b.md`, the fifth stop-point). Classify it owed and return it as data; `impl` coins no marker (the `said` / `flow` orchestrator emits `OPERATOR-QUESTION-HELD` on its `goal: stop` line). A marker lifted by a `## Lifted holds` record proceeds normally. The hold is lifted by one line in the log's `## Lifted holds` section, `- <id> lifted-by: user@WR-<seconds> -- "<verbatim quote>" -- <date> [supersedes: <prior>]`, that cites the operator's answer as a ruling recorded with the `ruled` skill in the work's `rulings.md` (example: `- Q-1 lifted-by: user@WR-1790160000 -- "use the Postgres advisory lock" -- 2026-09-23`). `user` is a fixed role word (the role of the cited answer); the person's name belongs to the ruling.
