# SAID starters

A **starter** is a per-stack kit that pre-fills everything the `said` engine needs, so a project adopts SAID with batteries included. The engine (the `said` plugin) is stack-agnostic; a starter is the stack-specific other half. Home: **https://saidkit.dev**.

A starter is the inverse of the [adoption guide](../guides/adoption-guide.md): the guide tells a human how to fill the binding by hand; a starter ships it already filled for one stack.

## The starter contract

A starter is its own cloneable git repo (e.g. a GitHub template) that a new project is scaffolded from. It MUST provide:

| File / dir                        | Purpose                                             | Engine consumer                   |
| --------------------------------- | --------------------------------------------------- | --------------------------------- |
| `docs/features/template.md`       | feature-spec template                               | `said:architect`                  |
| `docs/features/template-tasks.md` | task-log template + discipline                      | `said:architect`, `said:add-task` |
| `docs/qa/feature-qa-checklist.md` | hygiene-gate rules (your `R-*` labels)              | `said:review-qa`                  |
| `docs/adr/`                       | ADR templates + seed decisions                      | all phases (`Refs:`)              |
| `CLAUDE.md` bindings              | Lane, id-shape, surface-type, rules, ADR short map  | all skills                        |


## Representation contract

Every surface additionally ships its representation contract — content per `surface-type`. A non-visual surface ships `docs/ux` too, with endpoint / schema / flag rules instead of screens - UX here means what consumer actually sees.

- `docs/ux/`
  - Engine consumer: `said:architect`, `said:review-ux`
  - Purpose: the surface's design rules (screens for `visual`; endpoint / schema / flag rules for non-visual)
- `docs/ux/evaluation.md`
  - Engine consumer: `said:review-ux`, `said:review-ux-agent`
  - Purpose: UX-gate checklist (the `docs/ux` rules operationalized into `verify:` predicates) + the gate/wire label convention

Non-visual starters (server / CLI / library / MCP) still ship a `docs/ux` — its *content* is their surface's contract (endpoint / error-envelope rules for `api`, tool-schemas for `mcp`, flags / exit-codes for `cli`), not screen rules — and declare their lane's `surface-type` accordingly. `said:review-ux` gates against that surface's contract (schema / handshake / invocation) instead of a browser walk. A surface that lacks a `docs/ux` is a project deficiency the framework surfaces, not a supported mode.

## Starters

| Starter        | Stack                       | Status    | Repo |
| -------------- | --------------------------- | --------- | ---- |
| `said-next`    | Next.js + TS monorepo       | reference | TBD  |
| `said-saas`    | Next.js + Supabase for SaaS | roadmap   | -    |
| `said-ts`      | TS services / Bun / MCP     | reference | TBD  |
| `said-python`  | Python (FastAPI) / MCP      | reference | TBD  |
| `said-go`      | Go services / MCP           | reference | TBD  |
| `said-web`     | React + Vite + TS           | reference | TBD  |
| `said-rust-dx` | Rust Apps (Dioxus)          | roadmap   | -    |
| `said-tauri`   | Tauri Apps                  | roadmap   | -    |
| `said-swift`   | Native iOS / OSX apps       | roadmap   | -    |
| `said-kotlin`  | Native Android apps         | roadmap   | -    |

## Building a starter

1. Fork an existing starter (e.g. `said-next`) as your base, or author the docs from scratch per the contract above.
2. Specialize each for the stack — real ADRs, real checklist rules (your own `R-*` labels), command resolution for the toolchain.
3. Author the `CLAUDE.md` binding section (the contract in the adoption guide).
4. Validate end-to-end: install the engine, apply the starter to a scratch repo, run a throwaway feature `/said:scope-grill` → `/said:debrief`.

Starters are the main way to extend SAIDkit — contributions welcome at https://saidkit.dev.
