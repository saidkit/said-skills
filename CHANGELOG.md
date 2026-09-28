# Changelog

All notable changes to the SAID plugin are documented here. Format follows [Keep a Changelog](https://keepachangelog.com); the project uses semantic versioning.

## [0.19.0] — 2026-09-27

The context checkpoint's statusline becomes a one-step, consented install that survives plugin updates, and a missing one is announced instead of silent.

- **Added:** `hooks/said-statusline.sh` -- a version-stable statusline entry point that runs the newest installed plugin version's statusline script (a release outranks its own pre-release); with no installed plugin it prints the model name and exits 0.
- **Added:** `/said:setup statusline` -- a consent-gated writer (`setup_statusline.py`): shows the change, then backs up `settings.json`, copies the wrapper to `~/.claude/said-statusline.sh`, sets `statusLine` only, re-parses and restores on failure. `--fix` offers the same step; the read-only ledger reports a `statusline` row (ok / STALE / ADVISORY, never BLOCKER).
- **Changed:** `said:setup` governs lane configuration plus exactly one environment item, the statusline install; two writer paths (`--fix`, `statusline`), both consent-gated.
- **Added:** the re-anchor hook prints one line `context checkpoint inactive: run /said:setup statusline` when the session has no `context.json` and the user settings name no statusline script.
- **Changed:** `said`/`flow` -- when the context check is skipped for a missing `context.json`, the first skip in a session prints one line `context checkpoint inactive: run /said:setup statusline`, then proceeds (never a stop, never a `goal:` line).
- **Added:** README `## Hooks` section with the statusline install.

## [0.18.0] — 2026-09-27

A session boundary is a data boundary: the engine sheds inherited context at phase boundaries instead of carrying a build session into Deliver, and a debrief resumes instead of re-running.

- **Added:** `said`/`flow` read the session's `context.json` at Implement->Deliver, before `debrief` and at every lane rotate; above `SAID.context-checkpoint:` (optional lane key, default 300000 input tokens) they print a `CONTEXT-CHECKPOINT` stop -- an operator action (`/clear`, then re-issue the directive), announced once and held under `/goal`, never an owed decision. A Deliver resume starts at the first gate without a recorded pass.
- **Added:** shipped hooks -- a `SessionStart` re-anchor (`clear|compact` only, silent outside a `## Lane` cwd) that prints the lane's SAID status and the un-closed think-protocol leaves from disk, and a statusline script that writes `context.json`. Both auto-register with the plugin.
- **Added:** `debrief` Step 0 -- resume from an approved-not-applied row, a single-run guard keyed on position below the last close footer (a reopen proceeds, a re-run stops), scope-by-risk over the delta since that footer; the close footer carries `Scope:` and `Resumed:`.
- **Changed:** the judgment agents `scope-refine-agent` and `editorial-reviewer` pin `model: inherit` (the session's model; a caller may override), mechanical checkers keep their pins.
- **Added:** `SAID.context-checkpoint:` declared in `lane-schema.json` and the README's `## Lane` key list.

## [0.17.0] — 2026-09-22

Gate-independence hardening (SAID-22): no said Deliver/review gate is satisfiable by builder-written text -- every gate is mechanical/independent, or explicitly documented as an agent-side judgement. Extends the SAID-21 principle to three remaining gates.

- **Changed:** `review-ux` no longer pre-clears a rule PASS from the task's `### Fix` claims -- the builder-text skip-list is dropped, so `R-GATE-*` resolves only from the skill's own independent gate re-run (an unrunnable gate surfaces FAIL/BLOCKED, never a builder-claimed PASS).
- **Added:** `earned-rules.py check` resolves a cited rule's linked record on disk -- a present-but-unresolvable cited link is WARN before the contract date and FAIL on-or-after (pivoting on the task's close date); a no-link cited rule is WARN; "resolves" follows symlinks from the lane root, not git-committed-reachability. Whole-block link-health is advisory in `count`, never gating.
- **Added:** every `docs/qa/feature-qa-checklist.md` row carries an explicit independence class (mechanical / presence-only / documented-agent-side), asserted fail-closed by the review-qa eval; `R-QA-07` is documented presence-only.

## [0.16.0] — 2026-09-22

The anti-self-default backstop (SAID-21, socket 4): a decision a task *depends on* is now visible and attribution-checkable, so an autonomous builder under a blanket grant cannot self-default it and build the dependent work.

- **Added:** a task carries a write-once `**Blocked-on decision:** <id>` marker; its resolution is an append-only `## Decisions` ledger record (`- <id> resolved-by: user@<turn> -- "<verbatim quote>" -- <date> [supersedes: <prior>]`), authored by `architect` and `add-task` (explicit, never inferred) and written only by a main-context resolve step.
- **Added:** `decision-gate.py`, a bundled **structural** checker — it PASSes only when the ledger record cites a user-role turn with a verbatim substring quote, a basis not in the self-default deny-list (grant / standing-autonomy / default / assistant / subagent / arm), postdating the marker; else HOLD. The semantic "decides, not merely mentions" check stays agent-side.
- **Added:** `impl` blocks a marked-and-unresolved task at start and at close (returning it as an owed item, coining no marker); `said`/`flow` emit `OPERATOR-DECISION-HELD` and hold; `status`/`board` derive a "waiting on decision `<id>`" axis from the durable marker + ledger (derived, never stored).
- **Added:** a `decision-gate` eval package — a RED reproduction of a grant-basis self-default holding, negative controls (operator-cited, named-class, no-marker, legacy), and a documented `misattributed-cite` limit (structural PASS, agent-side FAIL).

## [0.15.0] — 2026-09-22

The owed-operator-decision fuse (SAID-21): a decision the engine reserves for the operator is announced once, then held — never settled by an autonomous builder and rubber-stamped by later gates.

- **Added:** the fuse's three sockets — **routing** (an owed decision emits `OPERATOR-DECISION-HELD` on the `goal: stop` line and holds, in `said`/`flow` and the `scope-refine` §D stop-points), **attribution** (`architect`'s preflight now requires §D *resolved with an operator-attributed record* — cite-and-verify, not merely empty), and **derivation** (a `status`/`board` "waiting on operator" axis derived from the recorded accept verdict, never stored).
- **Added:** `impl` main-side decisions (unsatisfiable Approach, mid-flight scope-creep, soft-finding defer) no longer relax under a blanket autonomy grant — they classify as owed and hold/return; and `said` consumes a **named** advance decision only for its named class (a blanket grant never covers an owed decision).
- **Added:** `accept` classification is un-gameable — a `mechanical`/`recorded-probe` label counts only if its evidence-source resolves, else it downgrades to `manual` and holds; `debrief` holds the close on a could-not-run reviewer-gate (distinct from a ran-and-FAILed reviewer); `scope-grill` blocks up-front when run with no operator to answer its Q&A.
- **Added:** eval packages (characterization harnesses) for `status` and `debrief`, which previously shipped none.

## [0.14.0] — 2026-09-16

Completeness projection hardening (nested-container stack + attribute-name collision) and a `dir:`-lane `reuses:` broken-link check. All three make the gate stricter — a surface that previously shipped a green PASS may now correctly FAIL.

- **Fixed (stricter gate, all lanes):** the element-projection loop tracked a single active-container depth, so on a unit with nested containers (an outer container whose items each open an inner container, then sibling leaf items) a dedent past an inner container swallowed every sibling leaf item after the first nested one — a whole class of elements shipped green (they passed vacuously). The loop now uses a container **stack** that restores the enclosing container on a dedent, so those sibling leaf items project and gate.
- **Fixed (stricter gate, all lanes):** a keyed line that is a **direct child of a container** but whose key collides with a declared attribute name was dropped before projection and silently un-gated. The attribute-set skip is now **context-aware** — it applies only to a key nested under a leaf element (a real attribute group); a direct container child, or a field under a grouping, projects. Declared scaffolding (`not-elements`) still skips at any depth, and the attribute-group projection is preserved.
- **Added (`dir:` unit-home lane):** the completeness check now resolves a `reuses: <ID>` attribute value against `<lane-root>/<unit-home>/<ID>.md` — a dangling reference (the reused unit's durable does not exist) is a broken-link FAIL. Resolution spans **any** lane-wide durable (a reused unit's home is normally a different feature), is single-ID, and the `<ID>` passes the same portable-id guard as the `units:` ids. An `inline` lane is unaffected.

## [0.13.0] — 2026-09-16

Durable-as-source-of-truth for a `dir:` unit-home lane: the per-unit durable spec, not the `toc.md` mirror, is what the completeness check gates, and `uxtoc` stops duplicating the durable bodies into the `toc.md`.

- **Changed (BREAKING for a `dir:` unit-home lane):** the completeness check now derives DESIGNED by parsing each declared durable spec `<lane-root>/<path>/<ID>.md` **directly** (the source of truth), instead of the `toc.md` mirror. The `toc.md` on a `dir:` lane supplies only the manifest — the `grammar:` stamp, the sealed `units:` line, and the `## <unit> <ID>` headers it cross-checks — so a durable and a stale `toc.md` can no longer disagree about the design. Each declared durable must **head its own unit id** (a copied / renamed / mis-levelled / empty durable answering for another unit FAILs); this identity check replaces the former lane-wide orphan sweep, which is **removed** (a `dir:` directory is commonly shared across features, so a durable this feature never declared is a sibling's, not this feature's orphan). The missing-durable (broken-link) direction is unchanged. An `inline` unit-home lane is unaffected (it still parses `toc.md`).
- **Changed (`uxtoc`, `dir:` unit-home lane):** `uxtoc` now emits a **thin-index `toc.md`** on a `dir:` lane — the front matter, the sealed `units:` line, and one `## <unit> <ID> - <title> -> <unit-home>/<ID>.md` header-with-pointer line per unit, with **no container bodies** (the body lives once, in the durable). An `inline` lane still emits the full outline. **No functional migration required** — the 0.13.0 gate reads the durables, not the `toc.md` bodies, so a pre-existing full-body `dir:` `toc.md` still passes; re-emit with `uxtoc` when convenient to drop the now-redundant duplicated bodies.
- **Fixed:** the unit-header projection is header-level-aware — a durable parsed directly heads its unit at H1 (`# <unit> <ID>`), while a `toc.md` / inline outline heads it at H2 (`## <unit> <ID>`); an ordinary H2 subheading inside a durable is now treated as subordinate content and no longer resets the unit context (it previously false-FAILed a valid durable).

## [0.12.0] — 2026-09-15

Completeness durable-spec resolution for a `dir:` unit-home lane, plus emit-time and under-specification signals.

- **Added (BREAKING for a `dir:` unit-home lane):** on a lane whose grammar declares `unit-home=dir:<path>`, the completeness check now resolves the per-unit durable spec `<lane-root>/<path>/<ID>.md` for every declared unit — a missing one FAILs (broken-link), an orphan durable file FAILs. The **declared unit set is read from a sealed `units: <ID1>;<ID2>;... (count: N)` front-matter line `uxtoc` now stamps** into `toc.md` (read explicitly, never inferred from prose; `count`-sealed; every element-projecting unit and every listed id cross-checked against the outline). **A `dir:` lane must re-emit its `toc.md` with `uxtoc`** so the line is present (absent → FAIL). An `inline` unit-home lane is unaffected (no `units:` line needed). Presence-only, so a hand-edited durable never fails the gate (no-seal-safe).
- **Added:** `uxtoc` warns at emit time on a missing/orphan durable spec (a `dir:` lane), on a key that would collide across two of a unit's containers, and on an off-grammar `none - owned by <component>` ownership handoff (a reused container references its own standalone unit instead).
- **Added:** the completeness verdict now WARNs (never FAILs) when a built element is absent from the outline (under-specification); the high-signal channel is alias- and boilerplate-aware.
- **Changed:** the `toc.md` reader is fenced-code aware (an outline example inside a ``` / `~~~` block is not parsed; an unterminated fence FAILs loud) and tab-indent aware.

## [0.11.0] — 2026-09-14

SAID-17 — the SAID-16 follow-ups (completeness executed-capture + built-floor, engine-word purge, plain-ASCII glyph gate).

- **Changed:** `said_completeness.py` now realizes the cli **oracle tier** — where a capture manifest declares a per-unit `cmd:`, it executes that command's own `--help` **read-only** (command-path + `--help` only; every invocation flag stripped; a flag is verified by a **two-witness** rule -- an options-section+column cluster corroborated by the `usage:` synopsis, so a flag named only in prose is not miscounted) and verifies the designed `Flags` against it; a manifest `built:` line cannot bluff an oracle element. A tool whose `--help` is not two-witness parseable (hand-formatted / truncated synopsis) falls to declared-evidence (manifest) with a WARN -- a documented coverage ceiling, not full author-independence. The completeness recipe row moves `said-capture: manifest` -> **`process-spawn`**. A non-cli (web) capture runs a front-declared probe as given (the front owns its read-only-ness; hermetic fixture shipped).
- **Added:** a **built-floor** — an all-dropped (zero-built) manifest FAILs (`BUILT intersect DESIGNED` must be non-empty); a legitimate partial-drop still PASSes. Closes the vacuous-completeness hole.
- **Changed:** the medium-agnostic engine (`uxtoc` / `architect` / `said_completeness.py`) carries **no incidental medium vocabulary** — `uxtoc` emits purely from the loaded grammar (the emit template lives in the grammar, discharging the SAID-05 §10.2 residual).
- **Added:** an enforcing **plain-ASCII gate** (`docs/evaluation/plain-ascii/`) over `plugins/said/**` (R-SAID-08 realized; em-dash `U+2014` carved out); the shipped surface is purged of banned watermark glyphs.

## [0.10.0] — 2026-09-13

Medium-agnostic uxtoc unit contract + no-seal completeness model. The design-outline engine (`uxtoc`, `element-projection.md`, `said_completeness.py`, `architect`) is now medium-agnostic: the engine owns the projection rule; each lane owns its vocabulary in a per-surface `docs/ux/feature-ux-grammar.md` grammar (one SC-HEADER section per surface, selected by `SAID.surface:`).
- **Removed:** the `toc-checksum:` count-seal added in 0.9.0 — it fought the operator-editable `toc.md` and was same-count-blind. Completeness now rests on the comparison + the L2 oracle verdict-recompute + a capture manifest (declared-evidence; the author-independent executed capture is the deferred per-lane probe-table); `uxtoc` stamps `grammar:<token>` + `last-revised:` instead of a checksum.
- **Changed:** `element-projection.md` reduced to the rule only (VERIFY-TOKEN `UXP-R-1`); the container set, attribute set, and scaffolding (`not-elements`) moved into the lane grammar. The element rule is attribute-set-aware — a key in the grammar's attribute set or `not-elements` set is not an element and never steals its parent's status, closing a projection bug where a nested attribute silently dropped an unbuilt element green.
- **Changed:** `said_completeness.py` derives DESIGNED unit-driven from the injected grammar (`SAID_GRAMMAR`/`SAID_SURFACE`, `--grammar` argv else `die(2)`), cross-checks the `grammar:<token>` stamp (absent → FAIL); BUILT is read from a capture manifest (declared-evidence), and the grammar's `oracle-containers:` records which containers will be verified author-independently once the deferred per-lane capture probe-table lands.
- **Changed:** `architect` folds one acceptance line per unit (generalized from per-screen) + stamps `last-revised:`; the completeness recipe row moves to `said-capture: manifest` (declared-evidence) with `said-env: SAID_GRAMMAR;SAID_SURFACE` (the executed cli/web capture is the deferred per-lane probe-table).
- **Added:** a `cli` grammar section (`unit=Command`) for this lane; a `web` grammar (`unit=Screen`) delivered to the front lane cross-repo.

## [0.9.0] — 2026-09-10

The uxtoc basis→contract lifecycle runs off a single source of truth (`toc.md`).
- **Added:** `uxtoc` emits a `toc-checksum: total=<N>,<SCREEN-ID>=<n>,…` line on `output=`, counted by the new `element-projection.md` taxonomy (LOAD-WHOLE + VERIFY-TOKEN).
- **Changed:** the completeness check parses `toc.md` directly and verifies the checksum (FAIL → "re-run uxtoc"); the `toc-elements.md` intermediate is retired (reverses SAID-08 decision (a)).
- **Added:** a hermetic web end-to-end fixture — outline → `architect` §AC fold → built manifest → `accept` recompute.
- **Added:** a generative-composition note in `uxtoc`.
- **Fixed:** `said:status` / `said:board` count a bulleted `- **Status:**` task line, not only the plain `**Status:**` form (`said_status.py` `STATUS_RE`).
- **Changed:** `said:add-task`'s task stencil emits the canonical non-bulleted `**Status:**` / `**Priority:**` / `**Refs:**` form (matches `template-tasks.md`).

## [0.8.1] — 2026-09-09

- **Changed (breaking):** the lane key is `SAID.profile:`, renamed from `SAID.impl-profile:` — the family of deliverable is a property of the lane, not of one skill.
- **Changed:** `SAID.code-review:` is an optional per-lane override of the profile's `code-review` slot, not a key a lane is expected to set.

## [0.8.0] — 2026-09-09

`said:impl` is a contract, a family-blind procedure, and one profile per family of deliverable.
- **Added (breaking for un-keyed lanes):** `SAID.impl-profile: code | doc | work` on the `## Lane` block is required; `impl` loads `references/profile-<name>.md` at Step 0 and at every phase start, and halts naming the shipped profiles when the key is absent or names none of them. The value is never derived from `SAID.surface:`.
- **Added:** `references/profile-{code,doc,work}.md` — six slots each (`gate · red · carve-out · tag · parity · code-review`), the only place a lane value may appear. A new family is one new file; the spine and the phase files never name a family.
- **Changed:** the standing read instruction moved to a `## Contract` block at the head of the spine (ends before byte 3,000), so it survives any compaction cut; the spine is 14,076 bytes.
- **Changed:** `SAID.code-review:` absent now means the profile's `code-review` slot (`code` on, `doc`/`work` off) instead of a constant `on`.
- **Changed:** the surface-contract consume block is SC-STUB v3 in `add-task`, `architect` and `impl`: the trigger sentence no longer lists media as examples — the shape vocabulary is the loaded registry's own `applies-to` values.

## [0.7.0] — 2026-09-08

`said:impl` carries no stack of its own — a lane's `## Earned rules` is its implementation discipline, re-read at every step and proven at close.
- **Changed (breaking for un-rolled lanes):** `said:impl` reads the lane's `CLAUDE.md` `## Earned rules` section at Step 0 by heading and **halts when the heading is missing** (an empty section proceeds). Add the section — one rule per `- ` line, an `R-*` id, a link to its ADR — plus a `## Significant ADRs (skill-referenced)` table and one reminder line under `## Claude Code Reminders`.
- **Changed:** the discipline is *test-first* with the red defined without naming a lane — the failing `<tests>` run where the lane binds one, otherwise the task's still-unchecked Acceptance item. The origin project's framework, mock and component identifiers, and the inline wire-probe procedure, are gone from `impl`; a lane that needs wire capture states it as its own rule.
- **Added:** before every Phase B confirmation unit (per Acceptance item in an arm) `impl` re-reads the section from disk, echoes its count, and writes one briefing line per applicable rule; each task's `### Fix` now carries `Rules applied: <ids | none> (block: N)`.
- **Added:** `said:review-qa` verifies that line (bundled `earned-rules.py`, reached by `impl` via the sibling-skill path): an id absent from the section or a count above the actual → FAIL; a count below the actual → WARN (the block grew since the close); an absent line → FAIL for closes on/after 2026-09-08, WARN before; a lane without the heading → WARN before that date, FAIL after.
- **Changed:** the standing re-anchor step and a self-re-read line sit at the top of `impl` (inside the part of a skill that survives a context compaction).

## [0.6.0] — 2026-09-07

Task-level fan-out for a single-lane cycle — arms build, main decides.
- **Added:** `said:impl <task> arm` / `said:impl <task> close`. A fan-out **arm** builds one task under
  forced autonomy (no operator, no log write, no commit), declaring its files before any edit and
  returning a close block; **close** applies that block in main and runs Phase C. `said:said` fans out a
  feature's write-disjoint `Todo` tasks — opt-in word `fan-out` — to concurrent arms via the Workflow
  tool, then closes them serially in main; intersecting and own-log tasks stay a serial set. The
  append-only log, gate verdicts and every decision stay in the main context.
- **Changed:** `impl`'s long-reserved fan-out mode is now defined; the stale "no nested subagent
  spawning" note is corrected **plugin-wide** — in `impl`, in the one line `flow` quoted, and in the
  `scope-audit` / `scope-refine-agent` agents (whose inline-audit design is unchanged, only the stated
  reason) — to the real per-subagent limits: the Workflow tool and the operator exist only in the main
  context (nested spawning itself is permitted).
- **Changed:** `said:said` tolerates a depth-1 invocation and records a fan-out as skipped there (no
  Workflow tool in a subagent); stale macro names removed from its depth clause.
- **Changed:** `review-qa` now asserts a Done task's `### Fix` is **present and non-placeholder** before
  parsing its claims (new checklist rule R-QA-07 + a Phase-A pre-check) — an empty `### Fix` on a Done
  task no longer passes vacuously. Earned from an independent acceptance review of the fan-out release.
- **Changed:** `add-task` and `architect` Approach rules now **name the task's write-target** (the
  unit/file it edits) as a key decision — the fan-out partition derives write-sets from it — while still
  forbidding file enumerations; `add-task` states it runs **main-context only** as the one writer of the
  append-only log (a task discovered inside a fan-out arm is owed to main, never appended there).
- **Fixed:** `add-task`'s Step 4 heading still read "Append + apply confirmed spec edit" — a stale
  pre-consume-contract remnant contradicting its own body ("writes the tasks log only — never the spec"); corrected.

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
  and runs natively for a `surface: doc` lane.
- **Added (withdrawn in 0.5.0):** a per-lane bar file `docs/qa/doc-gate.md` with `--bar`, `--init`,
  `--explain`.
- **Changed:** the `doc-editorial` agent names its optional inputs.

## [0.3.7] — 2026-09-04

- **Fixed:** the reviewer gate validates the Checker that RUNS — the checkers-dir defaults to the
  plugin's own `agents/`, resolved from `said_status.py`'s install location, never a per-project copy;
  a duplicate `said-checker:` id is surfaced, never last-writer-wins.
- **Changed:** the scope skills (`scope-refine`, `scope-grill`, `architect`) run `said:retrieval` as a
  read-only precedent sweep before proposing defaults; `review-qa` and `accept` recognise a `doc`
  surface; the `doc-editorial` agent names its L1 verdict artifact.

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
