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

A lane owes every playbook whose `to` is above its stamp for that id, in `after` order (ties by `to`
ascending): a kit playbook against `SAID.version` (`said@<semver>`), a starter playbook against
`SAID.starter` (`<starter>@<semver>`). An absent stamp owes every playbook of that id.

Kit playbooks come from the `upgrade/` folder of a local checkout of the plugin's own repository
(the manifest names it), starter playbooks from the starter's `upgrade/` folder; each directory is
looked for by name under the lane root, the lane-registry root above it and that root's parent.
A starter's release is the first `## <starter>@<semver>` heading of its CHANGELOG.md. A starter not
found prints `starter <id> not in workspace` with the paths tried; the kit half still prints. An
owed playbook whose floor is above the installed plugin is marked `blocked by plugin`; an unknown
install marks nothing. Nothing here sets a stamp: a stamp is set by hand after a lane's walk.

  --root <lane>       one versions block for the lane
  --registry <root>   one block per lane of the root's lane registry

Read-only: the script never writes a file, and always exits 0 (a usage error included).
"""
import argparse
import json
import os
import re
import selectors
import subprocess
import sys
import time
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import setup_check  # noqa: E402  the lane-block reader and the registry reader
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


# The versions section.

MANIFEST = os.path.join(HERE, "..", "..", ".claude-plugin", "plugin.json")
KIT_ID = "said"
DIR_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
PLUGIN_LIST_TIMEOUT = 10   # seconds for `claude plugin list --json`
PLUGIN_LIST_CAP = 1 << 20  # bytes of its output; past this every version is unknown
LANE_FILE_CAP = 4 << 20    # characters of a CLAUDE.md; a longer one is not read
ANCESTOR_DEPTH = 4         # how far above a lane root a lane registry is looked for
PATH_CAP = 400


def ver(t):
    return ".".join(str(n) for n in t)


def show_path(p):
    return sanitize(p, cap=PATH_CAP)


def physical(p):
    return os.path.realpath(os.path.abspath(p))


def read_text(path, cap=READ_CAP, whole=False):
    """A regular file's text up to `cap` characters, a last line cut by the cap dropped; with
    `whole`, a longer file raises ValueError instead. Raises OSError naming the cause. A FIFO or
    device is never opened, so a read never blocks."""
    if not os.path.isfile(path):
        raise OSError(0, "not a regular file" if os.path.exists(path) else "No such file or directory")
    with open(path, encoding="utf-8-sig", errors="replace") as fh:
        text = fh.read(cap + 1)
    if len(text) <= cap:
        return text
    if whole:
        raise ValueError("%s is longer than %d characters" % (os.path.basename(path), cap))
    return text[:cap].rpartition("\n")[0]


def manifest():
    """(said version tuple or None, kit checkout dir name or None) from the plugin's own manifest."""
    try:
        m = json.loads(read_text(MANIFEST))
        v = semver(str(m.get("version", "")))
        repo = m.get("repository") or ""
        repo = str(repo.get("url", "") if isinstance(repo, dict) else repo)
    except Exception:  # any manifest shape that is not the expected object: version and checkout unknown
        return None, None
    name = repo.rstrip("/").split("/")[-1]
    if name.endswith(".git"):
        name = name[:-4]
    return v, (name if DIR_RE.match(name) and name.strip(".") else None)


def bounded_output(cmd):
    """The stdout of `cmd` as text; raises when it runs past PLUGIN_LIST_TIMEOUT, writes more than
    PLUGIN_LIST_CAP bytes or exits non-zero. The child is killed on any overrun."""
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
    sel = selectors.DefaultSelector()
    sel.register(p.stdout, selectors.EVENT_READ)
    deadline, chunks, size = time.monotonic() + PLUGIN_LIST_TIMEOUT, [], 0
    try:
        while True:
            left = deadline - time.monotonic()
            if left <= 0 or not sel.select(left):
                raise TimeoutError("plugin list timed out")
            chunk = os.read(p.stdout.fileno(), 65536)
            if not chunk:
                break
            size += len(chunk)
            if size > PLUGIN_LIST_CAP:
                raise ValueError("plugin list output too long")
            chunks.append(chunk)
        if p.wait(timeout=max(deadline - time.monotonic(), 0.1)) != 0:
            raise ValueError("plugin list failed")
    finally:
        sel.close()
        if p.poll() is None:
            p.kill()
            p.wait()
        p.stdout.close()
    return b"".join(chunks).decode("utf-8", "replace")


def plugin_list():
    """{plugin name: version tuple} from `claude plugin list --json`; {} when it is not on PATH,
    fails or times out. A name installed at two different versions is left out (unknown)."""
    try:
        rows = json.loads(bounded_output(["claude", "plugin", "list", "--json"]))
    except Exception:  # not on PATH, a timeout, a flood, or output that is not plain JSON: all unknown
        return {}
    seen = {}
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict) or row.get("enabled") is False:
            continue
        name = str(row.get("id", "")).split("@")[0]
        v = semver(str(row.get("version", "")))
        if name and v:
            seen.setdefault(name, set()).add(v)
    return {n: next(iter(vs)) for n, vs in seen.items() if len(vs) == 1}


def lane_stamps(root):
    """(SAID.version value, SAID.starter value, why not read); a value is None for an absent key,
    a missing CLAUDE.md or no lane block, and is the key line's text as written. `why` is set only
    when the file exists but was not read (too long to read whole)."""
    try:
        lines = read_text(os.path.join(root, "CLAUDE.md"), cap=LANE_FILE_CAP, whole=True).splitlines()
    except OSError:
        return None, None, None
    except ValueError as e:
        return None, None, str(e)
    span = setup_check.lane_block_span(lines)
    text = setup_check.keys_text("\n".join(lines[span[0]:span[1]]) if span else "")
    vals = [setup_check.axis_value(text, k) for k in ("SAID.version", "SAID.starter")]
    return tuple(v if v else None for v in vals) + (None,)


def registry_rows(root):
    """[(token, lane root as written)] of the lane registry in <root>/CLAUDE.md; raises ValueError
    with the reason when the registry is refused or the reader is unavailable."""
    st = setup_check.said_status
    if st is None or not hasattr(st, "read_lane_registry"):
        raise ValueError("registry reader unavailable")
    md = os.path.join(root, "CLAUDE.md")
    if not os.path.isfile(md):
        return []
    if os.path.getsize(md) > LANE_FILE_CAP:
        raise ValueError("CLAUDE.md is longer than %d characters" % LANE_FILE_CAP)
    try:
        return st.read_lane_registry(root)[0]
    except st.RegistryRefused as e:
        raise ValueError("registry refused: %s" % e)


def registry_root(lane_root):
    """The nearest directory, the lane root or up to three levels above it, whose CLAUDE.md declares
    a lane registry; else the lane root's parent."""
    d = lane_root
    for _ in range(ANCESTOR_DEPTH):
        try:
            if registry_rows(d):
                return d
        except ValueError:
            pass
        up = os.path.dirname(d)
        if up == d:
            break
        d = up
    return os.path.dirname(lane_root)


def search_roots(lane_root, reg_root):
    roots = []
    for r in (lane_root, reg_root, os.path.dirname(reg_root)):
        if r not in roots:
            roots.append(r)
    return roots


def find_dir(name, roots):
    """(physical path or None, [paths tried]) for a directory named exactly `name`."""
    tried = [os.path.join(r, name) for r in roots]
    for p in tried:
        if os.path.isdir(p):
            return physical(p), tried
    return None, tried


def starter_release(folder, ident):
    """(version tuple, None) from the first `## <id>@<semver>` heading of folder/CHANGELOG.md, else
    (None, cause)."""
    try:
        lines = read_text(os.path.join(folder, "CHANGELOG.md")).splitlines()
    except OSError as e:
        return None, e.strerror or type(e).__name__
    for _, ln in unfenced(lines):
        if ln.startswith("## "):
            s = stamp((ln[3:].split() or [""])[0])
            if s and s[0] == ident:
                return s[1], None
    return None, "no ## %s@<semver> heading in CHANGELOG.md" % ident


def owed(headers, stamps):
    """The headers a lane owes, in `after` order with ties by `to` ascending. `stamps` maps an id to
    the lane's version tuple for it; an id without a stamp owes every playbook of that id."""
    due = []
    for h in headers:
        tid, tver = stamp(h["to"])
        have = stamps.get(tid)
        if have is None or tver > have:
            due.append(h)
    ids = {h["rollout"] for h in due}
    deps = {h["rollout"]: {a for a in h["after"] if a in ids} for h in due}
    key = lambda h: (stamp(h["to"])[1], stamp(h["to"])[0], h["rollout"])
    order, done = [], set()
    while len(order) < len(due):
        ready = sorted((h for h in due if h["rollout"] not in done and deps[h["rollout"]] <= done), key=key)
        if not ready:   # a loop the chain check missed: the rest by `to`
            ready = sorted((h for h in due if h["rollout"] not in done), key=key)
        order.append(ready[0])
        done.add(ready[0]["rollout"])
    return order


def owes_lines(label, loaded, stamps, installed):
    if not loaded.headers:
        why = "all %d playbooks refused" % loaded.count if loaded.count else "no playbooks"
        return ["%s owes: not computed (%s)" % (label, why)]
    due = owed(loaded.headers, stamps)
    lines = ["%s owes: %s" % (label, ", ".join(h["rollout"] for h in due) if due else "none")]
    for h in due:
        short = ["plugin %s >=%s (installed %s)" % (p, ver(v), ver(installed[p]))
                 for p, v in h["plugin"] if installed.get(p) is not None and installed[p] < v]
        if short:
            lines.append("  %s blocked by %s" % (h["rollout"], ", ".join(short)))
    return lines


class Section:
    """One run: the manifest, the plugin list and every playbook folder are read once."""

    def __init__(self):
        self.said_v, self.kit_dir = manifest()
        self._plugins = None
        self._loads = {}
        self._starters = {}

    def installed(self, names):
        out = {KIT_ID: self.said_v}
        others = [n for n in names if n != KIT_ID]
        if others and self._plugins is None:
            self._plugins = plugin_list()
        for n in others:
            out[n] = self._plugins.get(n)
        return out

    def load(self, folder):
        if folder not in self._loads:
            self._loads[folder] = load_playbooks(folder)
        return self._loads[folder]

    def block(self, lane_root, reg_root, title):
        lane_root = physical(lane_root)
        reg_root = physical(reg_root) if reg_root else registry_root(lane_root)
        roots = search_roots(lane_root, reg_root)
        ver_raw, st_raw, unread = lane_stamps(lane_root)
        lines = ["versions: %s" % title(show_path(lane_root))]
        if unread:
            lines.append("  lane block not read: %s" % sanitize(unread, cap=200))
        stamps = {}

        kit_stamp = stamp((ver_raw or "").split()[0]) if ver_raw and ver_raw.split() else None
        if ver_raw is None:
            lines.append("  SAID.version: -")
        elif kit_stamp and kit_stamp[0] == KIT_ID:
            stamps[KIT_ID] = kit_stamp[1]
            lines.append("  SAID.version: %s" % sanitize(ver_raw))
        else:
            lines.append("  SAID.version: %s (not a said@ stamp; kit playbooks owed as unversioned)"
                         % sanitize(ver_raw))

        st = stamp(st_raw.split()[0]) if st_raw and st_raw.split() else None
        st = st if st and st[0] != KIT_ID else None   # the kit id is never a starter
        if st_raw is None:
            lines.append("  SAID.starter: -")
        elif st:
            stamps[st[0]] = st[1]
            lines.append("  SAID.starter: %s" % sanitize(st_raw))
        else:
            lines.append("  SAID.starter: %s (not a starter <id>@<semver> stamp; no starter lookup)"
                         % sanitize(st_raw))

        kit_lines, kit_load = self.kit(roots)
        st_lines, st_load = self.starter(st, roots) if st else ([], None)
        names = sorted({p for r in (kit_load, st_load) if r for h in r.headers for p, _ in h["plugin"]})
        installed = self.installed(names)
        shown = [KIT_ID] + [n for n in names if n != KIT_ID]
        lines.append("  installed: " + ", ".join(self.installed_text(n, installed, stamps) for n in shown))
        lines += ["  " + ln for ln in st_lines[:1]]
        lines += ["  " + ln for ln in kit_lines]
        lines += ["  " + ln for ln in owes_lines("kit", kit_load, stamps, installed)]
        if st_load is not None:
            lines += ["  " + ln for ln in st_lines[1:]]
            lines += ["  " + ln for ln in owes_lines("starter", st_load, stamps, installed)]
        return lines

    def installed_text(self, name, installed, stamps):
        v = installed.get(name)
        if v is None:
            return "%s installed version unknown" % name
        if name != KIT_ID:
            return "%s %s" % (name, ver(v))
        s = stamps.get(KIT_ID)
        if s is None:
            delta = "no said@ stamp"
        else:
            delta = "stamp said@%s: installed %s" % (ver(s), "above the stamp" if v > s else
                                                    "at the stamp" if v == s else "below the stamp")
        return "said %s (%s)" % (ver(v), delta)

    def kit(self, roots):
        if not self.kit_dir:
            empty = Loaded()
            return ["kit playbooks: no repository named in the plugin manifest"] + render_load(empty), empty
        found, tried = find_dir(self.kit_dir, roots)
        if not found:
            empty = Loaded()
            return (["kit playbooks: no local checkout (tried: %s)" % ", ".join(show_path(p) for p in tried)]
                    + render_load(empty), empty)
        folder = os.path.join(found, "upgrade")
        r = self.load(folder)
        return ["kit playbooks: %s" % show_path(folder)] + render_load(r), r

    def starter(self, st, roots):
        """([lookup line, then the starter playbook lines], loaded or None) for starter `st`."""
        ident = st[0]
        found, tried = find_dir(ident, roots)
        if not found:
            shared = tuple(tried[1:])   # the paths every lane under one registry root shares
            if (ident, shared) in self._starters:
                paths = "tried: %s; other paths as above" % show_path(tried[0])
            else:
                paths = "tried: %s" % ", ".join(show_path(p) for p in tried)
            self._starters[(ident, shared)] = True
            return ["starter %s not in workspace (%s)" % (ident, paths)], None
        rel, why = starter_release(found, ident)
        line = "starter %s: %s, %s" % (ident, show_path(found), "release %s@%s" % (ident, ver(rel)) if rel
                                       else "release unreadable: %s" % sanitize(why, cap=200))
        folder = os.path.join(found, "upgrade")
        r = self.load(folder)
        return [line, "starter playbooks: %s" % show_path(folder)] + render_load(r), r


def run_root(root):
    s = Section()
    return s.block(root, None, lambda p: p)


def run_registry_section(root):
    root = physical(root)
    try:
        rows = registry_rows(root)
    except ValueError as e:
        return ["versions: %s" % sanitize(str(e), cap=200)]
    if not rows:
        return ["versions: no lane registry in %s" % show_path(os.path.join(root, "CLAUDE.md"))]
    s = Section()
    lines = []
    for token, lane_dir in rows:
        tok = sanitize(token)
        try:
            lines += s.block(os.path.join(root, lane_dir), root, lambda p, t=tok: "%s %s" % (t, p))
        except Exception as e:  # one lane's failure never hides the other lanes
            lines.append("versions: %s error: %s" % (tok, type(e).__name__))
    return lines


class Parser(argparse.ArgumentParser):
    def error(self, message):  # a usage error is one versions line, never a non-zero exit
        print("versions: usage error: %s" % sanitize(message, cap=200))
        sys.exit(0)


def main():
    ap = Parser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--root", default=".", help="lane root: one block for the lane")
    g.add_argument("--registry", help="root of a lane registry: one block per registry lane")
    a = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    try:
        lines = run_registry_section(a.registry) if a.registry else run_root(a.root)
    except Exception as e:  # never a traceback and never a non-zero exit: the section is advisory
        lines = ["versions: error: %s" % type(e).__name__]
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
