---
name: setup
description: >
  SAID lane CONFIGURATION doctor. Inspects an already-present lane's `## Lane` block, its
  required `CLAUDE.md` sections, reviewer resolvability, and docs skeleton against a shipped
  well-formed-lane schema; reports a ranked health ledger read-only, and on `--fix` repairs
  configuration + applies known-safe defaults, composing `said:install` for structural gaps and
  proposing on genuine choices. Triggered ONLY by "/said:setup [--fix] [--lane <name>]". Use it
  whenever the operator wants to validate / check / audit / repair a lane's SAID configuration:
  are the axes current, why does `impl` HALT on this lane, is the `## Earned rules` heading
  present, do the declared reviewers resolve, is the `## Lane` block stale or malformed. NOT
  `said:install` (the structural-onboarding WRITER that creates a lane / installs the plugin /
  scaffolds the skeleton from scratch or a remote source); NOT `said:status` (reports where a
  FEATURE sits in the phase chain); NOT `said:review-qa` (implementation-hygiene gate). This skill
  governs lane CONFIGURATION and nothing else.
---

# said:setup, the SAID lane configuration doctor

Governs the CONFIGURATION of a lane that already exists: its `## Lane` axes, defaults, required
`CLAUDE.md` sections, reviewer resolvability, and docs skeleton. It reports what is wrong and, on
`--fix`, repairs what it safely can, composing `said:install` for structural gaps. Installing a
lane from scratch is `said:install`'s job, not this skill's.

## Contract, holds every run

- **Read-only by default.** A bare `/said:setup` inspects and reports; it writes nothing. `--fix`
  is the ONLY path that mutates a file.
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
- `/said:setup --fix [--lane <name>]` , apply repairs + known-safe defaults (the only writer path).

## Step 0, resolve the lane (declaration-first)

The lane root is the directory holding the `## Lane` block's `CLAUDE.md`; every `SAID.<axis>:`
path resolves from it. Resolve, and state what resolved:

- Single lane , the lane root is the current repo root (its `CLAUDE.md` carries the `## Lane`
  block).
- Multi-lane , read the `SAID.lanes:` registry WHOLE from the umbrella block; `--lane <name>`
  selects one row, else default to the lane whose root is the current directory. Pass the selected
  lane's root to the checker. (This mirrors how `said:status` resolves lanes.)

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
  duplicated key, prose between keys). Name the current form.
- **ADVISORY** , a recommended-but-not-fatal gap (a missing skeleton dir, an absent optional axis).

## The `--fix` dispositions

`--fix` walks the findings and, per finding, does exactly ONE of three things:

- **Native config write** , a configuration-value repair the lane clearly needs: refresh a stale
  axis to its current key, add a missing scalar with its schema-stated default, normalize the
  block's shape. Write it, then re-run Step 1 to confirm the finding cleared.
- **Compose `said:install`** , a STRUCTURAL gap (missing docs skeleton, no `## Lane` block at all,
  the plugin not wired). Invoke `said:install` to create it; never hand-roll the scaffolding it
  owns. Where `said:install` is not available, PROPOSE "run `said:install`" and leave the gap,
  never a half-written scaffold.
- **Propose only** , a genuine choice the schema cannot settle (which `surface` medium? which
  `reviewers` for a surface-bearing lane?). State the proposal with its options and stop; write
  nothing until the operator confirms.

Apply a default ONLY where the schema's remediation states one unambiguously; otherwise propose.
After a `--fix` pass, re-run the checker and show the updated ledger.

## Anti-patterns

- **Do not auto-invoke a phase or another skill from a read-only run.** Report and stop.
- **Do not guess a discretionary value.** A choice the schema cannot settle is a proposal, never a
  silent write.
- **Do not hand-roll structural scaffolding** that `said:install` owns , compose it, or propose it.
- **Do not run as an always-on gate.** This is a doctor the operator invokes, not a cycle step.
- **Do not override the checker's verdicts in prose.** Fix the script or the schema instead.
- **Do not confuse the surface with `said:status`.** That skill reports a FEATURE's phase; this one
  reports whether the LANE is well-formed.
