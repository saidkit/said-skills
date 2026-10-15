---
name: setup
description: >
  SAID lane CONFIGURATION doctor. Inspects an already-present lane's `## Lane` block, its
  required `CLAUDE.md` sections, reviewer resolvability, and docs skeleton against a shipped
  well-formed-lane schema, plus one environment item: the statusline the context checkpoint
  reads. Reports a ranked health ledger read-only; on `--fix` repairs configuration + applies
  known-safe defaults, proposing on genuine choices; `statusline` installs the statusline with
  consent. Triggered ONLY by "/said:setup [--fix] [--lane <name>]" or "/said:setup statusline". Use it
  whenever the operator wants to validate / check / audit / repair a lane's SAID configuration:
  are the axes current, why does `impl` HALT on this lane, is the `## Earned rules` heading
  present, do the declared reviewers resolve, is the `## Lane` block stale or malformed, is the
  context checkpoint inactive. NOT creating a lane or scaffolding one from scratch; NOT
  `said:status` (reports where a FEATURE sits in the phase chain); NOT `said:review-qa`
  (implementation-hygiene gate). This skill governs exactly two things: lane CONFIGURATION and the
  statusline install; no other `settings.json` key.
---

# said:setup, the SAID lane configuration doctor

Governs the CONFIGURATION of a lane that already exists: its `## Lane` axes, defaults, required
`CLAUDE.md` sections, reviewer resolvability, and docs skeleton. It reports what is wrong and, on
`--fix`, repairs what it safely can, composing `said:install` for structural gaps. Installing a
lane from scratch is `said:install`'s job, not this skill's.

## Contract, holds every run

- **Read-only by default.** A bare `/said:setup` inspects and reports; it writes nothing. Two
  writer paths exist, both consent-gated: `--fix` (lane configuration) and `statusline` (the
  statusline install: `settings.json` `statusLine` and `~/.claude/said-statusline.sh`, nothing else).
- **The checker script owns the verdicts.** `setup_check.py` (beside this file) is the
  deterministic oracle; render what it emits, never override a verdict in prose. A wrong verdict
  is a bug to fix in the script or the schema, not a value to hand-edit.
- **Hard exit at the report** (read-only). End with the ledger; never proceed into a phase, never
  auto-invoke another skill.
- **Run-when-asked, not a gate.** This skill is invoked on demand; it is never wired into the SAID
  cycle as an always-on gate.
- **Propose, do not guess.** On any finding whose repair needs a decision the schema cannot settle
  (which surface? which reviewers?), state the proposal and stop; never write a chosen value the
  operator did not confirm.

## Invocation

- `/said:setup` , read-only health ledger for the current lane.
- `/said:setup --lane <name>` , target one lane in a multi-lane repo.
- `/said:setup --fix [--lane <name>]` , apply repairs + known-safe defaults (writer path).
- `/said:setup statusline` , install the statusline the context checkpoint reads (writer path).

## Step 0, resolve the lane (declaration-first)

The lane root is the directory holding the `## Lane` block's `CLAUDE.md`; every `SAID.<axis>:`
path resolves from it. Resolve, and state what resolved:

- Single lane , the lane root is the current repo root (its `CLAUDE.md` carries the `## Lane`
  block).
- Multi-lane , take the registry rows WHOLE from
  `python3 ${CLAUDE_SKILL_DIR}/../status/said_status.py --registry --root <root>`
  (echo its count; on `refused:` report it, select no row); `--lane <name>` selects one row, else
  default to the lane whose root is the current directory. Pass the selected lane's root to the checker.

## Step 1, run the checker

`setup_check.py` sits beside this SKILL.md and owns the mechanical evaluation. When `python3` is
present, run it, do not reconstruct by hand:

```
python3 <skill-dir>/setup_check.py --root <lane-root> [--json]
```

- It reads the lane's `## Lane` block, evaluates it against `references/lane-schema.json` (the
  shipped well-formed-lane contract, read WHOLE), and prints a per-item ledger: every config item
  maps to `ok` / `stale` / `missing` / `unresolvable`, grouped `BLOCKER` / `STALE` / `ADVISORY`.
- Exit code: non-zero iff at least one `BLOCKER` is present.
- `--json` emits the findings as structured data, reason over it for a `--fix` plan.
- **Show the ledger verbatim.** The columns are the script's; re-typing them reintroduces the
  drift the script exists to remove.
- **No `python3`?** Read `references/lane-schema.json` and evaluate each item against the lane
  block by hand (key-grep each `SAID.<axis>:`; check the required section headings; resolve each
  declared reviewer against the plugin's Checker set), and say you did so.

## Step 2, read the ledger

The script gives the facts; add the reading a script cannot:

- **BLOCKER** , the lane is not usable as-is: a missing `SAID.surface:` / `SAID.profile:` or a
  missing `## Earned rules` heading HALTs a consumer; a `SAID.reviewers:` entry that resolves to
  no Checker (or an empty `reviewers: []` on a surface-bearing lane) is a gate that reports PASS
  while running nothing. Name what each BLOCKER breaks.
- **STALE** , a withdrawn or drifted declaration a current lane should not carry (a retired axis, a
  duplicated key, prose between keys). Name the current form (a `write:` line gives it:
  `SAID.mounts: [a/]`).
- **ADVISORY** , a recommended-but-not-fatal gap (a missing skeleton dir, an absent optional axis,
  lanes beneath a root with no registry).

## The statusline step

`/said:setup statusline` runs `setup_statusline.py` (beside this file); the script owns the write.
1. Run `python3 <skill-dir>/setup_statusline.py --apply` : it prints the current and the new
   `statusLine` and the wrapper copy, writes nothing, and exits 3 (plan only, not an error). Show
   that output to the operator verbatim. Never pass `--yes` on this first run. If `settings.json` is
   unparseable or the wrapper source is missing it aborts instead (exit 1, no plan, nothing written):
   show that message and stop.
2. Ask the operator ONE question: confirm that exact change, yes or no. The question ends your turn:
   stop and wait; the answer arrives in the operator's next message; never answer it for the operator.
   No consent -> say nothing was written and stop. `--yes` is never run without the operator's
   explicit answer to that question.
3. Only after the operator confirms, run it again with `--apply --yes`: it backs up `settings.json`
   (an absent `settings.json` is created), copies the version-stable wrapper, sets `statusLine` only,
   re-parses, and restores on failure. Show what it wrote.
4. Then re-run `--check` and show its `statusline` row: that row is the proof of the install.

Never edit `settings.json` with any other tool or by hand; the script is the only writer.
The read-only ledger's `statusline` row comes from `setup_statusline.py --check` (never BLOCKER).

## The `--fix` dispositions

`--fix` walks the findings and, per finding, does exactly ONE of four things:

- **Native config write** , a configuration-value repair the lane clearly needs: refresh a stale
  axis to its current key and value shape (`SAID.mounts: [a/]`; copy the line the checker
  prints), add a missing scalar with its schema-stated default, normalize the
  block's shape; write a `SAID.lanes` row's `write:` line into the root's `## Lane` block,
  replacing `SAID.lanes: []`, else as a new key line (no `CLAUDE.md` or no block: compose `said:install` first). Write it,
  then re-run Step 1 to confirm the finding cleared.
- **Compose `said:install`** , a STRUCTURAL gap (missing docs skeleton, no `## Lane` block at all,
  the plugin not wired). Invoke `said:install` to create it; never hand-roll the scaffolding it
  owns. Where `said:install` is not available, PROPOSE "run `said:install`" and leave the gap,
  never a half-written scaffold.
- **Statusline step** , a `statusline` row that is not `ok`: run the statusline step above, with
  its consent gate; never write `settings.json` without the operator's confirmation.
- **Propose only** , a genuine choice the schema cannot settle (which `surface` medium? which
  `reviewers` for a surface-bearing lane? a `SAID.lanes:` registry in another shape: state its
  one-line form, never write it). State the proposal with its options and stop; write
  nothing until the operator confirms.

Apply a default ONLY where the schema's remediation states one unambiguously; otherwise propose.
After a `--fix` pass, re-run the checker and show the updated ledger.

## Anti-patterns

- **Do not guess a discretionary value.** A choice the schema cannot settle is a proposal, never a
  silent write.
- **Do not run as an always-on gate.** This is a doctor the operator invokes, not a cycle step.
- **Do not confuse the surface with `said:status`.** That skill reports a FEATURE's phase; this one
  reports whether the LANE is well-formed.
