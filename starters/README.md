# SAID starters

A **starter** is a per-stack kit that pre-fills everything the `said` engine needs, so a project adopts SAID with batteries included. The engine (the `said` plugin) is stack-agnostic; a starter is the stack-specific other half. Home: **https://saidkit.dev**.

A starter is the inverse of the [adoption guide](../docs/adoption-guide.md): the guide tells a human how to fill the binding by hand; a starter ships it already filled for one stack.

## The starter contract

A starter is its own cloneable git repo (e.g. a GitHub template) that a new project is scaffolded from. It MUST provide:

| File / dir                        | Purpose                                             | Engine consumer                   |
| --------------------------------- | --------------------------------------------------- | --------------------------------- |
| `docs/features/template.md`       | feature-spec template                               | `said:architect`                  |
| `docs/features/template-tasks.md` | task-log template + discipline                      | `said:architect`, `said:add-task` |
| `docs/qa/feature-qa-checklist.md` | hygiene-gate rules (your `R-*` labels)              | `said:review-qa`                  |
| `docs/adr/`                       | ADR templates + seed decisions                      | all phases (`Refs:`)              |
| `CLAUDE.md` binding section       | command resolution + ADR shortname map + rule vocab | all skills                        |

UI stacks additionally provide:

| File / dir                        | Purpose                                        | Engine consumer                          |
| --------------------------------- | ---------------------------------------------- | ---------------------------------------- |
| `docs/qa/feature-ux-checklist.md` | UX-gate rules + the gate/wire label convention | `said:review-ux`, `said:review-ux-agent` |
| `docs/ux/`                        | interaction / spec rules                       | `said:architect`, `said:review-ux`       |
| `docs/screens/` (optional)        | per-screen spec template                       | `said:uxgen`                             |

Server / CLI / library starters omit the UX pieces and run the spine (Scope → Architect → Implement → Debrief) without the UX gate.

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
