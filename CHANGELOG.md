# Changelog

All notable changes to the SAID plugin are documented here. Format follows [Keep a Changelog](https://keepachangelog.com); the project uses semantic versioning.

## [0.1.0] — 2026-06-23

Initial public release — the stack-agnostic SAID engine.

### Added
- 10 skills: `said:scope-grill`, `said:scope-refine`, `said:architect`, `said:add-task`, `said:impl`, `said:review-ux`, `said:review-qa`, `said:accept`, `said:debrief`, `said:triage`.
- 3 subagents: `scope-refine-agent`, `scope-audit`, `review-ux-agent`.
- Marketplace-of-one (`saidkit`) — install via `claude plugin marketplace add saidkit/said-skills` then `claude plugin install said@saidkit`.
- Adoption guide (`docs/adoption-guide.md`) + starter contract (`starters/README.md`) for the engine + per-stack-starter model.

## [0.1.1] - 2026-07-30

Added Flow skill - a cross-lane orchestrator for multi-repo setup of several said-* sub-projects.
