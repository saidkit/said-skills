#!/usr/bin/env python3
"""Reads the finding rows of a debrief's working file and prints what Phase A stops on.

  debrief-rows.py stop <debrief.md>

A row is a line inside a section whose heading text starts A.1 to A.6 (a section mark may come first; A.10 is
none) and whose last `|` cell starts `status:`; a deeper heading stays inside the section, a fenced line is no
heading. A row in an A.5 section is a ruling; a row whose action cell is `promote-to-existing` or `create-new` is
a proposal for a document the operator owns; every other row is owned (debrief writes its home). Prints, in file order:
  open: <line> proposal|ruling <first cell> (<status>)   a proposal or ruling still proposed or revise
  warn: line <n> owned row is <status>; Phase A writes an owned row approved
then `own: <n>` and `stop: <k>` (k open rows) or `stop: none`. Exit 0; 2 with `error: <why>` when unreadable.
Writes nothing.
"""
import re
import sys

SECTION = re.compile("^#+\\s+\u00a7?A\\.([1-6])(?![0-9])")
HEADING = re.compile(r"^(#+)\s")
FENCE = re.compile(r"^\s*(```|~~~)")
PROPOSAL = {"promote-to-existing", "create-new"}
OPEN = {"proposed", "revise"}


def cells(line):
    s = line.strip()
    if s.startswith(("- ", "* ")):
        s = s[2:]
    parts = [c.strip() for c in s.strip("|").split("|")]
    return parts if len(parts) >= 2 and parts[-1].startswith("status:") else None


def stop(path):
    try:
        with open(path, encoding="utf-8-sig") as f:
            text = f.read()
    except (OSError, UnicodeDecodeError) as e:
        print("error: cannot read %s: %s" % (path, e))
        return 2
    section, level, owned, opened, fenced = None, 0, 0, 0, False
    for n, line in enumerate(text.splitlines(), 1):
        if FENCE.match(line):
            fenced = not fenced
            continue
        h = None if fenced else HEADING.match(line)
        if h:
            depth = len(h.group(1))
            if section and depth > level:
                continue  # a sub-heading of the section keeps it
            m = SECTION.match(line)
            section, level = (m.group(1), depth) if m else (None, 0)
            continue
        if fenced:
            continue
        row = cells(line) if section else None
        if not row:
            continue
        status = (row[-1][len("status:"):].split() or ["?"])[0]
        kind = "ruling" if section == "5" else "proposal" if row[1] in PROPOSAL else "own"
        if kind == "own":
            owned += 1
            if status in OPEN:
                print("warn: line %d owned row is %s; Phase A writes an owned row approved" % (n, status))
        elif status in OPEN:
            opened += 1
            print("open: %d %s %s (%s)" % (n, kind, row[0], status))
    print("own: %d" % owned)
    print("stop: %d" % opened if opened else "stop: none")
    return 0


def main(argv):
    if len(argv) != 3 or argv[1] != "stop":
        print("error: usage: debrief-rows.py stop <debrief.md>")
        return 2
    return stop(argv[2])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
