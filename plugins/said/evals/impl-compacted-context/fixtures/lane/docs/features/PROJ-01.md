# PROJ-01: config parser hardening

**Surface:** `none`

## Requirements
### Functional Requirements
- [ ] **When built, `parse` rejects unknown keys in strict mode** — `strict=True` raises `KeyError` on a key outside `{a, b}` (R-PROJ-01).

## Acceptance Criteria
- [ ] `parse("zz=1", strict=True)` raises `KeyError`; `parse("zz=1")` still returns the dict.
- [ ] `make check` exit 0.

## Feature Tasks
| Task | Title | Status |
|---|---|---|
| PROJ-01-01 | strict mode rejects unknown keys | Todo |
