#!/usr/bin/env python3
"""hold-gate -- the deterministic anti-self-default checker for a SAID task.

A task may wait on an operator question by carrying a `**Blocked-on question:** <id>`
marker (a peer of `**Status:**` / `**Priority:**`, authored write-once). While the
question is open the task is held. The hold is lifted by an append-only record in the
task log's `## Lifted holds` section:

  - <id> lifted-by: user@WR-<seconds> -- "<verbatim quote>" -- <date> [supersedes: <prior>]

A lift cites a RULING: the operator's answer as the `ruled` skill records it -- one line in
the work's rulings list (`rulings.md`) and a ruling document that quotes the operator's
message word for word. `WR-<seconds>` is that ruling's id (unix seconds, `-<n>` suffix allowed).

This gate verifies the STRUCTURAL attribution predicate as DATA -- never a
free-form prose judgement. For each marker it returns PASS iff:
  1. a `## Lifted holds` record for <id> exists (the last one wins -- append-only,
     a later record supersedes an earlier one);
  2. its `lifted-by:` actor is exactly the role word `user` (lower case) with an `@WR-<seconds>` ruling id --
     an actor in the deny-list (grant, standing-autonomy, default, assistant, subagent,
     arm) is exactly the blanket-grant self-default this gate exists to catch;
  3. the ruling id is on exactly one line across the rulings lists given, and that line
     is `pending` or `landed` (a `rejected` ruling lifts nothing; a `superseded` one is
     replaced -- the lift cites its successor);
  4. the line links a ruling document (its first evidence path, a `-ruling-` file) that
     opens under the root or the list's folder;
  5. the document's `Provenance:` is `typed` or `dialog` (a ruling `stated-outside` a
     recorded session lifts nothing until the operator restates it in a session), and
     its `Ruled by:` names the same id;
  6. the lift's quote is non-empty and a literal substring of the document's block
     quote under `## The operator's message`;
  7. the lift date is a real calendar date, not more than one day before the ruling's
     own date (the UTC `<time>` in `Ruled by:`; the lift date is local), and, on a Done
     task (state word in any letter case), not after the close (the task's own first
     `**Status:**` date, which must be a calendar date); a Todo task's date bounds
     nothing, so a task reopened in place keeps its earlier lift.
Otherwise HOLD.

THE GRAMMAR -- read by a line parser, never a regular expression. Each line is
classified on its own (a trailing CR is dropped):
  - a task heading: `## ` (two hashes, then a space or tab) and the heading text;
    the heading `## Lifted holds` (any letter case) opens the record section;
  - the marker: `**Blocked-on question:**` (label in any letter case) at the start of
    the line, then one id made of ASCII letters, digits, `_` and `-`; anything else
    after the label makes the marker malformed (HOLD, never unguarded);
  - the status date: a `**Status:**` line whose first `(` opens `YYYY-MM-DD)`;
  - a record: `- `, the id, ` lifted-by: `, the actor, optionally `@` and a ruling id,
    ` -- `, a double-quoted quote with no `"` inside, ` -- `, a `YYYY-MM-DD` date,
    optionally ` [supersedes: <prior>]`. Runs of spaces between parts are allowed.

THE RULINGS LIST AND DOCUMENT -- read by a reader of this script's own (no import from
the plugin that writes them). A list line is `- WR-<10 digits>[-<n>] - <who>, <status>: <text>`
with an optional final ` [<path>, ...]` evidence bracket and, for `landed` / `superseded`,
a ` -> <home or new id>` arrow; other lines are ignored. A list is a file named
`rulings.md` whose first bullet line is an entry; an entry-like line (`-`, spaces, `WR` in
any case) that breaks the grammar makes every lift citing that list HOLD. Paths resolve
from `--root` (default: the current folder), then the list's folder, never outside both
(a symlink is judged by the real path it points to).
A document's header bullets `- Provenance: <word>` and `- Ruled by: <who>, <time>, <id>, ...`
are read once each before its first `## ` heading (headings and fences take up to three
leading spaces, as markdown renders them). The ruling id must be the third part of
`Ruled by:`; its second part dates the ruling. `## The operator's message` is read once, as
its `>` lines; every other part is ignored, whatever its name and whether or not it is present.
A fenced block (three or more ` or ~, closed only by a run of the same character at least as
long) is skipped whole: no header, heading or message inside it counts. The provenance word is
read with trailing periods trimmed (`typed.` is `typed`).
A bullet or the message section given twice makes the document ambiguous: HOLD.

Exit 0 = every markered task PASS (an unmarkered task is unguarded, PASS). Exit 1 =
>=1 HOLD. Exit 2 = config error (nothing to check, a vacuous root, a markered task
with no rulings list, a rulings list that does not open).

Ships inside the said plugin beside the deliver skill that runs it (review-qa),
run natively -- never a vendored per-project copy. Feature-agnostic: pass task
logs + the work's rulings list; it knows nothing about any one feature.
"""
from __future__ import annotations

import argparse
import datetime
import glob
import os
import sys

MARKER_LABEL = "**Blocked-on question:**"
# The one pattern that recognises the retired spellings -- only to HOLD with the rename, never to accept them.
OLD_SPELLINGS = {"marker": "**Blocked-on decision:**", "section": "decisions", "field": "resolved-by:"}
RENAME = ("old spelling -- rename the marker to `**Blocked-on question:**`, the section to "
          "`## Lifted holds`, the field to `lifted-by:`")
STATUS_LABEL = "**Status:**"
SECTION_NAME = "lifted holds"
FIELD_NAME = "lifted-by:"
ID_CHARS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-")
DIGITS = frozenset("0123456789")

# An actor other than the role word `user`. `user` is the only PASS actor; the
# deny-list names the failure set for a precise message (the grant-basis self-default).
DENY = ("grant", "standing-autonomy", "default", "assistant", "subagent", "arm")


class ConfigError(Exception):
    """A misconfiguration -- exit 2, never PASS or HOLD."""


# --- the line parser ----------------------------------------------------------

def is_id(tok):
    return bool(tok) and all(c in ID_CHARS for c in tok)


def is_date(tok):
    return (len(tok) == 10 and tok[4] == "-" and tok[7] == "-"
            and all(tok[i] in DIGITS for i in (0, 1, 2, 3, 5, 6, 8, 9)))


def calendar_date(tok):
    """True for a `YYYY-MM-DD` that names a real day."""
    if not is_date(tok):
        return False
    try:
        datetime.date(int(tok[:4]), int(tok[5:7]), int(tok[8:]))
    except ValueError:
        return False
    return True


def heading2(line):
    """The text of a level-2 heading, else None."""
    if not line.startswith("##") or line.startswith("###"):
        return None
    if line[2:3] not in (" ", "\t"):
        return None
    return line[3:].strip()


def marker_rest(line):
    """The text after the marker label when the line is a marker line, else None."""
    if line[:len(MARKER_LABEL)].lower() != MARKER_LABEL.lower():
        return None
    return line[len(MARKER_LABEL):].strip()


def status_date(line):
    """The `(YYYY-MM-DD)` date of a `**Status:**` line, else None."""
    if not line.startswith(STATUS_LABEL):
        return None
    k = line.find("(", len(STATUS_LABEL))
    if k < 0 or line[k + 11:k + 12] != ")":
        return None
    d = line[k + 1:k + 11]
    return d if is_date(d) else None


class Cursor:
    """A left-to-right reader over one line."""

    def __init__(self, text):
        self.s, self.i = text, 0

    def spaces(self, at_least=0):
        j = self.i
        while self.i < len(self.s) and self.s[self.i] in " \t":
            self.i += 1
        return self.i - j >= at_least

    def word(self, w):
        if self.s.startswith(w, self.i):
            self.i += len(w)
            return True
        return False

    def token(self):
        j = self.i
        while self.i < len(self.s) and self.s[self.i] in ID_CHARS:
            self.i += 1
        return self.s[j:self.i]

    def upto(self, ch):
        k = self.s.find(ch, self.i)
        if k < 0:
            return None
        out, self.i = self.s[self.i:k], k + 1
        return out

    def rest(self):
        return self.s[self.i:]


def record_field(line):
    """(id, field) for a line shaped `- <id> <field>:`, else None -- any field word, old or new."""
    c = Cursor(line)
    if not c.word("-") or not c.spaces(1):
        return None
    rid = c.token()
    if not is_id(rid) or not c.spaces(1):
        return None
    j = c.i
    while c.i < len(c.s) and c.s[c.i] not in " \t":
        c.i += 1
    word = c.s[j:c.i]
    k = word.find(":")  # the field ends at its colon, with or without a space after it
    return (rid, word[:k + 1]) if k > 0 else None


# Look-alike folding for attempted markers: zero-width and soft-hyphen characters dropped, dash
# look-alikes made `-`, the common Cyrillic/Greek homoglyphs of Latin letters made Latin.
_ZERO_WIDTH = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff\u00ad"))
_DASHES = dict.fromkeys(map(ord, "\u2010\u2011\u2012\u2013\u2014\u2015\u2212\ufe63\uff0d"), "-")
_HOMOGLYPHS = str.maketrans("\u0430\u0435\u043e\u0440\u0441\u0443\u0445\u043a\u0456\u0458\u0412\u041a\u041c\u041d\u041e\u0420\u0421\u0422\u0425\u0410\u0415"
                            "\u03bf\u03ba\u03b5\u0391\u0392\u0395\u039a\u039f\u03a4\u0131\u017f",
                            "aeopcyxkijBKMHOPCTXAEokeABEKOTis")


def _fold(line):
    import unicodedata
    t = unicodedata.normalize("NFKC", line).translate(_ZERO_WIDTH).translate(_DASHES)
    return t.translate(_HOMOGLYPHS).casefold()


_DECORATION = " \t>-*+_#`'\"([{]})"


def _undecorate(t):
    """A folded line with its leading decoration removed: indentation, bullets, quotes, brackets,
    emphasis, heading hashes, HTML tags and comments, checkboxes, list letters and numbers."""
    while True:
        before = t
        t = t.lstrip(_DECORATION)
        if t.startswith("<!--"):
            t = t[4:]
        elif t.startswith("<"):
            k = t.find(">")
            t = t[k + 1:] if 0 < k < 40 else t
        if t[:2] == "x]":
            t = t[2:]
        if len(t) >= 2 and "a" <= t[0] <= "z" and t[1] in ".)" and t[2:3] in (" ", "\t", "*", "_"):
            t = t[2:]
        k = 0
        while k < len(t) and t[k] in DIGITS:
            k += 1
        if k and t[k:k + 1] in (".", ")"):
            t = t[k + 1:]
        if t == before:
            return t


def marker_like(line):
    """True when a line reads as an attempted marker, however decorated (indent, bullets, checkboxes,
    numbering, quotes, brackets, HTML, emphasis, look-alike characters): its first word, once the
    decoration is removed, is `blocked` / `blocking` (any joiner to the next word), and it names a
    question or a decision, or a colon follows within twenty letters. Plain prose (`Blocked on the
    migration; ...`, `No blocking decision`) is not one."""
    t = _undecorate(_fold(line))
    letters = "".join(c for c in t if "a" <= c <= "z")
    if not (letters.startswith("blocked") or letters.startswith("blocking")):
        return False
    j = 0
    while j < len(t) and not ("a" <= t[j] <= "z"):
        j += 1
    if t[j:j + 5] != "block":
        return False  # a letter outside a-z (an unmapped look-alike) before the word: not this rule
    head = letters[:40]
    if "question" in head or "decision" in head:
        return True
    k = t.find(":")
    return k >= 0 and len([c for c in t[:k] if "a" <= c <= "z"]) <= 20


def stray_markers(text):
    """[(line_no, kind, line)] for every marker the task grammar does not accept as a task's marker:
    `half` -- a marker-like line not in the exact form (bulleted, indented, colon outside the bold,
    doubled space, look-alike or full-width characters); `outside` -- an exact marker that sits before
    the first task heading or inside `## Lifted holds`. Each fails closed: HOLD, never unguarded."""
    found, in_task = [], False
    old = OLD_SPELLINGS["marker"].lower()
    for n, raw in enumerate(text.split("\n"), 1):
        line = raw[:-1] if raw.endswith("\r") else raw
        name = heading2(line)
        if name is not None:
            in_task = name.lower() != SECTION_NAME
            continue
        if line[:len(old)].lower() == old:
            continue  # the old marker is reported by old_spellings
        if marker_rest(line) is not None:
            if not in_task:
                found.append((n, "outside", line))
        elif marker_like(line):
            found.append((n, "half", line))
    return found


def old_spellings(text):
    """[(line_no, kind, detail)] for every retired spelling in a task log: the old marker label on any
    line, the retired section (a level-2 heading named OLD_SPELLINGS["section"] whose section holds a
    record line), or the old field on any record line. That heading with no record line is not said's."""
    found, in_old = [], False
    for n, raw in enumerate(text.split("\n"), 1):
        line = raw[:-1] if raw.endswith("\r") else raw
        name = heading2(line)
        if name is not None:
            in_old = name.lower() == OLD_SPELLINGS["section"]
            continue
        label = OLD_SPELLINGS["marker"]
        if line[:len(label)].lower() == label.lower():
            found.append((n, "marker", line[len(label):].strip()))
            continue
        rf = record_field(line)
        if rf and rf[1].lower() == OLD_SPELLINGS["field"]:
            found.append((n, "field", rf[0]))
        elif rf and in_old and rf[1].lower() == FIELD_NAME:
            found.append((n, "section", rf[0]))
    return found


def parse_record(line):
    """One record line -> dict(id, actor, turn, quote, date, sup), else None."""
    c = Cursor(line)
    if not c.word("-") or not c.spaces(1):
        return None
    rid = c.token()
    if not is_id(rid) or not c.spaces(1) or not c.word(FIELD_NAME):
        return None
    c.spaces()
    actor = c.token()
    if not actor:
        return None
    turn = None
    if c.word("@"):
        turn = c.token()
        if not turn:
            return None
    if not c.spaces(1) or not c.word("--") or not c.spaces(1) or not c.word('"'):
        return None
    quote = c.upto('"')
    if quote is None or not c.spaces(1) or not c.word("--") or not c.spaces(1):
        return None
    date = c.s[c.i:c.i + 10]
    if not is_date(date):
        return None
    c.i += 10
    sup = None
    if c.spaces(1) and c.word("[supersedes:"):
        c.spaces()
        sup = c.upto("]")
        if sup is None or not sup.strip():
            return None
        sup = sup.strip()
        c.spaces()
    if c.rest():
        return None
    return {"id": rid, "actor": actor, "turn": turn, "quote": quote, "date": date, "sup": sup}


def parse_log(text):
    """A task log -> (tasks, records): tasks = [(name, [lines])] for every level-2 section
    except `## Lifted holds`; records = every well-formed record line in those sections."""
    tasks, records, cur, in_ledger = [], [], None, False
    for raw in text.split("\n"):
        line = raw[:-1] if raw.endswith("\r") else raw
        name = heading2(line)
        if name is not None:
            in_ledger = name.lower() == SECTION_NAME
            cur = None if in_ledger else (name, [])
            if cur is not None:
                tasks.append(cur)
            continue
        if in_ledger:
            rec = parse_record(line)
            if rec:
                records.append(rec)
        elif cur is not None:
            cur[1].append(line)
    return tasks, records


# --- inputs -------------------------------------------------------------------

def _read(path):
    """A file's text (a leading byte-order mark dropped); an unreadable file is a ConfigError."""
    try:
        with open(path, "r", encoding="utf-8-sig", errors="replace") as fh:
            return fh.read()
    except OSError as e:
        raise ConfigError(f"cannot read {shown(path)}: {e.strerror or e}")


RULING_STATUSES = ("pending", "landed", "rejected", "superseded")
RULING_DOC_TAG = "-ruling-"
LIFTING_PROVENANCE = ("typed", "dialog")


def ruling_id(tok):
    """True for `WR-<10 ASCII digits>` with an optional `-<digits>` suffix."""
    if not tok.startswith("WR-") or len(tok) < 13 or not all(c in DIGITS for c in tok[3:13]):
        return False
    rest = tok[13:]
    return rest == "" or (rest[:1] == "-" and len(rest) > 1 and all(c in DIGITS for c in rest[1:]))


def _evidence_path(item):
    """The path an evidence item names (backticks, a `:line` suffix and an `#anchor` dropped), else None."""
    item = item.strip()
    if item.startswith("`"):
        k = item.find("`", 1)
        if k <= 1:
            return None
        item = item[1:k]
    elif "`" in item:
        return None
    k = item.rfind(":")
    if k > 0 and all(part and all(c in DIGITS for c in part) for part in item[k + 1:].split("-", 1)):
        item = item[:k]
    item = item.split("#", 1)[0].strip()
    return item if item.strip("./") and not item.startswith("-") else None


def parse_ruling_line(line):
    """A rulings-list line -> dict(id, who, status, text, links, arrow); None for a non-entry line;
    "MALFORMED" for a line that starts like an entry but breaks the grammar (an entry-like line --
    `-`, spaces, then `WR` in any case -- that is not exactly `- WR-...`)."""
    if not line.startswith("- WR-"):
        return "MALFORMED" if line.startswith("-") and line[1:].lstrip(" \t")[:2].upper() == "WR" else None
    body = line[2:].rstrip()
    k = 0
    while k < len(body) and body[k] not in " \t":
        k += 1
    rid, rest = body[:k], body[k:]
    if not ruling_id(rid) or not rest.startswith(" - "):
        return "MALFORMED"
    rest = rest[3:]
    cut = None
    for st in RULING_STATUSES:
        j = rest.find(", " + st + ": ")
        if j > 0 and (cut is None or j < cut[0]):
            cut = (j, st)
    if cut is None:
        return "MALFORMED"
    who, status = rest[:cut[0]].strip(), cut[1]
    text = rest[cut[0] + len(status) + 4:]
    arrow = None
    if status in ("landed", "superseded"):
        j = text.rfind(" -> ")
        if j >= 0:
            arrow, text = text[j + 4:].strip(), text[:j]
        elif "->" in text or "=>" in text or "\u2192" in text:
            return "MALFORMED"
    links, t = [], text.rstrip()
    if t.endswith("]"):
        depth, j = 0, len(t) - 1
        while j >= 0:
            depth += {"]": 1, "[": -1}.get(t[j], 0)
            if depth == 0:
                break
            j -= 1
        inner = t[j + 1:-1] if j >= 0 else None
        if inner is None or "[" in inner or "]" in inner:
            return "MALFORMED"
        for item in inner.replace(";", ",").split(","):
            path = _evidence_path(item)
            if path is None:
                return "MALFORMED"
            links.append(path)
        t = t[:j].rstrip()
    if not who or not t.strip():
        return "MALFORMED"
    return {"id": rid, "who": who, "status": status, "text": t.strip(), "links": links, "arrow": arrow}


def load_rulings(paths):
    """{list_path: [(line_no, entry)]} plus {list_path: [malformed line numbers]} for every list.
    A list is a file named `rulings.md` whose first bullet line is an entry."""
    if not paths:
        raise ConfigError("a markered task needs the work's rulings list: pass --rulings <rulings.md>")
    entries, broken = [], {}
    for p in paths:
        if not os.path.isfile(p):
            raise ConfigError(f"rulings list not found: {shown(p)}")
        if os.path.basename(p) != "rulings.md":
            raise ConfigError(f"not a rulings list (the file is named rulings.md): {shown(p)}")
        first_bullet = True
        for n, raw in enumerate(_read(p).split("\n"), 1):
            line = raw[:-1] if raw.endswith("\r") else raw
            e = parse_ruling_line(line)
            if first_bullet and line.startswith("-"):
                if e is None:
                    raise ConfigError(f"not a rulings list (its first bullet is not a ruling line): {shown(p)}")
                first_bullet = False
            if e == "MALFORMED":
                broken.setdefault(p, []).append(n)
            elif e is not None:
                entries.append((p, n, e))
    return entries, broken


def shown(text, cap=80):
    """List- or log-derived text as printed: printable ASCII only, capped (builder-authored input)."""
    return "".join(c if 0x20 <= ord(c) < 0x7f else "?" for c in str(text))[:cap]


def _inside(base, full):
    b = os.path.realpath(base)
    return full == b or full.startswith(b.rstrip(os.sep) + os.sep)


def open_evidence(root, list_path, link):
    """The file a list link opens -- from the root, then the list's folder, never outside both."""
    if os.path.isabs(link):
        return None
    own = os.path.dirname(os.path.abspath(list_path))
    for base in (root, own):
        try:
            full = os.path.realpath(os.path.join(base, link))  # a symlink is judged by where it points
            if (_inside(root, full) or _inside(own, full)) and os.path.isfile(full):
                return full
        except (ValueError, OSError):  # a path the OS cannot take (a NUL byte) does not open
            continue
    return None


def doc_heading2(line):
    """A level-2 heading as markdown renders it (up to three leading spaces, closing hashes), else None."""
    pad = len(line) - len(line.lstrip(" "))
    t = line[pad:]
    if pad > 3 or not t.startswith("##") or t.startswith("###") or t[2:3] not in (" ", "\t"):
        return None
    return t[3:].strip().rstrip("#").strip()


def fence_run(line):
    """(char, width, rest) when the line opens or may close a fenced block (up to three leading
    spaces, then three or more backticks or tildes), else None. A fence closes only on a run of the
    same character at least as wide as the one that opened it, with nothing after it but spaces."""
    lead = line.lstrip(" ")
    if len(line) - len(lead) > 3 or lead[:1] not in ("`", "~"):
        return None
    width = len(lead) - len(lead.lstrip(lead[0]))
    return (lead[0], width, lead[width:]) if width >= 3 else None


def read_ruling_doc(path):
    """dict(provenance, ruled_by, message, faults) from a ruling document. A header bullet given
    twice, or the message section given twice, is a fault (the document is ambiguous)."""
    prov, ruled_by, msg, faults, cur, in_head, seen = [], [], [], [], None, True, set()
    fence = None
    for raw in _read(path).split("\n"):
        line = raw[:-1] if raw.endswith("\r") else raw
        run = fence_run(line)
        if run is not None:
            char, width, rest = run
            if fence is None:
                fence = (char, width)
                continue
            if char == fence[0] and width >= fence[1] and not rest.strip():
                fence = None
                continue
        if fence is not None:  # a fenced block is example text: no header, heading or message
            continue
        name = doc_heading2(line)
        if name is not None:
            if name in seen and name == "The operator's message":
                faults.append("the operator's message section appears twice")
            in_head, cur = False, name
            seen.add(name)
            continue
        if in_head and line.startswith("- Provenance:"):
            prov.append(line[len("- Provenance:"):].strip().rstrip(". ").strip())  # `typed.` is written too
        elif in_head and line.startswith("- Ruled by:"):
            ruled_by.append([x.strip() for x in line[len("- Ruled by:"):].split(",")])
        elif cur == "The operator's message" and line.startswith(">"):
            msg.append(line[2:] if line.startswith("> ") else line[1:])
    if len(prov) > 1:
        faults.append("`Provenance:` appears %d times" % len(prov))
    if len(ruled_by) > 1:
        faults.append("`Ruled by:` appears %d times" % len(ruled_by))
    return {"provenance": prov[0] if prov else None, "ruled_by": ruled_by[0] if ruled_by else [],
            "message": "\n".join(msg), "faults": faults}


def resolve_task_files(roots):
    """(files, empty_roots) -- a root matching zero files is a vacuity error, never a
    silent PASS (a typo'd glob or a wrong cwd)."""
    files, empty = [], []
    for root in roots:
        got = []
        if os.path.isfile(root):
            got = [root]
        elif os.path.isdir(root):
            got = [os.path.join(dp, fn) for dp, _dn, fns in os.walk(root)
                   for fn in fns if fn.endswith(".md")]
        else:
            got = [p for p in glob.glob(root, recursive=True) if os.path.isfile(p)]
        (files.extend(sorted(got)) if got else empty.append(root))
    return files, empty


# --- the predicate ------------------------------------------------------------

class Verdict:
    __slots__ = ("state", "task", "qid", "reason")

    def __init__(self, state, task, qid, reason):
        self.state, self.task, self.qid, self.reason = state, task, qid, reason

    def __str__(self):  # every builder-derived part printed as printable ASCII, capped
        head = f"  [{self.state}] {shown(self.task, 160)}"
        reason = shown(self.reason, 1000)  # its builder-derived parts are capped where they are built
        return head + (f" (question {shown(self.qid, 40)}): {reason}" if self.qid else f": {reason}")


def judge_marker(task_name, task_status, qid, records, rulings, root):
    """PASS/HOLD for one marker -- the structural predicate only."""
    recs = [r for r in records if r["id"] == qid]
    if not recs:
        return Verdict("HOLD", task_name, qid, "no well-formed `## Lifted holds` record for it")
    r = recs[-1]  # append-only: the last record supersedes any earlier one
    actor = r["actor"]
    if actor != "user":  # a fixed role word: exactly `user`, no other letter case
        if actor.lower() in DENY:
            return Verdict("HOLD", task_name, qid,
                           f"lifted-by actor '{actor}' is a self-default basis, not the operator -- only the "
                           "operator's ruling lifts a hold")
        return Verdict("HOLD", task_name, qid,
                       f"lifted-by actor '{shown(actor, 40)}' -- write `user`, the fixed role word; the "
                       "person's name belongs to the ruling")
    if not r["turn"]:
        return Verdict("HOLD", task_name, qid, "the lift cites no ruling -- write `user@WR-<seconds>`, the ruling's id")
    rid = r["turn"]
    if not ruling_id(rid):
        return Verdict("HOLD", task_name, qid,
                       f"'{rid}' is not a ruling id -- a lift cites the operator's ruling as `user@WR-<seconds>`")
    entries, broken = rulings
    hits = [(lp, n, e) for lp, n, e in entries if e["id"] == rid]
    if not hits:
        return Verdict("HOLD", task_name, qid,
                       f"ruling {rid} is not in the rulings list -- record the operator's answer with the "
                       "`ruled` skill, then cite its id")
    lists = sorted({lp for lp, _n, _e in hits})
    if len(lists) > 1:
        return Verdict("HOLD", task_name, qid,
                       f"ruling {rid} is in {len(lists)} rulings lists -- pass only the work's own list")
    if len(hits) > 1:
        return Verdict("HOLD", task_name, qid, f"ruling {rid} is on {len(hits)} lines of {shown(lists[0])} -- one line per ruling")
    lp, n, e = hits[0]
    if broken.get(lp):
        return Verdict("HOLD", task_name, qid,
                       f"the rulings list {shown(lp)} has a malformed entry line (line {broken[lp][0]}) -- fix the list")
    if e["status"] == "rejected":
        return Verdict("HOLD", task_name, qid, f"ruling {rid} is rejected -- it cannot lift a hold")
    if e["status"] == "superseded":
        succ = shown(e["arrow"], 40) if e["arrow"] else "its successor"
        return Verdict("HOLD", task_name, qid, f"ruling {rid} is superseded -- cite {succ} instead")
    doc_link = e["links"][0] if e["links"] else None
    if not doc_link or RULING_DOC_TAG not in os.path.basename(doc_link):
        return Verdict("HOLD", task_name, qid,
                       f"ruling {rid} has no ruling document -- a lift cites a ruling recorded with its document")
    doc = open_evidence(root, lp, doc_link)
    if doc is None:
        return Verdict("HOLD", task_name, qid, f"ruling document {shown(doc_link)} does not open")
    try:
        d = read_ruling_doc(doc)
    except ConfigError as err:
        return Verdict("HOLD", task_name, qid, f"ruling document {shown(doc_link)}: {err}")
    if d["faults"]:
        return Verdict("HOLD", task_name, qid,
                       f"ruling document {shown(doc_link)} is ambiguous: {'; '.join(d['faults'])}")
    if d["provenance"] == "stated-outside":
        return Verdict("HOLD", task_name, qid,
                       f"ruling {rid} was stated outside a recorded session -- the operator restates it in a "
                       "session, then the lift cites that ruling")
    if d["provenance"] not in LIFTING_PROVENANCE:
        return Verdict("HOLD", task_name, qid,
                       f"ruling document {shown(doc_link)} has provenance '{shown(d['provenance'], 30)}', not typed or dialog")
    if len(d["ruled_by"]) < 3 or d["ruled_by"][2] != rid:
        return Verdict("HOLD", task_name, qid, f"ruling document {shown(doc_link)}: `Ruled by:` does not name {rid} "
                       "as its third part (`<who>, <time>, <id>, ...`)")
    if not r["quote"].strip():
        return Verdict("HOLD", task_name, qid, "the lift carries an empty quote (no verbatim evidence)")
    if not d["message"].strip() or r["quote"] not in d["message"]:
        return Verdict("HOLD", task_name, qid,
                       f"the quoted text is not a literal substring of the operator's message in {shown(doc_link)}")
    state, status_day = task_status
    done = (state or "").casefold() == "done"
    if done and not calendar_date(status_day or ""):
        return Verdict("HOLD", task_name, qid,
                       "the Done task's `**Status:**` line carries no calendar date to bound the lift against")
    if not calendar_date(r["date"]):
        return Verdict("HOLD", task_name, qid, f"the lift date {r['date']} is not a calendar date")
    ruled_day = d["ruled_by"][1][:10] if len(d["ruled_by"]) > 1 else ""
    if not calendar_date(ruled_day):
        return Verdict("HOLD", task_name, qid,
                       f"ruling document {shown(doc_link)}: `Ruled by:` carries no `<time>` to date the ruling")
    try:
        earliest = (datetime.date.fromisoformat(ruled_day) - datetime.timedelta(days=1)).isoformat()
    except (ValueError, OverflowError):
        return Verdict("HOLD", task_name, qid,
                       f"the `Ruled by:` time {ruled_day} is out of range in ruling document {shown(doc_link)}")
    if r["date"] < earliest:  # one day of slack: the ruling time is UTC, the lift date is local
        return Verdict("HOLD", task_name, qid, f"the lift ({r['date']}) predates its ruling ({ruled_day})")
    if done and r["date"] > status_day:
        return Verdict("HOLD", task_name, qid,
                       f"the lift ({r['date']}) is dated after the task closed ({status_day}) -- put the task "
                       "back to Todo, keep the lift, and close it again with a new date")
    return Verdict("PASS", task_name, qid, f"operator-attributed (ruling {rid}, {d['provenance']}, verbatim, {r['date']})")


def markers_of(lines):
    """[(rest)] for every marker line in a task's lines, plus the task's status date."""
    found, date = [], None
    for line in lines:
        rest = marker_rest(line)
        if rest is not None:
            found.append(rest)
        elif date is None:
            date = status_date(line)
    return found, date


def task_status_of(lines):
    """(state word, date) from the task's own first `**Status:**` line, else (None, None). The state
    is the first word after the label (`Todo`, `Done`, ...); the date is that line's `(YYYY-MM-DD)`."""
    for line in lines:
        if line.startswith(STATUS_LABEL):
            return line[len(STATUS_LABEL):].strip().split(" ")[0].split("(")[0], status_date(line)
    return None, None


def judge_file(path, rulings, root):
    """Every markered task in a log -> a Verdict; an unmarkered log yields one 'no marker' PASS.
    A retired spelling anywhere in the log HOLDs (no exemption by status or date)."""
    text = _read(path)
    tasks, records = parse_log(text)
    verdicts = [Verdict("HOLD", f"{path}:{n}", None, f"{kind} `{shown(detail, 40)}`: {RENAME}")
                for n, kind, detail in old_spellings(text)]
    for n, kind, line in stray_markers(text):
        if "decision" in line.casefold():
            why = f"a half-recognised marker in the old spelling: {RENAME}"
        elif kind == "outside":
            why = "a marker outside any task (before the first `## ` task heading or in `## Lifted holds`)"
        else:
            why = "a half-recognised marker -- write it as `**Blocked-on question:** <id>` at the start of the line"
        verdicts.append(Verdict("HOLD", f"{path}:{n}", None, f"`{shown(line.strip(), 50)}`: {why}"))
    for name, lines in tasks:
        found, _date = markers_of(lines)
        tstat = task_status_of(lines)
        for rest in found:  # every marker on the task is judged -- a second one is never shadowed
            if not is_id(rest):
                verdicts.append(Verdict("HOLD", f"{path}:{name}", rest or "(empty)",
                                        "malformed `Blocked-on question` marker -- expected a bare `<id>`"))
                continue
            verdicts.append(judge_marker(f"{path}:{name}", tstat, rest, records, rulings, root))
    if not verdicts:
        verdicts.append(Verdict("PASS", path, None, "no `Blocked-on question` marker -- unguarded"))
    return verdicts


def has_marker(path):
    """True when any line of the file -- preamble, task or record section -- is a marker line."""
    return any(marker_rest(ln[:-1] if ln.endswith("\r") else ln) is not None for ln in _read(path).split("\n"))


# --- driver -------------------------------------------------------------------

BANNER = "hold-gate -- structural attribution predicate for a lifted hold\n" + "-" * 60


def cmd_check(args):
    if not args.tasks:
        raise ConfigError("nothing to check: pass --tasks")
    task_files, empty = resolve_task_files(args.tasks)
    if empty:
        raise ConfigError("a --tasks root matched zero files (a gate that scans nothing must not PASS): "
                          + ", ".join(empty))

    # A markered task needs the work's rulings list to verify attribution. Peek first so a
    # missing list fails closed (config), never a silent PASS.
    rulings, root = [], os.path.abspath(args.root or os.getcwd())
    if any(has_marker(p) for p in task_files) or args.rulings:
        rulings = load_rulings(args.rulings)  # raises ConfigError if absent/unreadable

    verdicts = []
    for p in task_files:
        verdicts.extend(judge_file(p, rulings, root))

    holds = [v for v in verdicts if v.state == "HOLD"]
    print(BANNER)
    print(f"scope: {len(task_files)} task file(s), rulings list(s): {', '.join(args.rulings) or 'none'}")
    print("-" * 60)
    for v in verdicts:
        print(v)
    print("-" * 60)
    print(f"{'HOLD' if holds else 'PASS'}, {len(verdicts) - len(holds)} PASS, {len(holds)} HOLD")
    print("(structural predicate only; the semantic 'answers, not merely mentions' check is agent-side)")
    return 1 if holds else 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="hold-gate", description="anti-self-default hold gate")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="check task logs against their `## Lifted holds` records")
    c.add_argument("--tasks", nargs="*", default=[], help="task-log files/dirs/globs")
    c.add_argument("--rulings", nargs="*", default=[], help="the work's rulings list (rulings.md)")
    c.add_argument("--root", default=None, help="where ruling document paths resolve from (default: cwd)")
    c.set_defaults(fn=cmd_check)
    args = ap.parse_args(argv)
    try:
        return args.fn(args)
    except ConfigError as e:
        print(BANNER)
        print(f"  [CONFIG] {e}")
        print("-" * 60)
        print("CONFIG-ERROR, nothing was checked -- fix the inputs.")
        return 2


if __name__ == "__main__":
    sys.exit(main())
