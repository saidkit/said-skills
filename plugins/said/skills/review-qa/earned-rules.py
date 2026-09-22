#!/usr/bin/env python3
"""earned-rules — count and check a lane's `## Earned rules` section (SAID contract).

Usage:
  earned-rules.py count <CLAUDE.md>
      Prints the rule count, then the citable ids, then any uncitable lines.
      Exit 0; exit 3 when the file has no `## Earned rules` heading; exit 2 on a config error.
  earned-rules.py check --claude-md <CLAUDE.md> --task-file <tasks.md-or-excerpt> [--task-id <id>] --adr-date YYYY-MM-DD
      Reads the task's `Status: Done (YYYY-MM-DD)` date and its `### Fix` block, finds the
      `Rules applied: <ids | none> (block: N)` line, and prints PASS / WARN / FAIL with a reason.
      Grammar accepted: ids separated by commas or spaces, bare or backticked; an optional
      leading bullet/backtick; `(block:N)` with or without a space; an optional trailing period.
      Verdicts: cited id not in the section -> FAIL, claimed N > actual -> FAIL, claimed N < actual
      -> WARN "block grew since close" (a later rule is not a false close), absent line, heading present
      -> FAIL on/after --adr-date, WARN before (the heading is the lane's adoption marker; the date is the
      fallback for a rolled lane's pre-contract closes), no heading in CLAUDE.md -> WARN, never FAIL
      (roll the lane; the HALT on an un-rolled lane is the implement skill's, at close time).
      Then each CITED rule's linked record is checked against the strict grammar (the record = the rule
      line's FINAL arrow segment = one lane-root-relative path token, an optional `#anchor` stripped,
      nothing after it): conforming + resolves (opens as a regular file from the lane root by ANY path
      form, `..` or symlink alike) -> PASS; conforming + unresolvable -> dangling; an arrow present but its
      tail non-conforming (trailing prose, a second arrow, a pathless id, a ?query) -> malformed; dangling
      and malformed both WARN before --link-contract-date / FAIL on-or-after (the task Status-date pivot);
      a rule line with no arrow at all -> no-link, WARN, never FAIL.
      Exit 0 = PASS or WARN, 1 = FAIL, 2 = config error.

Section definition (the contract):
  * the section starts at a line matching ^## Earned rules (leading-words match) and ends at the
    next ^## heading or EOF;
  * a rule is a line matching ^- (an indented sub-bullet does not count);
  * a rule's id is the first token matching R-[A-Z]+-[A-Z0-9-]+ on its line; a rule without one
    is counted but cannot be cited.
Example id shapes: R-PROJ-01, R-PROJ-FE-07.
"""
import argparse
import os
import re
import sys

HEADING = re.compile(r"^## Earned rules")
NEXT_HEADING = re.compile(r"^## ")
RULE_LINE = re.compile(r"^- ")
ID_TOKEN = re.compile(r"(?<![A-Za-z])R-[A-Z]+-[A-Z0-9-]+")  # a whole token: `ADR-...` never yields an id
APPLIED_LINE = re.compile(r"^Rules applied:\s*(?P<ids>.*?)\s*\(block:\s*(?P<n>\d+)\)\s*\.?\s*$")
LINE_PREFIX = re.compile(r"^\s*(?:[-*]\s+)?`?\s*")  # a bullet marker and/or a backtick before the line is tolerated
DONE_DATE = re.compile(r"\*\*Status:\*\*\s*Done\s*\((\d{4}-\d{2}-\d{2})\)|^Status:\s*Done\s*\((\d{4}-\d{2}-\d{2})\)", re.M)
# A rule line's linked record (the earned-rules contract): the record is the line's FINAL
# `->` / Unicode-right-arrow segment = exactly ONE path token, bare or backticked, lane-root-relative, an
# optional `#anchor` allowed and stripped, with NOTHING after it. This is a strict grammar, not a
# heuristic: a tail that does not match (trailing prose, a second arrow after the path, a pathless id,
# stray punctuation, a `?query`) is MALFORMED -- never silently "no link". The arrow is built with chr()
# so the source stays plain-ASCII (no glyph in the file) while matching the real glyph in a rule line.
_ARROW = chr(0x2192)
# The whole tail after the final arrow: a lone path token (optionally backticked), an optional #anchor, nothing else.
_TAIL_RE = re.compile(r"^`?(?P<path>[\w./@~-]+?)(?:#[\w./@~-]+)?`?$")


def parse_link(line):
    """Classify a rule line's linked record per the strict grammar. Returns (kind, token):
      'conforming' -- the tail is a lone path token; token is that path (lane-root-relative, #anchor stripped);
      'malformed'  -- an arrow is present but its final segment is not a lone path token (trailing prose, a
                      second arrow after the path, a pathless id, a ?query, stray punctuation);
      'no-link'    -- the line carries no arrow at all.
    Resolution is the caller's job; a pathless token (no `/` and no `.`) is not a path and reads MALFORMED."""
    a_ascii, a_glyph = line.rfind("->"), line.rfind(_ARROW)
    if a_ascii < 0 and a_glyph < 0:
        return ("no-link", None)
    tail = (line[a_glyph + len(_ARROW):] if a_glyph > a_ascii else line[a_ascii + 2:]).strip()
    m = _TAIL_RE.match(tail)
    if not m:
        return ("malformed", None)
    tok = m.group("path")
    if "/" not in tok and "." not in tok:  # a bare record id (no path separator, no extension) is not a path token
        return ("malformed", None)
    return ("conforming", tok)


def read_section(path):
    """Return (count, citable_ids, uncitable_lines) or None when the heading is absent."""
    try:
        lines = open(path, encoding="utf-8").read().splitlines()
    except OSError as e:
        print(f"config error: cannot read {path}: {e}", file=sys.stderr)
        sys.exit(2)
    start = next((i for i, l in enumerate(lines) if HEADING.match(l)), None)
    if start is None:
        return None
    body = []
    for l in lines[start + 1:]:
        if NEXT_HEADING.match(l):
            break
        body.append(l)
    rules = [l for l in body if RULE_LINE.match(l)]
    ids, uncitable = [], []
    for l in rules:
        m = ID_TOKEN.search(l)
        (ids if m else uncitable).append(m.group(0) if m else l.strip())
    return len(rules), ids, uncitable


def rule_links(path):
    """id -> (kind, token) per parse_link, for each CITABLE rule line only. Uncitable rule lines (no id)
    are never cited, so they are skipped. Resolution is the caller's job (relative to the --claude-md's
    directory, symlink-following)."""
    try:
        lines = open(path, encoding="utf-8").read().splitlines()
    except OSError:
        return {}
    start = next((i for i, l in enumerate(lines) if HEADING.match(l)), None)
    if start is None:
        return {}
    out = {}
    for l in lines[start + 1:]:
        if NEXT_HEADING.match(l):
            break
        if not RULE_LINE.match(l):
            continue
        m = ID_TOKEN.search(l)
        if not m:
            continue
        out[m.group(0)] = parse_link(l)
    return out


def link_resolves(base_dir, link):
    """A cited link 'resolves' when it opens as a regular FILE from the lane root (relative to the
    --claude-md's directory) by ANY path form -- a `..` cross-lane link and a symlinked dir alike, both
    following symlinks. Resolution is by REACHABILITY, not spelling: cross-lane `..` record links are the
    established pattern across the workspace's lanes, and the accepted gitignored docs/ -> sibling symlink
    is equally non-portable, so singling out `..` was a false distinction. Rejections: an absolute link
    (os.path.join would discard the base, and a lane record is lane-relative); a directory (isfile, not
    exists -- a directory is not a record)."""
    if not link or os.path.isabs(link):
        return False
    return os.path.isfile(os.path.join(base_dir, link))


def cmd_count(args):
    sec = read_section(args.claude_md)
    if sec is None:
        print(f"no `## Earned rules` section in {args.claude_md} — add one (a `- ` line per rule, an R-* id, a link to its ADR), then re-run")
        return 3
    n, ids, unc = sec
    print(n)
    print("ids: " + (" ".join(ids) if ids else "(none)"))
    for u in unc:
        print(f"uncitable: {u}")
    # Advisory whole-block link-health -- non-gating (count is an echo, never a verdict). This is where an
    # UNCITED dangling/no-link rule surfaces, without blocking any close.
    links = rule_links(args.claude_md)
    base = os.path.dirname(os.path.abspath(args.claude_md))
    for rid, (kind, tok) in links.items():
        if kind == "conforming" and not link_resolves(base, tok):
            print(f"link-advisory: {rid} -> {tok} (missing)")
        elif kind == "malformed":
            print(f"link-advisory: {rid} (malformed link: the final arrow segment is not a lone path token)")
        elif kind == "no-link":
            print(f"link-advisory: {rid} (no linked record)")
    return 0


def fix_block(text, task_id=None):
    if task_id:
        m = re.search(rf"^## {re.escape(task_id)}:.*?(?=^## |\Z)", text, re.M | re.S)
        if not m:
            print(f"config error: task {task_id} not found", file=sys.stderr)
            sys.exit(2)
        text = m.group(0)
    m = re.search(r"^### Fix\s*\n(.*?)(?=^### |\Z)", text, re.M | re.S)
    return text, (m.group(1) if m else "")


def cmd_check(args):
    sec = read_section(args.claude_md)
    try:
        raw = open(args.task_file, encoding="utf-8").read()
    except OSError as e:
        print(f"config error: cannot read {args.task_file}: {e}", file=sys.stderr)
        return 2
    entry, fix = fix_block(raw, args.task_id)
    dm = DONE_DATE.search(entry)
    done = (dm.group(1) or dm.group(2)) if dm else None
    if sec is None:
        # A lane that has not been rolled: the HALT belongs to impl (it will not close there); the
        # sweep only points at the roll — never a FAIL it cannot act on.
        print(f"WARN — no `## Earned rules` section in {args.claude_md}; task closed {done or 'undated'} — roll the lane (add the section), then re-run (operator-verify)")
        return 0
    n, ids, _ = sec
    line = next((LINE_PREFIX.sub("", l) for l in fix.splitlines() if LINE_PREFIX.sub("", l).startswith("Rules applied:")), None)
    if line is None:
        if done and done < args.adr_date:
            print(f"WARN — no `Rules applied:` line; task closed {done}, before the contract date {args.adr_date} (operator-verify)")
            return 0
        print(f"FAIL — no `Rules applied:` line in `### Fix` (task closed {done or 'undated'}, contract date {args.adr_date})")
        return 1
    m = APPLIED_LINE.match(line.strip().rstrip("`").strip())
    if not m:
        print(f"FAIL — malformed line: {line.strip()!r} (expected `Rules applied: <ids | none> (block: N)`)")
        return 1
    claimed_n = int(m.group("n"))
    ids_text = m.group("ids").strip().strip("`").strip()
    cited = [] if ids_text.lower() in ("none", "") else list(dict.fromkeys(ID_TOKEN.findall(ids_text)))
    if ids_text.lower() not in ("none", "") and not cited:
        print(f"FAIL — malformed ids: {ids_text!r} (expected R-* tokens or `none`)")
        return 1
    bad = [c for c in cited if c not in ids]
    if bad:
        print(f"FAIL — cited id(s) not in the lane's `## Earned rules`: {', '.join(bad)}")
        return 1
    if claimed_n > n:
        print(f"FAIL — block count {claimed_n} > actual {n} rules in {args.claude_md}")
        return 1
    # Classify each CITED rule's linked record per the strict grammar, INDEPENDENTLY of the block-count
    # comparison -- a link FAIL must never be skipped by an under-claimed (block-grew) WARN (a close
    # answers only for what it cites). conforming+resolves -> ok; conforming+unresolvable -> dangling;
    # arrow present but tail not a lone path token -> malformed; no arrow -> no-link. dangling + malformed
    # pivot on the linked-record contract date via the task Status-date; an UNDATED close fails CLOSED (an
    # unknown date is not evidence of being before the pivot), the same polarity as the missing-line branch
    # above. Only after the links clear does the block-grew WARN (a later rule is not a false close) fire.
    links = rule_links(args.claude_md)
    base = os.path.dirname(os.path.abspath(args.claude_md))
    dangling = [c for c in cited if links.get(c, ("no-link", None))[0] == "conforming" and not link_resolves(base, links[c][1])]
    malformed = [c for c in cited if links.get(c, ("no-link", None))[0] == "malformed"]
    nolink = [c for c in cited if links.get(c, ("no-link", None))[0] == "no-link"]
    grew = f"; block grew since close ({claimed_n} then, {n} now, cited ids verified)" if claimed_n < n else ""
    if dangling or malformed:
        parts = []
        if dangling:
            parts.append(f"link to a missing record: {', '.join(dangling)}")
        if malformed:
            parts.append(f"a malformed link (the final arrow segment is not a lone path token): {', '.join(malformed)}")
        detail = "; ".join(parts)
        if done and done < args.link_contract_date:  # only a DATED close before the pivot gets the grace WARN
            print(f"WARN -- cited rule(s) {detail} (task closed {done}, before the linked-record contract date {args.link_contract_date}; operator-verify){grew}")
            return 0
        print(f"FAIL -- cited rule(s) {detail} (task closed {done or 'undated'}, linked-record contract date {args.link_contract_date})")
        return 1
    if nolink:
        print(f"WARN -- cited rule(s) carry no linked record: {', '.join(nolink)} (no arrow on the rule line, operator-verify){grew}")
        return 0
    if claimed_n < n:
        print(f"WARN — block grew since close: {claimed_n} then, {n} now in {args.claude_md}; cited ids verified (operator-verify)")
        return 0
    print(f"PASS — {len(cited)} id(s) cited, block {n} verified")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="earned-rules.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("count"); c.add_argument("claude_md"); c.set_defaults(fn=cmd_count)
    k = sub.add_parser("check"); k.add_argument("--claude-md", required=True); k.add_argument("--task-file", required=True)
    k.add_argument("--task-id"); k.add_argument("--adr-date", required=True)
    k.add_argument("--link-contract-date", default="2026-09-22")  # the linked-record grammar's phased date (WARN before, FAIL on/after)
    k.set_defaults(fn=cmd_check)
    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
