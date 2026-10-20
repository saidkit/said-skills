#!/usr/bin/env python3
"""Deterministic well-formed-lane checker for said:setup (read-only).

Reads a lane's CLAUDE.md ## Lane block + required sections and evaluates them
against the machine-readable schema (references/lane-schema.json, read WHOLE).
Emits a per-item ledger grouped by severity and exits non-zero when any BLOCKER
is present, so said:setup renders findings deterministically rather than by
judgement, and the same oracle backs the eval's negative control.

Reviewer resolvability reuses the canonical Checker resolver shipped beside this
file (../status/said_status.py: index_checkers / resolve_checkers_dir), rather
than re-implementing it. The lane-block parse lives here: one block locator (a
heading that is exactly "## Lane", outside code fences) and one value read (a
key's value is the rest of its own line; an empty value is no value).

Plugin-shipped: paths resolve relative to this file's own install location, so
the checker works whether or not the target repo vendors the plugin.
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# Reuse the canonical Checker resolver from the sibling status skill (same plugin).
sys.path.insert(0, os.path.join(HERE, "..", "status"))
try:
    import said_status  # noqa: E402
except Exception:  # pragma: no cover - resolver optional; reviewers check degrades to a note
    said_status = None

DEFAULT_SCHEMA = os.path.join(HERE, "references", "lane-schema.json")
SEV_ORDER = {"BLOCKER": 0, "STALE": 1, "ADVISORY": 2}


def load_schema(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


LANE_HEADING = "## Lane"
FENCE_RE = re.compile(r"^[ \t]*(`{3,}|~{3,})(.*)$")


def unfenced(lines):
    """Yield (index, line) for every line outside a code fence; a fence line is skipped."""
    fence = None
    for n, ln in enumerate(lines):
        if said_status is not None and hasattr(said_status, "fence_step"):
            marker, fence = said_status.fence_step(fence, ln)  # one fence rule for the checker and the reader
        else:
            m = FENCE_RE.match(ln)
            marker = bool(m) and (fence is None or m.group(1)[0] == fence[0])
            fence = (None if fence else m.group(1)) if marker else fence
        if not marker and not fence:
            yield n, ln


def lane_block_span(lines):
    """Return (start, end) line indexes of the lane block's body, or None.

    The block sits under a heading that is exactly '## Lane' at column 0, outside
    code fences, and runs to the next '## ' heading outside a fence or to EOF. A
    heading such as '## Lane web' or '## Lanes' is not the lane block; neither is
    a '## Lane' line shown inside a fenced example."""
    start = None
    for n, ln in unfenced(lines):
        if start is None:
            if ln.rstrip() == LANE_HEADING:
                start = n + 1
        elif ln.startswith("## "):
            return start, n
    return (start, len(lines)) if start is not None else None


def read_lane_block(claude_md):
    """Return (full_text, block_text); block_text is '' if there is no lane block."""
    with open(claude_md, encoding="utf-8-sig", errors="replace") as fh:
        text = fh.read()  # a byte-order mark or a stray byte does not stop the check
    lines = text.splitlines()
    span = lane_block_span(lines)
    return text, ("\n".join(lines[span[0]:span[1]]) if span else "")


def axis_value(block, key):
    """Return the value of SAID.<key> in the block: the rest of the key's own line,
    '' when the line carries no value, None when the key is absent. The read never
    crosses the line end, so an empty value is not taken from the line below."""
    m = re.search(r"^[ \t]*[-*]?[ \t]*%s:[ \t]*(.*?)[ \t]*$" % re.escape(key), block, re.M)
    return m.group(1) if m else None


def parse_reviewers(val):
    """Parse a list value like '[cli-gate, web-ux]' into ['cli-gate','web-ux']."""
    if not val:
        return []
    inner = val.strip().strip("[]")
    return [r.strip() for r in inner.split(",") if r.strip()]



KEYSHAPE_RE = re.compile(r"^[ \t]*[-*]?[ \t]*(SAID\.[\w-]+):")
ASIDE = r"#|\s--\s|\s\(|\.\.\."   # a trailing comment, aside or parenthetical on a key line


def indent_col(line):
    """A line's indent in columns (a tab counts four)."""
    return len(line[:len(line) - len(line.lstrip(" \t"))].expandtabs(4))


def off_column_keys(block):
    """Key-shaped lines of the block, outside code fences, that sit off the key list's column
    (the indent of the block's first key-shaped line): [(index, key)], index into the block's
    lines. Such a line is an annotation under a key, not a key line, and is never read."""
    shaped = [(n, ln) for n, ln in unfenced(block.splitlines()) if KEYSHAPE_RE.match(ln)]
    if not shaped:
        return []
    col = indent_col(shaped[0][1])
    return [(n, KEYSHAPE_RE.match(ln).group(1)) for n, ln in shaped if indent_col(ln) != col]


def keys_text(block):
    """The block's key lines and what sits around them, outside code fences and without the
    key-shaped lines indented off the key list: where a key, live or withdrawn, is read."""
    off = {n for n, _ in off_column_keys(block)}
    return "\n".join(ln for n, ln in unfenced(block.splitlines()) if n not in off)


def cut_aside(value):
    """A scalar value without a trailing comment, aside or parenthetical."""
    m = re.search(ASIDE, value)
    return value[:m.start()].rstrip() if m else value


def is_none_word(item):
    """True for the word none in any case, bare or quoted."""
    return item.strip().strip("\"'`").lower() == "none"


def read_path_list(value):
    """Read a path-list value leniently, for the finding and for the line to write. Return a
    dict: form ('bare-none' | 'none-word' | 'note-only' | 'unreadable' | 'unbracketed' |
    'list'); paths (the paths in order with none words left out, or None when an item is
    not one plain path); noted (a comment, aside or parenthetical rides on the value);
    after (text follows the closing bracket); empty_item; none_inside."""
    r = {"form": "list", "paths": None, "noted": False, "after": False, "empty_item": False, "none_inside": False}
    v = value.strip()
    if v == "none":
        r["form"] = "bare-none"
        return r
    bare = re.sub(r"\s*\([^()]*\)", "", v).strip()  # parentheticals leave first: they may hold brackets
    r["noted"] = bare != v
    if bare.startswith("["):
        close = bare.find("]")
        inner, tail = bare[1:close], bare[close + 1:].strip()
        if close == -1 or "[" in inner or (tail and not tail.startswith("#") and re.search(r"[\[\]]", tail)):
            r["form"] = "unreadable"
            return r
        if tail:
            r["after"] = r["noted"] = True
    else:
        r["form"] = "unbracketed"
        if "#" in bare:
            bare, r["noted"] = bare[:bare.index("#")].rstrip(), True
        if re.search(r"[\[\]]", bare):
            r["form"] = "unreadable"
            return r
        inner = bare
    items = []
    for item in inner.split(","):
        m = re.search(r"#|\s--(\s|$)|\.\.\.", item)
        if m:
            item, r["noted"] = item[:m.start()], True
        items.append(item.strip())
    if r["form"] == "unbracketed" and len(items) == 1:
        if not items[0]:
            r["form"] = "note-only"
            return r
        if is_none_word(items[0]):
            r["form"] = "none-word"
            return r
    r["empty_item"] = any(not x for x in items)
    r["none_inside"] = any(is_none_word(x) for x in items)
    kept = [x for x in items if x and not is_none_word(x)]
    if all(len(x.split()) == 1 and not re.search(r"[\"'`()]", x) for x in kept):
        r["paths"] = kept
    return r


def check_path_list(key, val):
    """Judge the spelling of a path-list value (never the paths themselves). Return None
    when it is well formed, else (verdict, severity, remediation). One finding per value: a
    note on the line is reported here, not by the one-line-value invariant."""
    r = read_path_list(val)
    if r["form"] == "bare-none":
        return None
    if r["paths"] is None:
        advice = "%s: [<path>, <path>]" % key
    elif r["paths"]:
        advice = "%s: [%s]" % (key, ", ".join(r["paths"]))
    else:
        advice = "%s: [<path>] or %s: none" % (key, key)
    if r["form"] == "note-only":
        return ("missing", "BLOCKER", "the value of %s is only a note, so the key counts as missing; write %s: "
                "[<path>, <path>]" % (key, key))
    if r["form"] == "unreadable":
        return ("missing", "BLOCKER", "the value of %s has a stray, unbalanced or nested bracket and cannot be read, "
                "so the key counts as missing; write %s: [<path>, <path>]" % (key, key))
    if r["form"] == "none-word":
        return ("stale", "STALE", "none is the bare word in lower case, with no quotes and no note; write %s: none" % key)
    if r["form"] == "unbracketed":
        return ("stale", "STALE", "write the value of %s in brackets, with no note beside it: %s" % (key, advice))
    if r["after"]:
        return ("stale", "STALE", "the value of %s carries text after its closing bracket; a value carries no "
                "note; write %s" % (key, advice))
    if r["empty_item"]:
        return ("stale", "STALE", "the value of %s carries an empty item; write %s" % (key, advice))
    if r["none_inside"]:
        return ("stale", "STALE", "none is written bare, never in brackets or beside a path; write %s" % advice)
    if r["paths"] is None:
        return ("stale", "STALE", "an item of %s is not one path; separate paths with commas and keep notes out of "
                "the value; write %s" % (key, advice))
    if r["noted"]:
        return ("stale", "STALE", "the value of %s carries a note beside a path; a value carries no note; write %s"
                % (key, advice))
    return None


def check_registry(key, text, lines, span, claude_md):
    """Judge the lane registry through the one reader the plugin ships, so the checker and a
    reader give one verdict. Return (findings, open): findings is a list of (verdict, severity,
    remediation), empty when there is nothing to report, ("ok", "OK", "") for a well-formed
    registry; open is True when the file declares no registry or the block the empty one. A registry in another shape (rows, a table or sub-bullets beneath the line, a
    line indented as a sub-bullet) is one BLOCKER wherever the line sits in the block."""
    key_re = re.compile(r"^[ \t]*[-*]?[ \t]*%s:" % re.escape(key))
    inside = range(span[0], span[1]) if span else range(0)
    outside = [n for n, ln in unfenced(lines) if n not in inside and key_re.match(ln)]
    stray = [("stale", "STALE", "a %s: line outside the ## Lane block (line %d) is read by nothing; the registry "
              "is one key line inside the block" % (key, outside[0] + 1))] if outside else []
    reader = said_status is not None and hasattr(said_status, "read_registry_text")
    if not reader:
        declared = any(key_re.match(ln) for n, ln in unfenced(lines) if n in inside)
        return stray + ([("unresolvable", "ADVISORY", "reader unavailable (../status/said_status.py not importable); "
                          "the registry line was not checked")] if declared else []), not (declared or stray)
    if said_status.locate_lane_registry(text) is None:
        return stray, not stray  # a line outside the block is the registry misplaced, not absent
    try:
        rows = said_status.read_registry_text(text)
    except said_status.RegistryRefused as e:
        if e.kind == "twice":
            return stray, False  # the list-key-once invariant reports it; no row is read
        if e.kind == "empty":
            return stray + [("stale", "STALE", "%s" % e)], True
        return stray + [("stale", "BLOCKER", "the registry line is not read: %s; a registry is one key line, "
                         "%s: [TOKEN=root, TOKEN=root]" % (e, key))], False
    out, unread = list(stray), 0
    base = os.path.dirname(os.path.abspath(claude_md))
    for token, lane_root in rows:
        target = os.path.join(base, lane_root, "CLAUDE.md")
        try:
            with open(target, encoding="utf-8-sig", errors="replace") as fh:
                has_block = said_status.lane_block_lines(fh.read()) is not None
        except (OSError, ValueError):
            has_block = False
        if not has_block:
            unread += 1
            if unread <= 50:  # the report stays readable on any registry
                out.append(("stale", "STALE", "the root %s of %s holds no lane block; a reader skips that row" % (lane_root, token)))
    if unread > 50:
        more = unread - 50
        out.append(("stale", "STALE", "and %d more %s no lane block" % (more, "root holds" if more == 1 else "roots hold")))
    return out or [("ok", "OK", "")], False



SKIP_DIRS = {"node_modules", "__pycache__", "venv", "vendor", "dist", "build", "target", "site-packages"}


def legal_token(raw):
    """A registry token from a name: its letters and digits upper-cased, or None when that
    does not start with a letter."""
    t = re.sub(r"[^A-Za-z0-9]", "", raw or "").upper()
    return t if re.match(r"[A-Z]", t) else None


def root_name_ok(name):
    """True when a directory name can stand as a registry root as written: valid UTF-8, no
    character the registry grammar ends a root at, and, where the reader is present, a pair
    the reader parses back unchanged."""
    try:
        name.encode("utf-8")
    except UnicodeEncodeError:
        return False
    if re.search(r"[\s,\]\[=;\x00-\x1f\x7f\ufffd]", name):
        return False
    if said_status is not None and hasattr(said_status, "parse_lane_registry"):
        try:
            return said_status.parse_lane_registry("[A=%s/]" % name) == [("A", name + "/")]
        except Exception:
            return False
    return True


def discover_lanes(base, keys):
    """The lanes one level beneath a root with no registry, `base` being the directory of the
    root's CLAUDE.md: ([(token, root)] in directory-name order, [dir/ not listed]). A lane is
    an immediate subdirectory whose CLAUDE.md carries a ## Lane block; a dot-directory, a
    dependency or build directory, the root's own docs root, the root itself, a second link
    to a lane already listed and a copy of the root's own lane are skipped. A lane whose name
    a root cannot carry, or whose CLAUDE.md cannot be read, is not listed and is named."""
    own = cut_aside((axis_value(keys, "SAID.lane") or "").strip())
    docs = cut_aside((axis_value(keys, "SAID.docs-root") or "docs").strip()) or "docs"
    skip_real = {os.path.realpath(os.path.join(base, docs)), os.path.realpath(base)}
    try:
        names = sorted(os.listdir(base))
    except OSError:
        return [], []
    rows, left, taken = [], [], set()
    for name in names:
        d = os.path.join(base, name)
        if name.startswith(".") or name in SKIP_DIRS or not os.path.isdir(d):
            continue
        real = os.path.realpath(d)
        if real in skip_real:
            continue
        try:
            with open(os.path.join(d, "CLAUDE.md"), encoding="utf-8-sig", errors="replace") as fh:
                lines = fh.read().splitlines()
        except FileNotFoundError:
            continue
        except (OSError, ValueError):
            left.append(name + "/")
            continue
        span = lane_block_span(lines)
        if span is None:
            continue
        value = cut_aside((axis_value(keys_text("\n".join(lines[span[0]:span[1]])), "SAID.lane") or "").strip())
        if own and value == own:
            continue
        if not root_name_ok(name):
            left.append(name.encode("utf-8", "replace").decode("utf-8") + "/")
            continue
        skip_real.add(real)
        base_token = legal_token(value) or legal_token(name) or legal_token("L" + name)
        if base_token is None:
            continue
        token, n = base_token, 1
        while token in taken:
            n += 1
            token = "%s%d" % (base_token, n)
        taken.add(token)
        rows.append((token, name + "/"))
    return rows, left


def discovery_finding(key, found, left, row=None):
    """The registry finding that carries the discovered lanes and the line to write: `row`
    (the empty registry's finding) extended, else a new ADVISORY row. `left` names the lanes
    not listed."""
    line = "write: %s: [%s]" % (key, ", ".join("%s=%s" % p for p in found))
    if left:
        line = ("not listed: %s (a name a registry root cannot carry, or a CLAUDE.md that cannot be read); %s"
                % (", ".join(left), line))
    if row is None:
        row = {"item": key, "verdict": "missing", "severity": "ADVISORY",
               "remediation": "no registry, and %d %s one level beneath this root (%s); add the registry line to "
                              "the ## Lane block" % (len(found), "lane sits" if len(found) == 1 else "lanes sit",
                                                     ", ".join(r for _, r in found))}
    row["remediation"] = "%s; %s" % (row["remediation"], line)
    row["discovered"] = [{"token": t, "root": r} for t, r in found]
    return row


def successor_line(old_value, successor, schema):
    """The line that replaces a withdrawn key, when its successor is one schema key and the
    old value yields a line that can be written as it stands; else None. A note beside the
    old value is not carried, and no path is ever dropped to make a line."""
    row = [a for a in schema["axes"] if a["key"] == successor]
    if not row or old_value is None or not old_value.strip():
        return None
    if row[0].get("value") != "path-list":
        v = cut_aside(old_value.strip())
        return "%s: %s" % (successor, v) if v else None
    r = read_path_list(old_value)
    if r["form"] in ("bare-none", "none-word"):
        return "%s: none" % successor
    if r["form"] in ("note-only", "unreadable") or r["paths"] is None:
        return None
    if r["paths"]:
        return "%s: [%s]" % (successor, ", ".join(r["paths"]))
    return "%s: none" % successor if r["none_inside"] else None


def has_section(text, heading, match):
    if match == "exact":
        return any(ln.rstrip() == heading for _, ln in unfenced(text.splitlines()))
    # leading-words: a '## ' heading whose text starts with the heading's words
    words = heading[len("## "):].strip()
    return re.search(r"^##\s+%s\b" % re.escape(words), text, re.M) is not None


def resolve_reviewers(lane_root, docs_root):
    """Return the Checker index (id -> meta) via the shipped resolver, or None
    if the resolver is unavailable."""
    if said_status is None:
        return None
    cdir = said_status.resolve_checkers_dir(lane_root, None)
    cdir_abs = cdir if os.path.isabs(cdir) else os.path.join(lane_root, cdir)
    recipe = os.path.join(lane_root, docs_root, "ux", "feature-ux-rules.md") if docs_root else None
    recipe = recipe if recipe and os.path.isfile(recipe) else None
    return said_status.index_checkers(cdir_abs, recipe)


def check_block_invariants(block, schema, text=None, skip=(), ignore=()):
    """Evaluate the block-shape invariants (STALE): a scalar key declared twice in the
    block or named again anywhere in the file, a list key declared twice in the block,
    a key line carrying a trailing comment/parenthetical/aside, or prose between key
    lines. Prose ABOVE the first key or BELOW the last is allowed (a lane may say what
    it is / how it routes); only lines strictly between keys must be key lines. A key line
    sits at the key list's column; `skip` holds the indexes of lines another finding already
    reports (a key-shaped line indented off the list, what sits beneath the registry), and
    `ignore` the same lines as indexes into the file, for the file-wide naming count. A
    key-shaped line inside a code fence is an example, never a declaration."""
    out = []
    inv = {i["id"]: i for i in schema.get("block_invariants", [])}
    lines = block.splitlines()
    keyline_re = re.compile(r"^\s*[-*]?\s*SAID\.[\w-]+:")
    off = {n for n, _ in off_column_keys(block)}
    plain = {n for n, _ in unfenced(lines)}
    key_idx = [n for n, ln in enumerate(lines) if keyline_re.match(ln) and n in plain and n not in off]
    graded = ({a["key"] for a in schema["axes"] if a.get("value") in ("path-list", "registry")}  # their value grammar reports a note itself
              | {w["key"] for w in schema.get("withdrawn_axes", []) if w.get("superseded_by")})  # so does a stale row's line
    list_keys = {a["key"] for a in schema["axes"] if a.get("kind") == "list"}
    counts = {}
    for n in key_idx:
        k = re.search(r"SAID\.[\w-]+", lines[n]).group(0)
        counts[k] = counts.get(k, 0) + 1
    if "single-hit-scalar" in inv:
        rule = inv["single-hit-scalar"]
        reported = set()
        for k, c in counts.items():
            if c > 1 and k not in list_keys:
                reported.add(k)
                out.append({"item": "invariant:single-hit-scalar", "verdict": "stale", "severity": rule["severity"],
                            "remediation": "%s is declared %d times; %s" % (k, c, rule["rule"])})
        # a scalar key is named once in the FILE: a second naming anywhere (prose above or below
        # the block, a fenced example) is what an unanchored key-grep would read instead
        file_lines = (text if text is not None else block).splitlines()
        for ax in schema["axes"]:
            k = ax["key"]
            if ax.get("kind") == "list" or k in reported:
                continue
            named = sum(1 for n, ln in enumerate(file_lines) if (k + ":") in ln and n not in ignore)
            if named > 1:
                out.append({"item": "invariant:single-hit-scalar", "verdict": "stale", "severity": rule["severity"],
                            "remediation": "%s is named %d times in the file; %s" % (k, named, rule["rule"])})
    if "list-key-once" in inv:
        rule = inv["list-key-once"]
        for k, c in counts.items():
            if c > 1 and k in list_keys:
                out.append({"item": "invariant:list-key-once", "verdict": "stale", "severity": rule["severity"],
                            "remediation": "%s is declared %d times in the block; %s" % (k, c, rule["rule"])})
    if "one-line-value" in inv:
        for n in key_idx:
            if re.search(r"SAID\.[\w-]+", lines[n]).group(0) in graded:
                continue
            if re.search(r"SAID\.[\w-]+:\s*\S.*(%s)" % ASIDE, lines[n]):
                out.append({"item": "invariant:one-line-value", "verdict": "stale",
                            "severity": inv["one-line-value"]["severity"],
                            "remediation": "a key line carries a trailing comment/parenthetical/aside; %s" % inv["one-line-value"]["rule"]})
                break
    if "keys-only-block" in inv and key_idx:
        for n in range(key_idx[0], key_idx[-1] + 1):
            if n in skip or n in off:
                continue
            if lines[n].strip() and not keyline_re.match(lines[n]):
                out.append({"item": "invariant:keys-only-block", "verdict": "stale",
                            "severity": inv["keys-only-block"]["severity"],
                            "remediation": "non-key line between keys (%r); %s" % (lines[n].strip()[:40], inv["keys-only-block"]["rule"])})
                break
    return out


def below_floor(digits, floor):
    """digits already matched [1-9][0-9]*: compare by length, then digit by digit (no int(), so no size limit)."""
    f = str(floor)
    return len(digits) < len(f) or (len(digits) == len(f) and digits < f)


def check_lane(lane_root, schema, claude_md=None):
    """Evaluate the lane at lane_root against schema. Return a list of findings:
    dicts {item, verdict, severity, remediation}. verdict in ok/stale/missing/unresolvable."""
    claude_md = claude_md or os.path.join(lane_root, "CLAUDE.md")
    findings = []
    if not os.path.isfile(claude_md):
        findings.append({"item": "CLAUDE.md", "verdict": "missing", "severity": "BLOCKER",
                         "remediation": "no CLAUDE.md at the lane root; the lane is invisible to the cycle"})
        registry_key = next((a["key"] for a in schema["axes"] if a.get("value") == "registry"), None)
        found, left = discover_lanes(os.path.dirname(os.path.abspath(claude_md)), "") if registry_key else ([], [])
        if found:
            findings.append(discovery_finding(registry_key, found, left))
        return findings
    text, block = read_lane_block(claude_md)

    # Required sections
    for sec in schema["required_sections"]:
        present = has_section(text, sec["heading"], sec.get("match", "leading-words"))
        findings.append({"item": sec["heading"], "verdict": "ok" if present else "missing",
                         "severity": sec["severity_if_missing"] if not present else "OK",
                         "remediation": "" if present else sec["remediation"]})

    lines = text.splitlines()
    span = lane_block_span(lines)
    keys = keys_text(block)
    surface = axis_value(keys, "SAID.surface")
    # Axes
    for ax in schema["axes"]:
        val = axis_value(keys, ax["key"])
        if ax.get("value") == "registry":
            rows, open_ = check_registry(ax["key"], text, lines, span, claude_md)
            rows = [{"item": ax["key"], "verdict": v, "severity": sev, "remediation": r} for v, sev, r in rows]
            found, left = discover_lanes(os.path.dirname(os.path.abspath(claude_md)), keys) if open_ else ([], [])
            empty = [f for f in rows if f["severity"] == "STALE" and f["remediation"] == getattr(said_status, "EMPTY_REGISTRY", None)]
            if found and empty:
                discovery_finding(ax["key"], found, left, empty[0])
            elif found:
                rows.append(discovery_finding(ax["key"], found, left))
            findings.extend(rows)
            continue
        present = val is not None and val != ""
        if present and ax.get("kind") == "list" and re.fullmatch(r"\[[\s,]*\]", val.strip()):
            present = False  # an empty list is not a declared value; a surface-bearing lane with reviewers: [] is a nominal gate
        required = ax.get("required", False)
        if ax.get("required_if") == "surface != none":
            required = (surface not in (None, "", "none"))
        problem = check_path_list(ax["key"], val) if present and ax.get("value") == "path-list" else None
        if present and ax.get("value") == "positive-integer" and not re.fullmatch(r"[1-9][0-9]*", cut_aside(val.strip())):
            shown = cut_aside(val.strip()).encode("unicode_escape").decode("ascii")
            shown = shown if len(shown) <= 40 else shown[:37] + "..."
            problem = ("unresolvable", ax.get("severity_if_invalid", "BLOCKER"),
                       "declared %s: %s -- %s" % (ax["key"], shown, ax["remediation_if_invalid"]))
        elif present and ax.get("value") == "positive-integer" and isinstance(ax.get("floor"), int) \
                and below_floor(cut_aside(val.strip()), ax["floor"]):
            problem = ("unresolvable", ax.get("severity_if_below", "ADVISORY"),
                       "declared %s: %s is below the floor %d -- %s"
                       % (ax["key"], cut_aside(val.strip()), ax["floor"], ax["remediation_if_below"]))
        if problem:
            findings.append({"item": ax["key"], "verdict": problem[0], "severity": problem[1], "remediation": problem[2]})
        elif present:
            findings.append({"item": ax["key"], "verdict": "ok", "severity": "OK", "remediation": ""})
        elif required:
            findings.append({"item": ax["key"], "verdict": "missing", "severity": ax["severity_if_missing"],
                             "remediation": ax["remediation"]})
        # absent + not required: not reported (a clean omission of an optional axis)

    # Withdrawn axes: looked for where a live key is read, inside the lane block and outside fences
    for w in schema["withdrawn_axes"]:
        old = axis_value(keys, w["key"])
        if old is not None:
            remediation = w["remediation"]
            if w.get("superseded_by"):
                remediation = "superseded by %s; %s" % (w["superseded_by"], remediation)
                line = successor_line(old, w["superseded_by"], schema)
                if line:
                    remediation += "; write: %s" % line
            findings.append({"item": w["key"], "verdict": "stale", "severity": w["severity"],
                             "remediation": remediation})

    # Block-shape invariants
    skip, registry_key = set(), next((a["key"] for a in schema["axes"] if a.get("value") == "registry"), None)
    loc = said_status.locate_lane_registry(text) if said_status is not None and hasattr(said_status, "locate_lane_registry") else None
    if loc and span:
        skip = {n - span[0] for n in loc["beneath"]}
    rule = {i["id"]: i for i in schema.get("block_invariants", [])}.get("keys-only-block")
    off = off_column_keys(block)
    for n, k in off:
        if rule and k != registry_key and n not in skip:  # the registry's lines are the registry's own BLOCKER
            findings.append({"item": "invariant:keys-only-block", "verdict": "stale", "severity": rule["severity"],
                             "remediation": "%s: on line %d is indented off the key list, as a sub-bullet under another "
                                            "key; it is an annotation, not a key line, and is not read; %s"
                                            % (k, span[0] + n + 1, rule["rule"])})
    owned = {n for n, _ in off} | skip
    findings.extend(check_block_invariants(block, schema, text, skip, {span[0] + n for n in owned} if span else ()))

    # Reviewer resolvability (surface-bearing lanes)
    if surface not in (None, "", "none"):
        reviewers = parse_reviewers(axis_value(keys, "SAID.reviewers"))
        docs_root = axis_value(keys, "SAID.docs-root") or "docs"
        idx = resolve_reviewers(lane_root, docs_root)
        if idx is None:
            findings.append({"item": "SAID.reviewers", "verdict": "unresolvable", "severity": "ADVISORY",
                             "remediation": "resolver unavailable (../status/said_status.py not importable); reviewer resolvability not checked"})
        else:
            for cid in reviewers:
                meta = idx.get(cid)
                if meta is None:
                    findings.append({"item": "reviewer:%s" % cid, "verdict": "unresolvable", "severity": "BLOCKER",
                                     "remediation": "reviewer %r resolves to no Checker; a nominal gate reports PASS while running nothing" % cid})
                elif meta.get("said-governs") and re.search(r"surface\s*=\s*<", meta["said-governs"]):
                    findings.append({"item": "reviewer:%s" % cid, "verdict": "stale", "severity": "BLOCKER",
                                     "remediation": "reviewer %r carries an un-instantiated said-governs placeholder; set surface= to the lane medium" % cid})
                else:
                    findings.append({"item": "reviewer:%s" % cid, "verdict": "ok", "severity": "OK", "remediation": ""})

    # docs skeleton
    docs_root = axis_value(keys, "SAID.docs-root") or "docs"
    for sk in schema["docs_skeleton"]:
        target = os.path.join(lane_root, docs_root, sk["path"])
        exists = os.path.isdir(target) if sk["type"] == "dir" else os.path.isfile(target)
        if not exists:
            findings.append({"item": "docs/%s" % sk["path"], "verdict": "missing",
                             "severity": sk["severity_if_missing"], "remediation": "scaffold %s under docs-root" % sk["path"]})

    return findings


def render(findings):
    problems = [f for f in findings if f["verdict"] != "ok"]
    by_sev = sorted(problems, key=lambda f: SEV_ORDER.get(f["severity"], 9))
    lines = []
    for sev in ("BLOCKER", "STALE", "ADVISORY"):
        rows = [f for f in by_sev if f["severity"] == sev]
        for f in rows:
            lines.append("  [%s] %-24s %-13s %s" % (sev, f["item"], f["verdict"], f["remediation"]))
    ok = len([f for f in findings if f["verdict"] == "ok"])
    lines.append("")
    lines.append("ledger: %d ok, %d flagged (%d BLOCKER, %d STALE, %d ADVISORY)" % (
        ok, len(problems),
        len([f for f in problems if f["severity"] == "BLOCKER"]),
        len([f for f in problems if f["severity"] == "STALE"]),
        len([f for f in problems if f["severity"] == "ADVISORY"])))
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Well-formed-lane checker for said:setup (read-only).")
    ap.add_argument("--root", default=".", help="lane root (dir holding the ## Lane CLAUDE.md)")
    ap.add_argument("--claude-md", default=None, help="explicit CLAUDE.md path (default: <root>/CLAUDE.md)")
    ap.add_argument("--schema", default=DEFAULT_SCHEMA, help="lane-schema.json (default: sibling references/)")
    ap.add_argument("--json", action="store_true", help="emit findings as JSON")
    a = ap.parse_args()

    schema = load_schema(a.schema)
    findings = check_lane(a.root, schema, a.claude_md)
    # The statusline install (the one environment item setup governs): never a BLOCKER.
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        import setup_statusline
        findings.append(setup_statusline.check_row())
    except Exception as e:
        findings.append({"item": "statusline", "verdict": "unresolvable", "severity": "ADVISORY",
                         "remediation": "statusline check failed: %s" % e})

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if a.json:
        print(json.dumps(findings, indent=2))
    else:
        print(render(findings))

    blockers = [f for f in findings if f["verdict"] != "ok" and f["severity"] == "BLOCKER"]
    return 1 if blockers else 0


if __name__ == "__main__":
    sys.exit(main())
