#!/usr/bin/env python3
"""said_status.py — deterministic SAID feature-state analyzer.

Read-only. Reconstructs every feature's position in the SAID phase chain
(Scope -> Architect -> Implement -> Delivery -> Closed) by INSPECTING on-disk
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
STATUS_RE = re.compile(r"^\*\*Status:\*\*\s*(Done|Todo|Canceled|Cancelled|Backlog)\b", re.I)
DATE_RE = re.compile(r"\((\d{4}-\d{2}-\d{2})\)")
HEADER_RE = re.compile(r"^##\s+([A-Z]+-\d+(?:-[A-Za-z0-9]+)*)\s*[:：]?\s*(.*?)\s*$")
FOOTER_RE = re.compile(r"^##\s+Debrief close\b", re.I)
IDDIR_RE = re.compile(r"^([A-Z]+)-(\d+)$")

# attention-first ordering; staleness thresholds (days idle) per phase
PHASE_RANK = {"Implement": 0, "Delivery": 1, "Architect": 2, "Scope": 3, "Closed": 4}
STALE_DEFAULT = {"Implement": 7, "Delivery": 7, "Architect": 14, "Scope": 14}

GLYPH = {"done": "█", "empty": "░", "none": "·",
         "ok": "✓", "pending": "○", "warn": "⚠", "block": "⛔"}


def sh(args):
    """Run a command, return stdout stripped, or None on any failure."""
    try:
        out = subprocess.run(args, capture_output=True, text=True, timeout=15)
        return out.stdout.strip() if out.returncode == 0 else None
    except Exception:
        return None


def feature_prefix(fid):
    m = IDDIR_RE.match(fid)
    return m.group(1) if m else fid.split("-")[0]


SPEC_H1_RE = re.compile(r"^#\s+([A-Z]+-\d+(?:-[A-Za-z0-9]+)*)\s*[:：]\s*(.+?)\s*$")


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
                if status == "Cancelled":
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
        return "Delivery", None
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
    if phase == "Delivery":
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
    # Pathspecs must be absolute: with a relative --root, `git -C <root> … -- <root>/x`
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
            extra += "  · %d canceled" % f["counts"]["Canceled"]
        return extra
    bits = []
    if f["sub"]:
        label = f["sub"]
        if not f["stale"] and f["idle_days"] is not None:
            label += " · %s" % ("active" if f["idle_days"] == 0 else "%dd" % f["idle_days"])
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
        tail.append(prefix + "Next: " + " · ".join(nexts))
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
    lines = ["SAID status · %s · %d lane%s · %s" % (
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
    seq = ["Scope", "Architect", "Implement", "Delivery", "Closed"]
    cur = f["phase"]
    ci = seq.index(cur) if cur in seq else -1
    pipe = []
    for i, p in enumerate(seq):
        pipe.append("%s %s" % (p, GLYPH["ok"] if i < ci else ("●" if i == ci else GLYPH["pending"])))
    out = (["lane: %s" % lane_label] if lane_label else []) + ["%s — %s" % (f["id"], cur), "", "  " + " → ".join(pipe)]
    g = f["gates"]
    gline = " · ".join([
        "review-qa " + (GLYPH["ok"] if g["qa"] else GLYPH["pending"]),
        "review-ux " + (GLYPH["ok"] if g["ux"] else GLYPH["pending"]),
        "accept " + (GLYPH["ok"] if g["accept"] else GLYPH["pending"]),
        "debrief " + (GLYPH["ok"] if f["debrief_closed"] else GLYPH["pending"]),
    ])
    out += ["  gates: " + gline, ""]
    c = f["counts"]
    out.append("Tasks   Done %d · Todo %d · Canceled %d      %s  %s" % (
        c["Done"], c["Todo"], c["Canceled"], bar(f["done"], f["denominator"]),
        ("%d%%" % round(100 * f["done"] / f["denominator"])) if f["denominator"] else "—"))
    for it in f["todo_items"]:
        out.append("  %s · %s" % (it["id"], it["title"] or ""))
    dl = "Dates   started %s · last activity %s · age %s · %s" % (
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
    out.append("Files   " + " · ".join([x for x in (p["spec"], p["tasks"], p["scope"]) if x]))
    return "\n".join(out)


def render_feature(data, fid):
    q = fid.lower()
    matches = [x for x in data["features"]
               if x["id"].lower() == q or x["id"].lower().startswith(q + "-")]
    if not matches:
        return "no such feature in registry: %s" % fid
    multi = data["lane_count"] > 1
    return "\n\n".join(_feature_block(f, f["lane"] if multi else None) for f in matches)


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
    a = ap.parse_args()

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
