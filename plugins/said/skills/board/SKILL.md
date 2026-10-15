---
name: board
description: >
  SAID status board — LOCAL WEB dashboard (browser sibling of /said:status):
  List + Kanban views, manual refresh, per-lane view, click-through deep-dive. Self-contained
  stdlib server; htmx + daisyUI from a CDN; read-only and loopback by default. Triggered ONLY
  by "/said:board [stop] [--port N] [--stale] [--lane ...] [--connect URL]" — `stop` kills the
  running server, `--connect` opts in to a local companion app (embed + Backlog view + two
  local-file writes). DEPENDS on the said:status skill (imports its said_status.py).
  NOT the terminal board ("/said:status"); NOT for driving a phase.
---

# said:board — the SAID status board as a local web dashboard

The browser sibling of `/said:status`: reuse `said:status`'s `analyze()` and serve it as a live local
page — **List + Kanban** views, filters, click-through deep-dive. One deterministic core, two
surfaces; the web numbers match the terminal board exactly because it imports the same `analyze()`.

## Contract — holds every run

- **Loopback, and read-only by default.** Bind `127.0.0.1` only; nothing on the network, no
  downstream skill invoked, no artifact mutated. Without `--connect` there are **no write routes at
  all** — GET only, exactly as it has always shipped.
- **Opt-in integration.** `--connect <url>` points the board at a **local companion app** and adds
  the embed, the cache-fed comment badges, the Backlog view and two local-file writes. Nobody who
  did not ask for it gets any of it: no script tag, no mount points, no extra routes.
- **The board writes local files; the app talks to the remote.** Even connected, the board holds no
  credential, makes no network call of its own, and proxies nothing. The browser talks to the app;
  the board only ever touches the working tree.
- **Derive on refresh, cache until the next one.** `analyze()` runs only on an explicit refresh — a full
  page load or the header button — and the result is cached until the next such refresh; non-fresh
  requests (deep-dive clicks, lane switches) reuse it, so navigating the board never re-runs git. A
  single-flight guard collapses the page-load fan-in onto one run.
  `Next` is copyable text, never a button that runs `/said:impl`.
- **Depends on `said:status`.** Import its `said_status.py` (`analyze()`, `feature_tasks()`) — never
  reimplement the derivation; the web numbers must match the terminal board. If that analyzer or
  `python3` is missing, say so and stop — never hand-render a web page.
- **Hard exit.** Launch (or stop) the server, report URL + pid, hand back. Never block on it, never
  proceed into a phase, never mutate an artifact.

## Invocation

- `/said:board` — launch the dashboard and open the browser.
- `/said:board stop` — stop the running server (by its pidfile / port).
- `/said:board --port N`, `--stale`, `--lane ...` — loopback port + analyzer flags (same vocabulary
  as `/said:status`), forwarded to `analyze()`.
- `/said:board --connect http://localhost:3000` — opt in to the companion app at that URL (loopback
  URLs only). Persisted by the board's own connect form; a later launch with no flag reuses it.
- `/said:board --todo-file docs/todo.md` — where the Backlog view reads and appends (that is the default).

## Step 0 — Resolve conventions (declaration-first)

Identical to `/said:status` Step 0: resolve docs/working roots, issued id-prefixes, and lanes
**declaration-first from `CLAUDE.md`** (lanes from its `SAID.lanes:` registry via the status skill's `--registry`, count echoed, where one is declared; glob fallback only where none is), and state what resolved. These become
`serve.py` flags, forwarded verbatim to `analyze()`.

## Step 1 — Launch (or stop) the server

```bash
# launch
python3 <skill-dir>/serve.py --root <repo-root> [--prefixes PROJ,LEGACY] \
  [--legacy-prefixes LEGACY] [--lane NAME:...]... [--port <n>] [--no-open] \
  [--connect http://localhost:3000] [--todo-file docs/todo.md]
# stop
python3 <skill-dir>/serve.py stop [--port <n>]
```

- On launch it binds `127.0.0.1:<port>`, **prints the URL + pid**, writes a state file
  (`$TMPDIR/said-board.json` = `{pid, port, url, started}`), and opens the browser.
- **Report the URL + pid to the operator**, then hand back — the server runs until stopped; do not
  block on it or tail it.
- **`stop`** reads that state file (or falls back to the port's listener) and kills the server;
  report what was stopped. Prefer `/said:board stop` over a manual `pkill`.
- Connected, the printed URL uses `localhost` rather than `127.0.0.1` **on purpose**: a browser treats
  the two as different hosts, so a session cookie the app set on one is simply not sent from the
  other — which looks like broken sign-in rather than like a configuration mistake. Serve and browse
  both sides on `localhost`.

## The integration (only with `--connect`)

### Local state — one root, `docs/.board/`

```
docs/.board/                 machine-local, gitignore it, safe to delete whole
├── config.json              {"app": "http://localhost:3000", "todo": "docs/todo.md"}
└── cache/index.json         comment counts for the badges
```

Nothing here is a record: the task file is the record, this is a cache and a config in front of it.
Deleting the tree loses nothing. The board reads `config.json` at launch (the `--connect` flag wins
over it) and writes it from the connect form.

### The embed contract

When connected, the page emits — and nothing else changes:

```html
<meta name="said-board-csrf" content="...">
<link rel="stylesheet" href="<app>/embed/said-widgets.css">
<script src="<app>/embed/said-widgets.js" defer data-said-origin="<app>"></script>

<div data-said-widget="status"></div>                      <!-- header, right zone -->
<div data-said-widget="thread" data-scope="feature" data-feature="PROJ-01"></div>
<div data-said-widget="thread" data-scope="task"
     data-feature="PROJ-01" data-task="PROJ-01-07"></div>  <!-- end of each task body -->
<div data-said-widget="backlog"></div>                     <!-- the Backlog view -->
```

The board emits the mount points and nothing more; the companion app's bundle finds them and
hydrates them. `data-said-origin` is the only place the app's origin is written — no port is
hardcoded anywhere. A mount point that never hydrates is an empty div, so a missing or broken bundle
costs the board nothing.

### Badges come off disk, never off a wire

`docs/.board/cache/index.json` feeds the muted mono chip in the task summary row and beside the id
in the deep-dive head:

```json
{"generated": "2026-01-31T09:12:00Z",
 "features": {"PROJ-01": {"comments": 7, "unread": 2,
                          "tasks": {"PROJ-01-07": {"comments": 3, "unread": 1}}}}}
```

Reading a file keeps the board's contract intact (no network call), makes the badges instant, and
keeps them true when whatever writes the cache is unavailable. **Zero renders nothing** — a task
nobody discussed gains no chip — and a missing, unreadable, malformed or stale cache also renders
nothing, never an error.

### The Backlog view

A third segment joins the header toggle — `List | Kanban | Backlog` — and shows the **local todo
file**, read-only, in the task-row idiom (`- [ ] item`, `- [x] item`, `#` headings as section
labels). The shared intake, if the app has one, arrives through the `backlog` mount point beside it.
One lane at a time and the keyboard model are untouched; the Backlog list has no row cursor.

### The two local writes, and the four controls they carry

`POST /connect` writes `docs/.board/config.json`. `POST /todo` appends one line to the local todo
file. That is the entire write surface: no other route, no other method, and **nothing at all when
the integration is off** (both answer 404).

A loopback server has no authentication, which was safe while it was GET-only. It stops being safe
the moment it accepts a write: any page in any tab can POST cross-origin to a localhost port, and a
form-encoded post is a *simple* request — the browser sends it with no preflight, and refusing to
hand back the response does not undo the side effect. So both routes require, **together**:

1. an **`Origin` check** against the board's own origins — the load-bearing control, compared against
   a fixed set rather than the request's `Host`, so a domain that resolves to loopback still fails;
2. a **CSRF token** minted into the page and sent back as `X-Said-Board-Csrf`;
3. **`Content-Type: application/json` plus the custom `X-Said-Board` header** — neither is producible
   by a cross-site form post, so a preflight becomes mandatory and control 1 actually runs (no CORS
   header is ever sent, so that preflight fails);
4. **opt-in** — no flag, no route.

Bodies are bounded and both targets come from the server's own configuration, so a request never
supplies a path.

## Anti-patterns

- **Don't add a third write route, and don't add one without all four controls.** Two local-file
  writes, both opt-in. Everything else is GET.
- **Don't give the board a credential or a network call.** No device token, no proxying the app's
  remote, no fetch from the Python side. The browser talks to the app; the board reads and writes
  local files.
- **Don't make the integration default-on.** A plain install must be byte-for-byte the read-only
  board: no script tag, no mount points, no extra routes.
- **Don't fetch badge counts.** They come from the cache file, so they are instant and survive the
  app being down.
- **Don't bind `0.0.0.0`.** Loopback only.
- **Don't add a build step, `npm install`, or a bundler.** htmx + daisyUI come from a CDN; the
  server is stdlib-only. No local web build, ever.
- **Don't reintroduce a render-blocking CDN `<script>`** (e.g. a CSS-framework play CDN) — it hangs
  the page when the CDN is slow/unreachable. htmx is `defer`; daisyUI is a plain stylesheet.
- **Don't reimplement `analyze()`.** Import `said:status`'s — the numbers must match the terminal
  board exactly.
- **Don't hardcode `docs/features` / a project prefix / a project name.** Resolve in Step 0.
