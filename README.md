# SAID — Software AI Development workflow for Claude Code

**Engine + starters.** Install the engine once; drop in a starter for your stack. Home: **https://saidkit.dev**

SAID organize the context in scalable way for the application to grow. It manages knowledge and specifications (ADRs, features, tasks etc) and provides a robust workflow to deliver features with quality and knowledge management discipline.

SAID workflow drives a feature through four phases — **Scope → Architect → Implement → Debrief** — as a set of Claude Code skills, with quality and UX gates along the way. It ships in two parts.

## 1. The engine — the `said` plugin

Stack-agnostic. **10 skills + 3 subagents** that run the phase chain (`said:scope-refine` → `said:architect` → `said:impl` → `said:debrief`, plus the inter-phases gates and helpers). The engine carries the *method* — it hardcodes nothing about your stack. Commands, ADRs, and rule labels all resolve from your repo at runtime. Full skill catalogue: [`plugins/said/README.md`](plugins/said/README.md).

## 2. The starters — batteries for your stack

A **starter** is a per-stack kit that pre-fills the binding the engine expects, and also templates for best-practices to build a robust software products. So adoption is "install + apply" instead of "read a guide and wire it yourself." Each starter ships pre-set:

- `docs/features/` — feature-spec + task-log templates
- `docs/qa/` — hygiene + UX checklists tuned to the stack
- `docs/ux/` — interaction / spec rules (UI stacks)
- `docs/adr/` — ADR templates + seed decisions
- `CLAUDE.md` binding — command resolution, ADR shortname map, rule vocabulary

The engine runs without a starter — you just fill the binding yourself (the [adoption guide](docs/adoption-guide.md) walks it). A starter is the fast path. The starter contract — what files a starter must provide — is in [`starters/README.md`](starters/README.md).

### Ready-made starters 

| Starter        | Stack                       | Status    | Repo                                  |
| -------------- | --------------------------- | --------- | ------------------------------------- |
| `said-next`    | Next.js / TS                | reference | https://github.com/saidkit/said-next  |
| `said-ts`      | TS services / Bun / MCP     | reference | https://github.com/saidkit/said-ts    |
| `said-python`  | Python (FastAPI) / MCP      | reference | TBD                                   |
| `said-go`      | Go services / MCP           | reference | TBD                                   |
| `said-web`     | React + Vite + TS           | reference | TBD                                   |
| `said-saas`    | Next.js + Supabase for SaaS | roadmap   | -                                     |
| `said-flg`     | Flutter/LiquidGlass         | roadmap   | -                                     |
| `said-fda`     | Flutter/Desktop App         | roadmap   | -                                     |
| `said-swift`   | Native iOS / OSX apps       | roadmap   | -                                     |
| `said-kotlin`  | Native Android apps         | roadmap   | -                                     |

## Install

```bash
# Recommended (CLI)
claude plugin marketplace add saidkit/said-skills
claude plugin install said@saidkit
```

Or in an active Claude Code session: `/plugin marketplace add saidkit/said-skills` → `/plugin install said@saidkit` → `/reload-plugins`.

For your project, clone a per-stack **starter** (or fill the binding by hand — see the [adoption guide](docs/adoption-guide.md)); a `saidkit` scaffolding CLI is on the roadmap.

Skills are then invoked as `said:scope-refine`, `said:architect`, `said:impl`, `said:debrief`, etc.

## Quick start

1. Install the engine.
2. Apply a starter for your stack (or fill the binding by hand per the adoption guide).
3. Walk the chain: `/said:scope-grill <idea>` → `/said:architect` → `/said:impl` → `/said:debrief`.

## What's in this repo

```
said/                                 (engine repo + marketplace-of-one)
├── .claude-plugin/marketplace.json
├── plugins/said/                     the engine
│   ├── .claude-plugin/plugin.json
│   ├── skills/                       10 skills (bare verbs under said:)
│   ├── agents/                       3 subagents
│   └── README.md
├── starters/                         per-stack kits (contract + roadmap)
├── docs/adoption-guide.md            fill the binding by hand (starter-free path)
├── LICENSE                           MIT
└── README.md
```

## License

MIT — see [LICENSE](LICENSE). The **name** "SAID" / "SAIDkit" is a separate trademark matter (the license covers the code/prompts, not the mark).
