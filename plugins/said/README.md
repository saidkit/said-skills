# SAID — Scope → Architect → Implement → Debrief

A spec-driven feature-development methodology for Claude Code. SAID turns a thin idea or a messy handoff into a scoped spec, an append-only task log, a TDD-driven implementation, and a closing retrospective — with quality + UX gates between Implement and Debrief.

This is the **engine** (stack-agnostic). Pair it with a per-stack **starter** for batteries-included setup — see [saidkit.dev](https://saidkit.dev) and [`../../starters/README.md`](../../starters/README.md).

## The phase chain

| Phase | Skills | Produces |
|---|---|---|
| **1 — Scope** | `said:scope-grill` (thin idea), `said:scope-refine` (handoff/branch), `said:uxgen` (external product specs) | `scope.md` (purpose / target shape / constraints / open questions) |
| **1.5 — Inspect** | `said:uxtoc` | descriptive spec outline for fast iteration |
| **2 — Architect** | `said:architect`, `said:add-task` | feature spec (recreation contract) + append-only `*.tasks.md` |
| **3 — Implement** | `said:impl`, `said:review-ux` | tasks driven Todo → Done under TDD, per-task UX gate |
| **3.5 — Gates** | `said:review-qa` (hygiene), `said:accept` (acceptance contract) | pass/fail reports |
| **4 — Debrief** | `said:debrief` | retrospective + backports + shipping reports |
| **Helper** | `said:triage` | read-only root-cause investigation |
| **Observe** | `said:status` (terminal), `said:board` (local web dashboard) | read-only status board — where every feature sits in the phase chain, what's stalled, and the exact command that advances it |
| **Recall** | `said:retrieval` | precedent/decision-record search: what the project already decided (`CLAUDE.md` · memory · ADRs · working dirs · probes), before you propose a default |
| **Orchestrate** | `said:said` (single feature), `said:flow` (multi-lane) | drive a feature through the whole chain in one session to a printed `goal: done` signal — invoked by the `said!` / `flow!` operator macros |

### Subagents (spawned by the skills)

- `said:scope-refine-agent` — Phase-1 parallel codebase audit + wire/visual probes.
- `said:scope-audit` — the 5-section per-directory audit shape the refine agent follows inline.
- `said:review-ux-agent` — Phase-3 per-task UX verification against your UX checklist.

## Quick start

1. Install the plugin (see the [marketplace README](../../README.md)).
2. Set up the repo: clone a [starter](../../starters/README.md) for your stack (scaffolding pre-filled), or supply the binding by hand per the [adoption guide](../../guides/adoption-guide.md). **The skills need this scaffolding to be useful.**
3. Start a feature: `/said:scope-grill <your idea>` (or `/said:scope-refine <handoff-doc>`), then walk the chain.

## Scope honesty (read this)

- The **spine** — Scope, Architect, Implement, Debrief — is project-agnostic. It uses only file read/write, grep, and a quality-gate command it resolves at runtime. It ports to any stack (TS, Python, Go, …).
- The **UX gate** — `said:review-ux` + the `said:review-ux-agent` agent + the UX checklist — is currently **web-app-oriented** (it assumes browser surfaces, UI screen shapes, and Playwright-driven visual parity). Server/CLI/library projects run the spine and **adapt or skip** the UX gate. A non-web review sibling is a future addition.

## Conventions the skills rely on

- **Command resolution.** Skills never hardcode `npm`/`bun`/`make`/`cargo`. They resolve the quality-gate command at runtime: `CLAUDE.md` Development-Commands → `Makefile` → `package.json` (per lockfile) → ask you. Make sure your repo exposes one umbrella verifier.
- **Rule labels are the project's, not SAID's.** Skills cite rule labels (shown as `<RULE-LABEL>`) that **your checklists define** — SAID-core ships none of its own. The shipped example checklists include a starting set: gate rules (`R-GATE-*`) and, for web list surfaces, wire probes (`R-WIRE-*`). These came from a real web project and are a **convention the review machinery expects**, not SAID methodology — keep them (easy path) or rename and rewire the emit-sites. Author your own rules as `<RULE-LABEL>`-shaped entries (see the skeletons).
- **Placeholders.** Skill text uses `<PROJECT>`, `<ADR-ID>`, `<RULE-LABEL>`, `<entity>`, `<feature-path>`, `<FEAT-ID>` — your binding table + docs supply the concrete values.

## License

MIT — see [LICENSE](../../LICENSE).
