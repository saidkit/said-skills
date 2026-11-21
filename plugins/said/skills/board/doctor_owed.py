#!/usr/bin/env python3
"""The skill-doctor rows a task owes, derived from its diff, never from a hand list.

  doctor_owed.py --root <lane-root> --record <record> --base <task base>

The owed files are the files the diff `<task base>..<the record's store>` adds or changes (a deleted file owes
nothing) that are skill text: under the lane's `SAID.mounts:` (the lane root when `none` or absent) with a text
extension (.md, .json, .txt, .tsv, .yaml, .yml; a script owes no row), plus the lane root's `CHANGELOG.md`. A file
is covered by a `skill-doctor: <file> open-P1=0 reviewer=<id> base=<sha>` row of the record whose base is the task
base or an ancestor of it, so the review read the whole task's change. Each owed file not covered prints
`skill-doctor owed: <file> (<why>)`: no row, an open P1, a row with no base, or a row whose base is after the task
base. A record whose store is not the lane's current one adds `gate owed: ...`: its rows hold at its own store
only. A record at a dirty store (uncommitted change under the mounts) adds `gate owed: the record is at a dirty
store ...`: the diff reads commits only, so the change is committed before its rows are written. The last line is `skill-doctor: current, <n> file(s) covered` or `skill-doctor: <k> of <n> file(s) owed`.
Exit 0 nothing owed, 1 something owed, 2 a usage, record, lane or git error (`error: <why>`).
"""
import os
import re
import subprocess
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gate_record  # noqa: E402  the one reader of the record and the lane block

TEXT = (".md", ".json", ".txt", ".tsv", ".yaml", ".yml")  # a reference a skill reads; a script is run, not read
ROW = re.compile(r"(\S+) open-P1=([0-9]+) reviewer=(\S+)(?: base=([0-9a-f]{40}))?")


class Error(Exception):
    pass


def git(root, *args):
    r = subprocess.run(["git", "-C", root] + list(args), capture_output=True, text=True)
    return r.returncode, r.stdout.strip()


def resolve(root, rev):
    """The full commit sha of rev in the lane's repository."""
    rc, out = git(root, "rev-parse", "--verify", "--quiet", rev + "^{commit}")
    if rc != 0 or not re.fullmatch(r"[0-9a-f]{40}", out):
        raise Error("%s is not a commit of the lane" % rev)
    return out


def owed_files(root, base, tip):
    """The skill-text files the diff base..tip adds or changes, lane-relative, sorted."""
    rc, out = git(root, "diff", "--name-only", "--diff-filter=d", "-M", base, tip)
    if rc != 0:
        raise Error("git diff %s..%s failed" % (base[:12], tip[:12]))
    mounts = [m.strip("`'\"").strip("/") for m in gate_record.mount_list(gate_record.lane_key(root, "mounts"))] or [""]
    owed = []
    for f in out.split("\n"):
        if not f:
            continue
        under = any(m in ("", ".") or f.startswith(m + "/") for m in mounts)
        if f == "CHANGELOG.md" or (under and f.lower().endswith(TEXT)):
            owed.append(f)
    return sorted(set(owed))


def is_after(root, row_base, task_base):
    """True when row_base is neither the task base nor an ancestor of it."""
    if row_base == task_base:
        return False
    rc, _ = git(root, "merge-base", "--is-ancestor", row_base, task_base)
    return rc != 0


def rows_by_file(rows):
    """{file: (open_p1, reviewer, base or None)} of the record's skill-doctor rows; a malformed row is skipped."""
    out = {}
    for ln in rows:
        if ln.startswith("skill-doctor: "):
            m = ROW.fullmatch(ln[len("skill-doctor: "):])
            if m:
                out[m.group(1)] = (int(m.group(2)), m.group(3), m.group(4))
    return out


def owed(root, record, base):
    """(lines, owed count): the owed lines, the gate-owed line and the last line."""
    root = os.path.realpath(os.path.abspath(root))
    rec = gate_record.load(record)
    if rec is None:
        return ["gate owed: no record", "skill-doctor: owed, no record"], 1
    store, rows, _ = rec
    m = re.fullmatch(r"git ([0-9a-f]{40})( dirty [0-9a-f]{64})?", store or "")
    if not m:
        raise Error("the record's store %r is not a git store" % store)
    tip, task_base = m.group(1), resolve(root, base)
    files = owed_files(root, task_base, tip)
    have = rows_by_file(rows)
    out = []
    for f in files:
        if f not in have:
            why = "no row"
        elif have[f][0] != 0:
            why = "open-P1=%d" % have[f][0]
        elif have[f][2] is None:
            why = "row has no base"
        elif is_after(root, have[f][2], task_base):
            why = "row base %s is after the task base %s" % (have[f][2][:12], task_base[:12])
        else:
            continue
        out.append("skill-doctor owed: %s (%s)" % (f, why))
    n = len(out)
    lane = gate_record.identity(root, record)
    if store != lane:
        out.append("gate owed: the record is at %s, the lane at %s" % (store, lane))
    elif m.group(2):
        out.append("gate owed: the record is at a dirty store (%s): commit the change, then write its rows" % store)
    held = not n and store == lane and not m.group(2)
    out.append("skill-doctor: current, %d file(s) covered" % len(files) if held
               else "skill-doctor: %d of %d file(s) owed" % (n, len(files)))
    return out, 0 if held else max(n, 1)


def main(argv):
    args = {}
    it = iter(argv)
    for a in it:
        if a not in ("--root", "--record", "--base"):
            print("error: unknown argument %s" % a)
            return 2
        args[a] = next(it, None)
    for k in ("--root", "--record", "--base"):
        if not args.get(k):
            print("error: %s is required" % k)
            return 2
    try:
        lines, n = owed(args["--root"], args["--record"], args["--base"])
    except (Error, gate_record.Error, OSError) as e:
        print("error: %s" % e)
        return 2
    print("\n".join(lines))
    return 1 if n else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
