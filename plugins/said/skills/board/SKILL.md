---
name: board
description: >
  SAID status board — LOCAL WEB dashboard (browser sibling of /said:status):
  List + Kanban views, live refresh, click-through deep-dive. Self-contained
  stdlib server; htmx + daisyUI from a CDN; read-only, loopback. Triggered ONLY
  by "/said:board [stop] [--port N] [--stale] [--lane …]" — `stop` kills the
  running server. DEPENDS on the said:status skill (imports its said_status.py).
  NOT the terminal board ("/said:status"); NOT for driving a phase.
---

# said:board — the SAID status board as a local web dashboard

The browser sibling of `/said:status`: it reuses `said:status`'s `analyze()` and serves it as a live
local page — **List + Kanban** views, filters, click-through deep-dive.

Read-only by contract: GET-only, `127.0.0.1`-only, derive-never-store, and `Next` is copyable text
(never a button that runs `/said:impl`). It **depends on the sibling `said:status` skill** (imports
its `said_status.py`) — that skill must be present.

## When this fires

- `/said:board` — launch the dashboard and open the browser.
- `/said:board stop` — stop the running server (by its pidfile / port).
- `/said:board --port N` · `--stale` · `--lane …` — loopback port + analyzer flags (same vocabulary
  as `/said:status`), forwarded to `analyze()`.

## Step 0 — Resolve conventions (declaration-first)

Identical to `/said:status` Step 0: resolve docs/working roots, issued id-prefixes, and lanes
**declaration-first from `CLAUDE.md`** (glob fallback), and state what resolved. These become
`serve.py` flags, forwarded verbatim to `analyze()`.

## Step 1 — Launch (or stop) the server

```bash
# launch
python3 <skill-dir>/serve.py --root <repo-root> [--prefixes APP,INIT] \
  [--legacy-prefixes FEAT,CONF] [--lane NAME:…]... [--port <n>] [--no-open]
# stop
python3 <skill-dir>/serve.py stop [--port <n>]
```

- On launch it binds `127.0.0.1:<port>`, **prints the URL + pid**, writes a state file
  (`$TMPDIR/said-board.json` = `{pid, port, url, started}`), and opens the browser.
- **Report the URL + pid to the operator.** The server runs until stopped — do not block on it or
  tail it; hand back the URL and stop.
- **`stop`** reads that state file (or falls back to the port's listener) and kills the server;
  report what was stopped. Prefer `/said:board stop` over a manual `pkill`.
- If `python3` or the sibling `said:status` analyzer is missing, say so and stop — never hand-render
  a web page.

## Architecture

One deterministic core, two surfaces (terminal + web); htmx + daisyUI from a CDN, loaded
non-blocking. The web surface never re-derives status — it imports `said:status`'s `analyze()`, so
the numbers match the terminal board exactly.

## Anti-patterns

- **Don't add write/POST routes or action buttons.** Read-only, GET-only.
- **Don't bind `0.0.0.0`.** Loopback only.
- **Don't add a build step, `npm install`, or a bundler.** htmx + daisyUI come from a CDN; the
  server is stdlib-only. No local web build, ever.
- **Don't reintroduce a render-blocking CDN `<script>`** (e.g. the Tailwind Play CDN) — it hangs the
  page when the CDN is slow/unreachable. htmx is `defer`; daisyUI is a plain stylesheet.
- **Don't reimplement `analyze()`.** Import `said:status`'s — the numbers must match the terminal
  board exactly.
- **Don't hardcode `docs/features` / a project prefix / a project name.** Resolve in Step 0.

## Hard exit

The skill launches (or stops) the server and reports the URL + pid. The operator drives the browser;
`/said:board stop` (or Ctrl-C) stops it. The skill never proceeds into a phase and never mutates an
artifact.
