# Upgrade playbook said-0.26.0 -- the versions reader, the todo board and the said@ stamp

- rollout: said-0.26.0
- plugin: said >=0.26.0
- from: said@0.22.0
- to: said@0.26.0
- after: said-0.22.0

One ordered pass that brings a project from `said` 0.22.0 onto 0.26.0. Of the releases between, 0.23.0 asks nothing;
the others ask one thing each: the board skill replaces the status skill and its script paths move (0.24.0), the
quality gate is recomputed once per feature and read from a record (0.25.0), the todo list is read by the board
through each lane's own file and the stamp takes the `said@<semver>` spelling (0.26.0).
**Config only: no engine edit, no new skill, no commit unless the project's owner asks.**

## Preconditions

- **Engine floor:** `said` 0.26.0 or later, the release that reads the new stamp. Check the version, not presence (V1).
- **A lane stamped below `said@0.22.0`** takes playbook said-0.22.0 first, and the playbooks before it; the chain
  runs in order and `/said:setup` lists what a lane owes.
- **The steps change files of the project, never the plugin.** A step that edits a file the project's owner keeps
  by hand (a launch script, an instructions file) proposes the exact lines, and the owner says yes per diff.
- **Bash:** the blocks below are bash (in zsh, run `bash` first). They only read: they write nothing, call no model
  and use no network. `T` is the project root, `SAID_PLUGIN` the installed said plugin directory.

## Order (each step presupposes the prior)

**Plugin -> the script paths -> the gate record -> the todo file -> the stamp.** A script path repointed before the
update names a folder the old plugin does not have; a stamp set before the other steps claims a walk that has not
happened.

## Step 1 -- Update the plugin

`said` to 0.26.0 or later on the machine the project is worked on. Verify with V1.

## Step 2 -- Repoint script paths

The analyzer, completeness and recompute scripts moved from `skills/status/` to `skills/board/` under their own
names, and `/said:status` is gone (use `/said:board --cli`). In the project's own files, replace:

- `skills/status/said_status.py` -> `skills/board/said_status.py`
- `skills/status/said_completeness.py` -> `skills/board/said_completeness.py` (for example the `said-recompute:`
  line of a completeness Checker in a lane's surface rules)
- `skills/status/gate_recompute.sh` -> `skills/board/gate_recompute.sh`
- `/said:status` -> `/said:board --cli` in notes and lane instructions; a permission rule that names `said:status`
  or an old script path is replaced the same way.
- With `--lane`, a top-level `--prefixes` on a board launch line no longer reaches the lanes: a lane without
  `;prefixes=` infers its own set, so give a lane that needs a fixed set its own `;prefixes=`.

Check with V2.

## Step 3 -- Run the quality gate once per closed feature

A feature closed before 0.25.0 has no gate record, and `accept` and `debrief` stop with `gate owed` when they find
none. For each feature that is closed (its tasks log has a `## Debrief close` footer) and is reopened or checked
again, run `/said:review-qa <feature-id>` once. It writes `gate-<feature-id>.md` into the feature's working folder,
first line `head: <sha>`. A feature that is never touched again needs nothing. Check with V3.

## Step 4 -- Move the todo file, drop the flag

The board no longer takes a todo file by flag. It reads `<docs-root>todo.md` of every lane of the root's
`SAID.lanes:` registry. A todo file passed with `--todo-file <path>` moves to `<docs-root>todo.md` of its lane, and
the flag leaves the launch line or script (a launch line that still passes it exits 2 with a usage error). A `todo`
key left in `docs/.board/config.json` is ignored and can be deleted. A todo line is added by hand in the lane's
`todo.md`. Check with V4.

## Step 5 -- Stamp the lane

Set the lane's stamp by hand, last, after the walk: `SAID.version: said@0.26.0` in the `## Lane` block. The value is
`said@<semver>`, the said release the lane was last brought to; a bare semver is the former spelling and is
rewritten. A lane cloned from a starter may also declare `SAID.starter: <starter>@<semver>` once, the starter and
its release; a lane with no starter omits the key. Neither stamp gates anything. Check with V5.

## Informational

The shipped session roles pin a model: the supervisor `opus`, the worker `sonnet`. `--model` on the launch line
still overrides the pin. No lane action; no Verify block.

## Verify

**V1 -- plugin version.** Reads the installed plugin's manifest. Expect `version: 0.26.0` (or later) and
`floor: ok`.

```bash
SAID_PLUGIN="${SAID_PLUGIN:?set to the installed said plugin directory}"
V="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$SAID_PLUGIN/.claude-plugin/plugin.json")"
echo "version: $V"
python3 -c 'import sys; v=tuple(int(x) for x in sys.argv[1].split(".")[:3]); print("floor: ok" if v>=(0,26,0) else "floor: below 0.26.0")' "$V"
```

**V2 -- the old script paths.** Scans the project's instruction, build and script files and its `docs/ux` and
`docs/qa` rules. Expect `old script paths: 0` after Step 2.

```bash
T="${T:-.}"
FILES="$(ls "$T"/CLAUDE.md "$T"/Makefile "$T"/package.json 2>/dev/null; find "$T/.claude" "$T/scripts" "$T/docs/ux" "$T/docs/qa" -type f 2>/dev/null)"
N=0
if [ -n "$FILES" ]; then
  printf '%s\n' "$FILES" | xargs grep -nE 'skills/status/|said:status' 2>/dev/null
  N=$(printf '%s\n' "$FILES" | xargs cat 2>/dev/null | grep -cE 'skills/status/|said:status' || true)
fi
echo "old script paths: $N"
```

**V3 -- the gate record of each closed feature.** A closed feature is a tasks log with a `## Debrief close` line.
Expect `closed features without a record: 0` once Step 3 is done for the features that need it; a feature not
rerun is listed by its id and is not an error to fix. The record is `gate-<id>.md` in the feature's working folder
(`docs/working/<id>/`), and its first line must start with `head:` (shape only, never the sha).

```bash
T="${T:-.}"
N=0
for L in "$T"/docs/features/*.tasks.md; do
  [ -f "$L" ] || continue
  grep -q '^## Debrief close' "$L" || continue
  ID="$(basename "$L" .tasks.md)"
  R="$T/docs/working/$ID/gate-$ID.md"
  if [ -f "$R" ] && head -n 1 "$R" | grep -q '^head: '; then :; else echo "no record: $ID"; N=$((N+1)); fi
done
echo "closed features without a record: $N"
```

**V4 -- the todo flag and the stored key.** Expect `--todo-file lines: 0` and `config todo key: absent`.

```bash
T="${T:-.}"
FILES="$(ls "$T"/CLAUDE.md "$T"/Makefile "$T"/package.json 2>/dev/null; find "$T/.claude" "$T/scripts" -type f 2>/dev/null)"
N=0
[ -n "$FILES" ] && N=$(printf '%s\n' "$FILES" | xargs cat 2>/dev/null | grep -c -e '--todo-file' || true)
echo "--todo-file lines: $N"
python3 - "$T/docs/.board/config.json" <<'PY'
import json, sys
try:
    d = json.load(open(sys.argv[1]))
except (OSError, ValueError):
    d = {}
print("config todo key: " + ("present" if isinstance(d, dict) and "todo" in d else "absent"))
PY
```

**V5 -- the stamp spelling.** Reads the `## Lane` block of the project's `CLAUDE.md`. Expect `stamp: said@0.26.0`
and, where the lane declares a starter, `starter: <id>@<semver>`; `stamp: former spelling` or `stamp: absent` means
Step 5 is not done.

```bash
T="${T:-.}"
S="$(grep -E '^- SAID\.version:' "$T/CLAUDE.md" 2>/dev/null | head -n 1 | sed 's/^- SAID\.version: *//')"
case "$S" in
  said@[0-9]*.[0-9]*.[0-9]*) echo "stamp: $S" ;;
  "") echo "stamp: absent" ;;
  *) echo "stamp: former spelling" ;;
esac
grep -E '^- SAID\.starter:' "$T/CLAUDE.md" 2>/dev/null | head -n 1 | sed 's/^- SAID\.starter: */starter: /'
```

Then run `/said:setup`: its versions section lists the playbooks the lane still owes, none once the stamp is
`said@0.26.0`.

## What you do NOT do

- **No new rule.** This playbook orders existing contracts; it adds none.
- **No engine edit, no new skill.** Config against the project.
- **No stamp before the walk.** The stamp records a pass over the steps, it does not replace one.
- **No commit** unless the project's owner asks.
