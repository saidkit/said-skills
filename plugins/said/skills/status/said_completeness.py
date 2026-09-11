#!/usr/bin/env python3
"""Completeness recompute — the uxtoc basis->contract lifecycle's accept-time check.

A recipe-form Checker's `said-recompute` (said-judge: oracle). Deterministic and bluff-proof.
DESIGNED is re-derived by parsing the single source of truth ($SAID_WORKDIR/toc.md) through the
shared element-projection taxonomy (skills/uxtoc/element-projection.md, LOAD-WHOLE + VERIFY-TOKEN)
— no intermediate `toc-elements.md`; the check parses the single source directly. An
element is a valueless keyed line (`- <key>:`) nested under one of the taxonomy's container headers
that is a LEAF among keyed lines (its next-deeper line is an attribute/value line, not another
keyed group — so a form Sections section-name is a grouping, its field-keys are the elements). Its
id is `<key>` (the stable key). Each element is qualified by its screen (`## Screen <ID> — …`), so
DESIGNED is a set of `(screen, key)` pairs: the same key on two screens is two distinct elements.

toc.md self-certifies: it carries a `toc-checksum: total=<N>,<SCREEN>=<n>,…` line (uxtoc's own count
by the same taxonomy). This check re-parses toc.md and verifies the count == the checksum; a mismatch
means the outline was hand-edited after emission -> FAIL "re-run uxtoc". Counting is a mirror, never
evaluation (W2).

The capture manifest ($SAID_CAPTURE) uses the SAME `## <Screen>` grouping:
    ## <Screen>
    built: <key>
    dropped: <key> :: <reason>          # reason required + non-empty; delimiter ` :: `
so BUILT and DROPPED are also `(screen, key)` pairs. Exit 0 iff the checksum matches AND designed
is-subset-of (built union dropped) AND designed is non-empty; else 1; exit 2 on a usage / missing /
taxonomy input error. The bluff-proofing is against a fabricated *verdict* and an omitted *build*,
not against tampering with toc.md itself (the operator-owned source of truth), matching the
Done-when's scope.

Invoked by the L2 oracle (said_status.py --reviewer-gate) from the lane root with SAID_WORKDIR (the
feature working dir holding toc.md) and SAID_CAPTURE (the manifest) in the environment.
"""
import os
import re
import sys

TOKEN = "UXP-V-1"
SCREEN_RE = re.compile(r"^##\s+Screen\s+(\S+)")
KEY_RE = re.compile(r"^(\s*)-\s+(.+?):\s*$")   # a valueless bulleted key: `- <key>:`


def die(msg, code):
    sys.stderr.write("completeness: " + msg + "\n")
    sys.exit(code)


def load_containers():
    """The closed container set, from the shared element-projection taxonomy (one source;
    loaded whole and pinned by its verify token, never re-derived from memory)."""
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.environ.get("SAID_PLUGIN_ROOT")
    candidates = []
    if root:
        candidates.append(os.path.join(root, "skills", "uxtoc", "element-projection.md"))
    candidates.append(os.path.join(here, "..", "uxtoc", "element-projection.md"))
    for p in candidates:
        if os.path.isfile(p):
            with open(p, encoding="utf-8") as fh:
                text = fh.read()
            if TOKEN not in text:
                die("element-projection.md missing VERIFY-TOKEN %s" % TOKEN, 2)
            m = re.search(r"^containers:\s*(.+)$", text, re.M)
            if not m:
                die("element-projection.md has no `containers:` line", 2)
            return set(c.strip() for c in m.group(1).split(",") if c.strip())
    die("element-projection.md not found (looked: %s)" % "; ".join(candidates), 2)


def parse_designed(path, containers):
    """DESIGNED = set of (screen, key). An element is a valueless keyed line under a container
    header that is a leaf among keyed lines (its next-deeper line is not another valueless key)."""
    lines = []
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            if raw.strip():
                lines.append(raw.rstrip("\n"))
    meta = []  # (indent, key|None) per non-blank line, for the leaf look-ahead
    for ln in lines:
        m = KEY_RE.match(ln)
        meta.append((len(ln) - len(ln.lstrip(" ")), m.group(2) if m else None))
    designed = set()
    screen = ""
    cind = None   # active container indent; None = no active container
    for i, ln in enumerate(lines):
        sm = SCREEN_RE.match(ln)
        if sm:
            screen, cind = sm.group(1), None
            continue
        if ln.startswith("## "):          # ## Scope or any non-screen header
            cind = None
            continue
        ind, key = meta[i]
        if key is not None and key in containers:
            cind = ind                    # a container header opens/replaces the context
            continue
        if cind is None:
            continue
        if ind <= cind:                   # dedented out of the container
            cind = None
            continue
        if key is None:                   # an attribute (value) line — not an element
            continue
        nxt_ind, nxt_key = meta[i + 1] if i + 1 < len(meta) else (ind, None)
        if nxt_key is not None and nxt_ind > ind:
            continue                      # a keyed group (e.g. a Sections section-name) — not a leaf
        designed.add((screen, key))
    return designed


def read_checksum(path):
    """{'total': N, '<SCREEN>': n, ...} from the `toc-checksum:` line, or None if absent."""
    with open(path, encoding="utf-8") as fh:
        m = re.search(r"^toc-checksum:\s*(.+)$", fh.read(), re.M)
    if not m:
        return None
    out = {}
    for part in m.group(1).split(","):
        part = part.strip()
        if "=" not in part:
            continue
        k, _, v = part.partition("=")
        try:
            out[k.strip()] = int(v.strip())
        except ValueError:
            die("FAIL: toc-checksum has a non-integer count (%r) — re-run uxtoc" % part, 1)
    return out


wd = os.environ.get("SAID_WORKDIR")
cap = os.environ.get("SAID_CAPTURE")
if not wd or not cap:
    die("SAID_WORKDIR and SAID_CAPTURE are required in the environment", 2)

toc = os.path.join(wd, "toc.md")
if not os.path.isfile(toc):
    die("no toc.md at %s" % toc, 2)
if not os.path.isfile(cap):
    die("no capture manifest at %s" % cap, 2)

containers = load_containers()
designed = parse_designed(toc, containers)

if not designed:
    die("FAIL: toc.md yields zero designed elements (hollow — nothing to certify complete; the "
        "outline has no keyed elements under its container headers, or set Surface: none)", 1)

# checksum verify — toc.md must match its own count (catches a hand-edit after emission)
checksum = read_checksum(toc)
if checksum is None:
    die("FAIL: toc.md has no toc-checksum: line — re-run uxtoc", 1)
per = {}
for (s, k) in designed:
    per[s] = per.get(s, 0) + 1
if checksum.get("total") != len(designed):
    die("FAIL: toc.md does not match its own toc-checksum (checksum total=%s, re-parsed %d) — "
        "re-run uxtoc" % (checksum.get("total"), len(designed)), 1)
for s, n in per.items():
    if s in checksum and checksum[s] != n:
        die("FAIL: toc-checksum for screen %s says %d, re-parsed %d — re-run uxtoc"
            % (s, checksum[s], n), 1)

# BUILT + DROPPED — (screen, key) from the manifest (same `## <Screen>` grouping)
built, dropped = set(), set()
screen = ""
with open(cap, encoding="utf-8") as fh:
    for raw in fh:
        line = raw.strip()
        if not line:
            continue
        if line.startswith("## "):
            screen = line[3:].strip()
            continue
        if line.startswith("built:"):
            built.add((screen, line[len("built:"):].strip()))
        elif line.startswith("dropped:"):
            rest = line[len("dropped:"):].strip()
            if " :: " not in rest:
                die("FAIL: dropped element '%s' has no recorded reason (use 'dropped: <key> :: <reason>')" % rest, 1)
            eid, _, reason = rest.partition(" :: ")
            if not reason.strip():
                die("FAIL: dropped element '%s' has an empty reason" % eid.strip(), 1)
            dropped.add((screen, eid.strip()))

missing = sorted(s + " / " + e for (s, e) in designed if (s, e) not in built and (s, e) not in dropped)
if missing:
    die("FAIL: designed elements neither built nor dropped: %s" % ", ".join(missing), 1)
print("completeness PASS: %d designed <= %d built + %d dropped (checksum ok)"
      % (len(designed), len(built), len(dropped)))
sys.exit(0)
