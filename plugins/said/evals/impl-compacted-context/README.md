# impl — compacted-context eval

Measures the progressive-disclosure contract of `said:impl`: after a context compaction only the spine (`SKILL.md`, < 16,000 bytes) is re-attached; the executor must `Read` the phase procedure from `references/` before acting.

- `prompt.md` — a synthetic post-compaction state (summary + "you were about to start Phase A"); `case.yaml` adds `fixtures/lane` (a `CLAUDE.md` with a `## Lane` block and a 3-rule `## Earned rules` section, `docs/features/PROJ-01.md`, `PROJ-01.tasks.md` with one Todo task, a `Makefile` whose targets print and exit 0) to the run's directories. No placeholder substitution is assumed.
- `graders/` — `reads-phase-a` (tool_used Read, `input_match` on `references/phase-a.md`) + `reads-phase-a-bash` (the Bash-read indicator), `inventory-shape` (regex on the four-column inventory header), `no-edits` / `no-writes`, `classification` (llm).
- Run: `claude plugin eval ./plugins/said --case impl-compacted-context --runs 3 --ablation with-without`. Under ablation the "without" arm has no skill, so `reads-phase-a` is a plugin-fired indicator.
- **Grader caveat:** in an environment that steers agents to Bash for file reads, `tool_used: Read` under-counts — a `cat`/`sed` of `references/phase-a.md` is a read too. Pair `reads-phase-a` with a regex grader over the transcript's Bash commands where the runner allows it.
- Authored 2026-09-08 to the documented case/grader schema. The runner is early-access and gated per organization; the same experiment was run through fresh subagents with a JSON-walk grader and recorded under `docs/evaluation/impl/` (private) until the runner is enabled.
