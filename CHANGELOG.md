# Changelog

All notable changes to the SAID plugin are documented here. Format follows [Keep a Changelog](https://keepachangelog.com); the project uses semantic versioning.

## [Unreleased]

Two boards beside the features board, and a manager for the backlog: `/said:board backlog` and `/said:board todo` read the workspace backlog file and each lane's todo list through one grammar-driven reader, a row's priority and order are set from the page, and the new `said:backlog` skill is the one writer of backlog entries and idea records. The plugin ships 17 skills.

**Breaking.** The connected board's Backlog view, `GET /fragment/backlog`, `POST /todo` and the `--todo-file` flag are gone, with no alias and no stub, and with them the `backlog` mount point and the stored `todo` key of `docs/.board/config.json` (now ignored): read a lane's todo list on `/said:board todo` (it reads `<lane root>/<docs-root>todo.md` for every lane of the root's `SAID.lanes:` registry), and add a todo line by hand. A launch line that still passes `--todo-file` exits 2 with a usage error.

- **Added:** `/said:board backlog`: the backlog file `<docs-root>backlog.md` of the root, its entries by stage and by priority, each with its record trail and feature link. `/said:board todo`: one tab per registry lane that has a `todo.md` (no tab for a lane without one), with state and priority filters. The header's board switch moves between the features, backlog and todo boards on one page (`?board=backlog`, `?board=todo` in the URL); each board refreshes and caches on its own. `--cli` and `--json` print the same boards as text and data (`said_backlog.py --board backlog|todo`).
- **Added:** four page writes, on by default with no flag: `POST /backlog/priority`, `POST /backlog/order`, `POST /todo/priority`, `POST /todo/order`. A row's priority token (`[#A]`, `[#B]`, `[#C]`, or none) and its order within its section and group apply with no confirm step. Each write checks the Origin against the server's loopback origins, the CSRF token and the JSON content type with the `X-Said-Board` header, caps the body at 8 KiB and takes its target file from the server, never from the request; a refused or stale write answers with an error and writes nothing. The features board writes nothing; `POST /connect` keeps its four controls.
- **Added:** `said:backlog`, the backlog manager: `/said:backlog lint | add | move | supersede | promote | set-priority`. `lint` checks the backlog against its own frontmatter grammar and the priority grammar (`lint: N errors, M warnings`, exit 1 on an error); `add` appends one open, stamped entry; `move` carries an entry's notes into a new idea record from `backlog/template-idea.md` (the engine's `record`; its own `move` is the page's reorder); `supersede` replaces an entry with one that names what it supersedes; `promote` moves a record folder into a registry lane's working dir for a feature, plan first and one confirm; `set-priority` writes the token on an entry or a record head. Every write runs through `said_backlog.py` in the board skill folder; a refusal exits 2 with `refused:` and writes nothing. The skill never reads or writes a `todo.md`.
- **Added:** `said_backlog.py`, a stdlib-only reader of the backlog file and the lanes' todo lists by their grammars (text and `--json`); every text field is stripped of control characters and capped; a malformed line is a finding, never a crash.
- **Changed:** `debrief` routes each pending proposal at its close: a proposal you want kept becomes a backlog entry plus its idea record through `said:backlog`, a leftover becomes one plain line in the lane's `todo.md`, anything else stays in `debrief.md`; each entry records where it went and the footer counts them.
- **Changed:** the deep-dive fragment takes the lane: `/fragment/feature/<id>?lane=<lane>` opens that lane's feature when two lanes share an id.
- **Changed:** the board skill's write rule reads "Don't add a write route without its controls": every write carries the controls above and an integration write also needs `--connect`.
- **Migration:** update the plugin. Move a todo file you passed with `--todo-file <path>` to `<docs-root>todo.md` of its lane, then drop the flag from your launch line or script: the todo board finds each lane's file through the registry. A client that posted to `POST /todo` writes the line to the lane's `todo.md` itself; a client that fetched `GET /fragment/backlog` reads `said_backlog.py --root <root> --board todo --json`, or the board's fragments `GET /todo/board` and `GET /backlog/<view>`. A `todo` key left in `docs/.board/config.json` can be deleted. A companion app that mounted the board's `backlog` mount point has no mount to hydrate; a stored `backlog` view opens the List view.

One gate verdict per feature: the full harness recompute runs once, at `review-qa`, and every later gate reads its record.

- **Changed:** `review-qa` runs its quality-gate step through `skills/board/gate_recompute.sh` with `SAID_GATE_OUT=<working dir>/gate-<feature-id>.md`; the script writes that record itself (`head: <sha>` first, then every `gate-recompute:` row), and a session never types a row. A halted or killed run leaves no record; with the variable unset the script prints exactly what it printed before. A `doc` lane keeps its `doc-gate` terminal and writes no record.
- **Changed:** `accept` and `debrief` read the record at a matching HEAD and rerun nothing; an absent or stale record stops them with `gate owed: run /said:review-qa <id>`. `accept` keeps its reviewer-gate call only for a declared Checker that is not process-spawn plus deterministic.
- **Added:** the record also carries one reviewer-written `skill-doctor: <file> open-P1=<n> reviewer=<session>` row per touched skill file, written through the bundled `skills/board/gate_record_row.py`; a rerun of the script at the same head keeps these rows and a moved head drops them, and `accept` and `debrief` never read them.
- **Removed:** the reviewer-gate recorded probe at `impl` Phase C (task close) and, for a `cli-gate` Checker, at `accept` Preflight. `impl` Phase C step 2 now runs the lane command plus the `docs/evaluation/<unit>/harness.sh` each task names, never the full recompute; Phase C has seven steps.
- **Migration:** a feature closed before this release has no record: run `/said:review-qa <feature-id>` once before `accept` or `debrief`.

## [0.24.0] - 2026-10-26

One observe skill: `said:status` is folded into `said:board`. `/said:board` opens the web page; `/said:board --cli` prints the terminal board it replaces, and `/said:board --json` its data.

**Breaking.** `/said:status` no longer exists, with no alias and no stub: use `/said:board --cli` (with `<feature-id>`, `--lanes` or `--stale` as before), or `/said:board --json`. The analyzer, completeness and recompute scripts moved from `skills/status/` to `skills/board/` under their own names.

- **Changed (breaking):** `said:board` is the one read-only observe skill. The web page is its default surface, `--cli` the terminal board, `--json` the data layer; `/said:board <feature-id>` opens the web board on that feature's deep-dive (the page reads `#<feature-id>` from its URL). The board skill no longer depends on a second skill.
- **Changed (breaking):** `said_status.py`, `said_completeness.py` and `gate_recompute.sh` live in `skills/board/`. The `cli-gate` Checker's recompute, the re-anchor hook, `setup` and every skill that runs the analyzer use the new path; the re-anchor hook now prints `/said:board --cli`.
- **Changed:** the web server is a shell plus one module per board (the features board in `boards/features.py`); every route and its response are unchanged.
- **Changed (breaking):** with `--lane`, a top-level `--prefixes` no longer applies to the lanes (it used to reach every lane): a lane without `;prefixes=` infers its own set, and `--legacy-prefixes` still applies to every lane unless it gives `;legacy=`.
- **Fixed:** a feature's review gate ticks when every Checker the lane declares in `SAID.reviewers:` (read whole from the lane's `## Lane` block) has a verdict file `review-<checker-id>-<feature-id>*.md`; it used to read `review-ux*.md` only, so a `cli-gate` verdict never ticked it. On a lane with several Checkers, one Checker's file does not tick. Presence only, as before.
- **Fixed:** the accept wait reads the accept file's last `Verdict:` line outside a code fence, so an earlier `MANUAL-PENDING` followed by a later verdict no longer shows as waiting.
- **Fixed:** a Deliver-phase feature gets the Deliver colour on the web board (column accent, row stripe and phase pill).
- **Migration:** update the plugin, then repoint anything that runs a bundled script by path: `skills/status/said_status.py` -> `skills/board/said_status.py`; `skills/status/said_completeness.py` -> `skills/board/said_completeness.py` (for example the `said-recompute:` line of the completeness Checker in a lane's surface rules); `skills/status/gate_recompute.sh` -> `skills/board/gate_recompute.sh`; a `SAID_STATUS` override of the re-anchor hook that names the old path; a permission rule in your settings that names `said:status` or an old script path. Replace `/said:status` with `/said:board --cli` in your own notes and lane instructions.

## [0.23.0] — 2026-10-23

Fast-track runs: on your word, a named set of a feature's tasks defers its per-task review-ux, code review, review-qa and accept to one close over the set, recorded in the tasks log where every session reads it.

- **Added:** `/said:add-task <feature-id> fast-track "<task ids>"` opens a run: it appends a `## Fast-track F<NN>` block to the tasks log with `feature:`, `opened:` (date and HEAD the run opened on), `operator:` (your words quoted with their date, a ruling id when one exists), `tasks:` and an empty `closed:`. Run ids count `F01`, `F02` per feature, never gap-filled; one run is open per feature at a time and a task is in exactly one run; opening refuses an id with no task heading or one already Done, and refuses when HEAD cannot be read. A task added while the run is open carries `**Fast-track:** F<NN>` after `**Refs:**`. `/said:add-task <feature-id> fast-track F<NN> closed` writes the block's one later line, `closed:` (date, HEAD plus `dirty` when uncommitted, the run's report names), and refuses while a listed task is not Done and unless every required report reads PASS. The block is a recorded, operator-confirmed skip of per-task gates; said checks no transcript for it.
- **Added:** `impl` Phase C, for a task in an open run, runs parity, the quality gate, the reviewer-gate probe and the close-of-task steps as today, defers review-ux, the code review and the hand-off, and adds the line `fast-track F<NN>: review-ux, code review, review-qa, accept deferred to its close` to `### Fix`; Status stays `Done (YYYY-MM-DD)`. A task outside every open run takes the full chain.
- **Added:** run forms of the three gates, each the feature-mode gate narrowed to the run's listed tasks: `/said:review-qa <feature-id> fast-track F<NN>` (Fix integrity includes the deferral line and each task's code-review line), `/said:review-ux <feature-id> fast-track F<NN>` (once per screen shape on `web`, once per run on a doc lane, nothing when no agent-form Checker is declared), `/said:accept <feature-id> fast-track F<NN>` (the listed tasks' Acceptance items only). They write `review-qa-<feature-id>-F<NN>.md`, `review-<checker>-<feature-id>-F<NN>.md` and `accept-<feature-id>-F<NN>.md`, never the feature's verdict.
- **Added:** `said:said` reads open runs: a Done task in an open run is deferred, not an unconfirmed omission; the `gates:` line shows `deferred (F<NN>)`; the goal line reads `continue` while a run is open; a due run (every listed task Done) closes before the next Todo task and before Deliver: its close step runs the code review per group you cut (said spawns the read-only reviewer over the run's whole diff, `git diff <opened sha> -- <files>`, committed and uncommitted together, untracked files included; the close refuses a run whose `opened:` carries no resolvable HEAD sha; each grouped task gets a `fast-track F<NN> code review:` line in its Fix), then the three gates' run forms, then the `closed` write, and prints the run's path list and HEAD sha; an open run at Deliver closes first; `said closed: yes` needs every run closed.
- **Added:** `said:status` prints `fast-track open: F<NN>, <n> tasks` for a feature's open run in the deep-dive and `<feature-id> fast-track open: ...` in every roster, `--stale` included, so the re-anchor after `/clear` shows it. A run's `-F<NN>` reports never tick a feature-level gate, never raise the accept wait and never move the `Next` action.
- **Changed:** `debrief` blocks while a fast-track run is open (a `## Fast-track F<NN>` block with an empty `closed:` line) and redirects to that run's close, and its Phase-3.5 gate check reads feature-level reports only, never a run's `-F<NN>` report.
- **Migration:** none required. A feature with no `## Fast-track` block behaves as before.

- **Added:** `said:gate-reviewer`, a read-only reader for one step of `review-qa`, `accept` or `debrief`. Above the optional lane key `SAID.gate-reviewer-threshold: <tokens>` (read at the start of each gate from the same `context.json` the statusline writes) the gate hands its reading and classifying step to the reviewer, which proposes rows with file:line evidence; the gate opens the cited lines and keeps every command, pause, verdict and write. Debrief's A.1-A.4 inventory is proposed the same way; main scans, keeps A.5, A.6 and every mark. The handoff is bounded: closed readings and envelope, a main-vetted manifest, encoded excerpts, a runtime fallback when the reviewer is unavailable. `setup` knows the key (schema row, README paragraph).
- **Changed:** the context checkpoint in `said` and `flow` names a threshold no fresh session can meet: when `SAID.context-checkpoint` is below the session's own first reading plus said's load (read from the session's transcript by the bundled `first_reading.py`), the stop says the sum is at least that number and that only raising the key ends the stop, instead of asking for another `/clear`. `setup` reports a checkpoint value below the schema floor as one ADVISORY.

## [0.22.1] — 2026-10-20

- **Changed:** `debrief` no longer waits for you to type a `landed` mark. In the rulings step the session running the debrief opens every home a ruling lands in and checks that it holds the ruling, applies the `ruled!! mark <id> landed <home>` line itself with the installed rulings tool, and records `mark applied by <session role>` on the row; the re-read before and after is unchanged. A `rejected` or `superseded <new-id>` mark is still printed for you to type. Without a rulings tool the row goes deferred to `## Pending proposals`, as before. Debrief still never writes a rulings list or invokes another plugin's skill.
- **Changed:** in a supervised run (a `said:worker` session under a `said:supervisor` session) the supervisor's brief answers the debrief's Phase A rows and gives the Phase B go-ahead, and you review the `## Debrief close` footer; a row that needs a product or scope call still holds for you. An unsupervised run is unchanged.

## [0.22.0] — 2026-10-19

Debrief now places a feature's rulings, two session-role definitions ship for running a supervisor session over worker sessions, and the reviewer gate reads the right verdict and passes a lane that ships nothing.

- **Added:** session-role definitions `said:supervisor` and `said:worker`, launched as top-level sessions (`claude --name <session> --agent said:supervisor`, `claude --name <session> --agent said:worker`), not spawned as subagents. The supervisor briefs the worker sessions you name, accepts a worker's report only after re-running its gate or reading its changes, and keeps your reserved calls for you; a worker builds on the supervisor's brief, forwards your typed words to it, commits only by brief and holds a reserved call instead of acting on it. Each definition pins a model (the supervisor `fable`, the worker `opus`), which `--model` on the launch line overrides. The README's "Session roles" section carries the launch lines.
- **Added:** `debrief` places the feature's rulings (a ruling is the operator's recorded answer, one line in the work's `rulings.md`). A bundled read-only reader, `debrief/rulings-read.py` (`list` and `status`), reads the work's `rulings.md` with the hold gate's own line parser. Step 0 reads the feature's list from its working folder, and a sibling feature's list only on your word. Phase A gains section A.5, one row per pending ruling with a proposed home class (task-log home when a Done task cites the ruling id, lane home, or owed to a named owner); the successor section moves to A.6. Phase B's rulings step re-reads each ruling's status first, prints the exact `ruled!! mark ...` line for you to type, and sets the row applied only when the re-read shows the new status, else deferred. Owed and deferred rulings are carried in `## Pending proposals` in their own entry forms. The close footer gains a `Rulings:` line counting landed, marked, owed, deferred and skipped rulings, and the footer does not land while a rulings row is proposed or revise. Debrief never writes a rulings list.
- **Changed:** a doc-surface lane whose `SAID.mounts:` is the bare `none` ships nothing, so its editorial reviewer is recorded as N/A at the gate instead of failing for a missing verdict: `said_status.py --reviewer-gate` prints the reviewer as `N/A -- SAID.mounts: none, nothing shipped` and passes. `review-ux` runs nothing for such a lane, at task or feature scope (no checklist load, no reviewer, no verdict file), names that gate line as where the N/A is recorded, and reports the outcome `N/A-NOTHING-SHIPPED` with its next step: close the task. A doc lane with a real mount still fails when its verdict is missing.
- **Fixed:** the reviewer gate reads, among a reviewer's `review-<checker>-*.md` verdict files, the one whose `target-sha` is HEAD (the newest by modification time if several), else the newest by modification time; never the last by file name. An older verdict whose name sorts later no longer shadows the current one. Every check after the pick is unchanged, so a newest verdict at an older sha still fails on the sha.
- **Migration:** none required. A rulings list is written by the `ruled` skill of the `magic` plugin, 0.13.0 or later; without it there is no list, and debrief prints `warn: no rulings list` and continues.

## [0.21.0] — 2026-10-15

**Breaking.** The context checkpoint is off unless the session switches it on; the mounts key replaces the code-mount key; the lane registry has one written grammar. A lane block that still spells the old key, or a registry in any other shape, is reported by `setup` and read by nothing; no alias period.

- **Changed (breaking):** the context checkpoint stop is off by default (`SAID_CONTEXT_CHECKPOINT` unset means no check, no stop, no notice). A session switches it on from its launch line, `SAID_CONTEXT_CHECKPOINT=on claude`, or inside the session with the opt-in word `checkpoint` in the directive (`said! <feature-id> checkpoint`, `flow! <feature-id> checkpoint`); the word makes the skill write an empty marker `checkpoint-on` in the session scratchpad, which a compaction keeps and a `/clear` drops, so a stop the word switched on prints its re-issue directive with the word. Either source means on; the word is never a grant. `SAID.context-checkpoint:` stays the threshold and is never the switch.
- **Changed (breaking):** `SAID.code-mount:` is withdrawn; a lane declares `SAID.mounts: [<path>, <path>]`, relative to the lane root, a single path bracketed too, or the bare word `none` for a lane that ships nothing. `setup` reports a lane without it as a BLOCKER and the old key as STALE with the exact line to write; `/said:setup --fix` writes that line when the old value carries over as written, and otherwise proposes it.
- **Changed (breaking):** the lane registry is one key line in the root's `## Lane` block, `SAID.lanes: [TOKEN=root/, TOKEN=root/]` (a token is a letter then letters and digits; a root is a relative directory ending in `/`, `./` for the root itself). A token-only line, a table or bullets beneath the line are refused by the reader and reported by `setup` as a BLOCKER, and the skills that read the registry (`said`, `flow`, `add-task`, `architect`, `status`) stop with the reason until it is rewritten; where no registry line exists, `setup` proposes one from the lane blocks it finds below the root.
- **Added:** `said_status.py --registry` prints the registry's rows in the form `--lane` takes; `--registry --resolve` prints each row as the full `--lane` argument, its docs and working dirs read from that lane's own block, and skips a row it cannot resolve with one line.
- **Changed:** at a root that declares a registry, the re-anchor hook tries a branch feature it cannot find there in each listed lane and prints the lane that holds it; a lane that is its own git repository adds one line for its own branch feature; a directory the registry does not list is never read. The hook's lane gate is the exact heading `## Lane` (a `## Lanes` heading is not a lane), and its inactive-checkpoint hint prints only in a session that switched the checkpoint on.
- **Changed:** `setup` rejects a declared `SAID.context-checkpoint:` that is not a positive integer (`off`, `0`, `300_000`) as a BLOCKER naming the key.
- **Migration:** update the plugin first. In each lane block, replace `SAID.code-mount:` with `SAID.mounts: [...]` (`/said:setup --fix` writes or proposes the line); at a multi-lane root, write the registry as one `SAID.lanes: [TOKEN=root/, ...]` line and remove any token line, table or bullets that carried the rows. To keep the checkpoint stop, add `SAID_CONTEXT_CHECKPOINT=on` to the launch line or the word `checkpoint` to the directive.

## [0.20.0] — 2026-10-02

**Breaking.** The hold vocabulary is renamed, and a hold is lifted by citing a recorded ruling. A task log that still carries the old marker, section or field HOLDs until it is renamed; old spellings are rejected with a message naming the rename, never accepted beside the new ones.

- **Changed (breaking):** the open item only the operator may answer is an "operator question". Marker `**Blocked-on question:** <id>` (was `**Blocked-on decision:**`); section `## Lifted holds` (was `## Decisions`); field `lifted-by:` (was `resolved-by:`); stop token `OPERATOR-QUESTION-HELD` (was `OPERATOR-DECISION-HELD`); `review-ux` verdict `NEEDS-OPERATOR-ANSWER` (was `NEEDS-OPERATOR-DECISION`); an id minted mid-flight is `Q-<n>` (was `D-<n>`; a scope id is kept).
- **Changed (breaking):** `review-qa/decision-gate.py` is now `review-qa/hold-gate.py`, with no alias. A lift line reads `- <id> lifted-by: user@WR-<seconds> -- "<verbatim quote>" -- <date> [supersedes: <prior>]` and passes only when the cited ruling is in the work's `rulings.md` (recorded with the `ruled` skill of the `magic` plugin, 0.13.0 or later), its provenance is typed or dialog, and the quote is inside the operator's message. The turns file is gone.
- **Changed:** `status` calls the gate's own judge, so the board and the gate agree; a task closed while held shows "closed without a lift".
- **Fixed:** a reopened feature no longer reads Closed: Todo tasks below the last `## Debrief close` footer read Implement; all Done below it reads Deliver.
- **Migration:** in each task log and in your `template-tasks.md`, rename the marker, the section heading and the field; record each operator answer as a ruling and cite its id in the lift line; delete `decision-turns.jsonl`. Update the plugin first, then the templates. Re-sync your copy of the macro block from the `magic` plugin (it says "operator question").

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
