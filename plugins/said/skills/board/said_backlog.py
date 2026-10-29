#!/usr/bin/env python3
"""said_backlog.py - the backlog and todo reader beside the analyzer (stdlib only).

Reads two things by their own grammars and reports them as text or `--json`:

* the backlog, one fixed file `<docs-root>backlog.md` at the given root, plus its record folders
  `<docs-root>backlog/<YYMMDD>-<kind>-<slug>/idea.md`;
* each registry lane's todo list, `<lane root>/<docs-root>todo.md` (no argument names either file).

The backlog grammar (stated in the file's own frontmatter): the top level is a section, an H1
`# <title>` over an `=` rule, named by a registry lane token or by a target the frontmatter declares under
`targets:`; below it two topic levels, `##` then `###`; an entry is one line `- [<state>] [YYYY-MM-DD] <text>`
at column 0, state ` ` open, `+` in progress, `X` done; a priority token `[#A]`, `[#B]` or `[#C]` (or
`[#High]`, `[#Medium]`, `[#Low]`, the same values) follows the stamp; `#word` tokens in the text are tags;
sub-items are `- ` lines two spaces deeper, nested further by indent, at most two at the first depth, one
of them the record link `[<slug>](backlog/<slug>/idea.md)` or, once promoted, the feature link
`[<FEAT-NN>](<path to the feature spec>)`. The entry stages are Entry, Record, Promoted.

The todo grammar (stated in the file's header comment): `# <section>` over an `=` rule, an optional
`## <sub-section>` over a `-` rule, checkbox entries at column 0 with nested boxes under them, and
sub-bullets `- in ...`, `- adr: ...`, `- ref: ...`.

A line that breaks its grammar is a finding (file, line, code, message), never a crash; every text
field is stripped of control characters and capped, so the page, `--cli` and `--json` carry the same
bounded plain text. Roots are made absolute before anything derives from them.
"""
import argparse
from collections import Counter
import datetime
import json
import os
import sys
import time
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import said_status  # noqa: E402  the registry and lane-block readers live in the analyzer
import todo_md  # noqa: E402  the format's profile layer over the block parser; every read and every edited span comes from it
from todo_md import (  # noqa: E402,F401
    BIDI, FORMAT, FORMER_FORMATS, FORMER_KEYS, FORMER_STAGES, MIDDOT, PRIORITY_LETTERS, STATES, TEXT_CAP,
    bracket_spans, bracket_words, clean, norm_priority, stable_key, stamp_date, take_tags)

todo_md.PRIORITY_WORDS = said_status.PRIORITY_WORDS
PRIORITY_WORDS = said_status.PRIORITY_WORDS
STAGES = ("Entry", "Record", "Promoted")
RECORD_KINDS = ("idea", "handover", "bugfix")


def read_lines(path):
    with open(path, encoding="utf-8-sig", errors="replace") as fh:
        return fh.read().split("\n")


def rel(path, root):
    try:
        return os.path.relpath(path, root)
    except ValueError:
        return path


class Findings(object):
    def __init__(self):
        self.items = []

    def add(self, path, line, code, message, severity="error"):
        self.items.append({"file": clean(path, 300), "line": line, "code": code, "message": clean(message, 200), "severity": severity})


# ---------------------------------------------------------------- lane roots

def docs_root_of(root):
    """The lane's `SAID.docs-root:` from its own `## Lane` block; `docs/` when the block says nothing."""
    try:
        with open(os.path.join(root, "CLAUDE.md"), encoding="utf-8-sig", errors="replace") as fh:
            block = said_status.lane_block_lines(fh.read())
    except (OSError, ValueError):
        block = None
    value = said_status._block_key(block, "docs-root") if block else None
    value = (value or "docs/").rstrip("/") + "/"
    if value.startswith(("/", "~")) or ".." in value.split("/"):
        return "docs/"
    return value


def lane_rows(root):
    """[(token, absolute lane root)]: the registry rows of `<root>/CLAUDE.md`, else the root itself
    under its own `SAID.lane:` token (or `lane`)."""
    try:
        rows, _ = said_status.read_lane_registry(root)
    except Exception as e:  # a refused registry: one lane, the root, and a finding by the caller
        rows = []
        lane_rows.refused = str(e)
    if rows:
        return [(clean(token, 40), os.path.realpath(os.path.join(root, lane_root))) for token, lane_root in rows]
    token = None
    try:
        with open(os.path.join(root, "CLAUDE.md"), encoding="utf-8-sig", errors="replace") as fh:
            block = said_status.lane_block_lines(fh.read())
        token = said_status._block_key(block, "lane") if block else None
    except (OSError, ValueError):
        pass
    return [(clean(token or "lane", 40), root)]


lane_rows.refused = ""


# ---------------------------------------------------------------- the backlog file

class _Ctx(object):
    """What the profile layer needs from this module: where findings go, the lane tokens, how a link resolves."""

    def __init__(self, findings, rp, lanes=(), base_dir="", root="", token=""):
        self.findings, self.rp, self.lanes, self.base_dir, self.root, self.token = findings, rp, set(lanes), base_dir, root, token

    def add(self, line, code, message, severity="error"):
        self.findings.add(self.rp, line, code, message, severity=severity)

    def classify(self, label, href):
        return classify_link(label, href, self.base_dir, self.root)


def classify_link(label, href, base_dir, root):
    """The link's kind (record, feature, other), whether it resolves, and the slug or feature id."""
    target = href.split("#", 1)[0]
    if todo_md.starts_with_scheme(href) or not target:
        return {"label": clean(label, 120), "href": clean(href, 300), "kind": "other", "resolves": None, "id": ""}
    tpath = os.path.normpath(os.path.join(base_dir, target))
    exists = os.path.exists(tpath)
    parts = target.replace("\\", "/").split("/")
    kind, ident = "other", ""
    if len(parts) >= 3 and parts[-3] == "backlog" and parts[-1] == "idea.md":
        kind, ident = "record", parts[-2]
    elif "features" in parts and parts[-1].endswith(".md"):
        kind, ident = "feature", todo_md.feature_head(parts[-1])
        if not exists and ident:  # a promoted link also passes when the feature's working dir exists
            lane_root = os.path.normpath(os.path.join(os.path.dirname(tpath), "..", ".."))
            wd = os.path.join(lane_root, "docs", "working", ident)
            exists = os.path.isdir(wd)
    return {"label": clean(label, 120), "href": clean(href, 300), "kind": kind, "resolves": exists, "id": ident, "path": tpath}


def read_backlog(root, docs_root, findings, path=None, lines=None):
    """The backlog at `path` (default: the root's), read from `lines` when given (a rewrite checked before it is written)."""
    path = path or os.path.join(root, docs_root, "backlog.md")
    out = {"path": rel(path, root), "exists": os.path.isfile(path), "targets": {}, "sections": [], "entries": [], "records": []}
    if not out["exists"]:
        return out
    ctx = _Ctx(findings, out["path"], {token for token, _ in lane_rows(root)}, os.path.dirname(path), root)
    targets, fmt, _, sections, entries = todo_md.read_backlog(read_lines(path) if lines is None else lines, ctx)
    out["targets"] = {clean(k, 120): clean(v, 40) for k, v in targets.items()}
    out["front"] = {"format": clean(fmt or "", 40), "targets": out["targets"]}
    out["sections"] = sections
    out["entries"] = entries
    out["records"] = read_records(root, docs_root, findings)
    by_folder = {r["folder"]: r for r in out["records"]}
    for e in entries:
        e["stage"] = entry_stage(e)
        e["trail"] = entry_trail(e, by_folder.get(e.get("record")), root)
    return out


def read_records(root, docs_root, findings):
    bdir = os.path.join(root, docs_root, "backlog")
    records = []
    if not os.path.isdir(bdir):
        return records
    for d in sorted(os.listdir(bdir)):
        p = os.path.join(bdir, d)
        if not os.path.isdir(p) or d.startswith("."):
            continue
        fm = todo_md.record_folder(d)
        if not fm:
            continue  # a folder outside the record grammar (a generator, a map) is not a record
        rec = {"folder": clean(d, 200), "path": clean(rel(os.path.join(p, "idea.md"), root), 300), "stamp": fm[0], "date": stamp_date(fm[0]),
               "kind": clean(fm[1], 40), "slug": clean(fm[2], 160), "exists": os.path.isfile(os.path.join(p, "idea.md")),
               "title": "", "status": "", "status_class": "unrecorded", "priority": "", "priority_line": None,
               "resolution": "", "feature_line": "", "feature": None, "trail": []}
        known = rec["kind"] in RECORD_KINDS
        if not known:  # one finding on the folder, not a second for its missing idea.md
            findings.add(clean(rel(p, root), 300), 0, "record-kind-unknown", "the folder kind `%s` is not idea, handover or bugfix" % rec["kind"])
        if not rec["exists"]:
            if known:
                findings.add(clean(rel(p, root), 300), 0, "record-no-idea", "a record folder without idea.md")
            records.append(rec)
            continue
        lines = read_lines(os.path.join(p, "idea.md"))
        sec = ""
        for i, ln in enumerate(lines, 1):
            s = ln.strip()
            if ln.startswith("# ") and not rec["title"]:
                rec["title"] = clean(ln[2:].strip(), 200)
                continue
            if i <= 40:
                word = todo_md.priority_head(s)
                if word is not None and rec["priority_line"] is None:
                    rec["priority_line"] = i
                    letter = norm_priority(word)
                    if letter and letter not in PRIORITY_LETTERS:
                        findings.add(rec["path"], i, "priority-letter", "the priority `%s` is outside A, B, C (High, Medium, Low)" % clean(letter, 20))
                    rec["priority"] = letter if letter in PRIORITY_LETTERS else ""
                status = todo_md.bold_line(s, "Status")
                if status is not None and not rec["status"]:
                    rec["status"] = clean(status, 160)
            if ln.startswith("## "):
                sec = ln[3:].strip()
                continue
            if sec.startswith("Resolution") and s and not s.startswith("<") and not rec["resolution"]:
                rec["resolution"] = clean(s, 200)
            if sec.startswith("4. Feature") and s.startswith("-") and not rec["feature_line"]:
                rec["feature_line"] = clean(s[1:].strip(), 200)
                fid = todo_md.feature_search(rec["feature_line"])
                if fid and not rec["feature_line"].lower().startswith("none"):
                    rec["feature"] = fid
        low = rec["status"].lower()
        if rec["resolution"]:
            rec["status_class"] = "resolved"
        elif low.startswith("idea"):
            rec["status_class"] = "idea"
        elif low.startswith("pre-scope"):  # the template's bare state word: the folder's kind decides
            rec["status_class"] = "bugfix" if rec["kind"] == "bugfix" else "idea"
        elif low.startswith("owed"):
            rec["status_class"] = "owed"
        elif low.startswith("in scope"):
            rec["status_class"] = "in-scope"
        elif low.startswith("bugfix"):
            rec["status_class"] = "bugfix"
        records.append(rec)
    return records


def entry_stage(e):
    """Promoted once a feature link is read, Record once a record link is, else Entry; done is a state, not a stage."""
    return "Promoted" if e.get("feature") else "Record" if e.get("record") else "Entry"


def entry_trail(e, rec, root):
    """entry -> idea record -> feature scope -> spec -> tasks, each with its existence."""
    trail = []
    if rec:
        trail.append({"kind": rec["kind"], "path": rec["path"], "exists": rec["exists"], "date": rec["date"]})
    fid = e.get("feature") or (rec or {}).get("feature")
    fp = e.get("feature_path") or ""
    if fid and fp:
        lane_root = os.path.normpath(os.path.join(os.path.dirname(fp), "..", ".."))
        docs = os.path.join(lane_root, "docs")
        for kind, path in (("scope", os.path.join(docs, "working", fid, "scope.md")),
                           ("spec", os.path.join(docs, "features", fid + ".md")),
                           ("tasks", os.path.join(docs, "features", fid + ".tasks.md"))):
            trail.append({"kind": kind, "path": rel(path, root), "exists": os.path.isfile(path)})
    return trail


# ---------------------------------------------------------------- the todo files

def read_lane_todo(token, lane_root, root, findings):
    docs_root = docs_root_of(lane_root)
    path = os.path.join(lane_root, docs_root, "todo.md")
    out = {"lane": token, "root": rel(lane_root, root), "path": rel(path, root), "exists": os.path.isfile(path),
           "sections": [], "entries": []}
    if not out["exists"]:
        return out
    ctx = _Ctx(findings, out["path"], (), os.path.dirname(path), root, token)
    fmt, _, sections, entries = todo_md.read_lane(read_lines(path), ctx)
    out["front"] = {"format": clean(fmt or "", 40)}
    out["sections"] = sections
    out["entries"] = entries
    return out


# ---------------------------------------------------------------- the whole read

def known_features(rows):
    """The feature ids any registry lane holds: a spec file `<docs>features/<id>.md` or a working folder `<docs>working/<id>/`."""
    ids = set()
    for _token, lane_root in rows:
        docs = os.path.join(lane_root, docs_root_of(lane_root))
        for sub, tail in (("features", ".md"), ("working", "")):
            try:
                names = os.listdir(os.path.join(docs, sub))
            except OSError:
                continue
            ids.update(n[:len(n) - len(tail)] for n in names if n.endswith(tail) and todo_md.is_feature_id(n[:len(n) - len(tail)]))
    return ids


def serves_feature(entry, known):
    """The known feature id a todo line's first `in <id>` sub-bullet names, else ''."""
    for b in entry["sub_bullets"]:
        ident = b["kind"] == "in" and todo_md.serves_id(b["text"])
        if ident:
            return ident if ident in known else ""
    return ""


def read_all(root):
    root = os.path.realpath(os.path.abspath(root))  # absolute and physical before anything derives from it
    findings = Findings()
    docs_root = docs_root_of(root)
    lane_rows.refused = ""
    rows = lane_rows(root)
    if lane_rows.refused:
        findings.add("CLAUDE.md", 0, "registry-refused", lane_rows.refused)
    data = {"root": root, "docs_root": docs_root, "backlog": read_backlog(root, docs_root, findings),
            "todo": [read_lane_todo(token, lane_root, root, findings) for token, lane_root in rows]}
    known = known_features(rows)
    for t in data["todo"]:
        for e in t["entries"]:
            e["serves"] = serves_feature(e, known)
    data["findings"] = findings.items
    bl = data["backlog"]
    data["counts"] = {
        "backlog_entries": len(bl["entries"]), "backlog_records": len(bl["records"]),
        "backlog_open": sum(1 for e in bl["entries"] if e["state"] == "open"),
        "backlog_wip": sum(1 for e in bl["entries"] if e["state"] == "wip"),
        "backlog_done": sum(1 for e in bl["entries"] if e["state"] == "done"),
        "backlog_prioritized": sum(1 for e in bl["entries"] if e["priority"]),
        "todo_lanes": len(data["todo"]), "todo_files": sum(1 for t in data["todo"] if t["exists"]),
        "todo_entries": sum(len(t["entries"]) for t in data["todo"]),
        "findings": len(findings.items),
    }
    return data


def render_text(data):
    bl = data["backlog"]
    out = ["backlog: %s%s" % (bl["path"], "" if bl["exists"] else " (missing)")]
    for sec in bl["sections"]:
        total = len(sec["entries"]) + sum(len(t["entries"]) + sum(len(u["entries"]) for u in t["subtopics"]) for t in sec["topics"])
        out.append("  # %s%s  (%d entries, %d topics)" % (sec["title"], " [target]" if sec["kind"] == "target" else "", total, len(sec["topics"])))
        for e in sec["entries"]:
            out.append("    %s" % entry_line(e))
        for t in sec["topics"]:
            out.append("    ## %s  (%d)" % (t["title"], len(t["entries"]) + sum(len(u["entries"]) for u in t["subtopics"])))
            for e in t["entries"]:
                out.append("      %s" % entry_line(e))
            for u in t["subtopics"]:
                out.append("      ### %s  (%d)" % (u["title"], len(u["entries"])))
                for e in u["entries"]:
                    out.append("        %s" % entry_line(e))
    if bl["records"]:
        out.append("  records: %d" % len(bl["records"]))
        for r in bl["records"]:
            out.append("    %s  %s  %s" % (r["folder"], r["status_class"], ("[#%s]" % r["priority"]) if r["priority"] else ""))
    for t in data["todo"]:
        out.append("todo %s: %s%s" % (t["lane"], t["path"], "" if t["exists"] else " (missing)"))
        for sec in t["sections"]:
            n = len(sec["entries"]) + sum(len(s["entries"]) for s in sec["subsections"])
            out.append("  # %s  (%d entries)" % (sec["title"], n))
    if data["findings"]:
        out.append("findings: %d" % len(data["findings"]))
        for f in data["findings"]:
            out.append("  %s:%s %s %s" % (f["file"], f["line"], f["code"], f["message"]))
    else:
        out.append("findings: none")
    return "\n".join(out)


def entry_line(e):
    mark = {"open": "[ ]", "wip": "[+]", "done": "[X]"}.get(e["state"], "[?]")
    prio = ("[#%s] " % e["priority"]) if e["priority"] else ""
    tags = "".join(" #" + t for t in e.get("tags") or [])
    return "%s %s%s%s%s %s" % (mark, ("[%s] " % e["date"]) if e["stamp"] else "", prio, e["text"][:80], tags, ("-> " + e["feature"]) if e.get("feature") else "")


# ---------------------------------------------------------------- the backlog board's view model
#
# One view model for the board page and `--board backlog` (text and `--json`), so the page's numbers are
# the terminal's: every entry once by stage and once by priority, each row with its record trail and the
# feature it was promoted into. Paths are root-relative; no absolute path leaves the reader.

STAGE_ORDER = STAGES
PRIORITY_ORDER = ("A", "B", "C", "none")


def board_row(e):
    return {"key": e["key"], "line": e["line"], "state": e["state"], "stamp": e["stamp"], "date": e["date"],
            "position": 0 if e.get("parent") else e.get("position") or 0,
            "priority": e["priority"], "section": e["section"], "group": e["group"], "subgroup": e["subgroup"], "text": e["text"], "tags": e["tags"],
            "stage": e["stage"], "feature": e.get("feature") or "", "record": e.get("record") or "",
            "trail": [{"kind": t["kind"], "path": t["path"], "exists": t["exists"], "date": t.get("date") or ""} for t in e["trail"]],
            "raw": e.get("raw", ""),
            "notes": [{"text": b["text"], "depth": b["depth"], "line": b["line"], "raw": b.get("raw", "")} for b in e["sub_bullets"]]}


def board_view(data):
    bl = data["backlog"]
    rows = [board_row(e) for e in bl["entries"]]
    stages = [s for s in STAGE_ORDER if any(r["stage"] == s for r in rows)]
    stages += sorted({r["stage"] for r in rows} - set(STAGE_ORDER))
    by_stage = [{"stage": s, "rows": [r for r in rows if r["stage"] == s]} for s in stages]
    by_priority = [{"priority": p, "rows": [r for r in rows if (r["priority"] or "none") == p]} for p in PRIORITY_ORDER]
    by_priority = [g for g in by_priority if g["rows"]]
    outline = [{"title": sec["title"], "topics": [{"title": t["title"], "subtopics": [u["title"] for u in t["subtopics"]]} for t in sec["topics"]]} for sec in bl["sections"]]
    return {"board": "backlog", "path": bl["path"], "exists": bl["exists"], "targets": bl["targets"], "outline": outline,
            "by_stage": by_stage, "by_priority": by_priority,
            "counts": {"entries": len(rows),
                       "by_stage": {g["stage"]: len(g["rows"]) for g in by_stage},
                       "by_priority": {g["priority"]: len(g["rows"]) for g in by_priority},
                       "findings": len(data["findings"])}}


def render_board_text(view):
    c = view["counts"]
    out = ["backlog board: %s%s  %d entries, %d findings" % (view["path"], "" if view["exists"] else " (missing)",
                                                            c["entries"], c["findings"])]
    for title, groups, label in (("by stage", view["by_stage"], "stage"), ("by priority", view["by_priority"], "priority")):
        out.append("  %s" % title)
        for g in groups:
            out.append("    %s  (%d)" % (g[label], len(g["rows"])))
            for r in g["rows"]:
                trail = ", ".join("%s%s" % (t["kind"], "" if t["exists"] else " (missing)") for t in r["trail"])
                out.append("      %s%s" % (board_line(r), ("  trail: " + trail) if trail else ""))
    return "\n".join(out)


def board_line(r):
    mark = {"open": "[ ]", "wip": "[+]", "done": "[X]"}.get(r["state"], "[?]")
    prio = ("[#%s] " % r["priority"]) if r["priority"] else ""
    return "%s %s%s%s%s" % (mark, ("[%s] " % r["date"]) if r["stamp"] else "", prio, r["text"][:80],
                            (" -> " + r["feature"]) if r["feature"] else "")


# ---------------------------------------------------------------- the todo board's view model
#
# One tab per registry lane whose todo file exists, none for a lane without one; when no lane has one, the
# board names the paths it checked. The page, `--board todo` and `--board todo --json` share this model.

TODO_STATES = ("open", "wip", "done")


def todo_row(e, depth, parent_line):
    return {"key": e["key"], "line": e["line"], "depth": depth, "state": e["state"], "stamp": e["stamp"],
            "position": 0 if e.get("parent") else e.get("position") or 0,
            "date": e["date"], "priority": e["priority"], "section": e["section"], "subsection": e["subsection"],
            "text": e["text"], "parent_line": parent_line, "raw": e["raw"], "serves": e["serves"],
            "sub_bullets": [{"kind": b["kind"], "text": b["text"], "line": b["line"], "raw": b["raw"]} for b in e["sub_bullets"]]}


def todo_tab(t):
    rows, stack, sect = [], [], None  # stack: (indent, line) of the open boxes; depth and parent by indent, never by key
    for e in t["entries"]:
        where = (e["section"], e["subsection"])
        if where != sect:
            stack, sect = [], where
        while stack and stack[-1][0] >= e["indent"]:
            stack.pop()
        rows.append(todo_row(e, len(stack), stack[-1][1] if stack else 0))
        stack.append((e["indent"], e["line"]))
    counts = {"entries": len(rows)}
    for s in TODO_STATES + ("unknown",):
        counts[s] = sum(1 for r in rows if r["state"] == s)
    for p in PRIORITY_ORDER:
        counts[p] = sum(1 for r in rows if (r["priority"] or "none") == p)
    return {"lane": t["lane"], "root": t.get("root") or "", "path": t["path"], "rows": rows, "counts": counts}


def todo_view(data):
    tabs = [todo_tab(t) for t in data["todo"] if t["exists"]]
    return {"board": "todo", "tabs": tabs, "checked": [t["path"] for t in data["todo"]],
            "counts": {"tabs": len(tabs), "entries": sum(t["counts"]["entries"] for t in tabs),
                       "findings": len(data["findings"])}}


def todo_filter(rows, state="all", priority="all"):
    """The rows that match, each with its non-matching ancestors before it as context: (row, matched)."""
    hit = {r["line"] for r in rows if (state == "all" or r["state"] == state)
           and (priority == "all" or (r["priority"] or "none") == priority)}
    parent = {r["line"]: r["parent_line"] for r in rows}
    keep = set(hit)
    for line in hit:
        p = parent.get(line)
        while p:
            keep.add(p)
            p = parent.get(p)
    return [(r, r["line"] in hit) for r in rows if r["line"] in keep]


def render_todo_text(view):
    c = view["counts"]
    out = ["todo board: %d tabs, %d entries, %d findings" % (c["tabs"], c["entries"], c["findings"])]
    if not view["tabs"]:
        out.append("  no lane has a todo file; checked: %s" % (", ".join(view["checked"]) or "no lane"))
    for t in view["tabs"]:
        tc = t["counts"]
        out.append("  %s: %s  %d entries (open %d, in progress %d, done %d, unknown %d; A %d, B %d, C %d, none %d)"
                   % (t["lane"], t["path"], tc["entries"], tc["open"], tc["wip"], tc["done"], tc["unknown"], tc["A"], tc["B"], tc["C"], tc["none"]))
        for r in t["rows"]:
            mark = {"open": "[ ]", "wip": "[+]", "done": "[X]"}.get(r["state"], "[?]")
            prio = ("[#%s] " % r["priority"]) if r["priority"] else ""
            out.append("    %s%s %s%s%s" % ("  " * r["depth"], mark, ("[%s] " % r["date"]) if r["stamp"] else "", prio, r["text"][:80]))
    return "\n".join(out)


# ---------------------------------------------------------------- the writers
#
# Two writes, one code path for the page routes and the manage skill: a priority token on an entry
# line, a todo line or a record head, and a manual order (a line move within an entry's section and
# topic, its sub-bullets and nested boxes carried). A write names its target by the reader's stable
# key and line position and refuses when the file no longer holds that entry there, checked again on
# the bytes it is about to rewrite; a refusal leaves every byte as it was. The file is rewritten byte
# for byte except the edited or moved lines (line endings, a byte-order mark, the trailing newline and
# the file mode kept), through a fresh temp file in the same directory, and only inside the root (or
# the lane root) it was read from. Every argument is treated as untrusted: an odd value is a refusal,
# never an exception.

import tempfile  # noqa: E402  (the writers' temp file)


class Refused(Exception):
    """A write that must not happen; the message says why."""


def _text(value, what, cap=200):
    if not isinstance(value, str):
        raise Refused("%s must be text" % what)
    return clean(value, cap)


def _int(value, what):
    if isinstance(value, bool) or not isinstance(value, int):
        try:
            value = int(str(value).strip())
        except (TypeError, ValueError):
            raise Refused("%s must be a whole number" % what)
    return value


def _read_raw(path):
    with open(path, "rb") as fh:
        text = fh.read().decode("utf-8", "surrogateescape")
    bom = text.startswith("\ufeff")
    return bom, (text[1:] if bom else text).split("\n")


def _eol(lines):
    """('\\r' when every line but the last ends in CR, else ''), and whether the file ends in a newline."""
    body = lines[:-1]
    crlf = bool(body) and all(ln.endswith("\r") for ln in body)
    return ("\r" if crlf else ""), lines[-1] == ""


def _apply_eol(lines, cr, terminated):
    """Every line but the last ends with the file's terminator; the last line is bare (unterminated
    file) or empty (terminated file). Only called when the file was consistent to begin with."""
    if not cr:
        return lines
    out = [ln if ln.endswith("\r") else ln + "\r" for ln in lines[:-1]]
    last = lines[-1]
    out.append("" if terminated else last.rstrip("\r"))
    return out


def _write_raw(path, bom, lines):
    """Replace `path` (a real file) with `lines`, through a fresh temp file beside it; mode kept."""
    if not os.access(path, os.W_OK):
        raise Refused("%s is read-only; a write never replaces a file it may not write" % os.path.basename(path))
    data = (("\ufeff" if bom else "") + "\n".join(lines)).encode("utf-8", "surrogateescape")
    mode = os.stat(path).st_mode & 0o7777
    fd, tmp = tempfile.mkstemp(prefix=".writing-", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _docs_home(lane):
    """The real folder of `lane`'s declared docs root: every backlog, record and todo write stays in it
    (a symlinked docs root is the lane's own choice)."""
    return os.path.realpath(os.path.join(lane, docs_root_of(lane).rstrip("/")))


def _inside(path, root):
    """The real path of `path`, which must lie under `root` (both physical)."""
    real = os.path.realpath(path)
    if real != root and not real.startswith(root.rstrip(os.sep) + os.sep):
        raise Refused("%s lies outside %s; a write never leaves its root" % (rel(path, root), root))
    return real


def _check_letter(letter):
    letter = _text(letter, "the priority letter", 20).strip()
    if letter.lower() == "none":
        letter = ""
    if letter and letter not in PRIORITY_LETTERS:
        raise Refused("the priority letter `%s` is outside A, B, C (or `none` to remove)" % letter)
    return letter


def _locate(root, key, line, lane):
    """The reader's view of the file holding `key` at `line`: (real file path, key prefix, entries,
    top-level containers, the entry)."""
    key = _text(key, "the key", 80)
    line = _int(line, "the line")
    if lane is None:
        if not key.startswith("backlog:"):
            raise Refused("`%s` is not a backlog key; a todo key needs --lane <token>" % key)
        bl = read_backlog(root, docs_root_of(root), Findings())  # a backlog write reads no todo file
        if not bl["exists"]:
            raise Refused("no backlog file at %s" % bl["path"])
        containers = []
        for sec in bl["sections"]:
            containers.append(("section `%s`" % sec["title"], sec["entries"]))
            for tp in sec["topics"]:
                containers.append(("topic `%s` of section `%s`" % (tp["title"], sec["title"]), tp["entries"]))
                for u in tp["subtopics"]:
                    containers.append(("subtopic `%s` of topic `%s`" % (u["title"], tp["title"]), u["entries"]))
        path, entries, prefix = _inside(os.path.join(root, bl["path"]), _docs_home(root)), bl["entries"], "backlog"
    else:
        data = read_all(root)
        lane = _text(lane, "the lane token", 40)
        t = next((t for t in data["todo"] if t["lane"] == lane), None)
        if t is None:
            raise Refused("no lane `%s` in the registry" % lane)
        if not t["exists"]:
            raise Refused("lane `%s` has no todo file (%s)" % (lane, t["path"]))
        if not key.startswith("todo-%s:" % lane):
            raise Refused("`%s` is not a key of lane `%s`" % (key, lane))
        containers = []
        for sec in t["sections"]:
            containers.append(("section `%s`" % sec["title"], sec["entries"]))
            for sub in sec["subsections"]:
                containers.append(("sub-section `%s` of section `%s`" % (sub["title"], sec["title"]), sub["entries"]))
        lane_root = os.path.realpath(os.path.join(root, t["root"]))
        path, entries, prefix = _inside(os.path.join(root, t["path"]), _docs_home(lane_root)), t["entries"], "todo-" + lane
    at = next((e for e in entries if e["line"] == line), None)
    if at is None or at["key"] != key:
        now = next((e["line"] for e in entries if e["key"] == key), None)
        where = ("it is now at line %d" % now) if now else "it is not in the file"
        raise Refused("stale position: line %d does not hold the entry `%s` (%s)" % (line, key, where))
    return path, prefix, entries, containers, at


def _verify_raw(lines, prefix, key, line):
    """The bytes about to be rewritten still hold `key` at `line` (the check the reader made, redone
    on this read, so a change between the two reads is a refusal)."""
    if line < 1 or line > len(lines):
        raise Refused("stale position: line %d is past the end of the file" % line)
    box = todo_md.box_of(lines[line - 1].rstrip("\r"))
    if not box or stable_key(prefix, box[2]) != key:
        raise Refused("stale position: the file changed since it was read; line %d no longer holds `%s`" % (line, key))


def _container_of(containers, entry):
    for name, members in containers:
        if any(m["line"] == entry["line"] for m in members):
            return name, [m for m in members if m.get("parent") is None]
    return None, []


def _opens_entry_or_heading(body):
    s = body.lstrip(" ")
    return todo_md.box_of(body) is not None or (len(body) - len(s) <= 3 and s.startswith("#"))


def _block_last(entries, top, entry, lines):
    """The 1-based last line of the entry's block as the reader attached it: its sub-bullets, its
    nested boxes and theirs; refused when another top-level entry sits inside that span, or when a line
    that belongs to no entry follows it before the next entry or heading (it would attach to another entry)."""
    last = entry["line"]
    pending = [entry]
    seen = set()
    while pending:
        e = pending.pop()
        if e["line"] in seen:
            continue
        seen.add(e["line"])
        last = max([last] + [sb["line"] for sb in e["sub_bullets"]])
        for child in entries:
            if child.get("parent") == e["key"] and child["line"] > entry["line"]:
                last = max(last, child["line"])
                pending.append(child)
    inside = [t["line"] for t in top if entry["line"] < t["line"] <= last]
    if inside:
        raise Refused("the block of line %d runs over the entry at line %d; fix the file's indentation first" % (entry["line"], inside[0]))
    for i in range(last, len(lines)):
        body = lines[i].rstrip("\r")
        if _opens_entry_or_heading(body):
            break
        if body.strip():
            raise Refused("line %d belongs to no entry; a write would attach it to another entry, fix the file first" % (i + 1))
    return last


def _token_line(line, letter):
    """The box line with its priority token written, replaced or removed; every other byte kept."""
    new = todo_md.with_priority(line, letter)
    if new is None:
        raise Refused("line is not a checkbox entry")
    return new


def _split_cr(line):
    body = line.rstrip("\r")
    return body, line[len(body):]


def set_priority(root, letter, key=None, line=None, lane=None, record=None):
    """Write, replace or remove (`none`) the priority token of one entry line (`key` + `line`, with
    `lane` for a todo line) or of one record head (`record`, the folder name). (ok, message)."""
    try:
        root = os.path.realpath(os.path.abspath(_text(root, "the root", 1000)))
        letter = _check_letter(letter)
        if record is not None:
            return True, _set_record_priority(root, _text(record, "the record folder"), letter)
        if key is None or line is None:
            raise Refused("name the target: --key and --line (with --lane for a todo line), or --record")
        path, prefix, entries, containers, at = _locate(root, key, line, lane)
        bom, lines = _read_raw(path)
        _verify_raw(lines, prefix, at["key"], at["line"])
        new = _token_line(lines[at["line"] - 1], letter)
        if new == lines[at["line"] - 1]:
            return True, "same %s:%d already %s" % (rel(path, root), at["line"], letter or "none")
        lines[at["line"] - 1] = new
        _write_raw(path, bom, lines)
        return True, "wrote %s:%d priority %s -> %s" % (rel(path, root), at["line"], at["priority"] or "none", letter or "none")
    except Refused as e:
        return False, "refused: %s" % e
    except (OSError, ValueError, TypeError, KeyError, IndexError) as e:
        return False, "refused: %s" % clean("%s: %s" % (type(e).__name__, e), 200)


def _set_record_priority(root, folder, letter):
    if not todo_md.record_folder(folder) or "/" in folder or "\\" in folder or folder in (".", ".."):
        raise Refused("`%s` is not a record folder name (<YYMMDD>-<kind>-<slug>)" % folder)
    path = os.path.join(root, docs_root_of(root), "backlog", folder, "idea.md")
    if not os.path.isfile(path):
        raise Refused("no record %s" % rel(path, root))
    path = _inside(path, _docs_home(root))
    bom, lines = _read_raw(path)
    cr, terminated = _eol(lines)
    head = min(40, len(lines))
    pl = next((j for j in range(head) if todo_md.priority_head(lines[j].rstrip("\r").strip()) is not None), None)
    new = ("**Priority:** [#%s]" % letter) if letter else None
    if pl is not None:
        if new:
            if lines[pl].rstrip("\r").strip() == new:
                return "same %s already %s" % (rel(path, root), letter)
            lines[pl] = new + cr
        else:
            del lines[pl]
    elif new:
        st = next((j for j in range(head) if todo_md.bold_line(lines[j].rstrip("\r").strip(), "Status") is not None), None)
        h1 = next((j for j in range(head) if lines[j].startswith("# ")), None)
        at = (st + 1) if st is not None else ((h1 + 1) if h1 is not None else 0)
        if st is None and h1 is not None and at < len(lines) and lines[at].strip() == "":
            at += 1
        if at >= 40:
            raise Refused("no room for a priority line in the first 40 lines of %s (the reader looks no further)" % rel(path, root))
        lines.insert(at, new + cr)
    else:
        return "same %s already none" % rel(path, root)
    _write_raw(path, bom, _apply_eol(lines, cr, terminated))
    return "wrote %s priority -> %s" % (rel(path, root), letter or "none")


def _spec_head_lines(lines, letter, cr):
    """`lines` of a feature spec with the `**Priority:**` line of its head set to `letter` ('' removes it);
    a minted id token that ends that line stays. A new line goes under the title, a blank line each side;
    removing it takes the blank it made. Every other line is kept as it was."""
    term = lines[-1:] if lines and lines[-1] == "" else []
    body = lines[:len(lines) - len(term)]
    at = said_status.head_priority(body)[1]
    if at is not None:
        ident = todo_md.priority_head_parts(body[at].rstrip("\r").strip())[1]
        if letter or ident:
            body[at] = " ".join(w for w in ("**Priority:**", ("[#%s]" % letter) if letter else "", ident or "") if w) + cr
        else:
            del body[at]
            if at and not body[at - 1].strip() and (at >= len(body) or not body[at].strip()):
                del body[at - 1]
        return body + term
    if not letter:
        return lines
    h1 = next((j for j in range(min(said_status.HEAD_LINES, len(body))) if body[j].startswith("# ")), None)
    pos, put = (0, []) if h1 is None else (h1 + 1, [])
    if h1 is not None:
        if pos < len(body) and not body[pos].strip():
            pos += 1
        else:
            put.append(cr)
    if pos >= said_status.HEAD_LINES:
        raise Refused("no room for a priority line in the first %d lines of the spec (the reader looks no further)" % said_status.HEAD_LINES)
    put.append("**Priority:** [#%s]" % letter + cr)
    if pos < len(body) and body[pos].strip():
        put.append(cr)
    return body[:pos] + put + body[pos:] + term


def _spec_in(spec, lane_root):
    """The real path of a feature spec, which must lie in the lane (its root or its declared docs root)."""
    try:
        return _inside(spec, lane_root)
    except Refused:
        return _inside(spec, _docs_home(lane_root))


def set_feature_priority(spec, lane_root, letter):
    """Write, replace or remove (`none`) the `**Priority:**` line on the head of one feature spec, a file inside
    `lane_root`; a trailing id token on that line stays. (ok, message)."""
    try:
        letter = _check_letter(letter)
        lane_root = os.path.realpath(os.path.abspath(lane_root))
        path = _spec_in(_text(spec, "the spec path", 1000), lane_root)
        if not os.path.isfile(path):
            raise Refused("no spec at %s" % rel(path, lane_root))
        bom, lines = _read_raw(path)
        now = said_status.head_priority(lines)[0]
        cr, terminated = _eol(lines)
        new = _spec_head_lines(lines, letter, cr)
        if new == lines:
            return True, "same %s already %s" % (rel(path, lane_root), letter or "none")
        _write_raw(path, bom, _apply_eol(new, cr, terminated))
        return True, "wrote %s priority %s -> %s" % (rel(path, lane_root), now or "none", letter or "none")
    except Refused as e:
        return False, "refused: %s" % e
    except (OSError, ValueError, TypeError, KeyError, IndexError) as e:
        return False, "refused: %s" % clean("%s: %s" % (type(e).__name__, e), 200)


def move_entry(root, key, line, lane=None, to=None, before=None):
    """Move the entry `key` at `line` (with `lane` for a todo entry) to position `to` (1-based) among
    the top-level entries of its own section, topic or subtopic, or ahead of the entry `before` (a key in the
    same container); the entry's sub-bullets and nested boxes travel with it. (ok, message)."""
    try:
        root = os.path.realpath(os.path.abspath(_text(root, "the root", 1000)))
        if (to is None) == (before is None):
            raise Refused("name the destination: --to <position> or --before <key>, one of them")
        path, prefix, entries, containers, at = _locate(root, key, line, lane)
        if at.get("parent"):
            raise Refused("`%s` is a nested box; move its top-level entry" % at["key"])
        name, top = _container_of(containers, at)
        if name is None:
            raise Refused("the entry sits in no section")
        top = sorted(top, key=lambda e: e["line"])
        others = [e for e in top if e["line"] != at["line"]]
        if before is not None:
            before = _text(before, "the key to move before", 80)
            target = next((e for e in top if e["key"] == before), None)
            if target is None:
                if any(e["key"] == before for e in entries):
                    raise Refused("`%s` is outside the entry's %s; an entry moves within its own section, topic or subtopic" % (before, name))
                raise Refused("no entry `%s` to move before" % before)
            if target["line"] == at["line"]:
                return True, "same %s:%d already there" % (rel(path, root), at["line"])
            to = next(i + 1 for i, e in enumerate(others) if e["line"] == target["line"])
        to = _int(to, "the position")
        if to < 1 or to > len(top):
            raise Refused("position %d is outside 1..%d of the entry's %s" % (to, len(top), name))
        if others[:to - 1] + [at] + others[to - 1:] == top:
            return True, "same %s:%d already at position %d" % (rel(path, root), at["line"], to)
        bom, lines = _read_raw(path)
        for e in top:
            _verify_raw(lines, prefix, e["key"], e["line"])
        cr, terminated = _eol(lines)
        last = {e["line"]: _block_last(entries, top, e, lines) for e in top}
        s = at["line"]
        moving = lines[s - 1:last[s]]
        del lines[s - 1:last[s]]

        def adj(n):
            return n - len(moving) if n > s else n

        if to - 1 < len(others):
            idx = adj(others[to - 1]["line"]) - 1
        else:
            idx = adj(last[others[-1]["line"]])
        lines[idx:idx] = moving
        _write_raw(path, bom, _apply_eol(lines, cr, terminated))
        return True, "wrote %s: moved line %d (%d lines) to position %d of %s" % (rel(path, root), s, len(moving), to, name)
    except Refused as e:
        return False, "refused: %s" % e
    except (OSError, ValueError, TypeError, KeyError, IndexError) as e:
        return False, "refused: %s" % clean("%s: %s" % (type(e).__name__, e), 200)


# ---------------------------------------------------------------- the manager's operations
#
# lint, record, supersede and promote serve the backlog manager skill. They read the backlog file and
# its record folders only (never a todo file), refuse with exit 2 and a line starting `refused:`, and
# leave every file unchanged on a refusal.

ARG_CAP = {"the slug": 60, "the feature id": 40, "the kind": 20, "the date": 10}


def _exact(value, what, grammar):
    """The argument as given, accepted whole by its ASCII grammar (a todo_md predicate) and within its length:
    never stripped, cut or cleaned into shape first."""
    if not isinstance(value, str):
        raise Refused("%s must be text" % what)
    if len(value) > ARG_CAP[what] or not grammar(value):
        raise Refused("%s `%s` is not in its grammar" % (what, clean(value, 40).replace("\n", " ")))
    return value
KIND_TITLE = {"idea": "Idea", "handover": "Handover", "bugfix": "Bugfix"}
KIND_STATUS = {"idea": "Idea / pre-scope", "handover": "owed reply", "bugfix": "Bugfix / not started"}


def lint(root):
    """The backlog against its frontmatter grammar plus the priority grammar: (data, exit code)."""
    root = os.path.realpath(os.path.abspath(root))
    findings = Findings()
    docs_root = docs_root_of(root)
    bl = read_backlog(root, docs_root, findings)
    if not bl["exists"]:
        findings.add(bl["path"], 0, "backlog-missing", "no backlog file")
    items = sorted((dict(f, severity="warning" if f["severity"] == "warn" else f["severity"]) for f in findings.items),
                   key=lambda f: (f["file"] != bl["path"], f["file"], f["line"], f["code"]))
    errors = sum(1 for f in items if f["severity"] == "error")
    data = {"path": bl["path"], "findings": items, "errors": errors, "warnings": len(items) - errors}
    return data, (1 if errors else 0)


def render_lint(data):
    out = ["%s:%s %s %s: %s" % (f["file"], f["line"], f["severity"], f["code"], f["message"]) for f in data["findings"]]
    out.append("lint: %d error%s, %d warning%s" % (data["errors"], "" if data["errors"] == 1 else "s",
                                                   data["warnings"], "" if data["warnings"] == 1 else "s"))
    return "\n".join(out)


def _backlog_entry(root, key, line):
    """(backlog path, raw bom, raw lines, the entry, the reader's backlog) for a top-level entry."""
    path, prefix, entries, containers, at = _locate(root, key, line, None)
    if at.get("parent"):
        raise Refused("`%s` is a nested box; the backlog nests one level only, fix the file first" % at["key"])
    if at["indent"] != 0:
        raise Refused("the entry at line %d sits at %d spaces, outside the grammar; fix the file first" % (at["line"], at["indent"]))
    bom, lines = _read_raw(path)
    _verify_raw(lines, prefix, at["key"], at["line"])
    return path, bom, lines, at, entries


def _words(text, what):
    if not isinstance(text, str):
        raise Refused("%s must be text" % what)
    if "\n" in text or "\r" in text:
        raise Refused("%s must be one line" % what)
    words = text.strip()
    if not words:
        raise Refused("%s are empty" % what)
    if MIDDOT in words:
        raise Refused("%s carry the middle dot; separate with `, `, ` / ` or ` - `" % what)
    if clean(words, 300) != words or any(unicodedata.category(c) in ("Cf", "Cs", "Co", "Cn") for c in words):
        raise Refused("%s carry control or invisible characters, or run over 300 characters" % what)
    if "](" in words:
        raise Refused("%s carry a link; the record and promote operations write those" % what)
    hashes = len(words) - len(words.lstrip("#"))
    if words[:3] in ("```", "~~~") or words.startswith(("<!--", ">")) or (0 < hashes <= 6 and words[hashes:hashes + 1] in ("", " ")):
        raise Refused("%s open a block (fence, comment, quote or heading); write plain words" % what)
    if any(w.lower() in FORMER_STAGES for w in bracket_words(words)):
        raise Refused("%s carry a former stage word in brackets; the stage is read from the links" % what)
    if todo_md.has_stamp_or_token(words):
        raise Refused("%s carry a stamp or a priority token; the operation writes those" % what)
    if any(todo_md.id_start(w) for w in words.split()):
        raise Refused("%s carry an id; the writer mints it" % what)
    return words


ID_ROOM = 300 - (todo_md.ID_DIGITS + 2)  # the words of a new line: the id and its space count in the 300


def _now_ms():
    return int(time.time() * 1000)


def mint_id(taken):
    """A new line's id: `@` and the clock in Unix milliseconds, one millisecond later until no line of the file has it."""
    ms = _now_ms()
    while "@%d" % ms in taken:
        ms += 1
    return "@%d" % ms


def _room(words):
    if len(words) > ID_ROOM:
        raise Refused("the words run over %d characters; the line's id counts in the 300" % ID_ROOM)


def _line_room(text):
    """An entry line's text after its box, without the stamp and the priority token, holds within 300 characters."""
    if len(todo_md.strip_lead(text)) > 300:
        raise Refused("the line would run over 300 characters")


def _guard(root, path, old, new, span):
    """Refuse a rewrite that adds a finding the file did not have, or leaves an error on a line it wrote (`span`: line numbers)."""
    rp = rel(path, root)
    base = Counter(f["code"] for f in _findings_of(root, rp, old))
    items = _findings_of(root, rp, new)
    if Counter(f["code"] for f in items) - base or any(f["severity"] == "error" and f["file"] == rp and f["line"] in span for f in items):
        raise Refused("the write would leave a line that breaks the backlog grammar")


def _code(text):
    """`text` as one inline code span: a fence one backtick longer than its longest run, padded when it starts or ends with a backtick."""
    run = best = 0
    for c in text:
        run = run + 1 if c == "`" else 0
        best = max(best, run)
    fence = "`" * (best + 1)
    pad = " " if text.startswith("`") or text.endswith("`") else ""
    return fence + pad + text + pad + fence


def _fill_template(tpl, kind, entry, notes, section, rel_backlog):
    """idea.md from the template: the head lines filled, the item and the notes carried word for word."""
    out, sec, wrote_notes, wrote_item = [], "", False, False
    if not any(ln.startswith("## 1.") for ln in tpl):
        raise Refused("the template has no `## 1. The item` section")
    head_line = "[%s] %s" % (entry["date"], entry["text"])
    for ln in tpl:
        body = ln.rstrip("\r")
        if body.startswith("# ") and not out:
            out.append("# %s: %s" % (KIND_TITLE[kind], entry["text"]))
            continue
        if body.startswith("## "):
            sec = body[3:]
            out.append(body)
            continue
        if body.startswith("**Date:**"):
            out.append("**Date:** %s" % entry["date"])
        elif body.startswith("**Status:**"):
            out.append("**Status:** %s" % KIND_STATUS[kind])
        elif body.startswith("**Scope of this doc:**"):
            out.append("**Scope of this doc:** carried over from %s word for word" % rel_backlog)
        elif body.startswith("**Backlog entry:**"):
            out.append("**Backlog entry:** `%s` section `# %s` - %s" % (rel_backlog, section, _code(head_line)))
        elif sec.startswith("1.") and body.strip() and not wrote_item:
            out.append(entry["text"])
            wrote_item = True
        elif sec.startswith("2.") and body.lstrip().startswith("- "):
            if not wrote_notes:
                out.extend("- %s" % n for n in notes) if notes else out.append(body)
                wrote_notes = True
        else:
            out.append(body)
    if notes and not wrote_notes:
        raise Refused("the template's `## 2.` section has no `- ` line to carry the notes")
    return out


def record(root, key, line, kind, slug):
    """Move an entry's notes into a new record folder `backlog/<stamp>-<kind>-<slug>/idea.md` built from
    `backlog/template-idea.md`; the entry keeps its first line and one link sub-bullet. (ok, message)."""
    made = None
    try:
        root = os.path.realpath(os.path.abspath(_text(root, "the root", 1000)))
        if not isinstance(kind, str) or kind not in RECORD_KINDS:
            raise Refused("the kind `%s` is not idea, handover or bugfix" % clean(str(kind), 20).replace("\n", " "))
        slug = _exact(slug, "the slug", todo_md.is_slug)
        path, bom, lines, at, entries = _backlog_entry(root, key, line)
        if at["record"] or at["feature"] or any(lk["kind"] in ("record", "feature") for lk in at["links"]):
            raise Refused("the entry at line %d already carries a record or feature link" % at["line"])
        if at["state"] == "done":
            raise Refused("the entry at line %d is done; a done entry is ticked in place" % at["line"])
        if not at["stamp"]:
            raise Refused("the entry at line %d has no `[YYYY-MM-DD]` stamp; the folder name needs the day" % at["line"])
        name = "%s-%s-%s" % (at["stamp"], kind, slug)
        bdir = os.path.join(os.path.dirname(path), "backlog")
        tpl_path = os.path.join(bdir, "template-idea.md")
        if not os.path.isfile(tpl_path):
            raise Refused("no template %s" % rel(tpl_path, root))
        tpl_path = _inside(tpl_path, _docs_home(root))
        folder = os.path.join(bdir, name)
        if os.path.lexists(folder):
            raise Refused("the record folder %s exists" % rel(folder, root))
        if len(_block_lines(lines, at)) != len(at["sub_bullets"]):
            raise Refused("the entry's block holds more than its sub-bullets; fix the file first")
        _block_last(entries, [e for e in entries if e.get("parent") is None], at, lines)
        _, tpl = _read_raw(tpl_path)
        notes = [_raw_sub(lines, sb) for sb in at["sub_bullets"]]  # the file's own bytes, never the reader's capped text
        rel_backlog = rel(path, root)
        idea = _fill_template(tpl, kind, dict(at, text=_raw_text(lines, at)), notes, at["section"], rel_backlog)
        cr, terminated = _eol(lines)
        ind = " " * (at["indent"] + 2)
        link = "%s- [%s](backlog/%s/idea.md)" % (ind, name, name)
        first = at["line"]
        last = max([first] + [sb["line"] for sb in at["sub_bullets"]])
        was = list(lines)
        lines[first:last] = [link]
        _inside(bdir, _docs_home(root))
        os.mkdir(folder)
        made = folder
        with open(os.path.join(folder, "idea.md"), "w", encoding="utf-8", newline="") as fh:
            fh.write("\n".join(idea).rstrip("\n") + "\n")
        _guard(root, path, was, lines, (first, first + 1))
        _write_raw(path, bom, _apply_eol(lines, cr, terminated))
        made = None
        return True, "wrote %s:%d: the notes moved to %s; the entry keeps its first line and the link" % (
            rel_backlog, first, rel(os.path.join(folder, "idea.md"), root))
    except Refused as e:
        return False, "refused: %s" % e
    except (OSError, ValueError, TypeError, KeyError, IndexError) as e:
        return False, "refused: %s" % clean("%s: %s" % (type(e).__name__, e), 200)
    finally:
        if made:  # the backlog write failed after the folder was made: take the new folder back out
            for f in os.listdir(made):
                os.unlink(os.path.join(made, f))
            os.rmdir(made)


def _raw_sub(lines, sb):
    sp = todo_md.sub_split(lines[sb["line"] - 1].rstrip("\r"))
    if not sp:
        raise Refused("line %d is not a sub-bullet" % sb["line"])
    return sp[1]


def _raw_text(lines, at):
    """The entry's text from the file's own line: after the box, without the stamp and the token."""
    return todo_md.raw_text(lines[at["line"] - 1])


def _block_lines(lines, at):
    """The raw lines after the entry line that belong to its block (deeper indent, up to a blank line
    or a line at the entry's own depth or less)."""
    out = []
    for raw in lines[at["line"]:]:
        body = raw.rstrip("\r")
        if not body.strip():
            break
        if len(body) - len(body.lstrip(" ")) <= at["indent"]:
            break
        out.append(body)
    return out


def _stamp_of(today):
    """The `YYMMDD` stamp of a `YYYY-MM-DD` day of the calendar."""
    day = _exact(today, "the date", todo_md.is_day)
    try:
        datetime.date(int(day[:4]), int(day[5:7]), int(day[8:10]))
    except ValueError:
        raise Refused("the date `%s` is no day of the calendar" % today)
    return day[2:4] + day[5:7] + day[8:10]


def _entry_line(today, words, tokens=()):
    """The one place an entry line is composed: the open box, the stamp, the words, then any trailing tokens."""
    return " ".join(["- [ ] [%s]" % today, words] + list(tokens))


def add(root, section, topic, subtopic, text, today, notes=None):
    """Append one open, stamped entry, with at most two note sub-bullets, at the end of a section, a topic
    or a subtopic that exists. (ok, message, written): the message names the new entry's key and line, `written` is {key, line} (None on a refusal)."""
    try:
        root = os.path.realpath(os.path.abspath(_text(root, "the root", 1000)))
        section = _words(section, "the section")
        topic = None if topic is None else _words(topic, "the topic")
        subtopic = None if subtopic is None else _words(subtopic, "the subtopic")
        if subtopic is not None and topic is None:
            raise Refused("a subtopic is named with its topic: add --topic")
        words = _words(text, "the words")
        _room(words)
        notes = [_words(nt, "the note") for nt in (notes or [])]
        if len(notes) > 2:
            raise Refused("%d notes; an entry carries at most two sub-bullets" % len(notes))
        stamp = _stamp_of(today)
        bl = read_backlog(root, docs_root_of(root), Findings())  # a backlog write reads no todo file
        if not bl["exists"]:
            raise Refused("no backlog file at %s" % bl["path"])
        secs = [s for s in bl["sections"] if s["title"] == section]
        if len(secs) != 1:
            raise Refused("%s sections titled `%s`; name one that exists once" % ("no" if not secs else len(secs), section))
        box, where = secs[0], "section `%s`" % section
        if topic is None:
            if box["topics"]:
                raise Refused("section `%s` holds topics; name the topic with --topic" % section)
        else:
            tps = [t for t in box["topics"] if t["title"] == topic]
            if len(tps) != 1:
                raise Refused("%s topics titled `%s` in section `%s`" % ("no" if not tps else len(tps), topic, section))
            box, where = tps[0], "topic `%s` of section `%s`" % (topic, section)
            if subtopic is None:
                if box["subtopics"]:
                    raise Refused("topic `%s` holds subtopics; name the subtopic with --subtopic" % topic)
            else:
                us = [u for u in box["subtopics"] if u["title"] == subtopic]
                if len(us) != 1:
                    raise Refused("%s subtopics titled `%s` in topic `%s`" % ("no" if not us else len(us), subtopic, topic))
                box, where = us[0], "subtopic `%s` of topic `%s`" % (subtopic, topic)
        key = stable_key("backlog", "[%s] %s" % (today, words))
        if any(e["key"] == key for e in bl["entries"]):
            raise Refused("an entry with these words is already in the backlog (key %s)" % key)
        ident = mint_id({e["id"] for e in bl["entries"]})
        path = _inside(os.path.join(root, bl["path"]), _docs_home(root))
        bom, lines = _read_raw(path)
        top = [e for e in box["entries"] if e.get("parent") is None]
        if top:
            last = top[-1]
            _verify_raw(lines, "backlog", last["key"], last["line"])
            after = _block_last(bl["entries"], [e for e in bl["entries"] if e.get("parent") is None], last, lines)
        else:
            after = box["line"]
            while after < len(lines) and todo_md.rule_line(lines[after].rstrip("\r")):
                after += 1
            if after < len(lines) - 1 and not lines[after].strip():
                after += 1
        cr, terminated = _eol(lines)
        new = [_entry_line(today, words, [ident])] + ["  - %s" % nt for nt in notes]
        old = list(lines)
        lines[after:after] = new
        _guard(root, path, old, lines, range(after + 1, after + len(new) + 1))
        _write_raw(path, bom, _apply_eol(lines, cr, terminated))
        return True, "wrote %s:%d: a new open entry in %s; key %s line %d" % (rel(path, root), after + 1, where, key, after + 1), {"key": key, "line": after + 1}
    except Refused as e:
        return False, "refused: %s" % e, None
    except (OSError, ValueError, TypeError, KeyError, IndexError) as e:
        return False, "refused: %s" % clean("%s: %s" % (type(e).__name__, e), 200), None


EDIT_OPS = ("text", "note", "note-add", "note-del", "tag-add", "tag-del", "restore", "restore-note")
LINE_CAP = 1000  # a whole entry line, tags and token included


def _is_tag(word):
    return len(word) > 1 and bool(take_tags(word)[0])


def _still_reads(line, expected):
    """True while the file's line is the text the editor was shown."""
    return line.rstrip("\r") == expected


def _entry_parts(text):
    """(lead words: the stamp and the priority token, the other words, the trailing id token) of an entry's text."""
    words = todo_md.words_of(text)
    ident = words.pop() if len(words) > 1 and todo_md.is_id(words[-1]) else ""
    n = len(todo_md.lead_spans(" ".join(words)))
    return words[:n], words[n:], ident


def strip_id(text):
    """(the text without its trailing minted id token, the token): the sheet edits the first and never shows the second."""
    i = text.rfind(" ")
    return (text[:i], text[i + 1:]) if i > 0 and todo_md.is_id(text[i + 1:]) else (text, "")


def _compose(pre, words):
    line = pre + " ".join(w for w in words if w)
    _line_room(line[len(pre):])
    return line


def _edit_entry(op, body, text):
    """The entry line after a text or tag operation: its box, stamp, token and trailing id kept."""
    bx = todo_md.box_of(body)
    pre = body[:bx[4]]
    lead, rest, ident = _entry_parts(bx[2])
    if op == "text":
        words = _words(text, "the words").split()
        if any(todo_md.id_start(w) for w in words):
            raise Refused("the words carry an id token; the board writes those")
        if not any(not _is_tag(w) for w in words):
            raise Refused("the words are only tags; the entry needs words of its own")
        typed = {w for w in words if _is_tag(w)}
        return _compose(pre, lead + words + [w for w in rest if _is_tag(w) and w not in typed] + [ident])
    tag = _text(text, "the tag", 60)
    if take_tags("#" + tag)[0] != [tag]:
        raise Refused("`%s` is not a tag: a letter first, then letters, digits, `-` or `_`" % clean(tag, 40))
    if op == "tag-add":
        if "#" + tag in rest:
            raise Refused("the entry already has the tag `%s`" % tag)
        return _compose(pre, lead + rest + ["#" + tag, ident])
    if "#" + tag not in rest:
        raise Refused("the entry has no tag `%s`" % tag)
    return _compose(pre, lead + [w for w in rest if w != "#" + tag] + [ident])


def edit(root, op, line, expected, text=None, depth=None):
    """Replace line `line` of the backlog if it still reads `expected`, by one operation: `text` (the entry's words),
    `note` (a note's words), `note-add` (a note of `depth` after the entry's or a note's last line), `note-del`,
    `tag-add`, `tag-del`, and the two Undo forms `restore` (an entry line as it was) and `restore-note` (a removed note,
    after its anchor line). Refused when the line changed or the result breaks the grammar.
    (ok, message, written): `written` is {line, raw} of the line now in the file, None on a refusal."""
    try:
        root = os.path.realpath(os.path.abspath(_text(root, "the root", 1000)))
        if op not in EDIT_OPS:
            raise Refused("the operation `%s` is not one of %s" % (clean(str(op), 20), ", ".join(EDIT_OPS)))
        line = _int(line, "the line")
        if not isinstance(expected, str) or len(expected) > LINE_CAP or "\n" in expected:
            raise Refused("the expected line must be one line of text within %d characters" % LINE_CAP)
        bl = read_backlog(root, docs_root_of(root), Findings())
        if not bl["exists"]:
            raise Refused("no backlog file at %s" % bl["path"])
        path = _inside(os.path.join(root, bl["path"]), _docs_home(root))
        bom, lines = _read_raw(path)
        if line < 1 or line > len(lines) or not _still_reads(lines[line - 1], expected):
            raise Refused("stale line: line %d changed in the file since it was read" % line)
        was, cr = _split_cr(lines[line - 1])
        ent = next((e for e in bl["entries"] if e["line"] == line), None)
        sub = next(((e, b) for e in bl["entries"] for b in e["sub_bullets"] if b["line"] == line), None)
        if ent is not None and (ent.get("parent") or ent["indent"] != 0):
            raise Refused("the entry at line %d sits outside the grammar; fix the file first" % line)
        out, at = [], line
        if op in ("text", "tag-add", "tag-del", "restore"):
            if ent is None:
                raise Refused("line %d is not an entry line" % line)
            if op == "restore":
                new = _text(text, "the line", LINE_CAP)
                a, b = todo_md.box_of(new), todo_md.box_of(was)
                if new != text or not a or not b or a[0] != b[0]:
                    raise Refused("the line to restore is not an entry line")
            else:
                new = _edit_entry(op, was, text)
            out = [new]
        elif op in ("note", "note-del"):
            if sub is None:
                raise Refused("line %d is not a note" % line)
            e, b = sub
            if any(lk["kind"] in ("record", "feature") for lk in b["links"]):
                raise Refused("a note that carries the record or feature link is changed by creating the record or scoping the feature")
            if op == "note":
                out = [todo_md.sub_split(was)[0] + "- " + _words(text, "the note")]
            else:
                nxt = e["sub_bullets"][e["sub_bullets"].index(b) + 1:][:1]
                if nxt and nxt[0]["depth"] > b["depth"]:
                    raise Refused("the note has notes under it; remove those first")
        else:
            anchor = ent if ent is not None else (sub[0] if sub else None)
            if anchor is None:
                raise Refused("line %d is neither an entry line nor a note" % line)
            deepest = -1 if ent is not None else sub[1]["depth"]
            if op == "note-add":
                depth = _int(depth, "the depth")
                new = " " * (2 + 2 * depth) + "- " + _words(text, "the note") if 0 <= depth <= deepest + 1 else None
                if new is None:
                    raise Refused("a note sits at depth 0 to %d here, one level under the note above at most" % (deepest + 1))
                if line != anchor["line"] + len(_block_lines(lines, anchor)):
                    raise Refused("a note is added after the last line of the entry")
            else:
                new = _text(text, "the note", LINE_CAP)
                m = todo_md.sub_split(new)
                depth = (len(m[0]) - 2) // 2 if m else -1
                if new != text or not m or (len(m[0]) - 2) % 2 or not 0 <= depth <= deepest + 1:
                    raise Refused("the line to restore is not a note that fits under line %d" % line)
            if depth == 0 and sum(1 for b in anchor["sub_bullets"] if b["depth"] == 0) >= 2:
                raise Refused("an entry carries at most two sub-bullets")
            out = [was, new]
            at = line + 1
        before = Counter(f["code"] for f in _findings_of(root, bl["path"], lines))
        lines[line - 1:line] = [x + cr for x in out]
        if Counter(f["code"] for f in _findings_of(root, bl["path"], lines)) - before:
            raise Refused("the edit would break the backlog grammar")
        cr_all, terminated = _eol(lines)
        _write_raw(path, bom, _apply_eol(lines, cr_all, terminated))
        written = {"line": line - 1, "raw": lines[line - 2].rstrip("\r")} if op == "note-del" else {"line": at, "raw": out[-1]}  # a removal names the line above, where Undo anchors
        return True, "wrote %s:%d: %s" % (rel(path, root), at, op), written
    except Refused as e:
        return False, "refused: %s" % e, None
    except (OSError, ValueError, TypeError, KeyError, IndexError, AttributeError) as e:
        return False, "refused: %s" % clean("%s: %s" % (type(e).__name__, e), 200), None


STATE_MARK = {"open": " ", "wip": "+", "done": "X"}
TODO_EDIT_OPS = ("text", "sub", "sub-add", "sub-del", "restore-sub")


def _todo_open(root, lane, line, expected):
    """(root, the lane's todo tab, its real file path, bom, lines, line) when the file's line still reads `expected`."""
    root = os.path.realpath(os.path.abspath(_text(root, "the root", 1000)))
    lane = _text(lane, "the lane token", 40)
    line = _int(line, "the line")
    if not isinstance(expected, str) or len(expected) > LINE_CAP or "\n" in expected:
        raise Refused("the expected line must be one line of text within %d characters" % LINE_CAP)
    t = next((t for t in read_all(root)["todo"] if t["lane"] == lane), None)
    if t is None:
        raise Refused("no lane `%s` in the registry" % lane)
    if not t["exists"]:
        raise Refused("lane `%s` has no todo file (%s)" % (lane, t["path"]))
    path = _inside(os.path.join(root, t["path"]), _docs_home(os.path.realpath(os.path.join(root, t["root"]))))
    bom, lines = _read_raw(path)
    if line < 1 or line > len(lines) or not _still_reads(lines[line - 1], expected):
        raise Refused("stale line: line %d changed in the file since it was read" % line)
    return root, t, path, bom, lines, line


def _todo_findings(root, t, lines):
    f = Findings()
    todo_md.read_lane(lines, _Ctx(f, t["path"], (), os.path.dirname(os.path.join(root, t["path"])), root, t["lane"]))
    return f.items


def _todo_commit(path, bom, lines, root=None, t=None, old=None):
    """Write `lines`; with `old` (the lines before the edit) a rewrite that adds a finding the file did not have is refused first."""
    if old is not None and Counter(f["code"] for f in _todo_findings(root, t, lines)) - Counter(f["code"] for f in _todo_findings(root, t, old)):
        raise Refused("the edit would break the todo grammar")
    cr_all, terminated = _eol(lines)
    _write_raw(path, bom, _apply_eol(lines, cr_all, terminated))


def todo_state(root, lane, line, expected, state):
    """Set the state of lane `lane`'s todo line `line` (`open`, `wip`, `done`: the box ` `, `+`, `X`) if it still reads
    `expected`; every other byte of the line stays. (ok, message, {line, raw} written, None on a refusal)."""
    try:
        if not isinstance(state, str) or state not in STATE_MARK:
            raise Refused("the state must be one of %s" % ", ".join(STATE_MARK))
        root, t, path, bom, lines, line = _todo_open(root, lane, line, expected)
        ent = next((e for e in t["entries"] if e["line"] == line), None)
        if ent is None:
            raise Refused("line %d is not a todo line" % line)
        if ent["state"] == state:
            raise Refused("the line is already %s" % state)
        body, cr = _split_cr(lines[line - 1])
        bx = todo_md.box_of(body)
        lines[line - 1] = body[:bx[3]] + STATE_MARK[state] + body[bx[3] + 1:] + cr
        _todo_commit(path, bom, lines)
        return True, "wrote %s:%d: state %s" % (rel(path, root), line, state), {"line": line, "raw": lines[line - 1].rstrip("\r")}
    except Refused as e:
        return False, "refused: %s" % e, None
    except (OSError, ValueError, TypeError, KeyError, IndexError, AttributeError) as e:
        return False, "refused: %s" % clean("%s: %s" % (type(e).__name__, e), 200), None


def _sub_words(text):
    words = _words(text, "the sub-item")
    if not todo_md.sub_item_ok(words):
        raise Refused("a sub-item is `in <feature id>`, `adr: ...` or `ref: ...`")
    return words


def todo_edit(root, lane, op, line, expected, text=None):
    """Replace line `line` of lane `lane`'s todo file if it still reads `expected`, by one operation: `text` (the line's
    words; its box, stamp, priority token and trailing id token stay), `sub` (a sub-item's words), `sub-add` (a sub-item
    after the line's last), `sub-del`, and the Undo form `restore-sub` (a removed sub-item, after its anchor line).
    (ok, message, {line, raw} written, None on a refusal)."""
    try:
        if op not in TODO_EDIT_OPS:
            raise Refused("the operation `%s` is not one of %s" % (clean(str(op), 20), ", ".join(TODO_EDIT_OPS)))
        root, t, path, bom, lines, line = _todo_open(root, lane, line, expected)
        old = list(lines)
        was, cr = _split_cr(lines[line - 1])
        ent = next((e for e in t["entries"] if e["line"] == line), None)
        sub = next(((e, b) for e in t["entries"] for b in e["sub_bullets"] if b["line"] == line), None)
        at = line
        if op == "text":
            if ent is None:
                raise Refused("line %d is not a todo line" % line)
            bx = todo_md.box_of(was)
            lead, _rest, ident = _entry_parts(bx[2])
            words = _words(text, "the words").split()
            if any(todo_md.id_start(w) for w in words):
                raise Refused("the words carry an id token; the board writes those")
            lines[line - 1] = _compose(was[:bx[4]], lead + words + [ident]) + cr
        elif op in ("sub", "sub-del"):
            if sub is None or sub[1]["kind"] not in ("in", "adr", "ref"):
                raise Refused("line %d is not an `in`, `adr:` or `ref:` sub-item" % line)
            if op == "sub":
                lines[line - 1] = todo_md.sub_split(was)[0] + "- " + _sub_words(text) + cr
            else:
                del lines[line - 1]
        elif op == "sub-add":
            if ent is None:
                raise Refused("line %d is not a todo line" % line)
            at = max([ent["line"]] + [b["line"] for b in ent["sub_bullets"]]) + 1
            lines.insert(at - 1, " " * (ent["indent"] + 2) + "- " + _sub_words(text) + cr)
        else:
            if ent is None and sub is None:
                raise Refused("line %d is neither a todo line nor a sub-item" % line)
            new = _text(text, "the line", LINE_CAP)
            m = todo_md.sub_split(new)
            if new != text or not m or len(m[0]) % 2 or not todo_md.sub_item_ok(m[1]):
                raise Refused("the line to restore is not a sub-item")
            at = line + 1
            lines.insert(line, new + cr)
        _todo_commit(path, bom, lines, root, t, old)
        written = {"line": line - 1, "raw": lines[line - 2].rstrip("\r")} if op == "sub-del" else {"line": at, "raw": lines[at - 1].rstrip("\r")}  # a removal names the line above, where Undo anchors
        return True, "wrote %s:%d: %s" % (rel(path, root), at, op), written
    except Refused as e:
        return False, "refused: %s" % e, None
    except (OSError, ValueError, TypeError, KeyError, IndexError, AttributeError) as e:
        return False, "refused: %s" % clean("%s: %s" % (type(e).__name__, e), 200), None


def _findings_of(root, rp, lines):
    f = Findings()
    read_backlog(root, docs_root_of(root), f, path=os.path.join(root, rp), lines=lines)
    return f.items


def supersede(root, key, line, text, today):
    """Replace the entry's line in place: open, stamped `today`, the new words, then
    ` - supersedes [<old stamp>]` (or the old text quoted when it has no stamp). (ok, message)."""
    try:
        root = os.path.realpath(os.path.abspath(_text(root, "the root", 1000)))
        words = _words(text, "the words")
        _room(words)
        stamp = _stamp_of(today)
        path, bom, lines, at, entries = _backlog_entry(root, key, line)
        if at["state"] == "done":
            raise Refused("the entry at line %d is done; a done entry is ticked in place, never replaced" % at["line"])
        if at["feature"]:
            raise Refused("the entry at line %d is promoted (%s); its feature owns it" % (at["line"], at["feature"]))
        old = ("[%s]" % at["date"]) if at["stamp"] else ('"%s"' % _raw_text(lines, at))
        body, cr = _split_cr(lines[at["line"] - 1])
        token = (" [#%s]" % at["priority"]) if at["priority"] else ""
        ident = mint_id({e["id"] for e in entries})
        tail = "%s - supersedes %s %s" % (words, old, ident)
        _line_room(tail)
        was = list(lines)
        lines[at["line"] - 1] = "%s- [ ] [%s]%s %s%s" % (" " * at["indent"], today, token, tail, cr)
        _guard(root, path, was, lines, (at["line"],))
        _write_raw(path, bom, lines)
        return True, "wrote %s:%d: the entry superseded, it names %s" % (rel(path, root), at["line"], old)
    except Refused as e:
        return False, "refused: %s" % e
    except (OSError, ValueError, TypeError, KeyError, IndexError) as e:
        return False, "refused: %s" % clean("%s: %s" % (type(e).__name__, e), 200)


def _lane_paths(root, token, feature):
    """(the folder a write must stay in, the feature's working dir, the feature spec path) for a registry
    token: the lane root, or the real folder of its declared docs root when the working dir lies under it."""
    try:
        rows = said_status.read_lane_registry(root)[0]
    except Exception as e:
        raise Refused("the registry of CLAUDE.md is refused: %s" % clean(str(e), 120))
    hit = [lr for t, lr in rows if t == token]
    if not hit:
        raise Refused("no lane `%s` in the registry of %s" % (token, "CLAUDE.md"))
    lane_root = os.path.realpath(os.path.join(root, hit[0]))
    try:
        with open(os.path.join(lane_root, "CLAUDE.md"), encoding="utf-8-sig", errors="replace") as fh:
            block = said_status.lane_block_lines(fh.read())
    except OSError:
        block = None
    if not block:
        raise Refused("lane `%s` has no `## Lane` block" % token)
    out = []
    for axis in ("working", "feature-spec"):
        v = said_status._block_key(block, axis)
        if not v or "<id>" not in v or v.startswith(("/", "~")) or ".." in v.split("/"):
            raise Refused("lane `%s` declares no usable SAID.%s (a path holding <id>)" % (token, axis))
        out.append(os.path.join(lane_root, v.replace("<id>", feature)))
    within = lane_root
    docs = docs_root_of(lane_root)
    if said_status._block_key(block, "working").startswith(docs):  # a symlinked docs root is the lane's own choice
        within = os.path.realpath(os.path.join(lane_root, docs.rstrip("/")))
    return within, out[0].rstrip("/"), out[1]


def promote(root, key, line, target_lane, feature, apply=False):
    """Promote an entry's record to a feature of a registry lane: the record folder moves whole into the
    lane's working dir for the feature, the entry goes `[+]` and its link becomes the feature link.
    Without `apply` it prints the plan and writes nothing. (ok, message)."""
    moved, made, wdir, spec_was = None, [], "", None  # spec_was: (path, bom, lines) of the spec before its priority write
    try:
        root = os.path.realpath(os.path.abspath(_text(root, "the root", 1000)))
        token = _text(target_lane, "the lane token", 40)
        feature = _exact(feature, "the feature id", todo_md.is_feature_id)
        lane_root, wdir, spec = _lane_paths(root, token, feature)
        path, bom, lines, at, entries = _backlog_entry(root, key, line)
        read = list(lines)
        if at["state"] == "done":
            raise Refused("the entry at line %d is done" % at["line"])
        if at["feature"]:
            raise Refused("the entry at line %d is already promoted (%s)" % (at["line"], at["feature"]))
        sb = next((s for s in at["sub_bullets"] if any(lk["kind"] == "record" for lk in s["links"])), None)
        src = os.path.join(os.path.dirname(path), "backlog", at["record"]) if at["record"] else None
        if sb is None or not src or not todo_md.record_folder(at["record"]) or at["record"] in (".", "..") \
                or "/" in at["record"] or "\\" in at["record"] or not os.path.isdir(src):
            raise Refused("the entry at line %d has no record folder to promote" % at["line"])
        src = _inside(src, _docs_home(root))
        dst = os.path.join(wdir, at["record"])
        if os.path.lexists(dst):
            raise Refused("the destination %s exists" % rel(dst, root))
        _within_before_write(wdir, lane_root)  # the deepest existing ancestor lies in the lane, before any write
        href = os.path.relpath(spec, os.path.dirname(path)).replace(os.sep, "/")
        rel_b = rel(path, root)
        plan = ["plan: move %s/ -> %s/" % (rel(src, root), rel(dst, root)),
                "plan: %s:%d [%s] -> [+], the link becomes [%s](%s)" % (rel_b, at["line"], at["state_char"], feature, href)]
        carry = at["priority"] if at["priority"] in PRIORITY_LETTERS else ""
        if carry and os.path.isfile(spec):
            spec_path = _spec_in(spec, lane_root)
            plan.append("plan: %s head gets **Priority:** [#%s]" % (rel(spec_path, root), carry))
        elif carry:
            plan.append("note: no spec at %s yet; set its priority there once it exists" % rel(spec, root))
        if not apply:
            plan.append("confirm: run the same command with --apply")
            return True, "\n".join(plan)
        cr, terminated = _eol(lines)
        body, c = _split_cr(lines[at["line"] - 1])
        bx = todo_md.box_of(body)
        lines[at["line"] - 1] = body[:bx[3]] + "+" + body[bx[3] + 1:] + c
        sbody, sc = _split_cr(lines[sb["line"] - 1])
        ind = sbody[:len(sbody) - len(sbody.lstrip(" "))]
        lines[sb["line"] - 1] = "%s- [%s](%s)%s" % (ind, feature, href, sc)
        if carry and os.path.isfile(spec):  # first, so a refusal here moves nothing; the rollback puts the spec back
            spec_bom, spec_lines = _read_raw(spec_path)
            ok, msg = set_feature_priority(spec_path, lane_root, carry)
            if not ok:
                raise Refused(msg[len("refused: "):] if msg.startswith("refused: ") else msg)
            spec_was = (spec_path, spec_bom, spec_lines)
        _makedirs_tracked(wdir, made)
        _inside(wdir, lane_root)
        os.rename(src, dst)
        moved = (dst, src)
        if _read_raw(path)[1] != read:  # the backlog is rewritten whole: a change made since it was read must not be lost
            raise Refused("the backlog changed while the promotion ran; nothing was kept")
        _write_raw(path, bom, _apply_eol(lines, cr, terminated))
        moved, made, spec_was = None, [], None
        return True, "\n".join(["wrote " + p[len("plan: "):] if p.startswith("plan: ") else p for p in plan])
    except Refused as e:
        return False, "refused: %s" % e
    except (OSError, ValueError, TypeError, KeyError, IndexError) as e:
        return False, "refused: %s" % clean("%s: %s" % (type(e).__name__, e), 200)
    finally:
        undo = []  # each step on its own, so one failing does not skip the others
        if moved:  # the backlog write failed after the move: the folder goes back
            undo.append(lambda: os.rename(moved[0], moved[1]))
        undo += [lambda d=d: os.rmdir(d) for d in reversed(made)]  # and the directories this call made go, deepest first
        if spec_was:  # and the spec goes back to the bytes it had
            undo.append(lambda: _write_raw(*spec_was))
        for step in undo:
            try:
                step()
            except (OSError, Refused) as e:
                print("refused: the rollback did not finish (%s); check %s" % (clean(str(e), 120), rel(wdir, root)))


# ---------------------------------------------------------------- migrate

STAGE_TAGS = {"entry": "", "idea": "", "owed reply": "", "bugfix": "", "promoted": "", "done": "",
              "scoped": "scoped", "wip only": "wip", "resolved": "resolved"}  # a former stage word: dropped (derived now) or a tag
P_LETTERS = {"P1": "A", "P2": "B"}
PREVIEW_CAP = 40


def _former_stamp(word, line):
    """`20YY-MM-DD` for a former stamp word `@YYMMDD`, None for any other word; a stamp that is no day is refused."""
    if len(word) != 7 or word[0] != "@" or not word[1:].isdigit():
        return None
    try:
        day = datetime.date(2000 + int(word[1:3]), int(word[3:5]), int(word[5:7]))
    except ValueError:
        raise Refused("line %d: the stamp `[%s]` is no calendar day" % (line, word))
    return day.isoformat()


def _stamps_only(text, line):
    """`text` with each former stamp rewritten (the todo target's whole job)."""
    out, pos = [], 0
    for a, b, w in bracket_spans(text):
        day = _former_stamp(w, line)
        if day:
            out.append(text[pos:a] + "[" + day + "]")
            pos = b
    return "".join(out) + text[pos:]


def _entry_text(text, line):
    """One entry's text in grammar v2: stamps as dates, the P scale as A/B, a former stage word dropped or a tag."""
    out, pos, letter, tags, cut, lead_to = [], 0, "", [], False, 0
    for a, b, w in bracket_spans(text):
        day = _former_stamp(w, line)
        in_lead = not text[lead_to:a].strip()  # only brackets stand between the start and this one
        if day:
            out.append(text[pos:a] + "[" + day + "]")
        elif len(w) == 2 and w[0] in "Pp" and w[1].isdigit():
            if w.upper() not in P_LETTERS:
                raise Refused("line %d: the priority `[%s]` has no A, B or C (only P1 and P2 map)" % (line, w))
            if letter:
                raise Refused("line %d: two former priorities" % line)
            letter, cut = P_LETTERS[w.upper()], True
            out.append(text[pos:a])
        elif w.lower() in STAGE_TAGS and in_lead:
            if STAGE_TAGS[w.lower()]:
                tags.append(STAGE_TAGS[w.lower()])
            cut = True
            out.append(text[pos:a])
        else:
            continue
        pos = b
        lead_to = b if in_lead else lead_to
    out.append(text[pos:])
    new = "".join(out)
    if not cut and new == text:
        return text
    new = " ".join(todo_md.words_of(new))
    if letter:
        if todo_md.find_token(new):
            raise Refused("line %d: a former priority beside a `[#...]` priority" % line)
        sm = todo_md.find_stamp(new)
        new = (new[:sm[1]] + " [#%s]" % letter + new[sm[1]:]) if sm else "[#%s] %s" % (letter, new)
    have = new.split()
    for t in tags:
        if "#" + t not in have:
            new += " #" + t
            have.append("#" + t)
    return new.strip()


def _assign_ids(lines):
    """`lines` with an id on every entry line outside a fence: an id there stays, the former letter form
    (`@B` or `@T` and 13 digits) is written bare, the others get the migration time, one millisecond later on a clash."""
    entry = []
    fence, taken = False, set()
    for i, ln in enumerate(lines):
        if ln.startswith("```"):
            fence = not fence
        bx = None if fence else todo_md.box_of(ln)
        if bx and bx[1] in STATES:
            entry.append(i)
            taken.add(todo_md.trailing_id(ln))
    out = list(lines)
    for i in entry:
        if todo_md.trailing_id(out[i]):
            continue
        head, _, last = out[i].rpartition(" ")
        bare = "@" + last[2:]
        if last[:2] in ("@B", "@T") and todo_md.is_id(bare) and bare not in taken:
            out[i] = head + " " + bare
            taken.add(bare)
        else:
            ident = mint_id(taken)
            taken.add(ident)
            out[i] = out[i].rstrip() + " " + ident
    return out


def _front_end(lines):
    """The index of the closing `---` of the frontmatter; the opening one is line 1."""
    for i in range(1, len(lines)):
        if lines[i].rstrip("\r").strip() == "---":
            return i
    return None


def _migrate_front(bodies, end):
    """The frontmatter (line, original line number) pairs in grammar v2: the former top-level key renamed `targets`, the `structure` block dropped,
    a rejected former `format` line replaced (the caller writes the current one first)."""
    front, has_targets, has_former, in_block = [], False, False, False
    for i in range(1, end):
        ln = bodies[i]
        if in_block and (not ln.strip() or ln.startswith((" ", "\t"))):
            continue
        in_block = False
        if ln.strip() and not ln.startswith((" ", "\t")) and not ln.lstrip().startswith("#"):
            key, _, val = ln.partition(":")
            low = key.strip().lower()
            if low == "format":
                if val.strip() == FORMAT:
                    raise Refused("the file is already at %s; migrate runs once" % FORMAT)
                if val.strip() not in FORMER_FORMATS:
                    raise Refused("line %d: a `format` key of `%s`; the former grammar has none" % (i + 1, clean(val.strip(), 40)))
                continue
            if low == "structure":
                in_block = True
                continue
            has_targets = has_targets or low == "targets"
            if low in FORMER_KEYS:
                has_former = True
                if val.strip():
                    raise Refused("line %d: `%s` carries a value; it is a map of `<name>: external`" % (i + 1, low))
                if has_targets:
                    raise Refused("line %d: `%s` beside `targets:`; merge them by hand" % (i + 1, low))
                ln = "targets:"
        front.append((ln, i + 1))
    if has_former and has_targets:
        raise Refused("the former top-level key beside `targets:` in the frontmatter; merge them by hand")
    return front


def _migrate_backlog_lines(bodies):
    """(new body lines, original line number per new line) for a former-grammar backlog; refuses what it cannot map."""
    end = _front_end(bodies)
    if not bodies or bodies[0].strip() != "---" or end is None:
        raise Refused("the file has no frontmatter, so it is not a backlog file (a todo file is `migrate todo`)")
    out, origin = ["---", "format: " + FORMAT], [1, 0]
    for ln, n in _migrate_front(bodies, end):
        out.append(ln)
        origin.append(n)
    out.append("---")
    origin.append(end + 1)
    in_group, in_fence = False, False
    for i in range(end + 1, len(bodies)):
        ln, n = bodies[i], i + 1
        new = ln
        if ln.startswith("```"):
            in_fence = not in_fence
        elif not in_fence:
            box = todo_md.box_of(ln)
            grp = todo_md.group_of(ln)
            if ln.startswith("# ") and ln[2:].strip():
                in_group = False
            elif grp:
                new, in_group = "## " + grp, True
            elif box:
                indent, st, text = box[:3]
                if in_group and indent != 2:
                    raise Refused("line %d: an entry at %d spaces under a group; entries sit 2 spaces under it (a column-0 entry after a group would join it)" % (n, indent))
                body = _entry_text(text, n)
                if in_group or body != text:
                    new = "- [%s] %s" % (st, body) if in_group or box[0] == 0 else ln[:len(ln) - len(ln.lstrip())] + "- [%s] %s" % (st, body)
            elif in_group and todo_md.sub_split(ln) and ln.startswith("  "):
                new = ln[2:]
        out.append(new)
        origin.append(n)
    return out, origin


def _migrate_todo_lines(bodies):
    """(new body lines, original line number per new line) for a todo file: the frontmatter with the version key,
    the todo format comment dropped, the stamps rewritten."""
    if bodies and bodies[0].strip() == "---":
        end = _front_end(bodies)
        if end is not None and any(ln.partition(":")[0].strip() == "format" and ln.partition(":")[2].strip() == FORMAT for ln in bodies[1:end]):
            raise Refused("the file is already at %s; migrate runs once" % FORMAT)
        raise Refused("the file has frontmatter, so it is a backlog file (that is `migrate backlog`)")
    out, origin, in_fence, i = ["---", "format: " + FORMAT, "---"], [0, 0, 0], False, 0
    while i < len(bodies):
        ln = bodies[i]
        if not in_fence and ln.startswith("<!-- todo format"):
            start = i
            while i < len(bodies) and "-->" not in bodies[i]:
                i += 1
            if i == len(bodies):
                raise Refused("line %d: the todo format comment never closes; close it by hand, then migrate" % (start + 1))
            i += 1
            if i < len(bodies) and not bodies[i].strip():
                i += 1
            continue
        if ln.startswith("```"):
            in_fence = not in_fence
        out.append(ln if in_fence else _stamps_only(ln, i + 1))
        origin.append(i + 1)
        i += 1
    return out, origin


def migrate(root, target, lane=None, file=None, apply=False, full=False):
    """Rewrite a former-grammar backlog (target `backlog`) to grammar v2, or a todo file's stamps (target `todo`).
    Without `apply` it prints the plan and writes nothing. (ok, message)."""
    try:
        root = os.path.realpath(os.path.abspath(_text(root, "the root", 1000)))
        if target not in ("backlog", "todo"):
            raise Refused("the target is `backlog` or `todo`")
        if file is not None:
            if not os.path.isabs(file) or os.path.realpath(file) != file:
                raise Refused("--file must be an absolute, physical path (no symlink in it)")
            path = _inside(file, root)
        elif target == "backlog":
            path = os.path.join(root, docs_root_of(root), "backlog.md")
        else:
            if lane is None:
                raise Refused("`migrate todo` needs --lane <token> or --file <path>")
            row = next((r for r in lane_rows(root) if r[0] == _text(lane, "the lane token", 40)), None)
            if row is None:
                raise Refused("no lane `%s` in the registry" % lane)
            path = os.path.join(row[1], docs_root_of(row[1]), "todo.md")
        if not os.path.isfile(path):
            raise Refused("no %s file at %s" % (target, rel(path, root)))
        path = _inside(path, root)
        bom, lines = _read_raw(path)
        bodies = [_split_cr(ln)[0] for ln in lines]
        new, origin = (_migrate_backlog_lines if target == "backlog" else _migrate_todo_lines)(bodies)
        new = _assign_ids(new)
        if target == "todo":
            ctx = lambda: _Ctx(Findings(), rel(path, root), (), os.path.dirname(path), root, "x")
            if len(todo_md.read_lane(bodies, ctx())[3]) != len(todo_md.read_lane(new, ctx())[3]):
                raise Refused("the migration would change the number of todo lines; fix the file by hand, then migrate")
        if target == "backlog":
            findings = Findings()
            read_backlog(root, docs_root_of(root), findings, path=path, lines=new)
            bad = sorted((f["line"], f["message"]) for f in findings.items if f["severity"] == "error" and f["file"] == rel(path, root))
            if bad:
                n = (origin[bad[0][0] - 1] if 0 < bad[0][0] <= len(origin) else 0) or bad[0][0]
                raise Refused("line %d: %s; fix it by hand, then migrate" % (n, bad[0][1]))
        rp = rel(path, root)
        changes = ["line %d: %s -> %s" % (origin[j], clean(bodies[origin[j] - 1], 100), clean(new[j], 100))
                   for j in range(len(new)) if origin[j] and bodies[origin[j] - 1] != new[j]]
        kept = set(origin)
        removed = ["line %d: %s -> (removed)" % (n, clean(bodies[n - 1], 100)) for n in range(1, len(bodies) + 1) if n not in kept]
        plan = ["plan: migrate %s (%s)" % (rp, "grammar %s, `format` key added, `structure` block dropped, ids" % FORMAT if target == "backlog" else "`format` key added, todo format comment dropped, stamps, ids")]
        shown = removed + changes  # every deletion is listed first, so a cap never hides one before a change
        plan += ["plan: %s" % c for c in (shown if full else shown[:PREVIEW_CAP])]
        if not full and len(shown) > PREVIEW_CAP:
            hid_r = max(0, len(removed) - PREVIEW_CAP)
            plan.append("plan: ... not shown: %d changed lines, %d removed lines (--full prints the whole plan)" % (len(shown) - PREVIEW_CAP - hid_r, hid_r))
        if not apply:
            plan.append("confirm: run the same command with --apply")
            return True, "\n".join(plan)
        ends = [ln[len(b):] for ln, b in zip(lines, bodies)]  # each line keeps its own ending; a new line takes the first one's
        out = [b + (ends[origin[j] - 1] if origin[j] else ends[0]) for j, b in enumerate(new[:-1])] + [new[-1] + ends[-1]]
        _write_raw(path, bom, out)
        return True, "wrote migrate %s: %d lines changed, %d removed%s" % (rp, len(changes), len(removed), ", format " + FORMAT)
    except Refused as e:
        return False, "refused: %s" % e
    except (OSError, ValueError, TypeError, KeyError, IndexError) as e:
        return False, "refused: %s" % clean("%s: %s" % (type(e).__name__, e), 200)


def _within_before_write(path, root):
    """Refuse unless the deepest existing ancestor of `path` resolves inside `root`."""
    probe = path
    while not os.path.lexists(probe):
        parent = os.path.dirname(probe)
        if parent == probe:
            break
        probe = parent
    _inside(probe, root)


def _makedirs_tracked(path, made):
    """os.makedirs that appends each directory it makes to `made`, outermost first, as it goes."""
    todo = []
    probe = path
    while not os.path.lexists(probe):
        todo.append(probe)
        probe = os.path.dirname(probe)
    for d in reversed(todo):
        os.mkdir(d)
        made.append(d)


def main(argv=None):
    try:
        return _main(argv)
    except OSError as e:  # an unreadable file is a refusal, never a traceback
        print("refused: cannot read %s: %s" % (clean(os.path.basename(e.filename or "a file"), 80), clean(e.strerror or type(e).__name__, 80)))
        return 2


def _main(argv=None):
    ap = argparse.ArgumentParser(description="read the backlog file and the registry lanes' todo files by their grammars; "
                                 "`lint` checks the backlog; `set-priority`, `move`, `add`, `record`, `supersede` and `promote` write")
    ap.add_argument("--root", default=".", help="the root whose <docs-root>backlog.md is read (default: the current directory)")
    ap.add_argument("--json", action="store_true", help="print the data as JSON")
    ap.add_argument("--board", choices=["backlog", "todo"], help="print a board's view model (the page's numbers): `backlog`, by stage and by priority; `todo`, one tab per lane with a todo file")
    sub = ap.add_subparsers(dest="cmd")
    sp = sub.add_parser("set-priority", help="write, replace or remove the priority token of an entry line, a todo line or a record head")
    sp.add_argument("--letter", required=True, help="A, B, C, or none to remove")
    sp.add_argument("--key", help="the entry's stable key (from --json)")
    sp.add_argument("--line", type=int, help="the entry's line position (from --json)")
    sp.add_argument("--lane", help="the lane token for a todo line")
    sp.add_argument("--record", help="a record folder name, for the head's **Priority:** line")
    mv = sub.add_parser("move", help="move an entry (with its sub-bullets) within its section, topic or subtopic")
    mv.add_argument("--key", required=True, help="the entry's stable key (from --json)")
    mv.add_argument("--line", type=int, required=True, help="the entry's line position (from --json)")
    mv.add_argument("--lane", help="the lane token for a todo entry")
    mv.add_argument("--to", type=int, help="the destination position, 1-based, among the container's top-level entries")
    mv.add_argument("--before", help="the key of the entry to move ahead of (same section, topic and subtopic)")
    li = sub.add_parser("lint", help="check the backlog against its frontmatter grammar plus the priority grammar; writes nothing")
    li.add_argument("--json", action="store_true", dest="lint_json", help="print the findings as JSON")
    rc = sub.add_parser("record", help="move an entry's notes into a new record folder from the template")
    rc.add_argument("--key", required=True, help="the entry's stable key (from --json)")
    rc.add_argument("--line", required=True, help="the entry's line position (from --json)")
    rc.add_argument("--kind", required=True, help="idea, handover or bugfix")
    rc.add_argument("--slug", required=True, help="the folder slug, lowercase words joined by -")
    ad = sub.add_parser("add", help="append one open, stamped entry at the end of a section, a topic or a subtopic")
    ad.add_argument("--section", required=True, help="the H1 section's title")
    ad.add_argument("--topic", help="the `##` topic's title, when the section holds topics")
    ad.add_argument("--subtopic", help="the `###` subtopic's title, when the topic holds subtopics")
    ad.add_argument("--text", required=True, help="the entry's words, one line")
    ad.add_argument("--today", required=True, help="the day, YYYY-MM-DD (the stamp)")
    ad.add_argument("--note", action="append", default=[], help="a note sub-bullet, one line; at most two")
    ss = sub.add_parser("supersede", help="replace an entry's line with one that names what it supersedes")
    ss.add_argument("--key", required=True, help="the entry's stable key (from --json)")
    ss.add_argument("--line", required=True, help="the entry's line position (from --json)")
    ss.add_argument("--text", required=True, help="the new words, one line")
    ss.add_argument("--today", required=True, help="the day, YYYY-MM-DD (the new stamp)")
    pr = sub.add_parser("promote", help="move an entry's record into a registry lane's working dir for a feature; plan without --apply")
    pr.add_argument("--key", required=True, help="the entry's stable key (from --json)")
    pr.add_argument("--line", required=True, help="the entry's line position (from --json)")
    pr.add_argument("--target-lane", required=True, help="the registry token of the lane that owns the feature")
    pr.add_argument("--feature", required=True, help="the feature id, <PREFIX>-<NN>")
    pr.add_argument("--apply", action="store_true", help="write; without it the plan is printed and nothing is written")
    mg = sub.add_parser("migrate", help="rewrite a former-grammar backlog to grammar v2 (target backlog), or a todo file's stamps (target todo); plan without --apply")
    mg.add_argument("target", choices=["backlog", "todo"], help="the file's kind; a file of the other kind is refused")
    mg.add_argument("--lane", help="the registry lane token whose todo file the todo target rewrites")
    mg.add_argument("--file", help="an absolute, physical path under the root, instead of the default file")
    mg.add_argument("--apply", action="store_true", help="write; without it the plan is printed and nothing is written")
    mg.add_argument("--full", action="store_true", help="print the whole plan, not the first 40 rows")
    a = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if a.cmd == "set-priority":
        ok, msg = set_priority(a.root, a.letter, key=a.key, line=a.line, lane=a.lane, record=a.record)
        print(msg)
        return 0 if ok else 2
    if a.cmd == "move":
        ok, msg = move_entry(a.root, a.key, a.line, lane=a.lane, to=a.to, before=a.before)
        print(msg)
        return 0 if ok else 2
    if a.cmd == "lint":
        data, code = lint(a.root)
        print(json.dumps(data, indent=1, ensure_ascii=True) if (a.json or a.lint_json) else render_lint(data))
        return code
    if a.cmd == "migrate":
        ok, msg = migrate(a.root, a.target, lane=a.lane, file=a.file, apply=a.apply, full=a.full)
        print(msg)
        return 0 if ok else 2
    if a.cmd in ("add", "record", "supersede", "promote"):
        if a.cmd == "add":
            ok, msg, _ = add(a.root, a.section, a.topic, a.subtopic, a.text, a.today, a.note)
        elif a.cmd == "record":
            ok, msg = record(a.root, a.key, a.line, a.kind, a.slug)
        elif a.cmd == "supersede":
            ok, msg = supersede(a.root, a.key, a.line, a.text, a.today)
        else:
            ok, msg = promote(a.root, a.key, a.line, a.target_lane, a.feature, apply=a.apply)
        print(msg)
        return 0 if ok else 2
    data = read_all(a.root)
    if a.board == "backlog":
        view = board_view(data)
        print(json.dumps(view, indent=1, ensure_ascii=True) if a.json else render_board_text(view))
        return 0
    if a.board == "todo":
        view = todo_view(data)
        print(json.dumps(view, indent=1, ensure_ascii=True) if a.json else render_todo_text(view))
        return 0
    if a.json:
        print(json.dumps(data, indent=1, ensure_ascii=True))
    else:
        print(render_text(data))
    return 0

if __name__ == "__main__":
    sys.exit(main())
