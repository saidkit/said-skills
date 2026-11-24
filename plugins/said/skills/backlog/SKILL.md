---
name: backlog
description: >
  SAID backlog manager - writes the workspace backlog file (<docs-root>backlog.md) through its engine:
  lint the file against its own frontmatter grammar, add a new entry, move an entry's notes to an idea
  record, supersede an entry, promote a record to a feature of a registry lane (plan first, one confirm),
  set-priority on an entry or a record head, migrate a file of the former grammar once (the backlog, or a todo
  file). Triggered ONLY by
  "/said:backlog lint | add | move | supersede | promote | set-priority | migrate ...".
  Fires only on the operator's own typed command; a skill, agent, hook or peer message never invokes it.
  NOT for looking at the backlog - that's "/said:board backlog". NOT for a feature's tasks - that's
  "/said:add-task". NOT for a lane todo line or a todo.md file - only `migrate todo` touches one, once, to bring it to the current format.
---

# said:backlog - the backlog manager

## Contract

1. **One engine, by path.** Every operation is one subcommand of
   `python3 "${CLAUDE_SKILL_DIR}/../board/said_backlog.py" --root <root> <subcommand> ...`. Never edit the
   backlog file, a record folder or a lane's working dir by hand (a hand edit is the operator's, never yours); the engine keeps every write in the file's
   grammar and refuses what would break it.
2. **The root** is the directory whose `CLAUDE.md` declares the backlog's docs root and holds
   `<docs-root>backlog.md` (the multi-lane root when a `SAID.lanes:` registry exists). Find it from the
   working directory upward; none found -> HALT naming the missing file. Pass it absolute.
3. **An entry is named by the engine, never by eye.** Take its `key` and `line` from
   `said_backlog.py --root <root> --json` (`backlog.entries`: match the operator's words to `text`, or the
   `[YYYY-MM-DD]` stamp to `date`). No match, or more than one -> ask the operator which entry, listing the
   candidates with their line.
4. **A refusal is the answer.** Exit 2 with a line starting `refused:` means nothing was written; show the
   line to the operator and stop. Never retry with altered arguments to get past it.
5. **Show each write.** After a write (add, move, supersede, promote or migrate with `--apply`, set-priority) show the
   engine's `wrote ...` line, then point to `/said:board backlog` to see the result. `lint` writes nothing.
   This skill has no report, page or view of its own.
6. **Never a todo line.** Refuse a request for a lane todo line or a todo edit other than `migrate todo`: this
   skill never edits a todo file (only `migrate todo` rewrites one), and the priority write it runs never
   names a lane. A todo item is a feature task (`/said:add-task`) or a hand edit the operator makes in the lane's own list.
7. **The format the engine reads.** The file is `todo-md/2`, specified once in the SPEC.md of the todo-md
   repository, https://github.com/saidkit/todo-md (its version key is `format: todo-md/2`); cite it, never restate it. The engine
   reports any other form as a lint finding and never reads it beside the current one; fix it with
   `migrate`, or name it to the operator, who may edit it by hand.
8. **One operation per call.** A bare `/said:backlog`, or an operation not listed below -> name the seven
   operations and stop; run nothing.
9. **`--today`** (on `add` and `supersede`) is today's date in the operator's local time (`date +%Y-%m-%d`).
10. **The operator's ask.** Run only on the operator's own typed `/said:backlog`, never for a skill, agent, hook or peer message. Every write but the engine's `move` passes `--asked` with at least 12 characters of that command's argument words, word for word. The engine refuses (`refused: no operator ask`) a quote it does not find in a command typed in the root's 5 newest Claude Code sessions; that refusal is the answer (rule 4).
11. **One command, one write.** The command must open with the operation and carry one of its targets: the `--text` words for `add` and `supersede`; for `record`, `set-priority` and `promote`, the entry's key, id, stamp date or first three words, or the record's name for a record head; `backlog` or `todo` for `migrate`.
12. **Outside the ask.** The engine's `move`, the board page's writes (whoever drives the page over HTTP), the engine's functions called in-process, and a `CLAUDE_CONFIG_DIR` or `HOME` pointing the engine at another store pass no check; the check stops an assumed ask and does not authenticate the transcript files.
13. **The author.** The engine writes the author word `~@name` before the id of each entry or todo line it writes: the operator's name on a write that passed rule 10, `~@agent` on the engine's `move`, a page write and an in-process call. Never type one (`--text` refuses a `~@` word).
14. **The operator's name** is the root's git `user.name`, lowercased, each run of characters outside a-z and 0-9 one `-` (none at the ends); a letter first, at most 40 characters, not `agent`. On `refused: no operator name`, ask the operator for the name and to set it with `git config user.name`; never set or guess it, nor write the line another way.

## Operations

In the commands below, substitute before running: `$ENGINE` is `"${CLAUDE_SKILL_DIR}/../board/said_backlog.py"`
(keep the quotes: the path may hold spaces), `ROOT` the absolute root of Contract rule 2, `K` and `N` the
entry's `key` and `line` of Contract rule 3. Every other placeholder comes from the operator's request.

### lint

`python3 $ENGINE --root ROOT lint` (add `--json` for the findings as data). Read-only. Show the findings
grouped by code, then the summary line `lint: N errors, M warnings`. Exit 1 means errors were found, not a
failure of the run.

- `stamp-missing` and `id-missing` are warnings: a legacy entry is kept, and a file not yet migrated shows many `id-missing`, which is expected.
- `id-malformed` and `id-duplicate` are errors.
- `author-missing` (a line with no author) and `author-agent` (a line no typed command last wrote) are warnings; `migrate` writes the missing authors. `author-malformed` and `author-duplicate` are errors.
- Offer no fix the operator did not ask for; each fix is one of the operations below or a hand edit the operator makes.

### add (a new entry)

`python3 $ENGINE --root ROOT add --section "<section>" [--topic "<topic>" [--subtopic "<subtopic>"]] --text "<words>" --today YYYY-MM-DD [--note "<note>"]... --asked "<the command's words>"`.
The engine appends one open entry, stamped today, at the end of the named section, topic or subtopic (a
section that holds topics needs `--topic`, a topic that holds subtopics needs `--subtopic`), with at most two
notes as its sub-bullets. It creates no section, topic or subtopic. `<section>`, `<topic>` and `<subtopic>`
are titles as `--json` prints them (`backlog.sections`); ask for them when the operator did not name them.
A `#word` in `--text` becomes a tag. `--text` and each `--note` are one line of at most
300 characters, with no middle dot, stamp, priority token or id; words an entry already has are refused. The engine
mints the entry's id (`@` and 13 digits, the clock in Unix milliseconds) at the end of the line text, after the author
(rule 13). Both count in the 300, so `--text` holds 285 characters less the author word (and its space:
272 for `~@jane-smith`). A `supersede` mints a new id the same way. The
`wrote ...` line names the new entry's `key` and `line`, ready for a move of its notes to an idea record.

### move (an entry's notes to an idea record)

The skill's move is the engine's `record` subcommand. Never run the engine's `move`: that reorders an entry
within its section, topic or subtopic and is the board page's write.

`python3 $ENGINE --root ROOT record --key K --line N --kind idea|handover|bugfix --slug <slug> --asked "<the command's words>"`.
The engine makes `backlog/<YYMMDD>-<kind>-<slug>/idea.md` from `backlog/template-idea.md`, carries the
entry's notes word for word, and leaves the entry its first line plus one link sub-bullet. Ask for the kind
when the operator did not name it; derive the slug from the entry's words (lowercase, `-` between words, a
few words) and show it before running.

### supersede

`python3 $ENGINE --root ROOT supersede --key K --line N --text "<new words>" --today YYYY-MM-DD --asked "<the command's words>"`.
The entry's line is replaced in place: open, stamped today, the new words, then ` - supersedes [<old stamp>]`
(or the old text quoted when it had no stamp), then a new id (the old id is dropped); its sub-bullets stay. A done entry is
refused: it is ticked in place, never replaced.

### promote (a record to a feature, one confirm)

1. Plan: `python3 $ENGINE --root ROOT promote --key K --line N --target-lane <TOKEN> --feature <FEAT-NN>`.
   `<TOKEN>` is a lane token of the root's `SAID.lanes:` registry; `<FEAT-NN>` the feature id the operator
   names, `<PREFIX>-<NN>` (for example `PROJ-01`); ask for either when it is missing. The
   engine prints the plan (the record folder's move into the lane's working dir for the feature, the entry
   going `[+]`, the new feature link, and, when the entry has a priority and the feature's spec exists, the
   `**Priority:**` line the spec's head gets) and writes nothing. A spec that does not exist yet is not created; the
   plan says so, and the priority is set from the features board once it exists.
2. Show the plan and ask the operator to confirm it. This is the one confirm.
3. On yes, run the same command with `--apply --asked "<the command's words>"`. One invocation writes in both roots (the backlog's and the
   lane's). On no, stop; nothing was written.

### set-priority

`python3 $ENGINE --root ROOT set-priority --letter A|B|C|none --key K --line N --asked "<the command's words>"` for an entry line, or
`--letter A|B|C|none --record <YYMMDD>-<kind>-<slug>` in place of `--key` and `--line` for a record head's `**Priority:**` line. `none`
removes the token. The letter and the target come from the operator; ask when either is missing. Never
pass `--lane`.

### migrate (a former-grammar file to grammar v2, or the authors of a v2 file, one confirm)

1. Ask which file: the workspace backlog (`backlog`), or one lane's todo file (`todo`, which also needs the lane token from the registry, or the file path). Never choose for the
   operator, and never run it on any file the operator did not name.
2. Plan: `python3 $ENGINE --root ROOT migrate backlog`, or `python3 $ENGINE --root ROOT migrate todo --lane <TOKEN>`
   (`--file <absolute physical path>` names another file under the root). The engine prints each changed line and each removed line
   (`-> (removed)`) and writes nothing; a long plan is capped at 40 rows with a last row counting what is not shown, and `--full` prints it all. The mapping:
   - The backlog target maps the former top-level heads to sections (a lane token or a name the frontmatter
     declares), numbered groups to topics, former stage words to `#word` tags, `[P1]` and `[P2]` to `[#A]` and
     `[#B]`, and `[@YYMMDD]` to `[20YY-MM-DD]`, adds `format: todo-md/2` and drops the frontmatter `structure:` block.
   - The todo target adds the frontmatter with that key, drops the todo format comment and rewrites stamps.
   - Both targets keep an existing id, rewrite the former `@B` and `@T` letter forms bare, and give every other
     entry line an id of the migration time, unique in its file.
   - Both targets write the operator's author (rules 13 and 14) before the id of every entry line that has none; a line
     with an author keeps it. On a file already at version 2 that is the whole plan; when every line has an author
     the engine prints `nothing to migrate` and writes nothing.
3. Show the plan and ask the operator to confirm it. This is the one confirm.
4. On yes, run the same command with `--apply --asked "<the command's words>"`. On no, stop; nothing was written.
5. A former-grammar file of the other kind, and any form the engine cannot map are refused with the
   line named and the file unchanged. Show the refusal and stop; the fix is a hand edit by the operator, then a new plan.

## Anti-patterns

- Don't open `backlog.md` in an editor tool to make the change yourself: the engine is the one writer.
- Don't guess a `--line` from a file read; the engine refuses a stale position, so read it from `--json`.
- Don't run promote or migrate with `--apply` before the operator has seen the plan.
- Don't route a todo line or todo edit here (except `migrate todo`); say it is refused and where it goes.
