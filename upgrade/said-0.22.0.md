# Upgrade playbook said-0.22.0 -- the checkpoint switch and the shipped session roles

- rollout: said-0.22.0
- plugin: said >=0.22.0
- from: said@0.21.0
- to: said@0.22.0
- after: said-0.21.0

One ordered pass that brings a project onto two `said` changes: the context-checkpoint stop is off unless a session
switches it on, and the plugin ships the two session-role definitions a project launches with `--agent`.
**Config only: no engine edit, no new skill, no commit unless the project's owner asks.**

## Preconditions

- **Engine floor:** `said` 0.22.0 or later, the release that ships the session roles. Check the version, not
  presence (V1), and on each machine check that the roles resolve after the update (V3).
- **The stop is off after the update.** A session that does not switch it on has no check, no stop and no notice.
  A project that relied on the stop being on by default switches it on per session (Step 3).
- **Every write to a role definition is its owner's.** A definition is a session's own instructions: propose the
  exact lines, the owner says yes per diff. A worker session never edits them.
- **A lane with no keyed lane block yet** takes playbook said-0.8.0 first; for the lane-block keys of 0.21.0
  (`SAID.mounts`, the registry line) see playbook said-0.21.0.
- **Bash:** the blocks below are bash (in zsh, run `bash` first). `T` is the project root, `SAID_PLUGIN` the
  installed said plugin directory.

## Order (each step presupposes the prior)

**Plugin -> the override line -> the switch -> the threshold key -> the role definitions -> verify.** An override
dropped before the update leaves an older worker at a stop that is on by default there, with nobody at its window;
a definition replaced by `said:<role>` before the release that ships it names an agent the CLI refuses.

## Step 1 -- Update the plugin

`said` to 0.22.0 or later on the machine the project is worked on. Verify with V1 and V3.

## Step 2 -- Drop the worker override line

A hand-written worker definition may carry a line that re-invokes the skill on `goal: stop -- CONTEXT-CHECKPOINT`.
With the stop off by default it overrides nothing, so it goes. The owner deletes the line; nothing else in the file
changes. Check with V2.

## Step 3 -- Switch the stop on where a person wants it

The stop is per session. Either source means on:

- the launch line: `SAID_CONTEXT_CHECKPOINT=on claude`; only the exact value `on` counts;
- the directive: the trailing word `checkpoint`, as in `said! <feature-id> checkpoint` or
  `flow! <feature-id> checkpoint`. The skill writes an empty marker `checkpoint-on` in the session scratchpad; a
  compaction keeps it, a `/clear` drops it, so the stop prints its re-issue line with the word.

Whoever switches it on answers the stop: it asks for `/clear`, which a cross-session message cannot run in another
window. The check reads `context.json`, which only the plugin's statusline writes (`/said:setup statusline`);
without it the check is skipped with one notice line.

## Step 4 -- The threshold key, where declared

`SAID.context-checkpoint:` is the threshold, never the switch. Where a lane declares it, the value is a positive
integer token count; `off`, `0` or `300_000` is a BLOCKER naming the key. Absent means 300000. Check with V4.

## Step 5 -- The role definitions

The plugin ships `said:supervisor` (pins `model: fable`) and `said:worker` (pins `model: opus`), launched as
`claude --name <session> --agent said:supervisor` and `claude --name <session> --agent said:worker`; the supervisor
binds workers by the names they were launched with, and `--model` on the launch line overrides the pin.

A project replaces its hand-written `.claude/agents/` supervisor and worker files with the shipped pair, or keeps
its own only where it needs project-specific text, and then without a checkpoint line (Step 2). The shipped launch
lines use the qualified name; a project file of the same bare name (`worker`) is a case to check on the project's
own machine.

## Verify

**V1 -- plugin version.** Expect `said@<marketplace> 0.22.0` or later per install scope.

```bash
claude plugin list 2>/dev/null | awk '/ said@/{p=$2} /Version:/{if(p){print p, $2; p=""}}'
```

**V2 -- the override line.** Expect `override lines: 0` after Step 2.

```bash
T="${T:-.}"
grep -nE 'CONTEXT-CHECKPOINT' "$T"/.claude/agents/*.md 2>/dev/null
echo "override lines: $(cat "$T"/.claude/agents/*.md 2>/dev/null | grep -cE 'CONTEXT-CHECKPOINT')"
```

**V3 -- the shipped roles resolve.** Asks the CLI for an agent that does not exist from an empty directory: it
refuses before any model call and lists the agents it resolves. Expect `exit=1`, the `not found` line, then
`said:supervisor` and `said:worker`.

```bash
P="$(mktemp -d)"
OUT="$(cd "$P" && claude -p --agent said:no-such-role x 2>&1)"; RC=$?
echo "exit=$RC"
printf '%s\n' "$OUT" | head -1 | cut -c1-60
printf '%s\n' "$OUT" | tr ',' '\n' | sed 's/^ *//' | grep -E '^said:(supervisor|worker)$'
```

**V4 -- the threshold key's value.** Builds a lane block in a temp dir with `SAID.context-checkpoint: off`, then
`300000`. Expect for `off` one `[BLOCKER] SAID.context-checkpoint` line and a ledger with `1 BLOCKER`; for `300000`
no key line and a ledger with `0 BLOCKER`.

```bash
SAID_PLUGIN="${SAID_PLUGIN:?set to the installed said plugin directory}"
F="$(mktemp -d)"
for V in off 300000; do
  printf '%s\n' '# t' '' '## Lane' '- SAID.lane:         demo' '- SAID.docs-root:    docs/' \
    '- SAID.mounts:       [web/]' '- SAID.feature-spec: docs/features/<id>.md' \
    '- SAID.task-log:     docs/features/<id>.tasks.md' '- SAID.working:      docs/working/<id>/' \
    '- SAID.id-shape:     DEMO-<NN>' '- SAID.adr-prefix:   ADR-DEMO-*' '- SAID.surface:      none' \
    '- SAID.reviewers:    []' '- SAID.profile:      code' '- SAID.commands:     make check' \
    "- SAID.context-checkpoint: $V" '' '## Earned rules' '- R-DEMO-01 a rule' > "$F/CLAUDE.md"
  echo "value $V:"
  python3 "$SAID_PLUGIN/skills/setup/setup_check.py" --root "$F" | grep -E 'SAID\.context-checkpoint|^ledger' | cut -c1-90
done
```

Then set `SAID.version: said@0.22.0` by hand.

## What you do NOT do

- **No new rule.** This playbook orders existing contracts; it adds none.
- **No engine edit, no new skill.** Config against the project.
- **No override dropped before the update.**
- **No role definition edited by a worker session.**
- **No commit** unless the project's owner asks.
