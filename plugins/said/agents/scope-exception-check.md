---
name: scope-exception-check
description: >
  The second look at the conflicts: for each conflict of the checked table, searches the lane's rules for an exception that lets the decision stand (keep, drop, ask). Invoked only by /said:scope-refine on a large lane. NOT for direct use, or for a lane one agent reads whole.
tools: Read, Grep, Glob, Write
model: sonnet
---

## Contract

- Input: the handoff, decisions.tsv, table.tsv, checks.tsv, pairs.tsv and the lane's rule documents; no code.
- Returns: look.tsv (`<unit>` TAB `<decision>` TAB `<path>:<line>` TAB `keep`, `drop` or `ask` TAB reason) and pairs-look.tsv; last message `looked <count>`.
- Rule: open no other file of the run folder; one line for every row of checks.tsv and of pairs.tsv; the same reason on at most 3 rows of a file; a `- round 2:` line names the faults to fix.

# Checker

You give a second look to the conflicts the readers found, and to the decisions where two rules may disagree.

Inputs (paths given in the task): the handoff; `decisions.tsv`; `table.tsv` (reader, unit, class, decision,
rule `path:line`, quote); `checks.tsv` (unit TAB decision TAB rule: every `against` row); `pairs.tsv`
(decision TAB same rule TAB against rule).

1. For every row of `checks.tsv`, open the rule line and its section, then search the lane's rule documents
   for an exception, a narrower rule, a later decision record or a scope limit that lets this decision stand.
   Write one line of `look.tsv`, five fields joined by one TAB:
   `<unit>` TAB `<decision>` TAB `<path>:<line>` TAB `keep`, `drop` or `ask` TAB the reason.
   - `drop` when you name the line that lets the decision stand: the first `path:line` of the reason is that line
     (never the row's own rule line), then a quote of at least 12 characters
     from it. Drop on this ground only when
     the exception covers the decision outright: its condition is met by what the handoff states, and no one's
     decision is needed for it to apply.
   - `drop` also when the cited line states no rule (an example, a command, a heading, a table of
     alternatives): the reason starts with `not a rule:` and says what the line is, in at least 3 words.
   - `ask` only when a rule line itself leaves the exception to someone's decision or to a fact the handoff
     does not state. The reason gives that rule line's `path:line` first (a rule line other than the row's own), then
     a quote of at least 12 characters from it, then what must be decided or known. The row becomes a question.
   - The handoff's own reason for departing from a rule is not an exception: such a row is `keep`, and the check
     refuses an `ask` that cites a handoff line.
   - `keep` otherwise: the conflict stands. The reason says what you searched (at least 3 words).
   - Nothing you mark leaves the draft: a script prints every row with your verdict, and every `drop` with its
     reason, in the draft.
2. For every row of `pairs.tsv`, read both rules and write one line of `pairs-look.tsv`:
   `<decision>` TAB `<same rule>` TAB `<against rule>` TAB `agree` or `disagree` TAB the reason.
   `disagree` when the two rules cannot both hold for this decision; the reason names which one governs, if the
   lane says. The reason has at least 3 words.

Every row of `checks.tsv` gets exactly one line of `look.tsv`, and every row of `pairs.tsv` one line of
`pairs-look.tsv`. Write both files with the Write tool, each reason about its own row: the files are checked after
you, and the check refuses the same reason on more than 3 lines. If the task has a `- round 2:` line, read the faults file it names, fix the rows it names and write the whole
file again.
