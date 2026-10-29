#!/usr/bin/env python3
"""todo_md.py - the todo-md profile over the block parser (stdlib, no regular expressions).

Layer two of the reader. md_blocks.py turns the lines of a file into blocks; this module walks that tree and
yields what the format means: the front matter data, the sections, topics and entries of a backlog, the
sections and boxes of a todo list, and the findings (file line, code, text) a line that breaks the grammar
earns. The inline words of a line (the stamp, the priority cookie, tags, ids, links) are scanned here with
plain string code. The writers in said_backlog.py find the spans they edit with the same scanners, so there
is one reader of the format.

A read takes the file's lines and a context object with: `add(line, code, message, severity)`, `lanes` (the
registry tokens), `classify(label, href)` (a link's kind and whether it resolves), `rp` (the file's
root-relative path). It never raises on text.
"""
import hashlib

import md_blocks

TEXT_CAP = 500
STATES = {" ": "open", "+": "wip", "X": "done", "x": "done"}
PRIORITY_LETTERS = ("A", "B", "C")
PRIORITY_WORDS = {"high": "A", "medium": "B", "low": "C"}
FORMAT = "todo-md/2"
ID_DIGITS = 13
FORMER_FORMATS = ("said-backlog/2",)  # a rejected version key: never read beside the current one
FORMER_KEYS = ("owner", "owners")  # frontmatter keys the grammar rejects: the top level is a section
FORMER_STAGES = ("entry", "idea", "owed reply", "scoped", "bugfix", "wip only", "promoted", "resolved", "done")
MIDDOT = "\u00b7"
BIDI = {0x200E, 0x200F, 0x202A, 0x202B, 0x202C, 0x202D, 0x202E, 0x2066, 0x2067, 0x2068, 0x2069, 0x2028, 0x2029}
NOTE_KINDS = ("in", "adr", "ref")


def clean(s, cap=TEXT_CAP):
    """Every text field: C0 and C1 control characters, line separators and bidi controls out, length capped."""
    s = "".join(c for c in s if ((ord(c) >= 32 and ord(c) != 127) or c == "\t") and not (0x80 <= ord(c) <= 0x9F) and ord(c) not in BIDI)
    s = s.replace("\t", " ")
    return s[:cap]


# ---------------------------------------------------------------- inline words

def _digits(text, i, n):
    return i + n <= len(text) and all("0" <= text[j] <= "9" for j in range(i, i + n))


def _alnum(c):
    return c.isascii() and c.isalnum()


def _word_char(c):
    return c.isalnum() or c == "_"


def stamp_end(text, i):
    """The end of a `[20YY-MM-DD]` stamp that starts at `i`, else 0."""
    if text[i:i + 3] != "[20" or not _digits(text, i + 3, 2) or text[i + 5:i + 6] != "-":
        return 0
    if not _digits(text, i + 6, 2) or text[i + 8:i + 9] != "-" or not _digits(text, i + 9, 2) or text[i + 11:i + 12] != "]":
        return 0
    return i + 12


def former_stamp_end(text, i):
    """The end of a former `[@YYMMDD]` stamp that starts at `i`, else 0."""
    if text[i:i + 2] == "[@" and _digits(text, i + 2, 6) and text[i + 8:i + 9] == "]":
        return i + 9
    return 0


def token_end(text, i):
    """The end of a `[#word]` priority cookie (ASCII letters and digits) that starts at `i`, else 0."""
    if text[i:i + 2] != "[#":
        return 0
    j = i + 2
    while j < len(text) and _alnum(text[j]):
        j += 1
    return j + 1 if j > i + 2 and text[j:j + 1] == "]" else 0


def code_spans(text):
    """[(start, end)] of the code spans of `text`: a run of N backticks to the next run of exactly N; a run with no
    partner is plain text. One pass over the runs."""
    runs, i = [], 0
    while True:
        a = text.find("`", i)
        if a < 0:
            break
        i = a
        while i < len(text) and text[i] == "`":
            i += 1
        runs.append((a, i))
    nxt, seen = [-1] * len(runs), {}
    for k in range(len(runs) - 1, -1, -1):
        width = runs[k][1] - runs[k][0]
        nxt[k] = seen.get(width, -1)
        seen[width] = k
    out, k = [], 0
    while k < len(runs):
        if nxt[k] < 0:
            k += 1
        else:
            out.append((runs[k][0], runs[nxt[k]][1]))
            k = nxt[k] + 1
    return out


def masked(text):
    """`text` with the characters of each code span replaced by `_`, same length: code span content is opaque."""
    out, pos = [], 0
    for a, b in code_spans(text):
        out.append(text[pos:a] + "_" * (b - a))
        pos = b
    out.append(text[pos:])
    return "".join(out)


def word_spans(text):
    """[(start, end)] of the words of `text`: runs of non-space characters, a code span never split."""
    m, out, i = masked(text), [], 0
    while i < len(m):
        if m[i].isspace():
            i += 1
            continue
        j = i
        while j < len(m) and not m[j].isspace():
            j += 1
        out.append((i, j))
        i = j
    return out


def words_of(text):
    return [text[a:b] for a, b in word_spans(text)]


STAMP_KINDS = (("stamp", stamp_end), ("former", former_stamp_end), ("token", token_end))


def lead_spans(text):
    """[(kind, start, end)] of the lead of an entry's text: the stamp (`stamp`, or the former `former`) and the priority
    cookie (`token`), each only as the first word, or the second after the other one. Nothing later is a lead."""
    out = []
    for a, b in word_spans(text)[:2]:
        kind = next((k for k, f in STAMP_KINDS if f(text, a) == b), None)
        if kind is None or any((kind == "token") == (k == "token") for k, _, _ in out):
            break
        out.append((kind, a, b))
    return out


def _lead(text, kind):
    return next(((a, b) for k, a, b in lead_spans(text) if k == kind), None)


def find_stamp(text):
    return _lead(text, "stamp")


def find_former_stamp(text):
    return _lead(text, "former")


def find_token(text):
    r = _lead(text, "token")
    return None if r is None else (r[0], r[1], text[r[0] + 2:r[1] - 1])


def stamp_digits(text, a):
    """`YYMMDD` of the stamp that starts at `a`."""
    return text[a + 3:a + 5] + text[a + 6:a + 8] + text[a + 9:a + 11]


def has_stamp_or_token(text, kinds=("stamp", "former", "token")):
    """True when a stamp, a former stamp or a priority cookie stands anywhere in `text` outside a code span."""
    ends = [f for k, f in STAMP_KINDS if k in kinds]
    m = masked(text)
    i = m.find("[")
    while i >= 0:
        if any(f(m, i) for f in ends):
            return True
        i = m.find("[", i + 1)
    return False


def strip_lead(text):
    """The words of `text` after its lead (stamp, former stamp, priority cookie), joined by single spaces; the inside
    of a code span is kept as written."""
    drop = {a for _, a, _ in lead_spans(text)}
    return " ".join(text[a:b] for a, b in word_spans(text) if a not in drop)


def _tag_name(w):
    """The tag a word is (`#`, a letter first, then letters, digits, `-`, `_`), else ''."""
    ok = len(w) > 1 and w[0] == "#" and w[1].isalpha() and all(c.isalnum() or c in "-_" for c in w[1:])
    return w[1:] if ok else ""


def take_tags(text):
    """(tags, text without them): a `#word` word outside a code span is a tag."""
    tags, keep = [], []
    for w in words_of(text):
        t = _tag_name(w)
        if not t:
            keep.append(w)
        elif t not in tags:
            tags.append(t)
    return tags, " ".join(keep)


def bracket_spans(text):
    """(start, end, word) of each bare `[word]` token of a line, in order; a link label (a `]` followed by `(`) and a
    code span are not one."""
    out, i, m = [], 0, masked(text)
    while True:
        a = m.find("[", i)
        b = m.find("]", a) if a >= 0 else -1
        if b < 0:
            return out
        if not m.startswith("(", b + 1):
            out.append((a, b + 1, text[a + 1:b]))
        i = b + 1


def bracket_words(text):
    return [w for _, _, w in bracket_spans(text)]


def links_in(text):
    """[(label, target)] of each `[label](target)` link, in order; a target holds no space and no `)`."""
    out, i = [], 0
    while True:
        a = text.find("[", i)
        if a < 0:
            return out
        b = text.find("]", a + 1)
        if b < 0:
            return out
        j = b + 2
        ok = b > a + 1 and text[b + 1:b + 2] == "("
        if ok:
            while j < len(text) and text[j] != ")" and not text[j].isspace():
                j += 1
            ok = j > b + 2 and text[j:j + 1] == ")"
        if ok:
            out.append((text[a + 1:b], text[b + 2:j]))
            i = j + 1
        else:
            i = a + 1


def norm_priority(raw):
    """A, B or C for the letters and for High, Medium, Low; anything else comes back as given."""
    return PRIORITY_WORDS.get(raw.lower(), raw)


def stamp_date(stamp):
    return "20%s-%s-%s" % (stamp[:2], stamp[2:4], stamp[4:6]) if stamp else ""


def split_entry_text(text, with_tags=True):
    """stamp, priority letter, token position, clean text (lead, tags removed), tags."""
    lead = lead_spans(text)
    stamp = next((stamp_digits(text, a) for k, a, _ in lead if k == "stamp"), "")
    letter, pos = "", ""
    for i, (k, a, b) in enumerate(lead):
        if k == "token":
            letter = norm_priority(text[a + 2:b - 1])
            pos = "before-stamp" if i == 0 and any(k2 == "stamp" for k2, _, _ in lead) else "after-stamp"
    tags, body = take_tags(strip_lead(text)) if with_tags else ([], strip_lead(text))
    return stamp, letter, pos, body, tags


def id_start(w):
    """True for a word that is an id by its first characters: `@` and a digit (never a mention)."""
    return len(w) > 1 and w[0] == "@" and "0" <= w[1] <= "9"


def is_id(w):
    """True for a whole-word id: `@` and exactly 13 ASCII digits (a Unix time in milliseconds)."""
    return len(w) == ID_DIGITS + 1 and w[0] == "@" and all("0" <= c <= "9" for c in w[1:])


def trailing_id(text):
    """The id that ends a line's text, else ''."""
    words = words_of(text)
    return words[-1] if words and is_id(words[-1]) else ""


def without_id(text):
    """`text` without the id that ends it."""
    ident = trailing_id(text)
    return text[:text.rstrip().rfind(ident)].rstrip() if ident else text


def read_id(add, line, text, seen):
    """The id of an entry line's text, '' when it has none; a missing id is a warning, a word that starts `@` and a
    digit but is no id at the end of the text is `id-malformed`, an id met twice in one file is `id-duplicate`."""
    words = words_of(text)
    bad = 0
    for i, w in enumerate(words):
        if id_start(w) and not (is_id(w) and i == len(words) - 1):
            bad += 1
            add(line, "id-malformed", "`%s` is no id: an id is `@` and %d digits, the last word of the text" % (clean(w, 30), ID_DIGITS))
    ident = trailing_id(text)
    if not ident:
        if not bad:
            add(line, "id-missing", "the line carries no `@<unix milliseconds>` id", "warn")
    elif ident in seen:
        add(line, "id-duplicate", "the id `%s` is already on an earlier line of this file" % ident)
    else:
        seen.add(ident)
    return ident


def stable_key(prefix, text):
    """A line's handle for the writers: its words, without the stamp, the priority cookie, the tags and the id."""
    core = take_tags(strip_lead(without_id(text)).replace("**", ""))[1].lower()
    return "%s:%s" % (prefix, hashlib.sha1(core.encode("utf-8")).hexdigest()[:10])


# ---------------------------------------------------------------- ids and names

def feature_id_end(s, i=0):
    """The end of the feature id (`PREFIX-NN` with optional `-word` parts, ASCII) that starts at `i`, else -1."""
    j = i
    while j < len(s) and "A" <= s[j] <= "Z":
        j += 1
    if j == i or s[j:j + 1] != "-":
        return -1
    k = j + 1
    while k < len(s) and s[k] in "0123456789":
        k += 1
    if k == j + 1:
        return -1
    while s[k:k + 1] == "-":
        m = k + 1
        while m < len(s) and _alnum(s[m]):
            m += 1
        if m == k + 1:
            break
        k = m
    return k


def is_feature_id(s):
    return bool(s) and feature_id_end(s) == len(s)


def feature_head(name):
    """The `PREFIX-NN` a file name starts with, else ''."""
    j = 0
    while j < len(name) and "A" <= name[j] <= "Z":
        j += 1
    if j == 0 or name[j:j + 1] != "-":
        return ""
    k = j + 1
    while k < len(name) and name[k].isdecimal():
        k += 1
    if k == j + 1 or (k < len(name) and _word_char(name[k])):
        return ""
    return name[:k]


def feature_search(text):
    """The first `PREFIX-NN` as a whole word in `text`, else ''."""
    i = 0
    while i < len(text):
        if "A" <= text[i] <= "Z" and (i == 0 or not _word_char(text[i - 1])):
            j = i
            while j < len(text) and "A" <= text[j] <= "Z":
                j += 1
            if text[j:j + 1] == "-":
                k = j + 1
                while k < len(text) and text[k].isdecimal():
                    k += 1
                if k > j + 1 and (k == len(text) or not _word_char(text[k])):
                    return text[i:k]
            i = j
        else:
            i += 1
    return ""


def serves_id(text):
    """The feature id of an `in <id>` note, else ''."""
    if not text.startswith("in") or len(text) < 3 or text[2] not in " \t\n\r\f\v":
        return ""
    i = 2
    while i < len(text) and text[i] in " \t\n\r\f\v":
        i += 1
    e = feature_id_end(text, i)
    if e < 0 or (e < len(text) and (_alnum(text[e]) or text[e] == "-")):
        return ""
    return text[i:e]


def is_slug(s):
    parts = s.split("-")
    return all(p and all(c.isascii() and (c.islower() or c.isdigit()) for c in p) for p in parts)


def is_day(s):
    return (len(s) == 10 and s[:2] == "20" and s[4] == "-" and s[7] == "-"
            and all(c in "0123456789" for c in s[:4] + s[5:7] + s[8:]))


def sub_item_ok(words):
    """A todo sub-item: `in <feature id>` (then end or one of ` ,;:` and anything), `adr: <word...>` or `ref: <word...>`."""
    for lead in ("adr: ", "ref: "):
        if words.startswith(lead):
            return len(words) > len(lead) and words[len(lead)] not in " \t\n\r\f\v"
    if words.startswith("in "):
        e = feature_id_end(words, 3)
        return e > 3 and (e == len(words) or words[e] in " ,;:")
    return False


def record_folder(name):
    """(stamp, kind, slug) of a `<YYMMDD>-<kind>-<slug>` folder name, else None."""
    if len(name) < 10 or not _digits(name, 0, 6) or name[6] != "-":
        return None
    j = 7
    while j < len(name) and "a" <= name[j] <= "z":
        j += 1
    if j == 7 or name[j:j + 1] != "-" or j + 1 >= len(name):
        return None
    return name[:6], name[7:j], name[j + 1:]


def starts_with_scheme(href):
    j = 0
    while j < len(href) and "a" <= href[j] <= "z":
        j += 1
    return j > 0 and href[j:j + 3] == "://"


def lead_word(text):
    """The run of letters, digits and `_` at the start of `text`."""
    j = 0
    while j < len(text) and _word_char(text[j]):
        j += 1
    return text[:j]


def note_kind(text):
    w = lead_word(text)
    return w if w in NOTE_KINDS else "note"


def bold_line(s, label):
    """The text after a leading `**<label>:**` of the stripped line `s`, left-stripped, else None."""
    head = "**%s:**" % label
    return s[len(head):].lstrip() if s.startswith(head) else None


def priority_head_parts(s):
    """(the priority word, the trailing id or '') of a `**Priority:**` head line `s`, else None. The word is a bare
    letter A, B or C, High, Medium or Low (any case), or the inside of `[#X]` (any word, so a wrong letter can be
    reported); '' for a bare label. An optional last word `@<13 digits>` is the id."""
    rest = bold_line(s, "Priority")
    if rest is None:
        return None
    words = rest.split()
    ident = words.pop() if words and is_id(words[-1]) else ""
    if not words:
        return "", ident
    if len(words) > 1:
        return None
    w = words[0]
    if token_end(w, 0) == len(w):
        return w[2:-1], ident
    return (w, ident) if w.upper() in PRIORITY_LETTERS or w.lower() in PRIORITY_WORDS else None


def priority_head(s):
    """None when `s` is no `**Priority:**` line; else its priority word ('' for a bare label)."""
    parts = priority_head_parts(s)
    return None if parts is None else parts[0]


# ---------------------------------------------------------------- one line

def lead_len(ln):
    i = 0
    while i < len(ln) and ln[i].isspace():
        i += 1
    return i


def box_of(ln):
    """(indent without tab characters, state char, text, index of the state char, index of the text) of a checkbox line, else None."""
    i = lead_len(ln)
    if ln[i:i + 3] != "- [" or ln[i + 4:i + 5] != "]" or len(ln) < i + 5:
        return None
    t = i + 5
    if t < len(ln) and ln[t].isspace():
        t += 1
    return len(ln[:i].replace("\t", "")), ln[i + 3], ln[t:], i + 3, t


def sub_split(ln):
    """(the indent as written, text) of an indented `- ` line, else None."""
    i = lead_len(ln)
    if i and ln[i:i + 2] == "- ":
        return ln[:i], ln[i + 2:]
    return None


def box_gap(add, n, bx):
    """A finding when the text of a box line follows the `]` with no space (`- [ ]x`)."""
    if bx[4] - bx[3] == 2 and bx[2]:
        add(n, "box-space", "a box is followed by a space: `- [ ] text`")


def group_of(ln):
    """The title of a `N. Title` numbered-group line (N up to six digits, at column 0), else None."""
    n = 0
    while n < len(ln) and ln[n].isdecimal():
        n += 1
    if not 1 <= n <= 6 or ln[n:n + 1] != "." or n + 1 >= len(ln) or not ln[n + 1].isspace():
        return None
    title = ln[n + 1:].strip()
    return title or None


def rule_line(ln):
    """True for a rule line at column 0: a run of `=`, or four or more `-`, with trailing space allowed."""
    t = ln.rstrip()
    if not t or t != ln[:len(t)]:
        return False
    return not t.strip("=") or (len(t) >= 4 and not t.strip("-"))


def with_priority(line, letter):
    """The box line with its priority cookie written, replaced or removed; every other byte kept. None when the line is no box."""
    body = line.rstrip("\r")
    cr = line[len(body):]
    bx = box_of(body)
    if bx is None:
        return None
    pre, text = body[:bx[4]], body[bx[4]:]
    tm = find_token(text)
    if tm:
        a, b = tm[0], tm[1]
        if b < len(text) and text[b] == " ":
            b += 1
        elif a > 0 and text[a - 1] == " ":
            a -= 1
        text = text[:a] + text[b:]
    if letter:
        sm = find_stamp(text)
        if sm:
            text = text[:sm[1]] + " [#%s]" % letter + text[sm[1]:]
        else:
            text = "[#%s]%s%s" % (letter, " " if text else "", text)
        if not pre.endswith((" ", "\t")):
            pre += " "
    return pre + text + cr


def raw_text(ln):
    """An entry's text from the file's own line: after the box, without the lead (stamp and cookie)."""
    text = box_of(ln.rstrip("\r"))[2]
    return without_id(strip_lead(text))


# ---------------------------------------------------------------- front matter

def read_front(front, add):
    """(targets {name: kind}, the format value or None and its line) from the front matter's (line, text) pairs;
    a former key is a finding."""
    targets, key, fmt, fmt_line = {}, "", None, 1
    for i, ln in front:
        if not ln.strip() or ln.lstrip().startswith("#"):
            continue
        if not ln.startswith((" ", "\t")):
            key, _, val = ln.partition(":")
            key = key.strip()
            if key == "format":
                fmt, fmt_line = val.strip(), i
            if key.lower() in FORMER_KEYS:
                add(i, "former-key", "this key names the top level by a former word; the top level is a section: a lane token or a name under `targets:`")
        elif key == "targets":
            name, _, kind = ln.strip().partition(":")
            name, kind = clean(name.strip(), 120), kind.strip()
            if not name or kind != "external":
                add(i, "target-kind-unknown", "a target is `<name>: external`")
            targets[name] = kind
    return targets, fmt, fmt_line


def format_findings(fmt, fmt_line, add):
    """One finding for a version key that is missing, a rejected former one, or unknown."""
    if not fmt:
        add(1, "format-missing", "the frontmatter has no `format: %s` key" % FORMAT)
    elif fmt in FORMER_FORMATS:
        add(fmt_line, "format-former", "the format `%s` is a former version; write `format: %s`" % (clean(fmt, 40), FORMAT))
    elif fmt != FORMAT:
        add(fmt_line, "format-unknown", "the format `%s` is not `%s`" % (clean(fmt, 40), FORMAT))


def token_findings(add, line, text, stages=True):
    """The rejected bracket forms on an entry line: a former stage word, the `P1` / `P2` scale."""
    for w in bracket_words(text):
        if stages and w.lower() in FORMER_STAGES:
            add(line, "stage-former", "the stage word `[%s]` is not written in the file; the stage is read from the links" % w)
        elif len(w) == 2 and w[0] in "Pp" and w[1].isdigit():
            add(line, "priority-p-scale", "`[%s]` is not a priority; write `[#A]`, `[#B]` or `[#C]`" % w, "warn")


# ---------------------------------------------------------------- the walk

class _Out(object):
    """Findings in the order a top-to-bottom read of the lines meets them: by the line that triggers each."""

    def __init__(self, ctx):
        self.ctx, self.items, self.trigger, self.phase = ctx, [], 0, 1
        self.ids = set()

    def at(self, trigger, phase=1):
        self.trigger, self.phase = trigger, phase

    def add(self, line, code, message, severity="error"):
        self.items.append((self.trigger, self.phase, len(self.items), line, code, message, severity))

    def flush(self):
        for it in sorted(self.items, key=lambda x: x[:3]):
            self.ctx.add(*it[3:])


def _events(blocks):
    """(block, level) in document order: a list's items one by one, each followed by its children one level deeper."""
    stack = [iter([(b, 0) for b in blocks])]
    while stack:
        nxt = next(stack[-1], None)
        if nxt is None:
            stack.pop()
            continue
        b, level = nxt
        if b.kind == "list":
            stack.append(iter([(it, level) for it in b.items]))
        elif b.kind == "item":
            yield b, level
            stack.append(iter([(c, level + 1) for c in b.children]))
        else:
            yield b, level


def _strip_tabs(ln):
    """The line without the tab characters of its indent (a tab there is a finding)."""
    i = lead_len(ln)
    if "\t" not in ln[:i]:
        return ln
    gap = "" if ln[i:i + 3] == "- [" else "  "  # a note keeps a child's column; a box reads at the left
    return ln[:i].replace("\t", gap) + ln[i:]


class _Read(object):
    """One file read into blocks: the lines, the document-order events, the lines no line-level check looks at."""

    def __init__(self, lines, ctx):
        self.lines = [ln.rstrip("\r") for ln in lines]
        self.ctx, self.out = ctx, _Out(ctx)
        self.events, self.rule_at = list(_events(md_blocks.parse([_strip_tabs(ln) for ln in self.lines]).children)), 0
        self.skip, self.front, self.fences, self.comments = set(), None, [], []
        for b, _ in self.events:
            if b.kind == "front":
                self.front = b
                self.skip.update(n for n, _r in b.lines)
            elif b.kind == "fence":
                self.skip.update(n for n, _r in b.lines)
                self.skip.add(b.open[0])
                self.fences.append(b)
            elif b.kind == "html" and b.end == "-->":
                self.comments.append(b)
        self.claimed = set()
        self.para_of, self.reported = {}, set()
        for b, _ in self.events:
            if b.kind in ("para", "setext", "code", "html") and b.lines:
                self.para_of.update((n, b.lines[0][0]) for n, _r in b.lines)

    def unclosed(self, block):
        """True for a fence or a comment that runs to the end of the file without closing."""
        if block.kind == "fence":
            if block.close:
                return False
            last = block.lines[-1][0] if block.lines else block.open[0]
        else:
            if block.closed:
                return False
            last = block.lines[-1][0]
        return last >= len(self.lines)

    def front_data(self):
        """(targets, format value, its line) of a closed front matter block, its findings triggered at its closing line."""
        if self.front is None or not self.front.closed:
            return {}, None, 1
        self.out.at(self.front.lines[-1][0])
        return read_front([(n, self.lines[n - 1]) for n, _r in self.front.lines[1:-1]], self.out.add)

    def line_checks(self, backlog):
        """The findings of a single line, by the line's own text: a middle dot, a tab; none for the lines the blocks own."""
        for i, ln in enumerate(self.lines, 1):
            if i in self.skip:
                continue
            self.out.at(i, 0)
            if backlog and MIDDOT in ln:
                self.out.add(i, "middle-dot", "the middle-dot separator is banned; use `, `, ` / ` or ` - `")
            if not backlog and MIDDOT in ln and ln.strip().startswith(MIDDOT):
                self.out.add(i, "middle-dot-bullet", "a sub-bullet drawn with a middle dot; use `- `")
            if "\t" in ln:
                self.out.add(i, "tab-indent", "a tab in the indent; the %s indents with spaces" % ("grammar" if backlog else "outline"))

    def stray(self, n):
        self.out.at(n)
        block = self.para_of.get(n, n)
        if n not in self.claimed and block not in self.reported:
            self.reported.add(block)
            self.claimed.add(n)
            self.out.add(n, "stray-line", "a line that is neither a heading, an entry nor a sub-bullet")

    def rule_ok(self, n):
        """True when line `n` is the rule line of the heading just read (a rule line stands nowhere else)."""
        return n == self.rule_at and rule_line(self.lines[n - 1])

    def end_findings(self, fmt, fmt_line):
        self.out.at(len(self.lines) + 1, 2)
        format_findings(fmt, fmt_line, self.out.add)
        if self.front is not None and not self.front.closed:
            self.out.add(1, "frontmatter-unclosed", "the frontmatter opened on line 1 never closes")


class _Sections(object):
    """The open section, topic and subtopic of a backlog."""

    def __init__(self):
        self.section = self.topic = self.sub = None
        self.sections = []

    def box(self):
        return self.sub or self.topic or self.section


def read_backlog(lines, ctx):
    """(targets, format value, its line, sections, entries) of a backlog file's lines; findings go to `ctx.add`."""
    rd = _Read(lines, ctx)
    out, lines = rd.out, rd.lines
    targets, fmt, fmt_line = rd.front_data()
    rd.line_checks(True)
    st, entries = _Sections(), []
    state = {"last": None, "last_level": 0, "old_group": False, "position": 0}

    def need_section(n, what):
        if st.section is None:
            out.add(n, "entry-outside-section", what)
            st.section = {"title": "", "line": n, "kind": "undeclared", "topics": [], "entries": []}
            st.sections.append(st.section)

    for b, level in rd.events:
        k = b.kind
        if k == "heading":
            n = b.line[0]
            out.at(n)
            if not b.text:
                rd.stray(n)
            elif b.level == 1:
                rd.rule_at = n + 1
                t = clean(b.text, 120)
                kind = "lane" if t in ctx.lanes else "target" if t in targets else "undeclared"
                if kind == "undeclared":
                    out.add(n, "section-undeclared", "the section `%s` is neither a registry lane token nor declared under `targets:`" % t)
                st.section = {"title": t, "line": n, "kind": kind, "topics": [], "entries": []}
                st.sections.append(st.section)
                st.topic = st.sub = state["last"] = None
                state["old_group"], state["position"] = False, 0
            elif b.level in (2, 3):
                need_section(n, "a topic before the first H1 section")
                if b.level == 2:
                    st.topic = {"title": clean(b.text, 120), "line": n, "subtopics": [], "entries": []}
                    st.section["topics"].append(st.topic)
                    st.sub = None
                else:
                    if st.topic is None:
                        out.add(n, "topic-skip", "a `###` subtopic with no `##` topic above it")
                        st.topic = {"title": "", "line": n, "subtopics": [], "entries": []}
                        st.section["topics"].append(st.topic)
                    st.sub = {"title": clean(b.text, 120), "line": n, "entries": []}
                    st.topic["subtopics"].append(st.sub)
                state["last"], state["position"], state["old_group"] = None, 0, False
            else:
                out.add(n, "topic-depth", "a heading deeper than `###`; the topic tree is two levels, deeper items are sub-items")
        elif k == "fence":
            out.at(b.open[0])
            out.add(b.open[0], "fence", "a fenced block has no place in the backlog grammar")
        elif k == "item":
            _backlog_item(rd, b, level, st, state, entries, need_section)
        elif k != "front":
            for n in _plain_lines(b):
                if lines[n - 1].strip() and not rd.rule_ok(n):
                    rd.stray(n)
    rd.end_findings(fmt, fmt_line)
    for f in rd.fences:
        if rd.unclosed(f):
            out.add(f.open[0], "fence-unclosed", "a fence opened here never closes")
    out.flush()
    return targets, fmt, fmt_line, st.sections, entries


def _plain_lines(b):
    """The line numbers of a block the profile has no use for: a paragraph, a rule, an opaque block."""
    if b.kind in ("thematic",):
        return [b.line[0]]
    return [n for n, _r in b.lines] + ([b.underline[0]] if b.kind == "setext" else [])


def _backlog_item(rd, it, level, st, state, entries, need_section):
    n, out, ctx = it.line, rd.out, rd.ctx
    if n in rd.claimed:
        return
    out.at(n)
    ln = rd.lines[n - 1]
    plain = _strip_tabs(ln)
    first = lead_len(plain)
    last = state["last"]
    if it.ordered:
        if it.marker_col == 0 and it.delim == "." and st.section is not None and group_of(ln):
            rd.claimed.add(n)
            out.add(n, "group-numbered", "a numbered group is the former topic form; a topic is a `##` heading")
            state["last"], state["position"], state["old_group"] = None, 0, True
        else:
            rd.stray(n)
        return
    if it.marker != "-" or it.marker_col != first:
        rd.stray(n)
        return
    bx = box_of(ln)
    if bx:
        rd.claimed.add(n)
        box_gap(out.add, n, bx)
        indent, stc, text = bx[0], bx[1], bx[2]
        if plain != ln:
            indent = 0  # the tab was reported; it does not also misplace the entry
        nested = indent > 0 and last is not None and plain == ln and not (state["old_group"] and indent == 2)
        if nested:
            out.add(n, "nesting-depth", "a box nested under an entry; the backlog nests one level only")
            entry = _make_entry(out, n, indent, stc, text, st, state["position"])
            entry["parent"], entry["raw"] = last["key"], ln
            entries.append(entry)
            st.box()["entries"].append(entry)
            return
        if indent != 0 and not (state["old_group"] and indent == 2):
            out.add(n, "entry-indent", "an entry sits at %d spaces; %d expected here" % (indent, 0))
        need_section(n, "an entry before the first H1 section")
        state["position"] += 1
        entry = _make_entry(out, n, indent, stc, text, st, state["position"])
        entry["raw"] = ln
        entries.append(entry)
        st.box()["entries"].append(entry)
        state["last"], state["last_level"] = entry, level
        return
    if not (first and plain[first:first + 2] == "- " and level > 0 and last is not None):
        rd.stray(n)
        return
    rd.claimed.add(n)
    sub_text = plain[first + 2:]
    depth = max(0, level - state["last_level"] - 1)
    if plain == ln and first != last["indent"] + 2 * (depth + 1):
        out.add(n, "child-indent", "a sub-bullet sits two columns deeper than its parent, %d spaces here" % (last["indent"] + 2 * (depth + 1)))
    if has_stamp_or_token(sub_text, ("stamp", "former")):
        out.add(n, "stamp-in-sub-bullet", "a stamp in a sub-bullet; the stamp belongs on the entry line")
    links = [ctx.classify(a, b) for a, b in links_in(sub_text)]
    for lk in links:
        if lk["kind"] == "record":
            if lk["label"] != lk["id"]:
                out.add(n, "link-label-not-slug", "the link label `%s` is not the record slug `%s`" % (lk["label"], lk["id"]))
            last["record"] = lk["id"]
        if lk["kind"] == "feature" and lk["id"]:
            last["feature"] = lk["id"]
            last["feature_path"] = lk.get("path", "")
        if lk["resolves"] is False:
            out.add(n, "link-target-missing", "the link target `%s` does not exist" % lk["href"])
    last["sub_bullets"].append({"line": n, "depth": depth, "text": clean(sub_text), "links": links, "raw": ln})
    last["links"].extend(links)
    if depth == 0 and sum(1 for sb in last["sub_bullets"] if sb["depth"] == 0) == 3:
        out.add(last["line"], "sub-bullets-over-two", "an entry carries more than two sub-bullets")


def _make_entry(out, line, indent, mark, text, secs, position):
    if mark not in STATES:
        out.add(line, "state-unknown", "the state `[%s]` is not ` `, `+` (in progress) or `X`" % mark)
    elif mark == "x":
        out.add(line, "state-lowercase", "the done state is `[X]`; lowercase `[x]` read as done")
    stamp, letter, pos, body, tags = split_entry_text(text)
    if find_former_stamp(text):
        out.add(line, "stamp-former", "the stamp `[@YYMMDD]` is the former form; write `[YYYY-MM-DD]`")
    elif not stamp:
        out.add(line, "stamp-missing", "no `[YYYY-MM-DD]` stamp (a legacy entry is kept)", "warn")
    if letter and letter not in PRIORITY_LETTERS:
        out.add(line, "priority-letter", "the priority `%s` is outside A, B, C (High, Medium, Low)" % clean(letter, 20))
    if pos == "before-stamp":
        out.add(line, "token-before-stamp", "the priority token precedes the stamp; it follows it")
    token_findings(out.add, line, text)
    ident = read_id(out.add, line, text, out.ids)
    section, topic, sub = secs.section, secs.topic, secs.sub
    return {
        "key": stable_key("backlog", text), "line": line, "indent": indent, "position": position,
        "section": section["title"] if section else "", "group": topic["title"] if topic else "",
        "subgroup": sub["title"] if sub else "",
        "state": STATES.get(mark, "unknown"), "state_char": mark, "stamp": stamp, "date": stamp_date(stamp),
        "priority": letter if letter in PRIORITY_LETTERS else "", "priority_pos": pos,
        "text": clean(without_id(body) if ident else body), "id": ident, "tags": [clean(t, 60) for t in tags], "sub_bullets": [], "links": [], "record": None, "feature": None, "feature_path": "",
        "parent": None, "stage": "", "trail": [],
    }


def read_lane(lines, ctx):
    """(format value, its line, sections, entries) of a todo file's lines; findings go to `ctx.add`."""
    rd = _Read(lines, ctx)
    out, lines = rd.out, rd.lines
    for c in rd.comments:
        rd.skip.update(n for n, _r in c.lines)
    _, fmt, fmt_line = rd.front_data()
    rd.line_checks(False)
    sections, entries = [], []
    cur = {"section": None, "subsection": None, "stack": []}

    def other_line(n):
        out.at(n)
        ln = lines[n - 1]
        s = ln.strip()
        if not s or n in rd.claimed or rd.rule_ok(n):
            return
        if s.startswith(MIDDOT) and cur["stack"]:
            rd.claimed.add(n)
            host = cur["stack"][-1][1]
            host["sub_bullets"].append({"line": n, "kind": "note", "text": clean(s[1:].strip()), "links": [], "raw": ln})
        else:
            rd.stray(n)

    for b, level in rd.events:
        k = b.kind
        if k == "front" or k == "fence" or (k == "html" and b.end == "-->"):
            continue
        if k == "heading":
            n = b.line[0]
            out.at(n)
            if not b.text or b.level > 2:
                rd.stray(n)
            elif b.level == 1:
                rd.rule_at = n + 1
                cur["section"] = {"title": clean(b.text, 120), "line": n, "subsections": [], "entries": []}
                sections.append(cur["section"])
                cur["subsection"], cur["stack"] = None, []
            else:
                rd.rule_at = n + 1
                cur["subsection"] = {"title": clean(b.text, 120), "line": n, "entries": []}
                if cur["section"] is None:
                    cur["section"] = {"title": "", "line": n, "subsections": [], "entries": []}
                    sections.append(cur["section"])
                cur["section"]["subsections"].append(cur["subsection"])
                cur["stack"] = []
        elif k == "item":
            _todo_item(rd, b, cur, entries, other_line)
        else:
            for n in _plain_lines(b):
                other_line(n)
    rd.end_findings(fmt, fmt_line)
    for c in rd.comments:
        if rd.unclosed(c):
            out.add(c.lines[0][0], "comment-unclosed", "a comment opened here never closes")
    for f in rd.fences:
        if rd.unclosed(f):
            out.add(f.open[0], "fence-unclosed", "a fence opened here never closes")
    out.flush()
    return fmt, fmt_line, sections, entries


def _todo_item(rd, it, cur, entries, other_line):
    n, out, ctx = it.line, rd.out, rd.ctx
    if n in rd.claimed:
        return
    out.at(n)
    ln = rd.lines[n - 1]
    plain = _strip_tabs(ln)
    first = lead_len(plain)
    if it.ordered or it.marker != "-" or it.marker_col != first:
        rd.stray(n)
        return
    stack = cur["stack"]
    section, subsection = cur["section"], cur["subsection"]
    bx = box_of(ln)
    if bx:
        rd.claimed.add(n)
        box_gap(out.add, n, bx)
        indent, mark, text = bx[0], bx[1], bx[2]
        if mark not in STATES:
            out.add(n, "state-unknown", "the state `[%s]` is not ` `, `+` or `X`" % mark)
        stamp, letter, pos, body, _ = split_entry_text(text, with_tags=False)
        if letter and letter not in PRIORITY_LETTERS:
            out.add(n, "priority-letter", "the priority `%s` is outside A, B, C (High, Medium, Low)" % clean(letter, 20))
        token_findings(out.add, n, text, stages=False)
        if find_former_stamp(text):
            out.add(n, "stamp-former", "the stamp `[@YYMMDD]` is the former form; write `[YYYY-MM-DD]`")
        elif not stamp:
            out.add(n, "stamp-missing", "no `[YYYY-MM-DD]` stamp", "warn")
        ident = read_id(out.add, n, text, out.ids)
        while stack and stack[-1][0] >= indent:
            stack.pop()
        parent = stack[-1][1] if stack else None
        if parent and plain == ln and indent != stack[-1][0] + 2:
            out.add(n, "child-indent", "a child box sits two columns deeper than its parent, %d spaces here" % (stack[-1][0] + 2))
        entry = {"key": stable_key("todo-" + ctx.token, text), "line": n, "indent": indent,
                 "section": section["title"] if section else "", "subsection": subsection["title"] if subsection else "",
                 "state": STATES.get(mark, "unknown"), "state_char": mark, "stamp": stamp, "date": stamp_date(stamp),
                 "priority": letter if letter in PRIORITY_LETTERS else "", "priority_pos": pos, "text": clean(without_id(body) if ident else body),
                 "id": ident, "sub_bullets": [], "links": [], "parent": parent["key"] if parent else None, "raw": ln, "serves": "",
                 "position": len((subsection or section or {"entries": []})["entries"]) + 1 if parent is None else 0}
        entries.append(entry)
        if parent is None and (subsection or section):
            (subsection or section)["entries"].append(entry)
        stack.append((indent, entry))
        return
    if first and plain[first:first + 2] == "- " and stack:
        rd.claimed.add(n)
        sub_indent, sub_text = len(plain[:first]), plain[first + 2:]
        while len(stack) > 1 and stack[-1][0] >= sub_indent:
            stack.pop()
        host = stack[-1][1]
        if plain == ln and sub_indent != stack[-1][0] + 2:
            out.add(n, "child-indent", "a note sits two columns deeper than its box, %d spaces here" % (stack[-1][0] + 2))
        links = [ctx.classify(a, b) for a, b in links_in(sub_text)]
        host["sub_bullets"].append({"line": n, "kind": note_kind(sub_text), "text": clean(sub_text), "links": links, "raw": ln})
        host["links"].extend(links)
        return
    rd.stray(n)
