# Upgrade playbook said-0.28.0 -- the phases Scope, Act, Inspect, Debrief and the renamed agents

- rollout: said-0.28.0
- plugin: said >=0.28.0
- from: said@0.27.1
- to: said@0.28.0
- after: said-0.26.0

One ordered pass that brings a project from `said` 0.27.1 onto 0.28.0. A lane stamped `said@0.26.0` takes it too:
0.27.0 and 0.27.1 ask nothing of a lane. 0.28.0 renames the phases, five agents, one skill and one lane key.
**Config only: no engine edit, no new skill, no commit unless the project's owner asks.**

## Preconditions

- **Engine floor:** `said` 0.28.0 or later, the release that reads the new names. Check the version, not presence
  (V1).
- **A lane stamped below `said@0.26.0`** takes playbook said-0.26.0 first, and the playbooks before it; the chain
  runs in order and `/said:setup` lists what a lane owes.
- **The steps change files of the project, never the plugin.** A step that edits a file the project's owner keeps
  by hand (an instructions file, a launch script) proposes the exact lines, and the owner says yes per diff.
- **Bash:** the blocks below are bash (in zsh, run `bash` first). They only read: they write nothing, call no model
  and use no network. `T` is the project root, `SAID_PLUGIN` the installed said plugin directory.

## Order (each step presupposes the prior)

**Plugin -> the lane key -> the phase and agent names -> the stamp.** A key renamed before the update is a key the
old plugin does not read; a stamp set before the other steps claims a walk that has not happened.

## Step 1 -- Update the plugin

`said` to 0.28.0 or later on the machine the project is worked on. Verify with V1.

## Step 2 -- Rename the gate-reader key

`SAID.gate-reviewer-threshold` is now `SAID.gate-reader-threshold`, same value. Rename the key in the lane block.
The old spelling is ignored: the gates use the default 150000 until it is renamed, and `/said:setup` reports
nothing for it, so V2 is where a lane finds it. A lane that never declared the key does nothing.

## Step 3 -- Rename the phases and the agents in the project's own files

The phases are Scope, Act, Inspect, Debrief, Closed. In the project's instructions, notes and scripts, replace:

- the phase Architect -> "Act, the Architect step" (the spec and task log are written in Act's first step; the
  skill `/said:architect` keeps its name);
- the phase Implement -> Act;
- the phase Deliver -> Inspect for the gates (`review-qa`, `review-ux`, `accept`) and Debrief for `/said:debrief`;
- `said:review-ux-agent` -> `said:web-ux-reviewer`, `said:gate-reviewer` -> `said:gate-reader`, the agent
  `said:cli-gate` -> `said:cli-gate-reviewer`, `said:scope-refine-agent` -> `said:scope-refiner`,
  `said:scope-audit` -> `said:scope-auditor`. The Checker id `cli-gate` in `SAID.reviewers:` keeps its name:
  Checkers resolve by their `said-checker:` key, not by file name;
- the skill `said:retrieval` -> `said:precedent`, one name with the operator macro `precedent!!`: point the macro
  and every instruction that names the skill at `/said:precedent`. The old name is not accepted beside the new one.
- the Eval step is retired: `said`'s Inspect ends `/said:accept` -> `/said:debrief`. An instruction that runs or
  waits on an Eval after `accept`, or on a `QA-eval-<id>.md` file, drops that step; existing `QA-eval-*` files stay
  as history. A multi-lane feature's e2e/UAT close in `/said:flow` is not the Eval and stays.

A reader of `/said:board --json` sees the new phase values; a script that matched the old ones is updated the same
way. Check with V3.

## Step 4 -- Stamp the lane

Set the lane's stamp by hand, last, after the walk: `SAID.version: said@0.28.0` in the `## Lane` block. Neither
stamp gates anything. Check with V4.

## Kept uses of Architect

The shipped plugin names Architect only as Act's first step, "the Architect step". Each file below carries that many
lines with it; any other use is a leftover.

- `README.md`: 2
- `agents/scope-refiner.md`: 5
- `skills/add-task/SKILL.md`: 2
- `skills/architect/SKILL.md`: 4
- `skills/flow/SKILL.md`: 9
- `skills/said/SKILL.md`: 7
- `skills/setup/references/lane-schema.json`: 1
- `skills/scope-grill/SKILL.md`: 8
- `skills/scope-refine/SKILL.md`: 3
- `skills/uxtoc/SKILL.md`: 1

## Verify

**V1 -- plugin version.** Reads the installed plugin's manifest. Expect `version: 0.28.0` (or later) and
`floor: ok`.

```bash
SAID_PLUGIN="${SAID_PLUGIN:?set to the installed said plugin directory}"
V="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$SAID_PLUGIN/.claude-plugin/plugin.json")"
echo "version: $V"
python3 -c 'import sys; v=tuple(int(x) for x in sys.argv[1].split(".")[:3]); print("floor: ok" if v>=(0,28,0) else "floor: below 0.28.0")' "$V"
```

**V2 -- the old key.** Reads the project's `CLAUDE.md`. Expect `old key lines: 0`.

```bash
T="${T:-.}"
N=$(grep -cE '^- SAID\.gate-reviewer-threshold:' "$T/CLAUDE.md" 2>/dev/null || true)
echo "old key lines: ${N:-0}"
```

**V3 -- the old phase, agent and skill names.** Scans the project's instruction, build and script files. Expect
`old names: 0` after Step 3; a line it lists that is not a phase name (a word in another sense) is not an error.

```bash
T="${T:-.}"
FILES="$(ls "$T"/CLAUDE.md "$T"/Makefile "$T"/package.json 2>/dev/null; find "$T/.claude" "$T/scripts" -type f 2>/dev/null)"
P='\b(Implement|Deliver)\b|said:(review-ux-agent|gate-reviewer|cli-gate|scope-refine-agent|scope-audit|retrieval)([^a-z-]|$)'
N=0
if [ -n "$FILES" ]; then
  printf '%s\n' "$FILES" | xargs grep -nE "$P" 2>/dev/null
  N=$(printf '%s\n' "$FILES" | xargs cat 2>/dev/null | grep -cE "$P" || true)
fi
echo "old names: $N"
```

**V4 -- the stamp.** Expect `stamp: said@0.28.0`.

```bash
T="${T:-.}"
S="$(grep -E '^- SAID\.version:' "$T/CLAUDE.md" 2>/dev/null | head -n 1 | sed 's/^- SAID\.version: *//')"
echo "stamp: ${S:-absent}"
```

Then run `/said:setup`: its versions section lists the playbooks the lane still owes, none once the stamp is
`said@0.28.0`.

## What you do NOT do

- **No new rule.** This playbook orders existing contracts; it adds none.
- **No engine edit, no new skill.** Config against the project.
- **No second spelling.** The old key and the old names are replaced, never kept beside the new ones.
- **No stamp before the walk.** The stamp records a pass over the steps, it does not replace one.
- **No commit** unless the project's owner asks.
