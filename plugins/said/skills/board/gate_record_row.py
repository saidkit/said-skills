#!/usr/bin/env python3
"""Write one reviewer row into the feature's gate record.

  gate_record_row.py --root <lane-root> --out <record> --file <path> --open-p1 <n> --reviewer <id>
  gate_record_row.py --kind feature-review --root <lane-root> --out <record> --workdir <dir> --feature <id>
                     [--decisions <file>...]

The row is `skill-doctor: <file> open-P1=<n> reviewer=<id>`, one per file: a second call for the same file
replaces it. The record is written through gate_record.py: its first line is the store identity of the physical
lane root; a record written at another store keeps its round and matrix lines and drops its rows, so no
`gate-recompute:` row is ever typed here and a stale one is never carried to a new store. The feature-review form
runs the validator itself (said_status.feature_review_output, the code behind `said_status.py --feature-review`) on
<workdir>/review-feature-<id>.md and writes only the `feature-review: ` rows it produced, replacing every earlier
feature-review row of the record; it takes no rows from a file or stdin, so a row is never typed. With --decisions
(the decision records the reviewer was briefed with), each decision id of those records needs a row in Covers or
Uncovered decisions: the live rulings of a `rulings.md`, the `Q-<n>` ids of a `scope.md` section D, the `DL-`/`CL-`
first words of any other file (a ledger), fenced lines skipped; a missing one is owed, a named file that is not
there, cannot be read or holds a malformed ruling line an error. It prints the rows
it wrote. Exit 0 written, 1 refused (the validator's owed lines are printed, nothing written), 2 missing arguments or
a record, lane or validator error (`error: <why>`, nothing written).
"""
import argparse, os, re, sys

class Parser(argparse.ArgumentParser):
    def error(self, message):
        print("error: %s" % message)  # the line the skills promise on stdout, exit 2
        sys.exit(2)


ap = Parser()
ap.add_argument("--kind", choices=("skill-doctor", "feature-review"), default="skill-doctor")
ap.add_argument("--workdir")
ap.add_argument("--feature")
ap.add_argument("--rows-from")
ap.add_argument("--decisions", nargs="+")
for a in ("root", "out", "file", "open-p1", "reviewer"):
    ap.add_argument("--" + a, required=False)
a = ap.parse_args()
fr = a.kind == "feature-review"
if not fr and a.decisions:
    ap.error("--decisions is taken by --kind feature-review only")
if fr and a.rows_from is not None:
    ap.error("--rows-from is not taken by --kind feature-review: the rows come from the validator")
for name in (("root", "out", "workdir", "feature") if fr else ("root", "out", "file", "open_p1", "reviewer")):
    if not getattr(a, name):
        ap.error("--%s is required" % name.replace("_", "-"))
new_rows = []
if fr:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    sys.dont_write_bytecode = True
    import gate_record as _gr  # noqa: E402
    try:
        seen_at = _gr.identity(os.path.realpath(os.path.abspath(a.root)), a.out)  # the store the rows are validated at
    except (_gr.Error, OSError) as e:
        print("error: %s" % e)
        sys.exit(2)
    import said_status as _ss  # noqa: E402
    rc, lines = _ss.feature_review_output(a.root, a.workdir, a.feature, a.decisions or ())
    if rc == 2:
        print(lines[0])
        sys.exit(2)
    if rc == 1:
        print("\n".join(lines))
        sys.exit(1)
    why = _gr.feature_review_problem(lines)
    if why:
        print("feature review owed: the validator output is not a feature-review record (%s)" % why)
        sys.exit(1)
    new_rows = lines
elif not re.fullmatch(r"[0-9]+", a.open_p1):
    print("refused: --open-p1 is a count")
    sys.exit(1)
for name, val in (() if fr else (("file", a.file), ("reviewer", a.reviewer))):
    if not val or not val.isascii() or re.search(r"\s", val) or any(ord(c) < 32 or ord(c) == 127 for c in val):
        print("refused: --%s is one ASCII token without whitespace" % name)
        sys.exit(1)
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
    gate_record.update(a.out, os.path.realpath(os.path.abspath(a.root)), mutate, expect=seen_at if fr else None)
except gate_record.Moved as e:
    print("feature review owed: %s" % e)
    sys.exit(1)
except (gate_record.Error, OSError) as e:
    print("error: %s" % e)
    sys.exit(2)
if fr:
    print("\n".join(new_rows))
