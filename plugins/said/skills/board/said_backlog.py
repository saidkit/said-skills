#!/usr/bin/env python3
"""said_backlog.py - the backlog and todo reader beside the analyzer (stdlib only).

Reads two things by their own grammars and reports them as text or `--json`:

* the backlog, one fixed file `<docs-root>backlog.md` at the given root, plus its record folders
  `<docs-root>backlog/<YYMMDD>-<kind>-<slug>/idea.md`;
* each registry lane's todo list, `<lane root>/<docs-root>todo.md` (no argument names either file).

The backlog grammar (stated in the file's own frontmatter): an H1 section `# <title>` over an `=` rule;
inside it, optional numbered groups `N. <title>` one level deep; an entry is one line
`- [<state>] [@YYMMDD] <text>` at column 0 (no group) or two spaces under a group, state ` ` open,
`+` in progress, `X` done; a priority token `[#A]`, `[#B]` or `[#C]` follows the stamp; at most two
sub-bullets, two spaces deeper, one of them the record link `[<slug>](backlog/<slug>/idea.md)` or,
once promoted, the feature link `[<FEAT-NN>](<path to the feature spec>)`.

The todo grammar (stated in the file's header comment): `# <section>` over an `=` rule, an optional
`## <sub-section>` over a `-` rule, checkbox entries at column 0 with nested boxes under them, and
sub-bullets `- in ...`, `- adr: ...`, `- ref: ...`.

A line that breaks its grammar is a finding (file, line, code, message), never a crash; every text
field is stripped of control characters and capped, so the page, `--cli` and `--json` carry the same
bounded plain text. Roots are made absolute before anything derives from them.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import said_status  # noqa: E402  the registry and lane-block readers live in the analyzer

TEXT_CAP = 500
STATES = {" ": "open", "+": "wip", "X": "done", "x": "done"}
PRIORITY_LETTERS = ("A", "B", "C")
RECORD_KINDS = ("idea", "handover", "bugfix")

BOX_RE = re.compile(r"^(\s*)- \[(.)\]\s?(.*)$")
STAMP_RE = re.compile(r"\[@(\d{6})\]")
TOKEN_RE = re.compile(r"\[#([A-Za-z0-9])\]")
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
GROUP_RE = re.compile(r"^(\d{1,6})\.\s+(.*\S)\s*$")
H1_RE = re.compile(r"^# (.*\S)\s*$")
H2_RE = re.compile(r"^## (.*\S)\s*$")
RULE_RE = re.compile(r"^(=+|-{4,})\s*$")
SUB_RE = re.compile(r"^(\s+)- (.*)$")
FOLDER_RE = re.compile(r"^(\d{6})-([a-z]+)-(.+)$")
FEATURE_RE = re.compile(r"\b([A-Z]+-\d+)\b")
PRIO_LINE_RE = re.compile(r"^\*\*Priority:\*\*\s*(?:\[#([A-Za-z0-9])\])?\s*$")
STATUS_LINE_RE = re.compile(r"^\*\*Status:\*\*\s*(.*)$")
ISO_RE = re.compile(r"\b(20\d\d-\d\d-\d\d)\b")
MIDDOT = "\u00b7"


BIDI = {0x200E, 0x200F, 0x202A, 0x202B, 0x202C, 0x202D, 0x202E, 0x2066, 0x2067, 0x2068, 0x2069, 0x2028, 0x2029}


def clean(s, cap=TEXT_CAP):
    """Every text field: C0 and C1 control characters, line separators and bidi controls out, length capped."""
    s = "".join(c for c in s if ((ord(c) >= 32 and ord(c) != 127) or c == "\t") and not (0x80 <= ord(c) <= 0x9F) and ord(c) not in BIDI)
    s = s.replace("\t", " ")
    return s[:cap]


def stamp_date(stamp):
    return "20%s-%s-%s" % (stamp[:2], stamp[2:4], stamp[4:6]) if stamp else ""


def read_lines(path):
    with open(path, encoding="utf-8-sig", errors="replace") as fh:
        return fh.read().split("\n")


def rel(path, root):
    try:
        return os.path.relpath(path, root)
    except ValueError:
        return path


def stable_key(prefix, text):
    core = TOKEN_RE.sub("", STAMP_RE.sub("", text)).replace("**", "")
    core = re.sub(r"\s+", " ", core).strip().lower()
    return "%s:%s" % (prefix, hashlib.sha1(core.encode("utf-8")).hexdigest()[:10])


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

def parse_box(ln):
    """(indent, state char, text) for a checkbox line, else None."""
    m = BOX_RE.match(ln)
    if not m:
        return None
    lead = m.group(1)
    # a tab in the indent is its own finding (the caller reports it); the indent here is the spaces only
    return len(lead.replace("\t", "")), m.group(2), m.group(3)


def split_entry_text(text):
    """stamp, priority letter, token position, clean text (stamp and token removed)."""
    stamp = ""
    sm = STAMP_RE.search(text)
    if sm:
        stamp = sm.group(1)
    letter, pos = "", ""
    tm = TOKEN_RE.search(text)
    if tm:
        letter = tm.group(1)
        pos = "after-stamp" if (not sm or tm.start() > sm.start()) else "before-stamp"
    body = TOKEN_RE.sub("", STAMP_RE.sub("", text, count=1), count=1)
    return stamp, letter, pos, re.sub(r"\s+", " ", body).strip()


def classify_link(label, href, base_dir, root):
    """The link's kind (record, feature, other), whether it resolves, and the slug or feature id."""
    target = href.split("#", 1)[0]
    if re.match(r"^[a-z]+://", href) or not target:
        return {"label": clean(label, 120), "href": clean(href, 300), "kind": "other", "resolves": None, "id": ""}
    tpath = os.path.normpath(os.path.join(base_dir, target))
    exists = os.path.exists(tpath)
    parts = target.replace("\\", "/").split("/")
    kind, ident = "other", ""
    if len(parts) >= 3 and parts[-3] == "backlog" and parts[-1] == "idea.md":
        kind, ident = "record", parts[-2]
    elif "features" in parts and parts[-1].endswith(".md"):
        m = FEATURE_RE.match(parts[-1])
        kind, ident = "feature", (m.group(1) if m else "")
        if not exists and ident:  # a promoted link also passes when the feature's working dir exists
            lane_root = os.path.normpath(os.path.join(os.path.dirname(tpath), "..", ".."))
            wd = os.path.join(lane_root, "docs", "working", ident)
            exists = os.path.isdir(wd)
    return {"label": clean(label, 120), "href": clean(href, 300), "kind": kind, "resolves": exists, "id": ident, "path": tpath}


def read_backlog(root, docs_root, findings):
    path = os.path.join(root, docs_root, "backlog.md")
    out = {"path": rel(path, root), "exists": os.path.isfile(path), "sections": [], "entries": [], "records": []}
    if not out["exists"]:
        return out
    rp = out["path"]
    lines = read_lines(path)
    base_dir = os.path.dirname(path)
    sections, entries = [], []
    section = group = None
    last = None  # the entry open for sub-bullets
    in_fence = in_front = False
    fence_line = 0
    position = 0
    for i, raw in enumerate(lines, 1):
        ln = raw.rstrip("\r")
        if i == 1 and ln.strip() == "---":
            in_front = True
            continue
        if in_front:
            if ln.strip() == "---":
                in_front = False
            continue
        if ln.startswith("```"):
            if not in_fence:
                findings.add(rp, i, "fence", "a fenced block has no place in the backlog grammar")
                fence_line = i
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if MIDDOT in ln:
            findings.add(rp, i, "middle-dot", "the middle-dot separator is banned; use `, `, ` / ` or ` - `")
        if "\t" in ln:
            findings.add(rp, i, "tab-indent", "a tab in the indent; the grammar indents with spaces")
        m = H1_RE.match(ln)
        if m:
            section = {"title": clean(m.group(1), 120), "line": i, "groups": [], "entries": []}
            sections.append(section)
            group, last, position = None, None, 0
            continue
        if RULE_RE.match(ln) or not ln.strip():
            continue
        if H2_RE.match(ln):
            findings.add(rp, i, "h2-heading", "the backlog has no H2; groups are numbered lines")
            continue
        m = GROUP_RE.match(ln)
        if m and section is not None:
            group = {"number": int(m.group(1)), "title": clean(m.group(2), 120), "line": i, "entries": []}
            section["groups"].append(group)
            last, position = None, 0
            continue
        box = parse_box(ln)
        if box:
            indent, st, text = box
            expected = 2 if group is not None else 0
            if "\t" in ln[:len(ln) - len(ln.lstrip())]:
                indent = expected  # the tab was reported above; it does not also misplace the entry
            if indent > expected and last is not None:
                findings.add(rp, i, "nesting-depth", "a box nested under an entry; the backlog nests one level only")
                entry = make_entry(rp, i, indent, st, text, section, group, position, base_dir, root, findings)
                entry["parent"] = last["key"]
                entries.append(entry)
                (group or section)["entries"].append(entry)
                continue
            if indent != expected:
                findings.add(rp, i, "entry-indent", "an entry sits at %d spaces; %d expected here" % (indent, expected))
            if section is None:
                findings.add(rp, i, "entry-outside-section", "an entry before the first H1 section")
                section = {"title": "", "line": i, "groups": [], "entries": []}
                sections.append(section)
            position += 1
            entry = make_entry(rp, i, indent, st, text, section, group, position, base_dir, root, findings)
            entries.append(entry)
            (group or section)["entries"].append(entry)
            last = entry
            continue
        m = SUB_RE.match(ln)
        if m and last is not None:
            sub_text = m.group(2)
            if STAMP_RE.search(sub_text):
                findings.add(rp, i, "stamp-in-sub-bullet", "a stamp in a sub-bullet; the stamp belongs on the entry line")
            links = [classify_link(a, b, base_dir, root) for a, b in LINK_RE.findall(sub_text)]
            for lk in links:
                if lk["kind"] == "record":
                    if lk["label"] != lk["id"]:
                        findings.add(rp, i, "link-label-not-slug", "the link label `%s` is not the record slug `%s`" % (lk["label"], lk["id"]))
                    last["record"] = lk["id"]
                if lk["kind"] == "feature" and lk["id"]:
                    last["feature"] = lk["id"]
                    last["feature_path"] = lk.get("path", "")
                if lk["resolves"] is False:
                    findings.add(rp, i, "link-target-missing", "the link target `%s` does not exist" % lk["href"])
            last["sub_bullets"].append({"line": i, "text": clean(sub_text), "links": links})
            last["links"].extend(links)
            if len(last["sub_bullets"]) == 3:
                findings.add(rp, last["line"], "sub-bullets-over-two", "an entry carries more than two sub-bullets")
            continue
        if ln.strip():
            findings.add(rp, i, "stray-line", "a line that is neither a heading, a group, an entry nor a sub-bullet")
    if in_front:
        findings.add(rp, 1, "frontmatter-unclosed", "the frontmatter opened on line 1 never closes")
    if in_fence:
        findings.add(rp, fence_line, "fence-unclosed", "a fence opened here never closes")
    out["sections"] = sections
    out["entries"] = entries
    out["records"] = read_records(root, docs_root, findings)
    by_folder = {r["folder"]: r for r in out["records"]}
    for e in entries:
        e["stage"] = entry_stage(e, by_folder.get(e.get("record")))
        e["trail"] = entry_trail(e, by_folder.get(e.get("record")), root)
    return out


def make_entry(rp, line, indent, st, text, section, group, position, base_dir, root, findings):
    if st not in STATES:
        findings.add(rp, line, "state-unknown", "the state `[%s]` is not ` `, `+` or `X`" % st)
    elif st == "x":
        findings.add(rp, line, "state-lowercase", "the done state is `[X]`; lowercase `[x]` read as done")
    stamp, letter, pos, body = split_entry_text(text)
    if not stamp:
        findings.add(rp, line, "stamp-missing", "no `[@YYMMDD]` stamp (a legacy entry is kept)", severity="warn")
    if letter and letter not in PRIORITY_LETTERS:
        findings.add(rp, line, "priority-letter", "the priority letter `%s` is outside A, B, C" % letter)
    if pos == "before-stamp":
        findings.add(rp, line, "token-before-stamp", "the priority token precedes the stamp; it follows it")
    entry = {
        "key": stable_key("backlog", text), "line": line, "indent": indent, "position": position,
        "section": section["title"] if section else "", "group": group["title"] if group else "",
        "state": STATES.get(st, "unknown"), "state_char": st, "stamp": stamp, "date": stamp_date(stamp),
        "priority": letter if letter in PRIORITY_LETTERS else "", "priority_pos": pos,
        "text": clean(body), "sub_bullets": [], "links": [], "record": None, "feature": None, "feature_path": "",
        "parent": None, "stage": "", "trail": [],
    }
    return entry


def read_records(root, docs_root, findings):
    bdir = os.path.join(root, docs_root, "backlog")
    records = []
    if not os.path.isdir(bdir):
        return records
    for d in sorted(os.listdir(bdir)):
        p = os.path.join(bdir, d)
        if not os.path.isdir(p) or d.startswith("."):
            continue
        fm = FOLDER_RE.match(d)
        if not fm:
            continue  # a folder outside the record grammar (a generator, a map) is not a record
        rec = {"folder": clean(d, 200), "path": clean(rel(os.path.join(p, "idea.md"), root), 300), "stamp": fm.group(1), "date": stamp_date(fm.group(1)),
               "kind": clean(fm.group(2), 40), "slug": clean(fm.group(3), 160), "exists": os.path.isfile(os.path.join(p, "idea.md")),
               "title": "", "status": "", "status_class": "unrecorded", "priority": "", "priority_line": None,
               "resolution": "", "feature_line": "", "feature": None, "stage": "", "trail": []}
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
                m = PRIO_LINE_RE.match(s)
                if m and rec["priority_line"] is None:
                    rec["priority_line"] = i
                    letter = m.group(1) or ""
                    if letter and letter not in PRIORITY_LETTERS:
                        findings.add(rec["path"], i, "priority-letter", "the priority letter `%s` is outside A, B, C" % letter)
                    rec["priority"] = letter if letter in PRIORITY_LETTERS else ""
                m = STATUS_LINE_RE.match(s)
                if m and not rec["status"]:
                    rec["status"] = clean(m.group(1), 160)
            if ln.startswith("## "):
                sec = ln[3:].strip()
                continue
            if sec.startswith("Resolution") and s and not s.startswith("<") and not rec["resolution"]:
                rec["resolution"] = clean(s, 200)
            if sec.startswith("4. Feature") and s.startswith("-") and not rec["feature_line"]:
                rec["feature_line"] = clean(s[1:].strip(), 200)
                fm2 = FEATURE_RE.search(rec["feature_line"])
                if fm2 and not rec["feature_line"].lower().startswith("none"):
                    rec["feature"] = fm2.group(1)
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
        rec["stage"] = {"resolved": "Resolved", "idea": "Idea", "owed": "Owed reply", "in-scope": "Scoped",
                        "bugfix": "Bugfix"}.get(rec["status_class"], "Wip only")
        records.append(rec)
    return records


def entry_stage(e, rec):
    if e["state"] == "done":
        return "Done"
    if e.get("feature"):
        return "Promoted"
    if rec:
        return rec["stage"]
    return "Entry"


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
    rp = out["path"]
    lines = read_lines(path)
    base_dir = os.path.dirname(path)
    section = subsection = None
    stack = []  # (indent, entry) for nesting
    in_fence = in_comment = False
    comment_line = fence_line = 0
    for i, raw in enumerate(lines, 1):
        ln = raw.rstrip("\r")
        s = ln.strip()
        if in_comment:
            if "-->" in ln:
                in_comment = False
            continue
        if s.startswith("<!--"):
            if "-->" not in ln:
                in_comment, comment_line = True, i
            continue
        if ln.startswith("```"):
            if not in_fence:
                fence_line = i
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if MIDDOT in ln and s.startswith(MIDDOT):
            findings.add(rp, i, "middle-dot-bullet", "a sub-bullet drawn with a middle dot; use `- `")
        if "\t" in ln:
            findings.add(rp, i, "tab-indent", "a tab in the indent; the outline indents with spaces")
        m = H1_RE.match(ln)
        if m:
            section = {"title": clean(m.group(1), 120), "line": i, "subsections": [], "entries": []}
            out["sections"].append(section)
            subsection, stack = None, []
            continue
        m = H2_RE.match(ln)
        if m:
            subsection = {"title": clean(m.group(1), 120), "line": i, "entries": []}
            if section is None:
                section = {"title": "", "line": i, "subsections": [], "entries": []}
                out["sections"].append(section)
            section["subsections"].append(subsection)
            stack = []
            continue
        if RULE_RE.match(ln) or not s:
            continue
        box = parse_box(ln)
        if box:
            indent, st, text = box
            if st not in STATES:
                findings.add(rp, i, "state-unknown", "the state `[%s]` is not ` `, `+` or `X`" % st)
            stamp, letter, pos, body = split_entry_text(text)
            if letter and letter not in PRIORITY_LETTERS:
                findings.add(rp, i, "priority-letter", "the priority letter `%s` is outside A, B, C" % letter)
            if not stamp:
                findings.add(rp, i, "stamp-missing", "no `[@YYMMDD]` stamp", severity="warn")
            while stack and stack[-1][0] >= indent:
                stack.pop()
            parent = stack[-1][1] if stack else None
            entry = {"key": stable_key("todo-" + token, text), "line": i, "indent": indent,
                     "section": section["title"] if section else "", "subsection": subsection["title"] if subsection else "",
                     "state": STATES.get(st, "unknown"), "state_char": st, "stamp": stamp, "date": stamp_date(stamp),
                     "priority": letter if letter in PRIORITY_LETTERS else "", "priority_pos": pos, "text": clean(body),
                     "sub_bullets": [], "links": [], "parent": parent["key"] if parent else None,
                     "position": len((subsection or section or {"entries": []})["entries"]) + 1 if parent is None else 0}
            out["entries"].append(entry)
            if parent is None and (subsection or section):
                (subsection or section)["entries"].append(entry)
            stack.append((indent, entry))
            continue
        m = SUB_RE.match(ln)
        if m and stack:
            sub_indent = len(m.group(1).replace("\t", ""))
            while len(stack) > 1 and stack[-1][0] >= sub_indent:
                stack.pop()
            owner = stack[-1][1]
            sub_text = m.group(2)
            kind = "note"
            km = re.match(r"^(in|adr|ref)\b:?", sub_text)
            if km:
                kind = km.group(1)
            links = [classify_link(a, b, base_dir, root) for a, b in LINK_RE.findall(sub_text)]
            owner["sub_bullets"].append({"line": i, "kind": kind, "text": clean(sub_text), "links": links})
            owner["links"].extend(links)
            continue
        if s.startswith(MIDDOT) and stack:
            owner = stack[-1][1]
            owner["sub_bullets"].append({"line": i, "kind": "note", "text": clean(s[1:].strip()), "links": []})
            continue
        if s:
            findings.add(rp, i, "stray-line", "a line that is neither a heading, an entry nor a sub-bullet")
    if in_comment:
        findings.add(rp, comment_line, "comment-unclosed", "a comment opened here never closes")
    if in_fence:
        findings.add(rp, fence_line, "fence-unclosed", "a fence opened here never closes")
    return out


# ---------------------------------------------------------------- the whole read

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
        own = sec["entries"]
        out.append("  # %s  (%d entries, %d groups)" % (sec["title"], len(own) + sum(len(g["entries"]) for g in sec["groups"]), len(sec["groups"])))
        for g in sec["groups"]:
            out.append("    %d. %s  (%d)" % (g["number"], g["title"], len(g["entries"])))
            for e in g["entries"]:
                out.append("      %s" % entry_line(e))
        for e in own:
            out.append("    %s" % entry_line(e))
    if bl["records"]:
        out.append("  records: %d" % len(bl["records"]))
        for r in bl["records"]:
            out.append("    %s  %s  %s" % (r["folder"], r["stage"], ("[#%s]" % r["priority"]) if r["priority"] else ""))
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
    return "%s %s%s%s %s" % (mark, ("[@%s] " % e["stamp"]) if e["stamp"] else "", prio, e["text"][:80], ("-> " + e["feature"]) if e.get("feature") else "")


# ---------------------------------------------------------------- the backlog board's view model
#
# One view model for the board page and `--board backlog` (text and `--json`), so the page's numbers are
# the terminal's: every entry once by stage and once by priority, each row with its record trail and the
# feature it was promoted into. Paths are root-relative; no absolute path leaves the reader.

STAGE_ORDER = ("Entry", "Idea", "Owed reply", "Scoped", "Bugfix", "Wip only", "Promoted", "Resolved", "Done")
PRIORITY_ORDER = ("A", "B", "C", "none")


def board_row(e):
    return {"key": e["key"], "line": e["line"], "state": e["state"], "stamp": e["stamp"], "date": e["date"],
            "position": 0 if e.get("parent") else e.get("position") or 0,
            "priority": e["priority"], "section": e["section"], "group": e["group"], "text": e["text"],
            "stage": e["stage"], "feature": e.get("feature") or "", "record": e.get("record") or "",
            "trail": [{"kind": t["kind"], "path": t["path"], "exists": t["exists"], "date": t.get("date") or ""} for t in e["trail"]],
            "notes": [b["text"] for b in e["sub_bullets"]]}


def board_view(data):
    bl = data["backlog"]
    rows = [board_row(e) for e in bl["entries"]]
    stages = [s for s in STAGE_ORDER if any(r["stage"] == s for r in rows)]
    stages += sorted({r["stage"] for r in rows} - set(STAGE_ORDER))
    by_stage = [{"stage": s, "rows": [r for r in rows if r["stage"] == s]} for s in stages]
    by_priority = [{"priority": p, "rows": [r for r in rows if (r["priority"] or "none") == p]} for p in PRIORITY_ORDER]
    by_priority = [g for g in by_priority if g["rows"]]
    return {"board": "backlog", "path": bl["path"], "exists": bl["exists"],
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
    return "%s %s%s%s%s" % (mark, ("[@%s] " % r["stamp"]) if r["stamp"] else "", prio, r["text"][:80],
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
            "text": e["text"], "parent_line": parent_line,
            "sub_bullets": [{"kind": b["kind"], "text": b["text"]} for b in e["sub_bullets"]]}


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
        out.append("  %s: %s  %d entries (open %d, wip %d, done %d, unknown %d; A %d, B %d, C %d, none %d)"
                   % (t["lane"], t["path"], tc["entries"], tc["open"], tc["wip"], tc["done"], tc["unknown"], tc["A"], tc["B"], tc["C"], tc["none"]))
        for r in t["rows"]:
            mark = {"open": "[ ]", "wip": "[+]", "done": "[X]"}.get(r["state"], "[?]")
            prio = ("[#%s] " % r["priority"]) if r["priority"] else ""
            out.append("    %s%s %s%s%s" % ("  " * r["depth"], mark, ("[@%s] " % r["stamp"]) if r["stamp"] else "", prio, r["text"][:80]))
    return "\n".join(out)


# ---------------------------------------------------------------- the writers
#
# Two writes, one code path for the page routes and the manage skill: a priority token on an entry
# line, a todo line or a record head, and a manual order (a line move within an entry's section and
# group, its sub-bullets and nested boxes carried). A write names its target by the reader's stable
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


def _docs_home(owner):
    """The real folder of `owner`'s declared docs root: every backlog, record and todo write stays in it
    (a symlinked docs root is the owner's own choice)."""
    return os.path.realpath(os.path.join(owner, docs_root_of(owner).rstrip("/")))


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
            for g in sec["groups"]:
                containers.append(("group `%s` of section `%s`" % (g["title"], sec["title"]), g["entries"]))
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
    box = parse_box(lines[line - 1].rstrip("\r"))
    if not box or stable_key(prefix, box[2]) != key:
        raise Refused("stale position: the file changed since it was read; line %d no longer holds `%s`" % (line, key))


def _container_of(containers, entry):
    for name, members in containers:
        if any(m["line"] == entry["line"] for m in members):
            return name, [m for m in members if m.get("parent") is None]
    return None, []


def _block_last(entries, top, entry):
    """The 1-based last line of the entry's block as the reader attached it: its sub-bullets, its
    nested boxes and theirs; refused when another top-level entry sits inside that span."""
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
    return last


def _token_line(line, letter):
    """The box line with its priority token written, replaced or removed; every other byte kept."""
    body, cr = _split_cr(line)
    m = BOX_RE.match(body)
    if not m:
        raise Refused("line is not a checkbox entry")
    pre, text = body[:m.start(3)], body[m.start(3):]
    tm = TOKEN_RE.search(text)
    if tm:
        a, b = tm.span()
        if b < len(text) and text[b] == " ":
            b += 1
        elif a > 0 and text[a - 1] == " ":
            a -= 1
        text = text[:a] + text[b:]
    if letter:
        sm = STAMP_RE.search(text)
        if sm:
            text = text[:sm.end()] + " [#%s]" % letter + text[sm.end():]
        else:
            text = "[#%s]%s%s" % (letter, " " if text else "", text)
        if not pre.endswith((" ", "\t")):
            pre += " "
    return pre + text + cr


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
    if not FOLDER_RE.match(folder) or "/" in folder or "\\" in folder or folder in (".", ".."):
        raise Refused("`%s` is not a record folder name (<YYMMDD>-<kind>-<slug>)" % folder)
    path = os.path.join(root, docs_root_of(root), "backlog", folder, "idea.md")
    if not os.path.isfile(path):
        raise Refused("no record %s" % rel(path, root))
    path = _inside(path, _docs_home(root))
    bom, lines = _read_raw(path)
    cr, terminated = _eol(lines)
    head = min(40, len(lines))
    pl = next((j for j in range(head) if PRIO_LINE_RE.match(lines[j].rstrip("\r").strip())), None)
    new = ("**Priority:** [#%s]" % letter) if letter else None
    if pl is not None:
        if new:
            if lines[pl].rstrip("\r").strip() == new:
                return "same %s already %s" % (rel(path, root), letter)
            lines[pl] = new + cr
        else:
            del lines[pl]
    elif new:
        st = next((j for j in range(head) if STATUS_LINE_RE.match(lines[j].rstrip("\r").strip())), None)
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


def move_entry(root, key, line, lane=None, to=None, before=None):
    """Move the entry `key` at `line` (with `lane` for a todo entry) to position `to` (1-based) among
    the top-level entries of its own section and group, or ahead of the entry `before` (a key in the
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
                    raise Refused("`%s` is outside the entry's %s; an entry moves within its own section and group" % (before, name))
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
        last = {e["line"]: _block_last(entries, top, e) for e in top}
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

SLUG_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*", re.ASCII)
FEATURE_ID_RE = re.compile(r"[A-Z]+-[0-9]+(?:-[A-Za-z0-9]+)*", re.ASCII)
TODAY_RE = re.compile(r"(20[0-9][0-9])-([0-9][0-9])-([0-9][0-9])", re.ASCII)
ARG_CAP = {"the slug": 60, "the feature id": 40, "the kind": 20, "the date": 10}


def _exact(value, what, grammar):
    """The argument as given, fullmatched by its ASCII grammar and within its length: never stripped,
    cut or cleaned into shape first."""
    if not isinstance(value, str):
        raise Refused("%s must be text" % what)
    if len(value) > ARG_CAP[what] or not grammar.fullmatch(value):
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
    if at["indent"] != (2 if at["group"] else 0):
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
    if STAMP_RE.search(words) or TOKEN_RE.search(words):
        raise Refused("%s carry a stamp or a priority token; the operation writes those" % what)
    return words


def _fill_template(tpl, kind, entry, notes, section, rel_backlog):
    """idea.md from the template: the head lines filled, the item and the notes carried word for word."""
    out, sec, wrote_notes, wrote_item = [], "", False, False
    if not any(ln.startswith("## 1.") for ln in tpl):
        raise Refused("the template has no `## 1. The item` section")
    head_line = "[@%s] %s" % (entry["stamp"], entry["text"])
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
            out.append("**Backlog entry:** `%s` section `# %s` - `%s`" % (rel_backlog, section, head_line))
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
        slug = _exact(slug, "the slug", SLUG_RE)
        path, bom, lines, at, entries = _backlog_entry(root, key, line)
        if at["record"] or at["feature"] or any(lk["kind"] in ("record", "feature") for lk in at["links"]):
            raise Refused("the entry at line %d already carries a record or feature link" % at["line"])
        if at["state"] == "done":
            raise Refused("the entry at line %d is done; a done entry is ticked in place" % at["line"])
        if not at["stamp"]:
            raise Refused("the entry at line %d has no `[@YYMMDD]` stamp; the folder name needs the day" % at["line"])
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
        _, tpl = _read_raw(tpl_path)
        notes = [_raw_sub(lines, sb) for sb in at["sub_bullets"]]  # the file's own bytes, never the reader's capped text
        rel_backlog = rel(path, root)
        idea = _fill_template(tpl, kind, at, notes, at["section"], rel_backlog)
        cr, terminated = _eol(lines)
        ind = " " * (at["indent"] + 2)
        link = "%s- [%s](backlog/%s/idea.md)" % (ind, name, name)
        first = at["line"]
        last = max([first] + [sb["line"] for sb in at["sub_bullets"]])
        lines[first:last] = [link]
        _inside(bdir, _docs_home(root))
        os.mkdir(folder)
        made = folder
        with open(os.path.join(folder, "idea.md"), "w", encoding="utf-8", newline="") as fh:
            fh.write("\n".join(idea).rstrip("\n") + "\n")
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
    body = lines[sb["line"] - 1].rstrip("\r")
    m = SUB_RE.match(body)
    if not m:
        raise Refused("line %d is not a sub-bullet" % sb["line"])
    return m.group(2)


def _raw_text(lines, at):
    """The entry's text from the file's own line: after the box, without the stamp and the token."""
    body = lines[at["line"] - 1].rstrip("\r")
    m = BOX_RE.match(body)
    text = TOKEN_RE.sub("", STAMP_RE.sub("", m.group(3), count=1), count=1)
    return re.sub(r" {2,}", " ", text).strip(" ")


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
    m = TODAY_RE.fullmatch(_exact(today, "the date", TODAY_RE))
    try:
        datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        raise Refused("the date `%s` is no day of the calendar" % today)
    return m.group(1)[2:] + m.group(2) + m.group(3)


def add(root, section, group, text, today, notes=None):
    """Append one open, stamped entry, with at most two note sub-bullets, at the end of a section or of
    one of its groups. (ok, message); the message names the new entry's key and line."""
    try:
        root = os.path.realpath(os.path.abspath(_text(root, "the root", 1000)))
        section = _words(section, "the section")
        group = None if group is None else _words(group, "the group")
        words = _words(text, "the words")
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
        sec = secs[0]
        if group is None:
            if sec["groups"]:
                raise Refused("section `%s` holds groups; name the group with --group" % section)
            box, at_line, indent = sec, sec["line"], 0
        else:
            gs = [g for g in sec["groups"] if g["title"] == group]
            if len(gs) != 1:
                raise Refused("%s groups titled `%s` in section `%s`" % ("no" if not gs else len(gs), group, section))
            box, at_line, indent = gs[0], gs[0]["line"], 2
        key = stable_key("backlog", "[@%s] %s" % (stamp, words))
        if any(e["key"] == key for e in bl["entries"]):
            raise Refused("an entry with these words is already in the backlog (key %s)" % key)
        path = _inside(os.path.join(root, bl["path"]), _docs_home(root))
        bom, lines = _read_raw(path)
        top = [e for e in box["entries"] if e.get("parent") is None]
        if top:
            last = top[-1]
            _verify_raw(lines, "backlog", last["key"], last["line"])
            after = last["line"] + len(_block_lines(lines, last))
        else:
            after = at_line
            while after < len(lines) and RULE_RE.match(lines[after].rstrip("\r")):
                after += 1
        cr, terminated = _eol(lines)
        new = ["%s- [ ] [@%s] %s" % (" " * indent, stamp, words)] + ["%s- %s" % (" " * (indent + 2), nt) for nt in notes]
        lines[after:after] = new
        _write_raw(path, bom, _apply_eol(lines, cr, terminated))
        return True, "wrote %s:%d: a new open entry in %s; key %s line %d" % (
            rel(path, root), after + 1, ("group `%s` of section `%s`" % (group, section)) if group else "section `%s`" % section, key, after + 1)
    except Refused as e:
        return False, "refused: %s" % e
    except (OSError, ValueError, TypeError, KeyError, IndexError) as e:
        return False, "refused: %s" % clean("%s: %s" % (type(e).__name__, e), 200)


def supersede(root, key, line, text, today):
    """Replace the entry's line in place: open, stamped `today`, the new words, then
    ` - supersedes [@<old stamp>]` (or the old text quoted when it has no stamp). (ok, message)."""
    try:
        root = os.path.realpath(os.path.abspath(_text(root, "the root", 1000)))
        words = _words(text, "the words")
        stamp = _stamp_of(today)
        path, bom, lines, at, entries = _backlog_entry(root, key, line)
        if at["state"] == "done":
            raise Refused("the entry at line %d is done; a done entry is ticked in place, never replaced" % at["line"])
        if at["feature"]:
            raise Refused("the entry at line %d is promoted (%s); its feature owns it" % (at["line"], at["feature"]))
        old = ("[@%s]" % at["stamp"]) if at["stamp"] else ('"%s"' % _raw_text(lines, at))
        body, cr = _split_cr(lines[at["line"] - 1])
        token = (" [#%s]" % at["priority"]) if at["priority"] else ""
        lines[at["line"] - 1] = "%s- [ ] [@%s]%s %s - supersedes %s%s" % (" " * at["indent"], stamp, token, words, old, cr)
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
    moved, made, wdir = None, [], ""
    try:
        root = os.path.realpath(os.path.abspath(_text(root, "the root", 1000)))
        token = _text(target_lane, "the lane token", 40)
        feature = _exact(feature, "the feature id", FEATURE_ID_RE)
        lane_root, wdir, spec = _lane_paths(root, token, feature)
        path, bom, lines, at, entries = _backlog_entry(root, key, line)
        if at["state"] == "done":
            raise Refused("the entry at line %d is done" % at["line"])
        if at["feature"]:
            raise Refused("the entry at line %d is already promoted (%s)" % (at["line"], at["feature"]))
        sb = next((s for s in at["sub_bullets"] if any(lk["kind"] == "record" for lk in s["links"])), None)
        src = os.path.join(os.path.dirname(path), "backlog", at["record"]) if at["record"] else None
        if sb is None or not src or not FOLDER_RE.match(at["record"]) or at["record"] in (".", "..") \
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
        if not apply:
            plan.append("confirm: run the same command with --apply")
            return True, "\n".join(plan)
        cr, terminated = _eol(lines)
        body, c = _split_cr(lines[at["line"] - 1])
        m = BOX_RE.match(body)
        lines[at["line"] - 1] = body[:m.start(2)] + "+" + body[m.end(2):] + c
        sbody, sc = _split_cr(lines[sb["line"] - 1])
        ind = sbody[:len(sbody) - len(sbody.lstrip(" "))]
        lines[sb["line"] - 1] = "%s- [%s](%s)%s" % (ind, feature, href, sc)
        _makedirs_tracked(wdir, made)
        _inside(wdir, lane_root)
        os.rename(src, dst)
        moved = (dst, src)
        _write_raw(path, bom, _apply_eol(lines, cr, terminated))
        moved, made = None, []
        return True, "\n".join(["wrote " + p[len("plan: "):] for p in plan])
    except Refused as e:
        return False, "refused: %s" % e
    except (OSError, ValueError, TypeError, KeyError, IndexError) as e:
        return False, "refused: %s" % clean("%s: %s" % (type(e).__name__, e), 200)
    finally:
        try:
            if moved:  # the backlog write failed after the move: the folder goes back
                os.rename(moved[0], moved[1])
            for d in reversed(made):  # and the directories this call made go, deepest first
                os.rmdir(d)
        except OSError as e:
            print("refused: the rollback did not finish (%s); check %s" % (clean(str(e), 120), rel(wdir, root)))


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
    mv = sub.add_parser("move", help="move an entry (with its sub-bullets) within its section and group")
    mv.add_argument("--key", required=True, help="the entry's stable key (from --json)")
    mv.add_argument("--line", type=int, required=True, help="the entry's line position (from --json)")
    mv.add_argument("--lane", help="the lane token for a todo entry")
    mv.add_argument("--to", type=int, help="the destination position, 1-based, among the container's top-level entries")
    mv.add_argument("--before", help="the key of the entry to move ahead of (same section and group)")
    li = sub.add_parser("lint", help="check the backlog against its frontmatter grammar plus the priority grammar; writes nothing")
    li.add_argument("--json", action="store_true", dest="lint_json", help="print the findings as JSON")
    rc = sub.add_parser("record", help="move an entry's notes into a new record folder from the template")
    rc.add_argument("--key", required=True, help="the entry's stable key (from --json)")
    rc.add_argument("--line", required=True, help="the entry's line position (from --json)")
    rc.add_argument("--kind", required=True, help="idea, handover or bugfix")
    rc.add_argument("--slug", required=True, help="the folder slug, lowercase words joined by -")
    ad = sub.add_parser("add", help="append one open, stamped entry at the end of a section or of one of its groups")
    ad.add_argument("--section", required=True, help="the H1 section's title")
    ad.add_argument("--group", help="the numbered group's title, when the section holds groups")
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
    if a.cmd in ("add", "record", "supersede", "promote"):
        if a.cmd == "add":
            ok, msg = add(a.root, a.section, a.group, a.text, a.today, a.note)
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
