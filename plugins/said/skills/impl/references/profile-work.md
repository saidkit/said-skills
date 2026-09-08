# impl profile: work
PROFILE-HEADER · work · 6 slots

## gate
None. This family binds no runner: `<typecheck>`, `<tests>`, `<lint>` and `<quality-gates-umbrella>` stay unbound.
Never infer one from a file on disk and never invent one; an unbound placeholder is skipped wherever the procedure names it, and skipping it is not a deviation.

## red
The task's still-unchecked `### Acceptance` item, pre-committed before the work.
Green = the item is checked with `file:line` evidence in the artifact it names.

## carve-out
None. Every unit takes the red path — with no runner, the unchecked Acceptance item is the only pre-commitment there is.

## tag
No callsite tag.

## parity
No parity check. A parity-shaped Acceptance bullet closes `[N/A — no visual surface]`.

## code-review
Off: there is no code to review. Log `code-review SKIPPED — the work profile defaults it off`.
`SAID.code-review: on` overrides.
