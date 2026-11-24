#!/usr/bin/env python3
"""Reads a debrief's working file and the records around it, and prints what the debrief acts on. Writes nothing.

  debrief-rows.py stop <debrief.md>
  debrief-rows.py account --record <gate record>
  debrief-rows.py traces <debrief.md> [--record <gate record>]
  debrief-rows.py arrows <debrief.md> --rulings <rulings.md> [--rulings <rulings.md> ...] --root <lane root>
  debrief-rows.py sweep <todo.md> --root <lane root> --logs <task-log dir> [--stale <n>]
  debrief-rows.py table <feature spec> <tasks log>

Rows. A row is a line inside a section whose heading text starts A.1 to A.7 (a section mark may come first; A.10 is
none) and whose last `|` cell starts `status:`; a deeper heading stays inside the section; fenced lines are never
read. A row in an A.5 section is a ruling. A proposal is a row whose action cell is `promote-to-existing` or
`create-new`, or an A.7 row whose kind cell is `rule` or `check`. Every other row is owned (debrief writes its home).

stop: prints, in file order, `open: <line> proposal|ruling <first cell> (<status>)` for a proposal or ruling still
  proposed or revise, `warn: line <n> owned row is <status>; ...` for an owned row left open, then `own: <n>` and
  `stop: <k>` or `stop: none`.
account: one markdown table, a row per round row of the record and a sum row, then `leaks by class:`,
  `leaks by source:`, `leaks by finder:` and one `leak: <round>.<i> <class>/<source>/<finder>` line per leak. A
  round's leaks value is `-` (not on record), a count, or items `<class>/<source>/<finder>` joined by `+`
  (class lost, wrong or hold; finder look or read). A sum over rounds with a figure missing reads `<s> (<k> of <n>
  rounds)`.
traces: every leak of the record (none without --record) and every A.4 row not skipped needs an A.7 row whose first cell is its id (the
  leak's `<round>.<i>`, the lesson row's first cell) and whose kind cell is rule, check or observable. Prints
  `trace: <id> <kind>`, `untraced: <id> (<why>)`, `traces: <k> of <n>`; exit 1 when one is untraced.
arrows: for each A.5 row applied whose ruling the list shows landed, its home (the arrow, without `#...` or `:<line>`,
  placed as lane_place says) must hold `ruling: <id>`. Prints `arrow: <id> -> <home>` or `missing: <id> <home> (<why>)`; exit 1 when one misses.
sweep: for each open todo line whose text names `target <path>`: `close: <line> <id> target <path>` when the target
  exists inside the lane (see lane_place) and holds the line's id, else `keep: <line> <id> (<why>)`; any open line not closing
  whose date is older than <n> debriefed features (task logs with a `## Debrief close` footer dated after it, default
  3) prints `stale: <line> <id> <k> features debriefed since <date>`. Ends `sweep: <a> close, <b> keep, <c> stale`.
table: the spec's `## Feature Tasks` rows against the log's task statuses: `stale: <id> table <s>, log <s>`,
  `extra: <id> (no task in the log)`, `missing: <id> (<s> in the log, no table row)`; then the log's own `## Summary
  Table` against the same statuses, each line ending `(the log's summary table)`, read with or without the spec's table;
  a log with none adds nothing; exit 1 on any; a table with no Status column is refused (`error:`, exit 2).
Exit 0 unless stated; 2 with `error: <why>` on a usage error or an unreadable input.
"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.join(HERE, "..", "board")
PROPOSAL = {"promote-to-existing", "create-new"}
TRACE_KINDS = ("rule", "check", "observable")
OPEN = {"proposed", "revise"}
CLASSES = ("lost", "wrong", "hold")
FINDERS = ("look", "read")
COUNTS = ("decisions", "operator-min", "rework-min", "elapsed-min", "tokens")
LEAK_CAP = 1000  # a bare leaks count above it is no count


def is_count(v):
    return v.isascii() and v.isdecimal()


def bare(word):
    """A word without the quoting and punctuation that may wrap it in prose (backticks, brackets, `.,;:)`)."""
    return word.strip("`*[](),;:.")


class Fail(Exception):
    pass


def _module(name, path):
    sys.dont_write_bytecode = True  # read-only: no bytecode cache beside the shipped scripts
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _board(name):
    """A board module by name; the board folder goes on the path, since todo_md imports md_blocks by name."""
    sys.dont_write_bytecode = True
    board = os.path.realpath(BOARD)
    if board not in sys.path:
        sys.path.insert(0, board)
    return importlib.import_module(name)


def shown(text, cap=120):
    """File-derived text as printed: printable ASCII only, capped."""
    return "".join(c if 0x20 <= ord(c) < 0x7F else "?" for c in str(text))[:cap]


def read_text(path):
    try:
        with open(path, encoding="utf-8-sig") as f:
            return f.read()
    except (OSError, UnicodeDecodeError) as e:
        raise Fail("cannot read %s: %s" % (shown(path, 200), e))


def physical(path):
    try:
        return os.path.realpath(os.path.abspath(path))
    except ValueError as e:  # a NUL byte in a path read from a file
        raise Fail("not a path: %s (%s)" % (shown(path, 80), e))


def lane_place(top, spelled):
    """(physical path, None) for the file a lane-relative spelling names, else (None, why). The spelling is tried at
    the lane root, then at the lane's docs root; it is inside when cite_check admits it (the lane's own files, its
    declared routes: the docs root and the mounts, the lane CLAUDE.md wherever it links). `..` or absolute: outside."""
    cc, gr = _board("cite_check"), _board("gate_record")
    if "\0" in spelled:  # isfile() would read it as absent
        raise Fail("not a path: %s" % shown(spelled, 80))
    if not cc.inside(spelled):
        return None, "outside the lane root"
    docs = (gr.lane_key(top, "docs-root") or "").strip().strip("`'\"").strip("/")
    docs = docs if docs and cc.inside(docs) else ""
    routes = gr.mount_list(gr.lane_key(top, "mounts")) + ([docs] if docs else [])
    found = False
    for rel in [spelled] + ([docs + "/" + spelled] if docs else []):
        full = os.path.join(top, rel)
        if not os.path.isfile(full):
            continue
        found = True
        if cc.admitted(top, rel, routes):
            return physical(full), None
    return None, ("outside the lane root" if found else "no such file")


def cites(text, token):
    """True when `token` occurs in `text` with no letter, digit, `-` or `_` right after it and no letter, digit,
    `-`, `_` or `@` right before it (a longer id is no citation)."""
    i = text.find(token)
    while i >= 0:
        j = i + len(token)
        before_ok = i == 0 or not (text[i - 1].isalnum() or text[i - 1] in "-_@")
        if before_ok and (j == len(text) or not (text[j].isalnum() or text[j] in "-_")):
            return True
        i = text.find(token, i + 1)
    return False


# --- rows ------------------------------------------------------------------------------------------------------------
def section_of(text):
    """The section digit when the heading text starts A.1 to A.7 (after an optional section mark), else None."""
    s = text.strip().lstrip("*`_ ")
    if s.startswith("\u00a7"):
        s = s[1:].lstrip("*`_ ")
    if len(s) >= 3 and s[:2] == "A." and s[2] in "1234567" and not (len(s) > 3 and s[3].isdigit()):
        return s[2]
    return None


def cells(line):
    s = line.strip()
    if s.startswith(("- ", "* ")):
        s = s[2:]
    parts = [c.strip() for c in s.strip("|").split("|")]
    return parts if len(parts) >= 2 and parts[-1].startswith("status:") else None


def rows_of(path):
    """[(line, section digit, cells, status, kind)] of a debrief working file, in file order."""
    md = _board("md_blocks")
    doc = md.parse(read_text(path).splitlines())
    out, section, level = [], None, 0
    for b in md.walk(doc):
        if b.kind in ("heading", "setext"):
            depth = b.level
            if section and depth > level:
                continue  # a sub-heading of the section keeps it
            text = b.text if b.kind == "heading" else " ".join(t for _n, t in b.lines)
            got = section_of(text)
            section, level = (got, depth) if got else (None, 0)
            continue
        if b.kind != "para" or not section:
            continue
        for n, raw in b.lines:
            row = cells(raw)
            if not row:
                continue
            status = bare((row[-1][len("status:"):].split() or ["?"])[0]).lower()
            if section == "5":
                kind = "ruling"
            elif section == "7":
                kind = "proposal" if row[1] in ("rule", "check") else "own"
            else:
                kind = "proposal" if row[1] in PROPOSAL else "own"
            out.append((n, section, row, status, kind))
    return out


def cmd_stop(path):
    owned, opened = 0, 0
    for n, _sec, row, status, kind in rows_of(path):
        if kind == "own":
            owned += 1
            if status in OPEN:
                print("warn: line %d owned row is %s; Phase A writes an owned row approved" % (n, status))
        elif status in OPEN:
            opened += 1
            print("open: %d %s %s (%s)" % (n, kind, shown(row[0]), status))
    print("own: %d" % owned)
    print("stop: %d" % opened if opened else "stop: none")
    return 0


# --- account ---------------------------------------------------------------------------------------------------------
def leak_items(n, value):
    """[(id, class, source, finder)] of one round's leaks value; class etc. empty for a bare count."""
    if value in ("-", "0"):
        return []
    if is_count(value):
        if int(value) > LEAK_CAP:
            raise Fail("round %s leaks count %s is above %d" % (n, shown(value, 20), LEAK_CAP))
        return [("%s.%d" % (n, i), "", "", "") for i in range(1, int(value) + 1)]
    out = []
    for i, item in enumerate(value.split("+"), 1):
        parts = item.split("/")
        if len(parts) != 3 or not all(parts) or parts[0] not in CLASSES or parts[2] not in FINDERS:
            raise Fail("round %s leaks item %s is not <class>/<source>/<finder> (class %s; finder %s)"
                       % (n, shown(item, 60), ", ".join(CLASSES), ", ".join(FINDERS)))
        out.append(("%s.%d" % (n, i), parts[0], parts[1], parts[2]))
    return out


def rounds_of(record):
    gr = _board("gate_record")
    path = physical(record)
    try:
        got = gr.load(path)
    except gr.Error as e:
        raise Fail(str(e))
    if got is None:
        raise Fail("no gate record at %s" % shown(path, 200))
    rounds = []
    for line in got[2]:
        if not line.startswith("round: "):
            continue
        f = gr.round_fields(line)
        n = f.get("n", "?")
        for key in COUNTS:
            v = f.get(key, "-")
            if v != "-" and not is_count(v):
                raise Fail("round %s %s %s is no count" % (n, key, shown(v, 40)))
        rounds.append((f, leak_items(n, f.get("leaks", "-"))))
    return rounds


def total(values):
    have = [int(v) for v in values if v != "-"]
    if not have:
        return "-"
    s = str(sum(have))
    return s if len(have) == len(values) else "%s (%d of %d rounds)" % (s, len(have), len(values))


def tally(items, at):
    counts = {}
    for it in items:
        if it[at]:
            counts[it[at]] = counts.get(it[at], 0) + 1
    unclassed = sum(1 for it in items if not it[at])
    parts = ["%s %d" % (k, counts[k]) for k in sorted(counts)] + (["unclassed %d" % unclassed] if unclassed else [])
    return ", ".join(parts) or "none"


def cmd_account(record):
    rounds = rounds_of(record)
    head = ["round", "store"] + ["decisions", "leaks", "look"] + list(COUNTS[1:])
    print("| " + " | ".join(head) + " |")
    print("|" + "---|" * len(head))
    leaks_col, items = [], []
    for f, its in rounds:
        store = f.get("store", "-").split()
        store = " ".join(store[:1] + [w[:12] for w in store[1:2]]) or "-"
        lk = "-" if f.get("leaks", "-") == "-" else str(len(its))
        leaks_col.append(lk)
        items += its
        cells_ = [f.get("n", "?"), store, f.get("decisions", "-"), lk, f.get("look", "-")] + [f.get(k, "-") for k in COUNTS[1:]]
        print("| " + " | ".join(shown(c, 40) for c in cells_) + " |")
    looks = [f.get("look", "-") for f, _ in rounds]
    sums = ["sum", "%d rounds" % len(rounds), total([f.get("decisions", "-") for f, _ in rounds]), total(leaks_col),
            "%d of %d" % (looks.count("yes"), len(looks))] + [total([f.get(k, "-") for f, _ in rounds]) for k in COUNTS[1:]]
    print("| " + " | ".join(sums) + " |")
    print("leaks by class: " + tally(items, 1))
    print("leaks by source: " + shown(tally(items, 2), 200))
    print("leaks by finder: " + tally(items, 3))
    for it in items:
        print("leak: %s %s" % (it[0], "/".join(shown(x, 40) for x in it[1:]) if it[1] else "unclassed"))
    return 0


# --- traces ----------------------------------------------------------------------------------------------------------
def cmd_traces(path, record):
    rows = rows_of(path)
    wanted = [it[0] for _f, its in rounds_of(record) for it in its] if record else []
    wanted += [row[0] for _n, sec, row, status, _k in rows if sec == "4" and status != "skip"]
    traces = {}
    for n, sec, row, status, _k in rows:
        if sec == "7" and status != "skip":
            traces.setdefault(row[0], []).append((n, row[1]))
    known = set(wanted)
    for key, at in traces.items():
        if key not in known:
            print("warn: line %d traces %s, no such leak or lesson" % (at[0][0], shown(key)))
    ok = 0
    for key in wanted:
        kinds = [k for _n, k in traces.get(key, [])]
        good = [k for k in kinds if k in TRACE_KINDS]
        if good:
            ok += 1
            print("trace: %s %s" % (shown(key), good[0]))
        elif kinds:
            print("untraced: %s (kind %s is no trace: %s)" % (shown(key), shown(kinds[0], 30), ", ".join(TRACE_KINDS)))
        else:
            print("untraced: %s (no A.7 row)" % shown(key))
    print("traces: %d of %d" % (ok, len(wanted)))
    return 0 if ok == len(wanted) else 1


# --- arrows ----------------------------------------------------------------------------------------------------------
def home_path(arrow):
    p = arrow.split("#", 1)[0].strip()
    head, sep, tail = p.rpartition(":")
    return head if sep and tail.isdigit() else p


def cmd_arrows(path, lists, root):
    gate = _module("said_debrief_hold_gate", os.path.join(HERE, "..", "review-qa", "hold-gate.py"))
    try:
        entries, _broken = gate.load_rulings([os.path.abspath(p) for p in lists])
    except gate.ConfigError as e:
        raise Fail(str(e))
    landed = {e["id"]: e for _p, _n, e in entries if e["status"] == "landed"}
    top = physical(root)
    seen, ok, missed = set(), 0, 0
    for n, sec, row, status, _k in rows_of(path):
        if sec != "5" or status != "applied":
            continue
        rid = next((bare(w) for w in row[0].split() if bare(w).startswith("WR-")), None)
        if rid is None or rid in seen or rid not in landed or not landed[rid]["arrow"]:
            continue
        seen.add(rid)
        home = home_path(landed[rid]["arrow"])
        target, why = lane_place(top, home)
        if why is None and not cites(read_text(target), "ruling: " + rid):
            why = "no 'ruling: %s'" % rid
        if why:
            missed += 1
            print("missing: %s %s (%s)" % (shown(rid), shown(home), why))
        else:
            ok += 1
            print("arrow: %s -> %s" % (shown(rid), shown(home)))
    print("arrows: %d of %d" % (ok, ok + missed))
    return 1 if missed else 0


# --- sweep -----------------------------------------------------------------------------------------------------------
def target_of(text):
    words = text.split()
    for i, w in enumerate(words[:-1]):
        if bare(w) == "target":
            return home_path(bare(words[i + 1])) or None
    return None


def is_day(d):
    return len(d) == 10 and d[4] == "-" and d[7] == "-" and is_count(d[:4] + d[5:7] + d[8:])


def footer_dates(logs):
    md = _board("md_blocks")
    dates = []
    try:
        names = sorted(os.listdir(logs))
    except OSError as e:
        raise Fail("cannot list %s: %s" % (shown(logs, 200), e))
    for name in names:
        if not name.endswith(".tasks.md"):
            continue
        last = None
        for b in md.walk(md.parse(read_text(os.path.join(logs, name)).splitlines())):
            if b.kind == "heading" and b.level == 2 and b.text.startswith("Debrief close"):
                d = b.text[len("Debrief close"):].strip().strip("()").strip()
                if is_day(d) and (last is None or d > last):
                    last = d
        if last:
            dates.append(last)
    return dates


def cmd_sweep(todo, root, logs, stale):
    tm = _board("todo_md")

    class Ctx(object):
        lanes, token, rp = set(), "lane", ""

        def add(self, *a, **k):
            pass

        def classify(self, label, href):
            return {"label": label, "href": href, "kind": "other", "resolves": None, "id": ""}

    lines = [ln + "\n" for ln in read_text(todo).splitlines()]
    entries = tm.read_lane(lines, Ctx())[3]
    top = physical(root)
    dates = footer_dates(physical(logs))
    n_close = n_keep = n_stale = 0
    for e in entries:
        if e.get("state") == "done":
            continue
        ident = e.get("id") or ""
        target = target_of(e.get("text", ""))
        closing = False
        if target:
            try:
                path, where = lane_place(top, target)
            except Fail:
                path, where = None, "target is not a path"
            why = None
            if where == "target is not a path":
                why = where
            elif not ident:
                why = "no line id"
            elif where is not None:
                why = "target outside the lane root" if where.startswith("outside") else "no target file"
            elif not cites(read_text(path), ident):
                why = "target does not cite %s" % ident
            if why:
                n_keep += 1
                print("keep: %d %s (%s)" % (e["line"], shown(ident or "-"), shown(why)))
            else:
                closing = True
                n_close += 1
                print("close: %d %s target %s" % (e["line"], shown(ident), shown(target)))
        date = e.get("date") or ""
        if not closing and date:
            since = sum(1 for d in dates if d > date)
            if since >= stale:
                n_stale += 1
                print("stale: %d %s %d features debriefed since %s" % (e["line"], shown(ident or "-"), since, date))
    print("sweep: %d close, %d keep, %d stale" % (n_close, n_keep, n_stale))
    return 0


# --- table -----------------------------------------------------------------------------------------------------------
def spec_rows(spec, title="Feature Tasks"):
    md = _board("md_blocks")
    rows, level, on = [], 0, False
    for b in md.walk(md.parse(read_text(spec).splitlines())):
        if b.kind in ("heading", "setext"):
            text = b.text if b.kind == "heading" else " ".join(t for _n, t in b.lines)
            if on and b.level <= level:
                on = False
            if not on and text.strip().startswith(title):
                on, level = True, b.level
            continue
        if on and b.kind == "para":
            rows += [[c.strip() for c in t.strip().strip("|").split("|")] for _n, t in b.lines if t.strip().startswith("|")]
    if not rows:
        return None
    head = [c.lower() for c in rows[0]]
    if "status" not in head:
        raise Fail("the %s has no Status column" % (title if title.endswith("Table") else title + " table"))
    at = head.index("status")
    out = {}
    for r in rows[1:]:
        if all(set(c) <= set("-: ") for c in r) or len(r) <= at:
            continue
        cell = r[0].strip()
        if cell.startswith("[") and "](" in cell:  # a linked id: its label
            cell = cell[1:cell.index("](")]
        out[bare(cell)] = bare((r[at].split() or ["-"])[0])
    return out


def log_statuses(log):
    md = _board("md_blocks")
    out, cur = {}, None
    for b in md.walk(md.parse(read_text(log).splitlines())):
        if b.kind == "heading" and b.level <= 2:
            head = b.text.split(":", 1)[0] if b.level == 2 and ":" in b.text else ""
            cur = head if head and " " not in head else None
            continue
        if cur and b.kind == "para":
            first = b.lines[0][1].strip()
            if first.startswith("**Status:**"):
                out[cur] = (first[len("**Status:**"):].split() or ["-"])[0]
            cur = None  # only the first paragraph under a task heading is its status line
    return out


def cmd_table(spec, log):
    table = spec_rows(spec)
    if table is None:
        print("warn: no Feature Tasks table in %s" % shown(spec, 200))
    tasks = log_statuses(log)
    drift = diff_rows(table, tasks, "") if table is not None else 0
    own = spec_rows(log, "Summary Table")  # the log's own summary table, when it has one
    if own is not None:
        drift += diff_rows(own, tasks, " (the log's summary table)")
    if table is None and own is None:
        return 0
    print("table: %d rows, %d tasks, %d drift" % (len(table if table is not None else own), len(tasks), drift))
    return 1 if drift else 0


def diff_rows(table, tasks, where):
    drift = 0
    for tid, st in table.items():
        if tid not in tasks:
            drift += 1
            print("extra: %s (no task in the log)%s" % (shown(tid), where))
        elif tasks[tid] != st:
            drift += 1
            print("stale: %s table %s, log %s%s" % (shown(tid), shown(st, 20), shown(tasks[tid], 20), where))
    for tid, st in tasks.items():
        if tid not in table:
            drift += 1
            print("missing: %s (%s in the log, no table row)%s" % (shown(tid), shown(st, 20), where))
    return drift


# --- arguments -------------------------------------------------------------------------------------------------------
USAGE = ("usage: debrief-rows.py stop <debrief.md> | account --record <rec> | traces <debrief.md> [--record <rec>] | "
         "arrows <debrief.md> --rulings <list> [--rulings <list>] --root <lane> | "
         "sweep <todo.md> --root <lane> --logs <dir> [--stale <n>] | table <spec> <tasks log>")


def parse(args, flags, repeat=()):
    pos, opts = [], {}
    i = 0
    while i < len(args):
        a = args[i]
        if a in flags:
            if i + 1 >= len(args) or args[i + 1].startswith("--"):
                raise Fail("%s needs a value" % a)
            if a in repeat:
                opts.setdefault(a, []).append(args[i + 1])
            elif a in opts:
                raise Fail("%s given twice" % a)
            else:
                opts[a] = args[i + 1]
            i += 2
        elif a.startswith("--"):
            raise Fail("unknown option %s" % shown(a, 40))
        else:
            pos.append(a)
            i += 1
    return pos, opts


def need(opts, *names):
    for n in names:
        if n not in opts:
            raise Fail("%s is required" % n)


def main(argv):
    if len(argv) < 2:
        print("error: " + USAGE)
        return 2
    cmd, rest = argv[1], argv[2:]
    try:
        if cmd == "stop":
            pos, _ = parse(rest, ())
            if len(pos) != 1:
                raise Fail(USAGE)
            return cmd_stop(pos[0])
        if cmd == "account":
            pos, o = parse(rest, ("--record",))
            need(o, "--record")
            if pos:
                raise Fail(USAGE)
            return cmd_account(o["--record"])
        if cmd == "traces":
            pos, o = parse(rest, ("--record",))
            if len(pos) != 1:
                raise Fail(USAGE)
            return cmd_traces(pos[0], o.get("--record"))
        if cmd == "arrows":
            pos, o = parse(rest, ("--rulings", "--root"), repeat=("--rulings",))
            need(o, "--rulings", "--root")
            if len(pos) != 1:
                raise Fail(USAGE)
            return cmd_arrows(pos[0], o["--rulings"], o["--root"])
        if cmd == "sweep":
            pos, o = parse(rest, ("--root", "--logs", "--stale"))
            need(o, "--root", "--logs")
            stale = o.get("--stale", "3")
            if len(pos) != 1 or not is_count(stale) or int(stale) < 1:
                raise Fail(USAGE)
            return cmd_sweep(pos[0], o["--root"], o["--logs"], int(stale))
        if cmd == "table":
            pos, _ = parse(rest, ())
            if len(pos) != 2:
                raise Fail(USAGE)
            return cmd_table(pos[0], pos[1])
        raise Fail(USAGE)
    except Fail as e:
        print("error: %s" % e)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
