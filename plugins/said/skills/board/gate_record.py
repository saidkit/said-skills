#!/usr/bin/env python3
"""The feature's gate record, the Inspect record: its store identity, its rows, its rounds and its sign-off.

  gate_record.py identity --root <lane-root> [--record <record>]
  gate_record.py check    --root <lane-root> --record <record> --reads <read>[,<read>...]
  gate_record.py round    --root <lane-root> --record <record> --matrix-from <file> [--set <key>=<value>]...

Line grammar, one kind per line, read by a line parser:
  store: git <sha> [dirty <sha256>] | store: content <sha256>   first line; the store identity
  gate-recompute: <unit> exit=<n> <PASS|EXPECTED|FAIL> [ids]   rows of the current store (gate_recompute.sh)
  skill-doctor: <file> open-P1=<n> reviewer=<id>               rows of the current store (gate_record_row.py)
  feature-review: <row>                                         rows of the current store
  round: n=<k>, store=<identity>, <key>=<value>, ...            one per round, kept across stores
  matrix@<k>: <task> | covers: <c> | rules-applied: <r> | reviewer: <v>   round k's snapshot, kept across stores
An old first line `head: <sha>` reads as `git <sha>` and is rewritten as `store:` at the next write; `head: none`
matches no store. Rows of a moved store are dropped at the next write; round and matrix lines never are.

identity: `git <HEAD sha>` where the physical lane root is in git, else `content <sha256>` over every file under
  the lane's `SAID.mounts:` (the lane root when `none` or absent), by relative path and bytes, leaving out the
  `SAID.working:` tree, the record itself, `.git` and `__pycache__`; a mount that is a file counts as that file; a
  symlink counts by its target text and is never followed. A mount that is missing, leaves the lane root or lies
  inside the working tree is a lane error.
check: `current` (exit 0); `gate owed` (exit 1) when the record is absent or its store is not the current one
  (an unreadable record is a read error, never overwritten);
  `Inspect owed: <read>, ...` (exit 1) when a named read has no well-formed rows at the current store. Reads:
  gate-recompute (its rows: `<unit> exit=<n> <status> ...`, `<unit> skip (<reason>)` or `<unit> skipped (not selected)`), matrix (the current store's round and its snapshot, every cell non-empty),
  feature-review (a `verdict | PASS` row).
round: writes this store's round row and the snapshot from the `matrix: ` lines of --matrix-from (covers-read.py
  output; `-` reads stdin). The same store replaces its own round; a moved store appends round n+1. Keys:
  decisions, leaks, look, operator-min, rework-min, elapsed-min, tokens; a value is one token of printable ASCII
  without a comma or a space; a key not given is `-`.
A refused round value prints `refused: <why>` and writes nothing (exit 1); exit 2 = a usage, read or lane error
(`error: <why>`).
"""
import hashlib
import os
import subprocess
import sys
import tempfile
import unicodedata

sys.dont_write_bytecode = True
ROW_KINDS = ("gate-recompute: ", "skill-doctor: ", "feature-review: ")
ROUND_KEYS = ("decisions", "leaks", "look", "operator-min", "rework-min", "elapsed-min", "tokens")
READS = ("gate-recompute", "matrix", "feature-review")
STATUSES = ("PASS", "EXPECTED", "FAIL")


FR_MARKERS = ("reviewer-gate:", "verdict:", "goal:", "feature-review:", "feature review owed", "gate owed",
              "inspect owed", "store:", "gate-recompute:", "skill-doctor:", "round:", "matrix@", "operator-question-held")
FR_LINE_CAP = 300  # the validator's longest row is under 200 characters


FR_DECISIONS = "Uncovered decisions"  # group 2: the decisions no Covers line names
FR_GROUPS = (  # the six groups of a feature-review verdict and their table columns, in order; read by said_status too
    ("Covers", ("id", "requirement", "where built", "verdict")),
    (FR_DECISIONS, ("decision", "requirement", "where built", "verdict")),
    ("Uncovered requirements", ("requirement", "where built", "verdict")),
    ("Earned rules", ("rule", "evidence", "differs from Rules applied", "verdict")),
    ("Captures", ("item", "where built", "verdict")),
    ("Other defects", ("defect", "path:line", "verdict")),
)
FR_EDITORIAL = ("Editorial", ("attack or checklist row", "path:line", "finding", "fix shape", "verdict"))  # doc lane only


def fr_groups(doc=False):
    """The groups of a verdict, in order: the six on every lane, Editorial seventh on a doc lane."""
    return FR_GROUPS + ((FR_EDITORIAL,) if doc else ())


def fr_doc_lane(root):
    """True when the lane's `SAID.surface:` is doc: its verdict is review-doc-editorial-<id>.md with seven groups."""
    import said_status  # the engine's one lane-block reader; lazy: said_status imports this module
    return (said_status.lane_block_key(root, "surface") or "").strip().strip("`'\"") == "doc"


def feature_review_problem(lines, doc=False):
    """Why these lines are not the validator's output (`said_status.py --feature-review`), or None: one verdict line
    `feature-review: verdict | PASS|FAIL | not-read=<n>` first, then for each group of fr_groups(doc) in order either one
    `feature-review: <group> | none` line or rows `feature-review: <group> | <id> | <PASS|FAIL|NOT-READ|N/A> | <text>`,
    no control characters, and a verdict and a not-read count that agree with the rows."""
    if not lines or any(any(unicodedata.category(c) in ("Cc", "Cf", "Zl", "Zp") for c in ln) for ln in lines):
        return "no lines, or a control, format or line-break character in one"
    if any(len(ln) > FR_LINE_CAP for ln in lines):
        return "a line is longer than %d characters" % FR_LINE_CAP
    names = tuple(g for g, _cols in fr_groups(doc))
    if any(m in ln[len("feature-review: "):].lower() for ln in lines for m in FR_MARKERS):
        return "an authoritative marker in a row"
    head = lines[0].split(" | ")
    if len(head) != 3 or head[0] != "feature-review: verdict" or head[1] not in ("PASS", "FAIL") \
            or not head[2].startswith("not-read=") or not (head[2][9:].isascii() and head[2][9:].isdigit()):
        return "the first line is not a verdict line"
    fails = nots = 0
    seen = []
    for ln in lines[1:]:
        if not ln.startswith("feature-review: "):
            return "a line is not a feature-review line"
        cells = ln[len("feature-review: "):].split(" | ")
        if len(cells) == 2 and cells[1] == "none" and cells[0] in names:
            group = cells[0]
        elif len(cells) == 4 and cells[1].strip().lower() == "none":  # `none` is a line, not a row
            return "a `none` row in a group"
        elif len(cells) == 4 and cells[0] in names and cells[1] and cells[3] and cells[2] in (
                ("PASS", "FAIL", "NOT-READ", "N/A") if cells[0] == "Earned rules" else ("PASS", "FAIL", "NOT-READ")):
            group = cells[0]
            fails += cells[2] == "FAIL"
            nots += cells[2] == "NOT-READ"
        else:
            return "a line is not a group row"
        if not seen or seen[-1] != group:
            seen.append(group)
        elif group in [s for s in seen[:-1]]:
            return "group rows out of order"
    if tuple(seen) != names:
        return "the %d groups are not each present once, in order" % len(names)
    if head[1] == "PASS" and fails or head[1] == "FAIL" and not fails or int(head[2][9:]) != nots:
        return "the verdict or the not-read count disagrees with the rows"
    return None


class Error(Exception):
    pass


class Refused(Error):
    """A value the record does not take: exit 1, nothing written."""


class Moved(Refused):
    """The lane's store changed after the caller validated what it writes: nothing is written, the step is owed."""


def lane_key(root, name):
    """The value of `SAID.<name>:` in the lane's `## Lane` block, or None."""
    try:
        with open(os.path.join(root, "CLAUDE.md"), encoding="utf-8-sig") as fh:
            text = fh.read()
    except (OSError, UnicodeDecodeError):
        return None
    in_lane = False
    for line in text.split("\n"):
        if line.startswith("## "):
            in_lane = line[3:].strip().startswith("Lane")
            continue
        s = line.strip().lstrip("-* ").strip()
        if in_lane and s.startswith("SAID.%s:" % name):
            return s[len("SAID.%s:" % name):].strip()
    return None


def mount_list(value):
    """The `SAID.mounts:` list, read whole: `[a/, b/]`, `none` or absent (None) -> paths."""
    if value is None or value == "none":
        return []
    v = value.strip()
    if v.startswith("[") and v.endswith("]"):
        v = v[1:-1]
    return [m.strip() for m in v.split(",") if m.strip()]


def git_sha(phys):
    try:
        r = subprocess.run(["git", "-C", phys, "rev-parse", "HEAD"], capture_output=True, text=True)
    except OSError:
        return None
    sha = r.stdout.strip()
    return sha if r.returncode == 0 and sha else None


def inside(path, top):
    return path == top or path.startswith(top + os.sep)


def entry(p, phys):
    if os.path.islink(p):
        digest = "link:" + os.readlink(p)
    else:
        with open(p, "rb") as fh:
            digest = hashlib.sha256(fh.read()).hexdigest()
    return "%s\0%s\n" % (os.path.relpath(p, phys), digest)


def git_dirty(phys, mounts, skip, own):
    """Sorted entries of the mount paths that differ from HEAD (staged, unstaged, untracked, deleted)."""
    spec = [m.strip("`'\"") or "." for m in mounts]
    try:
        top = subprocess.run(["git", "-C", phys, "rev-parse", "--show-toplevel"], capture_output=True, text=True)
        st = subprocess.run(["git", "--literal-pathspecs", "-C", phys, "status", "--porcelain=v1", "-z", "--untracked-files=all", "--no-renames",
                             "--"] + spec, capture_output=True)
    except OSError as e:
        raise Error("git status failed: %s" % e)
    if top.returncode != 0 or st.returncode != 0:
        raise Error("git status failed in %s" % phys)
    top = os.path.realpath(top.stdout.strip())
    entries = []
    for rec in st.stdout.split(b"\0"):
        if len(rec) < 4:
            continue
        p = os.path.join(top, os.fsdecode(rec[3:]))
        real = os.path.realpath(p)
        if real in own or (skip and inside(real, skip)) or not inside(os.path.abspath(p), phys):
            continue
        if os.path.islink(p) or (os.path.lexists(p) and not os.path.isdir(p)):
            entries.append(entry(p, phys))
        else:
            entries.append("%s\0deleted\n" % os.path.relpath(p, phys))
    return sorted(set(entries))


def digest(entries):
    h = hashlib.sha256()
    for e in sorted(set(entries)):
        h.update(e.encode("utf-8", "surrogateescape"))
    return h.hexdigest()


def identity(root, record=None):
    """The store identity of the lane at root; the record file itself is never part of it. In git it is the HEAD
    sha, plus `dirty <sha256>` over the changed mount paths when the tree under the mounts differs from HEAD."""
    phys = os.path.realpath(os.path.abspath(root))
    sha = git_sha(phys)
    working = (lane_key(phys, "working") or "").strip().strip("`'\"")
    work_top = working.split("<", 1)[0].strip().strip("/")
    skip = os.path.realpath(os.path.join(phys, work_top)) if work_top else None
    own = {os.path.realpath(record)} if record else set()
    mounts = mount_list(lane_key(phys, "mounts")) or ["."]
    if sha:
        dirty = git_dirty(phys, mounts, skip, own)
        return "git %s dirty %s" % (sha, digest(dirty)) if dirty else "git " + sha
    entries = []
    for m in mounts:
        m = m.strip("`'\"")
        joined = os.path.join(phys, m)
        top = os.path.realpath(joined)
        if not inside(top, phys):
            raise Error("mount %s leaves the lane root" % m)
        if not os.path.lexists(joined):
            raise Error("mount %s does not exist" % m)
        if skip and inside(top, skip):
            raise Error("mount %s lies inside the SAID.working: tree" % m)
        if not os.path.isdir(joined):
            if os.path.realpath(joined) not in own:
                entries.append(entry(joined.rstrip("/"), phys))
            continue
        for dp, dn, fn in os.walk(top):
            linked = [d for d in dn if os.path.islink(os.path.join(dp, d))]
            dn[:] = sorted(d for d in dn if d not in (".git", "__pycache__") and d not in linked
                           and os.path.join(dp, d) != skip)
            for f in sorted(fn) + sorted(linked):
                p = os.path.join(dp, f)
                if p not in own:
                    entries.append(entry(p, phys))
    return "content " + digest(entries)


def load(path):
    """(store identity or None, rows, history) of a record; None when the record is absent."""
    try:
        with open(path, encoding="utf-8-sig") as fh:
            lines = [ln.rstrip("\r") for ln in fh.read().split("\n")]
    except FileNotFoundError:
        return None
    except (OSError, UnicodeDecodeError) as e:
        raise Error("cannot read the record %s (left as it is): %s" % (path, e))
    first = lines[0] if lines else ""
    if first.startswith("store: "):
        store = first[len("store: "):].strip()
    elif first.startswith("head: "):
        old = first[len("head: "):].strip()
        store = None if old in ("", "none") else "git " + old
    else:
        store = None
    rows = [ln for ln in lines[1:] if ln.startswith(ROW_KINDS)]
    history = [ln for ln in lines[1:] if ln.startswith("round: ") or (ln.startswith("matrix@") and ": " in ln)]
    return store, rows, history


def write(path, store, rows, history):
    """Write the whole record atomically: a fresh temp file in its folder, flushed to disk, then renamed over it."""
    folder = os.path.dirname(os.path.abspath(path))
    os.makedirs(folder, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".gate-record-", dir=folder)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write("store: %s\n" % store)
            for ln in rows + history:
                fh.write(ln + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        mask = os.umask(0)
        os.umask(mask)
        os.chmod(tmp, 0o666 & ~mask)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def update(path, root, mutate, expect=None):
    """Rewrite the record at the current store: rows of another store dropped, history kept, mutate(rows, history).
    With `expect` (the identity the caller validated its rows at), a store that differs now is Moved: nothing is written."""
    store = identity(root, path)
    if expect is not None and store != expect:
        raise Moved("the lane's store changed while the rows were validated (%s, now %s)" % (expect, store))
    prior = load(path)
    rows, history = [], []
    if prior is not None:
        rows = prior[1] if prior[0] == store else []
        history = prior[2]
    rows, history = mutate(store, rows, history)
    write(path, store, rows, history)
    return store


def round_fields(line):
    """{key: value} of a `round: ` line."""
    out = {}
    for pair in line[len("round: "):].split(", "):
        k, sep, v = pair.partition("=")
        if sep:
            out[k] = v
    return out


def matrix_ok(line):
    body = line.split(": ", 1)[1] if ": " in line else ""
    cells = body.split(" | ")
    if len(cells) != 4 or not cells[0].strip():
        return False
    for cell, label in zip(cells[1:], ("covers:", "rules-applied:", "reviewer:")):
        if not cell.startswith(label) or not cell[len(label):].strip():
            return False
    return True


def gate_row_ok(line):
    """`<unit> exit=<n> <status> [ids]` (the unit may hold spaces), a declared `<unit> skip (<reason>)`, or a unit left
    out of a selected run, `<unit> skipped (not selected)`."""
    body = line[len("gate-recompute: "):]
    left_out = " skipped (not selected)"
    if body.endswith(left_out):
        return bool(body[:-len(left_out)].strip())
    unit, sep, reason = body.partition(" skip (")
    if sep:
        return bool(unit.strip()) and reason.endswith(")") and bool(reason[:-1].strip())
    parts = body.split()
    for i, p in enumerate(parts):
        if p.startswith("exit="):
            return i > 0 and p[5:].lstrip("-").isdigit() and i + 1 < len(parts) and parts[i + 1] in STATUSES
    return False


def check(root, path, reads):
    for r in reads:
        if r not in READS:
            raise Error("unknown read %s" % r)
    rec = load(path)
    if rec is None or rec[0] is None or rec[0] != identity(root, path):
        return 1, "gate owed"
    store, rows, history = rec
    owed = []
    for r in reads:
        if r == "gate-recompute":
            mine = [ln for ln in rows if ln.startswith("gate-recompute: ")]
            ok = bool(mine) and all(gate_row_ok(ln) for ln in mine)
        elif r == "feature-review":
            mine = [ln for ln in rows if ln.startswith("feature-review: ")]
            sound = feature_review_problem(mine, fr_doc_lane(root)) is None  # a hand-edited or inconsistent set is never current
            ok = sound and mine[0].startswith("feature-review: verdict | PASS | ")  # a FAIL verdict is owed until its rows are fixed
            if sound and not ok:
                r = "feature-review FAIL"  # its own owed line: the FAIL rows go to tasks, the reviewer is not rerun
        else:
            rounds = [round_fields(ln) for ln in history if ln.startswith("round: ")]
            last = rounds[-1] if rounds else {}
            snap = [ln for ln in history if ln.startswith("matrix@%s: " % last.get("n", "?"))]
            ok = last.get("store") == store and bool(snap) and all(matrix_ok(ln) for ln in snap)
        if not ok:
            owed.append(r)
    if owed:
        return 1, "Inspect owed: " + ", ".join(owed)
    return 0, "current"


def read_matrix(src):
    try:
        if src == "-":
            text = sys.stdin.read()
        else:
            with open(src, encoding="utf-8") as fh:
                text = fh.read()
    except (OSError, UnicodeDecodeError) as e:
        raise Error("cannot read --matrix-from %s: %s" % (src, e))
    return [ln.rstrip("\r")[len("matrix: "):] for ln in text.split("\n") if ln.startswith("matrix: ")]


def value_ok(v):
    return bool(v) and v.isascii() and v.isprintable() and not any(c in v for c in ", ")


def do_round(root, path, src, sets):
    given = {}
    for s in sets:
        k, sep, v = s.partition("=")
        if not sep or k not in ROUND_KEYS:
            raise Refused("unknown round key %s (keys: %s)" % (k, ", ".join(ROUND_KEYS)))
        if not value_ok(v):
            raise Refused("value of %s is not one token without a comma or a space" % k)
        given[k] = v
    snapshot = read_matrix(src)

    def mutate(store, rows, history):
        rounds = [round_fields(ln) for ln in history if ln.startswith("round: ")]
        last = rounds[-1] if rounds else None
        if last and last.get("store") == store and last.get("n", "").isdigit():
            n = int(last["n"])
            history = [ln for ln in history if not (ln.startswith("matrix@%d: " % n)
                       or (ln.startswith("round: ") and round_fields(ln).get("n") == str(n)))]
        else:
            n = max([int(r["n"]) for r in rounds if r.get("n", "").isdigit()] or [0]) + 1
        pairs = ["n=%d" % n, "store=%s" % store] + ["%s=%s" % (k, given.get(k, "-")) for k in ROUND_KEYS]
        history = history + ["round: " + ", ".join(pairs)] + ["matrix@%d: %s" % (n, m) for m in snapshot]
        return rows, history

    update(path, root, mutate)


def parse(argv):
    if not argv or argv[0] not in ("identity", "check", "round"):
        raise Error("usage: " + __doc__.strip().splitlines()[2].strip() + " | check ... | round ...")
    cmd, opts, sets, i = argv[0], {}, [], 1
    while i < len(argv):
        k = argv[i]
        if i + 1 >= len(argv) or k not in ("--root", "--record", "--reads", "--matrix-from", "--set"):
            raise Error("usage: unknown or incomplete option %s" % k)
        if k == "--set":
            sets.append(argv[i + 1])
        else:
            opts[k[2:]] = argv[i + 1]
        i += 2
    need = {"identity": ("root",), "check": ("root", "record", "reads"), "round": ("root", "record", "matrix-from")}[cmd]
    for k in need:
        if k not in opts:
            raise Error("usage: %s needs --%s" % (cmd, k))
    if not os.path.isdir(opts["root"]):
        raise Error("not a directory: --root %s" % opts["root"])
    opts["root"] = os.path.realpath(os.path.abspath(opts["root"]))
    if "record" in opts:
        opts["record"] = os.path.abspath(opts["record"])
    return cmd, opts, sets


def main(argv):
    try:
        cmd, o, sets = parse(argv)
        if cmd == "identity":
            print("store: " + identity(o["root"], o.get("record")))
            return 0
        if cmd == "check":
            code, text = check(o["root"], o["record"], [r for r in o["reads"].split(",") if r])
            print(text)
            return code
        do_round(o["root"], o["record"], o["matrix-from"], sets)
        return 0
    except Refused as e:
        print("refused: %s" % e)
        return 1
    except (Error, OSError) as e:
        print("error: %s" % e)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
