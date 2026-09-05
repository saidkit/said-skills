# Changelog

All notable changes to the SAID plugin are documented here. Format follows [Keep a Changelog](https://keepachangelog.com); the project uses semantic versioning.

## [0.5.0] — 2026-09-05

The `doc` lane conforms to the gates every lane runs. **Breaking** for a lane that carried a
`docs/qa/doc-gate.md` bar file.
- **Changed:** `doc-gate.py` — `--soft <rule>` / `--off <rule>` compose the effective rule set
  (every rule off is refused); the bar file, `--bar`, `--init`, `--force`, `--explain`,
  `--allow-exclaim` and `--refs-soft` are removed; finding lines and the no-argument run are unchanged.
- **Changed:** `impl` and `review-qa` resolve a `doc` lane's umbrella through a doc terminal in the
  command-resolution chain — `SAID.commands: doc-gate` is a plugin-provided verb expanded to the
  shipped engine (pipefail, a per-invocation log). review-qa's doc-specific carve-outs are gone; a
  semantic checklist row is discharged by the declared reviewer's recorded verdict.
- **Changed:** `review-ux` has two arms — the web arm (Steps 1–2) and a doc arm that runs the plugin's
  editorial reviewer per task and per feature against the lane's QA checklist, recording an inline
  degradation when it cannot spawn; `impl`'s Phase C trigger reads "an agent-form Checker for the medium".
- **Changed:** `accept` indexes `review-<checker-id>-*.md`, lists an editorial verdict among recorded
  evidence, and reads an absent feature `Surface:` as the lane's medium; `said` records a doc Eval at
  Deliver (`QA-eval-<id>.md`, no spawn); the `Step 0.SC` block (impl, architect, add-task) has a
  medium-neutral trigger (SC-STUB v2).
- **Changed:** the `doc-editorial` agent reads the lane's QA checklist (its editorial context and
  semantic rows) instead of a brief, and names its feature-scope verdict.
- **Docs:** the README describes the doc lane in the umbrella-plus-rows vocabulary.

## [0.4.0] — 2026-09-04

- **Added:** the `doc` lane's mechanical gate ships inside the plugin (`skills/review-qa/doc-gate.py`)
  and runs natively for a `surface: doc` lane; `said:retrieval` (a read-only precedent sweep at scope).
- **Added (withdrawn in 0.5.0):** a per-lane bar file `docs/qa/doc-gate.md` with `--bar`, `--init`,
  `--explain`.
- **Changed:** the `doc-editorial` agent names its L1 verdict artifact and its optional inputs.

## [0.3.7] — 2026-09-04

- **Fixed:** the reviewer gate validates the Checker that RUNS — the checkers-dir defaults to the
  plugin's own `agents/`, resolved from `said_status.py`'s install location, never a per-project copy;
  a duplicate `said-checker:` id is surfaced, never last-writer-wins.

## [0.3.6] — 2026-08-29

**`said:board`** — loading feedback, header restructure, and real-repo fixes:
- **Added:** a global loading indicator — the header logo ticks in 45° steps while any request is in
  flight (delay-before-show + min-visible so it never flashes on cached navigation), replacing the
  refresh-icon spin. The page shell now renders instantly from config and streams data into fragments,
  so a large repo no longer paints a blank page while the first derive runs.
- **Changed:** the header is restructured into three zones — identity + controls left, List|Kanban
  centred, options right; the refresh icon is now a labelled "Update" button.
- **Fixed:** the deep-dive showed no tasks for collapsed task-ids (e.g. `PROJ01-LANE-01`) — the
  analyzer's id grammar now accepts both the collapsed and dashed id shapes, and recognises a
  `Superseded` status.
- **Fixed:** the board re-ran the expensive derive on every interaction — it now caches until an
  explicit refresh (a full page load or the Update button).

PRD: `docs/specs/board/REQUIREMENTS.md`.

## [0.3.5] — 2026-08-29

**`said:board`** — multi-lane usability + stability:
- **Changed:** shows one lane at a time via a header selector (persisted across reloads), replacing the
  stacked all-lanes view; auto-poll removed — status refreshes on a full page load or an explicit
  refresh button. Amends the board's re-derive/refresh contract (read-only re-derive behind a
  single-flight + short-TTL guard; an explicit refresh forces a fresh derive).
- **Fixed:** the board wedged unreachable under concurrent repo git activity — an uncached, per-request
  `git`-backed status call collapsed under the board's own polling once `.git/index.lock` was
  contended. Fixed by the guard above plus running the read-only `git` calls with
  `core.optionalLocks=false` and a bounded timeout (degrading to task-log dates), so a status read
  never waits on a user-held index lock.
- **Fixed:** `said:board stop` sometimes terminated the browser — the port lookup that found the server
  also matched connected clients (an open dashboard tab). `stop` now signals listeners only, and trusts
  a recorded server pid only when it is a current listener.

PRD: `docs/specs/board/REQUIREMENTS.md`.

## [0.3.4] — 2026-08-09
Unified phases names - "Gates"/"Delivery" -> "Deliver" across all skills
Unified gates - added "review-ux" next to "review-qa"

**Fixed — the HITL livelock (`said:said` + `said:flow`).** An owed operator decision (a UAT/aesthetic
sign-off) under `/goal` no longer busy-waits: `/goal`'s evaluator is binary, so a `goal: stop` does not
end the loop — the skills now **announce the block once** (owed verdict + how to unblock: reply, or
`/goal clear`) and then **hold** on every re-fire — no re-done work, no faked verdict, no repeated
"still waiting". Corrects the earlier "`stop` ends the loop" wording (`stop` is surfaced, not enforced).
PRD: `docs/specs/said/REQUIREMENTS.md` (W16/D-8).

## [0.3.3] — 2026-08-09

**Added — `said:said`.** Single-feature SAID orchestrator: drives ONE feature through the full phase
chain (Scope → Architect → Implement → gates → Debrief) in one session, invoking the real `said:*`
skill at each phase and self-publishing a `goal: done|continue|stop` control line every turn — so a
plain `/goal implement <id> as said!` runs it to closure with no hand-written condition. The
single-lane twin of `said:flow`; backs the `said!` operator macro (whose closure signal was previously
a debrief *file* footer, invisible to `/goal`'s transcript-only evaluator). Route precondition
redirects a ≥2-lane feature to `said:flow`; main-context and depth-safe (never spawns to decide).
Reconstructs phase by inspection (re-entrant across compaction); omission is never silent (→
`goal: stop`). A **Step-0 request classifier** picks the entry (RESUME · SHORT · NEW · TINY · DONE) so a
bug/tweak/follow-up that fits an existing feature takes the short `triage → add-task → impl → gates`
path (Scope+Architect skipped), and a new ask on a Closed feature is never a silent `goal: done`. PRD:
`docs/specs/said/REQUIREMENTS.md`.

## [0.3.2] — 2026-08-09

**Added — `said:retrieval`.** Precedent/decision-record search, relocated from `magic:lumos` — it is
decision-investigation inside the SAID setup, not a context-hygiene macro, and was already built
against SAID's artifact layout. Before proposing a default, accepting a spawned-agent's framing, or
answering "what's the default for X", it exhausts five precedent sources in order (`CLAUDE.md` ·
memory · ADRs · prior working dirs · probe/wire captures) and reports per-source with citations.
Proactive (fires at `§D` walks, "did we decide this before?", about-to-propose-a-default) and
directly invocable via `/said:retrieval` (operator alias `lumos!`). Read-only. Each run closes with a
**loop-ready status signal** — `coverage` (complete/partial) + `goal` (achieved/open/none) +
`retrieval complete: yes|no` — so a driver (or a reserved `--exhaustive` loop-until-dry sweep) can
decide whether another pass is worth it. Self-contained SKILL.md.

## [0.3.1] — 2026-08-08

**Fixed — `said:status` dot-only working dirs.** The empty-dir probe counted any directory entry
as work-in-progress, so a reserved working dir holding only a dotfile (`.gitkeep`, `.DS_Store`)
misread as `Scope · scope pending` instead of `Scope · not started`. It now ignores dotfiles when
probing for content. (This also lets the private eval fixture keep its reserved-but-empty dirs as
`.gitkeep` placeholders — empty dirs don't survive a `git clone` — without shifting their golden
classification.)

## [0.3.0] — 2026-08-08

Two observability skills join the engine: a read-only status board in the terminal and its
local-web sibling. Both are derive-never-store reporters — they reconstruct every feature's
position in the SAID phase chain from on-disk artifacts on each run, and drive nothing.

**Added — `said:status`.** Terminal status board: a roster, a single-feature deep-dive, or a
cross-lane board, derived from the same Step-1 reconstruction `said:flow` uses. A bundled
`said_status.py` owns the mechanical derivation (enumerate → classify phase → count `Status:`
lines → dates + git idle → gate files) and emits JSON or rendered text, deterministic under
`--today`; the skill adds the judgment a script can't. Read-only — never writes, never invokes a
downstream skill.

**Added — `said:board`.** The browser sibling of `said:status`: a self-contained stdlib server
(htmx + daisyUI from a CDN, GET-only, `127.0.0.1`-only) that imports `said:status`'s `analyze()`
and serves List + Kanban views with a click-through deep-dive. One deterministic core, two
surfaces — the web numbers match the terminal board exactly. `/said:board stop` kills it.

Both ported from the `hypercommand` prototype. Their evaluation package (SUT-by-role harness,
hermetic fixture, five-verification EVAL) and design docs live in the private `said-skills-docs`
companion, not in the shipped plugin.

## [0.2.0] — 2026-08-03

`said:flow` — the multi-lane orchestrator — gains an assertable stop condition. Found by a
live post-mortem: a two-lane feature closed with one lane's Phase-3.5 gates and Phase-4
debrief never run, while the resume pointer reported the feature complete.

**Added — `said:flow` Output contract.** Every invocation now ends with a per-lane phase table
and a literal `feature closed: yes|no`. `yes` is permissible only when every lane reads
`Closed`, and a lane is `Closed` only when its own `debrief.md` exists *and* its task log
carries a `## Debrief close` footer. The skill is instructed to contradict an outer
orchestrator that has already declared the work finished.

**Fixed — per-lane feature-id.** Step 1 discovered a lane's task log and then discarded its
id, so downstream `/said:debrief`, `/said:review-qa`, `/said:accept` and `/said:impl` calls
used the umbrella id and silently addressed the wrong lane's log. Step 1 now records the id
(the `*.tasks.md` stem minus `.tasks` — `PROJ-01-BE`, `PROJ-02-BE-widgets`), and every later
invocation targeting a lane uses that lane's own id.

**Fixed — rule 7 under-specified.** *"per-lane review-qa → accept → debrief"* was satisfiable
by one pass over one lane. It now iterates explicitly, names the per-lane id, and is not
discharged until every lane's phase probe reads `Closed`.

Root cause the release addresses: nested under an outer planner, `said:flow` was invoked once
as a single plan step, which demoted its re-entrant loop to a subroutine and made every rule
it would have enforced on later passes unreachable. Pairs with `magic` 0.2.0, which teaches
the planner to drive loop-shaped skills to their stop condition.

**Added — lane discovery by declaration.** Step 1 now reads a `## Lane` block from each
candidate tree's `CLAUDE.md` — declared docs root, task-log path, working dir, task-id shape,
ADR prefix — and enumerates from a repo root's lane registry where one exists. The previous
glob (`docs/features/*.tasks.md` + `docs/working/<id>/`) is retained as a **fallback**, so
projects with no declaration are unaffected.

Why: the glob encodes one directory convention and returns nothing, silently, for a lane
shaped differently. A lane keeping its task logs at `docs/wip/<feature>/*.tasks.md` was
invisible for an entire feature, and its work got absorbed into a neighbouring lane's task by
default rather than by decision. Recorded under Known limits so the fallback is not later
mistaken for the primary path.

**Clarified — a lane is not a repo.** The precondition read "spans ≥ 2 lanes" without defining
a lane, while the skill's own fork preconditions separately reasoned about *mounts*. It now
reads **≥ 2 task logs, not ≥ 2 repos**: a lane owns a full SAID cycle, a mount is where code
lands, and one feature may change several mounts and stay single-lane. The `flow!` macro in
`magic`'s `docs/operator-macros.md` carries the matching wording.

## [0.1.0] — 2026-06-23

Initial public release — the stack-agnostic SAID engine.

### Added
- 10 skills: `said:scope-grill`, `said:scope-refine`, `said:architect`, `said:add-task`, `said:impl`, `said:review-ux`, `said:review-qa`, `said:accept`, `said:debrief`, `said:triage`.
- 3 subagents: `scope-refine-agent`, `scope-audit`, `review-ux-agent`.
- Marketplace-of-one (`saidkit`) — install via `claude plugin marketplace add saidkit/said-skills` then `claude plugin install said@saidkit`.
- Adoption guide (`guides/adoption-guide.md`) + starter contract (`starters/README.md`) for the engine + per-stack-starter model.

## [0.1.1] - 2026-07-30

Added Flow skill - a cross-lane orchestrator for multi-repo setup of several said-* sub-projects.
