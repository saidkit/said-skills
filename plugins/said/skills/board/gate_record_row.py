#!/usr/bin/env python3
"""Write one reviewer row into the feature's gate record.

  gate_record_row.py --root <lane-root> --out <record> --file <path> --open-p1 <n> --reviewer <id>

The row is `skill-doctor: <file> open-P1=<n> reviewer=<id>`, one per file: a second call for the same file
replaces it. The record's `head:` is the HEAD of the physical lane root ("none" without git). An absent record, or
one written at another head, becomes a record holding that head and this row alone: no `gate-recompute:` row is
ever typed here, and a stale one is never carried to a new head. Exit 0 written, 1 refused value, 2 missing arguments.
"""
import argparse, os, re, subprocess, sys

ap = argparse.ArgumentParser()
for a in ("root", "out", "file", "open-p1", "reviewer"):
    ap.add_argument("--" + a, required=True)
a = ap.parse_args()
if not re.fullmatch(r"\d+", a.open_p1):
    sys.exit("refused: --open-p1 is a count")
for name, val in (("file", a.file), ("reviewer", a.reviewer)):
    if not val or re.search(r"\s", val):
        sys.exit("refused: --%s is one token without whitespace" % name)
phys = os.path.realpath(a.root)
try:
    sha = subprocess.run(["git", "-C", phys, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip() or "none"
except OSError:
    sha = "none"
lines = []
try:
    prior = open(a.out).read().split("\n")
    if prior[0] == "head: %s" % sha:
        lines = [l for l in prior[1:] if l]
except OSError:
    pass
mine = "skill-doctor: %s " % a.file
lines = [l for l in lines if not l.startswith(mine)]
lines.append("skill-doctor: %s open-P1=%s reviewer=%s" % (a.file, a.open_p1, a.reviewer))
os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
tmp = a.out + ".tmp"
with open(tmp, "w") as f:
    f.write("head: %s\n" % sha)
    for l in lines:
        f.write(l + "\n")
os.replace(tmp, a.out)
