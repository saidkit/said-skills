---
name: status
description: >
  SAID status board (terminal) — read-only reporter of where every feature sits
  in the SAID phase chain (Scope → Architect → Implement → Deliver → Closed):
  a roster, a single-feature deep-dive, or a cross-lane board, derived from
  on-disk artifacts. Triggered ONLY by "/said:status [<feature-id>] [--lanes]
  [--stale]". NOT for driving a phase; NOT root-cause tracing ("/said:triage").
---

# said:status — SAID feature status board

The read-only, multi-feature sibling of `/said:flow`: run `flow`'s Step-1 reconstruction over **every** feature and **report** — phase, progress, what's stalled, and the command that advances each. `flow` decides and acts on one feature; this reports on all and drives nothing. The artifacts are the only source of truth.

## Contract — holds every run

- **Read-only.** No edits, no test runs, no downstream skill invoked.
- **Derive, never store.** Reconstruct from artifacts each run; write no status file, board cache, or `_resume.md`. There is no second copy to drift.
- **Script numbers are canonical.** `said_status.py` owns the counts — never override them in prose. A wrong number is a bug to fix in the script, not a value to hand-edit.
- **Hard exit at the report.** End with the rendered board + a suggested `Next:` command. The operator runs it; never proceed into a phase.

## Invocation

- `/said:status` — roster for the current lane.
- `/said:status <feature-id>` — single-feature deep-dive (across its lanes, if multi-lane).
- `/said:status --lanes` — cross-lane board, grouped by lane.
- `/said:status --stale` — attention filter: only non-`Closed` features with an idle/blocked flag.

## Step 0 — Resolve conventions (declaration-first, then glob)

Never hardcode paths or id shapes. Resolve in this order, and state what resolved:

| Fact | Declaration (first) | Fallback (second) |
|---|---|---|
| Docs root · working root | repo `CLAUDE.md` SAID doc paths / a `## Lane` block's declared roots | `docs/features/` and `docs/working/` |
| Issued id-prefixes | `CLAUDE.md` (e.g. *"issues `APP-NN` and `INIT-NN` only"*) | stems of `<docs>/features/*.md` |
| Id shape | `CLAUDE.md` / `template-tasks.md` (`<PREFIX>-<NN>`, sub-phase `-<slug>`, multi-target `-<APP>-<NN>`) | regex `[A-Z]+-[0-9]+` |
| Lanes | `## Lane` blocks / a repo-root lane registry | single lane |

**Enumerate the registry as a union** (dedup by feature-id) — a spec-only list hides the states an operator most needs to see (scoped-but-unarchitected, reserved-but-empty). Include:

- every `<docs>/features/<id>*.md` that is not `template*` / `README` / a `*.tasks.md`, AND
- every `<working>/<id>/` directory whose name matches an issued prefix.

**Foreign / legacy prefixes** — a `<working>/<id>/` whose prefix the repo doesn't issue and which has no current spec — never render per-row; collapse to one footer line `legacy: …`. (e.g. a `LEGACY-01..10` block whose prefix the repo no longer issues.)

## Step 1 — Run the analyzer

`said_status.py` sits beside this SKILL.md and owns the mechanical derivation. When `python3` is present, run it — do not reconstruct by hand.

```bash
python3 <skill-dir>/said_status.py \
  --root <repo-root> --docs-dir <docs>/features --working-dir <working> \
  [--prefixes APP,INIT] [--legacy-prefixes FEAT,CONF] [--today YYYY-MM-DD] \
  [--lane NAME[:root=…;docs=…;working=…;prefixes=…;legacy=…]]... [--project <label>] \
  [<feature-id>] [--stale] [--json]
```

- Args map to Step-0 values. **Omit `--prefixes` / `--legacy-prefixes`** and the script infers the active set (a prefix is active if any id has a spec or `scope.md`); pass them when `CLAUDE.md` states the issued set, to be exact.
- No `<feature-id>` → roster · `<feature-id>` → deep-dive · `--stale` → attention filter · `--json` → the structured data layer (reason over it; don't re-derive by eye).
- **Lanes default to one.** Omit `--lane` → single-lane output (no `lane:` headers). Multi-lane: read each `## Lane` block (`/said:flow` Step 1) and pass one `--lane NAME:root=…;prefixes=…` per lane. You resolve the fuzzy `## Lane` declarations; the script aggregates what you pass.
- `--today` makes a run reproducible; omit for the real date.
- **Show the text output verbatim** — columns are deterministically aligned; re-typing reintroduces the drift the script exists to remove.
- **No `python3`?** Execute the reconstruction contract below by hand with grep/git, and say so.

## Step 2 — Add the judgment a script can't

The script gives facts; you give the reading. After showing its output:

- Interpret a flag: `⚠ Nd idle` on Implement → name the likely stall (an open gate? a blocked task?); `! integrity` → point at the drift (Summary Table vs parsed sections).
- Answer follow-ups from `--json` (stalest, oldest-started, most Todo) — reason over the data.

## Reconstruction contract — what `said_status.py` computes (and the by-hand fallback)

Per registry feature-id, glob `<id>*` so sub-phased specs (`<id>-<slug>.md`) and their task logs count. Derive:

**Phase — ordered checks, first match wins.** Order matters: a `Closed` feature also has `Todo == 0`, so check the footer before the count. Never key phase on `Todo == 0` alone.

1. `## Debrief close` footer in a `<id>*.tasks.md` → **Closed**
2. spec + tasks, `Status: Todo` count `== 0`, no footer → **Deliver** — the post-Implement gate + debrief window (`/said:flow` names this same phase *Deliver*)
3. spec + tasks, `Status: Todo` count `> 0` → **Implement**
4. `<working>/<id>/scope.md` exists, no spec → **Architect**
5. no scope.md, no spec → **Scope** — append `· not started` when the working dir is absent or empty

**Task rollup.** Count `**Status:** <X>` across the tasks log: Done / Todo / Canceled / Backlog.
Denominator = `Done + Todo` (Canceled + Backlog shown but excluded from the bar). If a `## Summary
Table` exists, cross-check its rows vs the parsed counts; on mismatch emit a one-line **data-integrity** note — parsed `Status:` lines win, the table is a convenience index that can go stale.

**Gate sub-ticks** (meaningful at Deliver/Closed), from working-dir artifacts: `review-qa*.md`→qa · `review-ux*.md`→ux · `accept*.md`→accept · `debrief.md`→debrief-started · `## Debrief close` footer→debrief-done. Render `✓` present · `○` pending · `–` n/a (`ux –` for a no-UI feature — absence of a UX gate is not a failure).

**Dates.** `started` = min `(YYYY-MM-DD)` across Status lines · `last task-date` = max · `git last-activity` = `git log -1 --format=%cd --date=short -- <id>*.md <id>*.tasks.md <working>/<id>/`.
`idle` = today − max(last task-date, git last-activity) · `age` = today − started.

**Staleness.** Non-`Closed` only: `⚠ <idle>d idle` when idle exceeds the phase threshold — default
**Implement/Deliver 7d, Scope/Architect 14d** (tunable; state the value used). `Closed` carries no staleness. No git → say so, fall back to in-file dates; never fabricate an activity date.

**Blockers** (cross-lane; usually empty single-lane). A task whose Approach / Out-of-scope names an open crossing (`*-handover-*.md` with no reply / no `## Reply`) → `⛔ blocked: <task> → <crossing>`.

**Next action — by phase.** Scope → `/said:scope-refine <handoff>` (or `/said:scope-grill <id>` if the input is thin/empty) · Architect → `/said:architect <working>/<id>/scope.md` · Implement → `/said:impl <id>` · Deliver → the next un-run of `/said:review-qa <id>` → `/said:review-ux <id>` → `/said:accept <id>` → `/said:debrief <id>` · Closed → none.

**On probe disagreement**, trust the `## <id>` section over the Summary Table, and say so.

## Output shapes

### Roster — default, no argument

A monospace block (fenced, so columns align), sorted **attention-first**: Implement → Deliver → Architect → Scope → Closed; within a phase, most-idle first.

```
SAID status · <PROJECT> · <n> lane(s) · <today>

<ID-7>  <Phase-9>  <bar-9>  <done>/<tot>  <n Todo>  <flags>
...
Next: <cmd1> · <cmd2> · <cmd3>        ← top ≤3 actionable, phase order
legacy: <prefixes> — <one-line why, where they live>
!  <data-integrity notes, if any>
```

- **bar** = 9 cells, `█` × round(9 × done/denominator), `░` for the rest. No denominator yet (Scope/Architect) → `·········` — "no work counted," not "0% done."
- **flags** = `⚠ Nd idle` and/or `⛔ blocked: …`; `Closed` rows may show the gate ticks instead.
- One line per feature. Never list legacy features per-row.

### Deep-dive — `/said:status <feature-id>`

Markdown (keep `file:line` paths clickable) — the "position in the SAID cycle" view:

- **Pipeline** — an arrow sequence with the current stop marked:
  `Scope ✓ → Architect ✓ → Implement ● → Deliver ○ → Closed ○` (`✓` done · `●` current · `○` ahead).
  Never a box-drawn diagram.
- **Deliver** line (at/after Deliver): `review-qa ✓ · review-ux – · accept ○ · debrief ○`.
- **Tasks** — rollup (`Done N · Todo M · Canceled K`), then the open items:
  `<id>-<nn> · <title> · <status-date>`. Canceled/Backlog folded under a count.
- **Dates** — started · last activity · age · idle (with the threshold applied).
- **Blockers** — each open crossing and the task it holds, or `none`.
- **Next** — the exact command(s) to advance, and the key artifacts (`scope.md`, spec, tasks log) as clickable paths.

### Cross-lane — `/said:status --lanes`

Resolve lanes via `/said:flow` Step 1 (declaration-first `## Lane` blocks; glob fallback), then run the script with one `--lane NAME:root=…;docs=…;working=…;prefixes=…` per lane. One roster section per lane under a `lane: <name>  (<root>)` heading, columns aligned across lanes. A `<feature-id>` spanning lanes matches the umbrella id + suffixed lane ids together (`PROJ-01`, `PROJ-01-BE`), labelling each with its `lane:` and its own phase. (Phase is per-lane; cross-lane `Closed` / crossing semantics stay `/said:flow`'s job — this skill reports, it doesn't gate.)

## Rendering rules

- **No box-drawing / pseudographics** (`│ ─ ┌ └ ├ …`) anywhere. Pipelines are arrow sequences or nested lists; the roster is space-aligned columns in a code fence.
- **Block-glyph progress bars are fine** — `█`/`░` are data-viz marks, not diagram borders.
- One line per feature in the roster; the deep-dive may breathe. Prefer lists.

## Anti-patterns

- **Don't do the mechanical work by hand when `python3` is present** — that's the variance the script removes. Hand-execute the contract only as the declared no-python fallback.
- **Don't auto-invoke downstream skills.** Report the `Next:` command; the operator runs it.
- **Don't key phase on `Todo == 0`.** Check footer + spec presence first (the contract's ordering).
- **Don't trust the Summary Table over the sections** — the script emits an `! integrity` note on mismatch.
- **Don't render legacy/foreign prefixes per-row.** Collapse to the `legacy:` line.
- **Don't fabricate dates.** No git → say so, use in-file `(YYYY-MM-DD)` only.
- **Don't hardcode `docs/features` / a project prefix / a project name.** Resolve in Step 0.
