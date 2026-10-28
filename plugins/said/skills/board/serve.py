#!/usr/bin/env python3
"""serve.py — said:board local web dashboard.

Loopback-only, stdlib-only server. Reuses the analyzer beside it
(said_status.py), its deterministic core, and serves it as a live local page. The HTML shell
loads **htmx** and **daisyUI** from a CDN (no pip, no node_modules, no build);
htmx drives the auto-refresh + deep-dive, daisyUI provides components + themes.
Its only writes are local files: the backlog and todo boards set a priority token or move an
entry (`POST /backlog/priority`, `/backlog/order`, `/todo/priority`, `/todo/order`).

**Optional integration (opt-in, `--connect <url>`).** Pointed at a local companion
app, the board additionally emits an embed — one stylesheet link, one script tag,
and empty mount points that the app's bundle hydrates — reads comment counts off a
local cache file, and accepts one more local-file write, the app URL (`POST /connect`).
Without the flag none of that exists: no script tag, no mount points, no extra route.

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

# --- the analyzer beside this file (one deterministic core: the web numbers are the terminal numbers) ---
_BASE = os.path.dirname(os.path.abspath(__file__))
if _BASE not in sys.path:
    sys.path.insert(0, _BASE)
try:
    import said_status
except Exception as exc:  # pragma: no cover
    sys.stderr.write("said-board: cannot import the analyzer said_status.py beside %s (%s)\n" % (_BASE, exc))
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

# Phase colour comes from the brand ramp in board.css (neutral -> cobalt -> green),
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
CONFIG_JSON = "config.json"          # {"app": "http://localhost:<port>"}
CACHE_INDEX = ("cache", "index.json")  # badge counts, written by whatever syncs with the app
CACHE_MAX_AGE_DAYS = 30              # older than this: the cache is stale -> render nothing
MAX_BODY = 8192                      # a local write is one line of text, never a payload
LOOPBACK = ("localhost", "127.0.0.1", "::1")
CSRF_META = "said-board-csrf"        # the token is minted into the page...
CSRF_HEADER = "X-Said-Board-Csrf"    # ...and required back on every write
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
        return True                     # no claim of freshness -> the file is taken at face value
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
        lbl += ", %d unread" % unread
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


# --- single-flight guard: derive on refresh, cache until the next one --------
# The features board: analyze() (a git-per-feature call, seconds on a large repo)
# runs only on an explicit refresh — a full page load or the header button, both
# fresh=True — and the result is cached until the next such refresh. Non-fresh
# requests (deep-dive clicks, lane switches) always reuse the cached derive, so
# navigating the board never re-runs git. Single-flight collapses the page-load
# fan-in (page + roster + kanban) onto one run.
_cache = {}                       # (board, stale_days) -> (monotonic_ts, data)
_cache_lock = threading.Lock()
_write_lock = threading.Lock()    # the board writes, one at a time
_flight = {}                      # (board, stale_days) -> Lock (one derive per key in flight)


def _analyze(stale_days):
    return said_status.analyze(CFG["lanes"], CFG.get("today") or date.today().isoformat(), stale_days, CFG["project"])


_gen = {}                         # key -> writes so far: a derive that saw an older file is never cached


def _single_flight(key, derive, fresh):
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
        gen = _gen.get(key, 0)
        data = derive()
        if _gen.get(key, 0) == gen:   # a write landed meanwhile: serve this read once, cache nothing
            _cache[key] = (time.monotonic(), data)
        return data


def get_data(stale_days=None, fresh=False):
    return _single_flight(("features", stale_days), lambda: _analyze(stale_days), fresh)


def get_backlog(fresh=False):  # its own key: a backlog load or refresh never runs the analyzer
    return _single_flight(("backlog",), lambda: said_backlog.board_view(said_backlog.read_all(CFG["root"])), fresh)


def warm_features():
    """The features the features board already derived, or none: a backlog or todo load never runs the analyzer."""
    hit = _cache.get(("features", None))
    return (hit[1].get("features") or []) if hit else []


def get_todo(fresh=False):  # its own key, as the backlog's
    return _single_flight(("todo",), lambda: said_backlog.todo_view(said_backlog.read_all(CFG["root"])), fresh)


# --- the boards: one module per thing; they import the shell's helpers by name -----------------------
sys.modules.setdefault("serve", sys.modules[__name__])  # run as a script, the shell is still `serve` to its boards
from boards.features import render_feature, render_kanban, render_roster  # noqa: E402
from boards.backlog import VIEWS as BACKLOG_VIEWS, render_backlog_board  # noqa: E402
from boards.todo import render_todo_board  # noqa: E402
import said_backlog  # noqa: E402  the backlog reader beside the analyzer


# --- page shell (htmx + daisyUI from CDN; inline CSS only for layout) --------
# --- static assets -----------------------------------------------------------
# Hardcoded allowlist: the request path is only ever a dict KEY, never joined to a
# filesystem path - so there is no traversal surface (`/board.css`, `/board.js` and each board's own script).
ASSETS = {"/board.css": ("board.css", "text/css; charset=utf-8"),
          "/board.js": ("board.js", "application/javascript; charset=utf-8"),
          "/boards/features.js": ("boards/features.js", "application/javascript; charset=utf-8"),
          "/boards/backlog.js": ("boards/backlog.js", "application/javascript; charset=utf-8"),
          "/boards/todo.js": ("boards/todo.js", "application/javascript; charset=utf-8"),
          "/boards/lists.js": ("boards/lists.js", "application/javascript; charset=utf-8"),
          "/boards/lists.css": ("boards/lists.css", "text/css; charset=utf-8")}
# the boards the header switch offers, the features board first (the default); board.js swaps the surface
BOARD_WRITES = ("/backlog/priority", "/backlog/order", "/todo/priority", "/todo/order")  # on with no flag, all behind _write_guard
BOARD_SWITCH = (('features', 'Features', '/?board=features'), ('backlog', 'Backlog', '/?board=backlog'), ('todo', 'Todo', '/?board=todo'))


def read_asset(filename):
    with open(os.path.join(_BASE, filename), encoding="utf-8") as fh:
        return fh.read()



def page():
    # The header needs only cheap config (project, lane names, today) — NOT the full analyze() — so the
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
    # each option names the feature ids its lane shows, so a #<feature-id> link selects the lane that holds
    # that exact id (a file read, no git)
    lane_opts = "".join('<option value="%s" data-ids="%s">%s</option>' % (
        esc(L["name"]), esc(",".join(said_status.lane_ids(L))), esc(L["name"]))
        for L in lanes)
    lane_select = ('<select id="laneSelect" class="select select-xs laneSel" onchange="setLane(this)" '
                   'aria-label="Lane">%s</select>') % lane_opts
    # --- the embed (opt-in). Every one of these strings is "" unless --connect is on. ---
    app = CFG.get("app") or ""
    embed = conn_form = body_extra = ""
    if connected():
        # data-said-origin is the ONLY place the app's origin is written; nothing is hardcoded.
        embed = ('<meta name="%s" content="%s">'
                 '<link rel="stylesheet" href="%s/embed/said-widgets.css">'
                 '<script src="%s/embed/said-widgets.js" defer data-said-origin="%s"></script>'
                 % (CSRF_META, esc(CFG["csrf"]), esc(app), esc(app), esc(app)))
        body_extra = ' data-connected="1"'
        # the app-URL form posts to /connect: it exists only on an already-connected board
        conn_form = ('<form class="bl-conn" onsubmit="return saveConnect(this)"><span class="lbl">app</span>'
                     '<input class="input input-xs bl-input" name="app" value="%s" aria-label="Local app URL">'
                     '<button class="btn btn-xs" type="submit">save</button>'
                     '<span class="bl-msg" role="status"></span></form>' % esc(app))
    else:  # the board writes are on with no flag, so every page carries the token they require
        embed = '<meta name="%s" content="%s">' % (CSRF_META, esc(CFG["csrf"]))
    board_switch = '<nav class="board-switch" aria-label="Board">%s</nav>' % "".join(
        '<a class="btn btn-ghost btn-xs" data-board="%s" href="%s">%s</a>' % (esc(b), esc(h), esc(t)) for b, t, h in BOARD_SWITCH)
    # 3-zone header: LEFT (logo,SAID,project,lane,Update,updated-time) | CENTER (List|Kanban) | RIGHT (rest)
    head = (
        '<div class="hz-left">'
        '<div class="brand"><a class="lockup" href="%s" target="_blank" rel="noopener noreferrer" '
        'title="saidkit.dev" aria-label="SAID — saidkit.dev">%s<span class="wm">SAID</span></a>'
        '<span class="proj">%s</span></div>'
        '<span class="lane-wrap">%s%s</span>'
        '<button id="refreshBtn" class="btn btn-xs update-pill" onclick="refreshNow()" title="Update from git">Update</button>'
        '<span id="updated" class="stamp">loading...</span>'
        "</div>"
        '<div class="hz-center">%s<div class="join vtoggle">'
        '<button class="btn btn-xs join-item btn-active" data-view="list" onclick="setView(this)">List</button>'
        '<button class="btn btn-xs join-item" data-view="kanban" onclick="setView(this)">Kanban</button></div></div>'
        '<div class="hz-right">%s'
        '<label class="switch"><input id="staleToggle" type="checkbox" class="toggle toggle-sm" onchange="refreshVisible()">stale only</label>'
        '<label class="switch kanban-only"><input type="checkbox" class="toggle toggle-sm" onchange="toggleHideClosed(this)">hide closed</label>'
        '<button id="kbdBtn" class="btn btn-ghost btn-sm btn-square" onclick="toggleHelp()" title="Keyboard shortcuts (?)" aria-label="Keyboard shortcuts">⌨️</button>'
        '<button id="themeBtn" class="btn btn-ghost btn-sm btn-square" onclick="cycleTheme()" title="Toggle theme">\U0001F319</button>'
        "</div>"
    ) % (HOME, MARK % (22, 22), esc(project), lane_ico, lane_select, board_switch, mount("status"))
    vals = ("hx-vals='js:{stale: (document.getElementById(\"staleToggle\")||{}).checked?1:0, "
            "fresh: window.__fresh?1:0, "
            "lane: (document.getElementById(\"laneSelect\")||{}).value||\"\"}'")
    return (
        '<!doctype html><html data-theme="light"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1"><title>SAID board, %s</title>'
        '<link rel="icon" href="/favicon.svg" type="image/svg+xml">'
        '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        '<link rel="stylesheet" href="%s">'
        '<script src="%s" defer onerror="var b=document.getElementById(\'cdnwarn\');if(b)b.style.display=\'block\'"></script>'
        '<link rel="stylesheet" href="%s" onerror="var b=document.getElementById(\'cdnwarn\');if(b)b.style.display=\'block\'">'
        '<link rel="stylesheet" href="/board.css">%s</head><body data-view="list" class="sb-loading"%s>'
        # a full page load is an explicit refresh -> the initial fragment loads derive fresh (async, while
        # the logo ticks); board.js clears __fresh after they settle so later navigation reuses the cache.
        '<script>window.__fresh=true</script>'
        '<div id="cdnwarn">A CDN asset (htmx/daisyUI) failed to load — data is live, but styling/refresh may be limited.</div>'
        "<header>%s</header><main id=\"main\" aria-keyshortcuts=\"ArrowUp ArrowDown ArrowLeft ArrowRight Enter Escape\">"
        '<div id="listwrap" class="cols">'
        '<section class="roster" id="roster" hx-get="/fragment/roster" hx-trigger="load, refresh" hx-indicator="#refreshBtn" %s>'
        '<div class="empty-state">loading...</div></section>'
        '<section class="detail" id="detail" tabindex="-1"><div class="empty-state">Select a feature — or press <kbd class="k">Up</kbd> <kbd class="k">Down</kbd> — to see its position in the SAID cycle.</div></section>'
        "</div>"
        '<div id="kanbanwrap"><section id="kanban" class="kanban" hx-get="/fragment/kanban" hx-trigger="load, refresh" hx-indicator="#refreshBtn" %s></section></div>'
        "</main>"
        '<aside id="drawer" aria-label="feature detail"><div class="drawer-h">'
        '<button class="btn btn-xs btn-ghost" onclick="closeDrawer()" title="Close">✕ close</button></div>'
        '<div id="drawer-content" class="drawer-content"></div></aside>'
        '<div id="backdrop" onclick="closeDrawer()"></div>'
        '<div id="help" role="dialog" aria-modal="false" aria-label="keyboard shortcuts">'
        '<h5>Keyboard</h5>'
        '<div class="krow"><span>Move</span><span class="keys"><kbd class="k">Up</kbd><kbd class="k">Down</kbd><kbd class="k">Left</kbd><kbd class="k">Right</kbd></span></div>'
        '<div class="krow"><span>Open detail</span><span class="keys"><kbd class="k">Enter</kbd></span></div>'
        '<div class="krow"><span>Back / close</span><span class="keys"><kbd class="k">esc</kbd></span></div>'
        '<div class="krow"><span>First / last</span><span class="keys"><kbd class="k">Home</kbd><kbd class="k">End</kbd></span></div>'
        '<div class="krow"><span>Vim keys</span><span class="keys"><kbd class="k">h</kbd><kbd class="k">j</kbd><kbd class="k">k</kbd><kbd class="k">l</kbd></span></div>'
        '<div class="krow"><span>Toggle help</span><span class="keys"><kbd class="k">?</kbd></span></div>'
        "</div>"
        '<footer><span class="tagline">as said, so done</span>'
        "<span>%s</span>%s"
        '<span class="khint"><kbd>Up</kbd><kbd>Down</kbd> move, <kbd>Enter</kbd> open, <kbd>esc</kbd> back, <kbd>?</kbd> keys</span>'
        '<a href="/api/status.json" target="_blank">/api/status.json</a></footer>'
        '<script src="/board.js" defer></script><script src="/boards/features.js" defer></script><script src="/boards/lists.js" defer></script><script src="/boards/backlog.js" defer></script><script src="/boards/todo.js" defer></script></body></html>'
    ) % (esc(project), FONTS, HTMX, DAISY, embed, body_extra, head, vals, vals,
         "local files, %s" % (esc(app) if connected() else "127.0.0.1"), conn_form)


# --- HTTP handler ------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    server_version = "said-board"
    timeout = 10                  # a stalled request body never holds a handler thread for good

    def _send(self, body, ctype="text/html; charset=utf-8", code=200):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def _foreign_host(self):
        """True unless the Host is one of this server's own loopback origins (a rebinding page sends its own)."""
        own = {o.split("://", 1)[1] for o in (CFG.get("origins") or set())}
        return (self.headers.get("Host") or "").strip().lower() not in own

    def do_GET(self):
        if self._foreign_host():
            return self._send("host", ctype="text/plain", code=403)
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
                self._send(render_feature(get_data(), fid, lane=q.get("lane", [None])[0]) if ID_RE.match(fid)
                           else '<div class="empty-state">Invalid feature id.</div>', code=200 if ID_RE.match(fid) else 400)
            elif path.startswith("/backlog/") and path[len("/backlog/"):] in BACKLOG_VIEWS:
                fresh = q.get("fresh", ["0"])[0] in ("1", "true", "on")
                nexts = {f["id"]: f.get("next") or "" for f in warm_features()}
                self._send(render_backlog_board(get_backlog(fresh=fresh), path[len("/backlog/"):], nexts))
            elif path == "/todo/board":
                fresh = q.get("fresh", ["0"])[0] in ("1", "true", "on")
                self._send(render_todo_board(get_todo(fresh=fresh), lane=q.get("lane", [None])[0],
                                             state=q.get("state", ["all"])[0], priority=q.get("priority", ["all"])[0],
                                             features=warm_features(), lanes=CFG.get("lanes") or [], root=CFG["root"]))
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
        self._send("GET only", ctype="text/plain", code=405)

    do_PUT = do_DELETE = do_PATCH = _reject

    # --- local writes ---------------------------------------------------------
    # All LOCAL FILES: /connect writes docs/.board/config.json and exists only when the
    # integration is on; the four board writes set a priority token or move an entry in
    # the backlog or a lane's todo file. Nothing else, no other method.
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
    #   4. opt-in - no flag, no route (/connect only; the board writes carry controls 1-3).
    # No CORS header is ever sent, so that preflight fails and no other origin can reach
    # these routes even before the checks run.
    def _json(self, obj, code=200):
        self._send(json.dumps(obj, ensure_ascii=False), ctype="application/json; charset=utf-8", code=code)

    def _write_guard(self):
        """None when the request may write, else (code, reason)."""
        if self.headers.get("Origin") not in (CFG.get("origins") or set()):
            return (403, "origin")
        if (self.headers.get("Content-Type") or "").split(";")[0].strip().lower() != "application/json":
            return (415, "content-type")
        if not self.headers.get(WIDGET_HEADER):
            return (403, "header")
        want = CFG.get("csrf") or ""
        token = self.headers.get(CSRF_HEADER) or ""
        if not want or not hmac.compare_digest(token.encode("utf-8", "surrogateescape"), want.encode("utf-8")):
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
        except (ValueError, UnicodeDecodeError, RecursionError):
            return None
        return payload if isinstance(payload, dict) else None

    def do_POST(self):
        if self._foreign_host():
            return self._json({"ok": False, "error": "host"}, code=403)
        path = urlparse(self.path).path
        if path not in ("/connect",) + BOARD_WRITES:
            return self._reject()          # every other path: GET only
        if path == "/connect" and not connected():
            return self._json({"ok": False, "error": "not found"}, code=404)
        bad = self._write_guard()
        if bad:
            return self._json({"ok": False, "error": bad[1]}, code=bad[0])
        payload = self._body()
        if payload is None:
            return self._json({"ok": False, "error": "bad request"}, code=400)
        if path in BOARD_WRITES:
            return self._board_write(path, payload)
        try:
            app = normalize_origin(payload.get("app"))
            if not app:
                return self._json({"ok": False, "error": "a local http(s) URL is required"}, code=400)
            write_config({"app": app})
            CFG["app"] = app           # a reload picks up the new origin; no restart needed
            return self._json({"ok": True, "app": app})
        except OSError as exc:
            return self._json({"ok": False, "error": "cannot write: %s" % exc}, code=500)

    def _board_write(self, path, payload):
        """A priority or an order write on the backlog or a lane's todo file, through the reader's writers.
        The body names an entry (key, line, and the lane for a todo line), never a file: the root is the
        server's own, and any other key is refused."""
        board, kind = path.split("/")[1:3]
        allowed = {"key", "line", "letter"} if kind == "priority" else {"key", "line", "to", "before"}
        if board == "todo":
            allowed |= {"lane"}
        if set(payload) - allowed:
            return self._json({"ok": False, "error": "unknown field: %s" % ", ".join(sorted(set(payload) - allowed))[:80]}, code=400)
        lane = payload.get("lane") if board == "todo" else None
        if board == "todo" and not isinstance(lane, str):
            return self._json({"ok": False, "error": "lane is required"}, code=400)
        try:
            with _write_lock:            # one write at a time: a read-modify-replace never races another
                ok, msg = self._apply_write(kind, payload, lane)
                with _cache_lock:
                    _gen[(board,)] = _gen.get((board,), 0) + 1
                    _cache.pop((board,), None)  # the board re-reads on its next load
        except Exception as exc:  # the writers refuse rather than raise; this is the last fence
            ok, msg = False, "refused: %s" % type(exc).__name__
        msg = said_backlog.clean(str(msg), 300)
        for r in {os.path.realpath(os.path.abspath(CFG["root"])), os.path.abspath(CFG["root"])}:
            if len(r) > 1:
                msg = msg.replace(r, "<root>")  # a writer error never names an absolute path
        if not ok:
            return self._json({"ok": False, "error": msg}, code=409)
        return self._json({"ok": True, "result": msg})

    def _apply_write(self, kind, payload, lane):
        if kind == "priority":
            return said_backlog.set_priority(CFG["root"], payload.get("letter"), key=payload.get("key"),
                                             line=payload.get("line"), lane=lane)
        return said_backlog.move_entry(CFG["root"], payload.get("key"), payload.get("line"), lane=lane,
                                       to=payload.get("to"), before=payload.get("before"))

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
        sys.stderr.write("said:board stopped, pid %s, port %d\n" % (", ".join(map(str, killed)), port))
        return 0
    sys.stderr.write("said:board: no running server found (port %d)\n" % port)
    return 1


def main():
    ap = argparse.ArgumentParser(description="said:board - local web dashboard (loopback; local-file writes only).")
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
                    help="opt in to the local companion app at URL (loopback only): embed, badges, "
                         "mounts and the app-URL write. Omit and none of it exists.")
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
    CFG["csrf"] = secrets.token_urlsafe(32)  # every launch: the board writes need it, connected or not

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
    sys.stderr.write("said:board, %s, pid %d\n%s, loopback, htmx + daisyUI via CDN\n"
                     "stop: `python3 serve.py stop`  (or Ctrl-C), state: %s\n"
                     % (url, os.getpid(),
                        ("connected, %s, local writes: /connect and the board writes" % CFG["app"])
                        if connected() else "board writes: priority and order on the backlog and todo boards", PIDFILE))
    if not a.no_open:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        sys.stderr.write("\nstopping...\n")
    finally:
        _clear_pidfile()
        httpd.shutdown()
        httpd.server_close()


if __name__ == "__main__":
    main()
