# impl profile: code
PROFILE-HEADER, code, 6 slots

## gate
Resolution chain, first match wins: **Primary** the `## Lane` `SAID.commands:` umbrella target (`pre-commit`, `qa`, `check`, `all`), **Secondary** a `Makefile` (prefer `make pre-commit`, else `make qa` / `check` / `all`), **Tertiary** a `package.json` (scripts `pre-commit` / `qa` / `check` / `validate`, invoked per lockfile), **Quaternary** ask the operator once ("full quality-gate command + per-step typecheck + per-step test?"), cache for the session, never persist.
Bind `<typecheck>` to the fast per-rule verifier, `<tests>` to the test command, `<lint>` to the linter, `<quality-gates-umbrella>` to the full chain.
An answer of *none* leaves a placeholder unbound: it is not a gate to invent, and no unbound placeholder blocks a close.

## red
The failing `<tests>` run: pre-commit it before the work, watch it fail, implement until green, refactor.
`<tests>` unbound -> the task's still-unchecked `### Acceptance` item is the red.
Green = the run passes, with `file:line` evidence.

## carve-out
Structural (declarative-test / no-test): pure folder moves, import retargeting, and edits to documentation that is **not the lane's deliverable** (a README, a comment).
New behaviour never qualifies; a carve-out that turns out to be behaviour re-declares discipline.

## tag
Tag every changed callsite `// <task-id>` (no suffix) — **source code only**.

## parity
`SAID.surface: web` -> at Phase C walk the migrated URL side-by-side with the reference URL, enumerate every visible difference, and close the parity bullet only on an empty diff; a non-empty diff returns to Phase B.
Any other surface -> no parity walk; the lane's declared Checkers carry the contract check, and the parity bullet is `[N/A — non-visual surface]`.

## code-review
On: Phase C spawns the generic read-only code-review over the task's diff.
`SAID.code-review: off` overrides — log `code-review SKIPPED — lane declares SAID.code-review: off`.
