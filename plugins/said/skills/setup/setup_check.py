#!/usr/bin/env python3
"""Deterministic well-formed-lane checker for said:setup (read-only).

Reads a lane's CLAUDE.md ## Lane block + required sections and evaluates them
against the machine-readable schema (references/lane-schema.json, read WHOLE).
Emits a per-item ledger grouped by severity and exits non-zero when any BLOCKER
is present, so said:setup renders findings deterministically rather than by
judgement, and the same oracle backs the eval's negative control.

Reviewer resolvability reuses the canonical Checker resolver shipped beside this
file (../status/said_status.py: index_checkers / resolve_checkers_dir), rather
than re-implementing it. The lane-block parse lives here because no shipped
reader parses the block (the status skill supplies --lane values by hand).

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


def read_lane_block(claude_md):
    """Return (full_text, block_text). block_text = lines from '## Lane' to the
    next '## ' heading or EOF; '' if there is no lane block."""
    with open(claude_md, encoding="utf-8") as fh:
        text = fh.read()
    lines = text.splitlines()
    block, in_block = [], False
    for ln in lines:
        if re.match(r"^## Lane\b", ln):
            in_block = True
            continue
        if in_block and re.match(r"^## ", ln):
            break
        if in_block:
            block.append(ln)
    return text, "\n".join(block)


def axis_value(block, key):
    """Return the scalar value for SAID.<key> in the block, or None if absent.
    Unanchored key-grep on the whole line, matching the consume contract."""
    m = re.search(r"^\s*[-*]?\s*%s:\s*(.*?)\s*$" % re.escape(key), block, re.M)
    return m.group(1) if m else None


def parse_reviewers(val):
    """Parse a list value like '[cli-gate, web-ux]' into ['cli-gate','web-ux']."""
    if not val:
        return []
    inner = val.strip().strip("[]")
    return [r.strip() for r in inner.split(",") if r.strip()]


def has_section(text, heading, match):
    if match == "exact":
        return any(ln.strip() == heading for ln in text.splitlines())
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


def check_block_invariants(block, schema):
    """Evaluate the block-shape invariants (STALE): a duplicated scalar key, a key line
    carrying a trailing comment/parenthetical/aside, or prose between key lines. Prose
    ABOVE the first key or BELOW the last is allowed (a lane may say what it is / how it
    routes); only lines strictly between keys must be key lines."""
    out = []
    inv = {i["id"]: i for i in schema.get("block_invariants", [])}
    lines = block.splitlines()
    keyline_re = re.compile(r"^\s*[-*]?\s*SAID\.[\w-]+:")
    key_idx = [n for n, ln in enumerate(lines) if keyline_re.match(ln)]
    list_keys = {a["key"] for a in schema["axes"] if a.get("kind") == "list"}
    if "single-hit-scalar" in inv:
        counts = {}
        for n in key_idx:
            k = re.search(r"SAID\.[\w-]+", lines[n]).group(0)
            counts[k] = counts.get(k, 0) + 1
        for k, c in counts.items():
            if c > 1 and k not in list_keys:
                out.append({"item": "invariant:single-hit-scalar", "verdict": "stale",
                            "severity": inv["single-hit-scalar"]["severity"],
                            "remediation": "%s is declared %d times; %s" % (k, c, inv["single-hit-scalar"]["rule"])})
    if "one-line-value" in inv:
        for n in key_idx:
            if re.search(r"SAID\.[\w-]+:\s*\S.*(#|\s--\s|\s\(|\.\.\.)", lines[n]):
                out.append({"item": "invariant:one-line-value", "verdict": "stale",
                            "severity": inv["one-line-value"]["severity"],
                            "remediation": "a key line carries a trailing comment/parenthetical/aside; %s" % inv["one-line-value"]["rule"]})
                break
    if "keys-only-block" in inv and key_idx:
        for n in range(key_idx[0], key_idx[-1] + 1):
            if lines[n].strip() and not keyline_re.match(lines[n]):
                out.append({"item": "invariant:keys-only-block", "verdict": "stale",
                            "severity": inv["keys-only-block"]["severity"],
                            "remediation": "non-key line between keys (%r); %s" % (lines[n].strip()[:40], inv["keys-only-block"]["rule"])})
                break
    return out


def check_lane(lane_root, schema, claude_md=None):
    """Evaluate the lane at lane_root against schema. Return a list of findings:
    dicts {item, verdict, severity, remediation}. verdict in ok/stale/missing/unresolvable."""
    claude_md = claude_md or os.path.join(lane_root, "CLAUDE.md")
    findings = []
    if not os.path.isfile(claude_md):
        findings.append({"item": "CLAUDE.md", "verdict": "missing", "severity": "BLOCKER",
                         "remediation": "no CLAUDE.md at the lane root; the lane is invisible to the cycle"})
        return findings
    text, block = read_lane_block(claude_md)

    # Required sections
    for sec in schema["required_sections"]:
        present = has_section(text, sec["heading"], sec.get("match", "leading-words"))
        findings.append({"item": sec["heading"], "verdict": "ok" if present else "missing",
                         "severity": sec["severity_if_missing"] if not present else "OK",
                         "remediation": "" if present else sec["remediation"]})

    surface = axis_value(block, "SAID.surface")
    # Axes
    for ax in schema["axes"]:
        val = axis_value(block, ax["key"])
        present = val is not None and val != ""
        if present and ax.get("kind") == "list" and val.strip() in ("[]", "[ ]"):
            present = False  # an empty list is not a declared value; a surface-bearing lane with reviewers: [] is a nominal gate
        required = ax.get("required", False)
        if ax.get("required_if") == "surface != none":
            required = (surface not in (None, "", "none"))
        if present:
            findings.append({"item": ax["key"], "verdict": "ok", "severity": "OK", "remediation": ""})
        elif required:
            findings.append({"item": ax["key"], "verdict": "missing", "severity": ax["severity_if_missing"],
                             "remediation": ax["remediation"]})
        # absent + not required: not reported (a clean omission of an optional axis)

    # Withdrawn axes (flag if present anywhere in the file)
    for w in schema["withdrawn_axes"]:
        if axis_value(text, w["key"]) is not None:
            findings.append({"item": w["key"], "verdict": "stale", "severity": w["severity"],
                             "remediation": w["remediation"]})

    # Block-shape invariants
    findings.extend(check_block_invariants(block, schema))

    # Reviewer resolvability (surface-bearing lanes)
    if surface not in (None, "", "none"):
        reviewers = parse_reviewers(axis_value(block, "SAID.reviewers"))
        docs_root = axis_value(block, "SAID.docs-root") or "docs"
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
    docs_root = axis_value(block, "SAID.docs-root") or "docs"
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
