#!/usr/bin/env python3
"""Completeness recompute - the uxtoc basis->contract lifecycle's accept-time check.

A recipe-form Checker's `said-recompute` (said-judge: oracle). Deterministic and bluff-proof, and
medium-agnostic: the unit word + container set come from the injected per-surface lane grammar, never
from a hardcoded medium vocabulary and never from the operator-owned `toc.md`.

DESIGNED is re-derived by parsing the single source of truth ($SAID_WORKDIR/toc.md) through the
element-projection RULE (skills/uxtoc/element-projection.md, LOAD-WHOLE + VERIFY-TOKEN - the rule only)
and the injected grammar's vocabulary (unit, containers, attribute set). A `## <Unit> <ID> - <title>`
line opens a unit; a keyed line (`- <key>:`) directly under one of the grammar's declared containers is
one element, UNLESS its key is in the grammar's closed attribute set or its not-elements set (then it is a
non-element group,
not an element, and it does not disqualify its parent from being a leaf element). Its id is `<key>`.
DESIGNED is a set of `(unit, key)` pairs.

No toc seal: there is NO `toc-checksum:` read. The operator hand-edits `toc.md` freely; no check fails
on a legitimate design-content edit. The two bounded exceptions are machine-written front-matter (an
absent `grammar:<token>` stamp FAILs - provenance is not opt-out by deletion) and a unit that
yields zero designed elements (a hollow FAIL; a legitimately-emptied container is written `<container>: none - <reason>`).

Honesty rests on the comparison + recompute + capture:
  - the comparison DESIGNED subset-of (BUILT union accounted-drops), with the attribute-group
    projection fix (a nested attribute never steals its parent element's status);
  - the L2 oracle verdict-recompute (said_status.py --reviewer-gate re-derives, never trusts a PASS);
  - BUILT capture: BUILT is read from the capture manifest (declared-evidence). The author-independent
    EXECUTED capture (cli --help, web DOM/manifest probe) is the per-lane probe-table, DEFERRED beyond
    this release; until it lands, cli/web completeness is declared-evidence (manifest-based).

Trust tiers are declaration-bound (grammar `oracle-containers:`): the containers that WILL be
oracle-verified (author-independent) once the probe-table lands; until then every container is
declared-evidence. The verdict reports the manifest capture + the oracle-intended count.

Grammar resolution: `--grammar <path>` argv, else $SAID_GRAMMAR; the section is selected by
$SAID_SURFACE. A missing grammar die(2)s with a named redirect; two matching surface-sections exit 2.

Invoked by the L2 oracle (said_status.py --reviewer-gate) from the lane root with SAID_WORKDIR, the
grammar inputs, SAID_CAPTURE (a manifest file) and SAID_PLUGIN_ROOT in the env.
Exit 0 iff designed is non-empty AND designed subset-of (built union dropped); else 1; exit 2 on a
usage / missing-input / grammar error.
"""
import os
import re
import sys

RULE_TOKEN = "UXP-R-1"
KEY_RE = re.compile(r"^(\s*)-\s+(.+?):\s*$")   # a valueless bulleted key: `- <key>:`


def die(msg, code):
    sys.stderr.write("completeness: " + msg + "\n")
    sys.exit(code)


def verify_rule_token():
    """Prove-load the element-projection RULE by its VERIFY-TOKEN (the rule only; the vocabulary
    lives in the grammar). Resolves plugin-relative, SAID_PLUGIN_ROOT first (unvendored-root safe)."""
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.environ.get("SAID_PLUGIN_ROOT")
    candidates = []
    if root:
        candidates.append(os.path.join(root, "skills", "uxtoc", "element-projection.md"))
    candidates.append(os.path.join(here, "..", "uxtoc", "element-projection.md"))
    for p in candidates:
        if os.path.isfile(p):
            with open(p, encoding="utf-8") as fh:
                if RULE_TOKEN not in fh.read():
                    die("element-projection.md missing VERIFY-TOKEN %s" % RULE_TOKEN, 2)
            return
    die("element-projection.md not found (looked: %s)" % "; ".join(candidates), 2)


def _hdr_kv(fields, key):
    m = re.search(r"(?:^|,)\s*" + re.escape(key) + r"=(.+?)(?:,[a-z][a-z-]*=|$)", fields)
    return m.group(1).strip() if m else None


def _mr_line(body, key):
    m = re.search(r"(?m)^" + re.escape(key) + r":\s*(.+)$", body)
    if not m:
        return set()
    return set(x.strip() for x in m.group(1).split(";") if x.strip())


def load_grammar(path, surface):
    """Select the SC-HEADER section for `surface` and return its unit + vocabulary. The section
    spans from its SC-HEADER to the next SC-HEADER (or EOF), so a multi-surface grammar is scoped."""
    if not os.path.isfile(path):
        die("no grammar at %s - author docs/ux/feature-ux-grammar.md (a surface-bearing lane requires "
            "one; or set Surface: none)" % path, 2)
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    hdrs = list(re.finditer(r"<!--\s*SC-HEADER:\s*(.+?)\s*-->", text, re.S))
    if not hdrs:
        die("grammar %s has no SC-HEADER" % path, 2)
    matched = []
    for i, h in enumerate(hdrs):
        if _hdr_kv(h.group(1), "surface") == surface:
            end = hdrs[i + 1].start() if i + 1 < len(hdrs) else len(text)
            matched.append((h.group(1), text[h.end():end]))
    if not matched:
        die("no grammar section for surface=%s in %s (author one, or set Surface: none)"
            % (surface, path), 2)
    if len(matched) > 1:
        die("grammar has %d sections for surface=%s (ambiguous)" % (len(matched), surface), 2)
    fields, body = matched[0]
    unit = _hdr_kv(fields, "unit")
    token = _hdr_kv(fields, "token")
    count = _hdr_kv(fields, "count")
    containers = [c.strip() for c in (_hdr_kv(fields, "containers") or "").split(";") if c.strip()]
    if not unit or not token or not containers:
        die("grammar SC-HEADER (surface=%s) missing unit/token/containers" % surface, 2)
    if count is None or not count.isdigit() or int(count) != len(containers):
        die("grammar SC-HEADER count=%s != %d containers (surface=%s) - unbluffable count-seal"
            % (count, len(containers), surface), 2)
    oracle = _mr_line(body, "oracle-containers")
    stray = oracle - set(containers)
    if stray:
        die("oracle-containers names a container not in the SC-HEADER `containers=` (%s) - grammar "
            "config error (surface=%s)" % (", ".join(sorted(stray)), surface), 2)
    return {
        "unit": unit,
        "token": token,
        "containers": set(containers),
        "attributes": _mr_line(body, "attributes"),
        "not_elements": _mr_line(body, "not-elements"),
        "oracle_containers": oracle,
    }


def read_grammar_stamp(path):
    """The `grammar:<token>` front-matter line uxtoc stamps into toc.md, or None if absent."""
    with open(path, encoding="utf-8") as fh:
        m = re.search(r"(?m)^grammar:\s*(\S+)\s*$", fh.read())
    return m.group(1) if m else None


def parse_designed(path, unit, containers, attributes, not_elements):
    """DESIGNED = set of (unit, key), attribute-set-aware. A keyed line under a container is an
    element unless its key is a NON-ELEMENT key - the grammar's attribute set (an attribute group)
    OR its not-elements set (declared scaffolding, e.g. Sorts, Empty state) - or it is a real
    sub-grouping (it has a descendant keyed line that is itself an element key - e.g. a form Sections
    section-name). A nested non-element key never disqualifies its parent from being a leaf."""
    nonelt = set(attributes) | set(not_elements)
    unit_re = re.compile(r"^##\s+" + re.escape(unit) + r"\s+(\S+)")
    lines = []
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            if raw.strip():
                lines.append(raw.rstrip("\n"))
    meta = []
    for ln in lines:
        m = KEY_RE.match(ln)
        meta.append((len(ln) - len(ln.lstrip(" ")), m.group(2) if m else None))

    def is_grouping(i, ind):
        """True if the keyed line at i has any descendant keyed line whose key is NOT an attribute
        (a real sub-grouping); False if it is a leaf (no keyed descendants, or attribute-only)."""
        j = i + 1
        while j < len(lines):
            jind, jkey = meta[j]
            if jind <= ind:
                break
            if jkey is not None and jkey not in nonelt:
                return True
            j += 1
        return False

    designed = set()
    container_of = {}
    unit_id = ""
    cind = None
    for i, ln in enumerate(lines):
        um = unit_re.match(ln)
        if um:
            unit_id, cind = um.group(1), None
            continue
        if ln.startswith("## "):          # any non-unit header closes the container context
            cind = None
            continue
        ind, key = meta[i]
        if key is not None and key in containers:
            cind = ind
            active_container = key
            continue
        if cind is None:
            continue
        if ind <= cind:                   # dedented out of the container
            cind = None
            continue
        if key is None:                   # an attribute/value line - not an element
            continue
        if key in nonelt:                 # an attribute group or declared scaffolding - not an element
            continue
        if is_grouping(i, ind):           # a real sub-grouping (its children are the elements)
            continue
        designed.add((unit_id, key))
        container_of[(unit_id, key)] = active_container
    return designed, container_of


def read_manifest(cap):
    """BUILT + DROPPED as (unit, key) pairs from an author/tool-written capture manifest."""
    built, dropped = set(), set()
    unit = ""
    with open(cap, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue
            if line.startswith("## "):
                unit = line[3:].strip()
                continue
            if line.startswith("built:"):
                built.add((unit, line[len("built:"):].strip()))
            elif line.startswith("dropped:"):
                rest = line[len("dropped:"):].strip()
                if " :: " not in rest:
                    die("FAIL: dropped element '%s' has no recorded reason "
                        "(use 'dropped: <key> :: <reason>')" % rest, 1)
                eid, _, reason = rest.partition(" :: ")
                if not reason.strip():
                    die("FAIL: dropped element '%s' has an empty reason" % eid.strip(), 1)
                dropped.add((unit, eid.strip()))
    return built, dropped


def main():
    argv = sys.argv[1:]
    grammar = None
    if "--grammar" in argv:
        i = argv.index("--grammar")
        if i + 1 >= len(argv):
            die("--grammar needs a path", 2)
        grammar = argv[i + 1]
    grammar = grammar or os.environ.get("SAID_GRAMMAR")
    surface = os.environ.get("SAID_SURFACE")
    wd = os.environ.get("SAID_WORKDIR")
    cap = os.environ.get("SAID_CAPTURE")
    if not grammar:
        die("no grammar: pass --grammar <path> or set SAID_GRAMMAR (a surface-bearing lane requires "
            "docs/ux/feature-ux-grammar.md)", 2)
    if not surface:
        die("SAID_SURFACE is required (the grammar section selector)", 2)
    if not wd or not cap:
        die("SAID_WORKDIR and SAID_CAPTURE are required in the environment", 2)

    verify_rule_token()
    g = load_grammar(grammar, surface)

    toc = os.path.join(wd, "toc.md")
    if not os.path.isfile(toc):
        die("no toc.md at %s" % toc, 2)

    # grammar-stamp cross-check: provenance is not opt-out by deletion (absent -> FAIL)
    stamp = read_grammar_stamp(toc)
    if stamp is None:
        die("FAIL: toc.md has no `grammar:<token>` stamp - re-emit with uxtoc under this grammar", 1)
    if stamp != g["token"]:
        die("FAIL: toc.md grammar stamp %r != this grammar's token %r (wrong-grammar outline)"
            % (stamp, g["token"]), 1)

    designed, container_of = parse_designed(toc, g["unit"], g["containers"], g["attributes"], g["not_elements"])
    if not designed:
        die("FAIL: toc.md yields zero designed elements (hollow - nothing to certify complete; no "
            "keyed elements under container headers, or set Surface: none)", 1)

    # BUILT is read from the capture manifest (declared-evidence). The author-independent EXECUTED
    # capture (cli --help / web DOM probe) is the per-lane probe-table, deferred beyond this release;
    # the grammar's `oracle-containers:` records which containers WILL be oracle-verified once it lands.
    # `recomputed` is not yet a valid capture - a manifest supplies BUILT for every container.
    if cap == "recomputed":
        die("executed capture (the `recomputed` sentinel) is deferred to the per-lane probe-table; "
            "supply a capture manifest for BUILT", 2)
    if not os.path.isfile(cap):
        die("no capture manifest at %s" % cap, 2)
    built, dropped = read_manifest(cap)

    missing = sorted(u + " / " + e for (u, e) in designed if (u, e) not in built and (u, e) not in dropped)
    if missing:
        die("FAIL: designed elements neither built nor dropped: %s" % ", ".join(missing), 1)

    oracle_intended = sum(1 for k in designed if container_of.get(k) in g["oracle_containers"])
    print("completeness PASS: %d designed <= %d built + %d dropped "
          "(capture: manifest/declared-evidence; %d in oracle-intended containers, executed capture deferred)"
          % (len(designed), len(built), len(dropped), oracle_intended))
    sys.exit(0)


if __name__ == "__main__":
    main()
