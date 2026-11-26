#!/usr/bin/env python3
"""The feature's gate record, the Inspect record: its store identity, its rows, its rounds and its sign-off.

  gate_record.py identity --root <lane-root> [--record <record>]
  gate_record.py check    --root <lane-root> --record <record> --reads <read>[,<read>...]
  gate_record.py round    --root <lane-root> --record <record> --matrix-from <file> [--set <key>=<value>]...
  gate_record.py report   --root <lane-root> --record <record>
  gate_record.py debrief-open --root <lane-root> --record <record>
  gate_record.py debrief-seal --root <lane-root> --record <record>
  gate_record.py debrief-window --root <lane-root> --record <record>

Line grammar, one kind per line, read by a line parser:
  store: tree <sha256> [dirty <sha256>] [sources <sha256>] | store: content <sha256>   first line; the store identity
  source: <lane-relative path>                                  one per file the feature read was briefed with
  gate-recompute: <unit> exit=<n> <PASS|EXPECTED|FAIL> [ids]   rows of the current store (gate_recompute.sh)
  skill-doctor: <file> open-P1=<n> reviewer=<id> [base=<sha>]  rows of the current store (gate_record_row.py)
  feature-review: <row>                                         rows of the current store
  record-fail: <n>                                              reads with a record-class FAIL row at this store
  round: n=<k>, store=<identity>, <key>=<value>, ...            one per round, kept across stores
  matrix@<k>: <task> | covers: <c> | rules-applied: <r> | reviewer: <v>   round k's snapshot, kept across stores
An old first line `head: <sha>` reads as `git <sha>`, a form no current store has (the record reads gate owed once),
and is rewritten as `store:` at the next write; `head: none` matches no store. Rows of a moved store are dropped at the next write; round and matrix lines never are.

identity: `tree <sha256>` where the physical lane root is in git (see identity()), else `content <sha256>` over every file under
  the lane's `SAID.mounts:` (the lane root when `none` or absent), by relative path and bytes, leaving out the
  `SAID.working:` tree, the record itself, `.git` and `__pycache__`; a mount that is a file counts as that file; a
  symlink counts by its target text and is never followed. A mount that is missing, leaves the lane root or lies
  inside the working tree is a lane error.
sources: the feature-review writer adds `sources <sha256>` to the store line, a digest over the path and bytes of each
  `source:` file (feature specs and task logs without debrief's sections, CLAUDE.md by its lane and rules). Only the feature-review read compares it: a record without it, or with a digest the
  files no longer give, reads that read owed, unless the task log's last `## Debrief close` footer has no task below
  it. At a write, feature-review rows whose sources moved are dropped; the other rows keep to the lane part.
check: `current` (exit 0); `gate owed` (exit 1) when the record is absent or its store is not the current one
  (an unreadable record is a read error, never overwritten);
  `Inspect owed: <read>, ...` (exit 1) when a named read has no well-formed rows at the current store. Reads:
  gate-recompute (its rows: `<unit> exit=<n> <status> ...`, `<unit> skip (<reason>)` or `<unit> skipped (not selected)`), matrix (the current store's round and its snapshot, every cell non-empty),
  feature-review (a `verdict | PASS` row).
round: writes this store's round row and the snapshot from the `matrix: ` lines of --matrix-from (covers-read.py
  output; `-` reads stdin). The same store replaces its own round; a moved store appends round n+1. Keys:
  decisions, leaks, look, operator-min, rework-min, elapsed-min, tokens; a value is one token of printable ASCII
  without a comma or a space; a key not given is `-`.
report: the Inspect report, derived from the record and the lane's store, never written: the store, the check line
  over every read, each owed line, then each read and the skill-doctor rows with a status and their rows. A read the
  check names, a run that left a unit out, a FAIL row, an open P1 or a moved store reads owed, never current. Exit 0
  nothing owed, 1 something owed.
debrief-open: before debrief's first edit, on a current feature-review read, opens a window row. debrief-seal: after its
  last edit, moves the sources part to the spec and task log as they now stand and closes the window; a change to any
  other source refuses (exit 1, nothing written), except a pending ruling marked landed with its home.
  debrief-window: prints whether the record holds an open window (a read; a refused seal leaves one).
A refused round value prints `refused: <why>` and writes nothing (exit 1); exit 2 = a usage, read or lane error
(`error: <why>`).
"""
import hashlib
import os
import re
import subprocess
import sys
import tempfile
import unicodedata

sys.dont_write_bytecode = True
ROW_KINDS = ("gate-recompute: ", "skill-doctor: ", "feature-review: ", "record-fail: ", "debrief-window: ")
FR_RECORD = "record: "  # the evidence prefix of a FAIL row whose cites sit in the feature's records only
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


def fr_class_rows(rows):
    """The ids of the record-class FAIL rows among feature-review rows."""
    out = []
    for ln in rows:
        cells = ln[len("feature-review: "):].split(" | ") if ln.startswith("feature-review: ") else []
        if len(cells) == 4 and cells[0] != "verdict" and cells[2] == "FAIL" and cells[3].startswith(FR_RECORD):
            out.append(cells[1])
    return out


def fr_record_only(rows):
    """True when the feature-review rows hold a FAIL and every FAIL row is of the record class."""
    fails = [ln for ln in rows if ln.startswith("feature-review: ") and " | FAIL | " in ln
             and not ln.startswith("feature-review: verdict")]
    return bool(fails) and len(fr_class_rows(fails)) == len(fails)


def record_fails(rows):
    """The count on the record's `record-fail:` row, 0 without one."""
    for ln in rows:
        if ln.startswith("record-fail: ") and ln[len("record-fail: "):].isdigit():
            return int(ln[len("record-fail: "):])
    return 0


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


def git_dirty(phys, mounts, skip, own, leave=lambda rel: False):
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
        if leave(os.path.relpath(os.path.abspath(p), phys)):
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


def without_debrief(data):
    """The bytes of a feature file without the sections debrief writes: each `## Lessons`, `## Debrief close` and
    `## Account (<id>)` section, up to the next `## ` heading outside a code fence."""
    out, drop, fence = [], False, False
    for ln in data.split(b"\n"):
        mark = ln.lstrip()[:3]
        if mark in (b"```", b"~~~") and (not fence or fence == mark):
            fence = False if fence else mark
        elif not fence and ln.startswith(b"## "):
            drop = bool(re.match(rb"## +(Lessons *(\(|\r?$)|Debrief close\b|Account \()", ln, re.I))
        if not drop:
            out.append(ln)
    return b"\n".join(out).rstrip(b"\r\n")


def feature_file(phys):
    """A test on a lane-relative path: True for a feature spec or task log the lane's keys name."""
    shapes = []
    for key in ("feature-spec", "task-log"):
        value = (lane_key(phys, key) or "").strip().strip("`'\"")
        if value:
            shapes.append(re.compile("[^/]+".join(re.escape(p) for p in os.path.normpath(value).split("<id>"))))
    return lambda rel: any(m.fullmatch(rel) for m in shapes)


def claude_sections(phys, names, text=None):
    """The lines of the `## ` sections of the lane CLAUDE.md (or of text) whose heading starts with one of names."""
    if text is None:
        try:
            with open(os.path.join(phys, "CLAUDE.md"), encoding="utf-8-sig", errors="surrogateescape") as fh:
                text = fh.read()
        except OSError:
            return ""
    out, on = [], False
    for ln in text.split("\n"):
        if ln.startswith("## "):
            on = ln[3:].strip().startswith(names)
        if on:
            out.append(ln.rstrip())
    return "\n".join(out).rstrip()


def mount_repo(phys, m):
    """The mount's physical folder when it is in a git repo other than the lane's, else None."""
    joined = os.path.join(phys, m)
    if m in ("", ".") or not os.path.isdir(joined):
        return None
    if os.path.islink(joined.rstrip("/")):  # git pathspecs do not pass through a link
        return os.path.realpath(joined)
    other, lane_top = git_top(joined), git_top(phys)
    return os.path.realpath(joined) if other and other != lane_top else None


def tree_entries(phys, mounts, skip, own, leave):
    """One entry per file at HEAD under the lane's own mounts; the working dir and the files in own never count."""
    spec = [m.strip("`'\"") or "." for m in mounts]
    r = subprocess.run(["git", "--literal-pathspecs", "-C", phys, "ls-tree", "-r", "-z", "--full-name", "HEAD", "--"] + spec,
                       capture_output=True)
    if r.returncode != 0:
        raise Error("git ls-tree failed in %s" % phys)
    top, entries = git_top(phys), []
    for rec in r.stdout.split(b"\0"):
        if not rec:
            continue
        meta, _, name = rec.partition(b"\t")
        p = os.path.join(top, os.fsdecode(name))
        real = os.path.join(os.path.realpath(os.path.dirname(p)), os.path.basename(p))
        if real in own or (skip and inside(real, skip)) or leave(os.path.relpath(real, phys)):
            continue
        entries.append("%s\0%s\n" % (os.fsdecode(name), meta.decode("ascii", "replace")))
    return entries


def identity(root, record=None):
    """The store identity of the lane at root. In git it is `tree <sha256>` over the files of each `SAID.mounts:` path
    at HEAD (a linked mount or one that is its own repo by its HEAD tree), the `## Lane` block and CHANGELOG.md, plus
    `dirty <sha256>` when any of them differs from HEAD. The record, the working dir, feature specs and task logs (the sources part) and any other commit
    never count."""
    phys = os.path.realpath(os.path.abspath(root))
    sha = git_sha(phys)
    working = (lane_key(phys, "working") or "").strip().strip("`'\"")
    work_top = working.split("<", 1)[0].strip().strip("/")
    skip = os.path.realpath(os.path.join(phys, work_top)) if work_top else None
    own = {os.path.realpath(record)} if record else set()
    mounts = mount_list(lane_key(phys, "mounts")) or ["."]
    if sha:
        counted = own | {os.path.join(phys, "CLAUDE.md")}  # the lane block counts, not the whole file
        leave = feature_file(phys)
        repos = {m: mount_repo(phys, m.strip("`'\"")) for m in mounts}
        mine = [m for m in mounts if not repos[m]]
        held = os.path.realpath(os.path.join(phys, "CLAUDE.md"))  # a linked file is read at its own repo's HEAD
        shown = subprocess.run(["git", "-C", os.path.dirname(held), "show", "HEAD:./" + os.path.basename(held)],
                               capture_output=True)
        at_head = claude_sections(phys, ("Lane",), shown.stdout.decode("utf-8-sig", "surrogateescape") if shown.returncode == 0 else "")
        now = claude_sections(phys, ("Lane",))
        tree = ["lane\0%s\n" % at_head]
        dirty = [] if now == at_head else ["lane\0%s\n" % now]
        own_paths = mine + ["CHANGELOG.md"]  # skill text outside the mounts
        tree += tree_entries(phys, own_paths, skip, counted, leave)
        dirty += git_dirty(phys, own_paths, skip, counted, leave)
        for m, repo in repos.items():
            if repo:
                head = subprocess.run(["git", "-C", repo, "rev-parse", "HEAD:./"], capture_output=True, text=True)
                tree.append("mount\0%s\0%s\n" % (m, head.stdout.strip() if head.returncode == 0 else "no-head"))
                dirty += ["%s\0%s" % (m, e) for e in git_dirty(repo, ["."], skip, counted)]
        return "tree %s dirty %s" % (digest(tree), digest(dirty)) if dirty else "tree " + digest(tree)
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


SOURCES = " sources "


def git_top(phys):
    try:
        r = subprocess.run(["git", "-C", phys, "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    except OSError:
        return None
    return os.path.realpath(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip() else None


def lane_scope(root):
    """Sorted lane-relative paths left out of the lane's own diff: each registered lane root nested under the lane root
    (the SAID.lanes: registries of the lane root and each folder above it up to the git top), each declared mount that
    is its own git repo, and the SAID.working: root. An Error when a registry line is refused."""
    import said_status  # the one registry reader; lazy: said_status imports this module
    phys = os.path.realpath(os.path.abspath(root))
    top = git_top(phys) or phys
    out, d = set(), phys
    while True:
        try:
            rows, _ = said_status.read_lane_registry(d)
        except said_status.RegistryRefused as e:
            raise Error("the SAID.lanes: line of %s is refused: %s" % (os.path.join(d, "CLAUDE.md"), e))
        for _tok, r in rows:
            p = os.path.realpath(os.path.join(d, r.strip()))
            if p != phys and inside(p, phys):
                out.add(os.path.relpath(p, phys))
        parent = os.path.dirname(d)  # walk up to the git top
        if d == top or parent == d or not inside(d, top):
            break
        d = parent
    for m in mount_list(lane_key(phys, "mounts")):
        p = os.path.realpath(os.path.join(phys, m.strip("`'\"").rstrip("/")))
        mine = git_top(p) if os.path.isdir(p) else None
        if mine and mine != top and p != phys and inside(p, phys):  # a mount repo is read as its own mount diff
            out.add(os.path.relpath(p, phys))
    work = (lane_key(phys, "working") or "").strip("`'\"").split("<", 1)[0].rstrip("/")  # `<id>` or a named token
    p = os.path.realpath(os.path.join(phys, work)) if work else phys
    if p != phys and inside(p, phys):
        out.add(os.path.relpath(p, phys))
    bad = [x for x in out if any(unicodedata.category(c)[0] == "C" for c in x)]
    if bad:  # a path that would split the brief's command line
        raise Error("a path left out of the lane diff holds a control character: %r" % bad[0])
    return sorted(out)


def lane_pathspec(scope):
    """The git pathspec of the lane's own paths, relative to the lane root."""
    return ["."] + [":(exclude,literal)%s" % x for x in scope]


def lane_leave(scope):
    """The git_dirty `leave` test of a lane-relative path outside the lane's own paths."""
    return lambda rel: any(rel == x or rel.startswith(x + os.sep) for x in scope)


def sources_digest(root, files):
    """sha256 over each source file's lane-relative path and bytes: a feature spec or task log without debrief's
    sections, the lane CLAUDE.md by its `## Lane` and `## Earned rules` sections; an unreadable file counts as missing."""
    phys = os.path.realpath(os.path.abspath(root))
    is_feature = feature_file(phys)
    entries = []
    for f in files:
        try:
            with open(os.path.join(phys, f), "rb") as fh:
                data = fh.read()
            rel = os.path.normpath(f)
            if rel == "CLAUDE.md":
                data = claude_sections(phys, ("Lane", "Earned rules")).encode("utf-8", "surrogateescape")
            elif is_feature(rel):
                data = without_debrief(data)
            h = hashlib.sha256(data).hexdigest()
        except OSError:
            h = "missing"
        entries.append("%s\0%s\n" % (f, h))
    return digest(entries)


def load_sources(path):
    """(sources digest or None, [source files]) of a record; (None, []) when it is absent or carries none."""
    try:
        with open(path, encoding="utf-8-sig") as fh:
            lines = [ln.rstrip("\r") for ln in fh.read().split("\n")]
    except FileNotFoundError:
        return None, []
    except (OSError, UnicodeDecodeError) as e:
        raise Error("cannot read the record %s (left as it is): %s" % (path, e))
    first = lines[0] if lines else ""
    _, sep, src = first.partition(SOURCES)
    return (src.strip() or None) if first.startswith("store: ") and sep else None, \
        [ln[len("source: "):] for ln in lines[1:] if ln.startswith("source: ")]


def closed(root, path):
    """True when the feature's task log has a `## Debrief close` footer and no task heading below the last one."""
    phys = os.path.realpath(os.path.abspath(root))
    name = re.fullmatch(r"gate-(.+)\.md", os.path.basename(path))
    shape = (lane_key(phys, "task-log") or "").strip().strip("`'\"")
    if not name or not shape:
        return False
    import said_status  # the board's one task-heading grammar; lazy: said_status imports this module
    footer, below, fence = False, False, False
    try:
        with open(os.path.join(phys, shape.replace("<id>", name.group(1))), encoding="utf-8") as fh:
            for ln in fh:
                mark = ln.lstrip()[:3]
                if mark in ("```", "~~~") and (not fence or fence == mark):
                    fence = False if fence else mark
                elif not fence and re.match(r"##\s+Debrief close\b", ln, re.I):
                    footer, below = True, False
                elif not fence and said_status.HEADER_RE.match(ln.rstrip("\r\n")):
                    below = True
    except (OSError, UnicodeDecodeError):
        return False
    return footer and not below


WINDOW = "debrief-window: "


def _ruling_parser():
    """The shipped ruling-line parser."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("said_hold_gate", os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "review-qa", "hold-gate.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.parse_ruling_line


def _ruling_lines(text):
    """Each line of a rulings list: its parsed entry, or the line itself when it is not a well-formed entry."""
    parse = _ruling_parser()
    return [(lambda e: e if isinstance(e, dict) else ln)(parse(ln)) for ln in text.split("\n")]


def _ruling_hash(items):
    return hashlib.sha256(repr(items).encode("utf-8", "surrogateescape")).hexdigest()


def _ruling_parts(lines, pending):
    """(hash without each status and home, hash of the status and home of every entry on a line not in pending)."""
    body = [ln if isinstance(ln, str) else (ln["id"], ln["who"], ln["text"], tuple(ln["links"])) for ln in lines]
    held = [(k, e["id"], e["status"], e["arrow"]) for k, e in enumerate(lines)
            if isinstance(e, dict) and k not in pending]
    return _ruling_hash(body), _ruling_hash(held)


def rulings_shape(text):
    """What a later rulings_marks_only compares: {rulings, held, pending}, pending being line indexes."""
    lines = _ruling_lines(text)
    pending = [k for k, e in enumerate(lines) if isinstance(e, dict) and e["status"] == "pending"]
    body, held = _ruling_parts(lines, set(pending))
    return {"rulings": body, "held": held, "pending": pending}


def rulings_marks_only(shape, text):
    """True when text differs from the shaped list only by pending rulings marked landed with a home."""
    lines = _ruling_lines(text)
    pending = set(shape["pending"])
    if _ruling_parts(lines, pending) != (shape["rulings"], shape["held"]):
        return False
    return all(isinstance(lines[k], dict) and (lines[k]["status"] == "pending" and not lines[k]["arrow"]
                                               or lines[k]["status"] == "landed" and bool(lines[k]["arrow"]))
               for k in pending)


def _window_parts(root, path, files):
    """(digest of every source but this feature's spec, task log and rulings list, that rulings list's text)."""
    phys = os.path.realpath(os.path.abspath(root))
    name = re.fullmatch(r"gate-(.+)\.md", os.path.basename(path))
    own = set()
    for key in ("feature-spec", "task-log"):
        shape = (lane_key(phys, key) or "").strip().strip("`'\"")
        if name and shape:
            own.add(os.path.normpath(shape.replace("<id>", name.group(1))))
    mine = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(path)), "rulings.md"))
    rulings = [f for f in files if os.path.realpath(os.path.join(phys, f)) == mine]
    rest = [f for f in files if f not in rulings and os.path.normpath(f) not in own]
    text = ""
    for f in rulings:
        try:
            with open(os.path.join(phys, f), encoding="utf-8-sig", errors="surrogateescape") as fh:
                text += fh.read()
        except OSError:
            text += "\0missing %s\n" % f
    return sources_digest(root, rest), text


def _task_ids(root, path):
    """A hash of the task-heading ids of this feature's task log."""
    import said_status  # the board's one task-heading grammar
    phys = os.path.realpath(os.path.abspath(root))
    name = re.fullmatch(r"gate-(.+)\.md", os.path.basename(path))
    shape = (lane_key(phys, "task-log") or "").strip().strip("`'\"")
    ids, fence = [], False
    try:
        with open(os.path.join(phys, shape.replace("<id>", name.group(1) if name else "")), encoding="utf-8") as fh:
            for ln in fh:
                mark = ln.lstrip()[:3]
                if mark in ("```", "~~~") and (not fence or fence == mark):
                    fence = False if fence else mark
                elif not fence:
                    m = said_status.HEADER_RE.match(ln.rstrip("\r\n"))
                    if m:
                        ids.append(m.group(1))
    except (OSError, UnicodeDecodeError):
        ids = ["unreadable"]
    return _ruling_hash(sorted(ids))


def _window_fields(row):
    """{sources, tasks, others, rulings, held, pending} of a window row, or None for a row not of that form."""
    try:
        f = dict(p.split("=", 1) for p in row[len(WINDOW):].split())
        f["pending"] = [] if f["pending"] == "-" else [int(k) for k in f["pending"].split(",")]
        return f if all(f.get(k) for k in ("sources", "tasks", "others", "rulings", "held")) else None
    except (ValueError, KeyError):
        return None


def _window_holds(root, path, f):
    """True when a window's stamp is the record's sources part, no task was added and its other sources stand."""
    src, files = load_sources(path)
    if not src or f["sources"] != src or f["tasks"] != _task_ids(root, path):
        return False
    others, rulings = _window_parts(root, path, files)
    return others == f["others"] and rulings_marks_only(f, rulings)


def _open_window(path):
    rec = load(path)
    win = [ln for ln in rec[1] if ln.startswith(WINDOW)] if rec else []
    return _window_fields(win[0]) if win else None


def debrief_open(root, path):
    rec = load(path)
    f = _open_window(path)
    if f and rec[0] == identity(root, path) and _window_holds(root, path, f):
        return 0, "debrief-open: open"  # a resumed run keeps its window
    code, text = check(root, path, ["feature-review"])
    if code:
        return 1, text
    src, files = load_sources(path)
    others, rulings = _window_parts(root, path, files)
    s = rulings_shape(rulings)
    row = "%ssources=%s tasks=%s others=%s rulings=%s held=%s pending=%s" % (
        WINDOW, src, _task_ids(root, path), others, s["rulings"], s["held"],
        ",".join(str(k) for k in s["pending"]) or "-")
    update(path, root, lambda _store, rows, history: (
        [ln for ln in rows if not ln.startswith(WINDOW)] + [row], history))
    return 0, "debrief-open: open"


def debrief_window(path):
    rec = load(path)
    return 0, "debrief-window: " + ("open" if rec and any(ln.startswith(WINDOW) for ln in rec[1]) else "none")


def debrief_seal(root, path):
    rec = load(path)
    if rec is None or rec[0] is None or rec[0] != identity(root, path):
        return 1, "gate owed"
    store, rows, history = rec
    win = [ln for ln in rows if ln.startswith(WINDOW)]
    if not win:
        code, text = check(root, path, ["feature-review"])
        return code, "debrief-seal: current" if code == 0 else text
    f = _window_fields(win[0])
    if f is None:
        raise Error("the record's debrief window row is malformed (left as it is)")
    if not any(ln.startswith("feature-review: verdict | PASS") for ln in rows):
        return 1, "Inspect owed: feature-review (no PASS read on the record)"
    if not _window_holds(root, path, f):
        return 1, "Inspect owed: feature-review (a source other than the spec and task log moved)"
    files = load_sources(path)[1]
    write(path, store, [ln for ln in rows if not ln.startswith(WINDOW)], history, (sources_digest(root, files), files))
    return 0, "debrief-seal: sealed"


def sources_current(root, path):
    """True when the record's sources part holds for the feature-review read: a closed feature, a digest its source
    files still give, or an open debrief window whose other sources stand."""
    if closed(root, path):
        return True
    src, files = load_sources(path)
    if bool(src) and src == sources_digest(root, files):
        return True
    f = _open_window(path)
    return bool(f) and _window_holds(root, path, f)


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
        store = first[len("store: "):].partition(SOURCES)[0].strip()  # the lane part; load_sources reads the rest
    elif first.startswith("head: "):
        old = first[len("head: "):].strip()
        store = None if old in ("", "none") else "git " + old
    else:
        store = None
    rows = [ln for ln in lines[1:] if ln.startswith(ROW_KINDS)]
    history = [ln for ln in lines[1:] if ln.startswith("round: ") or (ln.startswith("matrix@") and ": " in ln)]
    return store, rows, history


def write(path, store, rows, history, sources=None):
    """Write the whole record atomically: a fresh temp file in its folder, flushed to disk, then renamed over it.
    sources = (digest, files) adds the sources part and the `source:` lines."""
    folder = os.path.dirname(os.path.abspath(path))
    os.makedirs(folder, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".gate-record-", dir=folder)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write("store: %s%s\n" % (store, SOURCES + sources[0] if sources else ""))
            for ln in (["source: " + f for f in sources[1]] if sources else []) + rows + history:
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


def update(path, root, mutate, expect=None, sources=None):
    """Rewrite the record at the current store: rows of another store dropped, history kept, mutate(rows, history).
    With `expect` (the identity the caller validated its rows at), a store that differs now is Moved: nothing is written.
    sources (the feature-review writer's briefed files) sets the sources part; any
    other write keeps the record's part while its files still give it, and else drops it with the feature-review rows."""
    store = identity(root, path)
    if expect is not None and store != expect:
        raise Moved("the lane's store changed while the rows were validated (%s, now %s)" % (expect, store))
    prior = load(path)
    rows, history, src = [], [], None
    if prior is not None:
        rows = prior[1] if prior[0] == store else []
        history = prior[2]
        old, files = load_sources(path)
        if old and rows:
            if sources_current(root, path):  # a closed feature or open debrief window keeps its part as recorded
                src = (old, files)
            else:
                rows = [ln for ln in rows if not ln.startswith("feature-review: ")]
    rows, history = mutate(store, rows, history)
    if sources is not None:
        src = (sources_digest(root, list(sources)), list(sources))
    elif not any(ln.startswith("feature-review: ") for ln in rows):
        src = None
    write(path, store, rows, history, src)
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


def check(root, path, reads, ident=None):
    for r in reads:
        if r not in READS:
            raise Error("unknown read %s" % r)
    rec = load(path)
    if rec is None or rec[0] is None or rec[0] != (ident or identity(root, path)):
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
            fresh = sources_current(root, path)  # a moved spec, log or rule owes the read again
            ok = sound and fresh and mine[0].startswith("feature-review: verdict | PASS | ")  # a FAIL verdict is owed until its rows are fixed
            if sound and fresh and not ok and not fr_record_only(mine):
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


def report(root, path):
    """The Inspect report of the record at path, derived from the record and the lane's store on every call and never
    written: {record, store, lane, state, owed, sections}. state is the check line over every read; each section (the
    three reads, then the skill-doctor rows) carries a status and its rows. A read the check line names, a run that
    left a unit out, a FAIL row, an open P1 or a moved store reads owed; no section reads current that the check line
    does not."""
    rec = load(path)
    lane = identity(root, path)
    rep = {"record": path, "store": None, "lane": lane, "state": "gate owed", "owed": [], "sections": []}
    if rec is None:
        rep["owed"].append("gate owed: no record")
        return rep
    store, rows, history = rec
    rep["store"] = store
    moved = store != lane
    if moved:
        rep["owed"].append("gate owed: the record is at %s, the lane at %s" % (store or "no store", lane))
        named = set(READS)
    else:
        rep["state"] = check(root, path, READS, ident=lane)[1]
        named = set(rep["state"][len("Inspect owed: "):].split(", ")) if rep["state"].startswith("Inspect owed: ") else set()
        if named:
            rep["owed"].append(rep["state"])
    stale = "not current (store %s)" % (store or "none")

    def mine(prefix):
        return [ln[len(prefix):] for ln in rows if ln.startswith(prefix)]

    gr = mine("gate-recompute: ")
    left = [r for r in gr if r.endswith(" skipped (not selected)")]
    failed = [r.split(" exit=")[0] for r in gr if " exit=" in r and r.split(" exit=")[1].split()[1:2] == ["FAIL"]]
    if moved:
        st = stale
    elif "gate-recompute" in named:
        st = "owed"
    elif left:
        st = "owed: %d unit(s) not selected, a full run owed" % len(left)
        rep["owed"].append("gate-recompute owed: a full run (%d unit(s) not selected)" % len(left))
    elif failed:
        st = "FAIL: %d unit(s)" % len(failed)
        rep["owed"].append("gate-recompute FAIL: " + ", ".join(failed))
    else:
        st = "current, %d row(s)" % len(gr)
    rep["sections"].append(("gate-recompute", st, gr))

    rounds = [ln for ln in history if ln.startswith("round: ")]
    last = round_fields(rounds[-1]) if rounds else {}
    snap = [ln for ln in history if ln.startswith("matrix@%s: " % last.get("n", "?"))]
    st = stale if moved else ("owed" if "matrix" in named else "current, round %s" % last.get("n"))
    rep["sections"].append(("matrix", st, rounds[-1:] + snap))

    fr = mine("feature-review: ")
    if moved:
        st = stale
    elif "feature-review FAIL" in named:
        st = "owed: verdict FAIL, each FAIL row without `record:` goes to a new task"
    elif "feature-review" in named:
        st = "owed"
    else:
        st = "current, verdict PASS"
    rep["sections"].append(("feature-review", st, fr))

    sd = mine("skill-doctor: ")
    open_p1 = [r.split(" ")[0] for r in sd if not re.search(r" open-P1=0( |$)", r)]  # no count reads open
    if moved:
        st = stale
    elif open_p1:
        st = "owed: open P1 in %d file(s)" % len(open_p1)
        rep["owed"].append("skill-doctor owed: open P1 in " + ", ".join(open_p1))
    else:
        st = "%d row(s), open-P1=0" % len(sd)
    rep["sections"].append(("skill-doctor", st, sd))
    return rep


def report_text(rep, root=None):
    """The report as lines, the record path shown relative to root when given."""
    rel = os.path.relpath(rep["record"], root) if root else rep["record"]
    out = ["Inspect record  %s" % rel,
           "  store   %s" % ("%s (current)" % rep["store"] if rep["store"] and rep["store"] == rep["lane"]
                             else "%s, the lane is at %s" % (rep["store"] or "none", rep["lane"])),
           "  state   %s" % rep["state"]]
    out += ["  owed    %s" % o for o in rep["owed"]]
    for name, status, rows in rep["sections"]:
        out.append("  %s  %s" % (name, status))
        out += ["    %s" % r for r in rows]
    return out


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
    if not argv or argv[0] not in ("identity", "check", "round", "report",
                                   "debrief-open", "debrief-seal", "debrief-window"):
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
    need = {"identity": ("root",), "check": ("root", "record", "reads"), "round": ("root", "record", "matrix-from"),
            "report": ("root", "record"), "debrief-open": ("root", "record"), "debrief-seal": ("root", "record"),
            "debrief-window": ("root", "record")}[cmd]
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
        if cmd == "report":
            rep = report(o["root"], o["record"])
            print("\n".join(report_text(rep, o["root"])))
            return 1 if rep["owed"] else 0
        if cmd == "debrief-window":
            code, text = debrief_window(o["record"])
            print(text)
            return code
        if cmd in ("debrief-open", "debrief-seal"):
            code, text = (debrief_open if cmd == "debrief-open" else debrief_seal)(o["root"], o["record"])
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
