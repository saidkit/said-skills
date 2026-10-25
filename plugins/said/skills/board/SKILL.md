---
name: board
description: >
  SAID board, the one read-only observe skill: where every feature sits in the SAID phase chain
  (Scope -> Architect -> Implement -> Deliver -> Closed), what is stalled or waiting, and the command
  that advances each, derived from on-disk artifacts. The local web page is the default surface;
  `--cli` prints the terminal board and `--json` the data. Triggered ONLY by "/said:board
  [<feature-id>] [--cli | --json] [--lanes] [--stale] [stop] [--port N] [--lane ...] [--connect URL]".
  NOT for driving a phase; NOT root-cause tracing ("/said:triage"); NOT lane configuration
  ("/said:setup").
---

# said:board — the SAID board

Run `flow`'s Step-1 reconstruction over **every** feature and **report**: phase, progress, what is stalled, and the command that advances each. `flow` decides and acts on one feature; this reports on all and drives nothing. One deterministic core, `said_status.py`, renders three surfaces: the web page (`serve.py`, the default), the terminal board (`--cli`) and the data layer (`--json`). The web numbers are the terminal numbers because both come from the same `analyze()`. The artifacts are the only source of truth.

## Contract — holds every run

- **Read-only.** No edits, no test runs, no downstream skill invoked. The web page is GET-only unless `--connect` opts in (below).
- **Derive, never store.** Reconstruct from artifacts each run; write no status file or `_resume.md`. The web page caches a derive only until the next explicit refresh (a full page load or the header button).
- **Script numbers are canonical.** `said_status.py` owns the counts; never override them in prose. A wrong number is a bug to fix in the script, not a value to hand-edit.
- **Loopback only.** The web server binds `127.0.0.1`, holds no credential, makes no network call of its own and proxies nothing.
- **Hard exit.** `--cli` / `--json`: end with the rendered board and a suggested `Next:` command. Web: launch (or stop) the server, report URL and pid, hand back. Never block on the server, never proceed into a phase. `Next` is copyable text, never a button that runs a `/said:` command.

## Invocation

- `/said:board` — open the web board for the current lane (launch the server, open the browser).
- `/said:board <feature-id>` — open the web board on that feature's deep-dive.
- `/said:board stop` — stop the running server.
- `/said:board --cli` — the terminal roster; `/said:board --cli <feature-id>` the terminal deep-dive.
- `/said:board --json` — the structured data layer (any view, with the same arguments).
- `--lanes` — the cross-lane board, grouped by lane: a `--cli` / `--json` view (`--lanes` alone renders it as `--cli`). The web page shows one lane at a time through its header's lane select.
- `--stale` — attention filter: only non-`Closed` features past their idle threshold. A `--cli` / `--json` argument; on the web page, the header's `stale only` toggle.
- `--port N`, `--lane ...`, `--stale-days N`, `--connect <url>`, `--todo-file <path>` — web server flags (below).

## Step 0 — Resolve conventions (declaration-first, then glob)

Never hardcode paths or id shapes. Resolve in this order, and state what resolved:

| Fact | Declaration (first) | Fallback (second) |
|---|---|---|
| Docs root, working root | a `## Lane` block's `SAID.docs-root:` + `SAID.working:` keys | `docs/features/` and `docs/working/` |
| Issued id-prefixes | `CLAUDE.md` (e.g. *"issues `PROJ-NN` only"*) | stems of `<docs>/features/*.md` |
| Id shape | a `## Lane` block's `SAID.id-shape:` key (`<PREFIX>-<NN>`, sub-phase `-<slug>`, multi-target `-<APP>-<NN>`) | regex `[A-Z]+-[0-9]+` |
| Lanes | the rows of the root's `SAID.lanes:` registry where one is declared (`--registry`); else `## Lane` blocks | single lane |

**Enumerate the registry as a union** (dedup by feature-id) — a spec-only list hides the states an operator most needs to see (scoped-but-unarchitected, reserved-but-empty). Include:

- every `<docs>/features/<id>*.md` that is not `template*` / `README` / a `*.tasks.md`, AND
- every `<working>/<id>/` directory whose name matches an issued prefix.

**Foreign / legacy prefixes** — a `<working>/<id>/` whose prefix the repo doesn't issue and which has no current spec — never render per-row; collapse to one footer line `legacy: ...`. (e.g. a `LEGACY-01..10` block whose prefix the repo no longer issues.)

**Lanes default to one.** Multi-lane: where the root declares a `SAID.lanes:` registry, run `python3 <skill-dir>/said_status.py --registry --root <root>`, echo its count (on `refused:` stop and show the reason; `/said:setup` reports the line), and pass each printed `TOKEN:root=<root>` row as one `--lane` (add `;prefixes=...` where needed); only with no registry, read each `## Lane` block (`/said:flow` Step 1) and pass one `--lane NAME:root=...;prefixes=...` per lane. These values become the flags of every surface below.

## Step 1 — Render the asked surface

`said_status.py`, `serve.py` and their assets sit beside this SKILL.md. When `python3` is present, run them — never reconstruct by hand. The web page has no fallback: with `python3` or `serve.py` missing, say so and stop; never hand-render a web page.

**`--cli` and `--json`** — run the analyzer:

```bash
python3 <skill-dir>/said_status.py \
  --root <repo-root> --docs-dir <docs>/features --working-dir <working> \
  [--prefixes PROJ,LEGACY] [--legacy-prefixes LEGACY] [--today YYYY-MM-DD] \
  [--lane NAME[:root=...;docs=...;working=...;prefixes=...;legacy=...]]... [--project <label>] \
  [<feature-id>] [--stale] [--json]
```

- No `<feature-id>` -> roster, `<feature-id>` -> deep-dive, `--stale` -> attention filter, one `--lane` per lane -> cross-lane board, `--json` -> the data layer (reason over it; don't re-derive by eye).
- **Omit `--prefixes` / `--legacy-prefixes`** and the script infers the active set (a prefix is active if any id has a spec or `scope.md`); pass them when `CLAUDE.md` states the issued set, to be exact. `--today` makes a run reproducible; omit it for the real date.
- **Show the text output verbatim** — columns are deterministically aligned; re-typing reintroduces the drift the script exists to remove.
- **No `python3`?** Execute the reconstruction contract below by hand with grep/git, and say so.

**The web page (default)** — launch or stop the server:

```bash
python3 <skill-dir>/serve.py --root <repo-root> [--prefixes PROJ,LEGACY] \
  [--legacy-prefixes LEGACY] [--lane NAME:...]... [--today YYYY-MM-DD] [--stale-days N] \
  [--port <n>] [--no-open] [--connect http://localhost:3000] [--todo-file docs/todo.md]
python3 <skill-dir>/serve.py stop [--port <n>]
```

- On launch it binds `127.0.0.1:<port>`, prints `said:board, <url>/, pid <pid>`, writes a state file (`$TMPDIR/said-board.json`) and opens the browser. With a `<feature-id>`, pass `--no-open` and open the printed URL (it ends in `/`) with `#<feature-id>` appended: the page opens on that feature's deep-dive (an unknown or malformed id opens the board as usual).
- **Report the URL and pid**, then hand back; the server runs until stopped. `stop` reads the state file (or falls back to the port's listener) and stops only that server; report what was stopped. Prefer `/said:board stop` over a manual `pkill`.
- **`--connect <url>`** opts in to a local companion app (loopback URLs only): the page then emits the app's embed, cache-fed comment badges, a Backlog view of the local todo file (`--todo-file`, default `docs/todo.md`) and two local-file writes (`POST /connect`, `POST /todo`), each behind the Origin check, the CSRF token, the JSON-plus-custom-header rule and the opt-in. Without the flag none of it exists. The page's connect form saves which app it talks to, and a later launch with no flag reuses that saved app. A connected board prints and opens a `localhost` URL, not `127.0.0.1`, so the app's session cookie is sent. The embed contract, the badge cache and the write controls are specified in the board's design record.

## Step 2 — Add the judgment a script can't

The script gives facts; you give the reading. After showing its output:

- Interpret a flag: `⚠ Nd idle` on Implement -> name the likely stall (an open gate? a blocked task?); `! integrity` -> point at the drift (Summary Table vs parsed sections); `waiting:` -> name the operator question it waits on.
- Answer follow-ups from `--json` (stalest, oldest-started, most Todo) — reason over the data.

## The reviewer-set enforcement gate (L2 / L4)

Separate from the read-only board, `said_status.py` exposes an **exit-coded** enforcement mode — `--reviewer-gate` — that validates a lane's declared `SAID.reviewers:` set (each Checker's L1 verdict header + a deterministic-family recompute) and exits non-zero on a failing set. `/said:board` never invokes it; the gates do. No pre-close hook runs it automatically: the plugin's only hook is a `SessionStart` re-anchor that injects context and blocks nothing, and no artifact claims the close is auto-blocked; the live-close block stays the gates' own rule.

## Reconstruction contract — what `said_status.py` computes (and the by-hand fallback)

Per registry feature-id, glob `<id>*` so sub-phased specs (`<id>-<slug>.md`) and their task logs count. Derive:

**Phase — ordered checks, first match wins.** Order matters: a `Closed` feature also has `Todo == 0`, so check the footer before the count. Never key phase on `Todo == 0` alone.

1. `## Debrief close` footer in a `<id>*.tasks.md` -> **Closed**
2. spec + tasks, `Status: Todo` count `== 0`, no footer -> **Deliver** — the post-Implement gate + debrief window (`/said:flow` names this same phase *Deliver*)
3. spec + tasks, `Status: Todo` count `> 0` -> **Implement**
4. `<working>/<id>/scope.md` exists, no spec -> **Architect**
5. no scope.md, no spec -> **Scope** — append `, not started` when the working dir is absent or empty

**Task rollup.** Count `**Status:** <X>` across the tasks log: Done / Todo / Canceled / Backlog.
Denominator = `Done + Todo` (Canceled + Backlog shown but excluded from the bar). If a `## Summary
Table` exists, cross-check its rows vs the parsed counts; on mismatch emit a one-line **data-integrity** note — parsed `Status:` lines win, the table is a convenience index that can go stale.

**Gate sub-ticks** (meaningful at Deliver/Closed), from working-dir artifacts, a run's `-F<NN>.md` report excluded: `review-qa*.md`->qa, `review-ux*.md` or `review-<checker-id>-<id>*.md` of a Checker the lane's `## Lane` block declares in `SAID.reviewers:`->ux (any verdict, PASS or FAIL: presence only; validation is the reviewer gate's), `accept*.md`->accept, `debrief.md`->debrief-started, `## Debrief close` footer->debrief-done. Render `✓` present, `○` pending, `–` n/a (`ux –` for a no-UI feature — absence of a UX gate is not a failure).

**Waiting on an operator question.** A separate axis from the gate ticks: a tick shows only that a file is present, never that it passed. A feature waits on one of two derived sources, the first that applies:
1. The accept file: the newest `accept-*.md` in `<working>/<id>/` by modification time (a run's `-F<NN>` report excluded) whose last `Verdict:` line, bulleted (`- Verdict: ...`) or not, outside a code fence, reads exactly `MANUAL-PENDING` -> reason `accept MANUAL-PENDING`. The `accept` tick stays present; the wait says it has not passed.
2. A `**Blocked-on question:** <id>` marker in the tasks log, judged by the hold gate's own rule (`review-qa/hold-gate.py`), never re-derived here: the marker waits until a `## Lifted holds` record lifts it by citing a ruling in the work's rulings list `<working>/<id>/rulings.md` that passes the gate's checks. The reason is `question <id>`, followed in parentheses by the gate's reason when the marker is malformed or old-spelled, its task closed without a lift, or its lift fails a check; with a lift record but no rulings list the lift shows as unverified. One waiting marker is reported: a malformed or old-spelled marker first, else the first unlifted marker in the log. The list holds one ruling per line, `- WR-<seconds> - <who>, <status>: <text>`, an optional `[<links>]` at the end, `<status>` one of `pending`, `landed`, `rejected`, `superseded`, and a `landed` or `superseded` line may end ` -> <target>`.
Render the reason as `waiting: <reason>` in the feature's roster flags and as `Waiting <reason> (operator question open)` in the deep-dive. `--stale` filters on idle only, so a waiting feature that is not idle is not in it.

**Fast-track runs.** A `## Fast-track F<NN>` block in the tasks log is a run, never a task: it matches no task heading and changes no count. Its listed set is the ids on its `tasks:` line plus every task carrying `**Fast-track:** F<NN>`; it is open while its `closed:` line is empty. For each open run the deep-dive prints `fast-track open: F<NN>, <n> tasks`, and every roster, `--stale` included, prints `<feature-id> fast-track open: F<NN>, <n> tasks`: an open run is always an attention item. Only tokens shaped like a task id (`PROJ-01-03`) on the `tasks:` line count. A run's reports (names ending `-F<NN>.md`) never tick a feature-level gate, never raise the accept wait and never move the `Next` action.

**Dates.** `started` = min `(YYYY-MM-DD)` across Status lines, `last task-date` = max, `git last-activity` = `git log -1 --format=%cd --date=short -- <id>*.md <id>*.tasks.md <working>/<id>/`.
`idle` = today − max(last task-date, git last-activity), `age` = today − started.

**Staleness.** Non-`Closed` only: `⚠ <idle>d idle` when idle exceeds the phase threshold — default
**Implement/Deliver 7d, Scope/Architect 14d** (tunable; state the value used). `Closed` carries no staleness. No git -> say so, fall back to in-file dates; never fabricate an activity date.

**Blockers** (cross-lane; usually empty single-lane). A task whose Approach / Out-of-scope names an open crossing (`*-handover-*.md` with no reply / no `## Reply`) -> `⛔ blocked: <task> -> <crossing>`.

**Next action — by phase.** Scope -> `/said:scope-refine <handoff>` (or `/said:scope-grill <id>` if the input is thin/empty), Architect -> `/said:architect <working>/<id>/scope.md`, Implement -> `/said:impl <id>`, Deliver -> the next un-run of `/said:review-qa <id>` -> `/said:review-ux <id>` -> `/said:accept <id>` -> `/said:debrief <id>`, Closed -> none.

**On probe disagreement**, trust the `## <id>` section over the Summary Table, and say so.

## Output shapes (`--cli`)

### Roster — default, no argument

A monospace block (fenced, so columns align), sorted **attention-first**: Implement -> Deliver -> Architect -> Scope -> Closed; within a phase, most-idle first.

```
SAID status, <PROJECT>, <n> lane(s), <today>

<ID-7>  <Phase-9>  <bar-9>  <done>/<tot>  <n Todo>  <flags>
...
Next: <cmd1>, <cmd2>, <cmd3>        <- top ≤3 actionable, phase order
legacy: <prefixes> — <one-line why, where they live>
!  <data-integrity notes, if any>
```

- **bar** = 9 cells, `█` × round(9 × done/denominator), `░` for the rest. No denominator yet (Scope/Architect) -> `,,,,,,,,,` — "no work counted," not "0% done."
- **flags** = `⚠ Nd idle`, `waiting: <reason>` and/or `⛔ blocked: ...`; `Closed` rows may show the gate ticks instead.
- One line per feature. Never list legacy features per-row.

### Deep-dive — `/said:board --cli <feature-id>`

Markdown (keep `file:line` paths clickable) — the "position in the SAID cycle" view:

- **Pipeline** — an arrow sequence with the current stop marked:
  `Scope ✓ -> Architect ✓ -> Implement ● -> Deliver ○ -> Closed ○` (`✓` done, `●` current, `○` ahead).
  Never a box-drawn diagram.
- **Deliver** line (at/after Deliver): `review-qa ✓, review-ux –, accept ○, debrief ○`.
- **Tasks** — rollup (`Done N, Todo M, Canceled K`), then the open items:
  `<id>-<nn>, <title>, <status-date>`. Canceled/Backlog folded under a count.
- **Dates** — started, last activity, age, idle (with the threshold applied).
- **Blockers** — each open crossing and the task it holds, or `none`.
- **Next** — the exact command(s) to advance, and the key artifacts (`scope.md`, spec, tasks log) as clickable paths.

### Cross-lane — `/said:board --cli --lanes`

Resolve lanes per Step 0, then run the script with one `--lane NAME:root=...;docs=...;working=...;prefixes=...` per lane. One roster section per lane under a `lane: <name>  (<root>)` heading, columns aligned across lanes. A `<feature-id>` spanning lanes matches the umbrella id + suffixed lane ids together (`PROJ-01`, `PROJ-01-BE`), labelling each with its `lane:` and its own phase. (Phase is per-lane; cross-lane `Closed` / crossing semantics stay `/said:flow`'s job — this skill reports, it doesn't gate.)

## Rendering rules

- **No box-drawing / pseudographics** (`│ ─ ┌ └ ├ ...`) anywhere. Pipelines are arrow sequences or nested lists; the roster is space-aligned columns in a code fence.
- **Block-glyph progress bars are fine** — `█`/`░` are data-viz marks, not diagram borders.
- One line per feature in the roster; the deep-dive may breathe. Prefer lists.

## Anti-patterns

- **Don't do the mechanical work by hand when `python3` is present** — that's the variance the script removes. Hand-execute the contract only as the declared no-python fallback.
- **Don't auto-invoke downstream skills.** Report the `Next:` command; the operator runs it.
- **Don't key phase on `Todo == 0`.** Check footer + spec presence first (the contract's ordering).
- **Don't trust the Summary Table over the sections** — the script emits an `! integrity` note on mismatch.
- **Don't render legacy/foreign prefixes per-row.** Collapse to the `legacy:` line.
- **Don't fabricate dates.** No git -> say so, use in-file `(YYYY-MM-DD)` only.
- **Don't add a write route to the web page without all four controls, or one that is on without `--connect`.** Everything else is GET.
- **Don't make the integration default-on.** A plain launch is byte-for-byte the read-only board: no script tag, no mount points, no extra routes.
- **Don't fetch badge counts.** They come from the board's local cache file, so they are instant and survive the app being down.
- **Don't give the server a credential, a network call, a non-loopback bind, a build step or a render-blocking CDN `<script>`.** htmx is `defer`, daisyUI a plain stylesheet, the server stdlib-only.
- **Don't reimplement `analyze()`.** Every surface reads `said_status.py` beside this file.
- **Don't hardcode `docs/features` / a project prefix / a project name.** Resolve in Step 0.
