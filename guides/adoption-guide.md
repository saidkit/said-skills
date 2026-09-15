# SAID adoption guide -- per-project setup

The SAID skills are deliberately project-agnostic: they carry the _methodology_, not your project's specifics. To make them work in your repo you supply a thin **binding layer** once. This guide is that one-time setup. Budget ~30 minutes.

> **Tip:** a [starter](../starters/README.md) for your stack pre-fills everything below. Use this guide when no starter fits yet, or to understand exactly what a starter provides. Home: https://saidkit.dev.

## Why a binding layer

SAID skills reference things every project has but names differently -- your ADRs, your UX/spec rules, your quality-gate command, your docs layout. Rather than hardcode one project's answers (which would make the skills non-portable), the skills use placeholders (`<ADR-ID>`, `<RULE-LABEL>`, `<PROJECT>`, ...) and read the concrete values from a **`## Lane` block in your repo's `CLAUDE.md`**. You author that binding once; the skills read every value from it as `SAID.<key>:` lines.

## Step 1 -- Adopt the docs layout (or remap it)

SAID's default layout. If yours differs, note the remapping in your `## Lane` block (Step 3, the `SAID.docs-root:` / path keys); the conventions below are the only project paths the skills assume. If you remap `docs-root`, the completeness reviewer resolves the grammar from your `SAID.docs-root:` (`<docs-root>/ux/feature-ux-grammar.md`), so a remapped layout works -- keep the grammar reachable under your docs-root.

| Default path                        | Holds                                                                               |
| ----------------------------------- | ----------------------------------------------------------------------------------- |
| `docs/working/<feature>/`           | transient operator workspace -- `scope.md`, `toc.md`, handoff drafts, probe captures, debriefs |
| `docs/features/<FEAT>.md`           | feature spec (recreation contract)                                                  |
| `docs/features/<FEAT>.tasks.md`     | append-only task log                                                                |
| `docs/adr/`                         | architecture decision records                                                       |
| `docs/ux/feature-ux-rules.md`       | the surface-contract **rule registry** (screen-shape taxonomy + routing the architect/impl skills consume; carries a proof-of-load sentinel) -- required on a surface-bearing lane |
| `docs/ux/feature-ux-grammar.md`     | the per-surface **unit grammar** (one `SC-HEADER` section per surface: `unit`, `containers` in emit order, per-container attribute schema, and a `## Unit-spec stencil`) -- `uxtoc` **emits from it**, the completeness check projects against it; required on a surface-bearing lane |
| `docs/ux/feature-ux-checklist.md`   | UX-gate rules (read by the `web-ux` reviewer for a `web` surface)                   |
| `docs/qa/feature-qa-checklist.md`   | hygiene-gate rules (read by `said:review-qa`)                                        |

## Step 2 -- Get the scaffolding (clone a starter)

The plugin ships **no project files** -- it's the method only. The scaffolding the skills read (`docs/features/` templates, `docs/qa/` + `docs/ux/` checklists + the rule registry + the grammar, `docs/adr/` seeds, source layout) comes from a **starter repo** for your stack, cloned into place:

```bash
# use the starter's GitHub "use this template", or:
npx degit saidkit/said-<stack> my-app
```

No starter for your stack yet? The plain files you can author directly; the **surface-contract files are the involved part** -- copy them from a starter for the nearest surface and adapt, rather than hand-writing from scratch:

- `docs/features/template.md` -- the feature-spec shape `said:architect` writes (the recreation contract). A surface-bearing lane's per-unit design lives inline as `### <Unit> <ID>` sub-sections (or one file per unit under a declared unit-home dir).
- `docs/features/template-tasks.md` -- the append-only task-log shape; carries the discipline + an app-segment vocab token you set to your project's vocab.
- `docs/qa/feature-qa-checklist.md` (+ `docs/ux/feature-ux-checklist.md` for UI stacks) -- your rule set. The gate/wire label convention (`R-GATE-*` / `R-WIRE-*`) is what the review machinery emits; the rest are your own `<RULE-LABEL>` rules citing your ADRs/UX-specs.
- `docs/adr/` -- seed decisions the ADR-shortname table (Step 3) points at.
- **`docs/ux/feature-ux-rules.md` + `docs/ux/feature-ux-grammar.md` (surface-bearing lanes only) -- the surface contract.** Each opens with an `SC-HEADER` proof-of-load sentinel the engine validates (a token + a count it recomputes; a **missing OR malformed** sentinel HALTs). The grammar's sentinel shape is:

  ```
  <!-- SC-HEADER: feature-ux-grammar,surface=web,unit=Screen,unit-home=inline,containers=Columns;Sections;Row actions,token=UXG-WEB-1,count=3 -->
  ```

  (comma-separated; `count` MUST equal the number of `containers`.) The rules registry opens with its own sentinel naming its token + rule count. These two are the newest part of the contract, and a published starter for your stack may not ship them yet -- if your clone's `docs/ux/` has only a checklist, you author them: copy from a starter that ships them, if one exists for your stack, else write them by hand (authoring the full grammar -- `unit` + `containers` in emit order + per-container attribute schema + the `## Unit-spec stencil` `uxtoc` emits from -- is an advanced task). Either way, if you run a surface-bearing lane without them, `said:architect` / `said:uxtoc` HALT with a named redirect telling you exactly what to author -- that HALT (not `/said:setup`, which does not ledger these files) is what catches a missing grammar.

## Step 3 -- Write the `## Lane` block in your `CLAUDE.md`

Add a `## Lane` block the skills read. It is **keys only**: from the first `SAID.` key to the last, every line is a key line, each carrying its whole value on ONE line with **no trailing comment or parenthetical**. A consumer key-greps the value, so an inline note becomes part of it (and corrupts a list value like `SAID.reviewers:`). Put every explanation in the legend BELOW the block, never inside it. A list value (`SAID.reviewers:`, `SAID.lanes:`) is read WHOLE.

```markdown
## Lane

SAID.lane:         <name>
SAID.docs-root:    docs/
SAID.code-mount:   src/
SAID.feature-spec: docs/features/PROJ-01.md
SAID.task-log:     docs/features/PROJ-01.tasks.md
SAID.working:      docs/working/PROJ-01/
SAID.id-shape:     PROJ-01
SAID.adr-prefix:   ADR-<PREFIX>-*
SAID.surface:      web
SAID.reviewers:    [web-ux, completeness]
SAID.commands:     make pre-commit
SAID.profile:      code
SAID.version:      <starter>@<semver>
```

Legend (do NOT paste into the block -- these are notes, not part of any value):

- `SAID.lane` -- the lane name.
- `SAID.docs-root` -- where docs live; the path keys below resolve from it.
- `SAID.code-mount` -- where lane code lives (a lane spans mounts; a mount is not a lane). Comma-separate multiple mounts.
- `SAID.feature-spec` / `task-log` / `working` -- your path patterns (`PROJ-01` is a placeholder id).
- `SAID.id-shape` -- your id convention, verbatim (e.g. `PROJ-01` or `PROJ-01-BE-07`); recorded, never normalized.
- `SAID.adr-prefix` -- your ADR id glob.
- `SAID.surface` -- the lane's medium, one of an OPEN set: `web`, `native`, `cli`, `api`, `mcp`, `audio`, `doc`, ... or `none`. Declared, never inferred; an omitted value HALTs.
- `SAID.reviewers` -- the Checkers that gate this surface, a WHOLE-read list (see Step 4). Required for a surface-bearing lane.
- `SAID.commands` -- your umbrella gate command, language-neutral (e.g. `make pre-commit`, `npm run check`, `cargo test`).
- `SAID.profile` -- the lane's work profile: `code`, `doc`, or `work`.
- `SAID.version` -- which starter you applied, `<starter>@<semver>`, stamped once at setup (optional; a standalone lane not built on a starter omits it).
- Optional axes for special cases: `SAID.lanes:` (a registry, when one feature spans two or more lanes) and `SAID.checkers-dir:` (only when this lane ships its own agent-form Checker -- **declaring it REPLACES the plugin's shipped agents dir, not adds to it**, so a mixed set that also names a shipped Checker like `web-ux` must re-declare it there or drop the name).

Then add three supporting sections to the same `CLAUDE.md`:

**1. `## Earned rules` -- REQUIRED.** A lane whose `CLAUDE.md` has no `## Earned rules` heading HALTs the implement phase at close -- on ANY surface, including `none`. Start with the heading; add rules as they earn their place (an empty-but-present heading is a valid start).

```markdown
## Earned rules

- **R-<AREA>-01** -- <one-line rule> -> <your ADR/spec path>
```

**2. `## Significant ADRs (skill-referenced)` -- recommended.** Bind each skill-cited shortname to YOUR ADR file:

```markdown
## Significant ADRs (skill-referenced)

| Skill shortname       | This project's ADR file                        |
| --------------------- | ---------------------------------------------- |
| feature-structure-ADR | docs/adr/ADR-<PREFIX>-NN-feature-structure.md  |
| service-adapter-ADR   | docs/adr/ADR-<PREFIX>-NN-service-adapter.md    |
| earn-its-place-ADR    | docs/adr/ADR-<PREFIX>-NN-no-mega-components.md  |
```

**3. `## Claude Code Reminders` -- recommended.** Carry the drive line: "before each implementation step, re-read `## Earned rules` and name the ids you apply."

That block + these sections are the contract. The skills resolve every `<ADR-ID>` / `<RULE-LABEL>` / path / command through them.

## Step 4 -- Declare your surface + reviewers (what gates the work)

The lane declares two things: `SAID.surface:` (what this lane IS) and `SAID.reviewers:` (which Checkers gate it). A Checker is either **agent-form** (a shipped subagent you just NAME) or **recipe-form** (a block you DECLARE in your own `docs/ux/feature-ux-rules.md`). Either form is no engine edit -- but a name in `SAID.reviewers:` that resolves to no Checker makes the gate a BLOCKER (it would report a nominal pass while running nothing), so every name must resolve.

Common pairings:

| `SAID.surface:` | `SAID.reviewers:`        | Checker form + what it does |
| --------------- | ------------------------ | --------------------------- |
| `web`           | `[web-ux, completeness]` | `web-ux` (agent-form, shipped): Playwright visual/interaction parity vs `feature-ux-checklist.md`. `completeness` (recipe-form -- YOU declare it, see below): the `uxtoc` outline is fully built, per the grammar. |
| `cli`           | `[cli-gate]`             | `cli-gate` (agent-form, shipped): structural + eval gate over the shipped command surface. |
| `doc`           | `[doc-editorial]`        | `doc-editorial` (agent-form, shipped): editorial review over the shippable artifacts (also loads `docs/qa/feature-qa-checklist.md`). |
| `api` / `mcp`   | `[<your-checker>]`       | **No Checker ships for these yet** -- author one. Prefer a **recipe-form** block in your registry (schema/contract checks; additive to the shipped Checkers). An agent-form Checker is possible but needs `SAID.checkers-dir:` (mind its replacement caveat in the Step-3 legend). |
| `none`          | `[]`                     | no surface reviewer runs (a non-surface lane). |

Only `web-ux`, `cli-gate`, and `doc-editorial` ship as agent-form Checkers you name directly. `completeness` is **recipe-form** -- it does not exist until you declare it in `docs/ux/feature-ux-rules.md` as a Checker block:

```markdown
said-checker:   completeness
said-governs:   surface=<your surface>
said-capture:   process-spawn
said-judge:     oracle
said-recompute: python3 "$SAID_PLUGIN_ROOT/skills/status/said_completeness.py"
```

Adapt that block into your `docs/ux/feature-ux-rules.md`, instantiating `said-governs: surface=` to your medium (a left-in `<...>` is a config-error gate FAIL). `said-capture: process-spawn` means an oracle-tier container is verified by executing a read-only probe **when your capture manifest supplies a per-unit `cmd:`** -- for a **cli** lane that probe is the command's own `--help` (nothing extra to wire); for a **web** lane it is a DOM/route probe your lane supplies under its own cycle. **Absent a probe `cmd:`, the container falls to declared-evidence honestly** (read from the manifest's `built:` lines, reported as such) -- so the block applies one-shot on any surface and auto-strengthens to the oracle tier once you add a probe. Naming `completeness` in `SAID.reviewers:` WITHOUT this block makes the gate a BLOCKER.

Prerequisites by Checker:
- **`web-ux`** needs a running dev server URL the task ships to, a **seeded reference fixture** (visual-parity walks fail against an empty/404 backend -- provision seed data first), and a way to mint a dev auth token if the app is gated (document the recipe in your `## Lane` block).
- **`completeness`** needs the Checker block above + `docs/ux/feature-ux-grammar.md` (the per-surface section) + a `uxtoc` `toc.md`; it re-derives the designed element set from the outline + grammar and checks it against the built surface. On a surface-bearing lane an absent grammar HALTs -- surface-gated, never version-gated.
- **`cli-gate` / `doc-editorial` / your api Checker** need whatever their `verify:` / `said-recompute:` actions call for (a built binary, the shippable docs, a reachable endpoint + schema).

A surface-bearing lane does not skip its gate: if it declares a surface, its reviewers run -- so every reviewer named must resolve to a real Checker.

## Step 5 -- Smoke-test

First, check the binding itself is well-formed:

```
/said:setup
```

It ledgers your `## Lane` block + required sections against the current axis set and names any BLOCKER / STALE / ADVISORY with a fix -- the deterministic way to catch a missing key, a stale axis, an unresolved reviewer, or an absent `## Earned rules` before you run a phase. Resolve any BLOCKER, then:

```
/said:scope-grill a tiny throwaway feature
```

Confirm it writes `docs/working/<feature>/scope.md` in your layout. If it asks for paths you haven't bound, fill them into your `## Lane` block (Step 3) and retry. Then `/said:status` should show the feature in the Scope phase.

## What ships generic vs what you own

- **Ships generic (don't edit in the plugin):** the said:* skills + agents (currently 17 skills + 6 agents) -- all placeholder-driven. The plugin ships no project files; scaffolding comes from your starter.
- **You own (per project):** the `## Lane` block, your `## Earned rules`, your ADRs / UX-specs / rule registry / grammar, the filled checklists, your docs layout -- all yours; the plugin ships none of it.
