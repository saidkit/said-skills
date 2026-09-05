#!/usr/bin/env python3
"""doc-gate — the real gate for a `doc` SAID lane.

A doc lane has no compiler. This is the mechanical half of its gate: a
feature-agnostic set of checks that CAN fail, on the defect classes that a code
gate (`make pre-commit`) cannot see and that an editorial read is slow to catch
by hand. The semantic half — two artifacts that now contradict, a figure whose
"current source" is itself stale, invented prose the greps miss — is the
editorial reviewer agent (reviewer != builder): the `doc-editorial` Checker the
lane names in `SAID.reviewers:`, which reads the lane's prose brief
(`<docs-root>/qa/editorial-brief.md`) for the judgment a regex cannot carry.

Rules (each on|soft|off; on FAILs the gate, soft WARNs, off is skipped):
  closure        C1  a `Status: Done` task with any unchecked `- [ ]` acceptance
                     box. (A `[x]`/`[N/A]` box is fine.)
  void-source    C2  a shippable artifact carrying a fabrication / do-not-ship /
                     superseded-source marker (a figure whose source was voided).
  voice-exclaim  C3  an exclamation mark in prose.
  voice-lexicon  C3  a term from the lane's banned lexicon.
  dangling-ref   C4  a local path cited by an artifact that does not exist on disk.
  custom:<id>        a lane's own regex rule, from its bar file.

THE BAR — per-lane data, never code. `--bar <docs-root>/qa/doc-gate.md`: the
engine machine-reads ONLY the first fenced block tagged ```doc-gate (prose outside
it is free — the file documents its own bar). Each line splits on the FIRST ": ":
  rule <id>: on|soft|off [reason: <text>]   (`off` REQUIRES a reason)
  lexicon: <path>                           (relative to the bar file's directory)
  void-markers: a, b, c                     (REPLACES the built-in marker set)
  custom <id>: on|soft <regex>              (severity first; the regex is the rest; max 8)
Absent bar (or a bar with no ```doc-gate block) = the default bar: all rules on,
the built-in markers, the lexicon from `--banned`. A gate is never neutered
silently: the EFFECTIVE BAR prints on every run; all rules off, an unknown key, a
malformed line, `off` without a reason, or more than 8 custom rules → exit 2.

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

# void-source — a shippable artifact should never carry these (the built-in set; a bar's
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
CUSTOM_CAP = 8
FENCE_TAG = "doc-gate"


class Finding:
    __slots__ = ("sev", "check", "path", "line", "msg")

    def __init__(self, sev, check, path, line, msg):
        self.sev, self.check, self.path, self.line, self.msg = sev, check, path, line, msg

    def __str__(self):
        loc = f"{self.path}:{self.line}" if self.line else self.path
        return f"  [{self.sev}] {self.check}  {loc}\n        {self.msg}"


class BarError(Exception):
    """A config error in the bar file — exit 2, never PASS or FAIL."""


class Bar:
    """The effective bar: rule severities (+ off reasons), lexicon, markers, custom rules."""

    def __init__(self, default_lexicon):
        self.source = "default (no bar file)"
        self.rules = {r: ("on", None) for r in RULES}
        self.lexicon = default_lexicon
        self.lexicon_src = "--banned" if default_lexicon else "none"
        self.void_re = VOID_MARKERS
        self.markers_src = "built-in"
        self.custom = []  # (id, sev, compiled regex, pattern text)

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


# --- the bar file ------------------------------------------------------------

def _fenced_block(text):
    """The body of the FIRST ```doc-gate fenced block, or None if the file has none."""
    m = re.search(r"^```" + re.escape(FENCE_TAG) + r"[ \t]*\n(.*?)^```", text, re.MULTILINE | re.DOTALL)
    return m.group(1) if m else None


def parse_bar(path, default_lexicon):
    """Parse the bar file into a Bar. Missing file / no block → the default bar (never an error).
    Unknown key · malformed line · `off` without reason · all rules off · >CUSTOM_CAP custom
    rules → BarError (exit 2): a bar can be tuned, never silently neutered."""
    bar = Bar(default_lexicon)
    if not path or not os.path.isfile(path):
        return bar
    block = _fenced_block(_read(path))
    if block is None:
        bar.source = f"default ({path}: no ```{FENCE_TAG} block)"
        return bar
    bar.source = path
    bar_dir = os.path.dirname(os.path.abspath(path))
    seen_rules = set()
    for n, raw in enumerate(block.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ": " not in line:
            raise BarError(f"malformed line {n} in {path}: {raw!r} (expected `key: value`)")
        key, value = line.split(": ", 1)
        key, value = key.strip(), value.strip()
        parts = key.split(None, 1)
        head = parts[0]
        if head == "rule":
            if len(parts) != 2 or parts[1] not in RULES:
                raise BarError(f"unknown rule {key!r} (line {n}); rules: {', '.join(RULES)}")
            rid = parts[1]
            toks = value.split(None, 1)
            sev = toks[0] if toks else ""
            if sev not in SEVERITIES:
                raise BarError(f"malformed line {n}: rule {rid} needs on|soft|off, got {value!r}")
            reason = None
            rest = toks[1].strip() if len(toks) > 1 else ""
            if rest:
                if not rest.startswith("reason:"):
                    raise BarError(f"malformed line {n}: rule {rid} trailing {rest!r} (expected `reason: <text>`)")
                reason = rest[len("reason:"):].strip() or None
            if sev == "off" and not reason:
                raise BarError(f"rule {rid}: off requires reason: <text> (line {n}) — an off rule must say why")
            if rid in seen_rules:
                raise BarError(f"duplicate rule {rid} (line {n}) — a rule is declared once; the bar must not contradict itself")
            seen_rules.add(rid)
            bar.rules[rid] = (sev, reason)
        elif head == "lexicon" and len(parts) == 1:
            p = value if os.path.isabs(value) else os.path.join(bar_dir, value)
            if not os.path.isfile(p):
                raise BarError(f"lexicon file not found: {value!r} (line {n}; resolved {p}) — the bar names a lexicon that is not there")
            bar.lexicon, bar.lexicon_src = p, f"bar lexicon: {value}"
        elif head == "void-markers" and len(parts) == 1:
            terms = [t.strip() for t in value.split(",") if t.strip()]
            if not terms:
                raise BarError(f"malformed line {n}: void-markers needs at least one term")
            bar.void_re = re.compile(r"\b(" + "|".join(re.escape(t) for t in terms) + r")\b", re.IGNORECASE)
            bar.markers_src = "bar: " + ", ".join(terms)
        elif head == "custom":
            if len(parts) != 2:
                raise BarError(f"malformed line {n}: custom needs an id (`custom <id>: on|soft <regex>`)")
            cid = parts[1]
            if any(c[0] == cid for c in bar.custom):
                raise BarError(f"duplicate custom rule {cid} (line {n})")
            toks = value.split(None, 1)
            if len(toks) != 2 or toks[0] not in ("on", "soft"):
                raise BarError(f"malformed line {n}: custom {cid} needs `on|soft <regex>`, got {value!r}")
            try:
                rx = re.compile(toks[1])
            except re.error as e:
                raise BarError(f"custom {cid}: bad regex {toks[1]!r} ({e})")
            bar.custom.append((cid, toks[0], rx, toks[1]))
        else:
            raise BarError(f"unknown key {key!r} (line {n}); keys: rule <id> · lexicon · void-markers · custom <id>")
    if len(bar.custom) > CUSTOM_CAP:
        raise BarError(f"custom rules exceed the cap: {len(bar.custom)} > {CUSTOM_CAP} — judgment beyond a few regexes belongs in the editorial brief, not the bar")
    return bar


def refuse_if_neutered(bar):
    """All rules off — whether by the bar, by alias flags, or both — is refused. Checked AFTER
    the legacy alias flags are applied, so a four-off bar plus `--allow-exclaim` cannot slip
    through as a nominal green."""
    if all(bar.sev(r) == "off" for r in RULES):
        raise BarError("all rules off — a gate that cannot fail is not a gate (nominal-gate refusal)")


def default_bar_text():
    """The commented default bar `--init` writes: every knob shown, the defaults live."""
    return f"""# doc-gate bar — this lane's mechanical quality bar (data, not code)

The `said` plugin's doc-gate reads ONLY the fenced ```{FENCE_TAG} block below; everything
else in this file is yours to explain the bar to a reader. One `key: value` per line
(split on the first `: `). Rules are `on` (FAIL), `soft` (WARN), or `off` — and `off`
requires a `reason:` so a silenced rule is never silent. Turning every rule off is
refused (exit 2). Run the gate with `--explain` to see, per finding, the exact line
here that would relax it. Judgment a regex cannot carry — tone, whether a claim is
supportable, audience fit — belongs in `editorial-brief.md` beside this file.

```{FENCE_TAG}
rule closure: on
rule void-source: on
rule voice-exclaim: on
rule voice-lexicon: on
rule dangling-ref: on
# A comment is a whole line starting with `#` — never trailing text after a value.
# To use a knob below, remove ONLY its leading `# `.
# The banned lexicon, relative to this file (the default is this sibling, if present):
# lexicon: banned-lexicon.txt
# REPLACES the built-in void-marker set with your own list:
# void-markers: fabricated, do not ship
# Your own rules — up to 8; severity first (on|soft), then the regex, verbatim:
# custom no-first-person: soft \\b(I|we)\\b
```
"""


# --- checks ------------------------------------------------------------------

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


def check_void_source(artifact_roots, bar, sev):
    """void-source (C2) — a shippable artifact carrying a fabrication / void-source marker."""
    out = []
    for path in _iter_files(artifact_roots):
        for text, line, offset in _prose_lines(path):
            for m in bar.void_re.finditer(line):
                out.append(Finding(
                    _label(sev), "void-source", path, _lineno(text, offset + m.start()),
                    f"shippable artifact carries a fabrication/do-not-ship/voided-source "
                    f"marker: “{m.group(0)}” — a figure's source may be stale or invented",
                ))
    return out


def check_voice(artifact_roots, bar, sev_exclaim, sev_lexicon):
    """voice-exclaim (C3) — exclamation in prose · voice-lexicon (C3) — the banned lexicon."""
    out = []
    banned = []
    if sev_lexicon != "off" and bar.lexicon:
        for ln in _read(bar.lexicon).splitlines():
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


def check_custom(artifact_roots, bar):
    """custom:<id> — the lane's own regex rules. A rule that matched nothing across the whole
    scan is reported as a WARN: a rule that cannot fire is suspect (a typo'd regex is nominal)."""
    out = []
    hits = {cid: 0 for cid, _s, _rx, _p in bar.custom}
    if not bar.custom:
        return out
    for path in _iter_files(artifact_roots):
        for text, line, offset in _prose_lines(path):
            for cid, sev, rx, _pat in bar.custom:
                for m in rx.finditer(line):
                    hits[cid] += 1
                    out.append(Finding(
                        _label(sev), f"custom:{cid}", path, _lineno(text, offset + m.start()),
                        f"custom rule `{cid}` matched: “{m.group(0)}”",
                    ))
    for cid, _sev, _rx, pat in bar.custom:
        if hits[cid] == 0:
            out.append(Finding("WARN", f"custom:{cid}", bar.source, None,
                               f"custom rule `{cid}` never fires (regex {pat!r} matched no scanned "
                               f"file) — a rule that cannot fail is suspect; check the regex"))
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


def print_bar(bar, n_tasks, n_arts):
    """The effective bar, on EVERY run — a softened gate is visible, never silent."""
    print(f"effective bar: {bar.source}")
    for r in RULES:
        sev, reason = bar.rules[r]
        print(f"  {r}: {sev}" + (f" (reason: {reason})" if reason else ""))
    print(f"  lexicon: {bar.lexicon or 'none'} [{bar.lexicon_src}]")
    print(f"  void-markers: {bar.markers_src}")
    if bar.custom:
        print("  custom: " + ", ".join(f"{cid} ({sev})" for cid, sev, _rx, _p in bar.custom))
    print(f"  scope: {n_tasks} task file(s) + {n_arts} artifact file(s)")
    print("-" * 44)


def relax_line(check):
    """The exact bar line that would soften this finding one notch."""
    if check.startswith("custom:"):
        return f"custom {check[len('custom:'):]}: soft <regex>"
    return f"rule {check}: soft   (or: rule {check}: off reason: <why>)"


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="doc-gate", description="mechanical gate for a doc SAID lane")
    ap.add_argument("--repo-root", default=".", help="root for resolving cited paths")
    ap.add_argument("--tasks", nargs="*", default=[],
                    help="task-log files/globs (closure)")
    ap.add_argument("--artifacts", nargs="*", default=[],
                    help="shippable artifact files/dirs (void-source · voice · dangling-ref · custom)")
    ap.add_argument("--banned", default=None, help="default banned-lexicon file (one term/line)")
    ap.add_argument("--bar", default=None,
                    help="the lane's bar file (<docs-root>/qa/doc-gate.md); absent = the default bar")
    ap.add_argument("--allow-exclaim", action="store_true",
                    help="alias for `rule voice-exclaim: off` (kept for compatibility)")
    ap.add_argument("--refs-soft", action="store_true",
                    help="alias for `rule dangling-ref: soft` (kept for compatibility)")
    ap.add_argument("--explain", action="store_true",
                    help="per finding: its rule-id, why it fired, the bar line that relaxes it")
    ap.add_argument("--init", action="store_true",
                    help="write the commented default bar to --bar <path> and exit (refuses to overwrite; see --force)")
    ap.add_argument("--force", action="store_true", help="with --init: overwrite an existing bar file")
    args = ap.parse_args(argv)

    if args.init:
        if not args.bar:
            ap.error("--init needs --bar <path> (where to write the bar)")
        if os.path.exists(args.bar) and not args.force:
            print(f"  [CONFIG] {args.bar} already exists — a tuned bar is not overwritten; pass --force to replace it")
            return 2
        os.makedirs(os.path.dirname(os.path.abspath(args.bar)) or ".", exist_ok=True)
        with open(args.bar, "w", encoding="utf-8") as fh:
            fh.write(default_bar_text())
        print(f"wrote the default bar to {args.bar} — edit the ```{FENCE_TAG} block; run with --bar to use it")
        return 0

    if not args.tasks and not args.artifacts:
        ap.error("nothing to check: pass --tasks and/or --artifacts")

    default_lexicon = args.banned if (args.banned and os.path.isfile(args.banned)) else None
    try:
        bar = parse_bar(args.bar, default_lexicon)
    except BarError as e:
        print(BANNER)
        print(f"  [CONFIG] {e}")
        print("-" * 44)
        print("CONFIG-ERROR · the bar file is not a valid bar — fix it; a broken bar never PASSes.")
        return 2
    # legacy flags are severity aliases (reported in the header like any override)
    if args.allow_exclaim:
        bar.rules["voice-exclaim"] = ("off", "--allow-exclaim")
    if args.refs_soft and bar.sev("dangling-ref") == "on":
        bar.rules["dangling-ref"] = ("soft", "--refs-soft")
    try:
        refuse_if_neutered(bar)
    except BarError as e:
        print(BANNER)
        print(f"  [CONFIG] {e}")
        print("-" * 44)
        print("CONFIG-ERROR · the effective bar (bar file + flags) has every rule off — refused.")
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
    if bar.sev("closure") != "off":
        findings += check_closure(args.tasks, bar.sev("closure"))
    if bar.sev("void-source") != "off":
        findings += check_void_source(args.artifacts, bar, bar.sev("void-source"))
    findings += check_voice(args.artifacts, bar, bar.sev("voice-exclaim"), bar.sev("voice-lexicon"))
    findings += check_custom(args.artifacts, bar)
    if bar.sev("dangling-ref") != "off":
        findings += check_dangling(args.artifacts, args.repo_root, bar.sev("dangling-ref"))

    fails = [f for f in findings if f.sev == "FAIL"]
    warns = [f for f in findings if f.sev == "WARN"]

    print(BANNER)
    print_bar(bar, len(task_files), len(art_files))
    if not findings:
        print("PASS · no findings")
    for f in fails + warns:
        print(f)
        if args.explain:
            print(f"        rule-id: {f.check}")
            print(f"        relax: {relax_line(f.check)}")
    print("-" * 44)
    print(f"scanned {len(task_files)} task file(s) + {len(art_files)} artifact file(s)")
    print(f"{'FAIL' if fails else 'PASS'} · {len(fails)} FAIL · {len(warns)} WARN")
    print("(the editorial reviewer agent — reviewer ≠ builder — covers the "
          "semantic half: contradictions, figure-source currency, invented prose)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
