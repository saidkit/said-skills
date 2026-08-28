# SAID — Scope → Architect → Implement → Debrief

A spec-driven feature-development methodology for Claude Code. SAID turns a thin idea or a messy handoff into a scoped spec, an append-only task log, a TDD-driven implementation, and a closing retrospective — with quality + UX gates between Implement and Debrief.

This is the **engine** (stack-agnostic). Pair it with a per-stack **starter** for batteries-included setup — see [saidkit.dev](https://saidkit.dev) and [`../../starters/README.md`](../../starters/README.md).

## The phase chain

| Phase | Skills | Produces |
|---|---|---|
| **1 — Scope** | `said:scope-grill` (thin idea), `said:scope-refine` (handoff / branch / external product specs) | `scope.md` (purpose / target shape / constraints / open questions) |
| **2 — Architect** | `said:uxtoc` (outline: design-seed early, inspect late), `said:architect`, `said:add-task` | feature spec (recreation contract) + append-only `*.tasks.md` |
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

## Scope honesty — the model under the spine (read this)

- The **spine** — Scope, Architect, Implement, Debrief — is project-agnostic. It uses only file read/write, grep, and a quality-gate command it resolves at runtime. It ports to any stack (TS, Python, Go, …).

Under that spine sits one **surface-agnostic model**. Naming it is what lets a research, CLI, server, or web lane recognize it has the same three legs — just with different content and check-modes.

**The three legs.** Every deliverable, whatever the lane, moves through three:

1. **Intent contract** — *what to build + its shape*: `scope.md` + the design contract (`docs/ux`) + the feature spec's Acceptance Criteria.
2. **Production** — *build it*: `said:impl`.
3. **Evaluation contract + independent gate** — *prove it meets intent*: `docs/qa` (the checkable criteria) + `said:review-qa` / `said:review-ux` / `said:accept` (the judges).

Bound by one **meta-invariant**: *leg 3 is derived from leg 1, pre-committed, artifact-external, and judged by someone other than leg 2.* The producer neither writes nor grades their own acceptance. Collapse evaluation into production and you get a wall of green gates that never checked the built thing against a complete contract.

**The UX contract (`docs/ux`) — the surface-contract triad.** Every lane ships a *surface* a consumer binds to through a *contract* (its `docs/ux` representation contract), and each surface needs three legs of its own: a frozen design contract, an Architect-phase step that **designs** the surface against it, and a runtime gate that **checks** the built surface against it. UX is not special — it is the *web/human-visual* instance of a general pattern. Keep the vocabulary unified ("UX" = the experience of whoever consumes the surface — a developer for an API, an agent for an MCP tool, an operator for a CLI); do **not** split it into a parallel "UX vs DX" machinery. Parameterize it by **`surface-type`** instead:

| `surface-type` | Consumer | Design contract | Gate check-mode |
|---|---|---|---|
| `visual` | a person | list / form / shell / field rules | Playwright / visual parity |
| `api` | a developer | REST shape, error envelope, pagination, versioning | schema conformance / contract-tests / curl |
| `mcp` | an agent | tool naming, input schema, idempotency, error shape | handshake + schema probes |
| `cli` | an operator | flags, exit codes, output format, `--help` | invocation + output assertions |

**The load-bearing guard:** a lane's `SAID.surface-type:` decides whether `said:review-ux` reaches for Playwright or for schema / contract checks. Without that branch an autonomous run tries to Playwright-walk an API, reports it "env-blocked", and ships it unverified. So the gate (`said:review-ux`) and the design step (`said:architect`) both read `SAID.surface-type:` and pick their mode from it — **config in the per-project binding, not a new skill per surface.**

**The QA contract (`docs/qa`) — the evaluation harness.** `docs/qa` is the evaluation *contract*, not the gate: the frozen, per-project, *checkable* definition of what must be verifiably true to accept the work (`feature-qa-checklist.md`; the UX contract's operationalized checklist lives UX-side at `docs/ux/feature-ux-checklist.md`), run by the gates at the Implement→Debrief seam. It is `docs/ux` (+ structural ADR rules + spec Acceptance Criteria) **operationalized into `verify:` predicates** — same intent, two faces: `docs/ux` is the **generative** face (*what it should be*, used to design), `docs/qa` the **evaluative** face (*how we prove it is that*, used to accept). This is the error-correction channel — correctness defined and judged *apart from* the act of producing it. Software has a partial ground-truth backstop (the compiler, the tests); a research- or knowledge-shaped lane has none, so there the pre-committed contract + an independent judge is not merely good practice — it is the *only* backstop there is.

## Conventions the skills rely on

- **The `## Lane` block — the binding unit.** Every per-project axis binds in ONE home: a `## Lane` block in your `CLAUDE.md` (per lane; add a `SAID.lanes:` registry when a feature spans ≥2 lanes). Fields are hardcoded `SAID.<axis>:` keys — declare once; every skill resolves by key-grep (`grep 'SAID.<axis>:'`), never by prose match: `SAID.lane:` · `SAID.docs-root:` · `SAID.code-mount:` (a lane spans mounts; a mount is not a lane) · `SAID.feature-spec:` · `SAID.task-log:` · `SAID.working:` · `SAID.id-shape:` (your own convention, verbatim — a plain `PROJ-01` or a segmented `PROJ-01-BE-07`; recorded, never normalized into sub-fields) · `SAID.adr-prefix:` · `SAID.surface-type:` (`visual|api|mcp|cli`, declared) · `SAID.commands:` (the umbrella gate command; language-neutral). The `said`/`flow`/`status`/`board` skills read lane state from these keys; the task-log stencil (`template-tasks.md`) derives its id-shape from `SAID.id-shape:`. Single lane → `said!`; ≥2 task-log-carrying lanes → `flow!`.
- **Command resolution.** Skills never hardcode `npm`/`bun`/`make`/`cargo`. They resolve the quality-gate command at runtime: `SAID.commands:` (in `CLAUDE.md`) → `Makefile` → `package.json` (per lockfile) → ask you. Make sure your repo exposes one umbrella verifier.
- **Rule labels are the project's, not SAID's.** Skills cite rule labels (shown as `<RULE-LABEL>`) that **your checklists define** — SAID-core ships none of its own. The shipped example checklists include a starting set: gate rules (`R-GATE-*`) and, for `visual` list surfaces, wire probes (`R-WIRE-*`). These came from a real `visual`-surface project and are a **convention the review machinery expects**, not SAID methodology — keep them (easy path) or rename and rewire the emit-sites. Author your own rules as `<RULE-LABEL>`-shaped entries (see the skeletons).
- **Surface-type.** A lane declares the kind of surface it ships — `SAID.surface-type:` ∈ `{visual, api, mcp, cli}` — on the `## Lane` block. Every lane sets it explicitly — it is not inferred. The design step (`said:architect`) and the UX gate (`said:review-ux`) branch on it — so a lane's `SAID.surface-type:`, not a hardcoded browser assumption, decides how its surface is designed and checked (see **Scope honesty** for the full triad + guard).
- **The two contracts — `docs/ux` + `docs/qa`, universal.** Every lane carries both under its docs-root, whatever its surface: `docs/ux` is the **UX / representation** contract (how the surface presents — screens for `visual`, endpoints / error-envelopes for `api`, tool-schemas for `mcp`, flags / exit-codes for `cli`), and `docs/qa` is the **QA / evaluation** contract (the checkable bar). Only their *content* varies by `surface-type`; their presence never does — so `docs/ux` presence is **not** a signal for anything, and there is no `contract-face` axis to configure. Skills resolve both relative to docs-root.
- **Placeholders.** Skill text uses `<PROJECT>`, `<ADR-ID>`, `<RULE-LABEL>`, `<entity>`, `<feature-path>`, `<FEAT-ID>` — your binding table + docs supply the concrete values.

## License

MIT — see [LICENSE](../../LICENSE).
