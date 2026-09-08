---
name: impl-compacted-context
tags: [impl, compaction, progressive-disclosure]
runs: 3
max_turns: 12
timeout_seconds: 300
allowed_tools: [Read, Glob, Grep, Bash]
---
[Conversation compacted] Summary of the session so far: the operator ran `/said:impl PROJ-01-01` in the fixture lane shipped with this case (the `fixtures/lane` directory: its `CLAUDE.md` carries the `## Lane` block and a 3-rule `## Earned rules` section). Step 0 completed: keys resolved (task log `docs/features/PROJ-01.tasks.md`, spec `docs/features/PROJ-01.md`, surface `none`, no reviewers, umbrella `make check`, `<typecheck>` = `make typecheck`, `<tests>` = `make test`), the lane's `## Earned rules` echoed as 3 rules (R-PROJ-01..03), the shortname table absent. You were about to start Phase A. Only the first part of the `said:impl` skill body survived the compaction and is in your context; the skill's own directory is the `said` plugin's `skills/impl/` directory (the base directory the Skill tool printed when it was invoked).

Continue the run from here: perform Phase A for PROJ-01-01 exactly as the skill prescribes, then STOP at the end of Phase A and print your Phase A output. Do not edit any file.
