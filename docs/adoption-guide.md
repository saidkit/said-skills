# SAID adoption guide — per-project setup

The SAID skills are deliberately project-agnostic: they carry the _methodology_, not your project's specifics. To make them work in your repo you supply a thin **binding layer** once. This guide is that one-time setup. Budget ~30 minutes.

> **Tip:** a [starter](../starters/README.md) for your stack pre-fills everything below. Use this guide when no starter fits yet, or to understand exactly what a starter provides. Home: https://saidkit.dev.

## Why a binding layer

SAID skills reference things every project has but names differently — your ADRs, your UX/spec rules, your quality-gate command, your docs layout. Rather than hardcode one project's answers (which would make the skills non-portable), the skills use placeholders (`<ADR-ID>`, `<RULE-LABEL>`, `<PROJECT>`, …) and read the concrete values from **your repo's `CLAUDE.md`** (or a dedicated `docs/SAID.md`). You author that binding once.

## Step 1 — Adopt the docs layout (or remap it)

SAID's default layout. If yours differs, note the remapping in your binding table (Step 3); the conventions below are the only project paths the skills assume.

| Default path                      | Holds                                                                               |
| --------------------------------- | ----------------------------------------------------------------------------------- |
| `docs/working/<feature>/`         | transient operator workspace — `scope.md`, handoff drafts, probe captures, debriefs |
| `docs/features/<FEAT>.md`         | feature spec (recreation contract)                                                  |
| `docs/features/<FEAT>.tasks.md`   | append-only task log                                                                |
| `docs/adr/`                       | architecture decision records                                                       |
| `docs/ux/`                        | UX / interaction specs (web projects)                                               |
| `docs/qa/feature-qa-checklist.md` | hygiene-gate rules (read by `said:review-qa`)                                       |
| `docs/qa/feature-ux-checklist.md` | UX-gate rules (read by `said:review-ux` / `said:review-ux-agent`)                   |

## Step 2 — Get the scaffolding (clone a starter)

The plugin ships **no project files** — it's the method only. The scaffolding the skills read (`docs/features/` templates, `docs/qa/` checklists, `docs/adr/` seeds, `docs/ux/` specs, source layout) comes from a **starter repo** for your stack, cloned into place:

```bash
# use the starter's GitHub "use this template", or:
npx degit saidkit/said-<stack> my-app
```

No starter for your stack yet? Author the files the skills expect, using an existing starter (e.g. `said-web`) as the reference for each shape:

- `docs/features/template.md` — the feature-spec shape `said:architect` writes (the recreation contract).
- `docs/features/template-tasks.md` — the append-only task-log shape; carries the discipline + an app-segment vocab token you set to your project's vocab.
- `docs/qa/feature-qa-checklist.md` (+ `docs/qa/feature-ux-checklist.md` for UI stacks) — your rule set. The gate/wire label convention (`R-GATE-*` / `R-WIRE-*`) is what the review machinery emits; the rest are your own `<RULE-LABEL>` rules citing your ADRs/UX-specs.
- `docs/adr/` — seed decisions the binding table (Step 3) points at.

## Step 3 — Write the binding table in your `CLAUDE.md`

Add a section your skills can read. Minimum contents:

```markdown
## SAID bindings

### Quality-gate command

- Umbrella verifier: `make pre-commit` # or `npm run check`, `cargo test`, etc.
  (skills also auto-resolve via Makefile / package.json if this is absent)

### ADR shortname -> file

| Skill shortname        | This project's ADR file                |
| ---------------------- | -------------------------------------- |
| feature-structure-ADR  | docs/adr/ADR-XXX-feature-structure.md  |
| service-adapter-ADR    | docs/adr/ADR-XXX-service-adapter.md    |
| earn-its-place-ADR     | docs/adr/ADR-XXX-no-mega-components.md |
| entity-granularity-ADR | docs/adr/ADR-XXX-entity-triad.md       |
| <add your own>         | ...                                    |

### Rule-label scheme (optional)

- We label frozen UX/spec rules as `R-<AREA>-<N>` (e.g. `R-CHECKOUT-3`, `R-PROFILE-7`). Skills cite these
  as `<RULE-LABEL>`; substitute your real labels when authoring specs.

### Docs layout overrides (only if you deviate from SAID defaults)

- e.g. specs live under `planning/` not `docs/features/`.
```

That table is the contract. The skills resolve every `<ADR-ID>` / `<RULE-LABEL>` / command through it.

## Step 4 — (Web projects) confirm the UX-gate prerequisites

`said:review-ux` runs Playwright-driven visual parity and curl wire-probes. For those tasks to pass, ensure:

- a running dev server URL the task ships to,
- a **seeded reference fixture** (visual-parity walks fail against an empty/404 backend — provision seed data first),
- a way to mint a dev auth token if your app is gated (document the recipe in your binding section).

Server/CLI/library projects: skip this step and run the spine without the UX gate.

## Step 5 — Smoke-test

```
/said:scope-grill a tiny throwaway feature
```

Confirm it writes `docs/working/<feature>/scope.md` in your layout. If it asks for paths you haven't bound, fill them into Step 3 and retry.

## What ships generic vs what you own

- **Ships generic (don't edit in the plugin):** the 10 skills + 3 agents — all placeholder-driven. The plugin ships no project files; scaffolding comes from your starter.
- **You own (per project):** the binding table, your ADRs/UX-specs, the filled checklists, your docs layout. Upgrading the plugin never touches these.
