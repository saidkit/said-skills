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
        return False, set()                      # not two-witness parseable -> caller keeps declared-evidence
    verified = set()
    for cl in clusters:
        if cl & usage:                           # cluster corroborated by the usage synopsis
            verified |= cl
    return True, verified


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

    designed, container_of = parse_designed(toc, g["unit"], g["containers"], g["attributes"], g["not_elements"])
    if not designed:
        die("FAIL: toc.md yields zero designed elements (hollow - nothing to certify complete; no "
            "keyed elements under container headers, or set Surface: none)", 1)

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
            # cli: capture_help returns (oracle_tier, verified). web: the front-supplied probe is machine
            # output (built keys, one per line), always oracle-tier. SAID_SURFACE selects.
            if surface == "cli":
                help_cache[u] = capture_help(cmds[u])
            else:
                help_cache[u] = (True, capture_web(cmds[u]))
            if help_cache[u][0]:
                oracle_units.add(u)          # only a two-witness-parseable tool is oracle-enforced
        tier, verified = help_cache[u]
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
                    "(no two-witness-parseable capture)" % oracle_intended)
    print("completeness PASS: %d designed <= %d built + %d dropped (%s)"
          % (len(designed), len(built), len(dropped), cap_note))
    sys.exit(0)


if __name__ == "__main__":
    main()
