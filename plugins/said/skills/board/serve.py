#!/usr/bin/env python3
"""serve.py — said:board local web dashboard.

Read-only, loopback-only, stdlib-only server. Reuses the sibling said-status
analyzer's deterministic core and serves it as a live local page. The HTML shell
loads **htmx** and **daisyUI** from a CDN (no pip, no node_modules, no build);
htmx drives the auto-refresh + deep-dive, daisyUI provides components + themes.
See REQUIREMENTS.md for the contract.
"""

import argparse
import html
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
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
PHASE_SEQ = ["Scope", "Architect", "Implement", "Delivery", "Closed"]

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


def get_data(stale_days=None):
    return said_status.analyze(CFG["lanes"], CFG.get("today") or date.today().isoformat(), stale_days, CFG["project"])


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
    if f.get("integrity"):
        bits.append('<span class="warn">! %s</span>' % esc(f["integrity"]))
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
        if multi:
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


def render_tasks(tasks):
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
        dt = '<span class="t-date">%s</span>' % esc(t["date"] or "")
        rows.append(
            '<details class="task t-%s"><summary>'
            '<span class="t-dot"></span><code class="t-id">%s</code>'
            '<span class="t-title">%s</span>%s<span class="t-status">%s</span>'
            "</summary><div class=\"task-body\">%s</div></details>"
            % (esc(cls), esc(t["id"]), esc(t["title"] or ""), dt, esc(disp), detail))
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
    return (
        '<div class="d-head"><span class="rid big">%s</span>%s%s</div>%s'
        '<ul class="steps steps-horizontal d-steps">%s</ul>'
        '<div class="d-gates">%s</div>%s'
        '<div class="d-dates">%s</div>%s%s'
        '<div class="d-files">%s</div>'
    ) % (esc(f["id"]), _pill(f["phase"]), lane_tag, d_name, steps, esc(gate_line), prog, dates,
         render_tasks(said_status.feature_tasks([f["paths"]["tasks"]] if f["paths"]["tasks"] else [])), nxt, files)


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
    d = get_data()
    n = d["lane_count"]
    head = (
        '<div class="brand">'
        '<a class="lockup" href="%s" target="_blank" rel="noopener noreferrer" '
        'title="saidkit.dev" aria-label="SAID — saidkit.dev">%s<span class="wm">SAID</span></a>'
        '<span class="proj">%s</span><span class="sub">%d lane%s · %s</span></div>'
        '<div class="ctrls">'
        '<div class="join vtoggle"><button class="btn btn-xs join-item btn-active" data-view="list" onclick="setView(this)">List</button>'
        '<button class="btn btn-xs join-item" data-view="kanban" onclick="setView(this)">Kanban</button></div>'
        '<span id="updated" class="stamp">loading…</span>'
        '<label class="switch"><input id="staleToggle" type="checkbox" class="toggle toggle-sm" onchange="refreshVisible()">stale only</label>'
        '<label class="switch kanban-only"><input type="checkbox" class="toggle toggle-sm" onchange="toggleHideClosed(this)">hide closed</label>'
        '<button id="kbdBtn" class="btn btn-ghost btn-sm btn-square" onclick="toggleHelp()" title="Keyboard shortcuts (?)" aria-label="Keyboard shortcuts">⌨️</button>'
        '<button id="themeBtn" class="btn btn-ghost btn-sm btn-square" onclick="cycleTheme()" title="Toggle theme">\U0001F319</button>'
        "</div>"
    ) % (HOME, MARK % (22, 22), esc(d["project"]), n, "" if n == 1 else "s", esc(d["today"]))
    vals = "hx-vals='js:{stale: (document.getElementById(\"staleToggle\")||{}).checked?1:0}'"
    return (
        '<!doctype html><html data-theme="light"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1"><title>SAID board · %s</title>'
        '<link rel="icon" href="/favicon.svg" type="image/svg+xml">'
        '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        '<link rel="stylesheet" href="%s">'
        '<script src="%s" defer onerror="var b=document.getElementById(\'cdnwarn\');if(b)b.style.display=\'block\'"></script>'
        '<link rel="stylesheet" href="%s" onerror="var b=document.getElementById(\'cdnwarn\');if(b)b.style.display=\'block\'">'
        '<link rel="stylesheet" href="/board.css"></head><body data-view="list">'
        '<div id="cdnwarn">A CDN asset (htmx/daisyUI) failed to load — data is live, but styling/refresh may be limited.</div>'
        "<header>%s</header><main id=\"main\" aria-keyshortcuts=\"ArrowUp ArrowDown ArrowLeft ArrowRight Enter Escape\">"
        '<div id="listwrap" class="cols">'
        '<section class="roster" id="roster" hx-get="/fragment/roster" hx-trigger="load, refresh" %s>'
        '<div class="empty-state">loading…</div></section>'
        '<section class="detail" id="detail" tabindex="-1"><div class="empty-state">Select a feature — or press <kbd class="k">↑</kbd> <kbd class="k">↓</kbd> — to see its position in the SAID cycle.</div></section>'
        "</div>"
        '<div id="kanbanwrap"><section id="kanban" class="kanban" hx-get="/fragment/kanban" hx-trigger="load, refresh" %s></section></div>'
        "</main>"
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
        '<span>read-only · 127.0.0.1</span>'
        '<span class="khint"><kbd>↑</kbd><kbd>↓</kbd> move · <kbd>↵</kbd> open · <kbd>esc</kbd> back · <kbd>?</kbd> keys</span>'
        '<a href="/api/status.json" target="_blank">/api/status.json</a></footer>'
        '<script src="/board.js" defer></script></body></html>'
    ) % (esc(d["project"]), FONTS, HTMX, DAISY, head, vals, vals)


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
                self._send(render_roster(get_data(), stale_only=stale, lane=q.get("lane", [None])[0]))
            elif path == "/fragment/kanban":
                stale = q.get("stale", ["0"])[0] in ("1", "true", "on")
                self._send(render_kanban(get_data(), stale_only=stale, lane=q.get("lane", [None])[0]))
            elif path.startswith("/fragment/feature/"):
                fid = path[len("/fragment/feature/"):]
                self._send(render_feature(get_data(), fid) if ID_RE.match(fid)
                           else '<div class="empty-state">Invalid feature id.</div>', code=200 if ID_RE.match(fid) else 400)
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

    do_POST = do_PUT = do_DELETE = do_PATCH = _reject

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
    try:
        out = subprocess.run(["lsof", "-ti", "tcp:%d" % port], capture_output=True, text=True, timeout=5)
        return [int(x) for x in out.stdout.split()]
    except Exception:
        return []


def stop_server(port):
    info, killed, targets = _read_pidfile(), [], []
    if info and info.get("pid"):
        targets.append(int(info["pid"]))
        port = int(info.get("port") or port)
    for p in _pids_on_port(port):  # fallback / catches a server started before pidfiles
        if p not in targets:
            targets.append(p)
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

    missing = [f for f, _ in ASSETS.values() if not os.path.isfile(os.path.join(_BASE, f))]
    if missing:
        sys.stderr.write("said-board: missing asset(s) beside serve.py: %s — the page will render unstyled\n"
                         % ", ".join(missing))

    httpd = _bind("127.0.0.1", a.port)
    port = httpd.server_address[1]
    url = "http://127.0.0.1:%d/" % port
    _write_pidfile(port, url)
    sys.stderr.write("said:board · %s · pid %d\nread-only · loopback · htmx + daisyUI via CDN\n"
                     "stop: `python3 serve.py stop`  (or Ctrl-C) · state: %s\n" % (url, os.getpid(), PIDFILE))
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
