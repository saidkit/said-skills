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
import re
import sys

HEADING = re.compile(r"^## Earned rules")
NEXT_HEADING = re.compile(r"^## ")
RULE_LINE = re.compile(r"^- ")
ID_TOKEN = re.compile(r"(?<![A-Za-z])R-[A-Z]+-[A-Z0-9-]+")  # a whole token: `ADR-...` never yields an id
APPLIED_LINE = re.compile(r"^Rules applied:\s*(?P<ids>.*?)\s*\(block:\s*(?P<n>\d+)\)\s*\.?\s*$")
LINE_PREFIX = re.compile(r"^\s*(?:[-*]\s+)?`?\s*")  # a bullet marker and/or a backtick before the line is tolerated
DONE_DATE = re.compile(r"\*\*Status:\*\*\s*Done\s*\((\d{4}-\d{2}-\d{2})\)|^Status:\s*Done\s*\((\d{4}-\d{2}-\d{2})\)", re.M)


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
    k.add_argument("--task-id"); k.add_argument("--adr-date", required=True); k.set_defaults(fn=cmd_check)
    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
