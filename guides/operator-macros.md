# Operator macros

The `said` plugin ships its skills; the **macro block that drives them from one line** — `said!!`, `flow!!` and the `task-comments!!` shorthand — lives in **[`guides/CLAUDE.md`](./CLAUDE.md)** beside this file. That is the single source; this page keeps **no copy of the macros**, it only explains what the block is and how to install it.

A Claude Code plugin cannot add text to your `CLAUDE.md`, and a macro is the orchestration layer a skill cannot provide for itself: it forces the skill's first call (`said!!` = `Skill(said:said)`, `flow!!` = `Skill(said:flow)`), says how that call composes with an autonomy grant, and names the loop's stop signal — the `goal:` line the orchestrator prints every turn.

Without the block the skills still work — you invoke them as `/said:said <feature-id>` and `/said:flow <feature-id>`. With it, `said!! <directive>` (or `<directive> as said!!`) runs the whole chain, and the `goal:` line it prints is the completion condition a plain `/goal` loop runs to.

## Install

Paste the contents of **[`guides/CLAUDE.md`](./CLAUDE.md)** (beside this file) into **`~/.claude/CLAUDE.md`** (applies to every project) or a project's **`./CLAUDE.md`** (that project only).

## Notes

- **The autonomy verbs come from MagicKit.** `said!!` and `flow!!` name `run!!` and `proceed!!` in their Compose slot; those live in the [MagicKit macro block](https://github.com/saidkit/magic-skills/blob/main/guides/operator-macros.md). Without it the orchestrators still run; they confirm at each stage instead of reporting and proceeding.
- **`task-comments!!` is the source-comment rule** the orchestrators apply during impl: a reference comment is a task id plus a very short why, nothing more; the rationale lives in the task body or a decision record.
- **`!!` is the operator-macro marker.** Every operator macro ends in `!!` — the double bang is what tells the agent you mean the macro, not the English word. One form per macro: no bare-word or single-`!` variants.
- **Macros do not carry across invocations.** Every macro is scoped to the message that invoked it, so an autonomy grant can never silently persist into later work.
- **A `goal: stop -- CONTEXT-CHECKPOINT` is a planned stop,** not a failure: `/clear`, then re-issue the same directive; the skill resumes by inspection.
