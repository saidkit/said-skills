---
name: debrief
description: >
  SAID/Phase 4 (Debrief) driver — feature-level retrospective that runs ONCE
  after every task in `<feature>.tasks.md` is verified-closed. Drives three
  sequential phases: Phase A (Read + Scan + Propose, STOP for operator review),
  Phase B (Execute backports rule-by-rule with per-finding confirmation), Phase
  C (Close — append `## Lessons` section + `## Debrief close` footer + optional
  shipping reports). Triggered ONLY by the explicit command "/said:debrief
  <feature-id> [--no-reports]". NOT for per-task verification — that's
  `/said:review-ux`, `/said:review-qa`, Phase 3. NOT for spec authoring — that's `/said:architect`, Phase 2. NOT for backlog additions — that's
  `/said:add-task`.
---

# Feature Debrief — Phase 4 (Debrief): Per-Feature Retrospective Driver

This skill drives a closed feature through a feature-level retrospective: reconciles spec + tasks against shipped reality, migrates forward-looking rules into durable ADR/UX-spec hosts, compacts the spec back to template shape, captures distilled lessons, and (if shipping) emits PR + Slack summary artifacts. Phase 3 is the input boundary (every task `Status: Done`, quality gates green, manual UX/QA pass complete); operator commit is the output boundary.

The skill itself is the orchestrator — there is NO separate agent. You — the main agent — drive three sequential phases within ONE invocation. **Operator pauses at every phase boundary are mandatory; no auto-progression.** Phase A produces findings + STOPS. Phase B is per-finding with mandatory operator confirmation. Phase C closes only when footer + lessons + handoff (or N/A each) are all settled.

**Single-pass goal.** Multiple debrief runs on the same feature = failure mode. The whole point of operator-driven Phase A review is to catch surprises before backports start. If mid-Phase-B you discover Phase A missed a category — STOP, return to Phase A, expand findings.

## When this fires

The operator invokes:

- `/said:debrief <feature-id>` — runs against `docs/features/<feature-id>.md` + `docs/features/<feature-id>.tasks.md`. Suffix-variants (e.g. `<feature>-phaseB.md`) auto-resolved via recency glob.
- `/said:debrief <feature-id> --no-reports` — same as above, suppresses Phase C `pr.md` + `report-slack.md` emission (use when feature is parked, not shipping).

If any task is `Status: Todo` / `Status: In progress` — BLOCK + redirect (`/said:impl <feature-id>` to close remaining tasks).

If spec § Related links to other feature specs, ask operator whether they are **siblings** (umbrella — all must be closed before Debrief) or **successors** (post-Debrief — irrelevant to gate). BLOCK on sibling incompletion. A sibling the operator names can also have its rulings list read (Step 0, the sibling check).

If operator asks to author a new feature — wrong skill, redirect to `/said:architect`. If to add a follow-up task — redirect to `/said:add-task`.

## Common compositions (upstream -> this skill)

After Phase 3 closes (all tasks Done, all quality gates green, operator's manual UX/QA pass complete):

```
/said:impl <feature-id>          # final task closes; whole-feature mode confirms green
                                    # operator runs manual UX/QA pass
/said:debrief <feature-id>
```

## Step 0 — Preflight

1. Resolve feature paths from `SAID.feature-spec:` + `SAID.task-log:` + `SAID.working:` on the `## Lane` block; no block/key -> HALT (operator declares it), never glob-guess. The resolved working root is used for every Phase A/B/C output below. **ADR ids + dir:** from `SAID.adr-prefix:` + `SAID.docs-root:` — every promoted/minted ADR id, `Refs:` pointer, and the close-footer migration id binds to `SAID.adr-prefix:`; the ADR dir resolves under `SAID.docs-root:`. **Rulings list:** the feature's own list is `rulings.md` in the feature's working folder (the `SAID.working:` value with the feature id filled in), derived from the key and never globbed; read it with the bundled reader, `python3 ${CLAUDE_SKILL_DIR}/rulings-read.py list <that path>`, and keep its output for §A.5. No list -> the reader prints `warn: no rulings list`: record that line and §A.5 reads N/A. An `error:` line (exit 2) -> show it; Phase A does not start until the list reads, and a resumed run continues (item 2a skips Phase A, so the list stays unread there).
2. **Resume + single-run guard (before any full read).** Read the last `## Debrief close` footer of the tasks log (if any) and `docs/working/<feature-id>/debrief.md` (if any). (a) **Resume** -- `debrief.md` has at least one finding row whose `status:` cell is `approved` and not yet `applied` -> this is a resumed run: skip Phase A, continue Phase B from that row; Phase C resumes the same way. A `debrief.md` with no `status:` cells, or with every row `applied | skip | deferred`, is a finished debrief, not a resume. (b) **Single-run guard** -- a footer exists and, **below it in the file** (position, never dates: same-day closes are common), there is neither a task entry with `**Status:** Done` nor a `## Reopen` heading -> STOP: "Feature already debriefed on <footer date>; nothing closed since, a re-run is the single-pass failure mode. Re-open via `/said:add-task` or name what changed." Anything closed below the footer is a **reopen increment**: proceed, and the new footer names it. **Precedence:** (a) is checked first; a resume proceeds and (b) is not evaluated for that invocation. The guard cannot see a footer written for a single task (that is the never-a-footer-per-task anti-pattern below).
3. **Scope the debrief before reading (scope-by-risk).** Take the **delta since the last footer**: the tasks-log lines below the last `## Debrief close` footer (excluding the footer block itself), plus the spec only where it changed since that footer (`git diff <footer commit>..HEAD -- <spec>`; the whole spec when no git history). Grep the delta for non-empty `### Gotchas` / `### Deviations` bodies and for the leak markers of §A.2. **Both zero -> TINY debrief:** run §A.1 stale-state diff + §A.5 rulings + §A.6 successor only, skip §A.2-§A.4, record `Scope: tiny, 0 gotchas, 0 leak hits` in the footer. Otherwise read both files in full (tasks files > 100 KB: the §A.4 stream-read applies to the whole read). A first debrief (no footer) is always full.
4. Status check. For each task entry, confirm `Status: Done`. If any open -> BLOCK with: "Cannot debrief — N task(s) still open. Close them via `/said:impl <feature-id>` first." List the open IDs.
5. Sibling check. If spec § Related cites other feature specs, ask operator: "Are these siblings (umbrella, must all close) or successors (post-Debrief)?" BLOCK only if siblings incomplete. When the operator also names a sibling whose rulings list should be read, derive its path as in item 1 with the sibling's feature id (from the `SAID.working:` key of the lane that holds the sibling) and read it with the same reader, with the same `warn:` and `error:` handling. Its rows enter §A.5 tagged `sibling <feature-id>` in the id cell, every one `proposed` for the operator to keep or drop (approved keeps a row, skip drops it); none is taken as this feature's because its evidence paths point into this lane.
6. Quality gate spot-check. Resolve and run the project's quality-gate command at runtime the same way `/said:review-qa` Step 0 resolves it. Halt if it goes red — the feature isn't actually closed.
7. **Phase-3.5 gate check.** Glob `docs/working/<feature-id>/review-qa-*.md` and `accept-*.md` (most recent by mtime). (a) If **neither exists** -> do not proceed silently: surface "No Phase-3.5 gate artifacts for `<feature-id>` — run `/said:review-qa` + `/said:accept` first, or confirm skip." **A confirmed skip is carried forward, not waved through — it is recorded at Phase C as the `Gate-skip` line of the `## Debrief close` footer (step 3), so the omission leaves an audit trail instead of a silent gap.** (b) If the latest `review-qa` **or** `accept` verdict is **FAIL** -> BLOCK with redirect: "Resolve `/said:review-qa` / `/said:accept` failures before debrief." This is the gate `/said:review-qa` and `/said:accept` advertise (their "Gate effect for `/said:debrief`" sections) — without this read it never actually fires. **(c) If the latest `accept` verdict is MANUAL-PENDING** -> HOLD: announce once, then hold (the operator question `accept:164` promises -- operator confirms the manual items inline before debrief proceeds); never proceed on an unresolved MANUAL-PENDING, never auto-promote it. **(d) If the reviewer-gate could-not-run** (a declared reviewer's verdict **could not be produced** -- a missing verdict artifact or an impossible recompute; distinct from a **ran-and-FAILed reviewer** (which stays surfaced-not-blocking) and from an operator `[N/A]` skip (which stays PASS)) -> **HOLD**: announce once, then hold -- a could-not-run gate is **not a passed gate**. The recorded-probe design is preserved: **no auto-block** pre-close hook is introduced (a HOLD is operator-owned, not a machine block).

## Phase A — Read + Scan + Propose (STOP for operator review)

Output: `docs/working/<feature-id>/debrief.md` with 6 sections. Then STOP.

1. **§A.1 stale-state candidates.** Diff acceptance checkboxes in spec vs `Status: Done` evidence in tasks. Surface every `[ ]` whose corresponding task closed; surface narrative-tense drift (future-tense for shipped features); surface stale § Feature Tasks summary table rows (counts / status / dates).

2. **§A.2 leak-scan candidates.** Grep spec + tasks for forward-looking rule markers: `must`, `always`, `never`, `frozen`, `convention`, `spec change`. Sort each hit into one of three tiers by the action it implies for Phase B:

   - **§A.2a — Collapse to pointer.** Rule appears verbatim or near-verbatim in an existing `docs/adr/<X>.md` § or `docs/ux/<area>.md` frozen rule. Phase B replaces the spec paraphrase with a one-line `Refs:` pointer. Row: `<file>:<line> | collapse-to-pointer | <existing destination § header> | <reason> | status: proposed`.

   - **§A.2b — Promote to existing destination.** Rule is new content, the destination file exists, and the rule fits under an existing § header (or amends an existing frozen rule's wording). Phase B appends or amends + adds `Refs:` pointer + removes from spec/tasks. Row: `<file>:<line> | promote-to-existing | <destination § header> | <reason> | status: proposed`.

   - **§A.2c — Create new ADR sub-section or new frozen UX rule.** Rule needs a heading that does not exist yet. Row: `<file>:<line> | create-new | <destination path>[ § <draft heading>] | <earn-its-place rationale> | <evidence: task IDs> | status: proposed`. Draft heading is optional — include when the heading is obvious, omit when authoring needs research. §A.2c rows surface in Phase C's pending-proposals list with a suggested authoring prompt; Phase B captures the proposal handle but leaves the new heading body for the operator to author.

   **Adjacent-rule scan.** When one frozen rule in a UX-spec file (`docs/ux/<area>.md`) lands in §A.2b or §A.2c, read all other frozen rules in the same file and add any sibling rule showing the same staleness signal as a §A.2b row alongside the original finding. Adjacent rules travel together.

3. **§A.3 bloat candidates.** Identify bullets in spec § Context to load / UI/UX Requirements / API Integration that:
   - Paraphrase content already in an ADR or UX-spec.
   - Narrate implementation history rather than committing to behavior.
   - Repeat what's elsewhere in the same spec.
   Each gets a proposed action: cut / collapse-to-pointer / merge.

4. **§A.4 lessons candidates.** Read every Done task entry; harvest `### Gotchas` + `### Deviations`. Each surprise or hard-won insight is a lesson candidate. Format as draft `**<one-line statement>**. Why: <reason>. Source: <task ID>.` For tasks files > 100 KB, stream-read: § Summary Table -> identify Done IDs -> per-task grep `### Gotchas` + `### Deviations` line ranges; avoid full-file load.

5. **§A.5 rulings.** The reader shows each line as `pending`, `landed`, `rejected` or `superseded`. One row per `pending` line in the rulings lists Step 0 read (the other three need no row): `<id> | <ruling text as the reader shows it> | <evidence paths, or `none`> | <proposed home class> | status: proposed`. Propose the first home class that fits, in this order:
   - **task-log home** -- if a Done task of this feature cites the ruling id or applied it, its log entry is the home;
   - **lane home** -- else, if the ruling is or should be written under `SAID.docs-root:` or in the lane `CLAUDE.md`;
   - **owed** -- else (another lane, another project, or code and config the operator lands); name the owner.
   A malformed line the reader reports gets a row too (`malformed line <n>`; the operator fixes the list). No list -> the section holds the reader's `warn:` line and nothing else. This section runs on every debrief, a TINY one included.

6. **§A.6 successor.** Ask operator: "Successor feature queued?" If yes, name it. If no, mark N/A.

**`pre-completion-checks.md` ingestion.** If `docs/working/<feature-id>/pre-completion-checks.md` exists (cross-cutting verifications surfaced during scope grilling that don't bind to specific tasks), read it. Fold each entry into §A.1 stale-state or §A.2 leak-scan as appropriate.

Default finding row: `<file>:<line> | <proposed action> | <proposed destination> | <reason> | status: proposed`. **Per-row status** is the resume state: Phase A writes `proposed`; the operator sets `approved | skip | revise`; Phase B sets `applied @ <file>:<line>` or `deferred`. A resumed run (Step 0 item 2a) continues from the first `approved` row not `applied`. §A.2 carries per-tier extended shapes — see §A.2a/b/c above.

**STOP.** Tell operator: "Phase A complete — N findings in `docs/working/<feature-id>/debrief.md`. Review (mark approved / skip / revise) before I begin Phase B."

## Phase B — Execute backports

For each approved finding, in order: stale -> leak -> bloat -> lessons -> handoff.

**One finding, one confirmation.** After each edit: report `<file>:<line>` + 1-sentence summary; await operator nod before next.

- **Stale-state.** Flip `[ ]` -> `[x]` (or `[N/A — <reason>]`). Sync § Feature Tasks summary table rows from `<feature>.tasks.md` `Status:` lines. Fix narrative tense (future -> past) on shipped-feature descriptions.

- **Leak-scan.** Before promoting, grep the ADR dir (`SAID.docs-root:`-relative `docs/adr/*.md`) + `docs/ux/*.md` for clauses that **contradict** the rule being moved. If any surface, flag to operator and halt this finding pending decision. On approval: add rule to destination ADR/UX-spec; remove from spec/tasks; add `Refs: <ADR-ID> §<n>` (id per `SAID.adr-prefix:`) (or `Refs: ux/<area>.md §<n>`) pointer. Earn-its-place gate: pattern must have appeared in ≥2 features OR carry independent strong-spec justification — single-feature patterns stay in feature-spec.

- **Bloat.** Cut paraphrased bullets; trim § Context to load to template's ~6–10 entries; collapse implementation narrative into one-liners or pointer to commits.

- **Lessons.** Append `## Lessons (<feature-id>)` section to `<feature-id>.tasks.md` immediately **before** the `## Debrief close` footer (or at file end if no footer yet). One bullet per lesson, shape: `**<one-line statement>**. Why: <reason / past incident>. Source: <task ID>.` Terse; ≤ ~10 entries per feature. If no lessons captured — skip section entirely (no empty header).

- **Handoff (if applicable).** Write `docs/working/<next-feature>/idea.md` with §A purpose / §B target shape / §C constraints / §D open questions, per Phase 1 scope-shape convention. Skip if operator marked successor=N/A.

- **Mid-Phase-B findings.** When a candidate surfaces during Phase B work that was not in the §A inventory, append it to the correct section of `debrief.md` (§A.1 / §A.2a/b/c / §A.3 / §A.4), surface the new row inline to operator with the same y/skip/revise prompt, then resume Phase B per the answer. Single-pass discipline holds — the Phase A inventory grows inline as findings appear.

## Phase C — Close

1. Re-verify quality gates green. Resolve and run the project's quality-gate command at runtime the same way `/said:review-qa` Step 0 resolves it. Halt if it goes red.

2. **Pending proposals.** For every §A.2c row, plus every Phase-A row the operator marked `defer` (operator chose to author later), append a `## Pending proposals (<feature-id>)` section to `debrief.md` (working file — tasks file stays clean). Each entry carries:

   - Destination path + draft heading (when supplied) or destination path + topic (when not).
   - One-line rule statement.
   - Evidence (task IDs).
   - Suggested authoring prompt the operator can copy-paste into a follow-up turn.

   Entry shape:

   ```
   - **`<destination path>` § <draft heading or topic>** — <one-line rule statement>.
     Evidence: <task IDs>.
     Suggested prompt: `Author <destination path> § <draft heading>. Rule: <one-line statement>. Evidence: <task IDs>. Earn-its-place: <rationale>.`
   ```

   If no candidates qualify, mark Pending proposals N/A in the close footer (next step).

3. Append `## Debrief close` footer to `<feature-id>.tasks.md` (after `## Lessons (<feature-id>)` if present). First confirm no `debrief.md` row is still `approved` and not `applied` -- resolve each to `applied`, `skip` or `deferred`; a footer never lands over an unfinished resume:

   ```
   ## Debrief close (YYYY-MM-DD)
   - Reconciliations: N (one-line summary)
   - Migrations: M (rule -> `<SAID.adr-prefix>` id / ux/yyy.md)
   - Compactions: K (spec A -> B lines)
   - Lessons: in this file § Lessons (or N/A)
   - Pending proposals: in debrief.md § Pending proposals (or N/A)
   - Successor: `docs/working/<next-feature>/idea.md` (or N/A — reason)
   - Gate-skip: N/A (or: Phase-3.5 gates skipped per operator YYYY-MM-DD — <reason>, per Step-0 item 7)
   - Scope: full (or: tiny, 0 gotchas, 0 leak hits, per Step-0 item 3), Resumed: no (or: from row N)
   ```

4. **If shipping** (operator confirms feature is being merged/released, not parked), and `--no-reports` not set:
   - Emit `docs/working/<feature-id>/pr.md` — technical PR body: Title / Summary / Changes table / Breaking changes for FE.
   - Emit `docs/working/<feature-id>/report-slack.md` — human-readable team summary.

5. Operator commits.

## Anti-patterns

- **Don't run on features with open tasks.** BLOCK + redirect to `/said:impl`.
- **Don't autonomous-backport.** Phase A -> operator review -> Phase B is mandatory. No exceptions.
- **Don't create a new task ID for Debrief close.** It's a footer section, not a task. A **reopen increment** (tasks closed after the last footer) appends a dated footer naming the increment; a **re-run with nothing closed since** is blocked at Step 0 (single-pass goal). Never a footer per task.
- **Don't cite `docs/working/<feature>/` paths in `Refs:` on backport edits.** Working folder is operator workspace per `template-tasks.md` discipline; durable refs point to spec / ADR / UX-spec / source-code.
- **Don't promote a pattern to ADR from single-feature evidence** unless the pattern carries independent strong-spec justification. Default: ≥2-feature appearance per the earn-its-place-ADR.
- **Don't pollute the spec with retrospective content.** Lessons live in `<feature>.tasks.md` § Lessons, NEVER in `<feature>.md`. Spec stays forward-looking contract.
- **Don't create a new directory.** No `docs/lessons/`, no per-feature subdirectories. Lessons + close footer + reports all land in existing paths.

## Anchors

- `docs/features/template.md` — spec target shape that Bloat compaction restores.
- `docs/features/template-tasks.md` — close-of-task discipline Debrief inherits + canonical home for `## Lessons` + `## Debrief close` shapes.
- `said:impl` — Phase 3 driver; analogous A/B/C structure precedent.

## Re-read self-check (acceptance)

Before exiting Phase C:

- [ ] All 3 phases distinct in the conversation transcript.
- [ ] Phase A produced `docs/working/<feature-id>/debrief.md` with 6 sections + STOPPED.
- [ ] Phase B is incremental — per-finding confirmation visible in transcript.
- [ ] Phase C closes only when footer + lessons + handoff (or N/A each) are all settled.
- [ ] Quality gates green at Phase C.
- [ ] `## Lessons (<feature-id>)` section present in `<feature>.tasks.md` (or operator-approved absence).
- [ ] No new artifact category beyond `## Lessons` + `## Debrief close` (both in tasks file) + `## Pending proposals` (in `debrief.md`, when non-N/A) + optional `pr.md` / `report-slack.md` (shipping only).
- [ ] Phase C lists pending proposals in `debrief.md` (or operator-confirmed N/A).
- [ ] `Refs:` pointers in backport edits point to durable hosts (spec / ADR / UX-spec / source-code), never `docs/working/`.
