#!/usr/bin/env python3
"""Write one reviewer row into the feature's gate record.

  gate_record_row.py --root <lane-root> --out <record> --file <path> --open-p1 <n> --reviewer <id>

The row is `skill-doctor: <file> open-P1=<n> reviewer=<id>`, one per file: a second call for the same file
replaces it. The record is written through gate_record.py: its first line is the store identity of the physical
lane root; a record written at another store keeps its round and matrix lines and drops its rows, so no
`gate-recompute:` row is ever typed here and a stale one is never carried to a new store. Exit 0 written, 1 refused
value, 2 missing arguments or a record or lane error (`error: <why>`, nothing written).
"""
import argparse, os, re, sys

ap = argparse.ArgumentParser()
for a in ("root", "out", "file", "open-p1", "reviewer"):
    ap.add_argument("--" + a, required=True)
a = ap.parse_args()
if not re.fullmatch(r"\d+", a.open_p1):
    sys.exit("refused: --open-p1 is a count")
for name, val in (("file", a.file), ("reviewer", a.reviewer)):
    if not val or re.search(r"\s", val):
        sys.exit("refused: --%s is one token without whitespace" % name)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True
import gate_record  # noqa: E402  the one reader and writer of the record

mine = "skill-doctor: %s " % a.file


def mutate(store, rows, history):
    rows = [l for l in rows if not l.startswith(mine)]
    return rows + ["skill-doctor: %s open-P1=%s reviewer=%s" % (a.file, a.open_p1, a.reviewer)], history


try:
    gate_record.update(a.out, os.path.realpath(os.path.abspath(a.root)), mutate)
except (gate_record.Error, OSError) as e:
    print("error: %s" % e)
    sys.exit(2)
