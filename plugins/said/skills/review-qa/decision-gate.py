#!/usr/bin/env python3
"""decision-gate -- the deterministic anti-self-default checker for a SAID task.

A task may declare it depends on an owed operator decision by carrying a
`**Blocked-on decision:** <id>` marker (a peer of `**Status:**` / `**Priority:**`,
authored write-once). The decision is resolved by an append-only `## Decisions`
ledger record in the same task log:

  - <id> resolved-by: user@<turn> -- "<verbatim quote>" -- <date> [supersedes: <prior>]

This gate verifies the STRUCTURAL attribution predicate as DATA -- never a
free-form prose judgement. For each marker it returns PASS iff:
  1. a `## Decisions` record for <id> exists (the last one wins -- append-only,
     a later record supersedes an earlier one);
  2. its `resolved-by:` actor is `user` with an `@<turn>` reference -- an actor in
     the deny-list (grant, standing-autonomy, default, assistant, subagent, arm)
     is exactly the blanket-grant self-default this gate exists to catch;
  3. the cited turn resolves in the role-labelled turns source and is a user turn;
  4. the record's verbatim quote is a literal substring of that turn's text;
  5. the record postdates the marker (an operator resolution cannot predate the
     task that raised the block).
Otherwise HOLD.

WHAT THIS GATE DOES NOT DECIDE. Whether the cited turn actually *decides this id*
(rather than merely mentioning something) is a semantic judgement -- it stays
agent-side (the resolve step and the second-look reviewer), never in this script.
A record can be structurally perfect and still cite the wrong decision; this gate
PASSes it by design, and the agent-side check is what fails it. Putting that
judgement in a regex would be the free-form-parsing failure mode the contract
rejects.

THE TURNS SOURCE -- the gate-readable transcript. `--turns` points at a JSONL file
of role-labelled turns, one object per line: {"turn": "<id>", "role": "user|assistant|...",
"text": "<verbatim turn text>"}. This is the unforgeable source (the role label),
provided by the resolve step (the session transcript excerpt under the working dir);
the eval package bundles its own. A markered task with no turns source cannot be
verified -- the gate fails closed (config error), never a silent PASS.

Exit 0 = every markered task PASS (an unmarkered task is unguarded, PASS). Exit 1 =
>=1 HOLD. Exit 2 = config error (nothing to check, a vacuous root, a markered task
with no/unreadable turns source).

Ships inside the said plugin beside the deliver skill that runs it (review-qa),
run natively -- never a vendored per-project copy. Feature-agnostic: pass task
logs + a turns source; it knows nothing about any one feature.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys

# --- grammar ----------------------------------------------------------------

HEADING = re.compile(r"^##\s+(?P<name>.+?)\s*$", re.MULTILINE)
STATUS_DATE = re.compile(r"^\*\*Status:\*\*[^\n(]*\((?P<date>\d{4}-\d{2}-\d{2})\)", re.MULTILINE)
# A marker LINE is detected loosely (case-insensitive) so a malformed marker fails CLOSED
# (HOLD), never fails open to "unguarded". The id must then be a bare token; a trailing
# annotation, a typo, or extra text makes it malformed -> HOLD, never a silent PASS.
MARKER_LINE = re.compile(r"^\*\*Blocked-on decision:\*\*\s*(?P<rest>.*?)\s*$",
                         re.MULTILINE | re.IGNORECASE)
ID_ONLY = re.compile(r"^[A-Za-z0-9_-]+$")
RECORD = re.compile(
    r"^-\s+(?P<id>[A-Za-z0-9_-]+)\s+resolved-by:\s*"
    r"(?P<actor>[A-Za-z0-9_-]+)(?:@(?P<turn>[A-Za-z0-9_-]+))?\s+--\s+"
    r'"(?P<quote>[^"]*)"\s+--\s+(?P<date>\d{4}-\d{2}-\d{2})'
    r"(?:\s+\[supersedes:\s*(?P<sup>[^\]]+)\])?\s*$",
    re.MULTILINE,
)

# An actor other than a plain operator/user turn. `user` is the only PASS actor; the
# deny-list names the failure set for a precise message (the grant-basis self-default).
DENY = ("grant", "standing-autonomy", "default", "assistant", "subagent", "arm")


class ConfigError(Exception):
    """A misconfiguration -- exit 2, never PASS or HOLD."""


# --- inputs -----------------------------------------------------------------

def _read(path):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def load_turns(path):
    """turn-id -> (role, text) from a JSONL role-labelled transcript. A real parser
    (json per line), never a regex over prose."""
    if not path or not os.path.isfile(path):
        raise ConfigError(f"turns source not found: {path or '(none given)'}")
    turns = {}
    for n, line in enumerate(_read(path).splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except ValueError as e:
            raise ConfigError(f"turns source line {n} is not valid JSON: {e}")
        if not isinstance(obj, dict):
            raise ConfigError(f"turns source line {n} is valid JSON but not an object")
        tid, role, text = obj.get("turn"), obj.get("role"), obj.get("text")
        if not tid or role is None or text is None:
            raise ConfigError(f"turns source line {n} missing turn/role/text")
        turns[str(tid)] = (str(role), str(text))
    return turns


def resolve_task_files(roots):
    """(files, empty_roots) -- a root matching zero files is a vacuity error, never a
    silent PASS (a typo'd glob or a wrong cwd)."""
    files, empty = [], []
    for root in roots:
        got = []
        if os.path.isfile(root):
            got = [root]
        elif os.path.isdir(root):
            got = [os.path.join(dp, fn) for dp, _dn, fns in os.walk(root)
                   for fn in fns if fn.endswith(".md")]
        else:
            got = [p for p in glob.glob(root, recursive=True) if os.path.isfile(p)]
        (files.extend(sorted(got)) if got else empty.append(root))
    return files, empty


# --- parse a task log -------------------------------------------------------

def split_blocks(text):
    """Return (tasks, ledger_text): tasks = [(name, block_text)] for every `## ` block
    except the `## Decisions` ledger, whose combined body is ledger_text."""
    heads = list(HEADING.finditer(text))
    tasks, ledger = [], []
    for i, h in enumerate(heads):
        start = h.end()
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        body = text[start:end]
        if h.group("name").strip().lower() == "decisions":
            ledger.append(body)
        else:
            tasks.append((h.group("name").strip(), body))
    return tasks, "\n".join(ledger)


def records_for(ledger_text, dec_id):
    """Every well-formed ledger record for dec_id, in file order (last = current truth)."""
    return [m.groupdict() for m in RECORD.finditer(ledger_text) if m.group("id") == dec_id]


# --- the predicate ----------------------------------------------------------

class Verdict:
    __slots__ = ("state", "task", "dec_id", "reason")

    def __init__(self, state, task, dec_id, reason):
        self.state, self.task, self.dec_id, self.reason = state, task, dec_id, reason

    def __str__(self):
        head = f"  [{self.state}] {self.task}"
        return head + (f" (decision {self.dec_id}): {self.reason}" if self.dec_id else f": {self.reason}")


def judge_marker(task_name, marker_date, dec_id, ledger_text, turns):
    """PASS/HOLD for one marker -- the structural predicate only."""
    recs = records_for(ledger_text, dec_id)
    if not recs:
        return Verdict("HOLD", task_name, dec_id, "no well-formed `## Decisions` record for it")
    r = recs[-1]  # append-only: the last record supersedes any earlier one
    actor = r["actor"].lower()
    if actor != "user":
        note = " (a deny-listed self-default basis)" if actor in DENY else ""
        return Verdict("HOLD", task_name, dec_id,
                       f"resolved-by actor '{actor}' is not an operator/user turn{note}")
    if not r["turn"]:
        return Verdict("HOLD", task_name, dec_id, "user cite carries no `@<turn>` reference")
    turn = r["turn"]
    if turn not in turns:
        return Verdict("HOLD", task_name, dec_id, f"cited turn '{turn}' is absent from the turns source")
    role, text = turns[turn]
    if role.lower() != "user":
        return Verdict("HOLD", task_name, dec_id, f"cited turn '{turn}' is a {role} turn, not a user turn")
    if not r["quote"].strip():
        return Verdict("HOLD", task_name, dec_id,
                       "the resolution record carries an empty quote (no verbatim evidence)")
    if r["quote"] not in text:
        return Verdict("HOLD", task_name, dec_id,
                       f"the quoted text is not a literal substring of turn '{turn}'")
    if marker_date is None:
        return Verdict("HOLD", task_name, dec_id, "the marker has no `**Status:**` date to anchor the record against")
    if r["date"] < marker_date:
        return Verdict("HOLD", task_name, dec_id,
                       f"the resolution ({r['date']}) predates the marker ({marker_date})")
    return Verdict("PASS", task_name, dec_id, f"operator-attributed (user@{turn}, verbatim, {r['date']})")


def judge_file(path, turns):
    """Every markered task in a log -> a Verdict; an unmarkered log yields one 'no marker' PASS.
    Returns (verdicts, needs_turns) -- needs_turns True when any task carries a marker."""
    text = _read(path)
    tasks, ledger_text = split_blocks(text)
    verdicts, needs_turns = [], False
    for name, body in tasks:
        markers = list(MARKER_LINE.finditer(body))
        if not markers:
            continue
        needs_turns = True
        dm = STATUS_DATE.search(body)
        mdate = dm.group("date") if dm else None
        for m in markers:  # every marker on the task is judged -- a second one is never shadowed
            rest = m.group("rest")
            if not ID_ONLY.match(rest):
                verdicts.append(Verdict("HOLD", f"{path}:{name}", rest or "(empty)",
                                        "malformed `Blocked-on decision` marker -- expected a bare `<id>`"))
                continue
            verdicts.append(judge_marker(f"{path}:{name}", mdate, rest, ledger_text, turns))
    if not verdicts:
        verdicts.append(Verdict("PASS", path, None, "no `Blocked-on decision` marker -- unguarded"))
    return verdicts, needs_turns


# --- driver -----------------------------------------------------------------

BANNER = "decision-gate -- structural attribution predicate for an owed task decision\n" + "-" * 60


def cmd_check(args):
    if not args.tasks:
        raise ConfigError("nothing to check: pass --tasks")
    task_files, empty = resolve_task_files(args.tasks)
    if empty:
        raise ConfigError("a --tasks root matched zero files (a gate that scans nothing must not PASS): "
                          + ", ".join(empty))

    # A markered task needs the turns source to verify attribution. Peek first so a missing
    # --turns fails closed (config), never a silent PASS.
    any_marker = any(MARKER_LINE.search(_read(p)) for p in task_files)
    turns = {}
    if any_marker or args.turns:
        turns = load_turns(args.turns)  # raises ConfigError if absent/unreadable

    verdicts = []
    for p in task_files:
        vs, _ = judge_file(p, turns)
        verdicts.extend(vs)

    holds = [v for v in verdicts if v.state == "HOLD"]
    print(BANNER)
    print(f"scope: {len(task_files)} task file(s), turns source: {args.turns or 'none'}")
    print("-" * 60)
    for v in verdicts:
        print(v)
    print("-" * 60)
    print(f"{'HOLD' if holds else 'PASS'}, {len(verdicts) - len(holds)} PASS, {len(holds)} HOLD")
    print("(structural predicate only; the semantic 'decides, not merely mentions' check is agent-side)")
    return 1 if holds else 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="decision-gate", description="anti-self-default decision gate")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="check task logs against their `## Decisions` ledger")
    c.add_argument("--tasks", nargs="*", default=[], help="task-log files/dirs/globs")
    c.add_argument("--turns", default=None, help="role-labelled turns source (JSONL)")
    c.set_defaults(fn=cmd_check)
    args = ap.parse_args(argv)
    try:
        return args.fn(args)
    except ConfigError as e:
        print(BANNER)
        print(f"  [CONFIG] {e}")
        print("-" * 60)
        print("CONFIG-ERROR, nothing was checked -- fix the inputs.")
        return 2


if __name__ == "__main__":
    sys.exit(main())
