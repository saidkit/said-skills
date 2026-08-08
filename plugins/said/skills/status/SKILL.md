---
name: status
description: >
  SAID status board (terminal) — read-only reporter of where every feature sits
  in the SAID phase chain (Scope → Architect → Implement → Delivery → Closed):
  a roster, a single-feature deep-dive, or a cross-lane board, derived from
  on-disk artifacts. Triggered ONLY by "/said:status [<feature-id>] [--lanes]
  [--stale]". NOT for driving a phase; NOT root-cause tracing ("/said:triage").
---

# said:status — SAID feature status board

The read-only, multi-feature sibling of `/said:flow`. `flow` reconstructs one feature's lanes to
**decide the next action and take it**; this skill reconstructs **every** feature to **report** —
where each one sits in the SAID cycle, what is stalled, and the exact command that advances it.

It runs the same reconstruction `/said:flow` Step 1 uses. Nothing here is a new source of truth;
the artifacts are.

## Architecture — deterministic facts + model judgment

Two layers, on purpose:

- **`said_status.py` (bundled) owns the mechanical derivation** — enumerate features, classify
  phase, count Status lines, compute dates + git idle, read gate files — and emits **JSON** (a
  stable data interface) or a rendered **text** roster / deep-dive. Deterministic, reproducible
  with `--today`, and it **stores nothing** (prints to stdout).
- **This skill owns resolution + judgment** — resolve the agnostic bits from `CLAUDE.md` (Step 0),
  run the script, show its output verbatim, and add what a script cannot: interpreting anomalies,
  answering "why is this stuck", follow-ups.

Why a script *here* and not for `triage` / `impl` / `architect`: those carry genuine judgment that
resists scripting; a status board is pure aggregation, where determinism *is* the feature — the
value is that you trust the numbers at a glance. A miscounted `Status:` line or a fumbled date read
by hand silently poisons that.

## Prime directive — derive, never store

**State lives in artifacts. This skill reconstructs by inspection on every run and writes nothing
— no status file, no board cache, no `_resume.md`.** A stored board drifts from the task logs the
moment a `Status:` line changes; the whole point is that there is no second copy to drift. If a
report is wanted on disk, that is a different, explicitly-requested action — the default is
terminal-only and read-only.

Read-only by contract: no edits, no test runs, no downstream skill invoked. The skill stops at the
report plus a suggested next command. The operator owns the next move.

## When this fires

- `/said:status` — roster for the current lane.
- `/said:status <feature-id>` — single-feature deep-dive (across its lanes, if multi-lane).
- `/said:status --lanes` — cross-lane board, grouped by lane.
- `/said:status --stale` — attention filter: only non-`Closed` features with an idle/blocked flag.

## Step 0 — Resolve conventions (declaration-first, then glob)

Never hardcode paths or id shapes. Resolve, in this order, and state what resolved:

| Fact | Declaration (first) | Fallback (second) |
|---|---|---|
| Docs root · working root | repo `CLAUDE.md` SAID doc paths / a `## Lane` block's declared roots | `docs/features/` and `docs/working/` |
| Issued id-prefixes | `CLAUDE.md` (e.g. *"issues `APP-NN` and `INIT-NN` only"*) | stems of `<docs>/features/*.md` |
| Id shape | `CLAUDE.md` / `template-tasks.md` (`<PREFIX>-<NN>`, sub-phase `-<slug>`, multi-target `-<APP>-<NN>`) | regex `[A-Z]+-[0-9]+` |
| Lanes | `## Lane` blocks / a repo-root lane registry | single lane |

**The registry is a union, not just the spec list.** Enumerate feature-ids from BOTH:

- every `<docs>/features/<id>*.md` that is not `template*` / `README` / a `*.tasks.md`, AND
- every `<working>/<id>/` directory whose name matches an issued prefix.

Dedup by feature-id. The union is what surfaces a feature that is scoped-but-unarchitected (a
`scope.md`, no spec) or reserved-but-empty (a working dir, nothing in it) — a spec-only registry
would render those invisible, which is exactly the state an operator most needs to see.

**Foreign / legacy prefixes** — a `<working>/<id>/` whose prefix the repo does not issue and which
has no current spec — are NOT rendered per-row. Collapse them into one footer line
(`legacy: …`). (In this repo: `FEAT-01..10`, `CONF-01` — pre-fork Hyperflow history.)

## Step 1 — Run the analyzer (deterministic)

The mechanical reconstruction is owned by the bundled script — do not do it by hand when it is
available. It sits beside this SKILL.md: `said_status.py`.

```bash
python3 <skill-dir>/said_status.py \
  --root <repo-root> --docs-dir <docs>/features --working-dir <working> \
  [--prefixes APP,INIT] [--legacy-prefixes FEAT,CONF] [--today YYYY-MM-DD] \
  [--lane NAME[:root=…;docs=…;working=…;prefixes=…;legacy=…]]... [--project <label>] \
  [<feature-id>] [--stale] [--json]
```

- no `<feature-id>` → the **roster**; a `<feature-id>` → the **deep-dive**; `--stale` → attention
  filter; `--json` → the structured data layer (reason over it, don't re-derive by eye).
- Pass the Step-0 values as flags. Omit `--prefixes` / `--legacy-prefixes` and the script
  **infers** the active set (a prefix is active if any of its ids has a spec or a `scope.md`); pass
  them when `CLAUDE.md` states the issued set, to be exact.
- **Lanes — default is one lane.** Omit `--lane` entirely and the output is single-lane (no `lane:`
  headers). For a multi-lane feature, read each lane's `## Lane` block (`/said:flow` Step 1) and
  pass one `--lane NAME:root=…;prefixes=…` per lane — the board then renders a `lane:` section each,
  `--stale` skips clean lanes, and a `<feature-id>` deep-dive labels each lane it appears in. A lone
  `--lane` still renders lane-less. This is the model/script split again: you resolve the fuzzy
  `## Lane` declarations; the script deterministically aggregates what you pass.
- `--today` makes a run reproducible; omit it for the real date.
- **Show the text output verbatim** — its columns are deterministically aligned; re-typing them
  reintroduces the drift the script exists to remove.
- **Fallback (no `python3`):** execute the reconstruction contract below by hand with grep/git,
  and say you fell back.

## Step 2 — Add the judgment a script can't

The script gives facts; you give the reading. After showing its output:

- Interpret a flag: a `⚠ Nd idle` on Implement → name the likely stall (an open gate? a blocked
  task?); an `! integrity` note → point at the drift (Summary Table vs parsed sections).
- Answer follow-ups from `--json` (which features are stale, oldest-started, most Todo) — reason
  over the data, never re-count by eye.
- The script's numbers are **canonical**. Never override them in prose; if a number looks wrong,
  that is a script bug to fix, not a value to hand-edit.

## The reconstruction contract — what `said_status.py` computes (and the by-hand fallback)

For each registry feature-id, glob `<id>*` so sub-phased specs (`<id>-<slug>.md`) and their task
logs count. Derive:

**Phase — ordered checks, first match wins.** (Order matters: a `Closed` feature also has
`Todo == 0`, so the footer is checked before the count. Never key phase on `Todo == 0` alone.)

1. `## Debrief close` footer present in a `<id>*.tasks.md` → **Closed**
2. spec + tasks exist, `Status: Todo` count `== 0`, no footer → **Delivery** — the post-Implement
   gate + debrief window (`/said:flow` names this same phase *Gates*)
3. spec + tasks exist, `Status: Todo` count `> 0` → **Implement**
4. a `<working>/<id>/scope.md` exists, no spec → **Architect**
5. no scope.md, no spec → **Scope** — append `· not started` when the working dir is absent or empty

**Task rollup.** Count `**Status:** <X>` across the tasks log: Done / Todo / Canceled / Backlog.
Progress denominator = `Done + Todo` (active work); Canceled + Backlog are shown but excluded from
the bar. If the log carries a `## Summary Table`, cross-check its rows against the parsed counts
and, on mismatch, emit a one-line **data-integrity** note (the parsed `Status:` lines win — the
table is a convenience index that can go stale).

**Gate sub-ticks** (meaningful at Delivery/Closed) — from working-dir artifacts:
`review-qa*.md`→qa · `review-ux*.md`→ux · `accept*.md`→accept · `debrief.md`→debrief-started ·
`## Debrief close` footer→debrief-done. Render `✓` present · `○` pending · `–` n/a (e.g. `ux –`
for a feature with no UI surface — absence of a UX gate is not a failure).

**Dates.** `started` = min `(YYYY-MM-DD)` across Status lines · `last task-date` = max of them ·
`git last-activity` = `git log -1 --format=%cd --date=short -- <id>*.md <id>*.tasks.md <working>/<id>/`.
`idle` = today − max(last task-date, git last-activity). `age` = today − started.

**Staleness flag.** For non-`Closed` features, `⚠ <idle>d idle` when idle exceeds the phase
threshold — default **Implement/Delivery 7d, Scope/Architect 14d** (tunable; state the value used).
`Closed` features carry no staleness. If the tree is not a git repo, say so and fall back to
in-file dates — never fabricate an activity date.

**Blockers** (cross-lane; usually empty single-lane). A task whose Approach / Out-of-scope names an
open crossing (`*-handover-*.md` with no reply / no `## Reply`) → `⛔ blocked: <task> → <crossing>`.

**Next action** — from phase: Scope → `/said:scope-refine <handoff>` (or `/said:scope-grill <id>`
if the input is thin/empty) · Architect → `/said:architect <working>/<id>/scope.md` · Implement →
`/said:impl <id>` · Delivery → the next un-run of `/said:review-qa <id>` → `/said:accept <id>` →
`/said:debrief <id>` · Closed → none.

**Report probe results honestly.** If two probes disagree (a Summary-Table row says Done, its
`## <id>` section says Todo), trust the section and say so.

## Output shapes — what the analyzer prints (and the fallback renders)

### Roster — default, no argument

A monospace block (fenced, so columns align), sorted **attention-first**:
Implement → Delivery → Architect → Scope → Closed; within a phase, most-idle first.

```
SAID status · <PROJECT> · <n> lane(s) · <today>

<ID-7>  <Phase-9>  <bar-9>  <done>/<tot>  <n Todo>  <flags>
...
Next: <cmd1> · <cmd2> · <cmd3>        ← top ≤3 actionable, phase order
legacy: <prefixes> — <one-line why, where they live>
!  <data-integrity notes, if any>
```

- **bar** = 9 cells, `█` × round(9 × done/denominator), `░` for the rest. A feature with no task
  denominator yet (Scope/Architect) renders `·········` — "no work counted," not "0% done."
- **flags** = `⚠ Nd idle` and/or `⛔ blocked: …`; `Closed` rows may show the gate ticks instead.
- Keep one line per feature. Do not list legacy features per-row.

### Deep-dive — `/said:status <feature-id>`

Normal markdown (keep `file:line` paths clickable). This is the "position in the SAID cycle" view:

- **Pipeline** — an arrow sequence with the current stop marked, e.g.
  `Scope ✓ → Architect ✓ → Implement ● → Delivery ○ → Closed ○` (`✓` done · `●` current · `○` ahead).
  Never a box-drawn diagram.
- **Delivery** line (when at/after Delivery): `review-qa ✓ · review-ux – · accept ○ · debrief ○`.
- **Tasks** — rollup (`Done N · Todo M · Canceled K`) then the open items listed:
  `<id>-<nn> · <title> · <status-date>`. Canceled/Backlog folded under a count.
- **Dates** — started · last activity · age · idle (with the threshold applied).
- **Blockers** — each open crossing and the task it holds, or `none`.
- **Next** — the exact command(s) to advance, and the key artifacts (`scope.md`, spec, tasks log)
  as clickable paths.

### Cross-lane — `/said:status --lanes`

The user verb `--lanes` means "show every lane." Resolve lanes via `/said:flow` Step 1
(declaration-first `## Lane` blocks; glob fallback), then invoke the script with one `--lane
NAME:root=…;docs=…;working=…;prefixes=…` per lane. It renders one roster section per lane under a
`lane: <name>  (<root>)` heading, with global column alignment across lanes. For a `<feature-id>`
that spans lanes, the deep-dive matches the umbrella id and its suffixed lane ids together
(`INIT-28`, `INIT-28-BE`) and labels each with its `lane:` — each carrying its own phase. (Phase is
per-lane; cross-lane `Closed`/crossing semantics stay `/said:flow`'s job — this skill reports, it
doesn't gate.)

## Rendering rules

- **No box-drawing / pseudographics** (`│ ─ ┌ └ ├ …`) anywhere. Pipelines are arrow sequences or
  nested lists; the roster is space-aligned columns in a code fence.
- **Block-glyph progress bars are fine** — `█`/`░` are data-viz marks, not diagram borders.
- One line per feature in the roster; the deep-dive may breathe.
- Prefer lists; the roster's aligned columns are the one place a monospace block earns its keep.

## Anti-patterns

- **Don't write anything.** No status file, no cached board, no `_resume.md`. Read-only, every run.
- **Don't hand-edit the script's numbers.** Its output is canonical; a wrong number is a bug to fix
  in `said_status.py`, not a value to correct in prose.
- **Don't do the mechanical work by hand when `python3` is present.** That is the variance the
  script removes. Hand-execute the contract only as the declared no-python fallback.
- **Don't auto-invoke downstream skills.** Report the `Next:` command; the operator runs it.
- **Don't key phase on `Todo == 0`.** Check footer + spec presence first (the contract's ordering).
- **Don't trust the Summary Table over the sections.** Parse `## <id>` `Status:` lines; the table
  is an index that can lie (the script emits an `! integrity` note on mismatch).
- **Don't render legacy/foreign prefixes per-row.** Collapse to the `legacy:` line.
- **Don't fabricate dates.** No git → say so, use in-file `(YYYY-MM-DD)` only.
- **Don't hardcode `docs/features` / a project prefix / a project name.** Resolve in Step 0.

## Hard exit

The skill ends at the rendered report + the `Next:` suggestion(s). It never proceeds into a phase.
