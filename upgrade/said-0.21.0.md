# Upgrade playbook said-0.21.0 -- the `SAID.mounts` key and the lane registry line

- rollout: said-0.21.0
- plugin: said >=0.21.0
- from: said@0.20.0
- to: said@0.21.0
- after: said-0.20.0

One ordered pass that brings a lane or a multi-lane root onto two changes of the lane block: the key
`SAID.code-mount` becomes the list key `SAID.mounts`, and a `SAID.lanes:` registry becomes one key line of
`TOKEN=root` pairs. **Config only: no engine edit, no new skill, no commit unless the lane's owner asks.**

## Preconditions

- **Engine floor:** `said` 0.21.0 or later. Check the version, not presence (V1).
- **0.21.0 is breaking for a lane block.** On it, a block that still writes `SAID.code-mount:` reports
  `SAID.mounts missing BLOCKER` and `SAID.code-mount stale STALE`; a registry in any other shape reports
  `SAID.lanes BLOCKER` and no reader returns a row. On an older release the reverse holds: a block already renamed
  reports `SAID.code-mount missing BLOCKER`. So: **plugin first, then the blocks**, never the reverse.
- **Resolve companion symlinks before editing:** edit the target file, never the link, and count it once.
- **Every write to a `CLAUDE.md` is its owner's.** `/said:setup --fix` shows the change and writes on consent.
- **A lane with no keyed lane block yet** takes playbook said-0.8.0 first; its template already writes both keys in the
  new form.
- **Bash:** the blocks below are bash (in zsh, run `bash` first). `LANE` is the lane root (the folder holding its
  `CLAUDE.md`), `SAID_PLUGIN` the installed said plugin directory.

## Order (each step presupposes the prior)

**Plugin -> the mounts key -> the registry line -> second namings -> verify.** A block renamed before its plugin is
updated is a BLOCKER on the old build; a registry line rewritten before the mounts key is repaired still leaves
the root's own block at BLOCKER. Never skip a step to reach a later one.

## Step 1 -- Update the plugin

`said` to 0.21.0 or later on the machine the lane is worked on. Verify with V1.

## Step 2 -- The mounts key (every lane block)

Run `/said:setup --fix` in the lane. For the old key it performs one write, on the owner's consent: the key and
the value's shape together, the line the checker prints. `SAID.code-mount: web/, server/` becomes
`SAID.mounts: [web/, server/]`; a single path is bracketed too; `none` stays bare. Nothing else on the line
changes. Check with V3: the two mounts findings are gone.

Prose in the same file that names the old key is not a key line and is not reported; rename it by hand where the
owner wants it.

## Step 3 -- The registry line (a multi-lane root only)

`/said:setup --fix` only proposes here: a root cannot be derived from a bare token. The owner rewrites the registry
as one key line inside the root's `## Lane` block and deletes the old registry sub-section with everything in it
(its heading, its table, its sub-bullets). Any table row or `TOKEN: path/` bullet left below the line, up to the
next `## ` heading, is one `SAID.lanes` BLOCKER and the reader refuses the line:

    - SAID.lanes:        [WEB=web/, API=api/, APP=./]

A token is a letter, then letters and digits. A root is that lane's directory, relative to the directory of the
file that carries the line, ending in `/`; the root's own directory is `./` and that row is optional. Facts the old
sub-section carried that are not a token or a root move to the project's own docs first. Check with V4.

A registry under a heading other than exactly `## Lane` (for example `## Lanes`) is outside the lane block: it is
reported STALE and read by nothing, and it moves into the block in the same edit.

A root with no registry line, or `SAID.lanes: []`: run `/said:setup --fix` at the root. It reads the root's
immediate subdirectories, prints one `SAID.lanes` row ending `write: SAID.lanes: [...]` with a token per lane that
carries a `## Lane` block, and writes that line on consent. Check the listed rows first: drop a row the root does
not coordinate (a starter copy, for example), then verify with V4.

## Step 4 -- Second namings (optional, STALE only)

The build reports a scalar key named a second time anywhere in the file. It is STALE, never a BLOCKER. The owner
rewords the prose so that it does not spell the key with its colon (write "the surface key" for `SAID.surface:`),
or leaves it.

## Verify

**V1 -- plugin version.** Expect `said@<marketplace> 0.21.0` or later, one line per install scope.

```bash
claude plugin list 2>/dev/null | awk '/ said@/{p=$2} /Version:/{if(p){print p, $2; p=""}}'
```

**V2 -- what the lane writes today.** Prints the mounts line and, on a root, the registry line. Expect the old key
before Step 2 and `SAID.mounts:` after it.

```bash
LANE="${LANE:-.}"
grep -nE '^[-* ]*SAID\.(code-mount|mounts|lanes):' "$LANE/CLAUDE.md"
```

**V3 -- the checker's verdict on the two keys.** After the steps, expect no line for `SAID.mounts`,
`SAID.code-mount` or `SAID.lanes` and a ledger with `0 BLOCKER, 0 STALE` (ADVISORY rows do not count).

```bash
SAID_PLUGIN="${SAID_PLUGIN:?set to the installed said plugin directory}"
LANE="${LANE:-.}"
python3 "$SAID_PLUGIN/skills/setup/setup_check.py" --root "$LANE" | grep -E 'SAID\.(mounts|code-mount|lanes)|single-hit|^ledger'
```

**V4 -- the registry's rows (a root only).** Expect one `TOKEN:root=<root>` line per lane, then `count: <N>`. A
`refused:` line (exit 2) means Step 3 is not done; `count: 0` on a root means the line is not inside the `## Lane`
block. A single lane prints `count: 0` and that is correct.

```bash
SAID_PLUGIN="${SAID_PLUGIN:?set to the installed said plugin directory}"
LANE="${LANE:-.}"
python3 "$SAID_PLUGIN/skills/board/said_status.py" --registry --root "$LANE"
```

**V5 -- the repair converges (no lane needed).** Builds a block in the old spelling in a temp dir, prints the two
findings, writes the line the checker printed, and prints the ledger. Expect one `[BLOCKER] SAID.mounts` line, one
`[STALE] SAID.code-mount` line ending in `write: SAID.mounts: [web/, server/]`, then a ledger with
`0 BLOCKER, 0 STALE`.

```bash
SAID_PLUGIN="${SAID_PLUGIN:?set to the installed said plugin directory}"
F="$(mktemp -d)"
printf '%s\n' '# t' '' '## Lane' '- SAID.lane:         demo' '- SAID.docs-root:    docs/' \
  '- SAID.code-mount:   web/, server/' '- SAID.feature-spec: docs/features/<id>.md' \
  '- SAID.task-log:     docs/features/<id>.tasks.md' '- SAID.working:      docs/working/<id>/' \
  '- SAID.id-shape:     DEMO-<NN>' '- SAID.adr-prefix:   ADR-DEMO-*' '- SAID.surface:      none' \
  '- SAID.reviewers:    []' '- SAID.profile:      code' '- SAID.commands:     make check' '' \
  '## Earned rules' '- R-DEMO-01 a rule' > "$F/CLAUDE.md"
python3 "$SAID_PLUGIN/skills/setup/setup_check.py" --root "$F" | grep -E 'SAID\.(mounts|code-mount)' | cut -c1-70
LINE="$(python3 "$SAID_PLUGIN/skills/setup/setup_check.py" --root "$F" | sed -n 's/.*write: \(SAID\.mounts: .*\)$/\1/p')"
echo "line to write: $LINE"
sed -i.bak "s|^- SAID\.code-mount:.*|- $LINE|" "$F/CLAUDE.md"
python3 "$SAID_PLUGIN/skills/setup/setup_check.py" --root "$F" | tail -1
```

Then set `SAID.version: said@0.21.0` by hand.

## What you do NOT do

- **No new rule.** This playbook orders existing contracts; it adds none.
- **No engine edit, no new skill.** Config against the lane.
- **No rename before the plugin.** The old build blocks on a block it cannot read.
- **No registry line written for an owner.** `--fix` proposes it; the owner writes it.
- **No path changed.** The pass changes a key and a spelling, never where a lane's production lives.
- **No commit** unless the lane's owner asks.
