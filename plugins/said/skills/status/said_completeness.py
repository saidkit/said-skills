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
on a legitimate design-content edit. The bounded exceptions are all machine-written front-matter or
structural: (1) an absent `grammar:<token>` stamp FAILs - provenance is not opt-out by deletion;
(2) a unit that yields zero designed elements is a hollow FAIL (a legitimately-emptied container is
written `<container>: none - <reason>`); (3) on a `dir:` unit-home lane the sealed `units: A;B;C
(count: N)` line is required (absent -> FAIL) and count-sealed (mismatch -> FAIL) - it names the
DECLARED unit set the durable-spec check resolves, machine-written by uxtoc; an `inline` lane has no
such line. None of these reads or digests the design content, so a content edit never FAILs.

Honesty rests on the comparison + recompute + capture:
  - the comparison DESIGNED subset-of (BUILT union accounted-drops), with the attribute-group
    projection fix (a nested attribute never steals its parent element's status);
  - the built-floor: at least one DESIGNED element must be built (BUILT intersect DESIGNED
    non-empty); an outline whose every designed element is dropped ships nothing - the comparison then
    holds vacuously, so completeness FAILs it; a legitimate partial-drop PASSes;
  - the L2 oracle verdict-recompute (said_status.py --reviewer-gate re-derives, never trusts a PASS);
  - BUILT capture: for a **cli** unit whose manifest declares a `cmd:`, the grammar's oracle-containers
    are verified author-independently by executing that command's own `--help` read-only (command-path +
    `--help` only - every invocation flag stripped). A flag is oracle-verified by TWO machine witnesses
    (two-witness): the first usage-synopsis block AND an options-section+column cluster corroborated by it -
    a flag in prose, an epilog, a description column, or only one witness is not verified. A tool whose
    `--help` is not two-witness parseable (hand-rolled / truncated `[options]` synopsis) falls to
    declared-evidence, never a false FAIL. A **non-cli (web)** unit runs its front-declared probe as-given
    (the front owns its read-only-ness; no `--help`, no flag-strip); the rest is read from the capture
    manifest (declared-evidence).

Trust tiers are declaration-bound (grammar `oracle-containers:`): a container is oracle-verified where an
executed capture runs AND the tool's `--help` is two-witness parseable (its unit declares a `cmd:`), else
declared-evidence (manifest). The verdict reports the oracle-verified count and how many units were
two-witness oracle-verified, and WARNs when a designed oracle flag falls to declared-evidence because its
tool's `--help` is not two-witness parseable (the coverage ceiling, surfaced per-run, not silent).

Grammar resolution: `--grammar <path>` argv, else $SAID_GRAMMAR; the section is selected by
$SAID_SURFACE. A missing grammar die(2)s with a named redirect; two matching surface-sections exit 2.

Invoked by the L2 oracle (said_status.py --reviewer-gate) from the lane root with SAID_WORKDIR, the
grammar inputs, SAID_CAPTURE (a manifest file) and SAID_PLUGIN_ROOT in the env.
Exit 0 iff designed is non-empty AND designed subset-of (built union dropped); else 1; exit 2 on a
usage / missing-input / grammar error.
"""
import os
import re
import shlex
import subprocess
import sys

RULE_TOKEN = "UXP-R-1"
KEY_RE = re.compile(r"^(\s*)-\s+(.+?):\s*$")   # a valueless bulleted key: `- <key>:`
# the sealed DECLARED-units line uxtoc stamps into toc.md: `units: A;B;C (count: N)`. The engine reads the
# declared unit set from HERE - read explicitly, never inferred from free-form outline prose (uxtoc knows
# exactly which units it mirrored, so it declares them and `count` seals the line, exactly like the grammar's
# `count=` sentinel; inferring "is this markdown header a real unit" from prose is fragile by construction).
UNITS_RE = re.compile(r"(?m)^units:\s*(.*?)\s*\(count:\s*(\d+)\)\s*$")
# auto-added flags every CLI framework emits; never "designed", so flagging them under-spec is pure noise.
# Judged by the LONG form where a cluster has one (so `-v, --version` suppresses but `-h, --hard-reset` does
# not); a lone short flag with no long form falls back to the unambiguous-help short set.
BOILERPLATE_LONG = frozenset({"--help", "--version", "--usage", "--help-all"})
BOILERPLATE_SHORT = frozenset({"-h", "-?"})
FLAG_RE = re.compile(r"(?<![\w=-])(--?[A-Za-z][\w-]*)")   # a flag token in --help output (a value after `=` is not a flag)
# an option-definition line: indented, opening with a flag cluster (flag + comma-separated aliases).
# group(1) = the leading indent (for column-anchoring), group(2) = the leading flag cluster.
OPT_RE = re.compile(r"([ \t]+)(-{1,2}[A-Za-z][\w-]*(?:[ \t]*,[ \t]*-{1,2}[A-Za-z][\w-]*)*)")
SECTION_HDR_RE = re.compile(r"(?i)^(options|optional arguments|flags):\s*$")   # an options-section header
USAGE_HDR_RE = re.compile(r"(?i)^\s*usage:")   # the usage-synopsis header


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
        "unit_home": _hdr_kv(fields, "unit-home"),
    }


_FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")   # a CommonMark fence opener: indented at most 3 spaces


def _content_lines(path):
    """The file's lines with fenced (``` / ~~~) code blocks removed - the ONE fence rule both the
    front-matter/`units:` readers and the element parser share (so they can never disagree). A fence opens
    only when indented <= 3 spaces (CommonMark); a same-kind fence of >= the opening length closes it; a
    different-kind or shorter marker inside a fence is content. An UNTERMINATED fence is malformed input:
    FAIL loud (never silently drop the units/elements after it). Line endings stripped; tabs preserved."""
    kept, fence = [], None
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            s = raw.rstrip("\r\n")
            fm = _FENCE_RE.match(s)
            if fm:
                mark = fm.group(1)
                rest = s.lstrip()[len(mark):].strip()   # text after the marker run (an "info string")
                if fence is None:
                    fence = (mark[0], len(mark)); continue   # an opener MAY carry an info string
                # a CLOSER must be the same kind, >= the opening length, and BARE (no info string) - per
                # CommonMark; a nested ` ```lang ` inside a block is content, not a close.
                if mark[0] == fence[0] and len(mark) >= fence[1] and rest == "":
                    fence = None; continue
            if fence is None:
                kept.append(s)
    if fence is not None:
        die("FAIL: toc.md has an unterminated code fence - a dangling fence would silently drop every "
            "unit/element after it; close the fence or remove it", 1)
    return kept


def _defence(path):
    """The file's text with fenced code blocks removed (a stamp or `units:` line shown inside a documentation
    fence is not read as the real one). Built on the shared `_content_lines` fence rule."""
    return "\n".join(_content_lines(path)) + "\n"


def read_grammar_stamp(path):
    """The `grammar:<token>` front-matter line uxtoc stamps into toc.md, or None if absent. Read outside any
    fenced block (a documentation example of the stamp does not count) - consistent with the unit parser."""
    m = re.search(r"(?m)^grammar:\s*(\S+)\s*$", _defence(path))
    return m.group(1) if m else None


def read_units_decl(path):
    """The sealed `units: <ID1>;<ID2>;... (count: N)` line uxtoc stamps into toc.md - the AUTHORITATIVE
    DECLARED unit set for the durable-spec check, read explicitly rather than inferred from prose. Returns a
    set of ids, or None if the line is absent. A count that disagrees with the listed ids is a stale /
    hand-fudged line -> FAIL (unbluffable, exactly like the grammar's `count=` sentinel). Read outside any
    fenced block so a documentation example of the line does not count."""
    m = UNITS_RE.search(_defence(path))
    if not m:
        return None
    ids = [x.strip() for x in m.group(1).split(";") if x.strip()]
    # A unit id becomes the durable filename `<ID>.md`. Require a PORTABLE id: ASCII word chars, dot, dash.
    # This is deliberately strict (not just "no path separators"): a non-ASCII filename resolves through
    # platform-dependent Unicode normalization (macOS NFD vs Linux byte-exact), so a non-ASCII id would make
    # the durable-spec verdict non-deterministic across machines. The uxtoc emit slugifies a non-ASCII unit
    # name so the id stays a plain-ASCII, portable filename component.
    bad = [x for x in ids if not re.match(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?$", x) or ".." in x]
    if bad:
        die("FAIL: toc.md `units:` has a non-portable id: %s - a unit id is a portable filename component "
            "([A-Za-z0-9._-], ASCII, no leading/trailing dot-or-dash, no path separator); a non-ASCII unit "
            "name must be slugified at emit; re-emit with uxtoc" % ", ".join(bad), 1)
    n = int(m.group(2))
    # seal on the UNIQUE id count - `A;A (count: 2)` must not pass as two units (unbluffable like count=).
    if len(set(ids)) != n:
        die("FAIL: toc.md `units:` count %d != %d distinct listed id(s) - a stale, duplicated, or miscounted "
            "units line; re-emit with uxtoc" % (n, len(set(ids))), 1)
    # two ids differing only by case resolve to the same durable on a case-insensitive filesystem -> a
    # platform-dependent verdict; reject so the check is deterministic everywhere.
    if len({x.lower() for x in ids}) != len(set(ids)):
        die("FAIL: toc.md `units:` has ids differing only by case - ambiguous on a case-insensitive "
            "filesystem; give each unit a case-distinct id", 1)
    return set(ids)


def parse_designed(path, unit, containers, attributes, not_elements, level=2):
    """DESIGNED = set of (unit, key), attribute-set-aware. A keyed line under a container is an
    element unless its key is a NON-ELEMENT key - the grammar's attribute set (an attribute group)
    OR its not-elements set (declared scaffolding, e.g. Sorts, Empty state) - or it is a real
    sub-grouping (it has a descendant keyed line that is itself an element key - e.g. a form Sections
    section-name). A nested non-element key never disqualifies its parent from being a leaf.

    Fenced code blocks are skipped (an outline EXAMPLE in a ``` block is neither designed nor gated) and
    indentation is tab-aware. The DECLARED unit set (for the durable-spec check) is NOT inferred here - it is
    read from the sealed `units:` line uxtoc stamps (read_units_decl); this function returns only the projected
    element set (and its container map)."""
    nonelt = set(attributes) | set(not_elements)   # non-element keys, for is_grouping's leaf test
    attrs, not_els = set(attributes), set(not_elements)  # split out: an ATTRIBUTE key colliding with a direct
                                                          # container-child name (a `description` column) is a real
                                                          # element; a NOT-ELEMENT (scaffolding) never is.
    # The unit header sits at `level` hashes: 2 (`## <unit> <ID>`) for a toc or an inline spec, 1
    # (`# <unit> <ID>`) for a durable per-unit file parsed DIRECTLY (a standalone file titles its unit at H1).
    unit_re = re.compile(r"^#{%d}\s+" % level + re.escape(unit) + r"\s+(\S+)")
    # skip fenced code blocks (an outline EXAMPLE inside a ``` / ~~~ fence must not be parsed as real
    # units/elements) via the SHARED fence rule (`_content_lines`, same rule the front-matter/`units:`
    # readers use - so they can never disagree); an unterminated fence FAILs loud there. Then drop blanks.
    lines = [s for s in _content_lines(path) if s.strip()]
    meta = []
    for ln in lines:
        m = KEY_RE.match(ln)
        exp = ln.expandtabs(4)                        # tab-aware indent (markdown authors use tabs)
        meta.append((len(exp) - len(exp.lstrip(" ")), m.group(2) if m else None))

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

    def _under_leaf(i, ind):
        """True when this line's PARENT (the nearest enclosing keyed line) is a LEAF element - i.e. this line is
        an attribute OF an element. False when the parent is a container (this line is a direct container child,
        a real element - e.g. a `description` COLUMN that collides with the `description` attribute name) or a
        grouping (a field of a form section). Only when this returns True does an ATTRIBUTE-set key name a
        non-element; a not-element (scaffolding) is skipped regardless of depth, separately."""
        j = i - 1
        while j >= 0:
            jind, jkey = meta[j]
            if jkey is not None and jind < ind:
                if jkey in containers:
                    return False                 # parent is a container -> a direct child -> a real element
                return not is_grouping(j, jind)  # parent is a leaf element iff it has no element descendants
            j -= 1
        return False                             # no enclosing keyed line -> not an attribute of anything

    designed = set()
    container_of = {}
    headers = set()                       # every `## <unit> <ID>` header id present in the outline (a
                                          # presence set for cross-checking the sealed units line - NOT the
                                          # prose inference that was deleted; a header line unambiguously is one)
    unit_id = ""
    stack = []                            # [(container, indent)] outermost-first - a STACK, not one active depth:
                                          # a dedent past a NESTED container pops back to the ENCLOSING container
                                          # (never blanks it), so a sibling leaf item after a deep sibling still
                                          # projects under the popped-back enclosing container - a tabbed detail
                                          # screen no longer swallows its leaf/reuses tabs that follow a deep tab.
    for i, ln in enumerate(lines):
        um = unit_re.match(ln)
        if um:
            unit_id, stack = um.group(1), []
            headers.add(unit_id)
            continue
        if ln.startswith("#" * level + " "):  # a non-unit header AT THE UNIT'S OWN LEVEL closes the container
            unit_id, stack = "", []            # AND unit context, so a keyed element under a mis-levelled /
            continue                            # mis-worded later header is not silently reparented to the
            # previous unit (it hits the loud guard below). LEVEL-AWARE: at level=1 (a durable parsed directly)
            # only another H1 resets - an ordinary H2/H3 SUBHEADING is subordinate content of the same unit, not
            # a boundary, so it must not reset (its container closes by the dedent-pop below). At level=2
            # (toc/inline) this stays `## ` exactly as before.
        ind, key = meta[i]
        while stack and ind <= stack[-1][1]:  # dedented out of one or more open containers - pop them, which
            stack.pop()                       # restores the nearest still-open ENCLOSING container as active
        if key is not None and key in containers:
            stack.append((key, ind))          # open this container, nested under any shallower one still on the stack
            continue
        if not stack:                     # not inside any container
            continue
        if key is None:                   # an attribute/value line - not an element
            continue
        if key in not_els:                # declared scaffolding (Sorts, Empty state) - never an element, any depth
            continue
        if key in attrs and _under_leaf(i, ind):  # an attribute value-group OF a leaf element - not an element;
            continue                               # the SAME name as a direct container child (a `description`
                                                   # column) stays a real element (attribute-name collision)
        if is_grouping(i, ind):           # a real sub-grouping (its children are the elements)
            continue
        if not unit_id:                   # a keyed element before any unit header - never silently drop
            hh = "#" * level               # the expected header level for THIS parse target (H2 toc/inline, H1 durable)
            die("FAIL: %s has a keyed element under a container before any `%s %s <ID>` header "
                "(key %r) - a mis-levelled or mis-worded unit header leaves its elements outside any "
                "unit; fix the header" % (os.path.basename(path), hh, unit, key), 1)
        active_container = stack[-1][0]   # the innermost still-open container
        designed.add((unit_id, key))
        container_of[(unit_id, key)] = active_container
    return designed, container_of, headers


def read_manifest(cap):
    """BUILT + DROPPED as (unit, key) pairs, plus per-unit `cmd:` (the executed-capture command path),
    from an author/tool-written capture manifest."""
    built, dropped, cmds = set(), set(), {}
    unit = ""
    with open(cap, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue
            if line.startswith("## "):
                unit = line[3:].strip()
                continue
            if line.startswith("cmd:"):
                cmds[unit] = line[len("cmd:"):].strip()
            elif line.startswith("built:"):
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
    return built, dropped, cmds


def _dir_home(g, grammar_path):
    """`(rel, ddir)` for a `dir:<path>` unit-home, else None (an `inline` or absent unit-home). The lane
    root reaches a direct harness run via $SAID_ROOT (the reviewer gate injects it); absent, it falls back
    grammar-relative (the grammar sits at <root>/<docs-root>/ux/feature-ux-grammar.md, so the lane root is
    three dirs up)."""
    uh = (g.get("unit_home") or "inline").strip()
    if not uh.startswith("dir:"):
        return None
    rel = uh[len("dir:"):].strip().rstrip("/")
    root = os.environ.get("SAID_ROOT") or os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(grammar_path))))
    return rel, os.path.join(root, rel)


def check_unit_home(g, grammar_path, toc, designed_units, headers):
    """Resolve the grammar's unit-home. For a `dir:<path>` unit-home, every DECLARED unit needs a durable
    spec at <lane-root>/<path>/<ID>.md - a missing one FAILs (broken-link). There is NO lane-wide orphan
    sweep: a `dir:` unit-home is commonly SHARED across features (many features' unit files in one directory),
    so a durable this feature never declared is a SIBLING feature's, not this feature's orphan - sweeping it
    would fail one feature's gate on another's file. The teeth against a copied / renamed / stale / empty
    durable are elsewhere: `main` parses each DECLARED durable DIRECTLY (level=1) and cross-checks that it
    heads its OWN id, so a durable answering for the wrong unit FAILs there.

    The DECLARED set is read EXPLICITLY from the sealed `units: A;B;C (count: N)` line uxtoc stamps
    (`declared_line`), NOT inferred from free-form outline prose (inferring "is this markdown header a real
    unit" from prose is fragile by construction; uxtoc knows exactly which units it mirrored, including one
    whose containers are legitimately emptied, so it declares them and `count` seals the line). A `dir:` lane
    therefore REQUIRES the line (absent -> FAIL, re-emit with uxtoc); every unit that projects an element must
    appear in it (a stale line that omits one -> FAIL); every declared id must be backed by a real `## <unit>
    <ID>` outline header (a fabricated / stale-basename id -> FAIL, so a phantom cannot mask an orphan); a
    hand-edited durable that adds/removes an element never changes the declared set, so no legit design edit
    flips PASS<->FAIL (no-seal-safe). Presence-stat ONLY (never reads a durable's content). An
    `inline` (or absent) unit-home has no durable dir and skips (medium-agnostic). The lane root reaches a
    direct harness run via $SAID_ROOT (the reviewer gate injects it); absent, it falls back grammar-relative
    (grammar at <root>/<docs-root>/ux/feature-ux-grammar.md, so the lane root is three dirs up). Ignore
    convention: a README, a `_`-prefixed draft, or a dotfile under the durable dir never counts as an orphan."""
    uh = (g.get("unit_home") or "inline").strip()
    if not uh.startswith("dir:"):
        return                                  # an inline lane has no durable dir and never reads a units line
    declared_line = read_units_decl(toc)        # read ONLY on a dir: lane (its shape guards must not fire on inline)
    if declared_line is None:
        die("FAIL: unit-home is `dir:` but toc.md has no sealed `units: A;B;C (count: N)` line - the "
            "durable-spec check reads the DECLARED unit set from it (no prose inference); re-emit with uxtoc", 1)
    # The declared set must EXACTLY match the outline's `## <unit> <ID>` headers, both directions (a
    # header-PRESENCE cross-check, NOT the deleted prose inference):
    #   phantom  = a declared id with no outline header (a fabricated / stale-basename id masking an orphan) -> FAIL
    #   stranded = an outline header not on the line (a hand-added header, or an emptied unit uxtoc did not
    #              re-emit) -> FAIL; without this, an element-less header escapes the durable-spec gate. On a
    #              dir: lane THIS is what catches "a unit designs elements but is off the sealed line": the
    #              unit's outline header is present (stranded) even though the durable-derived DESIGNED never
    #              includes an off-line unit.
    #   omitted  = a unit that projects an element but is not on the line. Since DESIGNED is now derived by
    #              parsing ONLY the DECLARED durables (main, dir: block), `designed_units` is always a subset of
    #              `declared_line`, so this branch is VACUOUS on a dir: lane - kept as a cheap defensive
    #              invariant (it must never fire; if a future change re-derives designed_units differently it
    #              catches the regression), with `stranded` carrying the real "off-line unit" scenario above.
    omitted = sorted(designed_units - declared_line)
    if omitted:
        die("FAIL: toc.md `units:` line omits unit(s) that design elements: %s - a stale units line; "
            "re-emit with uxtoc so the sealed set matches the outline" % ", ".join(omitted), 1)
    stranded = sorted(headers - declared_line)
    if stranded:
        die("FAIL: toc.md has `## %s <ID>` header(s) not on the sealed `units:` line: %s - a hand-added or "
            "un-re-emitted unit escapes the durable-spec gate; re-emit with uxtoc" % (g["unit"], ", ".join(stranded)), 1)
    phantom = sorted(declared_line - headers)
    if phantom:
        die("FAIL: toc.md `units:` line names unit(s) with no `## %s <ID>` outline header: %s - a stale or "
            "fabricated units line (it must match the outline); re-emit with uxtoc" % (g["unit"], ", ".join(phantom)), 1)
    rel, ddir = _dir_home(g, grammar_path)
    units = sorted(declared_line)
    missing = [u for u in units if not os.path.isfile(os.path.join(ddir, u + ".md"))]
    if missing:
        die("FAIL: unit-home dir:%s - durable spec(s) missing for declared unit(s): %s (a renamed / "
            "deleted / never-authored <ID>.md; re-add or rename it under the durable dir)"
            % (rel, ", ".join(missing)), 1)
    # No lane-wide orphan sweep: a `dir:` unit-home is commonly SHARED across features (many features' unit
    # files in one directory), so a durable this feature never declared is a SIBLING feature's, not
    # this feature's orphan - a lane-wide "extra .md is an orphan" sweep would fail one feature's gate on
    # another feature's file. The declared set is sealed by `units:`, and each declared durable is parsed
    # DIRECTLY (main, level=1) with an identity cross-check (it must head its own id), so a copied / renamed
    # / stale / 0-byte durable is caught there; presence + identity are the teeth, not a directory sweep.


def _usage_synopsis_flags(text):
    """Witness-1: the optional flags in the FIRST `usage:` synopsis block, read as synopsis GRAMMAR (not as
    raw flag-shaped tokens - that is what makes this witness independent of the options section).

    The block is the `usage:` line plus its indented continuation lines, ending at the first blank line,
    options-section header, or column-0 line (so it never absorbs the options section). Then:
      - from the FIRST `usage:` line, every flag token (a value after `=` is excluded by FLAG_RE's
        lookbehind) - this covers a bare required option (argparse prints it unbracketed) and bracketed
        optionals alike;
      - from each wrapped CONTINUATION line, only flags inside a `[...]` group (a real wrapped optional).
    A bare flag-shaped token on a continuation line, or a flag named in prose, is NOT a synopsis optional
    and is ignored - so a phantom cannot enter witness-1 (this is the boundary a raw-token scan got wrong).
    A truncated `[options]` synopsis yields no flags; a `usage:` line forged later (an epilog) injects nothing."""
    lines = text.splitlines()
    start = next((i for i, ln in enumerate(lines) if USAGE_HDR_RE.match(ln)), None)
    if start is None:
        return set()
    block = [lines[start]]
    for ln in lines[start + 1:]:
        if ln.strip() == "" or SECTION_HDR_RE.match(ln) or not ln[:1].isspace():
            break                     # a blank line, an options header, or a column-0 line ends the synopsis
        block.append(ln)
    flags = set(FLAG_RE.findall(block[0]))                       # first usage line: bare + bracketed optionals
    for ln in block[1:]:                                         # continuations: only bracketed optionals
        for grp in re.findall(r"\[([^\]]*)\]", ln):
            flags.update(FLAG_RE.findall(grp.split("=")[0]))
    return flags


def _options_section_clusters(text):
    """Witness-2: the option-definition CLUSTERS at the definition column inside a detected options
    section (an `options:` / `optional arguments:` / `flags:` header to the next column-0 line). Each
    cluster is the flag tokens of one definition line's leading cluster (`-j, --json` -> {-j, --json}).
    Column-anchored to the shallowest indent, so a wrapped description line (deeper column) or a flag
    named inside a description never becomes a definition. Empty if no section (hand-rolled help)."""
    lines = text.splitlines()
    in_sec = False
    defs = []
    for ln in lines:
        if SECTION_HDR_RE.match(ln):
            in_sec = True
            continue
        if in_sec and re.match(r"^\S", ln):   # a column-0 line ends the section
            in_sec = False
        if in_sec:
            m = OPT_RE.match(ln)
            if m:
                defs.append((len(m.group(1)), set(FLAG_RE.findall(m.group(2)))))
    if not defs:
        return []
    col = min(ind for ind, _ in defs)
    return [flags for ind, flags in defs if ind == col]


def capture_help(cmd_str):
    """Read-only executed capture for the cli oracle tier - the two-witness sound-tier.

    Runs ONLY the command-path tokens + `--help` and returns `(oracle_tier, verified)`:
      - shlex-split the declared command and DROP every token starting with '-', so no invocation flag
        ever executes (a mutating / `--dangerous` flag is stripped, never spawned);
      - reject a token carrying a shell metacharacter or '=' - defense-in-depth on the no-shell spawn;
      - keep the FULL command path (binary + every subcommand word); append only `--help`; list-form
        (shell=False) with a timeout. This adds NO new execution surface over the prior capture.
    The `cmd:` is a read-only command path the maintainer declares (same trust model as `said-recompute`
    / `SAID.commands`); the engine forwards no flag and appends only `--help`.

    `oracle_tier` is True iff the --help presents BOTH machine witnesses: a first usage-synopsis block
    that enumerates flags (witness-1) AND an options section with a definition column (witness-2). Both
    present signals framework-generated help, where the options column is the parser's own authoritative
    flag list. Missing either witness -> False, and the caller keeps the unit at declared-evidence
    (manifest) - never a false FAIL (hand-rolled help, or a truncated `[options]` synopsis).

    `verified` is the flag tokens of every option-definition cluster CORROBORATED by the usage synopsis
    (shares >=1 token with witness-1). Cluster-level, so an aliased flag (usage shows `-j`, the section
    lists `-j, --json`) is verified for either spelling; a lone option-column line not in the synopsis (a
    hand-added or prose-injected flag) is NOT verified. Empty when not oracle_tier.

    Soundness: a flag named only in prose, an epilog, a description column, a markdown bullet, or a forged
    non-first `usage:` line is in neither witness, so it is never verified - closing the indented
    flag-initial prose residual a single-witness line scan could not. The honest residual (an inherent
    ceiling): a flag presented as a real option in BOTH the synopsis and the options column is trusted; a
    tool that prints a phantom flag in both surfaces has its own --help bug, not a completeness miss.
    """
    bad = re.compile(r"[;&|<>`$()=]")   # shell control / redirect / subshell / operand=value
    try:
        toks = shlex.split(cmd_str)
    except ValueError as e:
        die("FAIL: capture cmd %r is not a parseable command (%s)" % (cmd_str, e), 2)
    path = []
    for t in toks:
        if t.startswith("-"):
            continue                    # a flag from the invocation - never executed
        if bad.search(t):
            die("FAIL: capture cmd token %r is not a command-path word (shell metacharacter or '=')" % t, 2)
        path.append(t)
    if not path:
        die("FAIL: capture cmd %r has no command-path token (only flags?)" % cmd_str, 2)
    try:
        proc = subprocess.run(path + ["--help"], capture_output=True, text=True, timeout=10, check=False)
    except (OSError, ValueError, subprocess.SubprocessError) as e:
        die("FAIL: read-only capture spawn failed for %r: %s" % (" ".join(path), e), 1)
    # Two-witness extraction. A single-witness scan (any indented flag-initial line) could not reject an
    # indented flag-initial PROSE line - it was miscounted. A flag is now oracle-verified only
    # where TWO machine-emitted witnesses agree: the first usage-synopsis block (witness-1) AND an
    # option-definition cluster in the options section (witness-2), the cluster corroborated by the synopsis.
    text = (proc.stdout or "") + "\n" + (proc.stderr or "")
    usage = _usage_synopsis_flags(text)          # witness-1
    clusters = _options_section_clusters(text)   # witness-2 (option-definition clusters, column-anchored)
    if not (usage and clusters):
        return False, set(), []                  # not two-witness parseable -> caller keeps declared-evidence
    verified = set()
    corroborated = []
    for cl in clusters:
        if cl & usage:                           # cluster corroborated by the usage synopsis
            verified |= cl
            corroborated.append(frozenset(cl))   # keep clusters so alias groups stay intact (BUILT-DESIGNED WARN)
    return True, verified, corroborated


def capture_web(cmd_str):
    """Executed read-only capture for a non-cli (e.g. web) oracle tier: run the
    front-supplied probe command AS DECLARED and read the built element keys it lists, one per line.
    Unlike the cli `--help` capture there is no universal read-only convention to enforce, so the front
    owns the probe's read-only-ness - the same trust model as `said-recompute` / `SAID.commands` (a
    declared command the engine runs); the engine runs it list-form (shell=False) with a timeout, never
    a shell. This ships the engine contract + a hermetic fixture; a real front lane supplies the concrete
    DOM/route probe under its own SAID cycle."""
    try:
        argv = shlex.split(cmd_str)
    except ValueError as e:
        die("FAIL: capture cmd %r is not a parseable command (%s)" % (cmd_str, e), 2)
    if not argv:
        die("FAIL: capture cmd %r is empty" % cmd_str, 2)
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=10, check=False)
    except (OSError, ValueError, subprocess.SubprocessError) as e:
        die("FAIL: read-only capture spawn failed for %r: %s" % (" ".join(argv), e), 1)
    out = (proc.stdout or "") + "\n" + (proc.stderr or "")
    return set(line.strip() for line in out.splitlines() if line.strip())


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

    designed, container_of, headers = parse_designed(toc, g["unit"], g["containers"], g["attributes"], g["not_elements"])

    # DIR: unit-home -> the DURABLE is the source of truth. Re-derive DESIGNED by parsing each DECLARED
    # unit's durable <lane-root>/<path>/<ID>.md DIRECTLY (H1-headed, level=1); the toc supplies ONLY the
    # manifest (the grammar stamp checked above + the sealed `units:` line + the `## <unit>` outline headers
    # check_unit_home cross-checks). This makes the operator-authored durable, not the toc mirror, what
    # gates - a durable and a stale mirror can no longer disagree about the design. An `inline` (or absent)
    # unit-home keeps parsing the toc, unchanged (the unit-home is the ONLY switch - the engine holds no
    # medium vocabulary). Each durable must head its OWN unit id (identity cross-check); a missing durable is
    # reported by check_unit_home (broken-link) below.
    _dh = _dir_home(g, grammar)
    if _dh is not None:
        _rel, _ddir = _dh
        _declared = read_units_decl(toc)
        if _declared is None:
            die("FAIL: unit-home is `dir:` but toc.md has no sealed `units: A;B;C (count: N)` line - the "
                "durable-spec check reads the DECLARED unit set from it; re-emit with uxtoc", 1)
        designed, container_of = set(), {}
        for _u in sorted(_declared):
            _dpath = os.path.join(_ddir, _u + ".md")
            if not os.path.isfile(_dpath):
                continue                       # a missing durable is the broken-link check_unit_home reports
            _du, _dc, _dhdr = parse_designed(_dpath, g["unit"], g["containers"], g["attributes"], g["not_elements"], level=1)
            if _dhdr != {_u}:
                _found = ", ".join(sorted(_dhdr)) or "no unit"
                die("FAIL: durable %s.md heads unit(s) {%s}, not its own id %r - a copied, renamed, "
                    "mis-levelled, or empty durable answering for another unit; each `dir:` durable heads "
                    "`# %s <ID>` for its own id (re-name or re-level it)" % (_u, _found, _u, g["unit"]), 1)
            designed |= _du
            container_of.update(_dc)

    if not designed:
        die("FAIL: zero designed elements (hollow - nothing to certify complete; no keyed elements under "
            "container headers, or set Surface: none)", 1)

    # resolve the grammar's unit-home: a `dir:` lane's durable per-unit specs are enforced (a missing
    # <ID>.md -> FAIL, an orphan durable file -> FAIL); an inline lane skips. Presence-only (no-seal-safe).
    # The DECLARED unit set is read from the sealed `units:` line uxtoc stamps (no prose inference); it is
    # cross-checked against BOTH the element-projecting units and the outline's `## <unit> <ID>` headers.
    # check_unit_home reads the line ONLY for a `dir:` lane (an inline lane never touches it).
    check_unit_home(g, grammar, toc, {u for (u, _k) in designed}, headers)

    # BUILT capture. For a unit whose manifest declares a `cmd:`, the grammar's oracle-containers are
    # verified author-independently by executing the command's own --help (capture_help, read-only);
    # everything else is read from the manifest (declared-evidence). The bare `recomputed` sentinel
    # carries no manifest, so there is no `cmd:` to spawn - unsupported.
    if cap == "recomputed":
        die("bare `recomputed` sentinel: no manifest, so no per-unit `cmd:` to spawn; supply a capture "
            "manifest (its `cmd:` lines drive the executed --help capture, its `built:` lines the rest)", 2)
    if not os.path.isfile(cap):
        die("no capture manifest at %s" % cap, 2)
    built, dropped, cmds = read_manifest(cap)

    # executed read-only capture for the oracle tier (two-witness). A designed element in an
    # oracle-container whose unit declares a `cmd:` is proven BUILT only where the command's own --help is
    # two-witness parseable AND the flag is verified by both witnesses (a manifest `built:` cannot bluff
    # it). A unit whose --help is NOT two-witness parseable (hand-rolled help / truncated synopsis) stays
    # declared-evidence (manifest) - the honest fallback, never a false FAIL. A unit without a `cmd:` is
    # declared-evidence too.
    oracle_built, oracle_units, help_cache = set(), set(), {}
    for (u, key) in designed:
        if container_of.get((u, key)) not in g["oracle_containers"] or u not in cmds:
            continue
        if u not in help_cache:
            # cli: capture_help returns (oracle_tier, verified, clusters). web: the front-supplied probe is
            # machine output (built keys, one per line), always oracle-tier; each key is its own cluster (no
            # aliases). SAID_SURFACE selects.
            if surface == "cli":
                help_cache[u] = capture_help(cmds[u])
            else:
                keys = capture_web(cmds[u])
                help_cache[u] = (True, keys, [frozenset({k}) for k in keys])
            if help_cache[u][0]:
                oracle_units.add(u)          # only a two-witness-parseable tool is oracle-enforced
        tier, verified = help_cache[u][0], help_cache[u][1]
        if tier and key in verified:
            oracle_built.add((u, key))

    def oracle_executed(u, key):
        return u in oracle_units and container_of.get((u, key)) in g["oracle_containers"]

    missing = []
    for (u, key) in sorted(designed):
        if (u, key) in dropped:
            continue
        if oracle_executed(u, key):
            if (u, key) not in oracle_built:
                missing.append(u + " / " + key + " (oracle: absent from executed --help)")
        elif (u, key) not in built:
            missing.append(u + " / " + key)
    if missing:
        die("FAIL: designed elements neither built nor dropped: %s" % ", ".join(missing), 1)

    # built-floor: at least one designed element must actually be built - by the executed capture (oracle
    # tier) or the manifest (declared-evidence). Scoped to `designed` (not raw `built:`): a stray/stale
    # key cannot satisfy it. Every designed element dropped => the comparison holds vacuously while the
    # feature ships nothing; a legitimate partial-drop keeps >=1 designed element built and PASSes.
    if not ((built & designed) | oracle_built):
        die("FAIL: no designed element is built (every designed element dropped) - vacuous completeness; "
            "a delivered feature builds at least one designed element", 1)

    # BUILT - DESIGNED: an element present in BUILT but absent from the outline (under-specification) is a
    # non-blocking WARN, NEVER a FAIL - a built-but-undesigned element may be intentional, and a WARN keeps
    # the no-seal substrate intact (the comparison is one-directional by design). Signal scales with capture
    # independence: a flag the author-independent --help presents but the outline never designed is
    # high-signal; a builder-declared manifest key is advisory. The verdict states which.
    # Cluster-aware + boilerplate-aware: a corroborated --help cluster under-specifies the outline only when
    # NONE of its flag tokens is designed for the unit (so an alias group `-j, --json` is covered when either
    # spelling is designed - mirroring the FAIL direction's cluster-level resolution) AND it is not a pure
    # auto-added boilerplate cluster (-h/--help/--version). Report one representative token (prefer a long
    # `--flag`). Without this the high-signal channel fires on every framework boilerplate flag and on the
    # short alias of a designed long flag - noise that trains operators to ignore it.
    designed_by_unit = {}
    for (du, dk) in designed:
        designed_by_unit.setdefault(du, set()).add(dk)
    def _cluster_rep(cl):
        longs = sorted((t for t in cl if t.startswith("--")), key=len, reverse=True)
        return longs[0] if longs else sorted(cl)[0]
    def _is_boilerplate(cl):
        # judged by the LONG form: `-v, --version` is boilerplate (long is `--version`), but `-h, --hard-reset`
        # is NOT (a real flag that merely shares a short letter). A lone short flag with no long form falls back
        # to the unambiguous-help short set.
        longs = {t for t in cl if t.startswith("--")}
        return bool(longs & BOILERPLATE_LONG) if longs else bool(cl & BOILERPLATE_SHORT)
    oracle_under = set()
    oracle_seen_tokens = set()                    # EVERY token in ANY corroborated --help cluster of an oracle
                                                  # unit - an oracle observation, so manifest_under never re-lists
                                                  # it (incl. an alias-covered or boilerplate cluster's tokens).
    for u in oracle_units:
        for cl in help_cache[u][2]:
            oracle_seen_tokens |= {(u, t) for t in cl}
            if cl & designed_by_unit.get(u, set()):
                continue                          # some spelling is designed -> alias group covered
            if _is_boilerplate(cl):               # auto-added help/version cluster -> not under-spec
                continue
            oracle_under.add((u, _cluster_rep(cl)))
    manifest_under = (built - designed) - oracle_seen_tokens
    if oracle_under or manifest_under:
        parts = []
        if oracle_under:
            parts.append("author-independent --help presents, outline under-specifies (high-signal): "
                         + ", ".join(sorted("%s / %s" % p for p in oracle_under)))
        if manifest_under:
            parts.append("manifest-declared (advisory): "
                         + ", ".join(sorted("%s / %s" % p for p in manifest_under)))
        sys.stderr.write("completeness WARN: built element(s) absent from DESIGNED (under-specified "
                         "outline; not a FAIL) -- %s\n" % "; ".join(parts))

    # Own the coverage ceiling: a designed oracle-container flag can fall to declared-evidence when its unit
    # DECLARED a capture cmd: but the tool's --help is not two-witness parseable (hand-formatted / truncated
    # synopsis). That is a legitimate honest fallback (it PASSes, manifest-built) but must not be SILENT -
    # WARN so a reader knows those flags are author-trusted (manifest), not author-independently verified.
    for u in sorted(help_cache):
        if help_cache[u][0]:
            continue                      # two-witness parseable -> genuinely oracle-verified, no ceiling
        fell = sorted(k for (uu, k) in designed
                      if uu == u and container_of.get((uu, k)) in g["oracle_containers"] and (uu, k) not in dropped)
        if fell:
            sys.stderr.write(
                "completeness WARN: unit %r declares a capture cmd but its --help is not two-witness "
                "parseable; %d designed oracle flag(s) verified by declared-evidence (manifest), NOT "
                "author-independently -- coverage ceiling: %s\n" % (u, len(fell), ", ".join(fell)))

    oracle_intended = sum(1 for k in designed if container_of.get(k) in g["oracle_containers"])
    if oracle_units:
        cap_note = ("oracle-verified: %d/%d in %d two-witness oracle unit(s); rest manifest/declared-evidence"
                    % (len(oracle_built), oracle_intended, len(oracle_units)))
    else:
        cap_note = ("capture: manifest/declared-evidence; %d in oracle-intended containers "
                    "(no author-independent capture available)" % oracle_intended)
    print("completeness PASS: %d designed <= %d built + %d dropped (%s)"
          % (len(designed), len(built), len(dropped), cap_note))
    sys.exit(0)


if __name__ == "__main__":
    main()
