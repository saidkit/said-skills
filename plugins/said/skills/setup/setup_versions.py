#!/usr/bin/env python3
"""Versions section for said:setup: read the upgrade-playbook headers a lane is compared against.

A published upgrade playbook carries a header directly under its title (the first `# ` line):
one blank line, then exactly five key lines `- <key>: <value>` in the order rollout, plugin,
from, to, after, then a blank line.

  rollout: <id>                                   the playbook's own id
  plugin:  <plugin> >=<x.y.z>[, <plugin> >=<x.y.z>] one engine floor per plugin
  from:    <id>@<x.y.z> | unversioned | any       the release a lane moves from
  to:      <id>@<x.y.z>                           the release a lane is brought to
  after:   <rollout-id>[, <rollout-id>] | none    the playbooks this one presupposes

Every version carries its id before `@`; a bare semver is refused. Within one id, `to` strictly
increases along the `after` chain. A header that breaks any of this is refused with a reason and
counted as refused; the others still load. Every value this script prints is sanitized first.

Read-only: the script never writes a file.
"""
import os
import re
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from setup_check import unfenced  # one fence rule for every block reader

KEYS = ("rollout", "plugin", "from", "to", "after")
KEY_RE = re.compile(r"^[a-z][a-z-]{0,31}$")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9.-]{0,63}$")
SEMVER_RE = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
FLOOR_RE = re.compile(r"^([a-z0-9][a-z0-9-]{0,63}) *>= *([0-9.]+)$")
MARKERS = ("PASS", "FAIL", "GOAL:", "OPERATOR-QUESTION-HELD", "[BLOCKER]", "BLOCKER", "[STALE]",
           "STALE", "[ADVISORY]", "ADVISORY", "[OK]")
READ_CAP = 65536   # the header sits at the top; the rest of a playbook is never read
LINE_CAP = 1000    # a longer line is refused before any pattern runs on it
VALUE_CAP = 120    # a value longer than this is refused, never parsed
SHOW_CAP = 80      # a printed value is cut to this many characters


def sanitize(value, cap=SHOW_CAP):
    """Printable form of a file-borne value: plain printable ASCII only (control, format, line and
    paragraph separator characters dropped, any other non-ASCII character shown as '?'), length
    capped, and a value that would begin with a verdict or loop-control word quoted, so reading a
    file can never forge a ledger row or a control line."""
    out = []
    for c in str(value):
        if " " <= c <= "~":
            out.append(c)
        elif unicodedata.category(c) not in ("Cc", "Cf", "Co", "Cs", "Cn", "Zl", "Zp"):
            out.append("?")
    s = "".join(out).strip()
    if len(s) > cap:
        s = s[:cap] + "..."
    if s.upper().startswith(MARKERS):
        s = "'" + s + "'"
    return s


def semver(text):
    m = SEMVER_RE.match(text)
    return tuple(int(g) for g in m.groups()) if m else None


def stamp(text):
    """`<id>@<x.y.z>` -> (id, (x, y, z)); anything else -> None."""
    ident, at, ver = text.partition("@")
    v = semver(ver) if at else None
    return (ident, v) if v and ID_RE.match(ident) else None


def _key_line(line):
    """(key, value) for a `- <key>: <value>` line at column 0, else None."""
    if not line.startswith("- "):
        return None
    key, colon, value = line[2:].partition(":")
    if not colon or not KEY_RE.match(key):
        return None
    return key, value.strip()


def _key_block(text):
    """The header's key lines [(key, value)] under the title, or a refusal reason."""
    lines = text.splitlines()
    title = next((n for n, ln in unfenced(lines) if ln.startswith("# ")), None)
    if title is None:
        return None, "no title line"
    n = title + 2
    if n >= len(lines) or lines[title + 1].strip() or not _key_line(lines[n]):
        return None, "no header under the title (want one blank line, then the key lines)"
    pairs = []
    while n < len(lines) and lines[n].strip():
        if len(lines[n]) > LINE_CAP:
            return None, "line %d is longer than %d characters" % (n + 1, LINE_CAP)
        kv = _key_line(lines[n])
        if not kv:
            return None, "prose in the header block (line %d is not a key line)" % (n + 1)
        pairs.append(kv)
        n += 1
    return pairs, None


def parse_header(text):
    """(header, None) for a well-formed header, else (None, reason)."""
    pairs, why = _key_block(text)
    if why:
        return None, why
    names = [k for k, _ in pairs]
    extra = [k for k in names if k not in KEYS]
    if extra:
        return None, "extra key %s" % sanitize(extra[0])
    missing = [k for k in KEYS if k not in names]
    if missing:
        return None, "missing key %s" % missing[0]
    if len(names) != len(set(names)):
        return None, "a key is repeated"
    if names != list(KEYS):
        return None, "keys out of order (want %s)" % ", ".join(KEYS)
    val = dict(pairs)
    for k in KEYS:
        if len(val[k]) > VALUE_CAP:
            return None, "%s value longer than %d characters" % (k, VALUE_CAP)
    if not ID_RE.match(val["rollout"]):
        return None, "rollout is not an id: %s" % sanitize(val["rollout"])
    floors = []
    for item in val["plugin"].split(","):
        m = FLOOR_RE.match(item.strip())
        v = semver(m.group(2)) if m else None
        if not v:
            return None, "plugin floor is not <plugin> >=<x.y.z>: %s" % sanitize(item)
        if m.group(1) in [p for p, _ in floors]:
            return None, "plugin %s is named twice; one floor per plugin" % m.group(1)
        floors.append((m.group(1), v))
    if val["from"] not in ("unversioned", "any") and not stamp(val["from"]):
        return None, "from is not <id>@<semver>, unversioned or any: %s" % sanitize(val["from"])
    to = stamp(val["to"])
    if not to:
        return None, "to is not <id>@<semver> (a bare semver is refused): %s" % sanitize(val["to"])
    frm = stamp(val["from"])
    if frm and frm[0] == to[0] and not frm[1] < to[1]:
        return None, "to is not above from"
    after = []
    if val["after"] != "none":
        after = [a.strip() for a in val["after"].split(",")]
        bad = [a for a in after if a == "none" or not ID_RE.match(a)]
        if bad:
            return None, "after is not a list of rollout ids or none: %s" % sanitize(bad[0])
    return {"rollout": val["rollout"], "plugin": floors, "from": val["from"], "to": val["to"],
            "after": after}, None


class Loaded:
    def __init__(self):
        self.count = 0
        self.headers = []
        self.refused = []   # [(file, reason)]
        self.files = {}     # rollout id -> file


def load_playbooks(folder):
    """Read every *.md file of `folder` (no subfolders), parse and check its header, then check
    the chain over the accepted set."""
    r = Loaded()
    try:
        names = sorted(n for n in os.listdir(folder)
                       if n.endswith(".md") and os.path.isfile(os.path.join(folder, n)))
    except OSError:
        return r
    for name in names:
        r.count += 1
        try:
            with open(os.path.join(folder, name), encoding="utf-8-sig", errors="replace") as fh:
                h, why = parse_header(fh.read(READ_CAP))
        except OSError as e:
            h, why = None, "unreadable: %s" % e.strerror
        if h and h["rollout"] in r.files:
            h, why = None, "rollout %s repeats %s" % (h["rollout"], sanitize(r.files[h["rollout"]]))
        if h:
            r.headers.append(h)
            r.files[h["rollout"]] = name
        else:
            r.refused.append((name, why))
    _check_chain(r)
    return r


def _check_chain(r):
    """Within one id, a playbook's `to` is above the `to` of every playbook it presupposes,
    directly or through others (any id) along `after`; a playbook that presupposes itself is
    refused. Checked over the accepted set, so one refusal never cascades."""
    by_id = {h["rollout"]: h for h in r.headers}
    bad = []
    for h in r.headers:
        tid, tver = stamp(h["to"])
        seen, todo, why = set(), list(h["after"]), None
        while todo and not why:
            a = todo.pop()
            if a == h["rollout"]:
                why = "after chain loops back to %s" % a
            if a in seen or a not in by_id or why:
                continue
            seen.add(a)
            p = by_id[a]
            pid, pver = stamp(p["to"])
            if pid == tid and not pver < tver:
                why = "chain not strictly increasing: to %s is not above %s's %s" % (h["to"], a, p["to"])
            todo.extend(p["after"])
        if why:
            bad.append((h, why))
    for h, why in bad:
        r.headers.remove(h)
        r.refused.append((r.files.pop(h["rollout"]), why))


def render_load(r):
    """The load summary lines: the usable count (and the refused count, when any), then one line
    per refused header."""
    if not r.count:
        lines = ["0 playbooks found"]
    else:
        lines = ["%d playbooks loaded" % len(r.headers)
                 + (", %d refused" % len(r.refused) if r.refused else "")]
    for name, why in sorted(r.refused):
        lines.append("header refused: %s: %s" % (sanitize(name), sanitize(why, cap=200)))
    return lines
