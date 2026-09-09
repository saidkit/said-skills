# fixture lane — CLAUDE.md

## Lane
- SAID.lane:         fixture
- SAID.docs-root:    docs/
- SAID.code-mount:   src/
- SAID.feature-spec: docs/features/<id>.md
- SAID.task-log:     docs/features/<id>.tasks.md
- SAID.working:      docs/working/<id>/
- SAID.id-shape:     <FEAT>-<NN>-<NN>
- SAID.adr-prefix:   ADR-PROJ-*
- SAID.surface:      none
- SAID.impl-profile: code
- SAID.reviewers:    []
- SAID.commands:     make check

## Claude Code Reminders
- **Before each implementation step, re-read `## Earned rules` and name the ids you apply.**

## Earned rules (full context in linked ADR)
- **R-PROJ-01** — Every parser accepts a `strict` flag; unknown keys raise when strict → docs/adr/ADR-PROJ-S01.md
- **R-PROJ-02** — Tests live next to their source file → docs/adr/ADR-PROJ-S02.md
- **R-PROJ-03** — No network calls in unit tests; use the recorded fixture → docs/adr/ADR-PROJ-S03.md
