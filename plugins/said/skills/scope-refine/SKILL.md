---
name: scope-refine
description: >
  SAID/Phase 1 (Scope) Case 1 — refines a substantive technical handoff
  (handoff doc OR current branch state) into a `scope.md` for Act's
  Architect step. Resolves input from operator argument, spawns the
  `said:scope-refine-agent` agent (codebase audit, and the lane's probe
  procedure when one is passed) on a small lane, or runs the bundled rule chain on a
  lane whose rule documents are large, and relays the draft and its §D to
  the operator.
  Triggered ONLY by the explicit command "/said:scope-refine
  [<handoff-path>] [probe-procedure=<path>] [scope-hint=<dirs>]".
  NOT for thin-input ideation — that's `/said:scope-grill` Case 2.
---

# Feature Scope Refine — Phase 1 (Scope) Case 1: Handoff or Branch-State Refinement

## Contract

1. **Scope only.** This skill writes the scope draft and nothing else: no spec, task list or code (Step 4).
2. **The script sizes the lane and lists its rule documents.** `size` decides small or large and names the documents; never decide or pick either yourself. A lane with no `SAID.scope-mounts` reads the default folders and stops only when none of them exists (Step 1c).
3. **Small lane: one agent.** `said:scope-refine-agent` does the work (Step 2).
4. **Large lane: the chain as written.** Every step of Step 2L runs as written; never write, edit or repair a file a script or an agent writes. A failed check goes back to its agent once, then BLOCK; the silence pass of step 5 goes back for up to three rounds, then STOP.
5. **Wait for every agent.** No agent runs in the background; its reply or its file comes before the next command.
6. **Section D reaches the operator unchanged.** Print it verbatim; never resolve, default or empty an item (Step 3).

This skill drives the Phase 1 Case 1 path — turning a substantive handoff into a refined `scope.md`. Case 2 (thin idea, no handoff) uses `/said:scope-grill` instead; THIS skill is for branch continuation, refactoring, or any work where a real handoff doc OR current git state already carries the substance.

The skill itself is a thin wrapper. The `said:scope-refine-agent` agent does the substantive work — Stage 0 contract reads, Stage 1 handoff index, Stage 2 codebase audit (one report per in-scope dir, by `said:scope-audit` agents or inline, as the agent's text says), Stage 3 the lane's probe procedure when one is passed, Stage 4 contract classification, Stage 5 scope.md write, Stage 6 self-check. Your job here is to resolve inputs, size the lane's rule documents (Step 1c), spawn the agent on a small lane or run the rule chain on a large one (Step 2L), and carry §D items visibly back to the operator.

**Surface note.** Works for every `SAID.surface:` medium. Stage 0 reads whichever contract docs the project's `CLAUDE.md` names; a live probe runs only from the probe procedure the lane passes for its surface (`probe-procedure=<path>`). The skill itself is surface-agnostic — it just resolves inputs and spawns.

## When this fires

The user invokes one of:

- `/said:scope-refine <handoff-path>` — refine the named handoff doc.
- `/said:scope-refine` — no path given; skill synthesizes a minimal handoff from current branch state.
- `/said:scope-refine <handoff-path> probe-procedure=<path>` — on a small lane, run the lane's probe procedure for its surface.
- `/said:scope-refine <handoff-path> scope-hint=<dir>,<dir>` — audit these dirs in place of the dirs the handoff names.

Args parse as: any token containing `=` is a flag (`probe-procedure=...`, `scope-hint=...`); the remaining token (at most one) is the handoff path. A flag other than these two (an old `probe-mode=` included) -> STOP naming it and the two flags this skill takes.

If the operator's input is a thin idea ("Let's ideate a notification preferences UI") rather than a handoff path or a real branch state, this is the WRONG skill. Redirect: "That's Case 2 — use `/said:scope-grill` for interactive ideation. This skill (`/said:scope-refine`) is Case 1, requires either a handoff doc path or substantive current-branch state."

## Step 1: Resolve inputs

Resolve five inputs — by reading sources, not by asking — except where explicitly noted:

1. **handoff-path** — depends on the operator's argument:
   - **Path given** — verify it exists via `ls <path>`. If missing, BLOCK with `handoff path not found: <path>` and ask the operator for the correct path.
   - **No path given (branch-state synth)** — synthesize a minimal handoff from git state:
     - Branch name: `git branch --show-current`.
     - Recent commits: `git log -10 --oneline`.
     - Uncommitted changes: `git status --short`.
     - Any `docs/working/**/wip*.md` files (via Glob).
     - Concatenate into a markdown handoff doc with sections `## Branch state`, `## Recent commits`, `## Uncommitted changes`, `## Wip notes`.
     - Write to `<SAID.working: root>/<feature>/_branch-state.md` (you'll need feature name first — see input 3). This file lives alongside `scope.md` as audit-trail; the agent's boundary rule treats only the named handoff path as authoritative, so co-located peer files don't pollute the audit.

2. **output-path** — `SAID.working:` root (`## Lane` block; no key -> HALT) + `scope.md`. The agent writes here. If `scope.md` already exists at that path, append `-N` (`scope-1.md`, `scope-2.md`, ...) so prior versions stay as history.

3. **feature name** — needed to construct paths in inputs 1 and 2. Derive from:
   - The operator's path argument: if it's under `docs/working/<feature>/...`, take the leaf segment.
   - The current branch name: convention varies (`feature/foo` -> `foo`; canonical task IDs matching `^([A-Z]+)(\d+)-.+$` derive to feature `${1}-${2}`; bare slugs like `proj-01` pass through).
   - If still ambiguous (e.g., on `main`), ASK the operator: "What feature name should I use for the scope.md output? Suggest: `<best-guess>`."

4. **scope-hint** (optional) — comma-separated list of feature dirs to audit, overriding the dir list extracted from the handoff, from the flag `scope-hint=<dir>,<dir>`. Pass it through when given; otherwise omit it and let the agent derive the list from Stage 1.

5. **probe-procedure** (optional) — the path of the lane's probe procedure for its surface, from the flag `probe-procedure=<path>`. Verify it exists via `ls <path>`; missing -> BLOCK with `probe procedure not found: <path>`. Pass it through when given. Without it the agent's Stage 3 is a no-op: say so in Step 3, never write a procedure yourself.

If any required resolution would force a guess, ASK the operator one focused question per gap — never the full questionnaire at once.

## Step 1b: Consult the decision record first (retrieval-at-scope)

Before spawning the agent, run **`said:retrieval`** on the feature question — a read-only precedent sweep so the scope starts from what the project already decided, not a blank slate. Pass its findings into the agent's spawn prompt (a `Precedent (said:retrieval): ...` block) so the agent's §A framing and §D open-questions weigh precedent first, and surface precedent-vs-handoff conflicts in §D rather than resolving them silently. **Surface-agnostic** (every medium) and **additive** — an empty decision record is a no-op ("no precedent found — proposing without"), so this never blocks a greenfield refine. **Compose** `said:retrieval` (read-only, terminal); never re-implement the sweep here.

The sweep ends with its own status lines (`retrieval complete: yes | no`). They end the sweep, not this skill: whatever they say, go on to Step 1c in the same turn. The sweep's findings go into the spawn prompt on a small lane, and into Step 3 beside the draft on a large lane; they are not your reply.

## Step 1c: Size the lane's rule documents

In every command below, `$CHAIN` stands for the words `python3 -I -B "${CLAUDE_SKILL_DIR}/rule_chain.py"`: write them out in every command, never as one shell variable. `<script>` in an agent prompt is the absolute path of `rule_chain.py`. Run every command from the lane root.

The lane's rule documents are `CLAUDE.md` and the paths its `## Lane` block declares in `SAID.scope-mounts:` (a path ending `/` is a folder, read for its `.md` files; any other path is that file; `none` is `CLAUDE.md` alone). With no such key they are `CLAUDE.md` and the default folders `<docs-root>/adr/`, `<docs-root>/ux/` and `<docs-root>/qa/`, those that exist; a declared key replaces the default. A document the handoff names outside them joins them for this refine. The script reads the key and lists the documents; never list, add or leave out a document yourself.

Run `mkdir -p <folder of output-path>`, then `$CHAIN size --lane . --handoff <handoff-path> --manifest <folder of output-path>/mounts.md`, and keep its lines for Step 3.

- Exit 3 -> STOP: the lane declares no `SAID.scope-mounts` and has none of the default folders. Relay its lines: the lane declares `SAID.scope-mounts: [<path>, ...]` in its `## Lane` block or holds one of `<docs-root>/adr/`, `ux/`, `qa/`. Nothing is refined until then.
- Exit 2 -> BLOCK with its lines (a declared path is missing, outside the lane or under a work folder).
- `size: small` -> one agent reads the lane's rules whole: go to Step 2.
- `size: large` -> run the rule chain, Step 2L, in place of Step 2. Never decide the size yourself.

On a large lane two heading passes and the silence pass sort the rule sections the cards keep into the zone (the sections that bear on the handoff's decisions) and the band (step 5). The zone is read whole twice, `zone-1` in document order and `zone-2` in reverse order, and the band once, `band-1` (step 6), each reading by readers who never see another reading. The script joins the tables.

## Step 2L: The rule chain (large lane)

A script fixes what is read; an agent gives a verdict on every unit; the script proves that no unit is missing and no verdict is dropped. Never write, edit or repair a file that the script or an agent writes. Never use the Write or Edit tool on a file of the chain folder: a step that saves a check's output as `<file>` runs that check again with `> <file>`. Never skip a step. Start no agent in the background; wait for every agent of a step before the next command. A command that exits 2 -> BLOCK with the lines it printed and stop. No command runs after one that exits 2: put the commands of a step in one Bash call only when `&&` joins them, else give each its own call.

Names, settled once before the first command and kept to the end:

- `$H` — the handoff path from the lane root.
- `$RUN` — the chain folder. When `<folder of output-path>` holds no `chain-<n>` folder, `$RUN` is `<folder of output-path>/chain-1`. Otherwise take the one with the highest `<n>` and run `$CHAIN status . <folder of output-path>/chain-<n> --handoff $H --budget 92000`, with `--hint <scope-hint>` when the operator gave one. It writes `status.txt` in that folder. Its first line is the answer, whatever its exit code (`blocked at` exits 1, `new chain` exits 3); only `size` exiting 3 is the no-rule-folder STOP. Read the first line:
  - `go on at <k>` -> `$RUN` is that folder. Run each line it prints as `run first: <words>` as `$CHAIN <words> --handoff $H`, in order. Then run step `<k>` from its first command and every step after it as written, with one change: start an agent only when the file it writes is not there (a reader's round-2 file included); a file already there goes to the step's check as if its agent had just written it.
  - `blocked at <k>: ...` -> BLOCK with its lines.
  - `done` -> `$RUN` is that folder; go to step 12.
  - `new chain: <reason>` -> `$RUN` is `chain-<n+1>`; give the reason in Step 3.

  A new `$RUN` (`chain-1`, or `chain-<n+1>`): create it with `mkdir`, then `cp <folder of output-path>/mounts.md $RUN/mounts.md`. Never delete, edit or reuse a file an earlier call wrote: a command that would write a file otherwise sets the old one aside as `<name>.failed-<k>`, and a chain folder whose inputs changed stands as it is.
- `$CARDS` — `<docs-root>/rule-index`, the folder of the lane's cards. The cards are lane files: two builds, `cards-a.tsv` and `cards-b.tsv`, written by step 2, committed by the operator, carded again only for a section whose text changed.

Agent prompts name every path from the lane root. Every command that reads the lane's rule documents carries `--handoff $H`, as written below.

1. **Cut.** `$CHAIN cut . $RUN/pieces.tsv --handoff $H`.

2. **Cards.** For each build `x` of `a` and `b`, independently:
   - `$CHAIN card-portions . $RUN/pieces.tsv $RUN/cards-x --cards $CARDS/cards-x.tsv --handoff $H` (leave out `--cards $CARDS/cards-x.tsv` while that file does not exist). It prints `nothing to card` -> build `x` is fresh. Otherwise it prints one `portion-r<n>` line a portion folder.
   - Start one `said:scope-card-writer` agent per portion folder printed, the writers of both builds in one assistant message, each with exactly this prompt (`<p>` the portion folder):

     ```
     Task: write the cards of one portion.
     - portion: <p>/portion.tsv
     - sections: <p>/sections.tsv
     - section items: <p>/section-items.tsv; pieces: <p>/pieces.tsv
     - write: <p>/cards.tsv
     - check command: python3 -I -B <script> cards <p> --lane .
     ```

   - Run each check command yourself. Exit 1 -> save its output as `<p>/cards-faults.txt` and start that writer once more with the same prompt and the line `- round 2: the check exited 1; its faults: <p>/cards-faults.txt. Fix cards.tsv, then run the check command again.` Exit 1 again -> BLOCK with the faults.
   - `mkdir -p $CARDS`, then `$CHAIN cards-join . $CARDS/cards-x.tsv <every portion folder of build x> --keep $CARDS/cards-x.tsv --handoff $H` (no `--keep` while the file did not exist).
   - `$CHAIN cards-fresh . $CARDS/cards-a.tsv --handoff $H` and `$CHAIN cards-fresh . $CARDS/cards-b.tsv --handoff $H` must each exit 0. Exit 1 -> BLOCK with its lines.

3. **Kinds.** `$CHAIN cards-agree . $CARDS/cards-a.tsv $CARDS/cards-b.tsv $RUN --handoff $H`. A section is left out only where both builds say `no-rule`. Exit 1 -> BLOCK with its lines.

4. **Decisions.** Start one `said:scope-decision-lister` agent with exactly this prompt:

   ```
   Task: list the decisions of the handoff.
   - handoff: <$H>
   - run folder: <$RUN>
   - check command: python3 -I -B <script> decisions <$H> <$RUN> --docs <$RUN>/pieces.tsv
   ```

   Run the check command yourself. Exit 1 -> save its output as `$RUN/decisions-faults.txt` and start the lister once more with the same prompt and the line `- round 2: the check exited 1; its faults: <$RUN>/decisions-faults.txt. Fix the three files, then run the check command again.` Exit 1 again -> BLOCK.

5. **Heading passes, the silence pass, the code audit and the tiers.**
   - `$CHAIN decisions-in $RUN` (copies `decisions.tsv` into `read-1/` with `made-on.tsv`, the hashes of the list, `kinds.tsv` and both card sets; when `read-1/` was made on another list, kinds file or card set, it first sets aside every output of steps 6 to 11 as `<name>.failed-<k>`, so each of those steps is made again)
   - `$CHAIN sections . $RUN/pieces.tsv $RUN/sec`
   - **Heading passes.** `mkdir -p $RUN/pass-1 $RUN/pass-2`, then `cp $RUN/sec/sections.tsv $RUN/pass-1/sections.tsv`, `$CHAIN reverse $RUN/sec/sections.tsv $RUN/pass-2/sections.tsv`, and `cp $RUN/decisions.tsv` into both folders. Start two `said:scope-first-pass` agents, one a folder, in one assistant message, each with exactly this prompt (`<p>` its folder):

     ```
     Task: the first pass.
     - handoff: <$H>
     - decisions: <p>/decisions.tsv
     - sections: <p>/sections.tsv
     - write: <p>/subjects.tsv
     - check command: python3 -I -B <script> subjects <p>
     ```

     Run each check command yourself. Exit 1 -> save its output as `<p>/subjects-faults.txt` and start that pass once more with the same prompt and the line `- round 2: the check exited 1; its faults: <p>/subjects-faults.txt. Fix subjects.tsv, then run the check command again.` Exit 1 again -> BLOCK with the faults.
   - **Silence pass.** `$CHAIN pair-silent $RUN` (writes `$RUN/pass-3/sections.tsv`: every rule section with no `touched` and no `out` row of either pass, each with its card line as a sixth field, and `$RUN/pass-3/decisions.tsv`). It prints `silent 0` -> make an empty `$RUN/pass-3/subjects.tsv` with `: > $RUN/pass-3/subjects.tsv` and run `$CHAIN pass-3 $RUN --round 1`. Otherwise start one `said:scope-first-pass` agent with exactly the prompt of the heading passes, `<p>` = `$RUN/pass-3`, then run `$CHAIN pass-3 $RUN --round 1` yourself. For each round `k`:
     - exit 0 -> the silence pass is closed: no listed section is silent;
     - exit 1 -> save its output as `<p>/subjects-faults-r<k>.txt` and start the pass once more with the same prompt and the line `- round <k+1>: the check exited 1; its faults: <p>/subjects-faults-r<k>.txt. Fix subjects.tsv, then run the check command again.`, then `$CHAIN pass-3 $RUN --round <k+1>`;
     - exit 3 -> STOP with its lines: a round that added no row, or a section still silent after round 3. Never a round 4.
   - **Code audit first.** Run step 10 (Code audit) now, as written: it reads the handoff and the code, not the table, which does not exist yet. When the chain reaches step 10, `$RUN/audit/dirs.tsv` is there: do not run `audit-dirs` again; run only `audit-check` on every report as step 10 says.
   - **Tiers.** `$CHAIN tiers $RUN` (writes `$RUN/join/zone.tsv`: the rule sections touched by a heading pass, with the decisions they name; `$RUN/join/band.tsv`: the rule sections touched by the silence pass; `$RUN/join/left-out.tsv`: every other section with its reason line, a rule section its `out` lines, a no-rule section its card line).

6. **Zone readings and the band reading.** `$CHAIN readings $RUN 2` (the chain's record of K for the zone, `readings.txt`). Three readings, each `<t>` with its list and order: `zone-1` over `$RUN/join/zone.tsv` in document order, `zone-2` over `$RUN/join/zone.tsv` in reverse order, `band-1` over `$RUN/join/band.tsv` in document order. For each: `mkdir -p $RUN/zsec-<t>`; for document order `cp $RUN/sec/sections.tsv $RUN/zsec-<t>/sections.tsv`, for reverse order `$CHAIN reverse $RUN/sec/sections.tsv $RUN/zsec-<t>/sections.tsv`; `cp $RUN/sec/section-items.tsv $RUN/zsec-<t>/section-items.tsv`; `$CHAIN zone . $RUN/pieces.tsv $RUN/zsec-<t> <its list> $RUN/<t> --selected --budget 92000`; `cp $RUN/decisions.tsv $RUN/<t>/decisions.tsv`.

   Start one `said:scope-zone-reader` agent per part `r<n>` of every reading, all in one assistant message, each with exactly this prompt (`<z>` = `$RUN/<t>`):

   ```
   Task: read portion r<n>.
   - handoff: <$H>
   - decisions: <z>/decisions.tsv
   - portion: <z>/portion-r<n>.tsv (unit id, path, first line, last line, heading)
   - zone file: <z>/zone-r<n>.md
   - write: <z>/read-r<n>.tsv
   ```

   Never name a file of another reading to them. Then `$CHAIN coverage . $RUN/<t>` on each. Exit 1 -> start once more, in one assistant message, the reader of every part that `<z>/gaps.tsv` names in its first field, with the same prompt, its first line `Task: read portion r<n>, round 2: answer only the gaps.`, its last line replaced by `- gaps: <z>/gaps.tsv (only its lines of portion r<n>)` and `- write: <z>/read-r<n>.r2.tsv`. Run `coverage` again; exit 1 again -> BLOCK with the lines of `gaps.tsv`.

7. **Join, holes and the line check.**
   - **Join.** `$CHAIN tier-join $RUN` (writes `$RUN/table-0.tsv`: zone-1's rows stand; a unit zone-1 found nothing in takes zone-2's rows; band-1's rows are added as they are).
   - **Holes.** `$CHAIN holes . $RUN --budget 92000` (on `table-0.tsv`, the zone and the band). A hole is a unit no reading gave a row, in a section (one heading of one document) where at least two other units carry a rule row on one same decision; `$RUN/holes/holes.md` gives one block a section: its heading, the rows the other units of the section carry, then each hole unit with its lines. The script deals the blocks into parts, `$RUN/holes/holes-<part>.md`, and prints them (`part <part>: ...`). No hole -> `$CHAIN hole-join . $RUN`. Holes -> start one `said:scope-zone-reader` agent for each part, all in one assistant message, each with exactly this prompt:

     ```
     Task: read portion holes-<part>, the hole round: answer only the holes.
     - handoff: <$H>
     - decisions: <$RUN>/decisions.tsv
     - zone file: <$RUN>/holes/holes-<part>.md
     - round: each block of the zone file is one section: its heading, the rows the other units of the section carry, then each hole unit with its lines. Judge each hole unit's lines as on any decision. Answer each hole unit once: its rows (on any decision of decisions.tsv) or one `none` row.
     - write: <$RUN>/holes/read-<part>.tsv
     ```

     Then run `$CHAIN hole-join . $RUN` yourself: it checks the read file of every part and writes `$RUN/table.tsv`, the table of the readings with the hole rows in place. Exit 1 -> start the reader of each part the faults name once more, all in one assistant message, with the same prompt and the line `- round 2: the check exited 1; its faults: <$RUN>/holes/faults.txt. Answer only the holes of your part it names; write <$RUN>/holes/read-<part>.r2.tsv.`, then run `hole-join` again. Exit 1 again -> BLOCK with its faults.
   - **Line check.** `$CHAIN line-check $RUN`: every rule section has a line, an `out` line of a pass in `join/left-out.tsv` or each of its items answered (a row or `none`) in `table.tsv`; every no-rule section its card line. Exit 1 -> BLOCK with its lines.

8. **One look and the confirm look.** `$CHAIN pairs-subject . $RUN` (writes `subject-pairs.tsv`: the pairs whose two sections share subject words), then `$CHAIN pairs $RUN --lane . --handoff $H` (writes `checks.tsv` and `pairs.tsv`). It prints `against rows 0` -> no look runs; go to 9. Otherwise:
   - `$CHAIN look-copy $RUN $RUN/look-a`, then `$CHAIN pairs-deal $RUN/look-a $RUN/look-a/parts --cap 60` (it prints its parts, `part-<k>: ...`, at most 60 pairs a part).
   - For every part `<k>`, start `said:scope-exception-check` on `$RUN/look-a/parts/part-<k>`, the looks of all parts in one assistant message, each with exactly this prompt (`<l>` its part folder):

     ```
     Task: the second look.
     - handoff: <$H>
     - decisions: <l>/decisions.tsv
     - table: <l>/table.tsv
     - checks: <l>/checks.tsv
     - pairs: <l>/pairs.tsv
     - write: <l>/look.tsv and <l>/pairs-look.tsv
     ```

   - Run `$CHAIN pairs <l> --lane . --handoff $H` yourself on every part folder; the looks never run a script. Exit 1 -> run it again as `$CHAIN pairs <l> --lane . --handoff $H > <l>/pairs-faults.txt` and start that look on that part once more with the same prompt and the line `- round 2: the check exited 1; its faults: <l>/pairs-faults.txt. Fix look.tsv and pairs-look.tsv.` Exit 1 again -> BLOCK with the faults.
   - `$CHAIN pairs-merge $RUN/look-a $RUN/look-a/parts`, then `$CHAIN pairs $RUN/look-a --lane . --handoff $H`; exit 1 -> BLOCK with its output.
   - `cp $RUN/look-a/look.tsv $RUN/look-a/pairs-look.tsv $RUN/`, then `$CHAIN pairs $RUN --lane . --handoff $H`; exit 1 -> BLOCK with its output.
   - **The confirm look.** `$CHAIN confirm-items $RUN . --handoff $H` (writes `$RUN/confirm/C<nn>.md`, one item a row `look.tsv` keeps, and `$RUN/confirm/items.tsv`). It prints `items 0` -> go to 9. Otherwise start one `said:scope-confirm-look` agent with exactly this prompt, every item file `C<nn>.md` of `$RUN/confirm` named in the order of their numbers:

     ```
     Task: the confirm look.
     - items, in this order: <$RUN>/confirm/C01.md, <$RUN>/confirm/C02.md, ...
     ```

   - Hand its reply, whole and unchanged, to the script in one Bash call: `$CHAIN confirm-in $RUN <<'CONFIRM_REPLY'`, the reply on the next lines, then a line `CONFIRM_REPLY` (it keeps the reply as `$RUN/confirm/answer-<k>.txt` and writes `$RUN/confirm/confirm.tsv` from its answer lines). Then `$CHAIN confirm-check $RUN`. Exit 1 -> run it again as `$CHAIN confirm-check $RUN > $RUN/confirm/confirm-faults.txt`, start the agent once more with the same prompt and the line `- round 2: your answer failed its check; its faults: <$RUN>/confirm/confirm-faults.txt. Answer every item again, one line each.`, hand its reply to `confirm-in` as before and run `confirm-check` again. Exit 1 again -> BLOCK with the faults.
   - The verdicts reach the draft through `draft-in` (step 11): a kept row the confirm look says `does not hold` is dropped, a `cannot tell` row becomes a question of the draft, a `holds` row stays a conflict.

9. **Questions.** `$CHAIN questions $RUN` (writes `questions.tsv`: the `asks` rows of the table). It prints `questions 0` -> go to 10. Otherwise:
   - `mkdir -p $RUN/qlook-a $RUN/qlook-b`; `cp $RUN/questions.tsv $RUN/decisions.tsv $RUN/qlook-a/` and the same into `$RUN/qlook-b/`; then `$CHAIN questions-deal $RUN $RUN/qlook-a/parts` and `$CHAIN questions-deal $RUN $RUN/qlook-b/parts --reverse` (each prints its parts, at most 70 questions a part, so one part a look up to 70 questions; the two lists are the same; `--reverse` writes each part's rows in the opposite order).
   - For every part `<k>`, start `said:scope-question-kind` on `$RUN/qlook-a/parts/part-<k>` and `said:scope-question-kind` on `$RUN/qlook-b/parts/part-<k>`, the looks of all parts in one assistant message, each with exactly this prompt (`<q>` its part folder):

     ```
     Task: the question look.
     - handoff: <$H>
     - decisions: <q>/decisions.tsv
     - questions: <q>/questions.tsv
     - write: <q>/qlook.tsv
     ```

   - Run `$CHAIN question-check <q> --look A --lane . --handoff $H` yourself on every part of `qlook-a` (`--look B` on every part of `qlook-b`); the looks never run a script. Exit 1 -> run it again with `> <q>/qlook-faults.txt` and start that look on that part once more with the same prompt and the line `- round 2: the check exited 1; its faults: <q>/qlook-faults.txt. Fix qlook.tsv.` Exit 1 again -> BLOCK with the faults.
   - `$CHAIN questions-merge $RUN/qlook-a $RUN/qlook-a/parts` and `$CHAIN questions-merge $RUN/qlook-b $RUN/qlook-b/parts`, then `$CHAIN question-join $RUN/qlook-a $RUN/qlook-b $RUN/questions-join.tsv --lane . --handoff $H` (a row stays a question when both looks say `choice`; a row only one look says `choice` on is not asked: it is named in its decision's question frame when the decision has one, otherwise listed as one look of two; any other row becomes a rule to follow or a rule the handoff follows when a look says `rule-settles` or `answered` (look A's kind when the two differ), and a rule read and judged not to bear when both say `no-bear`; the script writes the four lists with both grounds directly before section D).

10. **Code audit.** First, if `$RUN/audit/dirs.tsv` is there (made in step 5), run only the audit-check line below. Otherwise `$CHAIN audit-dirs . $RUN --handoff $H` (with the operator's scope-hint: add `--hint <scope-hint>`). It prints one line a directory the handoff names: `A<n>` with the directory to audit, or `-` with `absent` or `ambiguous` (no audit; the draft says so), or `audit: no directory named` -> go to 11. Start one `said:scope-audit` agent for every `A<n>`, all in one assistant message, each with exactly this prompt:

    ```
    Task: audit one directory.
    - inputs: $RUN/audit/A<n>.task.md
    - write: $RUN/audit/A<n>.md
    ```

    Run `$CHAIN audit-check $RUN/audit A<n> --lane .` yourself on every report. Exit 1 -> save its output as `$RUN/audit/A<n>-faults.txt` and start that audit once more with the same prompt and the line `- round 2: the check exited 1; its faults: $RUN/audit/A<n>-faults.txt. Fix the report.` Exit 1 again -> BLOCK with the faults.

11. **Draft.** `$CHAIN draft-in $RUN $RUN/draft --lane .` (the drafter's folder: the table without the split rows and the rows that are no longer questions, the looks, the split rows, the question looks' join, the audits, the list of rule documents read and the question frames `frames.md`, one a decision the owner must answer). Start one `said:scope-chain-drafter` agent with exactly this prompt (`<d>` = `$RUN/draft`):

   ```
   Task: the scope draft.
   - handoff: <$H>
   - decisions: <d>/decisions.tsv
   - decision pairs: <d>/decision-pairs.tsv
   - table: <d>/table.tsv
   - look: <d>/look.tsv
   - pairs look: <d>/pairs-look.tsv
   - audits: <d>/audit/
   - frames: <d>/frames.md
   - write: <d>/scope.md, <d>/d-items.tsv
   - check command: python3 -I -B <script> trace <d> && python3 -I -B <script> carried <d> --d-items
   ```

   Leave out the `look` and `pairs look` lines when step 8 ran no look. Then run `$CHAIN trace $RUN/draft` and `$CHAIN carried $RUN/draft --d-items` yourself. `carried` exits other than 0 -> save its output as `$RUN/draft/carried-faults.txt` and start the drafter once more with the same prompt and the line `- round 2: the check exited <code>; its output: <d>/carried-faults.txt. Fix the draft or d-items.tsv, then run the check command again.`, then run `trace` and `carried` again. Not 0 again -> BLOCK with its lines.

12. **Hand over.** `cp $RUN/draft/scope.md <output-path>`. Go to Step 3.

## Step 2: Spawn the agent (small lane)

Spawn `said:scope-refine-agent` via the Agent tool with the resolved inputs. The agent is generic — pass everything in the prompt; it has no memory of this conversation.

Example spawn prompt:

```
Run Phase 1 (Scope) refinement.

- handoff-path: docs/working/<wip-path>.md
- output-path: docs/working/scope-refine/scope.md
- scope-hint: (none)
- rule-documents: docs/working/scope-refine/mounts.md
- audit-shape: ${CLAUDE_SKILL_DIR}/../../agents/scope-audit.md
- Precedent (said:retrieval): <the findings of Step 1b, or: no precedent found>

Read the handoff in full and run every stage of your procedure. Write the refined draft to output-path.

Reply with the section of conflicts and open questions of the draft, verbatim, so the operator can resolve.
```

`rule-documents` is the file `size` wrote in Step 1c (`<folder of output-path>/mounts.md`). With a probe procedure add the line `- probe-procedure: <path>` after `scope-hint`. `audit-shape` is the file of the `said:scope-audit` agent of this plugin: its `## Report shape` is the shape of every audit report. The agent runs its own Stage 2 audits, by `said:scope-audit` agents or inline, as its text says; you do not manage them.

Run the agent and wait for its reply before you answer: do not start it in the background, and do not end your turn or report that it is still running.

## Step 3: Present the output

After the agent returns (small lane) or step 12 of the chain (large lane):

- **scope.md path** — confirm where the file landed.
- **Size** — the lines `size` printed: the declared paths, the folders no path reaches (`not read:`), any document added for this handoff, and the size line.
- **Rule chain** — only on a large lane: the run folder `$RUN`, and the lines printed by `cards-agree`, the two `subjects` checks, `pair-silent`, `tiers`, every `coverage`, `tier-join`, `hole-join` and `line-check`, then `confirm-check`, `draft-in` and the last `carried`, verbatim. When step 2 carded any portion, say that `$CARDS/cards-a.tsv` and `$CARDS/cards-b.tsv` are lane files to commit, so the next refine cards only the sections whose text changed. On a large lane the retrieval findings of Step 1b go here, beside the draft. When the chain went on from an earlier call: the first line of `status`, its `run first:` lines, and that steps 1 to `<k>`-1 are the earlier call's (their lines are in `status.txt`).
- **Probes** — when no probe procedure was passed: one line saying that no live probe ran. On a large lane with a probe procedure passed: one line saying that the chain runs no live probe and the procedure was not run.
- **§D — Conflicts and open questions** — print the section verbatim. Each entry names a conflict (handoff vs contract divergence) or an open question (handoff residual or checklist gap).
- **Recommended next step** — depends on §D state:
  - **§D empty** -> "Phase 1 (Scope) is done. Act's Architect step starts. Run `/said:architect` when ready, or build the spec interactively per `docs/features/template.md`."
  - **§D non-empty** -> "Phase 1 (Scope) is BLOCKED on §D. Resolve each item, then either re-run `/said:scope-refine` to regenerate, or hand-edit `scope.md` so §D is empty before proceeding to `/said:architect`."

DO NOT silently resolve §D items. The agent surfaces conflicts in §D deliberately; this skill carries them through to the operator unchanged. When unattended (a subagent with no operator, or a top-level run with no operator turn to answer), an operator question (a §D item) is never resolved, defaulted, or emptied: it routes into the announce-once-then-hold class -- the `goal: stop` line (the line the `said` and `flow` skills print) carries `OPERATOR-QUESTION-HELD` -- exactly as `said`/`flow` hold an operator question, then holds.

## Step 4: Do NOT auto-fix or auto-architect

The skill stops after presenting §D. If the operator wants conflicts resolved or wants the spec written, that's a separate explicit invocation. Phase 1 only writes `scope.md`; it does NOT write `spec.md`, task lists, or code.

## Anti-patterns

- **Don't merge with `/said:scope-grill`.** Different cases (Case 1 = handoff exists, Case 2 = thin idea), different drivers (this spawns the agent; grill is interactive and agent-less), different content shapes inside §A/§B/§C/§D. Conflating them produces shape-incoherent `scope.md`.
- **Don't auto-resolve §D.** Conflicts and open questions are operator questions by design. Carry them visibly to the operator; never pick the side yourself.
- **Don't write `spec.md`.** This is Phase 1. `spec.md` is the Architect step's. The earned-design-decision splits them deliberately.
- **Don't ask the operator the full input questionnaire** when most inputs resolve from path / branch / git state. Reach for an `ASK` only on the gap that genuinely can't be derived.
- **Don't size the lane or run a chain step by hand.** `size` decides small or large. On a large lane every step of Step 2L runs as written: never pick the sections to read, never write or repair a table, a look, a card or a draft yourself, never drop a step whose check failed. A gap the script names goes back to its agent at most once; then BLOCK.
- **Don't show a reader another reading.** The readers of each `zone-<k>` see only their zone part, the handoff and the decisions.
- **Don't pick the rule documents.** They are `CLAUDE.md` and the rule folders as `size` lists them: the lane's `SAID.scope-mounts:` paths, or with the key absent the default folders; never add the rest of the docs root.
- **Don't skip the existence check** on operator-given handoff paths. Spawning the agent with a non-existent path wastes a parallel-audit run and confuses Stage 1.
- **Don't reuse a prior `_branch-state.md`** across runs. Branch state evolves; each branch-synth invocation overwrites the file with fresh git output.
