# Upgrade playbook said-0.20.0 -- operator questions, holds, lifts and rulings

- rollout: said-0.20.0
- plugin: said >=0.20.0, magic >=0.13.0
- from: said@0.8.0
- to: said@0.20.0
- after: said-0.8.0

One ordered pass that brings a lane onto the hold vocabulary: a task that waits on an operator question carries a
marker, is held until a recorded ruling lifts it, and the lift cites that ruling. **Config and docs only: no
engine edit, no new skill, no commit unless the lane's owner asks.**

## Preconditions

- **Engine floors:** `said` 0.20.0 or later and `magic` 0.13.0 or later. Check the version, not presence (V1).
- **said 0.20.0 is breaking for the old spellings.** These now hold a task: the marker `**Blocked-on decision:**`,
  the section `## Decisions`, the field `resolved-by:`, the token `OPERATOR-DECISION-HELD`, the script
  `decision-gate.py`. An older engine does not see the new marker. So: **plugins first, then templates and logs**,
  never the reverse.
- **The lane has taken playbook said-0.8.0:** an `## Earned rules` section with citable ids and `SAID.profile:`.
- **Resolve companion symlinks before editing:** edit the target file, never the link.
- **Bash:** the blocks below are bash (in zsh, run `bash` first). `LANE` is the lane root (the folder holding its
  `CLAUDE.md`), `SAID_PLUGIN` the installed said plugin directory.

## Order (each step presupposes the prior)

**Plugins -> macro block -> template, logs and rulings -> linked-record form -> verify.** A log renamed before its
engine is 0.20.0 is unprotected; a template renamed before the macro block is re-synced leaves the old `ruled!!`
line pointing at a local skill. Never skip a step to reach a later one.

## Step 1 -- Update the plugins

`said` to 0.20.0 and `magic` to 0.13.0 or later on the machine the lane is worked on. Verify with V1.

## Step 2 -- Re-sync the macro block

The magic plugin's repository ships the operator macro block in `guides/CLAUDE.md`. Re-paste its sections into the
live block (`~/.claude/CLAUDE.md`, or a project `./CLAUDE.md`), keeping your own extra macros below it, outside
the shipped sections. What changes: "operator question" replaces "owed operator decision", and the `ruled!!` line
invokes `magic:ruled`. A stale personal block loaded beside the new one reopens the path a blanket grant could
take, so this step is not optional.

## Step 3 -- Template, old-spelled logs, rulings

1. **Template.** The lane's `docs/features/template-tasks.md` carries:
   - the task field `**Blocked-on question:** <id>` (a peer of `Status:`, `Priority:`, `Refs:`, written once), and
     that a marked task is held: neither started nor closed;
   - the append-only `## Lifted holds` section with its lift line, in the form the said plugin's README gives
     (section "Operator questions and holds"): the question id, `lifted-by: user@<ruling-id>`, the operator's
     words quoted, the date;
   - that the operator's answer is first recorded as a ruling with `ruled` (the magic plugin) in
     `docs/working/<id>/rulings.md`, and the lift cites its id. `user` is a fixed role word.

   No old word stays in the template (V2). A starter states this in its own words.
2. **Old-spelled logs.** Rename the marker, the section heading and the field. A rename alone does not clear a log
   whose lifts cite a conversation turn instead of a ruling id: such a lift still holds. Per log, the owner
   chooses: record each answer as a ruling with `ruled` (only on the operator's ask) and re-cite, or leave the
   closed log ungated. Never write a ruling for anyone.
3. **Turns files.** A `decision-turns.jsonl` in a working folder is read by nothing from 0.20.0; it goes with the
   rename.
4. **Rulings.** The plugin's `ruled` replaces any local copy. A ruling document with no `- Provenance:` line cannot
   back a lift.

## Step 4 -- The linked-record form

Every `## Earned rules` line ends with a link to its record, resolving from the lane root, with nothing after it;
an id-less line is uncitable. Verify with `earned-rules.py count` (no `link-advisory:` line, no `uncitable:` line).

## Verify

**V1 -- plugin versions.** Expect said 0.20.0 and magic 0.13.0, or later.

```bash
claude plugin list 2>/dev/null | awk '/ (said|magic)@/{p=$2} /Version:/{if(p){print p, $2; p=""}}'
```

**V2 -- the template.** Expect `new text present` and `no old text`.

```bash
LANE="${LANE:-.}"
T="$LANE/docs/features/template-tasks.md"
if [ ! -f "$T" ]; then echo "template: none at $T"
elif grep -qF '**Blocked-on question:**' "$T" && grep -qF '## Lifted holds' "$T" && grep -qF 'lifted-by: user@' "$T"
then echo "template: new text present"; else echo "template: new text MISSING"; fi
if [ -f "$T" ]; then
  if grep -nE 'Blocked-on decision|^## Decisions|resolved-by:|decision-turns|OPERATOR-DECISION-HELD' "$T"
  then echo "template: OLD text (lines above)"; else echo "template: no old text"; fi
fi
```

**V3 -- the gate over the lane's task logs.** Expect `exit 0`. Exit 1 lists each hold with its reason (an old
spelling, a lift citing a turn, a ruling with no Provenance); exit 2 is a marker with no rulings list.

```bash
SAID_PLUGIN="${SAID_PLUGIN:?set to the installed said plugin directory}"
LANE="${LANE:-.}"
shopt -s nullglob
logs=("$LANE"/docs/features/*.tasks.md); lists=("$LANE"/docs/working/*/rulings.md)
if [ ${#logs[@]} -eq 0 ]; then echo "no task logs"; else
  python3 "$SAID_PLUGIN/skills/review-qa/hold-gate.py" check --tasks "${logs[@]}" \
    ${lists[@]:+--rulings "${lists[@]}"} --root "$LANE" | grep -E '^\s*\[(HOLD|CONFIG)\]|^(PASS|HOLD|CONFIG)'
  echo "exit ${PIPESTATUS[0]}"
fi
```

**V4 -- earned rules.** Expect a rule count and no `uncitable:` or `link-advisory:` line.

```bash
SAID_PLUGIN="${SAID_PLUGIN:?set to the installed said plugin directory}"
LANE="${LANE:-.}"
python3 "$SAID_PLUGIN/skills/review-qa/earned-rules.py" count "$LANE/CLAUDE.md"
```

Then set `SAID.version: said@0.20.0` by hand.

## What you do NOT do

- **No new rule.** This playbook orders existing contracts; it adds none.
- **No engine edit, no new skill.** Config and docs against the lane.
- **No rename before the plugin.** An older engine ignores the new marker.
- **No ruling written for anyone.** `ruled` records only on the operator's marker or explicit ask; a lift without a
  ruling is not a lift.
- **No commit** unless the lane's owner asks.
