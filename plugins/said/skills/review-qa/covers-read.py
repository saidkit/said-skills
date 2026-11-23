#!/usr/bin/env python3
"""Read every task's `**Covers:**` line, resolve each id, report the dead ones. Read-only: it writes no file.

  covers-read.py --task-file <tasks.md> --root <lane-root> [--working <feature working dir>]
                 [--rulings <rulings.md>] [--todo <todo.md>]... [--backlog <backlog.md>]...
                 [--ledger <ledger.md>]... [--reviewer <feature-review verdict.md>]

A task is a `## <id>: <title>` heading outside a code fence, the id letters, digits and hyphens in two or more
segments, the last all digits; its Covers line is the first `**Covers:**` line
before its first `### ` heading; its ids are separated by `, ` (`none` names none; an empty line is `malformed`). Each id resolves as:
  WR-<10 digits>[-<digits>]  a line of --rulings: live (pending, landed), superseded, rejected, or missing
  @<digits>           an entry id of a --todo or --backlog file (read with the board's todo-md reader)
  DL-<id>, CL-<id>    a --ledger line whose first word is the id (after list, heading and bold marks)
  <file>#<fragment>   the file under --root has a heading (indented at most 3 spaces) whose slug is the fragment
                      (lowercase, spaces to hyphens, other punctuation dropped) or a line whose first word is the
                      fragment. A file at the root shadows a same-named file in --working. A bare file name not at
                      the root names the one file of that name in --working, the declared `SAID.working:` folder of
                      the feature named by --working's last part, the `SAID.feature-spec:` folder (direct children)
                      or a `SAID.mounts:` folder (any depth); with none or two it is `missing`.
                      Without --working only the mounts are searched, so a bare name that is not a file at the
                      root is `missing`. A file is inside by declared route: spelled under a declared folder, whatever
                      that folder links to, or with its real location in the lane or a declared folder's target. The id is `outside` when no file
                      inside the root or those folders is found and a candidate leaves it
A store whose flag is not given leaves its ids `unchecked`; a given --rulings file that does not exist makes
every ruling id `missing`. A bare `R-` id, a control character or a space inside an id is `malformed`.
Output, one line each, every text shown as printable ASCII and capped:
  id: <task> <id> <resolution> [<detail>]
  stale-cite: FAIL <task> <id> <why>          for superseded, rejected, missing, outside, malformed
  matrix: <task> | covers: <id>=<resolution>, ... | rules-applied: <line> | reviewer: <id>=<verdict>, ...
  summary: <n> tasks, <n> ids, <n> live, <n> stale, <n> unchecked
Exit: 0 no stale cite, 1 a stale cite, 2 a usage or read error.
"""
import importlib.util
import os
import sys

sys.dont_write_bytecode = True  # read-only: no bytecode cache beside the scripts
HERE = os.path.dirname(os.path.abspath(__file__))
LABEL = "**Covers:**"
STALE = ("superseded", "rejected", "missing", "outside", "malformed")
LIVE_RULING = ("pending", "landed")


class ReadError(Exception):
    pass


def _gate():
    spec = importlib.util.spec_from_file_location("said_hold_gate", os.path.join(HERE, "hold-gate.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


GATE = _gate()
shown = GATE.shown


def _board():
    board = os.path.normpath(os.path.join(HERE, "..", "board"))
    if board not in sys.path:
        sys.path.insert(0, board)


def _sibling(name):
    """A board module; a broken one is a read error."""
    _board()
    try:
        return importlib.import_module(name)
    except Exception as e:
        raise ReadError("cannot load %s: %s" % (name, shown(e, 120)))


def _todo_md():
    return _sibling("todo_md")


def read_lines(path):
    try:
        with open(path, encoding="utf-8-sig", newline="") as fh:
            text = fh.read()
    except (OSError, UnicodeDecodeError) as e:
        raise ReadError("cannot read %s: %s" % (shown(path, 200), shown(e, 120)))
    return [ln[:-1] if ln.endswith("\r") else ln for ln in text.split("\n")]


def fence(line):
    """(char, length, rest) of a fence line indented at most 3 spaces, else None."""
    s = line.lstrip(" ")
    if len(line) - len(s) > 3 or s[:3] not in ("```", "~~~"):
        return None
    n = len(s) - len(s.lstrip(s[0]))
    return s[0], n, s[n:].strip()


class Fences(object):
    """Tracks whether a line is inside a fenced code block; a fence closes on the same char, as long or longer."""

    def __init__(self):
        self.open = None

    def skip(self, line):
        f = fence(line)
        if self.open is None:
            if f:
                self.open = f[:2]
                return True
            return False
        if f and f[0] == self.open[0] and f[1] >= self.open[1] and not f[2]:
            self.open = None
        return True


def task_id(head):
    """The id of a `<id>: <title>` heading text, else None."""
    if ":" not in head:
        return None
    tid = head.split(":", 1)[0].strip()
    parts = tid.split("-")
    if len(parts) < 2 or not tid.isascii() or not all(p.isalnum() for p in parts) or not parts[-1].isdigit():
        return None
    return tid


def tasks(lines):
    """[(task_id, covers_value or None, rules_applied_line or None)] in file order."""
    out, cur, fences, in_fields, in_fix = [], None, Fences(), False, False
    for line in lines:
        if fences.skip(line):
            continue
        if line.startswith("## "):
            tid = task_id(line[3:].strip())
            if tid:
                cur = {"id": tid, "covers": None, "rules": None}
                out.append(cur)
                in_fields, in_fix = True, False
            else:
                cur = None
            continue
        if cur is None:
            continue
        if line.startswith("### "):
            in_fields = False
            in_fix = line[4:].strip() == "Fix"
            continue
        if in_fields and cur["covers"] is None and line.startswith(LABEL):
            cur["covers"] = line[len(LABEL):].strip()
        if in_fix and cur["rules"] is None:
            s = line.strip().lstrip("-* ").lstrip("`").strip()
            if s.startswith("Rules applied:"):
                cur["rules"] = s.rstrip("`").strip()[len("Rules applied:"):].strip()
    return [(t["id"], t["covers"], t["rules"]) for t in out]


def split_ids(value):
    if value is None or value == "none":
        return []
    return value.split(", ")


def slug(text):
    keep = []
    for c in text.strip().lower():
        if c.isalnum() or c == "-":
            keep.append(c)
        elif c == " ":
            keep.append("-")
    return "".join(keep)


def first_word(line):
    s = line.strip()
    while s and s[0] in "#|-*>`+ ":
        s = s[1:]
    for i, c in enumerate(s):
        if c in " |`*,:":
            return s[:i]
    return s


class Stores(object):
    def __init__(self, args):
        self.root = os.path.realpath(os.path.abspath(args["root"]))
        self.working = os.path.realpath(os.path.abspath(args["working"])) if args["working"] else None
        spelled = os.path.relpath(os.path.abspath(args["working"]), os.path.abspath(args["root"])) if args["working"] else ""
        self.spelled_working = os.path.join(self.root, spelled) if spelled and ".." not in spelled.split(os.sep) else self.working
        self.dirs = self._bare_dirs(args)
        feature = os.path.basename(os.path.abspath(args["working"])) if args["working"] else None
        self.routes = _sibling("said_status")._fr_routes(self.root, feature) \
            + tuple(d[:-3] if d.endswith("/**") else d for d in self.dirs)
        self.rulings = self._rulings(args["rulings"])
        self.line_ids = self._line_ids(args["todo"], args["backlog"])
        self.ledger = self._ledger(args["ledger"])
        self.files = {}

    def _rulings(self, path):
        if path is None:
            return None
        path = os.path.abspath(path)
        if not os.path.exists(path):
            return {}
        try:
            entries, _broken = GATE.load_rulings([path])
        except GATE.ConfigError as e:
            raise ReadError(str(e))
        return {e["id"]: e for _p, _n, e in entries}

    def _line_ids(self, todos, backlogs):
        if not todos and not backlogs:
            return None
        tm = _todo_md()

        class Ctx(object):
            lanes, token, rp = set(), "lane", ""

            def add(self, *a, **k):
                pass

            def classify(self, label, href):
                return {"label": label, "href": href, "kind": "other", "resolves": None, "id": ""}

        ids = set()
        for path, reader, at in [(p, tm.read_lane, 3) for p in todos] + [(p, tm.read_backlog, 4) for p in backlogs]:
            if not os.path.isfile(path):
                continue
            lines = [ln + "\n" for ln in read_lines(path)]
            ids.update(e["id"] for e in reader(lines, Ctx())[at] if e.get("id"))
        return ids

    def _ledger(self, paths):
        if not paths:
            return None
        words = set()
        for p in paths:
            if os.path.isfile(p):
                words.update(first_word(ln) for ln in read_lines(p))
        return words

    def _bare_dirs(self, args):
        """The folders a bare file name resolves in: the feature read's, plus --working (resolve() counts one file once)."""
        cite_check, said_status = _sibling("cite_check"), _sibling("said_status")
        if not self.working:
            return tuple(said_status._fr_cite_dirs(self.root))  # the mounts count without --working
        given = os.path.abspath(args["working"])
        dirs = list(said_status._fr_cite_dirs(self.root, os.path.basename(given)))
        for top, sub in ((os.path.abspath(args["root"]), given), (self.root, self.working)):
            rel = os.path.relpath(sub, top).replace(os.sep, "/")
            if rel != "." and cite_check.inside(rel):  # resolve() counts one physical file once
                dirs.append(rel)
        return tuple(dirs)

    def anchor_file(self, rel):
        cite_check = _sibling("cite_check")
        if not cite_check.inside(rel):
            return None, "outside"
        hit, bare = None, "/" not in rel
        if bare:
            hit = cite_check.resolve(self.root, rel, self.dirs)  # the feature read's rule
        if hit:
            cands = [os.path.join(self.root, hit)]
        else:  # no single file: these only tell `outside` from `missing`
            cands = ([os.path.join(self.spelled_working, rel)] if bare and self.working else []) + [os.path.join(self.root, rel)]
        left = False
        for c in cands:
            real = os.path.realpath(c)
            if not cite_check.admitted(self.root, os.path.relpath(c, self.root).replace(os.sep, "/"), self.routes):
                left = left or os.path.exists(real) or os.path.islink(c)
                continue
            if os.path.isfile(real) and (hit or not bare):
                return real, None
        return None, ("outside" if left else "missing")

    def fragments(self, path):
        if path not in self.files:
            heads, words, fences = set(), set(), Fences()
            for ln in read_lines(path):
                if fences.skip(ln):
                    continue
                s = ln.lstrip(" ")
                if s.startswith("#") and len(ln) - len(s) <= 3:
                    level = len(s) - len(s.lstrip("#"))
                    if level <= 6 and s[level:level + 1] == " ":
                        heads.add(slug(s[level:]))
                words.add(first_word(ln))
            self.files[path] = (heads, words)
        return self.files[path]


def malformed(tok):
    if not tok:
        return "empty Covers line: write `none`"
    if tok.startswith("R-"):
        return "bare R- id: applied earned rules go in `Rules applied`"
    if not tok or any(ord(c) < 0x21 or ord(c) == 0x7f for c in tok) or "," in tok:
        return "control character, space or comma inside the id"
    return None


def resolve(tok, st):
    """(resolution, detail) of one Covers id."""
    why = malformed(tok)
    if why:
        return "malformed", why
    if GATE.ruling_id(tok):
        if st.rulings is None:
            return "unchecked", "no --rulings"
        e = st.rulings.get(tok)
        if e is None:
            return "missing", "no such ruling in the list"
        if e["status"] in LIVE_RULING:
            return "live", e["status"]
        if e["status"] == "superseded":
            return "superseded", "cite %s instead" % shown(e.get("arrow") or "its successor", 40)
        return "rejected", "the ruling was rejected"
    if tok.startswith("@") and tok[1:].isdigit() and tok[1:].isascii():
        if st.line_ids is None:
            return "unchecked", "no --todo or --backlog"
        return ("live", "") if tok in st.line_ids else ("missing", "no todo or backlog line has this id")
    if tok.startswith(("DL-", "CL-")) and len(tok) > 3:
        if st.ledger is None:
            return "unchecked", "no --ledger"
        return ("live", "") if tok in st.ledger else ("missing", "no ledger line has this id")
    if tok.count("#") == 1 and tok.split("#")[0] and tok.split("#")[1]:
        rel, frag = tok.split("#")
        path, why = st.anchor_file(rel)
        if why == "outside":
            return "outside", "the path leaves the lane root"
        if path is None:
            return "missing", "no such file"
        heads, words = st.fragments(path)
        if frag in heads or frag in words:
            return "live", ""
        return "missing", "no heading slug or line names this fragment"
    return "malformed", "unknown id class"


def reviewer_rows(path):
    """[(first-cell words, verdict word)] of the verdict file's table rows."""
    if path is None:
        return None
    rows = []
    for ln in read_lines(path):
        s = ln.strip()
        if not s.startswith("|") or set(s) <= set("|-: "):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) < 2:
            continue
        verdict = cells[-1].split(" ")[0] if cells[-1] else ""
        words = set(w.strip("`*,;:()") for w in cells[0].split(" "))
        rows.append((words, verdict))
    return rows


def parse_args(argv):
    args = {"task-file": None, "root": None, "working": None, "rulings": None, "reviewer": None,
            "todo": [], "backlog": [], "ledger": []}
    i = 0
    while i < len(argv):
        k = argv[i]
        if not k.startswith("--") or k[2:] not in args or i + 1 >= len(argv):
            raise ReadError("usage: " + __doc__.strip().splitlines()[2].strip())
        v = argv[i + 1]
        if isinstance(args[k[2:]], list):
            args[k[2:]].append(v)
        else:
            args[k[2:]] = v
        i += 2
    if not args["task-file"] or not args["root"]:
        raise ReadError("usage: --task-file and --root are required")
    for k in ("task-file", "reviewer"):
        args[k] = os.path.abspath(args[k]) if args[k] else args[k]
    for k in ("todo", "backlog", "ledger"):
        args[k] = [os.path.abspath(p) for p in args[k]]
    return args


def main(argv):
    out = []  # buffered: a read error prints only the error line
    try:
        args = parse_args(argv)
        if not os.path.isdir(args["root"]):
            raise ReadError("not a directory: --root %s" % shown(args["root"], 200))
        st = Stores(args)
        found = tasks(read_lines(args["task-file"]))
        rev = reviewer_rows(args["reviewer"])
        n_ids = n_live = n_stale = n_unchecked = 0
        for task, covers, rules in found:
            cells, rcells = [], []
            for tok in split_ids(covers):
                res, detail = resolve(tok, st)
                label = shown(tok, 120) if tok else "(empty)"
                n_ids += 1
                n_live += res == "live"
                n_unchecked += res == "unchecked"
                out.append("id: %s %s %s%s" % (shown(task, 40), label, res, (" " + shown(detail)) if detail else ""))
                if res in STALE:
                    n_stale += 1
                    out.append("stale-cite: FAIL %s %s %s" % (shown(task, 40), label, shown(detail or res)))
                cells.append("%s=%s" % (label, res))
                if rev is not None:
                    hit = next((v for words, v in rev if tok and tok in words), "")
                    rcells.append("%s=%s" % (label, shown(hit, 20) if hit else "no row"))
            cov = "absent" if covers is None else (", ".join(cells) if cells else "none")
            reviewer = "not read" if rev is None else (", ".join(rcells) if rcells else "none")
            out.append("matrix: %s | covers: %s | rules-applied: %s | reviewer: %s"
                       % (shown(task, 40), cov, shown(rules, 200) if rules else "none", reviewer))
        out.append("summary: %d tasks, %d ids, %d live, %d stale, %d unchecked"
                   % (len(found), n_ids, n_live, n_stale, n_unchecked))
    except (ReadError, GATE.ConfigError) as e:
        print("error: %s" % shown(e, 300))
        return 2
    print("\n".join(out))
    return 1 if n_stale else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
