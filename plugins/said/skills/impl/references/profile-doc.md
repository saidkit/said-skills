# impl profile: doc
PROFILE-HEADER · doc · 6 slots

## gate
`SAID.commands:` carries a plugin verb: `doc-gate` expands, run from the lane root as ONE Bash line, to `set -o pipefail; python3 ${CLAUDE_SKILL_DIR}/../review-qa/doc-gate.py --repo-root . --tasks '<SAID.task-log glob for this feature>' --artifacts <SAID.code-mount> --banned <SAID.docs-root>/qa/banned-lexicon.txt <the lane's arguments after the verb> 2>&1 | tee <SAID.working>/doc-gate-<task-id>.log` — the engine is the sibling `review-qa` skill's bundled script.
Exit 0 = clean (WARNs allowed) · exit 1 = at least one FAIL · **exit 2 is a HALT, never a verdict**.
`<typecheck>`, `<tests>`, `<lint>` and `<quality-gates-umbrella>` ALL bind to this one umbrella — it is fast and idempotent, so per-rule and close-time runs are the same command.
No `Makefile` / `package.json` / operator-prompt step applies here.

## red
The failing gate row: the `[FAIL] <rule>` line the umbrella prints before the work, or — when the gate is already clean — the task's still-unchecked `### Acceptance` item.
Green = the row is gone from a fresh run / the item is checked with `file:line` evidence.

## carve-out
Structural only for work that is not the deliverable: moving research or notes that live outside `SAID.code-mount:`, retargeting links.
The shipped document **is** the deliverable — its tasks take the red path, never this carve-out.

## tag
No callsite tag. A deliverable document, a spec or a `CLAUDE.md` carries no `// <task-id>`.

## parity
No parity walk and no reference URL. The lane's declared agent-form Checker reads the shipped artifacts against the lane's contract at Phase C.
A parity-shaped Acceptance bullet closes `[N/A — no visual surface]`.

## code-review
Off by default: the deliverable is prose, and the declared Checker plus the umbrella are its review.
`SAID.code-review: on` overrides; when off, log `code-review SKIPPED — the doc profile defaults it off`.
