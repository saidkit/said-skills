#!/usr/bin/env python3
"""Write one reviewer row into the feature's gate record.

  gate_record_row.py --root <lane-root> --out <record> --file <path> --open-p1 <n> --reviewer <id>
  gate_record_row.py --kind feature-review --root <lane-root> --out <record> --rows-from <file|->

The row is `skill-doctor: <file> open-P1=<n> reviewer=<id>`, one per file: a second call for the same file
replaces it. The record is written through gate_record.py: its first line is the store identity of the physical
lane root; a record written at another store keeps its round and matrix lines and drops its rows, so no
`gate-recompute:` row is ever typed here and a stale one is never carried to a new store. The feature-review form writes the `feature-review: ` lines that `said_status.py --feature-review` printed
(from a file, or `-` for stdin): it replaces every earlier feature-review row of the record, and refuses input that
holds a line not starting `feature-review: `, a `feature-review: header` line, or no verdict line, so a row is
never typed by hand. Exit 0 written, 1 refused
value, 2 missing arguments or a record or lane error (`error: <why>`, nothing written).
"""
import argparse, os, re, sys

ap = argparse.ArgumentParser()
ap.add_argument("--kind", choices=("skill-doctor", "feature-review"), default="skill-doctor")
ap.add_argument("--rows-from")
for a in ("root", "out", "file", "open-p1", "reviewer"):
    ap.add_argument("--" + a, required=False)
a = ap.parse_args()
fr = a.kind == "feature-review"
for name in (("root", "out", "rows_from") if fr else ("root", "out", "file", "open_p1", "reviewer")):
    if not getattr(a, name):
        ap.error("--%s is required" % name.replace("_", "-"))
new_rows = []
if fr:
    try:
        text = sys.stdin.read() if a.rows_from == "-" else open(a.rows_from, encoding="utf-8").read()
    except (OSError, UnicodeError) as e:
        print("error: --rows-from is unreadable: %s" % type(e).__name__)
        sys.exit(2)
    new_rows = [l for l in text.split("\n") if l.strip()]
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    sys.dont_write_bytecode = True
    import gate_record as _gr  # noqa: E402
    why = _gr.feature_review_problem(new_rows)
    if why:
        sys.exit("refused: --rows-from holds no validator output (%s)" % why)
elif not re.fullmatch(r"\d+", a.open_p1):
    sys.exit("refused: --open-p1 is a count")
for name, val in (() if fr else (("file", a.file), ("reviewer", a.reviewer))):
    if not val or re.search(r"\s", val):
        sys.exit("refused: --%s is one token without whitespace" % name)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True
import gate_record  # noqa: E402  the one reader and writer of the record

mine = "skill-doctor: %s " % a.file if not fr else ""


def mutate(store, rows, history):
    if fr:
        return [l for l in rows if not l.startswith("feature-review: ")] + new_rows, history
    rows = [l for l in rows if not l.startswith(mine)]
    return rows + ["skill-doctor: %s open-P1=%s reviewer=%s" % (a.file, a.open_p1, a.reviewer)], history


try:
    gate_record.update(a.out, os.path.realpath(os.path.abspath(a.root)), mutate)
except (gate_record.Error, OSError) as e:
    print("error: %s" % e)
    sys.exit(2)
