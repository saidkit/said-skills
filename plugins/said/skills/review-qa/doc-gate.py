#!/usr/bin/env python3
"""doc-gate — the real gate for a `doc` SAID lane.

A doc lane has no compiler. This is the mechanical half of its gate: a
feature-agnostic set of checks that CAN fail, on the defect classes that a code
gate (`make pre-commit`) cannot see and that an editorial read is slow to catch
by hand. The semantic half — two artifacts that now contradict, a figure whose
"current source" is itself stale, invented prose the greps miss — is the
editorial reviewer agent (reviewer != builder): the `doc-editorial` Checker the
lane names in `SAID.reviewers:`, which reads the lane's `docs/qa/feature-qa-checklist.md`
(its editorial context and semantic rows) for the judgment a regex cannot carry.

Rules (each on|soft|off; on FAILs the gate, soft WARNs, off is skipped):
  closure        C1  a `Status: Done` task with any unchecked `- [ ]` acceptance
                     box. (A `[x]`/`[N/A]` box is fine.)
  void-source    C2  a shippable artifact carrying a fabrication / do-not-ship /
                     superseded-source marker (a figure whose source was voided).
  voice-exclaim  C3  an exclamation mark in prose.
  voice-lexicon  C3  a term from the lane's banned lexicon.
  dangling-ref   C4  a local path cited by an artifact that does not exist on disk.

THE EFFECTIVE RULE SET — arguments, never a file. The lane's umbrella line
(`SAID.commands: doc-gate [--soft <rule>] [--off <rule>]`) carries every relaxation;
the skills' resolution chain expands the verb to this script with the lane's paths.
A softened rule prints `[WARN] <rule>` and never fails the run; an off rule prints
nothing. A gate is never neutered silently: the EFFECTIVE RULE SET prints on every
run; every rule off, or an unknown rule name → exit 2. A lane's own checks are rows
in its `docs/qa/feature-qa-checklist.md`, never engine config.

Exit 0 = clean (WARNs allowed). Exit 1 = ≥1 FAIL. Exit 2 = usage/config error.

Feature-agnostic: pass the lane's task logs and shippable-artifact roots; the
gate knows nothing about any one feature. Ships inside the said plugin and is run
natively by the deliver gate (review-qa) for a `surface: doc` lane — resolved
from the skill's own installed dir, never a vendored per-project copy.
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import sys

# --- marker sets -------------------------------------------------------------

# void-source — a shippable artifact should never carry these (the built-in set; a rules's
# `void-markers:` replaces it). A fabricated figure, an unpublishable placeholder, or a
# *voided* source cited as if live.
VOID_MARKERS = re.compile(
    r"\b(do not publish|do not ship|fabricated|invented|superseded draft|"
    r"placeholder\s*[—-]\s*invented|not real(?:\s|,|\.)|no first-party)\b",
    re.IGNORECASE,
)

# voice-exclaim — exclamation in prose. Skips markdown image `![`, `!=`, `[!NOTE]`
# admonitions, and HTML comments `<!--` (a comment/escape is not prose — the
# mention escape below is itself an HTML comment). Anything else `!` is an exclamation.
EXCLAIM = re.compile(r"(?<![\[!=<])(?<!\]\()!(?!=)")

# dangling-ref — a cited local path: backticked `a/b.ext` or a markdown link `](a/b.ext)`.
BACKTICK_PATH = re.compile(r"`([\w./@-]+\.[A-Za-z0-9]{1,5})`")
MDLINK_PATH = re.compile(r"\]\(([^)]+)\)")
LOCAL_PATH = re.compile(r"^(?:\./|\.\./|[\w-]+/)[\w./@-]+$")  # has a slash, not a URL

# task parsing
TASK_HEADING = re.compile(r"^##\s+(\S+):", re.MULTILINE)
STATUS_DONE = re.compile(r"^\*\*Status:\*\*\s*Done\b", re.MULTILINE)
UNCHECKED = re.compile(r"^\s*-\s*\[\s\]", re.MULTILINE)

RULES = ("closure", "void-source", "voice-exclaim", "voice-lexicon", "dangling-ref")
SEVERITIES = ("on", "soft", "off")


class Finding:
    __slots__ = ("sev", "check", "path", "line", "msg")

    def __init__(self, sev, check, path, line, msg):
        self.sev, self.check, self.path, self.line, self.msg = sev, check, path, line, msg

    def __str__(self):
        loc = f"{self.path}:{self.line}" if self.line else self.path
        return f"  [{self.sev}] {self.check}  {loc}\n        {self.msg}"


class RuleSetError(Exception):
    """A config error in the effective rule set — exit 2, never PASS or FAIL."""


class RuleSet:
    """The effective rule set: severities from --soft/--off, the lexicon, the built-in markers."""

    def __init__(self, default_lexicon, soft=(), off=()):
        self.rules = {r: ("on", None) for r in RULES}
        for r in soft:
            self.rules[r] = ("soft", "--soft")
        for r in off:
            self.rules[r] = ("off", "--off")
        n = sum(1 for r in RULES if self.rules[r][0] != "on")
        self.source = "default (every rule on)" if n == 0 else f"arguments ({n} rule(s) relaxed)"
        self.lexicon = default_lexicon
        self.lexicon_src = "--banned" if default_lexicon else "none"
        self.void_re = VOID_MARKERS
        self.markers_src = "built-in"

    def sev(self, rule):
        return self.rules[rule][0]


def _read(path):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def _lineno(text, idx):
    return text.count("\n", 0, idx) + 1


def _iter_files(roots, exts=(".md",)):
    for root in roots:
        if os.path.isfile(root):
            yield root
        elif os.path.isdir(root):
            for dp, _dn, fns in os.walk(root):
                for fn in fns:
                    if fn.endswith(exts):
                        yield os.path.join(dp, fn)
        else:
            for p in glob.glob(root, recursive=True):
                if os.path.isfile(p):
                    yield p


def _resolve(roots, exts=(".md",)):
    """(files, empty_roots). A root that matches zero files is flagged: a gate that scans
    nothing must not report PASS — the exact vacuity a doc lane exists to end (a typo'd glob
    or a wrong cwd, both of which resolve to nothing and silently return green)."""
    files, empty = [], []
    for root in roots:
        got = list(_iter_files([root], exts))
        (files.extend(got) if got else empty.append(root))
    return files, empty


# --- the effective rule set ---------------------------------------------------

def refuse_if_neutered(rules):
    """All rules off is refused — a gate that cannot fail is not a gate (the
    effective set is the --soft/--off arguments; there is no rules file)."""
    if all(rules.sev(r) == "off" for r in RULES):
        raise RuleSetError("all rules off — a gate that cannot fail is not a gate (nominal-gate refusal)")


def _label(sev):
    return "FAIL" if sev == "on" else "WARN"


def check_closure(task_globs, sev):
    """closure (C1) — a Done task with any unchecked acceptance box."""
    out = []
    for path in _iter_files(task_globs):
        text = _read(path)
        heads = list(TASK_HEADING.finditer(text))
        for i, h in enumerate(heads):
            start = h.end()
            end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
            block = text[start:end]
            if not STATUS_DONE.search(block):
                continue
            # scope to the ### Acceptance subsection if present, else whole block
            acc = re.search(r"^###\s+Acceptance\s*$(.*?)(?=^###\s|\Z)",
                            block, re.MULTILINE | re.DOTALL)
            scope = acc.group(1) if acc else block
            for m in UNCHECKED.finditer(scope):
                base = start + (acc.start(1) if acc else 0)
                out.append(Finding(
                    _label(sev), "closure", path,
                    _lineno(text, base + m.start()),
                    f"task `{h.group(1)}` is Status: Done with an unchecked "
                    f"acceptance box — closure ⟺ acceptance broken",
                ))
    return out


def _is_mention(stripped, line):
    """A mention, not a live use — exempt from the prose rules so a doc can document its own
    bans or disclose its own retirements: a blockquote line, or one carrying the escape
    marker `<!-- doc-gate: mention -->`. (Fenced spans are skipped separately.)"""
    return stripped.startswith(">") or "<!-- doc-gate: mention -->" in line


def _prose_lines(path):
    """(line, offset) for every live-prose line of an artifact — fenced, blockquoted and
    mention-escaped spans skipped."""
    text = _read(path)
    in_fence = False
    offset = 0
    for line in text.splitlines(keepends=True):
        stripped = line.lstrip()
        if stripped.startswith("```"):
            in_fence = not in_fence
        elif not (in_fence or _is_mention(stripped, line)):
            yield text, line, offset
        offset += len(line)


def check_void_source(artifact_roots, rules, sev):
    """void-source (C2) — a shippable artifact carrying a fabrication / void-source marker."""
    out = []
    for path in _iter_files(artifact_roots):
        for text, line, offset in _prose_lines(path):
            for m in rules.void_re.finditer(line):
                out.append(Finding(
                    _label(sev), "void-source", path, _lineno(text, offset + m.start()),
                    f"shippable artifact carries a fabrication/do-not-ship/voided-source "
                    f"marker: “{m.group(0)}” — a figure's source may be stale or invented",
                ))
    return out


def check_voice(artifact_roots, rules, sev_exclaim, sev_lexicon):
    """voice-exclaim (C3) — exclamation in prose · voice-lexicon (C3) — the banned lexicon."""
    out = []
    banned = []
    if sev_lexicon != "off" and rules.lexicon:
        for ln in _read(rules.lexicon).splitlines():
            ln = ln.split("#", 1)[0].strip()
            if ln:
                banned.append(re.compile(r"\b" + re.escape(ln) + r"\b", re.IGNORECASE))
    for path in _iter_files(artifact_roots):
        for text, line, offset in _prose_lines(path):
            if sev_exclaim != "off":
                for m in EXCLAIM.finditer(line):
                    out.append(Finding(
                        _label(sev_exclaim), "voice-exclaim", path, _lineno(text, offset + m.start()),
                        "exclamation mark in prose (voice law: no exclamation)",
                    ))
            for rx in banned:
                m = rx.search(line)
                if m:
                    out.append(Finding(
                        _label(sev_lexicon), "voice-lexicon", path, _lineno(text, offset + m.start()),
                        f"banned lexicon: “{m.group(0)}”",
                    ))
    return out


def check_dangling(artifact_roots, repo_root, sev):
    """dangling-ref (C4) — a local path cited by an artifact that does not exist on disk."""
    out = []
    for path in _iter_files(artifact_roots):
        text = _read(path)
        cites = set()
        for rx in (BACKTICK_PATH, MDLINK_PATH):
            for m in rx.finditer(text):
                cites.add((m.group(1), m.start()))
        for ref, idx in cites:
            ref_clean = ref.split("#", 1)[0].strip()
            if ref_clean.startswith(("http://", "https://", "mailto:")):
                continue
            if not LOCAL_PATH.match(ref_clean):
                continue
            # resolve against repo-root and against the citing file's dir
            candidates = [
                os.path.join(repo_root, ref_clean),
                os.path.normpath(os.path.join(os.path.dirname(path), ref_clean)),
            ]
            if any(os.path.exists(c) for c in candidates):
                continue
            out.append(Finding(
                _label(sev), "dangling-ref", path, _lineno(text, idx),
                f"cites `{ref_clean}` — not found under repo root (dangling cross-reference)",
            ))
    return out


# --- output ------------------------------------------------------------------

BANNER = "doc-gate — mechanical rubric for a doc lane\n" + "-" * 44


def print_rules(rules, n_tasks, n_arts):
    """The effective rule set, on EVERY run — a softened gate is visible, never silent."""
    print(f"effective rules: {rules.source}")
    for r in RULES:
        sev, reason = rules.rules[r]
        print(f"  {r}: {sev}" + (f" (reason: {reason})" if reason else ""))
    print(f"  lexicon: {rules.lexicon or 'none'} [{rules.lexicon_src}]")
    print(f"  void-markers: {rules.markers_src}")
    print(f"  scope: {n_tasks} task file(s) + {n_arts} artifact file(s)")
    print("-" * 44)


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="doc-gate", description="mechanical gate for a doc SAID lane")
    ap.add_argument("--repo-root", default=".", help="root for resolving cited paths")
    ap.add_argument("--tasks", nargs="*", default=[],
                    help="task-log files/globs (closure)")
    ap.add_argument("--artifacts", nargs="*", default=[],
                    help="shippable artifact files/dirs (void-source · voice · dangling-ref)")
    ap.add_argument("--banned", default=None, help="default banned-lexicon file (one term/line)")
    ap.add_argument("--soft", action="append", default=[], metavar="RULE",
                    help="relax a rule to WARN (repeatable); one of: " + ", ".join(RULES))
    ap.add_argument("--off", action="append", default=[], metavar="RULE",
                    help="turn a rule off (repeatable); every rule off is refused")
    args = ap.parse_args(argv)

    if not args.tasks and not args.artifacts:
        ap.error("nothing to check: pass --tasks and/or --artifacts")

    default_lexicon = args.banned if (args.banned and os.path.isfile(args.banned)) else None
    unknown = [r for r in args.soft + args.off if r not in RULES]
    if unknown:
        print(BANNER)
        for r in unknown:
            print(f"  [CONFIG] unknown rule: {r} (rules: {', '.join(RULES)})")
        print("-" * 44)
        print("CONFIG-ERROR · an unknown rule was named — nothing was checked.")
        return 2
    rules = RuleSet(default_lexicon, soft=args.soft, off=args.off)
    try:
        refuse_if_neutered(rules)
    except RuleSetError as e:
        print(BANNER)
        print(f"  [CONFIG] {e}")
        print("-" * 44)
        print("CONFIG-ERROR · the effective rule set has every rule off — refused.")
        return 2

    # Non-vacuity: a --tasks/--artifacts root that matches zero files means the gate would check
    # nothing and report PASS — a typo'd glob or a wrong cwd. Refuse with exit 2, and always print
    # the scanned count so non-vacuity is observable from the gate's own output.
    task_files, task_empty = _resolve(args.tasks)
    art_files, art_empty = _resolve(args.artifacts)
    if task_empty or art_empty:
        print(BANNER)
        for r in task_empty + art_empty:
            print(f"  [CONFIG] root matched zero files: {r}")
        print("-" * 44)
        print(f"CONFIG-ERROR · a --tasks/--artifacts root matched zero files "
              f"(scanned {len(task_files)} task + {len(art_files)} artifact files) — a gate that "
              f"scans nothing must not PASS. Fix the path/glob or the cwd.")
        return 2

    findings = []
    if rules.sev("closure") != "off":
        findings += check_closure(args.tasks, rules.sev("closure"))
    if rules.sev("void-source") != "off":
        findings += check_void_source(args.artifacts, rules, rules.sev("void-source"))
    findings += check_voice(args.artifacts, rules, rules.sev("voice-exclaim"), rules.sev("voice-lexicon"))
    if rules.sev("dangling-ref") != "off":
        findings += check_dangling(args.artifacts, args.repo_root, rules.sev("dangling-ref"))

    fails = [f for f in findings if f.sev == "FAIL"]
    warns = [f for f in findings if f.sev == "WARN"]

    print(BANNER)
    print_rules(rules, len(task_files), len(art_files))
    if not findings:
        print("PASS · no findings")
    for f in fails + warns:
        print(f)
    print("-" * 44)
    print(f"scanned {len(task_files)} task file(s) + {len(art_files)} artifact file(s)")
    print(f"{'FAIL' if fails else 'PASS'} · {len(fails)} FAIL · {len(warns)} WARN")
    print("(the editorial reviewer agent — reviewer ≠ builder — covers the "
          "semantic half: contradictions, figure-source currency, invented prose)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
