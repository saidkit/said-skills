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

The browser sibling of `/said:status`: reuse `said:status`'s `analyze()` and serve it as a live local
page — **List + Kanban** views, filters, click-through deep-dive. One deterministic core, two
surfaces; the web numbers match the terminal board exactly because it imports the same `analyze()`.

## Contract — holds every run

- **Read-only, GET-only, loopback.** Bind `127.0.0.1` only; no write/POST routes, no mutation, no
  downstream skill invoked, nothing on the network.
- **Derive, never store.** Every request re-runs `analyze()`; no server-side board cache. `Next` is
  copyable text, never a button that runs `/said:impl`.
- **Depends on `said:status`.** Import its `said_status.py` (`analyze()`, `feature_tasks()`) — never
  reimplement the derivation; the web numbers must match the terminal board. If that analyzer or
  `python3` is missing, say so and stop — never hand-render a web page.
- **Hard exit.** Launch (or stop) the server, report URL + pid, hand back. Never block on it, never
  proceed into a phase, never mutate an artifact.

## Invocation

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
- **Report the URL + pid to the operator**, then hand back — the server runs until stopped; do not
  block on it or tail it.
- **`stop`** reads that state file (or falls back to the port's listener) and kills the server;
  report what was stopped. Prefer `/said:board stop` over a manual `pkill`.

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
