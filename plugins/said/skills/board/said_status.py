#!/usr/bin/env python3
"""said_status.py — deterministic SAID feature-state analyzer.

Read-only. Reconstructs every feature's position in the SAID phase chain
(Scope -> Act -> Inspect -> Debrief -> Closed) by INSPECTING on-disk
artifacts, and emits either JSON (a stable data interface) or a rendered
terminal roster / single-feature deep-dive. Stores nothing.

Backs the said:board skill's --cli and --json surfaces and its web page; see SKILL.md for the
prose contract this implements. Stdlib only, Python 3.8+.

Agnostic by construction: paths, issued id-prefixes, and lanes come from flags
(the skill resolves them declaration-first from CLAUDE.md and passes them);
sensible conventional defaults apply when a flag is omitted. The one thing read
from CLAUDE.md for lanes is the registry line: `--registry` prints its rows in
the form `--lane` takes (see read_lane_registry).
"""

import argparse
import glob
import json
import os
import re
import shlex
import subprocess
import sys
import unicodedata
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import todo_md  # noqa: E402  the format's profile layer: one reader of a `**Priority:**` head

# --- grammar (the SAID task-log shape) --------------------------------------
STATUS_RE = re.compile(r"^\s*(?:[-*+]\s+)?\*\*Status:\*\*\s*(Done|Todo|Canceled|Cancelled|Superseded|Backlog)\b", re.I)
DATE_RE = re.compile(r"\((\d{4}-\d{2}-\d{2})\)")
HEADER_RE = re.compile(r"^##\s+([A-Z]+-?\d+(?:-[A-Za-z0-9]+)+)\s*[:：]?\s*(.*?)\s*$")
FOOTER_RE = re.compile(r"^##\s+Debrief close\b", re.I)
IDDIR_RE = re.compile(r"^([A-Z]+)-(\d+)$")
RUN_RE = re.compile(r"^##\s+Fast-track\s+(F\d{2,})\s*$")  # a fast-track run block; never a task heading
RUN_FIELD_RE = re.compile(r"^\s*(?:[-*+]\s+)?\*\*Fast-track:\*\*\s*(F\d{2,})\b")
RUN_REPORT_RE = re.compile(r"-F\d{2,}\.md$")  # a run's report, never a feature-level gate
TASK_ID_RE = re.compile(r"[A-Z]+-?\d+(?:-[A-Za-z0-9]+)+")  # HEADER_RE's id: a `tasks:` token counts only if it is one

# attention-first ordering; staleness thresholds (days idle) per phase
PHASE_RANK = {"Act": 0, "Inspect": 1, "Debrief": 2, "Scope": 3, "Closed": 4}
# a `**Priority:**` head line: `[#A]`, a bare letter or High/Medium/Low, then an optional minted id token that ends the line
PRIORITY_WORDS = {"high": "A", "medium": "B", "low": "C"}
PRIO_RANK = {"A": 0, "B": 1, "C": 2}
HEAD_LINES = 40  # the lines of a spec the priority reader looks at
STALE_DEFAULT = {"Act": 7, "Inspect": 7, "Debrief": 7, "Scope": 14}
ARCHITECT_STEP = "architect step: "  # the sub-state of Act before tasks exist
STALE_ARCHITECT_STEP = 14

GLYPH = {"done": "█", "empty": "░", "none": ",",
         "ok": "✓", "pending": "○", "warn": "⚠", "block": "⛔"}


def sh(args, timeout=5):
    """Run a command, return stdout stripped, or None on any failure.

    Read-only git calls get `core.optionalLocks=false` so a status read never waits
    on `.git/index.lock` held by concurrent user git ops; a bounded timeout degrades
    to None (task-log dates) rather than stalling a caller.
    """
    if args and args[0] == "git":
        args = ["git", "-c", "core.optionalLocks=false", *args[1:]]
    try:
        out = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return out.stdout.strip() if out.returncode == 0 else None
    except Exception:
        return None


def feature_prefix(fid):
    m = IDDIR_RE.match(fid)
    return m.group(1) if m else fid.split("-")[0]


SPEC_H1_RE = re.compile(r"^#\s+([A-Z]+-?\d+(?:-[A-Za-z0-9]+)*)\s*[:：]\s*(.+?)\s*$")


def feature_name(spec_path):
    """The human name from a feature spec's H1: '# PROJ-01: Foo bar' -> 'Foo bar'.

    Returns None when the spec is unreadable, has no heading, or the first heading is
    not the `# <id>: <name>` form — the display layer falls back accordingly.
    """
    if not spec_path:
        return None
    try:
        with open(spec_path, encoding="utf-8", errors="replace") as fh:
            for ln in fh:
                s = ln.strip()
                if not s:
                    continue
                if s.startswith("#"):
                    m = SPEC_H1_RE.match(s)
                    return m.group(2).strip() if m else None
                return None  # first non-blank line is not a heading
    except OSError:
        return None
    return None


def feature_short_name(spec_path, fid):
    """The slug suffixed after the feature id in the filename.

    'PROJ-02-widgets.md' -> 'widgets'; a bare 'PROJ-01.md' -> None.
    """
    if not spec_path:
        return None
    base = os.path.basename(spec_path)
    if base.endswith(".md"):
        base = base[:-3]
    if base.startswith(fid) and len(base) > len(fid):
        return base[len(fid):].lstrip("-") or None
    return None


def parse_tasks(paths):
    """Parse one feature's task log(s). Returns counts, dates, open items, footer, integrity."""
    counts = {"Done": 0, "Todo": 0, "Canceled": 0, "Backlog": 0}
    dates, todo_items, sections = [], [], 0
    footer = False
    cur_id, cur_title = None, None
    for path in sorted(paths):
        try:
            lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
        except OSError:
            continue
        for ln in lines:
            if FOOTER_RE.match(ln):
                footer = True
                continue
            h = HEADER_RE.match(ln)
            if h:
                footer = False  # a task below the last close footer reopens the feature
                cur_id, cur_title = h.group(1), h.group(2).strip()
                sections += 1
                continue
            s = STATUS_RE.match(ln)
            if s:
                status = s.group(1).capitalize()
                if status in ("Cancelled", "Superseded"):  # obsolete/replaced -> counts as canceled
                    status = "Canceled"
                counts[status] = counts.get(status, 0) + 1
                d = DATE_RE.search(ln)
                if d:
                    dates.append(d.group(1))
                if status == "Todo" and cur_id:
                    todo_items.append({"id": cur_id, "title": cur_title,
                                       "date": d.group(1) if d else None})
    total_status = sum(counts.values())
    integrity = None
    if sections and total_status and sections != total_status:
        integrity = "%d task sections / %d Status lines (mismatch)" % (sections, total_status)
    return {"counts": counts, "dates": sorted(d for d in dates if d),
            "todo_items": todo_items, "footer": footer, "integrity": integrity}


def parse_runs(paths):
    """Fast-track run blocks: [{id, open, tasks}] in log order. The listed set is the block's `tasks:`
    ids plus every task carrying `**Fast-track:** F<NN>`; a run is open while its `closed:` is empty."""
    runs, field_ids = {}, {}
    order = []
    for path in sorted(paths):
        try:
            lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
        except OSError:
            continue
        cur_task, cur_run = None, None
        for ln in lines:
            r = RUN_RE.match(ln)
            if r:
                cur_run, cur_task = r.group(1), None
                if cur_run not in runs:
                    runs[cur_run] = {"id": cur_run, "open": True, "tasks": []}
                    order.append(cur_run)
                continue
            h = HEADER_RE.match(ln)
            if h or (ln.startswith("## ") and not r):
                cur_run, cur_task = None, (h.group(1) if h else None)
                continue
            if cur_run:
                k, _, v = ln.partition(":")
                k, v = k.strip(), v.strip()
                if k == "tasks":
                    runs[cur_run]["tasks"] += [x for x in TASK_ID_RE.findall(v) if x not in runs[cur_run]["tasks"]]
                elif k == "closed":
                    runs[cur_run]["open"] = not v
                continue
            f = RUN_FIELD_RE.match(ln)
            if f and cur_task:
                field_ids.setdefault(f.group(1), []).append(cur_task)
    out = []
    for rid in order:
        run = runs[rid]
        for t in field_ids.get(rid, []):
            if t not in run["tasks"]:
                run["tasks"].append(t)
        out.append(run)
    return out


def run_line(run):
    return "fast-track open: %s, %d tasks" % (run["id"], len(run["tasks"]))


_SECTION_RE = re.compile(r"^###+\s+(.+?)\s*$")


def feature_tasks(paths):
    """All tasks for one feature in file order (on-demand, not part of analyze()).

    Returns a list of {id, title, status, date, priority, sections} where sections maps a
    `### <Name>` heading to its body text. Used by the web board's deep-dive to
    show every task with expand/collapse detail; the CLI does not call this.
    """
    tasks, cur, sec = [], None, None
    for path in paths or []:
        try:
            lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
        except OSError:
            continue
        for ln in lines:
            if FOOTER_RE.match(ln):
                cur, sec = None, None
                continue
            h = HEADER_RE.match(ln)
            if h:
                cur = {"id": h.group(1), "title": h.group(2).strip(), "status": None, "date": None, "priority": "", "sections": {}}
                tasks.append(cur)
                sec = None
                continue
            if cur is None:
                continue
            s = STATUS_RE.match(ln)
            if s:
                cur["status"] = "Canceled" if s.group(1).capitalize() == "Cancelled" else s.group(1).capitalize()
                d = DATE_RE.search(ln)
                cur["date"] = d.group(1) if d else None
                continue
            if sec is None and not cur["priority"]:
                pm = todo_md.priority_head_parts(ln.strip())
                if pm:
                    cur["priority"] = norm_priority(pm[0])
                    continue
            m = _SECTION_RE.match(ln)
            if m:
                sec = m.group(1).strip()
                cur["sections"].setdefault(sec, [])
                continue
            if sec is not None:
                cur["sections"][sec].append(ln)
    for t in tasks:
        clean = {}
        for k, v in t["sections"].items():
            txt = "\n".join(v).strip()
            if txt and not (txt.startswith("<!--") and txt.endswith("-->")):
                clean[k] = txt
        t["sections"] = clean
    return tasks


def lane_reviewers(root):
    """The lane's declared Checkers, read WHOLE from the `SAID.reviewers:` key of the `## Lane` block of
    <root>/CLAUDE.md (never from prose or a fence elsewhere in the file): `[a, b]`, a bare `a`, quoted ids
    and a trailing ` # comment` -> ["a", "b"]; no file, no block, no key, or `[]` -> []."""
    try:
        with open(os.path.join(root, "CLAUDE.md"), encoding="utf-8") as fh:
            block = lane_block_lines(fh.read())
    except (OSError, UnicodeDecodeError):
        return []
    for line in block or []:
        m = re.match(r"^\s*[-*]?\s*SAID\.reviewers:\s*(.*?)\s*$", line)
        if m:
            v = re.sub(r"\s+#.*$", "", m.group(1)).strip()
            if v.startswith("[") and v.endswith("]"):
                v = v[1:-1]
            return [x.strip().strip("\"'") for x in v.split(",") if x.strip().strip("\"'")]
    return []


def gate_ticks(workdir, reviewers=(), fid=None):
    """Presence of the working-dir gate artifacts. The review gate ticks from a `review-ux*` report or
    when EVERY Checker the lane declares in `SAID.reviewers:` has a verdict file
    `review-<checker-id>-<feature-id>*.md` (the feature id after the Checker id, so `cli` never ticks
    from a `cli-gate` file); one declared Checker's file alone does not tick."""
    def has(pat):  # a run's `-F<NN>` report never ticks a feature-level gate
        return any(not RUN_REPORT_RE.search(p) for p in glob.glob(os.path.join(workdir, pat)))
    ux = has("review-ux*.md") or bool(fid) and bool(reviewers) and all(
        has("review-%s-%s*.md" % (glob.escape(cid), glob.escape(fid))) for cid in reviewers)
    return {"qa": has("review-qa*.md"), "ux": ux,
            "accept": has("accept*.md"), "debrief_started": os.path.isfile(os.path.join(workdir, "debrief.md"))}


def classify(has_spec, has_tasks, todo, footer, has_scope, dir_has_content, debrief_started=False):
    """Ordered phase probe — first match wins. Never keys on todo==0 alone."""
    if footer:
        return "Closed", None
    if has_tasks and todo == 0:
        return ("Debrief" if debrief_started else "Inspect"), None
    if has_tasks and todo > 0:
        return "Act", None
    if has_scope or has_spec:
        return "Act", ARCHITECT_STEP + ("spec, no tasks" if has_spec else "scope.md, no spec")
    if dir_has_content:
        return "Scope", "scope pending"
    return "Scope", "not started"


def relpath(p, root):
    """Display form: relative to the lane root, so a `Next` command pastes straight
    into a shell run from the project root. Absolute paths stay in `paths` for I/O."""
    if not p:
        return p
    try:
        r = os.path.relpath(os.path.abspath(p), os.path.abspath(root))
    except ValueError:  # different drive (win) — nothing sensible to relativize to
        return os.path.normpath(p)
    return os.path.normpath(p) if r.startswith(os.pardir) else r


def feature_review_failed(root, workdir, fid):
    """True when the feature's gate record, current at the lane's store, holds a feature-review verdict FAIL
    (derived from the record on every read, never stored)."""
    try:
        import gate_record
        path = os.path.join(workdir, "gate-%s.md" % fid)
        rec = gate_record.load(path)
        if rec is None or rec[0] is None or rec[0] != gate_record.identity(root, path):
            return False
        if not gate_record.sources_current(root, path):  # a moved source owes the read, not the FAIL's tasks
            return False
        return any(ln.startswith("feature-review: verdict | FAIL |") for ln in rec[1]) \
            and not gate_record.fr_record_only(rec[1])  # a record-class FAIL opens no task
    except Exception:  # an unreadable record or an identity error is not a FAIL; the gates report it
        return False


def feature_review_owed(root, workdir, fid):
    """True when the gate record does not hold the feature-reviewer's PASS rows at the lane's store: the read comes
    before review-qa. An unreadable record or an identity error is not owed here; the gates report it."""
    try:
        import gate_record
        code, line = gate_record.check(root, os.path.join(workdir, "gate-%s.md" % fid), ["feature-review"])
        return line != "current"
    except Exception:
        return False


def feature_review_state(root, workdir, fid):
    """The gates field of the feature-reviewer's read: `pass` or `fail` from the record's rows at the lane's store,
    `owed` when the read on record is not current there (rows at another store, unsound rows, or a filed verdict whose
    rows a later write dropped), `-` when no read was ever filed."""
    filed = any(os.path.isfile(os.path.join(workdir, n % fid)) for n in ("review-feature-%s.md", "review-doc-editorial-%s.md"))
    try:
        import gate_record
        path = os.path.join(workdir, "gate-%s.md" % fid)
        rec = gate_record.load(path)
        if rec is None or not any(ln.startswith("feature-review: ") for ln in rec[1]):
            return "owed" if filed else "-"
        code, line = gate_record.check(root, path, ["feature-review"])
    except Exception:  # an unreadable record holds no read the board can show; the gates report the error
        return "owed" if os.path.isfile(os.path.join(workdir, "gate-%s.md" % fid)) else "-"
    if code == 0:
        return "pass"
    return "fail" if line == "Inspect owed: feature-review FAIL" else "owed"


FR_GLYPH = {"pass": GLYPH["ok"], "-": GLYPH["pending"], "fail": "FAIL", "owed": "owed"}


def _fr_doc_lane(root):
    import gate_record
    return gate_record.fr_doc_lane(root)


def next_action(fid, phase, workdir, gates, sub, doc=False, fr_owed=False):
    workdir = os.path.normpath(workdir)
    if sub == "feature review FAIL":  # doc: the lane kind, so the action names the verdict that lane writes
        return "/said:add-task %s (one task per FAIL row of %s-%s.md without `record:` in the gate record)" % (fid, "review-doc-editorial" if doc else "review-feature", fid)
    if phase == "Scope":
        return "/said:scope-refine %s" % workdir if sub == "scope pending" else "/said:scope-grill %s" % fid
    if phase == "Act":
        if (sub or "").startswith(ARCHITECT_STEP):
            return "/said:architect %s" % os.path.join(workdir, "scope.md")
        return "/said:impl %s" % fid
    if phase in ("Inspect", "Debrief"):  # a gate still unrecorded comes before the debrief
        if fr_owed and not gates.get("qa"):  # the read's place in a round: before review-qa
            return "/said:review-feature %s --base <rev> --capture-ref <file|none>" % fid
        if not gates["qa"]:
            return "/said:review-qa %s" % fid
        if not gates["accept"]:
            return "/said:accept %s" % fid
        return "/said:debrief %s" % fid
    return None


def artifact_files(specs, tasks, workdir):
    """Every file that counts as this feature's on-disk footprint."""
    files = list(specs) + list(tasks)
    if os.path.isdir(workdir):
        for dirpath, _dirs, names in os.walk(workdir):
            files.extend(os.path.join(dirpath, n) for n in names)
    return files


def worktree_date(root, files, git_available):
    """Date of the newest *uncommitted* edit among a feature's artifacts, or None.

    `git log` only sees commits, so work sitting in the working tree — the normal
    state while a feature is being implemented — otherwise reads as no activity at
    all: PROJ-01 showed "10d idle" while its task log was being edited that hour.

    Gated on the tree actually being dirty, because a fresh clone stamps every file
    with checkout time and would make every feature look worked-on. With no git at
    all, mtime is the only signal there is, so use it directly.
    """
    if not files:
        return None
    # Pathspecs must be absolute: with a relative --root, `git -C <root> ... -- <root>/x`
    # resolves inside the repo again, matches nothing, and would read as a clean tree.
    if git_available and not sh(["git", "-C", root, "status", "--porcelain", "--"]
                                + [os.path.abspath(p) for p in files]):
        return None  # clean tree — the commit history already tells the story
    # Porcelain output is used as a dirty/clean signal only; parsing paths out of it is
    # fragile (sh() strips, so the first line loses its leading status space). Any dirty
    # artifact means this feature is being worked on, so date it by its newest artifact.
    newest = None
    for p in files:
        try:
            ts = os.path.getmtime(p)
        except OSError:
            continue
        if newest is None or ts > newest:
            newest = ts
    return date.fromtimestamp(newest).isoformat() if newest is not None else None


def idle_phrase(days):
    """Display form of the idle counter. Zero days means it was touched today —
    'active' says that; 'idle 0d' reads like neglect and is the opposite of true."""
    if days is None:
        return None
    return "active" if days == 0 else "idle %dd" % days


def days_between(a, b):
    try:
        ya, ma, da = map(int, a.split("-"))
        yb, mb, db = map(int, b.split("-"))
        return (date(yb, mb, db) - date(ya, ma, da)).days
    except Exception:
        return None


def norm_priority(raw):
    """A, B or C for the letters and for High, Medium, Low; anything else is none ('')."""
    v = (raw or "").strip()
    return v.upper() if v.upper() in PRIO_RANK else PRIORITY_WORDS.get(v.lower(), "")


def head_priority(lines):
    """(the letter, the index of the `**Priority:**` line) in the first lines of a spec, ('', None) when it has none."""
    for j, ln in enumerate(lines[:HEAD_LINES]):
        parts = todo_md.priority_head_parts(ln.strip())
        if parts:
            return norm_priority(parts[0]), j
    return "", None


def spec_priority(path):
    if not path:
        return ""
    try:
        with open(path, encoding="utf-8-sig", errors="replace") as fh:
            return head_priority(fh.read().split("\n"))[0]
    except OSError:
        return ""


def _sortkey(f):
    rank = PHASE_RANK.get(f["phase"], 9)
    if f["phase"] == "Closed":  # most-recently-closed first
        d = f["last_activity"] or "0000-00-00"
        return (rank, tuple(-int(x) for x in d.split("-")), f.get("lane", ""), f["id"])
    return (rank, PRIO_RANK.get(f.get("priority"), 3), (-(f["idle_days"] or 0),), f.get("lane", ""), f["id"])  # priority, then most-stale first


def waiting_reason(workdir):
    """Derive 'waiting on an operator question' from durable SAID artifacts ONLY
    (derive, never store): the recorded Inspect-gate verdicts under the feature's working
    dir. A run-engine hold recorded outside the lane's working dir is out of scope
    -- operator-visible, not analyzer-visible. Returns a short reason or None."""
    try:
        accepts = sorted((p for p in glob.glob(os.path.join(workdir, "accept-*.md")) if not RUN_REPORT_RE.search(p)),
                         key=os.path.getmtime)
    except OSError:
        return None
    if not accepts:
        return None
    try:
        txt = open(accepts[-1], encoding="utf-8", errors="replace").read()
    except OSError:
        return None
    # Only the accept VERDICT is a structured, unambiguous signal. A could-not-run reviewer-gate
    # also holds the close, but telling it apart from a ran-and-FAILed reviewer (both fail the
    # gate) requires a structured could-not-run field the gate does not yet emit; the free-form
    # per-reviewer probe prose is unsound to parse (mixed reviewers / multi-line recording drop a
    # real hold). Roster-surfacing it is deferred to that structured field; the close still holds
    # it via debrief's Inspect gate check. So the axis surfaces the one signal it can trust.
    # anchored to the report's own verdict bullet: a recorded probe line (which can carry builder-authored
    # recompute rows) never reads as the verdict
    # the file is append-only: a re-run appends a new verdict, so only its LAST verdict line is current
    # a Verdict line inside a code fence is an example of the form, never a verdict
    unfenced, fence = [], None
    for ln in txt.splitlines():
        marker, fence = fence_step(fence, ln)   # the lane block's own fence rule
        if not (marker or fence):
            unfenced.append(ln)
    verdicts = re.findall(r"^\s*[-*]?\s*Verdict:\s*(\S.*?)\s*$", "\n".join(unfenced), re.M)
    if verdicts and verdicts[-1] == "MANUAL-PENDING":   # a held operator question
        return "accept MANUAL-PENDING"
    return None


def completeness_note(workdir):
    """The completeness recompute's advisory report (the under-spec WARN + per-unit last-revised
    provenance), derived read-only from the recorded review-completeness-*.md note artifact for the
    board + deep-dive display. Non-gating: display text, never a verdict. Derive-never-store: reads only."""
    try:
        hits = sorted(glob.glob(os.path.join(workdir, "review-completeness-*.md")), key=os.path.getmtime)
    except OSError:
        return None
    if not hits:
        return None
    try:
        txt = open(hits[-1], encoding="utf-8", errors="replace").read()
    except OSError:
        return None
    return _completeness_report(txt) or None


# The hold marker + its append-only lift records are read with the hold gate's own line parser
# (`../review-qa/hold-gate.py`, same plugin), so status never reads the grammar more laxly than the gate.
_GATE = []


def _hold_gate():
    """The bundled hold gate, loaded once from the sibling review-qa skill; None when it cannot load."""
    if not _GATE:
        mod = None
        try:
            import importlib.util
            path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "review-qa", "hold-gate.py")
            spec = importlib.util.spec_from_file_location("said_hold_gate", path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
        except Exception:  # a missing or broken gate must not take the board down
            mod = None
        _GATE.append(mod)
    return _GATE[0]


def _shown_id(text):
    """A marker's id as displayed: printable ASCII only, capped (builder-authored text)."""
    return "".join(c if 0x20 <= ord(c) < 0x7f else "?" for c in text).strip()[:40] or "(empty)"


def waiting_on_question(tasks_paths, rulings_path=None, root=None):
    """Derive 'waiting on question <id>' from durable STRUCTURED state (derive, never store). Every
    `**Blocked-on question:** <id>` marker is judged by the hold gate's own `judge_marker` against the
    work's rulings list, so status and the gate share one rule: a marker the gate would HOLD waits
    (a Done task too: closed without a lift), and so does a malformed or old-spelled marker. With no
    rulings list a lift cannot be checked, so it shows as unverified. Returns a short reason or None."""
    gate = _hold_gate()
    rulings, list_err = None, None
    if gate is not None and rulings_path and os.path.isfile(rulings_path):
        try:
            rulings = gate.load_rulings([rulings_path])
        except gate.ConfigError as err:
            list_err = str(err)
    for path in sorted(tasks_paths or []):
        try:
            txt = open(path, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        if gate is None:  # cannot parse without the gate: any marker-looking text waits
            if "Blocked-on" in txt:
                return "question ? (hold gate unavailable)"
            continue
        olds = gate.old_spellings(txt)  # a retired spelling waits on any task, Done or not (as the gate)
        if olds:
            _n, kind, detail = olds[0]
            return "question %s (old spelling: rename the %s)" % (_shown_id(detail), kind)
        stray = gate.stray_markers(txt)  # a marker the gate half-recognises waits too (it HOLDs there)
        if stray:
            return "question ? (malformed marker: %s)" % _shown_id(stray[0][2].strip())
        tasks, records = gate.parse_log(txt)
        for name, lines in tasks:
            found, _date = gate.markers_of(lines)
            status = gate.task_status_of(lines)
            for rest in found:
                qid = _shown_id(rest)
                if not gate.is_id(rest):  # malformed waits on any task, Done or not (as the gate)
                    return "question %s (malformed marker)" % qid
                if not any(r["id"] == rest for r in records):
                    done = (status[0] or "").casefold() == "done"
                    return "question " + qid + (" (closed without a lift)" if done else "")
                if rulings is None:
                    why = _shown_id(list_err) if list_err else "no rulings list"
                    return "question %s (lift unverified: %s)" % (qid, why)
                try:  # one bad document shows that lift unverified; it never takes the board down
                    verdict = gate.judge_marker(name, status, rest, records, rulings, root or os.getcwd())
                except Exception as err:
                    return "question %s (lift unverified: %s)" % (qid, type(err).__name__)
                if verdict.state != "PASS":
                    return "question %s (%s)" % (qid, gate.shown(verdict.reason, 60))
    return None


def lane_registry(root, docs_dir, work_dir, prefixes, legacy_prefixes):
    """The lane's feature ids, split into the ones it shows (active) and the collapsed ones.
    File reads only (no git), so a page can ask it cheaply."""
    feats_dir = os.path.join(root, docs_dir)
    work_root = os.path.join(root, work_dir)

    # --- registry: specs UNION working dirs -------------------------------
    ids = {}
    for p in glob.glob(os.path.join(feats_dir, "*.md")):
        base = os.path.basename(p)
        if base.endswith(".tasks.md") or base.startswith("template") or base.startswith("README"):
            continue
        m = re.match(r"([A-Z]+-\d+)", base)
        if m:
            ids.setdefault(m.group(1), True)
    if os.path.isdir(work_root):
        for entry in os.listdir(work_root):  # not `name` — that is the lane parameter
            if IDDIR_RE.match(entry) and os.path.isdir(os.path.join(work_root, entry)):
                ids.setdefault(entry, True)

    # --- issued vs legacy -------------------------------------------------
    def has_scope(fid):
        return os.path.isfile(os.path.join(work_root, fid, "scope.md"))

    def has_spec(fid):
        return bool([q for q in glob.glob(os.path.join(feats_dir, fid + "*.md")) if not q.endswith(".tasks.md")])

    if prefixes:
        issued = set(prefixes)
    else:  # infer: a prefix is active if any of its ids has a spec or a scope.md
        issued = set(feature_prefix(f) for f in ids if has_spec(f) or has_scope(f))
    legacy = set(legacy_prefixes or [])

    active, legacy_seen = [], set()
    for fid in ids:
        pfx = feature_prefix(fid)
        if pfx in legacy or (issued and pfx not in issued):
            legacy_seen.add(pfx)
            continue
        active.append(fid)
    return {"active": active, "legacy_seen": legacy_seen}


def lane_ids(lane):
    """The feature ids a lane's page shows, the ones analyze_lane lists (collapsed ids are in no lane)."""
    reg = lane_registry(lane["root"], lane["docs_dir"], lane["work_dir"], lane.get("prefixes"), lane.get("legacy_prefixes"))
    return sorted(reg["active"])


def analyze_lane(name, root, docs_dir, work_dir, prefixes, legacy_prefixes, today, stale_days):
    feats_dir = os.path.join(root, docs_dir)
    work_root = os.path.join(root, work_dir)
    git_available = sh(["git", "-C", root, "rev-parse", "--is-inside-work-tree"]) == "true"
    reg = lane_registry(root, docs_dir, work_dir, prefixes, legacy_prefixes)
    active, legacy_seen = reg["active"], reg["legacy_seen"]

    def has_scope(fid):
        return os.path.isfile(os.path.join(work_root, fid, "scope.md"))

    # --- per-feature reconstruction ---------------------------------------
    out = []
    reviewers = lane_reviewers(root)
    for fid in active:
        workdir = os.path.join(work_root, fid)
        specs = [q for q in glob.glob(os.path.join(feats_dir, fid + "*.md")) if not q.endswith(".tasks.md")]
        tasks = glob.glob(os.path.join(feats_dir, fid + "*.tasks.md"))
        scope = has_scope(fid)
        # dotfiles (.gitkeep, .DS_Store) are not SAID artifacts — a dir holding only them is "empty"
        dir_content = os.path.isdir(workdir) and any(not e.startswith(".") for e in os.listdir(workdir))
        t = parse_tasks(tasks) if tasks else {"counts": {"Done": 0, "Todo": 0, "Canceled": 0, "Backlog": 0},
                                              "dates": [], "todo_items": [], "footer": False, "integrity": None}
        c = t["counts"]
        phase, sub = classify(bool(specs), bool(tasks), c["Todo"], t["footer"], scope, dir_content,
                              os.path.isfile(os.path.join(workdir, "debrief.md")))
        if phase in ("Inspect", "Debrief") and dir_content and feature_review_failed(root, workdir, fid):
            phase, sub = "Act", "feature review FAIL"  # a failed feature review: Inspect does not start
        gates = gate_ticks(workdir, reviewers, fid) if os.path.isdir(workdir) else {"qa": False, "ux": False, "accept": False, "debrief_started": False}
        gates["feature_review"] = feature_review_state(root, workdir, fid) if os.path.isdir(workdir) else "-"

        started = t["dates"][0] if t["dates"] else None
        last_task = t["dates"][-1] if t["dates"] else None
        git_last = None
        if git_available:
            git_last = sh(["git", "-C", root, "log", "-1", "--format=%cd", "--date=short", "--"]
                          + specs + tasks + ([workdir] if os.path.isdir(workdir) else []))
            git_last = git_last or None
        wt_last = worktree_date(root, artifact_files(specs, tasks, workdir), git_available)
        last_activity = max([d for d in (last_task, git_last, wt_last) if d], default=None)
        idle = days_between(last_activity, today) if last_activity else None
        age = days_between(started, today) if started else None
        threshold = stale_days if stale_days is not None else (
            STALE_ARCHITECT_STEP if (sub or "").startswith(ARCHITECT_STEP) else STALE_DEFAULT.get(phase))
        stale = bool(phase != "Closed" and idle is not None and threshold is not None and idle > threshold)

        fname = feature_name(specs[0] if specs else None)
        fshort = feature_short_name(specs[0] if specs else None, fid)
        out.append({
            "lane": name, "id": fid, "phase": phase, "sub": sub,
            # the feature's human name (spec H1) and the filename slug, if any;
            # display_name prefers the short slug, else the full name, else None.
            "name": fname, "short_name": fshort, "display_name": fshort or fname,
            "priority": spec_priority(specs[0] if specs else None),
            "counts": c, "done": c["Done"], "todo": c["Todo"],
            "denominator": c["Done"] + c["Todo"],
            "todo_items": t["todo_items"],
            "gates": gates, "debrief_closed": t["footer"],
            "started": started, "last_activity": last_activity,
            "age_days": age, "idle_days": idle, "stale": stale, "threshold": threshold,
            "next": next_action(fid, phase, relpath(workdir, root), gates, sub,
                                doc=sub == "feature review FAIL" and _fr_doc_lane(root),
                                fr_owed=phase in ("Inspect", "Debrief") and not gates["qa"]
                                and feature_review_owed(root, workdir, fid)),
            "integrity": t["integrity"],
            "fast_track_open": [r for r in parse_runs(tasks) if r["open"]],
            "waiting": (waiting_reason(workdir) if os.path.isdir(workdir) else None) or waiting_on_question(tasks, os.path.join(workdir, "rulings.md"), root),
            "completeness_note": (completeness_note(workdir) if os.path.isdir(workdir) else None),
            # `paths` stay absolute — they are read from. `paths_rel` is the display form.
            "paths": {"spec": os.path.normpath(specs[0]) if specs else None,
                      "tasks": os.path.normpath(tasks[0]) if tasks else None,
                      "scope": os.path.normpath(os.path.join(work_root, fid, "scope.md")) if scope else None},
            "paths_rel": {"spec": relpath(specs[0], root) if specs else None,
                          "tasks": relpath(tasks[0], root) if tasks else None,
                          "scope": relpath(os.path.join(work_root, fid, "scope.md"), root) if scope else None},
        })
        record = os.path.join(workdir, "gate-%s.md" % fid)
        if os.path.isfile(record):  # the record the deep-dive reports from; the report is derived at render time
            out[-1].update(inspect_record=os.path.normpath(record), lane_root=os.path.normpath(root))

    out.sort(key=_sortkey)
    return {
        "name": name, "root": os.path.normpath(root),
        "docs_dir": docs_dir, "working_dir": work_dir,
        "git_available": git_available, "legacy_prefixes": sorted(legacy_seen),
        "features": out,
    }


def parse_lane_arg(arg, defaults):
    """'NAME' or 'NAME:key=val;key=val' - keys: root, docs, working, prefixes, legacy.
    A relative root is taken from the --root directory (defaults["root"]), so a row the
    registry reader printed for that root resolves from any working directory."""
    name, _, rest = arg.partition(":")
    spec = dict(defaults)
    spec["prefixes"] = None  # a lane infers its prefixes unless it declares them; a top-level --prefixes is not inherited
    spec["name"] = name.strip() or defaults.get("name")
    for pair in rest.split(";"):
        if "=" not in pair:
            continue
        k, _, v = pair.partition("=")
        k, v = k.strip(), v.strip()
        if k == "root":
            base = defaults.get("root") or ""
            spec["root"] = v if (not v or os.path.isabs(v) or base in ("", ".")) else os.path.join(base, v)
        elif k == "docs":
            spec["docs_dir"] = v
        elif k == "working":
            spec["work_dir"] = v
        elif k == "prefixes":
            spec["prefixes"] = [x.strip() for x in v.split(",") if x.strip()]
        elif k == "legacy":
            spec["legacy_prefixes"] = [x.strip() for x in v.split(",") if x.strip()]
    return spec


STAMP_CAP = 64


def lane_stamps(root):
    """The lane's SAID.version and SAID.starter as written on its own `## Lane` block key list,
    `-` when absent or empty. A plain read for display: control and format characters are
    dropped and a value over STAMP_CAP is cut, so a stamp cannot rewrite the terminal."""
    try:
        with open(os.path.join(root, "CLAUDE.md"), encoding="utf-8-sig", errors="replace") as fh:
            block = lane_block_lines(fh.read())
    except (OSError, ValueError):
        block = None
    out = {}
    for key in ("version", "starter"):
        v = _block_key(block, key) if block is not None else None
        v = "".join(ch for ch in (v or "") if unicodedata.category(ch) not in ("Cc", "Cf"))
        out[key] = (v[:STAMP_CAP - 3] + "...") if len(v) > STAMP_CAP else (v or "-")
    return out


def analyze(lanes, today, stale_days, project, stamps=False):
    results = [analyze_lane(L["name"], L["root"], L["docs_dir"], L["work_dir"],
                            L.get("prefixes"), L.get("legacy_prefixes"), today, stale_days)
               for L in lanes]
    if stamps:  # the --lane board only; the single-lane board stays as it was
        for r, L in zip(results, lanes):
            r.update(lane_stamps(L["root"]))
    flat = [f for r in results for f in r["features"]]
    flat.sort(key=_sortkey)
    return {
        "project": project, "today": today, "lane_count": len(results),
        "git_available": all(r["git_available"] for r in results),
        "lanes": results, "features": flat,
    }


# --- rendering ---------------------------------------------------------------
def bar(done, denom):
    if denom <= 0:
        return GLYPH["none"] * 9
    fill = max(0, min(9, round(9 * done / denom)))
    return GLYPH["done"] * fill + GLYPH["empty"] * (9 - fill)


def gate_str(f):
    parts = []
    if f["gates"].get("feature_review") == "pass":
        parts.append("feature-review" + GLYPH["ok"])
    if f["gates"]["qa"]:
        parts.append("qa" + GLYPH["ok"])
    if f["gates"]["ux"]:
        parts.append("ux" + GLYPH["ok"])
    if f["gates"]["accept"]:
        parts.append("accept" + GLYPH["ok"])
    if f["debrief_closed"]:
        parts.append("debrief" + GLYPH["ok"])
    return " ".join(parts)


def flags(f):
    if f["phase"] == "Closed":
        extra = gate_str(f)
        if f["counts"]["Canceled"]:
            extra += " , %d canceled" % f["counts"]["Canceled"]
        return extra
    bits = []
    if f["sub"]:
        label = f["sub"]
        if not f["stale"] and f["idle_days"] is not None:
            label += ", %s" % ("active" if f["idle_days"] == 0 else "%dd" % f["idle_days"])
        bits.append(label)
    if f["stale"]:
        bits.append("%s %dd idle" % (GLYPH["warn"], f["idle_days"]))
    if f.get("integrity"):
        bits.append("! " + f["integrity"])
    if f.get("waiting"):
        bits.append("%s waiting: %s" % (GLYPH["warn"], f["waiting"]))
    return "  ".join(bits)


def _row(f, idw, phw):
    denom = f["denominator"]
    prog = "%d/%d" % (f["done"], denom) if denom else "—"
    todo = "%d Todo" % f["todo"] if f["todo"] else "—"
    return ("%-*s  %-*s  %s  %6s  %-7s  %s" % (
        idw, f["id"], phw, f["phase"], bar(f["done"], denom), prog, todo, flags(f))).rstrip()


def _lane_tail(next_from, legacy_prefixes, prefix, max_next):
    tail = []
    nexts = [f["next"] for f in next_from if f["next"]][:max_next]
    if nexts:
        tail.append(prefix + "Next: " + ", ".join(nexts))
    if legacy_prefixes:
        tail.append(prefix + "legacy: %s — not issued here (docs/working history)" % ", ".join(legacy_prefixes))
    return tail


def run_lines(lr, prefix):
    """One line per open fast-track run in the lane, stale or not: an open run is always an attention item."""
    return ["%s%s %s" % (prefix, f["id"], run_line(r)) for f in lr["features"] for r in f.get("fast_track_open") or []]


def _stamp_str(lr):
    return "  version: %s  starter: %s" % (lr["version"], lr["starter"])


def render_roster(data, stale_only=False):
    def shown(lr):
        return [f for f in lr["features"] if (not stale_only or f["stale"])]

    def tail_for(lr, rows, prefix, max_next):  # --stale: Next from stale rows only, no legacy noise
        return _lane_tail(rows if stale_only else lr["features"],
                          [] if stale_only else lr["legacy_prefixes"], prefix, max_next)

    allf = [f for f in data["features"] if (not stale_only or f["stale"])]
    idw = max([len(f["id"]) for f in allf] + [4])
    phw = max([len(f["phase"]) for f in allf] + [5])
    n = data["lane_count"]
    lines = ["SAID status, %s, %d lane%s, %s" % (
        data["project"], n, "" if n == 1 else "s", data["today"]), ""]
    if n == 1:
        lr = data["lanes"][0]
        if "version" in lr:
            lines[-1:-1] = [_stamp_str(lr).lstrip()]
        rows = shown(lr)
        for f in rows:
            lines.append(_row(f, idw, phw))
        runs = run_lines(lr, "")
        if stale_only and not rows and not runs:
            lines.append("(nothing stale)")
        lines += runs
        tail = tail_for(lr, rows, "", 3)
        if tail:
            lines.append("")
            lines += tail
        if not lr["git_available"]:
            lines.append("(no git: dates from task logs only)")
    else:
        any_shown = False
        for lr in data["lanes"]:
            rows = shown(lr)
            runs = run_lines(lr, "  ")
            if stale_only and not rows and not runs:  # a clean lane is not an attention item
                continue
            any_shown = True
            hint = lr["root"] if lr["root"] not in (".", "") else lr["docs_dir"]
            lines.append("lane: %s  (%s)%s" % (lr["name"], hint, _stamp_str(lr) if "version" in lr else ""))
            for f in rows:
                lines.append("  " + _row(f, idw, phw))
            lines += runs
            lines += tail_for(lr, rows, "  ", 2)
            lines.append("")
        while lines and lines[-1] == "":
            lines.pop()
        if stale_only and not any_shown:
            lines.append("(nothing stale)")
        if not data["git_available"]:
            lines.append("(some lanes have no git — dates from task logs only)")
    return "\n".join(lines)


def _feature_block(f, lane_label=None):
    seq = ["Scope", "Act", "Inspect", "Debrief", "Closed"]
    cur = f["phase"]
    ci = seq.index(cur) if cur in seq else -1
    pipe = []
    for i, p in enumerate(seq):
        pipe.append("%s %s" % (p, GLYPH["ok"] if i < ci else ("●" if i == ci else GLYPH["pending"])))
    out = (["lane: %s" % lane_label] if lane_label else []) + ["%s — %s" % (f["id"], cur), "", "  " + " -> ".join(pipe)]
    g = f["gates"]
    gline = ", ".join([
        "review-feature " + FR_GLYPH.get(g.get("feature_review", "-"), GLYPH["pending"]),
        "review-qa " + (GLYPH["ok"] if g["qa"] else GLYPH["pending"]),
        "review-ux " + (GLYPH["ok"] if g["ux"] else GLYPH["pending"]),
        "accept " + (GLYPH["ok"] if g["accept"] else GLYPH["pending"]),
        "debrief " + (GLYPH["ok"] if f["debrief_closed"] else GLYPH["pending"]),
    ])
    out += ["  gates: " + gline, ""]
    c = f["counts"]
    out.append("Tasks   Done %d, Todo %d, Canceled %d      %s  %s" % (
        c["Done"], c["Todo"], c["Canceled"], bar(f["done"], f["denominator"]),
        ("%d%%" % round(100 * f["done"] / f["denominator"])) if f["denominator"] else "—"))
    for it in f["todo_items"]:
        out.append("  %s, %s" % (it["id"], it["title"] or ""))
    for run in f.get("fast_track_open") or []:
        out.append(run_line(run))
    dl = "Dates   started %s, last activity %s, age %s, %s" % (
        f["started"] or "—", f["last_activity"] or "—",
        ("%dd" % f["age_days"]) if f["age_days"] is not None else "—",
        idle_phrase(f["idle_days"]) or "idle —")
    if f["stale"]:
        dl += " %s (> %dd)" % (GLYPH["warn"], f["threshold"])
    out += ["", dl]
    if f["integrity"]:
        out.append("Note    ! " + f["integrity"])
    if f.get("waiting"):
        out.append("Waiting %s (operator question open)" % f["waiting"])
    if f.get("completeness_note"):
        out.append("Complete %s" % f["completeness_note"])
    if f["next"]:
        out.append("Next    %s" % f["next"])
    p = f.get("paths_rel") or f["paths"]
    out.append("Files   " + ", ".join([x for x in (p["spec"], p["tasks"], p["scope"]) if x]))
    out += [""] + inspect_lines(f)
    return "\n".join(out).rstrip("\n")


def inspect_report(f):
    """The Inspect report of the feature's gate record (gate_record.report), or None with no record; derived on every
    call. A record or identity error is returned as {"error": <why>}."""
    if not f.get("inspect_record"):
        return None
    try:
        import gate_record
        return gate_record.report(os.path.realpath(os.path.abspath(f["lane_root"])), os.path.abspath(f["inspect_record"]))
    except Exception as e:  # an unreadable record is shown, never a crash of the board
        return {"error": str(e)[:200]}


def inspect_lines(f):
    rep = inspect_report(f)
    if rep is None:
        return []
    if "error" in rep:
        return ["Inspect record  error: " + rep["error"]]
    import gate_record
    return gate_record.report_text(rep, os.path.realpath(os.path.abspath(f["lane_root"])))


def render_feature(data, fid):
    q = fid.lower()
    matches = [x for x in data["features"]
               if x["id"].lower() == q or x["id"].lower().startswith(q + "-")]
    if not matches:
        return "no such feature in registry: %s" % fid
    multi = data["lane_count"] > 1
    return "\n\n".join(_feature_block(f, f["lane"] if multi else None) for f in matches)


# --- L2: the reviewer-set validating oracle (replaces the existence-only glob) ---
# The gate does NOT merely check a verdict file exists; it validates the L1 header and
# recomputes deterministic-family Checkers. Exit-coded — a new gate a pre-close hook
# would run; that hook is deferred, so nothing auto-runs this yet.
VERDICT_KEYS = ("checker-id", "target-sha", "capture-evidence-ref", "verdict", "timestamp")


def parse_verdict_header(path):
    """Read an L1 verdict artifact's `key: value` header. {} on unreadable."""
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return {}
    hdr = {}
    for key in VERDICT_KEYS:
        m = re.search(r"^%s:\s*(.+?)\s*$" % re.escape(key), text, re.M)
        if m:
            hdr[key] = m.group(1).strip()
    return hdr


def index_checkers(*paths):
    """Map `said-checker` id -> meta. Discovers both forms: an **agent-form** Checker
    (a subagent's frontmatter) and a **recipe-form** Checker (a `said-*` block in a
    `docs/ux` rules file — the row declares its capture + judge inline). A block is a
    run of lines between blank lines; any block carrying a `said-checker:` line is a
    Checker, so one rules file may declare several. `paths` are dirs (globbed `*.md`)
    or files."""
    files = []
    for p in paths:
        if p and os.path.isdir(p):
            files.extend(sorted(glob.glob(os.path.join(p, "*.md"))))
        elif p and os.path.isfile(p):
            files.append(p)
    idx = {}
    for path in files:
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
        except OSError:
            continue
        for block in re.split(r"\n[ \t]*\n", text):
            if "said-checker:" not in block:
                continue
            meta = {}
            for key in ("said-checker", "said-governs", "said-capture", "said-judge", "said-recompute"):
                m = re.search(r"^[ \t>*-]*%s:\s*(.+?)\s*$" % re.escape(key), block, re.M)
                if m:
                    # strip an inline ` # comment` (recipe-form rows document the field after the value);
                    # a `#` glued to a token (no leading space) is kept, so a value never loses content.
                    meta[key] = re.sub(r"\s+#.*$", "", m.group(1)).strip()
            cid = meta.get("said-checker")
            if cid:
                if cid in idx:  # duplicate said-checker id: deterministic first-wins (files sorted), surfaced not silent
                    sys.stderr.write("  ! index_checkers: duplicate said-checker id %r — keeping first, ignoring %s\n" % (cid, path))
                    continue
                idx[cid] = meta
    return idx


def _completeness_report(out):
    """The completeness recompute's advisory report lines (`completeness-report: ...`) from its stdout (or
    a recorded note artifact), as a compact one-line summary for the reviewer line / board: the under-spec
    WARN + each unit's last-revised provenance. Parses the producer's defined machine grammar (never the
    human sentence); tolerant of a leading markdown list marker / indentation so a recorded note field is
    extracted rather than silently dropped. Non-gating display text -- it never affects the reviewer verdict
    or the exit code. Sanitized: control chars dropped, length capped, and a literal `reviewer-gate:` /
    `completeness-report:` marker neutralized, so builder-authored content that reaches this line can never
    forge an authoritative marker or inject a control sequence."""
    tag = "completeness-report:"
    parts = []
    for ln in out.splitlines():
        s = ln.lstrip()
        while s[:1] in ("-", "*"):        # tolerate a leading list marker (a recorded note field)
            s = s[1:].lstrip()
        if s.startswith(tag):
            parts.append(s.split(tag, 1)[1].strip())
    report = "; ".join(parts)
    report = "".join(c if 0x20 <= ord(c) < 0x7f else " " for c in report)   # drop control chars
    for marker in ("reviewer-gate:", tag):                                  # neutralize a forged marker
        report = report.replace(marker, marker[:-1] + ";")
    return report[:500]


def _gate_recompute_rows(out):
    """The gate recompute's per-harness rows (`gate-recompute: <unit-path> exit=<n> <PASS|EXPECTED|FAIL> [ids]`)
    from its stdout, as one compact display string for the reviewer line; every other stdout line is
    discarded. Display only -- never affects the verdict or the exit code (the recompute's exit code is the
    only truth). Builder-authored harness text can reach it, so it is sanitized like `_completeness_report`:
    control chars dropped, each row and the whole string length-capped, authoritative markers neutralized."""
    tag = "gate-recompute:"
    rows = []
    for ln in out.splitlines():
        s = ln.lstrip()
        if s.startswith(tag):
            row = s.split(tag, 1)[1].strip()
            row = "".join(c if 0x20 <= ord(c) < 0x7f else " " for c in row)
            for marker in ("reviewer-gate:", tag, "completeness-report:", "Verdict:", "Blocked-on question:"):
                row = row.replace(marker, marker[:-1] + ";")
            rows.append(row[:160])
    return " | ".join(rows)[:600]


def _pick_verdict(hits, head_sha):
    """The verdict file to judge: the one whose target-sha is HEAD (the newest if several), else the newest
    by modification time; never the last by file name. Equal times fall back to name order."""
    def mtime(path):
        try:
            return os.path.getmtime(path)
        except OSError:
            return 0.0
    at_head = [p for p in hits if head_sha and parse_verdict_header(p).get("target-sha") == head_sha]
    return max(at_head or hits, key=lambda p: (mtime(p), p))


def validate_reviewer(workdir, cid, meta, head_sha, root=".", surface=None):
    """Validate one expected reviewer's L1 verdict. Returns (ok, reason)."""
    if meta is None:  # declared reviewer id resolves to no Checker — nominal; a verdict can never redeem it
        return False, "reviewer %r does not resolve to a Checker (nominal — no said-checker match)" % cid
    hits = sorted(glob.glob(os.path.join(workdir, "review-%s-*.md" % glob.escape(cid))))
    if not hits:
        if _oracle_kind(meta):  # no step writes this Checker's verdict file
            return _recompute_reviewer(workdir, meta, "recomputed", root, surface)
        return False, "missing verdict artifact (review-%s-*.md)" % cid
    picked = _pick_verdict(hits, head_sha)
    hdr = parse_verdict_header(picked)
    if hdr.get("verdict", "").upper() != "PASS":
        return False, "verdict != PASS (%s)" % (hdr.get("verdict") or "absent")
    cap = hdr.get("capture-evidence-ref")
    if not cap:
        return False, "no capture-evidence-ref"
    if cap == "none" and cid == "doc-editorial":  # a doc lane's feature read: the writer's own parse is the check
        try:
            with open(picked, encoding="utf-8") as fh:
                _fr_parse(fh.read(), head_sha, workdir, verdict_path=picked, doc=True)
        except (OSError, UnicodeDecodeError, FeatureReviewRefused) as e:
            return False, "`none` on a feature read the writer refuses: %s" % _fr_clean(str(e), 120)
        cap_path = cap
    elif cap == "none":
        return False, "`none` is the feature read's no-capture sentinel, never a Checker's capture"
    elif cap == "recomputed":  # `recomputed`: a sentinel, not a file — valid only where the recompute below actually re-derives the verdict
        if ((meta or {}).get("said-capture") != "process-spawn"
                or not (meta or {}).get("said-recompute")
                or (meta or {}).get("said-judge") not in ("oracle", "metric")):
            return False, "`recomputed` allowed only for a process-spawn + deterministic (oracle/metric) + said-recompute Checker"
        cap_path = cap  # the deterministic recompute below is the evidence (verdict already PASS-checked above)
    else:  # lane-path rule: a verdict cites only a path inside its own working dir
        cap_path = os.path.normpath(os.path.join(workdir, cap)); wd = os.path.normpath(workdir)
        if os.path.isabs(cap) or not (cap_path == wd or cap_path.startswith(wd + os.sep)):
            return False, "capture outside the lane working dir (%s)" % cap
        if not os.path.isfile(cap_path):  # a dir/missing ref is not a capture
            return False, "dangling capture (%s)" % cap
    tgt = hdr.get("target-sha")
    if head_sha and tgt != head_sha:  # absent tgt fails too — never skip the staleness check
        return False, "stale/missing target-sha (%s != HEAD %s)" % (tgt[:8] if tgt else "absent", head_sha[:8])
    return _recompute_reviewer(workdir, meta, cap_path, root, surface)


def _oracle_kind(meta):
    """A process-spawn oracle or metric Checker whose said-recompute runs the lane gate, from any Checker form."""
    meta = meta or {}
    if meta.get("said-capture") != "process-spawn" or meta.get("said-judge") not in ("oracle", "metric"):
        return False
    cmd = meta.get("said-recompute") or ""
    if re.search(r"[;|&<>()`#\n]", cmd):  # its exit status must be the script's own
        return False
    try:
        words = shlex.split(cmd)
    except ValueError:
        return False
    return len(words) == 2 and words[0] in ("sh", "bash") and os.path.basename(words[1]) == "gate_recompute.sh"


def _recompute_reviewer(workdir, meta, cap_path, root, surface):
    """(ok, reason) of a Checker's own recompute; a judge that is not deterministic passes on its verdict."""
    judge = (meta or {}).get("said-judge")
    if judge in ("oracle", "metric"):  # deterministic -> must recompute, never trust the file
        cmd = (meta or {}).get("said-recompute")
        if not cmd:
            return False, "%s Checker declares no said-recompute (unverifiable)" % judge
        # A plugin-shipped recompute script resolves via SAID_PLUGIN_ROOT (this oracle's own
        # plugin dir), so it works whether or not the target vendors the plugin.
        plugin_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        # The per-surface lane grammar (unit + containers + attribute set) the completeness recompute
        # reads, injected like SAID_PLUGIN_ROOT so a plugin-shipped recompute resolves it; a recompute
        # that does not need it ignores it. SAID_SURFACE selects the grammar's surface section.
        env = {**os.environ, "SAID_WORKDIR": os.path.abspath(workdir), "SAID_CAPTURE": cap_path,
               "SAID_PLUGIN_ROOT": plugin_root,
               # the lane root, so a completeness recompute can resolve the grammar's unit-home=dir:<path>
               # durable specs; a recompute that does not need it ignores it.
               "SAID_ROOT": os.path.abspath(root),
               "SAID_GRAMMAR": os.path.join(os.path.abspath(root), _lane_key(root, "docs-root") or "docs", "ux", "feature-ux-grammar.md")}
        if surface:
            env["SAID_SURFACE"] = surface
        for key in ("SAID_GATE_UNITS", "SAID_GATE_OUT"):  # a caller's unit list or record never narrows this run
            env.pop(key, None)
        proc = subprocess.run(cmd, shell=True, cwd=root, capture_output=True, env=env)
        stdout = proc.stdout.decode("utf-8", "replace")
        rows = _gate_recompute_rows(stdout)  # per-harness rows on both paths; display only
        if proc.returncode != 0:
            return False, "recompute failed (exit %d)%s" % (proc.returncode, " -- " + rows if rows else "")
        # Surface the recompute's advisory report (under-spec WARN + per-unit last-revised provenance) it
        # emits on stdout onto the reviewer line -- advisory text on a PASS; never flips ok or the exit code.
        report = "; ".join(x for x in (_completeness_report(stdout), rows) if x)
        return True, ("PASS -- " + report if report else "PASS")
    return True, "PASS"


def _governs_surface(meta, surface):
    """Whether a resolved Checker governs `surface` (self-selection: a Checker governs only the
    surface it declares). A Checker with no said-governs, no `surface=` clause (it governs by
    shape, not medium), or `surface=any` governs any surface (backward compat); otherwise it
    governs only the surface(s) its said-governs names."""
    g = (meta or {}).get("said-governs")
    if not g:
        return True
    m = re.search(r"surface\s*=\s*([A-Za-z0-9_,|-]+)", g)  # value stops at whitespace — no cross-token over-match
    if not m:
        return True
    vals = [v.strip().lower() for v in re.split(r"[,|]+", m.group(1)) if v.strip()]
    if not vals:  # a degenerate value (only separators) is not a surface restriction — govern-any, never a silent skip
        return True
    return "any" in vals or (surface or "").strip().lower() in vals


def _lane_mounts(root):
    """The whole SAID.mounts: value on the lane block's own key list, or None."""
    return lane_block_key(root, "mounts")


def lane_block_key(root, name):
    """The whole value of `SAID.<name>:` on the lane block's own key list (lane_block_lines, at the key column), or None."""
    try:
        with open(os.path.join(root, "CLAUDE.md"), encoding="utf-8-sig", errors="replace") as fh:
            block = lane_block_lines(fh.read())
    except (OSError, ValueError):
        return None
    if block is None:
        return None
    keyed = [ln for ln in block if re.match(r"^\s*[-*]?\s*SAID\.[\w-]+:", ln)]
    col = key_column(keyed[0]) if keyed else 0
    for ln in keyed:  # the whole value of the key's own line, so only the bare word reads as none
        m = re.match(r"^\s*[-*]?\s*SAID\.%s:[ \t]*(.*?)[ \t]*$" % re.escape(name), ln)
        if m and key_column(ln) == col:
            return m.group(1)
    return None


def reviewer_gate(workdir, surface, reviewers, checker_index, head_sha, root="."):
    """L2 gate over the declared reviewer set. Returns (passed, [(id, ok, reason), ...])."""
    surface = (surface or "").strip()
    reviewers = [r.strip() for r in reviewers if r and r.strip()]
    if surface in ("", "none"):
        return True, [("surface", True, "none — declared skip")]
    if not reviewers:
        return False, [("reviewers", False,
                        "surface-bearing (%s) but no reviewers declared — declare reviewers:, or surface: none" % surface)]
    details, skipped, passed = [], [], True
    nothing_shipped = surface == "doc" and _lane_mounts(root) == "none"
    for cid in reviewers:
        meta = checker_index.get(cid)
        if nothing_shipped and cid == "doc-editorial":  # a doc lane that ships nothing has no prose to review
            details.append((cid, True, "N/A -- SAID.mounts: none, nothing shipped"))
            continue
        # an un-instantiated said-governs placeholder on a REQUIRED Checker (a lane copied the recipe
        # template's surface=<...> without instantiating it) is a config error, never a silent govern-any:
        # the <...> value fails the surface= value regex below, which would otherwise fall through to
        # govern-any and let the outline-less gate pass. Fire only for a resolved (required) Checker.
        gv = (meta or {}).get("said-governs")
        if meta is not None and gv and re.search(r"surface\s*=\s*<", gv):
            details.append((cid, False, "malformed said-governs %r -- the recipe placeholder was never "
                            "instantiated; set surface= to the lane's medium (config error)" % gv))
            passed = False
            continue
        # said-governs routing (a Checker governs only the surface it declares): a RESOLVED Checker
        # that does not govern this surface
        # is not required here; a governs-less Checker governs any; an unresolved (nominal) reviewer
        # stays required, so a mismatched/absent said-governs is never a skip-the-gate lever
        if meta is not None and not _governs_surface(meta, surface):
            skipped.append((cid, (meta or {}).get("said-governs")))
            continue
        ok, reason = validate_reviewer(workdir, cid, meta, head_sha, root, surface)
        details.append((cid, ok, reason))
        passed = passed and ok
    if not details:  # empty-after-filter: a surface-bearing feature whose declared reviewers none govern is ungated
        return False, [("reviewers", False,
                        "surface-bearing (%s) but none of the declared reviewers govern surface=%s "
                        "(a Checker's said-governs must match, or omit it to govern any)" % (surface, surface))]
    for cid, gov in skipped:  # report the filtered Checkers — a skip is visible, never silent (no nominal-gate hole)
        details.append((cid, True, "skipped — %s does not govern surface=%s (not required for this feature)" % (gov, surface)))
    return passed, details


def _plugin_agents_dir():
    """The said plugin's OWN `agents/` dir (absolute), resolved from this file's install
    location — the dir the runtime loads Checkers from (same basis as the SAID_PLUGIN_ROOT
    recompute). Works whether or not the target repo vendors the plugin."""
    return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "agents")


# --- the lane registry (SAID.lanes:) -----------------------------------------
# One key line of TOKEN=root pairs in brackets, inside the "## Lane" block of a
# multi-lane root:  - SAID.lanes: [WEB=web/, API=api/, APP=./]
# Every script takes a lane's root from read_lane_registry(); none parses the line itself.
_REG_FENCE_RE = re.compile(r"^[ \t]*(`{3,}|~{3,})(.*)$")


def fence_step(fence, line):
    """One step of fence tracking: return (is_a_fence_line, fence_now_open). A fence opens on
    three or more backticks or tildes (a backtick opener's info string holds no backtick)
    and closes only on a line of the same character, at least as long, with nothing after."""
    m = _REG_FENCE_RE.match(line)
    if not m:
        return False, fence
    run, rest = m.group(1), m.group(2)
    if fence is None:
        if run[0] == "`" and "`" in rest:
            return False, None
        return True, run
    if run[0] == fence[0] and len(run) >= len(fence) and not rest.strip():
        return True, None
    return False, fence
_REG_KEY_RE = re.compile(r"^[ \t]*[-*]?[ \t]*SAID\.lanes:[ \t]*(.*?)[ \t]*$")
_REG_KEYSHAPE_RE = re.compile(r"^[ \t]*[-*]?[ \t]*SAID\.[\w-]+:")
# a roster row written as a bullet: `- TOKEN: path/`, `- TOKEN -> path/`, `- TOKEN = path/`, the path also
# one that ends in CLAUDE.md (`- TOKEN: dir/CLAUDE.md`); or a bullet whose token or path is a markdown link
# to such a path (`- [TOKEN](dir/CLAUDE.md)`, `- TOKEN: [dir](dir/)`)
_REG_DIR = r"(?:\.\.?/|[^\s`\"'\]/.~:][^\s`\"'\]/.:]*/)(?:[^\s`\"'\]]*/)?"  # relative, ends in /:
_REG_CLAUDE = r"CLAUDE\.md(?![\w-]|\.\w)"                                     # never absolute, ~,
_REG_PATH = r"%s(?:%s)?" % (_REG_DIR, _REG_CLAUDE)                              # a URL or a bare domain
_REG_LDIR = r"(?:\.\.?/|[^\s`\"'\]\[()/.~:][^\s`\"'\]\[()/.:]*/)(?:[^\s`\"'\]\[()]*/)?"  # in a link target
_REG_LINK = r"\[[^\]\n]*\]\((?:%s(?:%s)?|%s)(?:[ \t]+\"[^\"]*\")?\)" % (_REG_LDIR, _REG_CLAUDE, _REG_CLAUDE)
_REG_ROSTER_RE = re.compile(
    r"^[ \t]*(?:[-*+]|\d+[.)])[ \t]+(?:"               # a bullet or a numbered item
    + _REG_LINK + r"|"                                 # that opens with a link, or
    r"(?:\*\*|__|`)?[A-Za-z][\w-]*(?:\*\*|__|`)?"       # the token: plain, bold or in backticks
    r"(?:[ \t]*\([^)]*\))?"                           # a note on the token
    r"[ \t]*(?::|->|=|\u2014|\u2013|\u2192)[ \t]*"      # the separator
    r"(?:" + _REG_LINK + r"|[\"'`\[]?" + _REG_PATH +   # a link, or a path
    r"[\"'`\]]?(?:[\s,.;)]|$)))")
# a table's delimiter row, with or without its outer pipes: `--- | ---`, `|:--|--:|`
_REG_DELIM_RE = re.compile(r"^[ \t]*\|?[ \t]*:?-+:?[ \t]*(?:\|[ \t]*:?-+:?[ \t]*)+\|?[ \t]*$")
_REG_QUOTE_RE = re.compile(r"^[ \t]*(?:>[ \t]?)+")  # a blockquote prefix; what it quotes is read as written
EMPTY_REGISTRY = "an empty registry; remove the key or declare rows"


class RegistryRefused(ValueError):
    """A registry line the reader does not take. `kind` is 'empty' for `[]`, 'twice' when
    the key is declared more than once in the block, 'shape' when rows sit beneath the line
    or the line is indented off the key list, else 'malformed'."""

    def __init__(self, reason, kind="malformed"):
        ValueError.__init__(self, reason)
        self.kind = kind


def lane_block_numbered(text):
    """The lane block as [(line_number, line), ...], line numbers 0-based in the file, for the
    lines that sit outside code fences: under a heading that is exactly '## Lane' at column
    0, up to the next '## ' heading or EOF. None when the file has no such heading.
    '## Lane web' and '## Lanes' are not the lane block, and neither a heading nor a key
    line shown inside a fenced example is ever returned."""
    block, fence = None, None
    for n, ln in enumerate(text.splitlines()):
        marker, fence = fence_step(fence, ln)
        if marker or fence:
            continue
        if block is None:
            if ln.rstrip() == "## Lane":
                block = []
        elif ln.startswith("## "):
            break
        else:
            block.append((n, ln))
    return block


def lane_block_lines(text):
    """The lines of lane_block_numbered(text), without their numbers; None when no block."""
    block = lane_block_numbered(text)
    return None if block is None else [ln for _, ln in block]


def key_column(line):
    """A line's indent in columns (a tab counts four), so a tab cannot pass for a shallower
    indent. The key list's column is that of the block's first key-shaped line; a key-shaped
    line at another column is an annotation under a key, not a key line."""
    return len(line[:len(line) - len(line.lstrip(" \t"))].expandtabs(4))


def locate_lane_registry(text):
    """Where the registry sits in the lane block of `text`. None when the file has no lane
    block or the block carries no SAID.lanes: line. Else a dict:
      values  - the value of each SAID.lanes: line that sits at the key list's column
      nested  - file line numbers of SAID.lanes: lines indented off the key list
      beneath - file line numbers of what sits beneath the registry line, when there is
                exactly one: every line that abuts it and, past a blank line, table rows and
                indented lines up to the next key line or the first plain line; then, to the
                end of the section, any table row or roster bullet (`TOKEN: path/`), whatever
                plain lines or headings sit between: the registry's leftover
    One answer for the reader and for the checker, so they cannot disagree on a shape."""
    block = lane_block_numbered(text)
    if block is None:
        return None
    shaped = [i for i, (_, ln) in enumerate(block) if _REG_KEYSHAPE_RE.match(ln)]
    reg = [i for i in shaped if _REG_KEY_RE.match(block[i][1])]
    if not reg:
        return None
    col = key_column(block[shaped[0]][1])
    on = [i for i in reg if key_column(block[i][1]) == col]
    loc = {"values": [_REG_KEY_RE.match(block[i][1]).group(1) for i in on],
           "nested": [block[i][0] for i in reg if i not in on], "beneath": []}
    if len(reg) == 1:
        plain = [_REG_QUOTE_RE.sub("", ln) for _, ln in block]
        tabular = set()  # rows of a table, with or without its outer pipes
        for i, ln in enumerate(plain):
            if ln.lstrip(" \t").startswith("|"):
                tabular.add(i)
            elif _REG_DELIM_RE.match(ln) and i > 0 and "|" in plain[i - 1]:  # a table has a header row
                tabular.update((i - 1, i))
                j = i + 1
                while j < len(plain) and plain[j].strip() and "|" in plain[j]:
                    tabular.add(j)
                    j += 1
        abuts = attached = True
        for i in range(reg[0] + 1, len(block)):
            n, ln = block[i]
            if not ln.strip():
                abuts = False
                continue
            table = i in tabular
            if _REG_KEYSHAPE_RE.match(ln) and key_column(ln) == col:
                abuts = attached = False  # another key; the leftover scan goes on to the section's end
                continue
            if attached and (abuts or key_column(ln) > col or table):
                loc["beneath"].append(n)
                continue
            attached = False
            if table or _REG_ROSTER_RE.match(plain[i]):
                loc["beneath"].append(n)
    return loc


def read_registry_text(text):
    """The registry's rows, [(token, root_as_written), ...], from the text of a CLAUDE.md;
    [] when its lane block declares none. Raises RegistryRefused when the line, or what sits
    around it, is not the one key line the grammar admits."""
    loc = locate_lane_registry(text)
    if loc is None:
        return []
    if loc["nested"]:
        raise RegistryRefused("the SAID.lanes: line on line %d is indented as a sub-bullet; a key line sits at "
                              "the key list's own column, so no row is read" % (loc["nested"][0] + 1), kind="shape")
    if len(loc["values"]) > 1:
        raise RegistryRefused("SAID.lanes: is declared %d times in the lane block; a list key is declared once"
                              % len(loc["values"]), kind="twice")
    empty = None
    try:
        rows = parse_lane_registry(loc["values"][0])
    except RegistryRefused as e:
        if e.kind != "empty":
            raise
        empty = e
    if loc["beneath"]:
        raise RegistryRefused("%d line(s) sit beneath the SAID.lanes: line, from line %d; a row, a table or a "
                              "sub-bullet there is read by nothing, and the registry is one key line"
                              % (len(loc["beneath"]), loc["beneath"][0] + 1), kind="shape")
    if empty is not None:
        raise empty
    return rows


def parse_lane_registry(value):
    """Parse the value of a SAID.lanes: key line into [(token, root), ...].

    Grammar: '[' pair (',' pair)* ']'; pair = TOKEN '=' ROOT; TOKEN = a letter, then letters
    and digits, unique in the line; ROOT = a relative directory path ending in '/', with no
    whitespace. Whitespace after '[', before ']' and around ',' is not significant; around
    '=' it is malformed. Raises RegistryRefused with the reason."""
    s, n, i = value, len(value), 0

    def skip_ws(k):
        while k < n and s[k] in " \t":
            k += 1
        return k

    def found(k):
        return "end of line" if k >= n else repr(s[k])

    i = skip_ws(i)
    if i >= n:
        raise RegistryRefused("the key line carries no value; a registry is one bracketed line of TOKEN=root pairs")
    if s[i] != "[":
        raise RegistryRefused("the value does not open with '['; a registry is [TOKEN=root, TOKEN=root]")
    i = skip_ws(i + 1)
    if i < n and s[i] == "]":
        if skip_ws(i + 1) < n:
            raise RegistryRefused("text after the closing ']'")
        raise RegistryRefused(EMPTY_REGISTRY, kind="empty")
    rows, seen = [], set()
    while True:
        j = i
        if i < n and (("a" <= s[i] <= "z") or ("A" <= s[i] <= "Z")):
            i += 1
            while i < n and (("a" <= s[i] <= "z") or ("A" <= s[i] <= "Z") or ("0" <= s[i] <= "9")):
                i += 1
        token = s[j:i]
        if not token:
            raise RegistryRefused("expected a token (a letter, then letters and digits), found %s" % found(i))
        if i >= n or s[i] != "=":
            raise RegistryRefused("token %r is followed by %s, not '='; a pair is TOKEN=root and a bare token is not legal" % (token, found(i)))
        i += 1
        j = i
        while i < n and s[i] not in ", \t]=[;":
            i += 1
        root = s[j:i]
        if i < n and s[i] in "=[;":
            raise RegistryRefused("unexpected %s in the root of %r" % (found(i), token))
        if not root:
            raise RegistryRefused("token %r has no root" % token)
        if any(unicodedata.category(ch) in ("Cc", "Cf") or ch == "\ufffd" for ch in root):
            raise RegistryRefused("the root of %r carries a control or format character, or a byte that is not UTF-8" % token)
        if root.startswith("/"):
            raise RegistryRefused("the root of %r is absolute; a root is relative to the directory of the file that carries the registry" % token)
        if not root.endswith("/"):
            raise RegistryRefused("the root %r of %r does not end with '/'" % (root, token))
        if token in seen:
            raise RegistryRefused("token %r is declared twice" % token)
        seen.add(token)
        rows.append((token, root))
        i = skip_ws(i)
        if i >= n:
            raise RegistryRefused("the list is not closed with ']'")
        if s[i] == ",":
            i = skip_ws(i + 1)
            if i < n and s[i] == "]":
                raise RegistryRefused("an empty item before ']'")
            continue
        if s[i] == "]":
            i += 1
            break
        raise RegistryRefused("expected ',' or ']' after %s=%s, found %s" % (token, root, found(i)))
    if skip_ws(i) < n:
        raise RegistryRefused("text after the closing ']'")
    return rows


def read_lane_registry(root):
    """Read the lane registry declared in <root>/CLAUDE.md.

    Returns (rows, None) with rows = [(token, root_as_written), ...]; ([], None) when the
    lane block declares no registry (or there is no lane block, or no file). Raises
    RegistryRefused when the block's registry line is not one the grammar admits. Only the
    line inside the lane block is read: a directory the registry does not name is never a row."""
    try:
        with open(os.path.join(root, "CLAUDE.md"), encoding="utf-8-sig", errors="replace") as fh:
            text = fh.read()  # a stray byte elsewhere in the file does not hide the registry
    except (OSError, ValueError):
        return [], None
    return read_registry_text(text), None


def run_registry(a):
    """`--registry`: print one TOKEN:root=<root> line per row, the form --lane takes, then
    `count: <N>`; exit 0. A refused line prints `refused: <reason>` and exits 2."""
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    try:
        if a.resolve:
            rows, skipped = resolve_lane_rows(a.root)
            out = rows + skipped + ["count: %d" % len(rows)]
        else:
            rows, _ = read_lane_registry(a.root)
            out = ["%s:root=%s" % (token, lane_root) for token, lane_root in rows] + ["count: %d" % len(rows)]
    except RegistryRefused as e:
        print("refused: %s" % e)
        return 2
    except Exception as e:  # never a traceback: a caller reads rows or one refused line
        print("refused: unexpected %s" % type(e).__name__)
        return 2
    print("\n".join(out))
    return 0


LANE_DIR_RE = re.compile(r"[A-Za-z0-9._-]+(/[A-Za-z0-9._-]+)*")


def _block_key(block, key):
    """The value of `SAID.<key>:` on the lane block's own key list (the column of its first key
    line; a key-shaped annotation under another key is not read), cut at the first blank; None
    when the block does not declare the key."""
    keyed = [ln for ln in block if re.match(r"^\s*[-*]?\s*SAID\.[\w-]+:", ln)]
    col = key_column(keyed[0]) if keyed else 0
    for ln in keyed:
        m = re.match(r"^\s*[-*]?\s*SAID\.%s:[ \t]*(\S*)" % re.escape(key), ln)
        if m and key_column(ln) == col:
            return m.group(1)
    return None


def _lane_dir(value, key):
    """The directory a lane path key names, up to its `<id>` segment (the file's own dir when the
    value names no `<id>`). Raises ValueError naming the key when the value is absent or is not a
    plain relative path inside the lane: absolute, a `..` segment, or a character outside
    letters, digits and `._/-` (so a `;` or `=` never reaches the --lane row)."""
    if not value:
        raise ValueError("SAID.%s: is not declared in the lane block" % key)
    if value.startswith(("/", "~")):
        raise ValueError("SAID.%s: is not a plain relative path inside the lane" % key)
    cut = value.find("<id>")
    d = value[:cut] if cut >= 0 else (os.path.dirname(value) if key == "task-log" else value)
    d = d.rstrip("/") or "."
    if d != "." and (not LANE_DIR_RE.fullmatch(d) or ".." in d.split("/")):
        raise ValueError("SAID.%s: is not a plain relative path inside the lane" % key)
    return d


def resolve_lane_rows(root):
    """`--registry --resolve`: for each registry row, the full --lane argument
    `TOKEN:root=<root>;docs=<dir>;working=<dir>`, the two dirs read from the lane's OWN `## Lane`
    block (SAID.task-log, SAID.working). Returns (rows, skipped); a row whose root holds no
    CLAUDE.md or no lane block, or whose key is absent or unsafe, is skipped with one line.
    Raises RegistryRefused as read_lane_registry does. A directory the registry does not name
    is never read."""
    rows, skipped = [], []
    for token, lane_root in read_lane_registry(root)[0]:
        why = None
        try:
            with open(os.path.join(root, lane_root, "CLAUDE.md"), encoding="utf-8-sig", errors="replace") as fh:
                block = lane_block_lines(fh.read())
        except (OSError, ValueError):
            block, why = None, "no CLAUDE.md at the lane root"
        if why is None and block is None:
            why = "no ## Lane block outside a code fence in its CLAUDE.md"
        if why is None:
            try:
                docs = _lane_dir(_block_key(block, "task-log"), "task-log")
                work = _lane_dir(_block_key(block, "working"), "working")
            except ValueError as e:
                why = str(e)
        if why:
            skipped.append("skipped: %s root=%s -- %s" % (token, lane_root, why))
        else:
            rows.append("%s:root=%s;docs=%s;working=%s" % (token, lane_root, docs, work))
    return rows, skipped


def _lane_key(root, key):
    """Declaration-first read of a scalar `SAID.<key>:` from the lane's <root>/CLAUDE.md; returns
    the raw value of the first match, or None. The one read-shape resolve_checkers_dir,
    _resolve_recipe_rules, and the reviewer-gate grammar injection share (each keeps its own fallback)."""
    try:
        with open(os.path.join(root, "CLAUDE.md"), encoding="utf-8") as fh:
            for line in fh:
                m = re.match(r"^\s*[-*]?\s*SAID\.%s:\s*(\S+)" % re.escape(key), line)
                if m:
                    return m.group(1)
    except (OSError, UnicodeDecodeError):  # a missing OR non-UTF8 CLAUDE.md -> fall through, never crash the gate
        pass
    return None


def resolve_checkers_dir(root, arg):
    """Resolve the agent-form Checker dir the reviewer-gate VALIDATES. It MUST be the dir the
    runtime LOADS the Checker from, or the gate validates a different object than the one that
    runs — a per-project drop-in (e.g. `content/agents/`) that Claude Code never executes. So the
    default is the plugin's OWN `agents/` (the executing Checker), NOT a repo-relative path.
    Precedence: an explicit `--checkers-dir`; else the lane's `SAID.checkers-dir:` (only for a lane
    that ships its OWN executing agents, e.g. under `.claude/agents/`, and points the gate there);
    else the plugin's own agents dir. The resolvability invariant asserts on the *resolved* file."""
    if arg is not None:
        return arg
    d = _lane_key(root, "checkers-dir")
    return d if d is not None else _plugin_agents_dir()


def _resolve_recipe_rules(root, arg):
    """Resolve the recipe-form rules file the reviewer-gate scans for recipe-form Checkers.
    An explicit --recipe-rules naming a missing file is a hard error (exit 2, the path named) --
    never the silent skip index_checkers would take on a non-existent path. Absent, default it
    from the lane block: the lane's SAID.docs-root: joined with ux/feature-ux-rules.md, if that
    file exists -- the same declaration-first lane read resolve_checkers_dir does for
    SAID.checkers-dir:. No lane key, or no such file -> None (a lane that ships no recipe registry;
    the gate then points the operator at one)."""
    if arg is not None:
        cand = arg if os.path.exists(arg) else os.path.join(root, arg)  # a root-relative path resolves (the caller root-joins --checkers-dir too)
        if not os.path.exists(cand):  # a file or a dir (index_checkers globs a dir); only a genuinely-missing path is the hard error
            sys.stderr.write("reviewer-gate: --recipe-rules: no such file: %s\n" % arg)
            sys.exit(2)
        return cand
    dr = _lane_key(root, "docs-root")
    if dr is not None:
        cand = os.path.join(root, dr, "ux", "feature-ux-rules.md")
        return cand if os.path.isfile(cand) else None
    return None


def run_reviewer_gate(a):
    """CLI dispatch for --reviewer-gate: prints per-reviewer verdicts, exits 0/1."""
    head = sh(["git", "-C", a.root, "rev-parse", "HEAD"]) or ""
    checkers_dir = resolve_checkers_dir(a.root, a.checkers_dir)  # lane-declared / fallback chain
    recipe_rules = _resolve_recipe_rules(a.root, a.recipe_rules)  # explicit (hard-error if missing) else lane-block default
    idx = index_checkers(os.path.join(a.root, checkers_dir), recipe_rules)
    revs = a.reviewers.split(",") if a.reviewers else []
    passed, details = reviewer_gate(a.workdir or ".", a.surface, revs, idx, head, a.root)
    for cid, ok, reason in details:
        if (not ok) and (recipe_rules is None) and "no said-checker match" in reason:  # nominal + no resolved registry: point the operator at recipe-form Checkers
            reason += " - hint: a recipe-form Checker lives in a docs/ux rules file; pass --recipe-rules <that file>"
        glyph = GLYPH["pending"] if (ok and reason.startswith("skipped")) else (GLYPH["ok"] if ok else GLYPH["block"])
        print("  %s %s: %s" % (glyph, cid, reason))
    print("reviewer-gate: %s" % ("PASS" if passed else "FAIL"))
    return 0 if passed else 1


FR_KEYS = ("checker-id", "target-sha", "capture-evidence-ref", "verdict", "timestamp")
FR_FILE_CAP = 1024 * 1024  # a verdict file longer than this is owed, never read whole
FR_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


class FeatureReviewRefused(Exception):
    pass


def _fr_clean(text, cap):
    """A cell shown on a row: control, format and line-break characters dropped, pipes and backslashes replaced,
    authoritative markers neutralized (one pass, case-insensitive), then cut to cap characters."""
    import gate_record
    text = "".join(ch for ch in text if unicodedata.category(ch) not in ("Cc", "Cf", "Zl", "Zp"))
    text = text.replace("|", "[pipe]").replace("\\", "[backslash]")
    low = "".join(ch.lower() if len(ch.lower()) == 1 else ch for ch in text)  # same length as text
    out, i = [], 0
    while i < len(text):
        hit = next((m for m in gate_record.FR_MARKERS if low.startswith(m, i)), None)
        if hit:
            out.append(text[i] + "[x]" + text[i + 1:i + len(hit)])
            i += len(hit)
        else:
            out.append(text[i])
            i += 1
    return "".join(out)[:cap].strip() or "-"


def _fr_cells(line):
    line = line.strip()
    if not (line.startswith("|") and line.endswith("|") and len(line) > 1):
        return None
    return [c.strip() for c in line[1:-1].split("|")]


def _fr_parse(text, head_sha, workdir, verdict_path="", doc=False, record_path=""):
    """(verdict, [(group, cells)]) of a reviewer's verdict text, or raise FeatureReviewRefused(why) naming every shape
    fault, joined by `; `; doc: a doc lane's verdict, checker-id doc-editorial and the seventh group Editorial."""
    verdict, rows, faults, _ = _fr_scan(text, head_sha, workdir, verdict_path, doc, record_path)
    if faults:
        raise FeatureReviewRefused("; ".join(faults))
    return verdict, rows


class _FrStop(Exception):
    pass


def _fr_scan(text, head_sha, workdir, verdict_path="", doc=False, record_path=""):
    """(verdict, rows read, shape faults, stopped) of a reviewer's verdict text: every fault the text can be followed
    past, in reply order; a header key out of place, a heading out of order or text before the first group ends the
    scan (stopped True), the rows after it unread."""
    import gate_record  # the verdict's groups and columns, one place; lazy: the analyzer runs without it
    FR_GROUPS = gate_record.fr_groups(doc)
    checker = "doc-editorial" if doc else "feature-reviewer"
    faults, rows, head = [], [], {}

    def stop(why):
        faults.append(why)
        raise _FrStop()

    try:
        return _fr_scan_body(text, head_sha, workdir, verdict_path, record_path, FR_GROUPS, checker, faults, rows, head, stop)
    except _FrStop:
        return head.get("verdict"), rows, faults, True


def _fr_scan_body(text, head_sha, workdir, verdict_path, record_path, FR_GROUPS, checker, faults, rows, head, stop):
    lines = text.split("\n")
    if len(lines) < 7:
        stop("the header is shorter than five lines and a blank line")
    for i, key in enumerate(FR_KEYS):
        k, sep, v = lines[i].partition(":")
        if not sep or k != key:  # a wrong key may shift every line after it: the scan ends here
            stop("header line %d is not `%s:` (keys in order: %s)" % (i + 1, key, ", ".join(FR_KEYS)))
        head[key] = v.strip()
    if lines[5].strip():
        faults.append("no blank line after the five header lines")
    if head["checker-id"] != checker:
        faults.append("checker-id is not %s" % checker)
    if not head_sha or head["target-sha"] != head_sha:
        faults.append("target-sha is not the current head")
    ref = head["capture-evidence-ref"]
    wd = os.path.realpath(workdir)
    full = os.path.realpath(os.path.join(wd, ref)) if ref and "\x00" not in ref else ""
    if ref == "none":
        pass  # no capture: the Captures group must be the single line `none`, checked after the rows
    elif not ref or os.path.isabs(ref) or not full.startswith(wd + os.sep) or not os.path.isfile(full):
        faults.append("capture-evidence-ref is not a relative regular file inside the working dir")
    elif os.path.getsize(full) == 0:
        faults.append("capture-evidence-ref names an empty file")
    elif verdict_path and (full == os.path.realpath(verdict_path) or os.path.exists(verdict_path) and os.path.samefile(full, verdict_path)):
        faults.append("capture-evidence-ref names the verdict file itself, not a capture")
    elif record_path and os.path.exists(record_path) and os.path.samefile(full, record_path):
        faults.append("capture-evidence-ref names the gate record, not a capture")
    if head["verdict"] not in ("PASS", "FAIL"):
        faults.append("verdict is neither PASS nor FAIL")
    group, cols, state, want, got, fails, beyond, width, colbad = None, (), "", 0, 0, 0, set(), 0, False
    body = len(faults)  # a fault of the body hides rows: the verdict-to-rows checks then add nothing
    for raw in lines[5 if lines[5].strip().startswith("#") else 6:]:  # a heading in the blank line's place is read
        line = raw.strip()
        if line.startswith("#"):
            if group not in beyond and (state in ("open", "head") or state in ("rows", "closed") and not got):
                faults.append("group %s has no rows and no `none` line" % group)
            got = 0
            if want >= len(FR_GROUPS) or line != "## " + FR_GROUPS[want][0]:
                stop("heading `%s` is not the next of the %d groups" % (_fr_clean(line, 40), len(FR_GROUPS)))
            group, cols = FR_GROUPS[want]
            width = len(cols)
            state = "open"
            want += 1
            continue
        if not line:
            if state == "rows":
                state = "closed"
            continue
        if group is None:
            stop("text before the first group")
        if line == "none" and state == "open":
            state = "none"
            continue
        cells = _fr_cells(line)
        if cells is None or state in ("none", "closed"):
            if group not in beyond:  # once a group: the lines after it are skipped
                faults.append("group %s holds text or a second table beyond its one table" % group)
                beyond.add(group)
            if state in ("open", "head"):
                state = "none" if state == "open" else "rows"  # the text stands in for the answer or the separator
            continue
        if state == "open":
            state = "head"
            colbad = tuple(cells) != cols
            if colbad:
                faults.append("group %s table columns are not: %s" % (group, " | ".join(cols)))
                if all(c and set(c) <= set("-: ") for c in cells):
                    state = "rows"  # the line is the separator: the column row is missing
                else:
                    width = len(cells)  # the table is read at its own width: one fault, not one per row
            continue
        if state == "head":
            state = "rows"
            if len(cells) == width and all(c and set(c) <= set("-: ") for c in cells):
                continue
            if colbad or set(line) <= set("-:| "):
                faults.append("group %s table has no separator row" % group)
            if set(line) <= set("-:| "):
                continue  # a separator of the wrong shape, not a row
            # else the line is read as a row: under a right column line the missing separator is no fault
        got += 1
        fails += cells[-1] == "FAIL"
        if width != len(cols) and len(cells) == width:
            continue  # rows of a table whose column row is faulty are not read against the group's columns
        if len(cells) != width:
            more = ": a cell holds a pipe: write [pipe]" if len(cells) > width else ""  # a quoted pipe splits the cell
            faults.append("group %s row has %d cells, not %d%s" % (group, len(cells), width, more))
            continue
        ok = ("PASS", "FAIL", "NOT-READ") + (("N/A",) if group == "Earned rules" else ())
        if not all(cells):
            faults.append("group %s row has an empty cell" % group)
        elif cells[0].strip().lower() == "none":  # a group with no rows is the single line `none`
            faults.append("group %s has a `none` row; write the single line `none` instead" % group)
        elif cells[-1] not in ok:
            faults.append("group %s verdict cell is not one of %s" % (group, ", ".join(ok)))
        else:
            rows.append((group, cells))
    if group not in beyond and (state in ("open", "head") or state in ("rows", "closed") and not got):
        faults.append("group %s has no rows and no `none` line" % group)
    if want != len(FR_GROUPS):
        faults.append("only %d of the %d groups are present" % (want, len(FR_GROUPS)))
    if ref == "none" and any(g == "Captures" for g, _ in rows):
        faults.append("capture-evidence-ref is `none` over a Captures row")
    if len(faults) == body and head["verdict"] == "PASS" and fails:
        faults.append("verdict PASS with %d FAIL row(s)" % fails)
    if len(faults) == body and head["verdict"] == "FAIL" and not fails:
        faults.append("verdict FAIL with no FAIL row")
    return head["verdict"], rows, faults, False


FR_RULE_ID = re.compile(r"(?<![A-Za-z])R-[A-Z]+-[A-Z0-9-]+")  # the earned-rules id token


def _fr_rule_ids(root):
    """The rule ids of the lane's `## Earned rules` section (the review-qa checker's grammar), [] when it has none."""
    try:
        with open(os.path.join(root, "CLAUDE.md"), encoding="utf-8-sig") as fh:
            lines = fh.read().splitlines()
    except (OSError, UnicodeDecodeError):
        return []
    start = next((i for i, l in enumerate(lines) if l.startswith("## Earned rules")), None)
    if start is None:
        return []
    ids = []
    for l in lines[start + 1:]:
        if l.startswith("## "):
            break
        m = FR_RULE_ID.search(l) if l.startswith("- ") else None
        if m and m.group(0) not in ids:
            ids.append(m.group(0))
    return ids


FR_SECTION_D = re.compile("## \u00a7D(?:$|[ :-])")  # the scope's section D heading, not `## \u00a7Draft`
FR_DEFERRED = "defer to the architect step"  # scope-grill's marker of a deferred section D item (any case)


def _fr_decision_ids(paths):
    """The decision ids of the records the brief named: the live rulings of a `rulings.md`, the `Q-<n>` first words
    of the `## \u00a7D` section of a `scope.md`, the `DL-`/`CL-` first words of any other file (a ledger); fenced lines are
    skipped and trailing punctuation is not part of an id. Raises ValueError naming a file that is not there, cannot
    be read, or is a rulings list with a malformed line."""
    if not paths:
        return []
    import importlib.util
    try:
        spec = importlib.util.spec_from_file_location(
            "said_covers_read", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "review-qa", "covers-read.py"))
        cr = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cr)  # the review-qa readers of rulings and first words, not a second grammar
    except Exception as e:  # a missing or broken sibling script is an error line, never a traceback
        raise ValueError("cannot load the review-qa record readers: %s" % e)
    ids = []
    for p in paths:
        if not os.path.isfile(p):
            raise ValueError("--decisions names no file: %s" % _fr_clean(p, 120))
        name = os.path.basename(p)
        try:
            if name == "rulings.md":
                entries, broken = cr.GATE.load_rulings([p])
                if broken:
                    raise ValueError("%s has a malformed ruling line (line %s)" % (_fr_clean(p, 120), broken[p][0]))
                new = [e["id"] for _p, _n, e in entries if e["status"] in cr.LIVE_RULING]
            else:
                scope, inside, new, fences = name == "scope.md", name != "scope.md", [], cr.Fences()
                item = None  # [id, text] of the section D item being read: a deferred one is no decision
                pat = r"Q-[0-9]+" if scope else r"(DL|CL)-[A-Za-z0-9]+(?:[._-][A-Za-z0-9]+)*"
                for ln in cr.read_lines(p) + [None]:  # None ends the last item, even inside an unclosed fence
                    if ln is None:
                        if item and FR_DEFERRED not in " ".join(item[1].split()).lower():
                            new.append(item[0])
                        break
                    if fences.skip(ln):
                        continue
                    head = scope and ln.startswith("## ")
                    w = cr.first_word(ln).rstrip(".,;:)") if inside and not head else ""
                    is_id = bool(w) and re.fullmatch(pat, w) is not None
                    if item and (head or is_id):
                        if FR_DEFERRED not in " ".join(item[1].split()).lower():
                            new.append(item[0])
                        item = None
                    if head:
                        inside = bool(FR_SECTION_D.match(ln))
                    elif is_id and scope:
                        item = [w, ln]
                    elif is_id:
                        new.append(w)
                    elif item:
                        item[1] += " " + ln
        except (cr.ReadError, cr.GATE.ConfigError, OSError, UnicodeError) as e:
            raise ValueError("cannot read %s: %s" % (_fr_clean(p, 120), e))
        ids += [i for i in new if i not in ids]
    return ids


def _fr_workdir_ok(root, workdir, feature):
    """True when workdir is the lane's `SAID.working:` dir of this feature."""
    import gate_record
    value = (gate_record.lane_key(root, "working") or "").strip().strip("`'\"")
    if not value:
        return False
    for token in ("<id>", "<feature-id>", "<feature>"):
        value = value.replace(token, feature)
    return os.path.realpath(os.path.join(root, value)) == os.path.realpath(workdir)


def _fr_cite_dirs(root, feature=None):
    """The lane-relative folders a bare file name in a row's cite resolves in: the feature's `SAID.working:` dir and
    the dir of its `SAID.feature-spec:` (direct children; with a feature), and each `SAID.mounts:` folder
    (`<folder>/**`, any depth), each when declared and inside the lane."""
    import gate_record
    import cite_check
    out = []
    for key in ("working", "feature-spec") if feature else ():
        value = (gate_record.lane_key(root, key) or "").strip().strip("`'\"")
        for token in ("<id>", "<feature-id>", "<feature>"):
            value = value.replace(token, feature)
        value = (os.path.dirname(value) if key == "feature-spec" else value).strip("/")
        if value and cite_check.inside(value):
            out.append(value)
    for m in gate_record.mount_list(gate_record.lane_key(root, "mounts")):  # the list read whole; none adds nothing
        m = m.strip("`'\"").strip("/")
        if m and cite_check.inside(m):
            out.append(m + "/**")
    return tuple(out)


def _fr_routes(root, feature=None):
    """The lane's declared routes, lane-relative: the bare-name folders and the docs root. The one inside policy."""
    import gate_record
    import cite_check
    out = [d[:-3] if d.endswith("/**") else d for d in _fr_cite_dirs(root, feature)]
    docs = (gate_record.lane_key(root, "docs-root") or "").strip().strip("`'\"").strip("/")
    if docs and cite_check.inside(docs):
        out.append(docs)
    return tuple(out)


def _fr_names(cell, did):
    """True when the cell holds the id as a whole token, case as written: neither the character before nor the one
    after is an id character (a letter, digit, `-`, `_`, or a `.` with a letter or digit on its other side)."""
    def idc(ch, beyond):
        return ch.isalnum() or ch in "-_" or ch == "." and beyond.isalnum()
    at = cell.find(did)
    while at >= 0 and did:
        end = at + len(did)
        if not (at and idc(cell[at - 1], cell[at - 2:at - 1])) and not (end < len(cell) and idc(cell[end], cell[end + 1:end + 2])):
            return True
        at = cell.find(did, at + 1)
    return False


def _fr_owed(why):
    return 1, ["feature-review: header | FAIL | %s" % why, "feature review owed: %s" % why]


def feature_review_check(text, sha, workdir, verdict_path="", rule_ids=(), decision_ids=(), dirty=lambda: 0, doc=False,
                         cites=None, record_path="", record_cite=None):
    """(rc, lines) of a verdict text with no file or git read of its own: parse it against the head sha, then
    `dirty()` (the count of uncommitted files outside the working dir), a row per rule id and a Covers or Uncovered
    decisions row per decision id; rc 0 and the row lines, or rc 1 and the owed lines. cites(cell text) gives the
    failing cites of a row as [(cite, why)]: any of them on a FAIL row refuses the reply, naming every such cite; a row
    of another status with one is filed NOT-READ, the faults named in its evidence.
    record_cite(evidence) is True when every cite sits in a record (the task log, the spec, a working note) and
    one sits beyond the spec: the FAIL row is then the record class. feature_review_output reads the file, the store and the records, then calls this."""
    import gate_record
    verdict, rows, faults, stopped = _fr_scan(text, sha, workdir, verdict_path, doc, record_path)
    if not faults:
        n = dirty()
        if n:
            return _fr_owed("%d uncommitted file(s) outside the working dir" % n)
    if not stopped:  # the rows after a scan-ending fault are unread: their ids are not counted
        missing = [r for r in rule_ids if not any(_fr_names(c[0], r) for g, c in rows if g == "Earned rules")]
        if missing:
            faults.append("Earned rules has no row for %s; each rule row names its rule id in its first cell"
                          % ", ".join(missing[:8]))
        named = [c[0] for g, c in rows if g in ("Covers", gate_record.FR_DECISIONS)]
        missing = [d for d in decision_ids if not any(_fr_names(n, d) for n in named)]
        if missing:
            faults.append("no row in Covers or %s for %s; each decision row names its decision id in its first cell"
                          % (gate_record.FR_DECISIONS, ", ".join(missing[:8])))
    found = [(g, c, cites(" | ".join(c[:-1]))) for g, c in rows] if cites else []
    bad = [(c, x, why) for _, c, fs in found if c[-1] == "FAIL" for x, why in fs]
    if bad:  # every refused cite of a FAIL row named
        hint = "; name the path in full, or where the missing file is the finding, drop the line number" if any(w == "no such file" for _, _, w in bad) else ""
        faults.append("cite fault: " + "; ".join("%s %s %s" % (_fr_clean(c[0], 40), _fr_clean(x, 200), why) for c, x, why in bad) + hint)
    if faults:
        return _fr_owed("; ".join(faults))
    if cites:
        rows = [(g, _fr_unread(g, c, fs) if fs else c) for g, c, fs in found]
        rows = [(g, _fr_class_row(g, c, bool(c[-1] == "FAIL" and record_cite and record_cite(" | ".join(c[:-1]))))) for g, c in rows]
        verdict = "FAIL" if any(c[-1] == "FAIL" for _, c in rows) else verdict
    out = ["feature-review: verdict | %s | not-read=%d" % (verdict, sum(1 for _, c in rows if c[-1] == "NOT-READ"))]
    for group, _cols in gate_record.fr_groups(doc):
        if not any(g == group for g, _ in rows):
            out.append("feature-review: %s | none" % group)
            continue
        for g, cells in rows:
            if g == group:
                ev = cells[_fr_evidence_at(group, cells)]
                out.append("feature-review: %s | %s | %s | %s" % (group, _fr_clean(cells[0], 40), cells[-1], _fr_clean(ev, 80)))
    return 0, out


def _fr_unread(group, cells, faults):
    """A row of a status other than FAIL whose cites fail: NOT-READ, the faults ahead of its evidence; its id cell kept."""
    out = list(cells)
    at = _fr_evidence_at(group, out)
    out[at] = "cite fault: %s - %s" % ("; ".join("%s %s" % (x, why) for x, why in faults), out[at])
    out[-1] = "NOT-READ"
    return out


def _fr_evidence_at(group, cells):
    import gate_record
    return 1 if group in ("Earned rules", gate_record.FR_EDITORIAL[0]) else len(cells) - 2


def _fr_class_row(group, cells, in_record):
    """A FAIL row whose cites all hold and sit in records carries the record prefix; a typed prefix never counts."""
    import gate_record
    if cells[-1] != "FAIL":
        return cells
    at, out = _fr_evidence_at(group, cells), list(cells)
    if _fr_clean(out[at], 80).strip().lower().startswith("record:"):  # as the row will show it
        out[at] = "evidence " + _fr_clean(out[at], 80).strip()
    if in_record:
        out[at] = gate_record.FR_RECORD + out[at]
    return out


def feature_review_output(root, workdir, feature, decisions=()):
    """(rc, lines) of the feature-review validator: rc 0 and the verdict line then one row line per row; rc 1 and the
    FAIL header row then `feature review owed: <why>`; rc 2 and one `error: <why>` line. The one function behind
    `--feature-review` and `gate_record_row.py --kind feature-review`, so a row is only ever one this produced."""
    import gate_record
    if not workdir or not feature:
        return 2, ["error: --feature-review needs --workdir and a feature id (--feature)"]
    if not FR_ID.fullmatch(feature) or feature.endswith("."):
        return 2, ["error: --feature is a feature id"]
    root = os.path.realpath(os.path.abspath(root))
    if not _fr_workdir_ok(root, workdir, feature):
        return 2, ["error: --workdir is not the lane's SAID.working: dir of %s" % feature]
    try:
        dec = _fr_decision_ids(decisions or ())
    except ValueError as e:
        return 2, ["error: %s" % _fr_clean(str(e), 200)]
    doc = gate_record.fr_doc_lane(root)
    name = ("review-doc-editorial-%s.md" if doc else "review-feature-%s.md") % feature  # the name the reviewer gate reads
    path = os.path.join(workdir, name)
    try:
        ident = gate_record.identity(os.path.realpath(os.path.abspath(root)))
    except gate_record.Error as e:
        return 2, ["error: %s" % e]
    toks = ident.split()
    head_sha = gate_record.git_sha(os.path.realpath(os.path.abspath(root)))
    sha = head_sha or (toks[1] if len(toks) > 1 else "")  # the verdict names a commit, the store does not
    wd = os.path.realpath(workdir)
    try:  # the lane's own paths: a nested lane, a mount repo and the working root are not counted
        n = len(gate_record.git_dirty(root, ["."], wd, set(), gate_record.lane_leave(gate_record.lane_scope(root)))) if head_sha else 0
    except gate_record.Error as e:
        return 2, ["error: %s" % e]
    try:
        real = os.path.realpath(path)
        if not real.startswith(os.path.realpath(workdir) + os.sep):  # a fault the reply did not cause: no re-spawn
            return 2, ["error: the verdict file resolves outside the working dir"]
        if not os.path.isfile(real):
            return 2, ["error: no readable %s in the working dir" % name]
        with open(real, "rb") as fh:
            raw = fh.read(FR_FILE_CAP + 1)
        if len(raw) > FR_FILE_CAP:
            return _fr_owed("the verdict file is too large (over %d bytes)" % FR_FILE_CAP)
        text = raw.decode("utf-8")
    except (OSError, UnicodeError):
        return 2, ["error: no readable %s in the working dir" % name]
    if n:
        return 2, ["error: %d uncommitted file(s) outside the working dir" % n]
    said = re.match(r"target-sha:[ \t]*([0-9a-f]{40})[ \t\r]*$", (text.split("\n") + ["", ""])[1])
    if head_sha and said and said.group(1) != head_sha and subprocess.run(
            ["git", "-C", root, "merge-base", "--is-ancestor", said.group(1), head_sha], capture_output=True).returncode == 0:
        return 2, ["error: HEAD moved after the brief: target-sha %s is behind HEAD %s; prepare the read again"
                   % (said.group(1), head_sha)]
    try:
        import cite_check  # the one cite check, shared with the scope chain
        dirs = _fr_cite_dirs(root, feature)  # a bare file name resolves in the feature's own folders
        routes = _fr_routes(root, feature)
        recs = {}  # the feature's task log and spec, by realpath
        for key in ("task-log", "feature-spec"):
            rec = (gate_record.lane_key(root, key) or "").strip().strip("`'\"").replace("<id>", feature)
            if rec:
                recs[os.path.realpath(os.path.join(root, rec))] = key
        sources = {os.path.realpath(p) for p in decisions or ()}

        def a_note(real):  # a top-level working file that is no decision source and no gate output
            base = os.path.basename(real)
            return (os.path.dirname(real) == wd and real not in sources and base not in ("rulings.md", "scope.md")
                    and not base.startswith(("gate-", "review-", "accept-", "covers-", "QA-", "doc-gate-")))

        def in_log(ev):  # every cite in a record, and one beyond the spec: a spec line alone is a requirement's source
            hits = cite_check.text_paths(root, ev, dirs, strict=True)
            reals = [os.path.realpath(os.path.join(root, h)) for h in hits if h]
            if not hits or len(reals) < len(hits) or not all(r in recs or a_note(r) for r in reals):
                return False
            return any(recs.get(r) == "task-log" or a_note(r) for r in reals)

        return feature_review_check(text, sha, workdir, path, _fr_rule_ids(root), dec, lambda: 0, doc,
                                    lambda cell: cite_check.text_faults(root, cell, dirs, routes, strict=True),  # a reader row holds no host and port
                                    os.path.join(workdir, "gate-%s.md" % feature), in_log)
    except gate_record.Error as e:
        return 2, ["error: %s" % e]


def run_feature_review(a):
    """CLI dispatch for --feature-review: print what feature_review_output returns; exit 0, 1 (owed) or 2 (error)."""
    rc, lines = feature_review_output(a.root, a.workdir, a.feature, a.decisions or ())
    for ln in lines:
        print(ln)
    return rc


def main():
    ap = argparse.ArgumentParser(description="Deterministic SAID feature-state analyzer (read-only).")
    ap.add_argument("feature", nargs="?", help="feature-id for a deep-dive (else: roster)")
    ap.add_argument("--root", default=".")
    ap.add_argument("--docs-dir", default="docs/features")
    ap.add_argument("--working-dir", default="docs/working")
    ap.add_argument("--prefixes", help="issued id-prefixes, comma-sep (e.g. APP,INIT). Default: inferred.")
    ap.add_argument("--legacy-prefixes", help="prefixes to collapse, comma-sep (e.g. FEAT,CONF).")
    ap.add_argument("--today", default=date.today().isoformat(), help="YYYY-MM-DD (default: real today)")
    ap.add_argument("--stale-days", type=int, default=None, help="single idle threshold override")
    ap.add_argument("--stale", action="store_true", help="roster: attention items only")
    ap.add_argument("--json", action="store_true", help="emit structured JSON instead of text")
    ap.add_argument("--lane", action="append", default=[], metavar="NAME[:k=v;...]",
                    help="declare a lane (repeatable); keys: root,docs,working,prefixes,legacy. "
                         "A relative root is taken from --root. Omit entirely for one default lane.")
    ap.add_argument("--project", help="header label (default: --root basename)")
    ap.add_argument("--registry", action="store_true",
                    help="print the lane registry declared in <root>/CLAUDE.md: one TOKEN:root=<root> line per "
                         "row (the form --lane takes), then `count: <N>`; a refused line prints `refused: ...` and exits 2")
    ap.add_argument("--resolve", action="store_true",
                    help="with --registry: print each row as the full --lane argument, TOKEN:root=<root>;docs=<dir>;"
                         "working=<dir>, the dirs read from that lane's own lane block; a row that cannot be "
                         "resolved prints one `skipped: ...` line; `count: <N>` counts the resolved rows")
    ap.add_argument("--reviewer-gate", action="store_true",
                    help="L2: validate the declared reviewer set for a working dir (exit-coded gate)")
    ap.add_argument("--feature-review", action="store_true",
                    help="validate the feature-reviewer's verdict file in --workdir for --feature and print its rows")
    ap.add_argument("--workdir", help="reviewer-gate / feature-review: feature working dir holding verdict artifacts")
    ap.add_argument("--feature", dest="feature_opt", help="feature-review: the feature id")
    ap.add_argument("--decisions", nargs="+", help="feature-review: the decision records the reviewer was briefed with")
    ap.add_argument("--surface", help="reviewer-gate: the lane's SAID.surface medium")
    ap.add_argument("--reviewers", help="reviewer-gate: comma-sep declared reviewer ids")
    ap.add_argument("--checkers-dir", default=None,  # None -> resolve via lane SAID.checkers-dir -> the plugin's own agents/ (no lane-root/agents fallback)
                    help="reviewer-gate: dir of agent-form Checker files (default: lane SAID.checkers-dir: -> the plugin's own plugins/said/agents)")
    ap.add_argument("--recipe-rules", help="reviewer-gate: a docs/ux rules file to also scan for recipe-form Checkers")
    a = ap.parse_args()

    if a.resolve and not a.registry:
        ap.error("--resolve is a form of --registry")
    if a.registry:  # the lane registry's rows, for any caller that needs a lane's root
        sys.exit(run_registry(a))
    if a.feature_review:
        a.feature = a.feature_opt or a.feature
        sys.exit(run_feature_review(a))
    if a.reviewer_gate:  # L2 exit-coded enforcement gate
        sys.exit(run_reviewer_gate(a))

    project = a.project or os.path.basename(os.path.abspath(a.root))
    defaults = {"name": project, "root": a.root, "docs_dir": a.docs_dir, "work_dir": a.working_dir,
                "prefixes": [p.strip() for p in a.prefixes.split(",")] if a.prefixes else None,
                "legacy_prefixes": [p.strip() for p in a.legacy_prefixes.split(",")] if a.legacy_prefixes else None}
    lanes = [parse_lane_arg(x, defaults) for x in a.lane] if a.lane else [defaults]
    data = analyze(lanes, a.today, a.stale_days, project, stamps=bool(a.lane))

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if a.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    elif a.feature:
        print(render_feature(data, a.feature))
    else:
        print(render_roster(data, stale_only=a.stale))


if __name__ == "__main__":
    main()
