---
name: review-feature
description: >
  SAID Inspect, its first read: the feature-reviewer's read of one feature's sources against its build, once per
  round, at the Act->Inspect boundary and before `review-qa`. Checks that the gate record reads the read owed, builds
  the brief, spawns the `said:feature-reviewer` agent cold, files its verdict and writes its rows into the feature's
  gate record through the bundled scripts. Triggered ONLY by the explicit command
  "/said:review-feature <feature-id> --base <rev> --capture-ref <file|none> [--ledger <file>]... [--root <lane-root>]",
  issued by `said` and `flow` at Inspect or by the operator. NOT for a task close (that is `/said:review-qa`), NOT
  for reading a gate record (`review-qa` and `accept` read it), NOT for a run outside the session (that is
  `board/inspect_run.py`, this skill's headless form).
---

# review-feature: the feature-reviewer's read

## Contract

1. **One read per round, only when owed.** Spawn the reader only after `review_feature.py prepare` prints `review-feature: ready`. A `current` record is never read again, and a recorded FAIL is not read again: its FAIL rows go to `/said:add-task`.
2. **The scripts write; this skill never does.** The brief is the one `prepare` printed, passed verbatim, and on the one re-spawn passed verbatim plus the refusal line (Step 3). `review_feature.py file` runs the row writer and files the verdict only when the writer accepts it: rows are never typed, and the verdict file and the gate record are never edited by hand.
3. **The reader is cold and the only judge.** Spawn `said:feature-reviewer` cold with the printed brief alone, and on the one re-spawn its refusal line (Step 3); this skill judges nothing about the build.
4. **One outcome line ends every run** (**Outcome**); the caller routes it.

## When this fires

- `/said:review-feature <feature-id> --base <rev> --capture-ref <file|none> [--ledger <file>]... [--root <lane-root>]`
  - `--base`: the feature's base commit. `--capture-ref`: a non-empty capture file in the feature's `SAID.working:` dir, named relative to it, never the gate record; on a feature with no capture, the literal `none` (the reader then writes its Captures group as `none`).
  - `--ledger`: one per ledger file the spec cites under `## Context to load`; the script adds the working dir's `rulings.md` and `scope.md` itself when they exist.
  - `--root`: the lane root, the directory whose `CLAUDE.md` holds the lane's `## Lane` block; default the current lane's.

## Step 1 - Prepare

Run `python3 ${CLAUDE_SKILL_DIR}/review_feature.py prepare <feature-id> --root <lane-root> --base <rev> --capture-ref <file|none> [--ledger <file>]...`. Route on its first line:

- `review-feature: current` -> end with `review-feature: current`.
- `review-feature: FAIL recorded (not read again)` -> end with `review-feature: FAIL`.
- `review-feature: owed (no read: <why>)` -> end with `review-feature: owed: no read: <why>`.
- `error: <why>` (exit 2) -> end with `review-feature: error: <why>`.
- `review-feature: ready` -> report its `estimate:` line, then Step 2.

## Step 2 - Spawn the reader

With the brief in hand, spawn `said:feature-reviewer` cold (the Agent tool, subagent type `said:feature-reviewer`) with the lines between `--- brief` and `--- end` as its whole prompt, verbatim. On a lane whose `SAID.surface:` is `doc` the brief carries `surface: doc`, and the reader answers for the `doc-editorial` id in the same verdict. Write its reply, unchanged, to a file in the session scratchpad: never into the working dir, never under the verdict file's name.

## Step 3 - File the verdict and write the rows

Run `python3 ${CLAUDE_SKILL_DIR}/review_feature.py file <feature-id> --root <lane-root> --reply <that file> [--ledger <file>]...` with the `--ledger` files of Step 1. It runs `gate_record_row.py --kind feature-review` over the reply, which validates the verdict and writes only the rows it produced, and files the reply only when the writer accepts it, at the `out:` path `prepare` printed, `<SAID.working:>/review-feature-<id>.md`, on a `doc` lane `<SAID.working:>/review-doc-editorial-<id>.md` (the name the reviewer gate reads), never both. A refused reply is not filed: it stays in the scratchpad file.

- **Exit 0:** the rows are written; its verdict line reads `feature-review: verdict | <PASS or FAIL> | not-read=<N>`. End with `review-feature: PASS, not-read=<N>` or `review-feature: FAIL, not-read=<N>`.
- **Exit 1:** nothing written; the writer printed its `feature review owed: <why>` line, or the reply had no verdict line; re-spawn the reviewer once with the same brief plus one last line, `Your last reply was refused by the row writer: <that line>. Keep the Output rules exactly.`, then this step; a second exit 1 ends with `review-feature: owed: <that line>`.
- **Exit 2:** an `error:` line; end with `review-feature: error: <that line>`.

A lane outside git has no HEAD to brief, so the read reads owed there (a known limit).

## Outcome

The last line of every run is one of:

- `review-feature: current` or `review-feature: PASS, not-read=<N>`: the caller goes on to `/said:review-qa <id>` and reports `not-read=<N>`.
- `review-feature: FAIL` or `review-feature: FAIL, not-read=<N>`: Inspect does not start; the caller sends each FAIL row of the verdict file to `/said:add-task <id>`.
- `review-feature: owed: <why>` or `review-feature: error: <why>`: the caller stops.

## Headless form

`python3 ${CLAUDE_SKILL_DIR}/../board/inspect_run.py <id> --root <lane-root> --base <rev> --capture-ref <file|none> --ledger <file>... [--yes <token>]` runs the same `prepare` and `file` code with the reader headless, then the gate recompute over every unit, the Covers read and the round. It runs the read only with `--yes <token>`, the token of the estimate it prints, passed on the operator's yes to that estimate, never on a grant; it refuses (exit 3) while another run holds the lane.

## Anti-patterns

- Typing a row, or editing the verdict file or the gate record.
- Briefing the reader with anything beyond the printed brief and its refusal line, or forking it with this session's context.
- Reading again over a `current` record or a recorded FAIL.
- Spawning from `said` or `flow` directly: they invoke this skill.
