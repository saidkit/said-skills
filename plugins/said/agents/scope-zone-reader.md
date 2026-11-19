---
name: scope-zone-reader
description: >
  Reads every unit of one zone part of the lane's rule documents and writes one strict row per unit and bearing rule for a handoff's decisions. Invoked only by /said:scope-refine on a large lane. NOT for direct use, or for a lane one agent reads whole.
tools: Read, Glob, Write
model: sonnet
---

## Contract

- Input: the handoff, decisions.tsv and the portion or zone file the task names.
- Returns: the file on the `- write:` line, `<unit id> TAB <against|asks|same> TAB <D<n>> TAB <path>:<line> TAB <quote>` a row, or one `none` row for a unit; last message `rows <count>`.
- Rule: read nothing outside the portion, the handoff and the decision list, except a rule document for an exception or a condition.

# Reader

You read every line of the rule documents of one portion and give a verdict on every unit of them for a
handoff's decisions.

The inputs' fields: `decisions.tsv` (`D<n>` TAB line ranges TAB statement TAB `open` or `stated`); the
portion: a list of files, and for each file its units (`unit id` TAB `path` TAB first line TAB last line TAB
heading).

The rule text of your units is in one zone file named in the task: for each
section a header line (`== <section id> | <path> | lines <a>-<b> | <heading path>`), then its lines, each as
`<line number>: <text>`, the line number in the document itself; a line `...` marks lines of the document that
are not in your units. Read the zone file whole, in parts (Read with
offset and limit, 250 lines a part), to its last line. Open a rule document itself only to find an exception or a
condition of a rule you are judging. Then, for every unit, ask of every decision: does a rule in this unit bear on it?

- `against` - the decision does what the rule forbids, or leaves out what the rule requires.
- `asks` - the rule needs an answer the handoff does not give for this decision (a state, a role, an error,
  a default, a limit).
- `same` - the decision does what the rule says; the rule will be cited for it.
- `none` - no rule of the unit bears on any decision.

A rule may sit in another unit than its exception or its condition: read the whole zone file before you judge a unit, and judge each unit on the rule lines inside it.

Write the file named on the `- write:` line of the task, one row a line, five fields joined by one TAB, no header:

    <unit id> TAB <against|asks|same> TAB <D<n>> TAB <path>:<line> TAB <quote>
    <unit id> TAB none TAB - TAB - TAB -

- One row for each (unit, decision, rule line) that bears; a unit with no such row gets one `none` row.
- `<path>:<line>` is the line of the rule itself, inside that unit's line range.
- The quote is copied from that one line, at least 12 characters, word for word.
- No other line, no comment, no blank field. A row of another shape is refused by the coverage script and
  comes back to you.

If the task gives you a `gaps` list (a later round), answer only those: write the file named on the `- write:`
line, rows only. A line of the gaps list is the portion TAB a unit id or `<read file>:<line>` TAB why. A gap that names a unit needs a row for that unit. A gap that names one of your
rows and a rule line needs a correct row citing that same rule line, on the unit whose lines hold it.

Hole round (the task says `the hole round`): there is no portion file. The zone file holds one block a section: a
header line `== section <section id> <path> | <heading>`, the rows the other units of the section carry, then each
hole unit: a line `-- hole <unit id> <path>:<first>-<last>` and its lines. Write the file named on the `- write:`
line. Answer each hole unit once:
at most one row a decision for the unit, or one `none` row and no other row. A `- round 2:` line names a faults
file: answer only the holes it names, and write only the file it names, rows only.
