## `task-comments!!`
Use a rule: in source code, reference comments must be **task-id + very short why** only.
Format: `// <task-id>` (bare) or `// <task-id> — <≤10-word why>`.
When operator types `task-comments!!`, recall this rule and apply it; retroactively trim in-progress source files if asked. Multi-line rationale belongs in the task body / ADR / UX-spec — not the source.

## `said!!`
Single-feature SAID orchestrator — full cycle (skill: `said:said`) — 3 slots, Invoke · Compose · Drive:
1. **Invoke.** FIRST action = `Skill(said:said)` + the task — as `said!! <directive>` or `<directive> as said!!`. Hand-rolling stages = emulation (under `/goal`: no skill → no `goal:` line → spin).
2. **Compose.** Under `run!!`/`proceed!!`: the checklist-confirm relaxes to report-and-proceed — every stage/gate still runs; an unconfirmed omission is a wait autonomy can't drop (as is an operator question, per `proceed!!`). `task-comments!!` during impl.
3. **Drive.** The skill prints a `goal:` line every turn (`done` = debrief footer + gates passed / `continue` / `stop`). Under `/goal` that IS the completion condition — write a plain directive, never hand-write it. `continue` re-invokes `said:said`; `done`/`stop` end it. `run!!`: think-deep loop-shaped `via:` step.
A `goal: stop -- CONTEXT-CHECKPOINT` is a planned stop, not a failure and not an operator question: `/clear`, then re-issue the same directive (the skill resumes by inspection).

## `flow!!`
Multi-lane SAID orchestrator (skill: `said:flow`) — 3 slots, Invoke · Compose · Drive:
1. **Invoke.** FIRST action = `Skill(said:flow)` + feature id — as `flow!! <directive>` or `<directive> as flow!!`. Hand-rolling lanes = emulation (under `/goal`: no skill → no `goal:` line → the loop spins).
2. **Compose.** Under `run!!`/`proceed!!`: report replaces the wait — every gate still runs. `task-comments!!` during impl.
3. **Drive.** The skill prints a `goal:` line every turn (`done`/`continue`/`stop`). Under `/goal` that line IS the completion condition — write a plain directive, never hand-write it. `continue` re-invokes `/said:flow`; `done`/`stop` end it. `run!!`: think-deep drives it as a loop-shaped `via:` step.
A `goal: stop -- CONTEXT-CHECKPOINT` is a planned stop, not a failure and not an operator question: `/clear`, then re-issue the same directive (the skill resumes by inspection).

