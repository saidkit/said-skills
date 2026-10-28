---
name: backlog
description: >
  SAID backlog manager - writes the workspace backlog file (<docs-root>backlog.md) through its engine:
  lint the file against its own frontmatter grammar, add a new entry, move an entry's notes to an idea
  record, supersede an entry, promote a record to a feature of a registry lane (plan first, one confirm),
  set-priority on an entry or a record head. Triggered ONLY by
  "/said:backlog lint | add | move | supersede | promote | set-priority ...".
  NOT for looking at the backlog - that's "/said:board backlog". NOT for a feature's tasks - that's
  "/said:add-task". NOT for a lane todo line or a todo.md file - this skill never reads or writes one.
---

# said:backlog - the backlog manager

## Contract

1. **One engine, by path.** Every operation is one subcommand of
   `python3 "${CLAUDE_SKILL_DIR}/../board/said_backlog.py" --root <root> <subcommand> ...`. Never edit the
   backlog file, a record folder or a lane's working dir by hand; the engine keeps every write in the file's
   grammar and refuses what would break it.
2. **The root** is the directory whose `CLAUDE.md` declares the backlog's docs root and holds
   `<docs-root>backlog.md` (the multi-lane root when a `SAID.lanes:` registry exists). Find it from the
   working directory upward; none found -> HALT naming the missing file. Pass it absolute.
3. **An entry is named by the engine, never by eye.** Take its `key` and `line` from
   `said_backlog.py --root <root> --json` (`backlog.entries`: match the operator's words to `text`, or the
   `[@YYMMDD]` stamp to `stamp`). No match, or more than one -> ask the operator which entry, listing the
   candidates with their line.
4. **A refusal is the answer.** Exit 2 with a line starting `refused:` means nothing was written; show the
   line to the operator and stop. Never retry with altered arguments to get past it.
5. **Show each write.** After a write (add, record, supersede, promote with `--apply`, set-priority) show the
   engine's `wrote ...` line, then point to `/said:board backlog` to see the result. `lint` writes nothing.
   This skill has no report, page or view of its own.
6. **Never a todo line.** Refuse a request for a lane todo line or a `todo.md` path: this skill never reads
   or writes a todo file, and the priority write it runs never names a lane. A todo item is a feature task
   (`/said:add-task`) or a hand edit of the lane's own list.
7. **One operation per call.** A bare `/said:backlog`, or an operation not listed below -> name the six
   operations and stop; run nothing.

## Operations

In the commands below, substitute before running: `$ENGINE` is `"${CLAUDE_SKILL_DIR}/../board/said_backlog.py"`
(keep the quotes: the path may hold spaces), `ROOT` the absolute root of Contract rule 2, `K` and `N` the
entry's `key` and `line` of Contract rule 3. Every other placeholder comes from the operator's request.

### lint

`python3 $ENGINE --root ROOT lint` (add `--json` for the findings as data). Read-only. Show the findings
grouped by code, then the summary line `lint: N errors, M warnings`. Exit 1 means errors were found, not a
failure of the run. `stamp-missing` is a warning (a legacy entry is kept). Offer no fix the operator did not ask
for; each fix is one of the operations below or a hand edit the operator makes.

### add (a new entry)

`python3 $ENGINE --root ROOT add --section "<section>" [--group "<group>"] --text "<words>" --today YYYY-MM-DD [--note "<note>"]...`.
The engine appends one open entry, stamped today, at the end of the named section (or of its named group;
a section that holds groups needs `--group`), with at most two notes as its sub-bullets. `<section>` and
`<group>` are titles as `--json` prints them (`backlog.sections`); ask for them when the operator did not
name them. `--today` is today's date (`date +%Y-%m-%d`). `--text` and each `--note` are one line of at most
300 characters, with no middle dot, stamp or priority token; words an entry already has are refused. The
`wrote ...` line names the new entry's `key` and `line`, ready for a move of its notes to an idea record.

### move (an entry's notes to an idea record)

The skill's move is the engine's `record` subcommand. Never run the engine's `move`: that reorders an entry
within its group and is the board page's write.

`python3 $ENGINE --root ROOT record --key K --line N --kind idea|handover|bugfix --slug <slug>`.
The engine makes `backlog/<YYMMDD>-<kind>-<slug>/idea.md` from `backlog/template-idea.md`, carries the
entry's notes word for word, and leaves the entry its first line plus one link sub-bullet. Ask for the kind
when the operator did not name it; derive the slug from the entry's words (lowercase, `-` between words, a
few words) and show it before running.

### supersede

`python3 $ENGINE --root ROOT supersede --key K --line N --text "<new words>" --today YYYY-MM-DD`.
The entry's line is replaced in place: open, stamped today, the new words, then ` - supersedes [@<old stamp>]`
(or the old text quoted when it had no stamp); its sub-bullets stay. `--today` is today's date in the operator's local time (`date +%Y-%m-%d`). A done entry is
refused: it is ticked in place, never replaced.

### promote (a record to a feature, one confirm)

1. Plan: `python3 $ENGINE --root ROOT promote --key K --line N --target-lane <TOKEN> --feature <FEAT-NN>`.
   `<TOKEN>` is a lane token of the root's `SAID.lanes:` registry; `<FEAT-NN>` the feature id the operator
   names, `<PREFIX>-<NN>` (for example `PROJ-01`); ask for either when it is missing. The
   engine prints the plan (the record folder's move into the lane's working dir for the feature, the entry
   going `[+]`, the new feature link) and writes nothing.
2. Show the plan and ask the operator to confirm it. This is the one confirm.
3. On yes, run the same command with `--apply`. One invocation writes in both roots (the backlog's and the
   lane's). On no, stop; nothing was written.

### set-priority

`python3 $ENGINE --root ROOT set-priority --letter A|B|C|none --key K --line N` for an entry line, or
`--letter A|B|C|none --record <YYMMDD>-<kind>-<slug>` for a record head's `**Priority:**` line. `none`
removes the token. The letter and the target come from the operator; ask when either is missing. Never
pass `--lane`.

## Anti-patterns

- Don't open `backlog.md` in an editor tool to make the change yourself: the engine is the one writer.
- Don't guess a `--line` from a file read; the engine refuses a stale position, so read it from `--json`.
- Don't run promote with `--apply` before the operator has seen the plan.
- Don't route a todo request here; say it is refused and where it goes.
