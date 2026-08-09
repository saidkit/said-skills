---
name: retrieval
description: |
  Precedent/decision-record search. When to use: At the start of any `§D` walk, multi-question decision pass, or `scope.md` review; Before walking an agent-produced scope / decision-map / framing with the operator; When the operator asks "is this consistent with prior decisions?" or "did we decide this before?"; When you notice yourself about to propose a default without consulting precedent — STOP, run it, then propose; When the same type of question recurs across sessions (the meta-failure signal — precedent exists but isn't reachable from your usual research path). Also invocable directly via `/said:retrieval` (operator alias `lumos!`). Read-only; each run ends with a retrieval-status stop signal (coverage + goal), so it is loop-ready.
---

# said:retrieval — precedent/decision-record search

Before proposing a default, accepting a spawned-agent's framing, or answering "what's the default for X" — STOP and exhaust the project's decision record first.

## Contract — holds every run

- **Read-only, terminal.** Report and hand back; never edit, never invoke a downstream skill, never act on what you found.
- **Fresh sweep, no carry.** Each run re-searches for the current question; it never makes later answers "automatically precedent-checked".
- **Single-pass; never self-loop.** Run once, emit the status signal, stop. The status is for a driver to read (a future `--exhaustive` sweep) — this skill does not loop itself.
- **Emit the retrieval-status stop signal** (below) at the end of every run.
- **Agnostic.** Adapt to whatever decision-record layout the project uses (`docs/adr/` vs `decision-log/` vs RFCs; `docs/working/` vs `notes/` vs `planning/`). No decision record at all → that is the first finding ("no decision record found — proposing without precedent").

## Invocation

- `/said:retrieval` (operator alias `lumos!`). The proactive triggers live in the frontmatter `description`.

## Procedure — exhaust five sources, in order

1. **`CLAUDE.md`** (project + user-global) — grep for the question's core concepts. Project invariants live here; user-global macros and standing preferences live here. If the project uses R-rule labels (`R-ENGINE`, `R-DEV-TOKEN`, etc.) — grep those too; they're the project's shorthand for cross-cutting invariants and surface in ADR headings + scope.md citations + code comments.
2. **Memory files** — grep `MEMORY.md` index + every `<name>.md` in this project's memory directory. Prior-session feedback, project decisions, references.
3. **ADRs** (or whatever the project's decision-log directory is — `docs/adr/`, `decision-log/`, `architecture/decisions/`, etc.) — grep every file for the question's core concepts. Don't trust an agent's citation chain alone; the agent may have surfaced one ADR but missed a contradicting one.
4. **Prior-feature working dirs** (`docs/working/INIT-*/scope*.md`, `docs/working/FEAT-*/scope*.md`, `*/debrief.md`, `*/accept-*.md`, or project equivalents) — grep for the same concepts. Reuses across features signal precedent; reversals in debriefs signal "scope-time default was wrong."
5. **Prior probe / wire-capture records** (scope.md §A blocks, `wip*.md` files) — for probe-mode / live-system outcomes that the current question depends on. Workarounds (dev tokens, fixture endpoints, env overrides) live here, not in ADRs.

## Output

List what was found per source, with citations. Then:
- If precedent EXISTS → default to it; cite the source; surface conflicts between precedent and the current proposal (especially agent-produced ones) as the FIRST thing in your output.
- If precedent DOES NOT exist → name the gap explicitly; propose a default grounded in adjacent precedents (similar features, related ADRs) AND surface the gap as something the project may want to codify (e.g., as a new ADR or memory entry).

## Retrieval status — the loop-ready stop signal

Close every run with an explicit status block, so a driver (or a future `--exhaustive` sweep) can decide whether another pass is worth it:

- **coverage:** `complete` — all five sources swept and the last pass surfaced no new precedent (dry) · `partial` — sources left unswept, or fresh leads still point outward.
- **goal:** `achieved` — the decision/precedent question is answered · `open` — not yet answered · `none` — search exhausted, no precedent exists (recorded as a gap to codify).
- **retrieval complete: yes | no** — the stop signal. `yes` when `goal: achieved` OR `coverage: complete`; `no` only when coverage is partial AND the goal is still open (another sweep can still surface precedent).
