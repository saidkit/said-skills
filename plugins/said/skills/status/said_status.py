#!/usr/bin/env python3
"""said_status.py — deterministic SAID feature-state analyzer.

Read-only. Reconstructs every feature's position in the SAID phase chain
(Scope -> Architect -> Implement -> Deliver -> Closed) by INSPECTING on-disk
artifacts, and emits either JSON (a stable data interface) or a rendered
terminal roster / single-feature deep-dive. Stores nothing.

Backs the /said-status (-> plugin /said:status) skill; see SKILL.md for the
prose contract this implements. Stdlib only, Python 3.8+.

Agnostic by construction: paths, issued id-prefixes, and lanes come from flags
(the skill resolves them declaration-first from CLAUDE.md and passes them);
sensible conventional defaults apply when a flag is omitted.
"""

import argparse
import glob
import json
import os
import re
import subprocess
import sys
from datetime import date

# --- grammar (the SAID task-log shape) --------------------------------------
STATUS_RE = re.compile(r"^\s*(?:[-*+]\s+)?\*\*Status:\*\*\s*(Done|Todo|Canceled|Cancelled|Superseded|Backlog)\b", re.I)
DATE_RE = re.compile(r"\((\d{4}-\d{2}-\d{2})\)")
HEADER_RE = re.compile(r"^##\s+([A-Z]+-?\d+(?:-[A-Za-z0-9]+)+)\s*[:：]?\s*(.*?)\s*$")
FOOTER_RE = re.compile(r"^##\s+Debrief close\b", re.I)
IDDIR_RE = re.compile(r"^([A-Z]+)-(\d+)$")

# attention-first ordering; staleness thresholds (days idle) per phase
PHASE_RANK = {"Implement": 0, "Deliver": 1, "Architect": 2, "Scope": 3, "Closed": 4}
STALE_DEFAULT = {"Implement": 7, "Deliver": 7, "Architect": 14, "Scope": 14}

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
    for path in paths:
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


_SECTION_RE = re.compile(r"^###+\s+(.+?)\s*$")


def feature_tasks(paths):
    """All tasks for one feature in file order (on-demand, not part of analyze()).

    Returns a list of {id, title, status, date, sections} where sections maps a
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
                cur = {"id": h.group(1), "title": h.group(2).strip(), "status": None, "date": None, "sections": {}}
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


def gate_ticks(workdir):
    """Presence of the working-dir gate artifacts."""
    def has(pat):
        return bool(glob.glob(os.path.join(workdir, pat)))
    return {"qa": has("review-qa*.md"), "ux": has("review-ux*.md"),
            "accept": has("accept*.md"), "debrief_started": os.path.isfile(os.path.join(workdir, "debrief.md"))}


def classify(has_spec, has_tasks, todo, footer, has_scope, dir_has_content):
    """Ordered phase probe — first match wins. Never keys on todo==0 alone."""
    if footer:
        return "Closed", None
    if has_tasks and todo == 0:
        return "Deliver", None
    if has_tasks and todo > 0:
        return "Implement", None
    if has_scope or has_spec:
        return "Architect", ("spec, no tasks" if has_spec else "scope.md, no spec")
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


def next_action(fid, phase, workdir, gates, sub):
    workdir = os.path.normpath(workdir)
    if phase == "Scope":
        return "/said:scope-refine %s" % workdir if sub == "scope pending" else "/said:scope-grill %s" % fid
    if phase == "Architect":
        return "/said:architect %s" % os.path.join(workdir, "scope.md")
    if phase == "Implement":
        return "/said:impl %s" % fid
    if phase == "Deliver":
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


def _sortkey(f):
    rank = PHASE_RANK.get(f["phase"], 9)
    if f["phase"] == "Closed":  # most-recently-closed first
        d = f["last_activity"] or "0000-00-00"
        return (rank, tuple(-int(x) for x in d.split("-")), f.get("lane", ""), f["id"])
    return (rank, (-(f["idle_days"] or 0),), f.get("lane", ""), f["id"])  # most-stale first


def analyze_lane(name, root, docs_dir, work_dir, prefixes, legacy_prefixes, today, stale_days):
    feats_dir = os.path.join(root, docs_dir)
    work_root = os.path.join(root, work_dir)
    git_available = sh(["git", "-C", root, "rev-parse", "--is-inside-work-tree"]) == "true"

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

    # --- per-feature reconstruction ---------------------------------------
    out = []
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
        phase, sub = classify(bool(specs), bool(tasks), c["Todo"], t["footer"], scope, dir_content)
        gates = gate_ticks(workdir) if os.path.isdir(workdir) else {"qa": False, "ux": False, "accept": False, "debrief_started": False}

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
        threshold = stale_days if stale_days is not None else STALE_DEFAULT.get(phase)
        stale = bool(phase != "Closed" and idle is not None and threshold is not None and idle > threshold)

        fname = feature_name(specs[0] if specs else None)
        fshort = feature_short_name(specs[0] if specs else None, fid)
        out.append({
            "lane": name, "id": fid, "phase": phase, "sub": sub,
            # the feature's human name (spec H1) and the filename slug, if any;
            # display_name prefers the short slug, else the full name, else None.
            "name": fname, "short_name": fshort, "display_name": fshort or fname,
            "counts": c, "done": c["Done"], "todo": c["Todo"],
            "denominator": c["Done"] + c["Todo"],
            "todo_items": t["todo_items"],
            "gates": gates, "debrief_closed": t["footer"],
            "started": started, "last_activity": last_activity,
            "age_days": age, "idle_days": idle, "stale": stale, "threshold": threshold,
            "next": next_action(fid, phase, relpath(workdir, root), gates, sub),
            "integrity": t["integrity"],
            # `paths` stay absolute — they are read from. `paths_rel` is the display form.
            "paths": {"spec": os.path.normpath(specs[0]) if specs else None,
                      "tasks": os.path.normpath(tasks[0]) if tasks else None,
                      "scope": os.path.normpath(os.path.join(work_root, fid, "scope.md")) if scope else None},
            "paths_rel": {"spec": relpath(specs[0], root) if specs else None,
                          "tasks": relpath(tasks[0], root) if tasks else None,
                          "scope": relpath(os.path.join(work_root, fid, "scope.md"), root) if scope else None},
        })

    out.sort(key=_sortkey)
    return {
        "name": name, "root": os.path.normpath(root),
        "docs_dir": docs_dir, "working_dir": work_dir,
        "git_available": git_available, "legacy_prefixes": sorted(legacy_seen),
        "features": out,
    }


def parse_lane_arg(arg, defaults):
    """'NAME' or 'NAME:key=val;key=val' — keys: root, docs, working, prefixes, legacy."""
    name, _, rest = arg.partition(":")
    spec = dict(defaults)
    spec["name"] = name.strip() or defaults.get("name")
    for pair in rest.split(";"):
        if "=" not in pair:
            continue
        k, _, v = pair.partition("=")
        k, v = k.strip(), v.strip()
        if k == "root":
            spec["root"] = v
        elif k == "docs":
            spec["docs_dir"] = v
        elif k == "working":
            spec["work_dir"] = v
        elif k == "prefixes":
            spec["prefixes"] = [x.strip() for x in v.split(",") if x.strip()]
        elif k == "legacy":
            spec["legacy_prefixes"] = [x.strip() for x in v.split(",") if x.strip()]
    return spec


def analyze(lanes, today, stale_days, project):
    results = [analyze_lane(L["name"], L["root"], L["docs_dir"], L["work_dir"],
                            L.get("prefixes"), L.get("legacy_prefixes"), today, stale_days)
               for L in lanes]
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
        rows = shown(lr)
        for f in rows:
            lines.append(_row(f, idw, phw))
        if stale_only and not rows:
            lines.append("(nothing stale)")
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
            if stale_only and not rows:  # a clean lane is not an attention item
                continue
            any_shown = True
            hint = lr["root"] if lr["root"] not in (".", "") else lr["docs_dir"]
            lines.append("lane: %s  (%s)" % (lr["name"], hint))
            for f in rows:
                lines.append("  " + _row(f, idw, phw))
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
    seq = ["Scope", "Architect", "Implement", "Deliver", "Closed"]
    cur = f["phase"]
    ci = seq.index(cur) if cur in seq else -1
    pipe = []
    for i, p in enumerate(seq):
        pipe.append("%s %s" % (p, GLYPH["ok"] if i < ci else ("●" if i == ci else GLYPH["pending"])))
    out = (["lane: %s" % lane_label] if lane_label else []) + ["%s — %s" % (f["id"], cur), "", "  " + " -> ".join(pipe)]
    g = f["gates"]
    gline = ", ".join([
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
    dl = "Dates   started %s, last activity %s, age %s, %s" % (
        f["started"] or "—", f["last_activity"] or "—",
        ("%dd" % f["age_days"]) if f["age_days"] is not None else "—",
        idle_phrase(f["idle_days"]) or "idle —")
    if f["stale"]:
        dl += " %s (> %dd)" % (GLYPH["warn"], f["threshold"])
    out += ["", dl]
    if f["integrity"]:
        out.append("Note    ! " + f["integrity"])
    if f["next"]:
        out.append("Next    %s" % f["next"])
    p = f.get("paths_rel") or f["paths"]
    out.append("Files   " + ", ".join([x for x in (p["spec"], p["tasks"], p["scope"]) if x]))
    return "\n".join(out)


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


def validate_reviewer(workdir, cid, meta, head_sha, root=".", surface=None):
    """Validate one expected reviewer's L1 verdict. Returns (ok, reason)."""
    if meta is None:  # declared reviewer id resolves to no Checker — nominal; a verdict can never redeem it
        return False, "reviewer %r does not resolve to a Checker (nominal — no said-checker match)" % cid
    hits = sorted(glob.glob(os.path.join(workdir, "review-%s-*.md" % glob.escape(cid))))
    if not hits:
        return False, "missing verdict artifact (review-%s-*.md)" % cid
    hdr = parse_verdict_header(hits[-1])
    if hdr.get("verdict", "").upper() != "PASS":
        return False, "verdict != PASS (%s)" % (hdr.get("verdict") or "absent")
    cap = hdr.get("capture-evidence-ref")
    if not cap:
        return False, "no capture-evidence-ref"
    if cap == "recomputed":  # `recomputed`: a sentinel, not a file — valid only where the recompute below actually re-derives the verdict
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
        rc = subprocess.run(cmd, shell=True, cwd=root, capture_output=True, env=env).returncode
        if rc != 0:
            return False, "recompute failed (exit %d)" % rc
    return True, "PASS"


def _governs_surface(meta, surface):
    """Whether a resolved Checker governs `surface` (ADR-SAID-S06 section 3 self-selection). A Checker with
    no said-governs, no `surface=` clause (it governs by shape, not medium), or `surface=any` governs
    any surface (backward compat); otherwise it governs only the surface(s) its said-governs names."""
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
    for cid in reviewers:
        meta = checker_index.get(cid)
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
        # said-governs routing (ADR-SAID-S06 section 3): a RESOLVED Checker that does not govern this surface
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
                         "Omit entirely for one default lane.")
    ap.add_argument("--project", help="header label (default: --root basename)")
    ap.add_argument("--reviewer-gate", action="store_true",
                    help="L2: validate the declared reviewer set for a working dir (exit-coded gate)")
    ap.add_argument("--workdir", help="reviewer-gate: feature working dir holding verdict artifacts")
    ap.add_argument("--surface", help="reviewer-gate: the lane's SAID.surface medium")
    ap.add_argument("--reviewers", help="reviewer-gate: comma-sep declared reviewer ids")
    ap.add_argument("--checkers-dir", default=None,  # None -> resolve via lane SAID.checkers-dir -> the plugin's own agents/ (no lane-root/agents fallback)
                    help="reviewer-gate: dir of agent-form Checker files (default: lane SAID.checkers-dir: -> the plugin's own plugins/said/agents)")
    ap.add_argument("--recipe-rules", help="reviewer-gate: a docs/ux rules file to also scan for recipe-form Checkers")
    a = ap.parse_args()

    if a.reviewer_gate:  # L2 exit-coded enforcement gate
        sys.exit(run_reviewer_gate(a))

    project = a.project or os.path.basename(os.path.abspath(a.root))
    defaults = {"name": project, "root": a.root, "docs_dir": a.docs_dir, "work_dir": a.working_dir,
                "prefixes": [p.strip() for p in a.prefixes.split(",")] if a.prefixes else None,
                "legacy_prefixes": [p.strip() for p in a.legacy_prefixes.split(",")] if a.legacy_prefixes else None}
    lanes = [parse_lane_arg(x, defaults) for x in a.lane] if a.lane else [defaults]
    data = analyze(lanes, a.today, a.stale_days, project)

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
