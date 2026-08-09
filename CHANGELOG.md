# Changelog

All notable changes to the SAID plugin are documented here. Format follows [Keep a Changelog](https://keepachangelog.com); the project uses semantic versioning.

## [0.4.0] — 2026-08-09

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
