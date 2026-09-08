# PROJ-01 Task Log: config parser hardening

<!-- Id shape: `<FEAT>-<NN>-<NN>` — single lane; counters 2-digit zero-padded (feature `PROJ-01`, then a task counter; e.g. PROJ-01-01). Derives from the `## Lane` `SAID.id-shape:` key. -->

**Append-only historical record.**

- Never overwrite or strip detail from existing entries.
- Status update = change the `Status:` line only; add/update `### Fix` (optionally `### Deviations` / `### Gotchas`).

## Authoring discipline

- **Working folder vs body** — `docs/working/<feature-id>/` is operator workspace; the task body cites only durable artifacts.
- **Not here** — forward-looking rules (→ ADR + `Refs:` pointer) · file enumerations (→ `git log --name-only`) · historical narration · paraphrase of a referenced ADR/spec.
- **Depth varies** — planned tasks fill Problem / Approach / Reading list / Acceptance / Fix; ad-hoc tasks may carry only Problem + Fix + Gotchas.
- **`Refs:`** — mandatory when the task creates or edits an ADR / feature-spec.

---

## Summary Table

| Task | Title | Status |
|---|---|---|
| PROJ-01-01 | strict mode rejects unknown keys | Todo |

---

## PROJ-01-01: strict mode rejects unknown keys

**Status:** Todo (2026-09-08)
**Priority:** High
**Refs:**

### Problem
<one paragraph>

### Approach
<what to build; key decisions; no step-lists>

### Reading list
- `<file>` — <why>

### Acceptance
- [ ] <observable bullet>

### Fix
<!-- Filled at close. One verification line + `Rules applied: <ids | none> (block: N)`. -->

### Deviations
<!-- Optional. -->

### Gotchas
<!-- Optional. -->
