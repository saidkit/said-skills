# PROJ-01 Task Log

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
`parse` silently accepts any key; strict mode must reject keys outside `{a, b}` (R-PROJ-01).

### Approach
Add the strict check inside `src/parse.py`; the allowed set is a module constant.

### Reading list
- `src/parse.py`, `src/parse_test.py`.

### Acceptance
- [ ] `parse("zz=1", strict=True)` raises `KeyError`.
- [ ] `parse("zz=1")` unchanged (returns the dict).
- [ ] A test for both cases lives next to `src/parse.py` (R-PROJ-02).
- [ ] `make check` exit 0.

### Fix
<!-- Filled at close. -->

### Deviations
<!-- Optional. -->

### Gotchas
<!-- Optional. -->
