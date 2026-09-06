#!/usr/bin/env python3
"""serve.py — said:board local web dashboard.

Read-only, loopback-only, stdlib-only server. Reuses the sibling said-status
analyzer's deterministic core and serves it as a live local page. The HTML shell
loads **htmx** and **daisyUI** from a CDN (no pip, no node_modules, no build);
htmx drives the auto-refresh + deep-dive, daisyUI provides components + themes.
See REQUIREMENTS.md for the contract.

**Optional integration (opt-in, `--connect <url>`).** Pointed at a local companion
app, the board additionally emits an embed — one stylesheet link, one script tag,
and empty mount points that the app's bundle hydrates — reads comment counts off a
local cache file, serves a Backlog view of the local todo file, and accepts two
local-file writes (`POST /connect`, `POST /todo`). Without the flag none of that
exists: no script tag, no mount points, no extra routes, no behaviour change.

The rule that shapes the whole integration: **the board writes local files; the app
talks to the remote.** The board holds no credential, makes no network call of its
own, and never proxies anything.
"""

import argparse
import hmac
import html
import json
import os
import re
import secrets
import signal
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

# --- reuse the analyzer skill (one deterministic core) — resolve by role, not path ----------
# sibling is named `status` in the said plugin, `said-status` in the project-local prototype.
_BASE = os.path.dirname(os.path.abspath(__file__))
for _sib in ("status", "said-status"):
    _p = os.path.normpath(os.path.join(_BASE, "..", _sib))
    if os.path.isfile(os.path.join(_p, "said_status.py")):
        sys.path.insert(0, _p)
        break
try:
    import said_status
except Exception as exc:  # pragma: no cover
    sys.stderr.write("said-board: cannot import the analyzer skill (status/said-status) beside %s (%s)\n" % (_BASE, exc))
    sys.exit(2)

ID_RE = re.compile(r"^[A-Za-z]+-\d+(?:-[A-Za-z0-9]+)*$")
CFG = {}
PHASE_SEQ = ["Scope", "Architect", "Implement", "Deliver", "Closed"]

# --- CDN (pinned) ------------------------------------------------------------
HTMX = "https://unpkg.com/htmx.org@2.0.3"
DAISY = "https://cdn.jsdelivr.net/npm/daisyui@4.12.14/dist/full.min.css"
FONTS = ("https://fonts.googleapis.com/css2?family=Inter+Tight:wght@400;500;600;700;800"
         "&family=JetBrains+Mono:wght@400;500;600&display=swap")

HOME = "https://saidkit.dev"  # the lockup links here (new tab — never navigate the open board away)

# SAID mark — quartered diamond on a 16u grid, two cobalt triangles (brand book §03/§04).
# Drawn as-is: never rotated, recolored, outlined, or enclosed.
MARK = ('<svg class="mark" viewBox="0 0 16 16" width="%d" height="%d" fill="none" role="img" aria-label="SAID">'
        '<path d="M8 2 L14 8 L8 8 Z" fill="currentColor"/><path d="M2 8 L8 14 L8 8 Z" fill="currentColor"/></svg>')
FAVICON = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16">'
           '<path d="M8 2 L14 8 L8 8 Z" fill="#435AF6"/><path d="M2 8 L8 14 L8 8 Z" fill="#435AF6"/></svg>')

# Phase colour comes from the brand ramp in board.css (neutral → cobalt → green),
# never from daisyUI's semantic palette — the brand allows one accent, no new hues.


def esc(s):
    return html.escape("" if s is None else str(s))


def _md_inline(s):  # s is already html-escaped; render inline `code`/**bold**, same-line + bounded
    s = re.sub(r"`([^`\n]{1,44})`", r'<code class="ic">\1</code>', s)
    return re.sub(r"\*\*([^*\n]{1,80})\*\*", r"<strong>\1</strong>", s)


# --- optional integration with a LOCAL companion app (opt-in) ----------------
# Everything below is inert unless the operator passed `--connect <url>` (or left
# a config file behind an earlier connect). `connected()` gates every emitter, so
# an unconfigured install renders and routes exactly as it always has.
BOARD_DIR = "docs/.board"            # ONE machine-local root: config + cache. Gitignore it.
CONFIG_JSON = "config.json"          # {"app": "http://localhost:<port>", "todo": "docs/todo.md"}
CACHE_INDEX = ("cache", "index.json")  # badge counts, written by whatever syncs with the app
TODO_DEFAULT = "docs/todo.md"        # the local backlog file (--todo-file overrides)
CACHE_MAX_AGE_DAYS = 30              # older than this: the cache is stale → render nothing
MAX_BODY = 8192                      # a local write is one line of text, never a payload
MAX_TODO_LEN = 200
LOOPBACK = ("localhost", "127.0.0.1", "::1")
CSRF_META = "said-board-csrf"        # the token is minted into the page…
CSRF_HEADER = "X-Said-Board-Csrf"    # …and required back on every write
WIDGET_HEADER = "X-Said-Board"       # a custom header no cross-site form post can set


def connected():
    return bool(CFG.get("app"))


def normalize_origin(url):
    """A local app origin — http(s) + a LOOPBACK host + optional port. None for anything else.

    The board is a loopback tool: it may point at another local process and at
    nothing else. A remote URL here would be the board acquiring a network role.
    """
    try:
        p = urlparse((url or "").strip())
    except ValueError:
        return None
    if p.scheme not in ("http", "https") or not p.netloc or "@" in p.netloc:
        return None
    try:
        host = (p.hostname or "").lower()
    except ValueError:
        return None
    if host not in LOOPBACK:
        return None
    return "%s://%s" % (p.scheme, p.netloc.lower())


def own_origins(port):
    """Every spelling of THIS server's own origin. A write is accepted from no other.

    Comparing against a fixed set (not the request's Host header) is what makes the
    check survive DNS rebinding: a page on attacker.example that resolves to loopback
    still sends its own Origin, which is not in this set.
    """
    return set("http://%s:%d" % ("[%s]" % h if ":" in h else h, port) for h in LOOPBACK)


# --- badge counts: off disk, never from the network --------------------------
_cidx = {"key": None, "data": {}}


def _cache_fresh(stamp):
    if not stamp:
        return True                     # no claim of freshness → the file is taken at face value
    try:
        t = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return True
    if t.tzinfo is not None:
        t = t.astimezone().replace(tzinfo=None)
    return (datetime.now() - t).days <= CACHE_MAX_AGE_DAYS


def cache_index():
    """Comment counts read from docs/.board/cache/index.json. Never fetches, never raises.

    Shape (a bare integer is accepted as a comment count):

        {"generated": "<iso-8601>",
         "features": {"PROJ-01": {"comments": 3, "unread": 1,
                                  "tasks": {"PROJ-01-07": {"comments": 2, "unread": 0}}}}}

    Missing, unreadable, malformed or stale all read the same way: no data, and the
    board renders no chip at all rather than an error.
    """
    path = os.path.join(CFG.get("root", "."), BOARD_DIR, *CACHE_INDEX)
    try:
        st = os.stat(path)
        key = (st.st_mtime, st.st_size)
    except OSError:
        _cidx["key"], _cidx["data"] = None, {}
        return {}
    if _cidx["key"] == key:
        return _cidx["data"]
    data = {}
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
        if isinstance(raw, dict) and _cache_fresh(raw.get("generated")):
            feats = raw.get("features")
            data = feats if isinstance(feats, dict) else {}
    except (OSError, ValueError):
        data = {}
    _cidx["key"], _cidx["data"] = key, data
    return data


def _int(v):
    return max(v, 0) if isinstance(v, int) and not isinstance(v, bool) else 0


def _pair(entry):
    if isinstance(entry, dict):
        return (_int(entry.get("comments")), _int(entry.get("unread")))
    return (_int(entry), 0)


def counts(fid, tid=None):
    """(comments, unread) for a feature, or for one of its tasks. (0, 0) when unknown."""
    f = cache_index().get(fid)
    if tid is None:
        return _pair(f)
    tasks = f.get("tasks") if isinstance(f, dict) else None
    return _pair(tasks.get(tid)) if isinstance(tasks, dict) else (0, 0)


def chip(fid, tid=None):
    """The muted mono comment chip — omitted ENTIRELY at zero (a task nobody discussed gains no noise)."""
    if not connected():
        return ""
    n, unread = counts(fid, tid)
    if not n:
        return ""
    lbl = "%d comment%s" % (n, "" if n == 1 else "s")
    if unread:
        lbl += " · %d unread" % unread
    return '<span class="cchip%s" title="%s">\U0001F4AC %d</span>' % (
        " unread" if unread else "", esc(lbl), n)


def mount(kind, **attrs):
    """An embed mount point. Empty by contract: the app's bundle finds it and hydrates it."""
    if not connected():
        return ""
    extra = "".join(' data-%s="%s"' % (k.replace("_", "-"), esc(v)) for k, v in attrs.items() if v)
    return '<div data-said-widget="%s"%s></div>' % (esc(kind), extra)


# --- the two local-file writes ------------------------------------------------
# Both targets are resolved from the server's own configuration; a request never
# supplies a path, so there is nothing to traverse.
def read_config(root):
    try:
        with open(os.path.join(root, BOARD_DIR, CONFIG_JSON), encoding="utf-8") as fh:
            cfg = json.load(fh)
        return cfg if isinstance(cfg, dict) else {}
    except (OSError, ValueError):
        return {}


def write_config(update):
    """Merge into docs/.board/config.json — machine-local, gitignored, deletable at any time."""
    root = CFG.get("root", ".")
    cfg = read_config(root)
    cfg.update(update)
    d = os.path.join(root, BOARD_DIR)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, CONFIG_JSON), "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    return cfg


def append_todo(text):
    """Append one checklist line to the local todo file. Returns the line written."""
    line = " ".join(str(text).split())[:MAX_TODO_LEN]
    item = "- [ ] %s (%s)" % (line, date.today().isoformat())
    path = CFG["todo_path"]
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    exists = os.path.isfile(path)
    tail = "\n"
    if exists and os.path.getsize(path):
        with open(path, "rb") as fh:      # last byte only — the file may be long
            fh.seek(-1, os.SEEK_END)
            tail = fh.read(1).decode("utf-8", "ignore")
    with open(path, "a", encoding="utf-8") as fh:
        if not exists:
            fh.write("# Backlog\n\n")
        elif tail != "\n":
            fh.write("\n")
        fh.write(item + "\n")
    return item


# --- single-flight guard: derive on refresh, cache until the next one --------
# Read-only board: analyze() (a git-per-feature call, seconds on a large repo)
# runs only on an explicit refresh — a full page load or the header button, both
# fresh=True — and the result is cached until the next such refresh. Non-fresh
# requests (deep-dive clicks, lane switches) always reuse the cached derive, so
# navigating the board never re-runs git. Single-flight collapses the page-load
# fan-in (page + roster + kanban) onto one run.
_cache = {}                       # stale_days -> (monotonic_ts, data)
_cache_lock = threading.Lock()
_flight = {}                      # stale_days -> Lock (one derive per key in flight)


def _analyze(stale_days):
    return said_status.analyze(CFG["lanes"], CFG.get("today") or date.today().isoformat(), stale_days, CFG["project"])


def get_data(stale_days=None, fresh=False):
    key = stale_days
    started = time.monotonic()
    if not fresh:
        hit = _cache.get(key)
        if hit:                   # cache until an explicit refresh — no TTL expiry
            return hit[1]
    with _cache_lock:
        flight = _flight.setdefault(key, threading.Lock())
    with flight:                  # single-flight: one derive per key at a time
        hit = _cache.get(key)     # a concurrent request may have refreshed meanwhile
        if hit and (not fresh or hit[0] >= started):
            return hit[1]         # non-fresh reuses any cached value; fresh only one produced after it began
        data = _analyze(stale_days)
        _cache[key] = (time.monotonic(), data)
        return data


def _pct(f):
    d = f["denominator"]
    return round(100 * f["done"] / d) if d else 0


def _pill(phase):
    return '<span class="ph" data-phase="%s">%s</span>' % (esc(phase), esc(phase))


def _bar(pct, empty=False):
    if empty:
        return '<progress class="progress prog empty" value="0" max="100"></progress>'
    return '<progress class="progress progress-success prog" value="%d" max="100"></progress>' % pct


def _flag_html(f):
    if f["phase"] == "Closed":
        return '<span class="muted">%d canceled</span>' % f["counts"]["Canceled"] if f["counts"]["Canceled"] else '<span class="shipped">shipped</span>'
    bits = []
    if f["sub"]:
        idle = "" if (f["stale"] or f["idle_days"] is None) else \
            (" · active" if f["idle_days"] == 0 else " · %dd" % f["idle_days"])
        lbl = f["sub"] + idle
        bits.append('<span class="muted">%s</span>' % esc(lbl))
    if f["stale"]:
        bits.append('<span class="warn">⚠ %dd idle</span>' % f["idle_days"])
    if f.get("integrity"):  # compact in the row (full detail on hover) — long text overflowed the row
        bits.append('<span class="warn" title="%s">⚠ tasks≠status</span>' % esc(f["integrity"]))
    return " ".join(bits)


def render_row(f):
    d = f["denominator"]
    mid = ('%s<small class="nm">%d/%d</small>' % (_bar(_pct(f)), f["done"], d)) if d \
        else ('%s<small class="nm">—</small>' % _bar(0, empty=True))
    todo = '<small class="todo">%d&nbsp;Todo</small>' % f["todo"] if f["todo"] else '<small class="todo">—</small>'
    return (
        '<button class="row" data-id="%s" data-phase="%s" onclick="selectRow(this)" '
        'hx-get="/fragment/feature/%s" hx-target="#detail" hx-swap="innerHTML" aria-label="%s %s">'
        '<span class="rid">%s</span>%s<span class="mid">%s</span>%s<span class="rflag">%s</span>'
        "</button>"
    ) % (esc(f["id"]), esc(f["phase"]), esc(f["id"]), esc(f["id"]), esc(f["phase"]),
         esc(f["id"]), _pill(f["phase"]), mid, todo, _flag_html(f))


def render_kcard(f):
    d = f["denominator"]
    prog = (('<progress class="progress progress-success kc-bar" value="%d" max="100"></progress>'
             '<span class="kc-nm">%d/%d</span>') % (_pct(f), f["done"], d)) if d else '<span class="kc-nm muted">no tasks</span>'
    todo = '<span class="kc-todo">%d Todo</span>' % f["todo"] if f["todo"] else ""
    if f["stale"]:
        flag = '<div class="kc-flag warn">⚠ %dd idle</div>' % f["idle_days"]
    elif f["phase"] == "Closed":
        flag = '<div class="kc-flag muted">%s</div>' % ("%d canceled" % f["counts"]["Canceled"] if f["counts"]["Canceled"] else "shipped")
    elif f["sub"]:
        flag = '<div class="kc-flag muted">%s</div>' % esc(f["sub"])
    else:
        flag = ""
    # the feature name rides beside the id, clipped to the card — never wraps, never overflows
    nm = f.get("display_name")
    name = '<span class="kc-name" title="%s">%s</span>' % (esc(nm), esc(nm)) if nm else ""
    return (
        '<button class="kcard" data-id="%s" data-phase="%s" hx-get="/fragment/feature/%s" '
        'hx-target="#drawer-content" hx-swap="innerHTML" onclick="openDrawer(this)">'
        '<div class="kc-idrow"><span class="kc-id">%s</span>%s</div><div class="kc-mid">%s%s</div>%s</button>'
    ) % (esc(f["id"]), esc(f["phase"]), esc(f["id"]), esc(f["id"]), name, prog, todo, flag)


def render_kanban(data, stale_only=False, lane=None):
    feats = [f for f in data["features"] if (not stale_only or f["stale"])]
    if lane:
        feats = [f for f in feats if f["lane"] == lane]
    buckets = {p: [] for p in PHASE_SEQ}
    for f in feats:
        buckets.get(f["phase"], buckets["Scope"]).append(f)
    stamp = '<span id="updated" hx-swap-oob="true" class="stamp">updated %s</span>' % datetime.now().strftime("%H:%M:%S")
    cols = []
    for p in PHASE_SEQ:
        items = buckets[p]
        cards = "".join(render_kcard(f) for f in items) or '<div class="kcol-empty">none</div>'
        cols.append('<div class="kcol" data-phase="%s"><div class="kcol-h"><span class="kcol-name">%s</span>'
                    '<span class="kcol-n">%d</span></div><div class="kcol-body">%s</div></div>'
                    % (esc(p), esc(p), len(items), cards))
    return stamp + "".join(cols)


def render_roster(data, stale_only=False, lane=None):
    # OOB stamp updates the header clock on every htmx swap
    out = ['<span id="updated" hx-swap-oob="true" class="stamp">updated %s</span>' % datetime.now().strftime("%H:%M:%S")]
    lanes = [lr for lr in data["lanes"] if (lane is None or lr["name"] == lane)]
    multi = data["lane_count"] > 1
    shown = False
    for lr in lanes:
        rows = [f for f in lr["features"] if (not stale_only or f["stale"])]
        if multi and stale_only and not rows:
            continue
        if multi and lane is None:  # the select names the lane; no lanehead when one is chosen
            out.append('<div class="lanehead">%s <span class="muted">· %s</span></div>' % (esc(lr["name"]), esc(lr["root"])))
        for f in rows:
            out.append(render_row(f))
            shown = True
        legacy = [] if stale_only else lr["legacy_prefixes"]
        if legacy:
            out.append('<div class="legacy">legacy: %s <span class="muted">— not issued here</span></div>' % esc(", ".join(legacy)))
    if not shown:
        out.append('<div class="empty-state">%s</div>' % (
            "Nothing stale — all caught up." if stale_only else "No features found. Check <code>--prefixes</code> / <code>--root</code>."))
    return "\n".join(out)


SEC_ORDER = ["Problem", "Root cause", "Approach", "Reading list", "Acceptance",
             "Fix", "Deviations", "Gotchas", "Out of scope"]


def render_tasks(tasks, fid=None):
    if not tasks:
        return '<section class="d-tasks"><h4>Tasks</h4><div class="sec-b muted">No task log yet.</div></section>'
    rows = []
    for t in tasks:
        status = t["status"]
        cls, disp = (status or "none").lower(), (status or "—")
        secs = t["sections"]
        order = [s for s in SEC_ORDER if s in secs] + [s for s in secs if s not in SEC_ORDER]
        body = []
        for name in order:
            txt = secs[name]
            if len(txt) > 700:
                txt = txt[:700].rstrip() + " …"
            body.append('<div class="sec"><span class="sec-h">%s</span><div class="sec-b">%s</div></div>'
                        % (esc(name), _md_inline(esc(txt))))
        detail = "".join(body) or '<div class="sec-b muted">No recorded detail.</div>'
        # the task thread mounts at the END of the task body — collapsed tasks cost a DOM node
        # and zero requests; the bundle hydrates one only when its <details> is opened.
        detail += mount("thread", scope="task", feature=fid, task=t["id"])
        dt = '<span class="t-date">%s</span>' % esc(t["date"] or "")
        rows.append(
            '<details class="task t-%s"><summary>'
            '<span class="t-dot"></span><code class="t-id">%s</code>'
            '<span class="t-title">%s</span>%s%s<span class="t-status">%s</span>'
            "</summary><div class=\"task-body\">%s</div></details>"
            % (esc(cls), esc(t["id"]), esc(t["title"] or ""), dt, chip(fid, t["id"]), esc(disp), detail))
    total = len(tasks)
    todo_n = sum(1 for t in tasks if (t["status"] or "").lower() == "todo")
    default = "todo" if todo_n else "all"

    def fbtn(mode, label):
        active = " btn-active" if mode == default else ""
        return ('<button class="btn btn-xs join-item%s" data-mode="%s" onclick="setTaskFilter(this)">%s</button>'
                % (active, mode, label))
    head = ('<div class="d-tasks-h"><div class="th-left">'
            '<h4>Tasks · <span class="tcount">%d</span></h4>'
            '<div class="join tfilter">%s%s</div></div>'
            '<button class="btn btn-xs" onclick="toggleAll(this)">expand all</button></div>'
            % (todo_n if default == "todo" else total, fbtn("todo", "Todo"), fbtn("all", "All")))
    return ('<section class="d-tasks" data-filter="%s" data-all="%d" data-todo="%d">%s%s'
            '<div class="tempty">No open tasks.</div></section>'
            % (default, total, todo_n, head, "".join(rows)))


def render_feature(data, fid):
    f = next((x for x in data["features"] if x["id"].lower() == fid.lower()
              or x["id"].lower().startswith(fid.lower() + "-")), None)
    if not f:
        return '<div class="empty-state">No such feature: <code>%s</code></div>' % esc(fid)
    ci = PHASE_SEQ.index(f["phase"]) if f["phase"] in PHASE_SEQ else -1
    steps = "".join('<li class="step %s">%s</li>' % ("step-primary" if i <= ci else "", esc(p))
                    for i, p in enumerate(PHASE_SEQ))
    g = f["gates"]
    gate_line = " · ".join([
        "Evals: ",
        "review-qa %s" % ("✓" if g["qa"] else "○"), "review-ux %s" % ("✓" if g["ux"] else "○"),
        "accept %s" % ("✓" if g["accept"] else "○"), "debrief %s" % ("✓" if f["debrief_closed"] else "○"),
    ])
    dates = " · ".join(x for x in [
        "started %s" % esc(f["started"]) if f["started"] else "",
        "last %s" % esc(f["last_activity"]) if f["last_activity"] else "",
        "age %dd" % f["age_days"] if f["age_days"] is not None else "",
        ((said_status.idle_phrase(f["idle_days"]) or "") + (" ⚠" if f["stale"] else "")) if f["idle_days"] is not None else "",
    ] if x)
    nxt = ""
    if f["next"]:
        nxt = ('<div class="d-next"><span class="lbl">Next</span><code class="nextcmd">%s</code>'
               '<button class="btn btn-xs copybtn" onclick="copyNext(this)">copy</button></div>') % esc(f["next"])
    prog = ('<div class="d-prog"><progress class="progress progress-success" value="%d" max="100"></progress>'
            '<span class="nm">%d / %d · %d%%</span></div>' % (_pct(f), f["done"], f["denominator"], _pct(f))) if f["denominator"] else ""
    fp = f.get("paths_rel") or f["paths"]  # display relative to the project root
    files = " · ".join(esc(p) for p in (fp["spec"], fp["tasks"], fp["scope"]) if p)
    lane_tag = '<span class="badge badge-outline badge-sm">%s</span>' % esc(f["lane"]) if data["lane_count"] > 1 else ""
    # the feature name sits below the id in the detail header — full text, wraps freely here
    nm = f.get("display_name")
    d_name = '<div class="d-name">%s</div>' % esc(nm) if nm else ""
    tasks = render_tasks(said_status.feature_tasks([f["paths"]["tasks"]] if f["paths"]["tasks"] else []), f["id"])
    return (
        '<div class="d-head"><span class="rid big">%s</span>%s%s%s</div>%s'
        '<ul class="steps steps-horizontal d-steps">%s</ul>'
        '<div class="d-gates">%s</div>%s'
        '<div class="d-dates">%s</div>%s%s%s'
        '<div class="d-files">%s</div>'
    ) % (esc(f["id"]), _pill(f["phase"]), lane_tag, chip(f["id"]), d_name, steps, esc(gate_line), prog, dates,
         tasks, mount("thread", scope="feature", feature=f["id"]), nxt, files)


# --- the Backlog view: the LOCAL todo file, read-only, in the task-row idiom --
# Connected-only, because it is a route the default install does not have. The list
# is the local file and nothing else; the shared intake arrives through the
# `backlog` mount point, which the app's bundle owns.
TODO_ITEM = re.compile(r"^\s*[-*]\s+(?:\[([ xX])\]\s*)?(\S.*?)\s*$")
TODO_DATE = re.compile(r"\s*\((\d{4}-\d{2}-\d{2})\)\s*$")


def parse_todo(text):
    """Markdown checklist → rows. Headings become section labels; anything else is skipped."""
    out = []
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        if line.lstrip().startswith("#"):
            head = line.lstrip("#").strip()
            if head:
                out.append({"head": head})
            continue
        m = TODO_ITEM.match(line)
        if not m:
            continue
        box, body = m.group(1), m.group(2)
        when = ""
        md = TODO_DATE.search(body)
        if md:
            when, body = md.group(1), body[:md.start()].rstrip()
        if not body:
            continue
        status = "" if box is None else ("Done" if box.lower() == "x" else "Todo")
        out.append({"text": body, "status": status, "date": when})
    return out


def read_todo():
    """(rows, exists) for the configured local todo file. Never raises."""
    try:
        with open(CFG["todo_path"], encoding="utf-8") as fh:
            return parse_todo(fh.read()), True
    except OSError:
        return [], False


def render_backlog():
    rows, exists = read_todo()
    stamp = '<span id="updated" hx-swap-oob="true" class="stamp">updated %s</span>' % datetime.now().strftime("%H:%M:%S")
    rel = esc(CFG["todo_rel"])
    items = [r for r in rows if "text" in r]
    if not items:
        return stamp + ('<div class="empty-state">%s <code>%s</code>.</div>'
                        % ("No local backlog yet —" if exists else "No local backlog file at", rel))
    open_n = sum(1 for r in items if r["status"] != "Done")
    done_n = len(items) - open_n
    out = [stamp, '<div class="bl-note"><span class="lbl">local</span>'
                  '<span class="nm">%d open · %d done</span><code>%s</code></div>' % (open_n, done_n, rel)]
    for r in rows:
        if "head" in r:
            out.append('<div class="lanehead">%s</div>' % esc(r["head"]))
            continue
        cls = (r["status"] or "none").lower()
        out.append('<div class="bl-item t-%s"><span class="t-dot"></span>'
                   '<span class="t-title">%s</span><span class="t-date">%s</span>'
                   '<span class="t-status">%s</span></div>'
                   % (esc(cls), esc(r["text"]), esc(r["date"]), esc(r["status"] or "—")))
    return "\n".join(out)


# --- page shell (htmx + daisyUI from CDN; inline CSS only for layout) --------
# --- static assets -----------------------------------------------------------
# Hardcoded allowlist: the request path is only ever a dict KEY, never joined to a
# filesystem path — so there is no traversal surface (`/board.css` and `/board.js` only).
ASSETS = {"/board.css": ("board.css", "text/css; charset=utf-8"),
          "/board.js": ("board.js", "application/javascript; charset=utf-8")}


def read_asset(filename):
    with open(os.path.join(_BASE, filename), encoding="utf-8") as fh:
        return fh.read()



def page():
    # The header needs only cheap config (project · lane names · today) — NOT the full analyze() — so the
    # shell returns instantly and the fragments stream the feature data in (with the loading logo ticking),
    # instead of the browser sitting blank while a git-per-feature derive runs server-side on a big repo.
    lanes, project = CFG["lanes"], CFG["project"]
    # lane switcher icon — a small branch glyph (the lanes are repo parts: front/server/prototype)
    lane_ico = ('<svg class="lane-ico" viewBox="0 0 16 16" width="13" height="13" fill="none" stroke="currentColor" '
                'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
                '<path d="M5 3.6v8.8"/><path d="M5 8h3.4a2.6 2.6 0 0 0 2.6-2.6V4.4"/>'
                '<circle cx="5" cy="3.4" r="1.35" fill="currentColor" stroke="none"/>'
                '<circle cx="5" cy="12.6" r="1.35" fill="currentColor" stroke="none"/>'
                '<circle cx="11" cy="3.9" r="1.35" fill="currentColor" stroke="none"/></svg>')
    # One lane at a time: a select drives ?lane=. Always rendered (a one-option select on a
    # single-lane repo); the client persists the choice and defaults to the first declared lane.
    lane_opts = "".join('<option value="%s">%s</option>' % (esc(L["name"]), esc(L["name"])) for L in lanes)
    lane_select = ('<select id="laneSelect" class="select select-xs laneSel" onchange="setLane(this)" '
                   'aria-label="Lane">%s</select>') % lane_opts
    # --- the embed (opt-in). Every one of these strings is "" unless --connect is on. ---
    app = CFG.get("app") or ""
    embed = bl_toggle = bl_view = body_extra = ""
    if connected():
        # data-said-origin is the ONLY place the app's origin is written; nothing is hardcoded.
        embed = ('<meta name="%s" content="%s">'
                 '<link rel="stylesheet" href="%s/embed/said-widgets.css">'
                 '<script src="%s/embed/said-widgets.js" defer data-said-origin="%s"></script>'
                 % (CSRF_META, esc(CFG["csrf"]), esc(app), esc(app), esc(app)))
        body_extra = ' data-connected="1"'
        bl_toggle = ('<button class="btn btn-xs join-item" data-view="backlog" '
                     'onclick="setView(this)">Backlog</button>')
        bl_view = (
            '<div id="backlogwrap"><section class="backlog">'
            '<form class="bl-add" onsubmit="return addTodo(this)">'
            '<input class="input input-sm bl-input" name="text" maxlength="%d" autocomplete="off" '
            'placeholder="add a local backlog item…" aria-label="New backlog item">'
            '<button class="btn btn-xs" type="submit">add</button>'
            '<span class="bl-msg" role="status"></span></form>'
            '<section id="backlog-list" hx-get="/fragment/backlog" hx-trigger="load, refresh" '
            'hx-indicator="#refreshBtn"><div class="empty-state">loading…</div></section>'
            '%s'
            '<form class="bl-conn" onsubmit="return saveConnect(this)"><span class="lbl">app</span>'
            '<input class="input input-xs bl-input" name="app" value="%s" aria-label="Local app URL">'
            '<button class="btn btn-xs" type="submit">save</button>'
            '<span class="bl-msg" role="status"></span></form>'
            "</section></div>" % (MAX_TODO_LEN, mount("backlog"), esc(app)))
    # 3-zone header: LEFT (logo·SAID·project·lane·Update·updated-time) | CENTER (List|Kanban) | RIGHT (rest)
    head = (
        '<div class="hz-left">'
        '<div class="brand"><a class="lockup" href="%s" target="_blank" rel="noopener noreferrer" '
        'title="saidkit.dev" aria-label="SAID — saidkit.dev">%s<span class="wm">SAID</span></a>'
        '<span class="proj">%s</span></div>'
        '<span class="lane-wrap">%s%s</span>'
        '<button id="refreshBtn" class="btn btn-xs update-pill" onclick="refreshNow()" title="Update from git">Update</button>'
        '<span id="updated" class="stamp">loading…</span>'
        "</div>"
        '<div class="hz-center"><div class="join vtoggle">'
        '<button class="btn btn-xs join-item btn-active" data-view="list" onclick="setView(this)">List</button>'
        '<button class="btn btn-xs join-item" data-view="kanban" onclick="setView(this)">Kanban</button>%s</div></div>'
        '<div class="hz-right">%s'
        '<label class="switch"><input id="staleToggle" type="checkbox" class="toggle toggle-sm" onchange="refreshVisible()">stale only</label>'
        '<label class="switch kanban-only"><input type="checkbox" class="toggle toggle-sm" onchange="toggleHideClosed(this)">hide closed</label>'
        '<button id="kbdBtn" class="btn btn-ghost btn-sm btn-square" onclick="toggleHelp()" title="Keyboard shortcuts (?)" aria-label="Keyboard shortcuts">⌨️</button>'
        '<button id="themeBtn" class="btn btn-ghost btn-sm btn-square" onclick="cycleTheme()" title="Toggle theme">\U0001F319</button>'
        "</div>"
    ) % (HOME, MARK % (22, 22), esc(project), lane_ico, lane_select, bl_toggle, mount("status"))
    vals = ("hx-vals='js:{stale: (document.getElementById(\"staleToggle\")||{}).checked?1:0, "
            "fresh: window.__fresh?1:0, "
            "lane: (document.getElementById(\"laneSelect\")||{}).value||\"\"}'")
    return (
        '<!doctype html><html data-theme="light"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1"><title>SAID board · %s</title>'
        '<link rel="icon" href="/favicon.svg" type="image/svg+xml">'
        '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        '<link rel="stylesheet" href="%s">'
        '<script src="%s" defer onerror="var b=document.getElementById(\'cdnwarn\');if(b)b.style.display=\'block\'"></script>'
        '<link rel="stylesheet" href="%s" onerror="var b=document.getElementById(\'cdnwarn\');if(b)b.style.display=\'block\'">'
        '<link rel="stylesheet" href="/board.css">%s</head><body data-view="list" class="sb-loading"%s>'
        # a full page load is an explicit refresh → the initial fragment loads derive fresh (async, while
        # the logo ticks); board.js clears __fresh after they settle so later navigation reuses the cache.
        '<script>window.__fresh=true</script>'
        '<div id="cdnwarn">A CDN asset (htmx/daisyUI) failed to load — data is live, but styling/refresh may be limited.</div>'
        "<header>%s</header><main id=\"main\" aria-keyshortcuts=\"ArrowUp ArrowDown ArrowLeft ArrowRight Enter Escape\">"
        '<div id="listwrap" class="cols">'
        '<section class="roster" id="roster" hx-get="/fragment/roster" hx-trigger="load, refresh" hx-indicator="#refreshBtn" %s>'
        '<div class="empty-state">loading…</div></section>'
        '<section class="detail" id="detail" tabindex="-1"><div class="empty-state">Select a feature — or press <kbd class="k">↑</kbd> <kbd class="k">↓</kbd> — to see its position in the SAID cycle.</div></section>'
        "</div>"
        '<div id="kanbanwrap"><section id="kanban" class="kanban" hx-get="/fragment/kanban" hx-trigger="load, refresh" hx-indicator="#refreshBtn" %s></section></div>'
        "%s</main>"
        '<aside id="drawer" aria-label="feature detail"><div class="drawer-h">'
        '<button class="btn btn-xs btn-ghost" onclick="closeDrawer()" title="Close">✕ close</button></div>'
        '<div id="drawer-content" class="drawer-content"></div></aside>'
        '<div id="backdrop" onclick="closeDrawer()"></div>'
        '<div id="help" role="dialog" aria-modal="false" aria-label="keyboard shortcuts">'
        '<h5>Keyboard</h5>'
        '<div class="krow"><span>Move</span><span class="keys"><kbd class="k">↑</kbd><kbd class="k">↓</kbd><kbd class="k">←</kbd><kbd class="k">→</kbd></span></div>'
        '<div class="krow"><span>Open detail</span><span class="keys"><kbd class="k">↵</kbd></span></div>'
        '<div class="krow"><span>Back / close</span><span class="keys"><kbd class="k">esc</kbd></span></div>'
        '<div class="krow"><span>First / last</span><span class="keys"><kbd class="k">Home</kbd><kbd class="k">End</kbd></span></div>'
        '<div class="krow"><span>Vim keys</span><span class="keys"><kbd class="k">h</kbd><kbd class="k">j</kbd><kbd class="k">k</kbd><kbd class="k">l</kbd></span></div>'
        '<div class="krow"><span>Toggle help</span><span class="keys"><kbd class="k">?</kbd></span></div>'
        "</div>"
        '<footer><span class="tagline">as said, so done</span>'
        "<span>%s</span>"
        '<span class="khint"><kbd>↑</kbd><kbd>↓</kbd> move · <kbd>↵</kbd> open · <kbd>esc</kbd> back · <kbd>?</kbd> keys</span>'
        '<a href="/api/status.json" target="_blank">/api/status.json</a></footer>'
        '<script src="/board.js" defer></script></body></html>'
    ) % (esc(project), FONTS, HTMX, DAISY, embed, body_extra, head, vals, vals, bl_view,
         ("local files · %s" % esc(app)) if connected() else "read-only · 127.0.0.1")


# --- HTTP handler ------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    server_version = "said-board"

    def _send(self, body, ctype="text/html; charset=utf-8", code=200):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def do_GET(self):
        u = urlparse(self.path)
        path, q = u.path, parse_qs(u.query)
        try:
            if path == "/":
                self._send(page())
            elif path == "/fragment/roster":
                stale = q.get("stale", ["0"])[0] in ("1", "true", "on")
                fresh = q.get("fresh", ["0"])[0] in ("1", "true", "on")
                self._send(render_roster(get_data(fresh=fresh), stale_only=stale, lane=q.get("lane", [None])[0]))
            elif path == "/fragment/kanban":
                stale = q.get("stale", ["0"])[0] in ("1", "true", "on")
                fresh = q.get("fresh", ["0"])[0] in ("1", "true", "on")
                self._send(render_kanban(get_data(fresh=fresh), stale_only=stale, lane=q.get("lane", [None])[0]))
            elif path.startswith("/fragment/feature/"):
                fid = path[len("/fragment/feature/"):]
                self._send(render_feature(get_data(), fid) if ID_RE.match(fid)
                           else '<div class="empty-state">Invalid feature id.</div>', code=200 if ID_RE.match(fid) else 400)
            elif path == "/fragment/backlog" and connected():  # opt-in: absent (404) otherwise
                self._send(render_backlog())
            elif path == "/api/status.json":
                self._send(json.dumps(get_data(), ensure_ascii=False, indent=2), ctype="application/json; charset=utf-8")
            elif path == "/healthz":
                self._send("ok", ctype="text/plain")
            elif path in ASSETS:  # hardcoded allowlist — path is a dict key, never a filesystem join
                fname, ctype = ASSETS[path]
                try:
                    self._send(read_asset(fname), ctype=ctype)
                except OSError as exc:
                    sys.stderr.write("said-board: asset %s unreadable (%s)\n" % (fname, exc))
                    self._send("/* said-board: %s missing beside serve.py */" % fname, ctype=ctype, code=404)
            elif path == "/favicon.svg":
                self._send(FAVICON, ctype="image/svg+xml")
            elif path == "/favicon.ico":
                self._send("", ctype="text/plain", code=204)
            else:
                self._send('<div class="empty-state">404</div>', code=404)
        except BrokenPipeError:
            pass
        except Exception as exc:
            self._send('<div class="empty-state">Error: %s</div>' % esc(exc), code=500)

    do_HEAD = do_GET

    def _reject(self):
        self._send("read-only: GET only", ctype="text/plain", code=405)

    do_PUT = do_DELETE = do_PATCH = _reject

    # --- local writes (opt-in) -----------------------------------------------
    # Two routes, both LOCAL FILES: /connect writes docs/.board/config.json, /todo
    # appends one line to the local todo file. Nothing else, no other method — and
    # neither exists at all unless the integration is on.
    #
    # A loopback server has no authentication, which was safe while it was GET-only:
    # any page in any tab can POST cross-origin to a localhost port, and a form-encoded
    # post is a *simple* request — no preflight, and refusing to hand back the response
    # does not undo the side effect. So each write carries four controls together:
    #   1. Origin must be this server's own (the load-bearing one; survives DNS rebinding
    #      because the comparison is against a fixed set, not the request's Host header);
    #   2. a CSRF token minted into the page and required back;
    #   3. JSON content type PLUS a custom header — neither is producible by a cross-site
    #      form post, so a preflight becomes mandatory and control 1 actually runs;
    #   4. opt-in — no flag, no route.
    # No CORS header is ever sent, so that preflight fails and no other origin can reach
    # these routes even before the checks run.
    def _json(self, obj, code=200):
        self._send(json.dumps(obj, ensure_ascii=False), ctype="application/json; charset=utf-8", code=code)

    def _write_guard(self):
        """None when the request may write, else (code, reason)."""
        if self.headers.get("Origin") not in (CFG.get("origins") or set()):
            return (403, "origin")
        if not (self.headers.get("Content-Type") or "").lower().startswith("application/json"):
            return (415, "content-type")
        if not self.headers.get(WIDGET_HEADER):
            return (403, "header")
        want = CFG.get("csrf") or ""
        token = self.headers.get(CSRF_HEADER) or ""
        if not want or not hmac.compare_digest(token, want):
            return (403, "csrf")
        return None

    def _body(self):
        """The JSON object sent, or None. Bounded — a local write is one line of text."""
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return None
        if n <= 0 or n > MAX_BODY:
            return None
        try:
            payload = json.loads(self.rfile.read(n).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    def do_POST(self):
        path = urlparse(self.path).path
        if path not in ("/connect", "/todo"):
            return self._reject()          # every other path: read-only, GET only
        if not connected():
            return self._json({"ok": False, "error": "not found"}, code=404)
        bad = self._write_guard()
        if bad:
            return self._json({"ok": False, "error": bad[1]}, code=bad[0])
        payload = self._body()
        if payload is None:
            return self._json({"ok": False, "error": "bad request"}, code=400)
        try:
            if path == "/connect":
                app = normalize_origin(payload.get("app"))
                if not app:
                    return self._json({"ok": False, "error": "a local http(s) URL is required"}, code=400)
                write_config({"app": app})
                CFG["app"] = app           # a reload picks up the new origin; no restart needed
                return self._json({"ok": True, "app": app})
            text = payload.get("text")
            if not isinstance(text, str) or not text.strip():
                return self._json({"ok": False, "error": "text is required"}, code=400)
            item = append_todo(text)
            return self._json({"ok": True, "item": item, "file": CFG["todo_rel"]})
        except OSError as exc:
            return self._json({"ok": False, "error": "cannot write: %s" % exc}, code=500)

    def log_message(self, fmt, *args):
        sys.stderr.write("  %s %s\n" % (datetime.now().strftime("%H:%M:%S"), (fmt % args)))


def _bind(host, port, tries=25):
    last = None
    for p in range(port, port + tries):
        try:
            return ThreadingHTTPServer((host, p), Handler)
        except OSError as exc:
            last = exc
    raise last


# --- process/port tracking (for `serve.py stop` and back-reference) ----------
PIDFILE = os.path.join(tempfile.gettempdir(), "said-board.json")


def _write_pidfile(port, url):
    try:
        with open(PIDFILE, "w") as fh:
            json.dump({"pid": os.getpid(), "port": port, "url": url,
                       "started": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}, fh)
    except OSError:
        pass


def _read_pidfile():
    try:
        with open(PIDFILE) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _clear_pidfile():
    try:
        os.remove(PIDFILE)
    except OSError:
        pass


def _pids_on_port(port):
    # LISTENers only: a bare `lsof -i tcp:<port>` also matches connected CLIENTS
    # (an open browser tab holds a socket to the loopback port), which must never be signalled.
    try:
        out = subprocess.run(["lsof", "-t", "-i", "tcp:%d" % port, "-sTCP:LISTEN"],
                             capture_output=True, text=True, timeout=5)
        return [int(x) for x in out.stdout.split()]
    except Exception:
        return []


def stop_server(port):
    info, killed, targets = _read_pidfile(), [], []
    listeners = None
    if info and info.get("pid"):
        pid = int(info["pid"])
        port = int(info.get("port") or port)
        listeners = _pids_on_port(port)
        if pid in listeners:
            targets.append(pid)  # trust the recorded server; no broad port sweep
    if not targets:
        # pidfile missing/stale — fall back to the port's LISTENer(s) only
        targets = listeners if listeners is not None else _pids_on_port(port)
    for pid in targets:
        try:
            os.kill(pid, signal.SIGTERM)
            killed.append(pid)
        except ProcessLookupError:
            pass
        except OSError as exc:
            sys.stderr.write("said:board: could not kill pid %d (%s)\n" % (pid, exc))
    _clear_pidfile()
    if killed:
        sys.stderr.write("said:board stopped · pid %s · port %d\n" % (", ".join(map(str, killed)), port))
        return 0
    sys.stderr.write("said:board: no running server found (port %d)\n" % port)
    return 1


def main():
    ap = argparse.ArgumentParser(description="said:board — local web dashboard (read-only, loopback).")
    ap.add_argument("--root", default=".")
    ap.add_argument("--docs-dir", default="docs/features")
    ap.add_argument("--working-dir", default="docs/working")
    ap.add_argument("--prefixes")
    ap.add_argument("--legacy-prefixes")
    ap.add_argument("--lane", action="append", default=[], metavar="NAME[:k=v;...]")
    ap.add_argument("--project")
    ap.add_argument("--stale-days", type=int, default=None)
    ap.add_argument("--today", help="YYYY-MM-DD (default: real today) — pin for reproducible evals")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-open", action="store_true")
    ap.add_argument("--connect", metavar="URL",
                    help="opt in to the local companion app at URL (loopback only) — embed, badges, "
                         "Backlog view and the two local-file writes. Omit and none of it exists.")
    ap.add_argument("--todo-file", default=None,
                    help="the local backlog file, relative to --root (default: %s)" % TODO_DEFAULT)
    ap.add_argument("command", nargs="?", default="start", choices=["start", "stop"],
                    help="start (default) or stop the running server")
    a = ap.parse_args()

    if a.command == "stop":
        sys.exit(stop_server(a.port))

    project = a.project or os.path.basename(os.path.abspath(a.root))
    defaults = {"name": project, "root": a.root, "docs_dir": a.docs_dir, "work_dir": a.working_dir,
                "prefixes": [p.strip() for p in a.prefixes.split(",")] if a.prefixes else None,
                "legacy_prefixes": [p.strip() for p in a.legacy_prefixes.split(",")] if a.legacy_prefixes else None}
    CFG["project"] = project
    CFG["today"] = a.today
    CFG["lanes"] = [said_status.parse_lane_arg(x, defaults) for x in a.lane] if a.lane else [defaults]
    CFG["root"] = a.root

    # --- opt-in integration: the flag first, then a config left by an earlier connect ---
    stored = read_config(a.root)
    if a.connect:
        app = normalize_origin(a.connect)
        if not app:
            sys.stderr.write("said-board: --connect must be a loopback http(s) URL "
                             "(e.g. http://localhost:3000) — got %r\n" % a.connect)
            sys.exit(2)
    else:
        app = normalize_origin(stored.get("app"))
        if stored.get("app") and not app:
            sys.stderr.write("said-board: ignoring %s/%s — %r is not a loopback http(s) URL\n"
                             % (BOARD_DIR, CONFIG_JSON, stored.get("app")))
    if app and "127.0.0.1" in app:
        sys.stderr.write("said-board: the app is on 127.0.0.1 but the board opens on localhost — a browser "
                         "treats those as different hosts and will not send the app's session cookie. "
                         "Serve both on localhost.\n")
    CFG["app"] = app
    CFG["csrf"] = secrets.token_urlsafe(32) if app else ""
    todo_rel = a.todo_file or stored.get("todo") or TODO_DEFAULT
    CFG["todo_rel"] = todo_rel
    CFG["todo_path"] = os.path.normpath(os.path.join(a.root, todo_rel))

    missing = [f for f, _ in ASSETS.values() if not os.path.isfile(os.path.join(_BASE, f))]
    if missing:
        sys.stderr.write("said-board: missing asset(s) beside serve.py: %s — the page will render unstyled\n"
                         % ", ".join(missing))

    httpd = _bind("127.0.0.1", a.port)
    port = httpd.server_address[1]
    CFG["origins"] = own_origins(port)
    # Connected boards open on `localhost` deliberately: the browser treats localhost and
    # 127.0.0.1 as different hosts, and a session cookie set by the app on one is simply
    # not sent from the other — which presents as broken sign-in, not as a config error.
    url = "http://%s:%d/" % ("localhost" if connected() else "127.0.0.1", port)
    _write_pidfile(port, url)
    sys.stderr.write("said:board · %s · pid %d\n%s · loopback · htmx + daisyUI via CDN\n"
                     "stop: `python3 serve.py stop`  (or Ctrl-C) · state: %s\n"
                     % (url, os.getpid(),
                        ("connected · %s · local writes: /connect /todo (%s)" % (CFG["app"], CFG["todo_rel"]))
                        if connected() else "read-only", PIDFILE))
    if not a.no_open:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        sys.stderr.write("\nstopping…\n")
    finally:
        _clear_pidfile()
        httpd.shutdown()
        httpd.server_close()


if __name__ == "__main__":
    main()
