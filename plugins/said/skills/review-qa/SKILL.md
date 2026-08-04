---
name: review-qa
description: >
  SAID Phase 3.5 — implementation-hygiene verification gate that runs between
  Phase 3 (`/said:impl` close) and Phase 4 (`/said:debrief` entry).
  Verifies (a) quality gates clean, (b) `### Fix` claim integrity (test
  counts, grep results, file presence/absence), (c) `Refs:` ADR/UX mechanical
  conformance against `docs/qa/feature-qa-checklist.md`. Project-agnostic in command
  invocation — resolves commands at runtime via the same chain as
  `/said:impl` Step 0 #8 (`CLAUDE.md` → `Makefile` → `package.json` →
  operator-prompt). Read-only by contract; never edits code, specs, or tasks.
  Sibling skill `/said:accept` covers behavioral contract (AC items) —
  this skill covers hygiene only.
  Triggered ONLY by the explicit command "/said:review-qa
  <task-id|feature-id>". NOT for spec authoring (`/said:architect`,
  Phase 2). NOT for implementation (`/said:impl`, Phase 3). NOT for AC
  verification (`/said:accept`, sibling).
---

# Feature Review-QA — Implementation Hygiene Verification Gate

This skill verifies implementation hygiene at task or feature close: quality gates clean, `### Fix` claims honest, cited `Refs:` rules satisfied where mechanically assertable. Sits between Phase 3 close and Phase 4 entry as a parallel sibling to `/said:accept` (behavioral contract side).

**Read-only contract.** Never edits code, specs, or tasks. Surfaces verdicts (PASS / FAIL / WARN); operator decides remediation.

**Project-agnostic command invocation.** Skill never hardcodes language-specific commands. Quality-gate commands resolve at runtime via the same chain as `/said:impl` Step 0 #8.

## When this fires

- `/said:review-qa <task-id>` — **task-mode**: quality gates + Fix integrity for that task's `### Fix` claims + Refs conformance for that task's `Refs:` line.
- `/said:review-qa <feature-id>` — **feature-mode**: quality gates (once) + Fix integrity sweep across every Done task + Refs conformance sweep.

BLOCK + redirect if:

- Targeted task is `Status: Todo` / `Status: In progress` → redirect to `/said:impl`.
- Operator intent is AC verification → wrong skill, redirect to `/said:accept`.
- Operator intent is spec authoring → redirect to `/said:architect`.

## Common compositions

After Phase 3 closes (all targeted tasks `Status: Done`):

```
/said:impl <task-id|feature-id>      # task / batch closes
/said:review-qa <task-id|feature-id> # implementation hygiene cleared ┐
/said:accept <task-id|feature-id>    # behavioral contract verified   ┘ siblings, parallel
                                        # ↓ both green
/said:debrief <feature-id>           # Phase 4 entry allowed (preflight reads review-qa report)
```

## Step 0 — Preflight

1. **Resolve mode + inputs:**
   - Single arg matching project's task-id regex → task-mode. Derive feature-id from prefix; locate `## <task-id>:` anchor in `<feature>.tasks.md`.
   - Single arg matching `^[A-Z]+-\d+(-[A-Za-z0-9]+)*$` **and resolving to an existing `docs/features/<feature-id>.tasks.md`** (bare or slug-suffixed) → feature-mode (bare or suffixed per-lane feature-id, e.g. `INIT-28-BE`; task-mode above is matched first, so canonical task-ids are unaffected). Also resolve `docs/features/<feature-id>.md`. If the shape matches but no such feature log exists — e.g. a legacy task-id like `INIT-28-FE-16` — it is not a feature: BLOCK + redirect to `/said:impl`, mirroring `impl` Step 0's tasks-file guard.
2. **Status check:**
   - Task-mode: the named task must be `Status: Done (YYYY-MM-DD)`. Otherwise BLOCK + redirect to `/said:impl`.
   - Feature-mode: any task with `Status: Todo` / `Status: In progress` → BLOCK with list; operator confirms in-scope-vs-out-of-scope or closes first. (Backlog passes — intentional non-gating per SAID convention; matches `/said:debrief` preflight.)
3. **Resolve project quality-gate commands.** Same chain as `/said:impl` Step 0 #8 (first-match wins):
   - **Primary** — `CLAUDE.md` § Development Commands table: identify umbrella target (`pre-commit`, `qa`, `check`, `all`).
   - **Secondary** — if `Makefile` present: prefer `make pre-commit`; fall back to `make qa` / `check` / `all`.
   - **Tertiary** — if `package.json` present (JS/TS only): scripts named `pre-commit` / `qa` / `check` / `validate`; invoke via `npm run` or `bun run` per lockfile.
   - **Quaternary** — operator-prompt: "What's this project's full quality-gate command + per-step typecheck / test / lint commands?" Cache for session.

   Cache placeholder bindings for Phase B:
   - `<quality-gates-umbrella>` — full chain (e.g., `make pre-commit`).
   - `<typecheck>`, `<tests>`, `<lint>` — per-gate fallback if no umbrella resolves.

4. **Read `docs/qa/feature-qa-checklist.md`** — the non-UX QA contract (companion to `feature-ux-checklist.md`). Parse every rule entry's 5 fields (`id`, `source`, `applies-to`, `summary`, `verify`). The rule set the skill executes composes from three triggers (union) per Phase A: `applies-to: any` always-on + screen-shape filter (when known) + Refs-cite-driven match. Rules with no matching trigger are skipped; rules without `verify:` content surface as WARN.

## Phase A — Resolve plan (STOP for operator review)

> **Stance: read in-scope tasks; parse `### Fix` for mechanical claims; parse `Refs:` for cited rules; build execution plan. No execution yet.**

Procedure:

1. **Parse `### Fix` blocks** for mechanical claims (regex on canonical shapes):
   - **Test count delta** — match `Tests (\d+) → (\d+)` or `(\d+) pass` or `(\d+) tests` patterns. Extract claimed end-count.
   - **Quality-gate clean** — match `tsc + lint clean`, `tests pass`, `knip clean`, etc. Each → re-run the resolved per-gate command at Phase B.
   - **Grep result** — match `` `grep -rn <pattern> <path>` returns (\d+) results `` or `... shows (\d+) matches` shapes. Extract pattern + path + expected count. On parse failure → mark for operator-prompt fallback (Q2=c).
   - **File deletion** — match `` `<path>` deleted `` or `N files deleted` claims. Each → `! [ -e <path> ]` check.
   - **File presence** — match `` `<path>` written `` claims. Each → `[ -e <path> ]` check.

2. **Compose rule set from `feature-qa-checklist.md`** — three triggers (union; a rule fires if any matches):
   - **`applies-to: any` sweep:** always include every `any` rule. Universal defense — `<RULE-LABEL>` structural rules, `R-GATE-*`, etc.
   - **Screen-shape filter:** if the task / feature has a declared screen-shape (read from spec § Per-feature scope or task entry), include rules whose `applies-to` matches: `list-table`, `form`, `detail-with-tabs`, etc.
   - **Refs-cite-driven match:** for each entry in the task's `Refs:` line, find rules whose `source` matches the cite — by ADR file path (`docs/adr/<adr-file>.md`), ADR short name (`<ADR-shortname>`), or rule ID (`R-<XXX>-N`). Cite without matching rule → WARN (operator-verify).

3. **Parse `Refs:` line** for additional cites beyond the checklist mappings — purely spec/doc edits (e.g., spec edits, project-doc edits) surface as WARN since they have no mechanical assertion.

3. **Emit plan** to `docs/working/<feature-id>/review-qa-<task-id-or-feature-id>.md`:

   ```
   ## Phase A plan — <id> (YYYY-MM-DD)

   ### Quality gates
   | Resolved command | Source |
   |---|---|
   | <umbrella command> | <source — CLAUDE.md / Makefile / package.json> |

   ### Fix-claim re-checks
   | source | claim | re-verify command |
   |---|---|---|
   | <feat-id>.tasks.md:<line> (<task-id>) | <claim — e.g., Tests N → M> | <re-verify command> |
   | <feat-id>.tasks.md:<line> (<task-id>) | <claim — e.g., grep returns 0> | <re-verify command> |
   | <feat-id>.tasks.md:<line> (<task-id>) | <claim — e.g., file deleted> | <re-verify command> |

   ### Refs assertions
   | source | rule | mapped assertion |
   |---|---|---|
   | <feat-id>.tasks.md:<line> (<task-id>) | <ADR-shortname or rule ID> | (mapped: <test-file>) |
   | <feat-id>.tasks.md:<line> (<task-id>) | <ADR-shortname> | (no mapping — WARN: operator-verify) |
   ```

4. **STOP for operator review.** Brief status: "Phase A complete. <N> Fix claims + <M> Refs assertions (<K> mapped, <L> WARN) + 1 umbrella gate run planned. Plan at `docs/working/<feature-id>/review-qa-<id>.md`. Reply OK to execute (Phase B)."

## Phase B — Execute

> **Stance: run the umbrella once; re-run Fix-claim mechanicals; run Refs assertions where mapped. One verdict per check. No interpretation.**

Procedure:

1. **Quality gates (Q4=a — full umbrella always).** Run `<quality-gates-umbrella>` (resolved in Step 0 #3) in one shot. Capture exit code + stdout/stderr. PASS / FAIL by exit code.

2. **Fix-claim re-checks.** For each parsed claim:
   - **Test count (Q1=b — ≥-tolerant):** re-run `<tests>`, parse count from output, verify `actual >= claim_end`. PASS if so; FAIL if actual < claim (test deletion or regression).
   - **Grep (Q2=c — extract + prompt fallback):** run extracted grep command verbatim; verify count matches claim. On parse failure earlier (Phase A flagged), operator-prompt now: "Fix claim at `<file:line>` reads: <verbatim>. What re-verify command captures this assertion?" Operator-supplied command then runs.
   - **File deletion / presence:** `! [ -e <path> ]` or `[ -e <path> ]` check. PASS / FAIL.
   - **Quality gate sub-claim** (e.g., "tsc clean"): already covered by umbrella above; mark per-claim verdict from umbrella result.

3. **Rule-set assertions.** For each rule in the composed rule set (per Phase A § 2), run its `verify:` action. PASS / FAIL based on assertion's exit code or expected condition. Some `verify:` actions are mechanical bash; some are semantic (read-and-assert) and require operator review on output → MANUAL-PENDING; some carry default-SOFT-PASS semantics (e.g., `<RULE-LABEL>`, `<RULE-LABEL>`) and fire only when conditions warrant.

4. **Refs without mapping:** spec / project-doc cites with no rule match → WARN. Operator manually verifies. Never auto-PASS.

5. **Per-check output (Q4=c-style — one-line + embedded command + verbose redirect):**

   ```
   | section | check | verdict | evidence |
   |---|---|---|---|
   | quality-gates | <umbrella command> | PASS | exit 0; <test count + lint/typecheck/knip status> |
   | fix-claim/<task-id> | <claim — e.g., Tests N → M> | PASS | actual: M (≥ claim); `<tests>` |
   | fix-claim/<task-id> | <claim — e.g., grep returns 0> | PASS | `<re-verify command>` → 0 matches |
   | fix-claim/<task-id> | <claim — e.g., file deleted> | PASS | `! [ -e <path> ]` → true |
   | refs/<ADR-shortname> | <check description> | PASS | `<tests> <test-file>` → N tests pass |
   | refs/<ADR-shortname> | <check description> | WARN | no mapping in docs/qa/feature-qa-checklist.md; operator-verify |
   ```

6. **Verbose-output redirect.** If a re-check produces > ~20 lines of stdout/stderr (full test runner output, large diff, deep grep dump), redirect to `docs/working/<feature-id>/review-qa-<id>.full.md` under an anchor matching the check. Main report carries: `evidence: <one-line summary>; full output: review-qa-<id>.full.md § <anchor>`.

## Phase C — Report

Finalize `docs/working/<feature-id>/review-qa-<id>.md`:

```
## Review-QA verdict — <id> (YYYY-MM-DD)

- Quality gates: PASS | FAIL (1/1)
- Fix claims: <pass>/<total> PASS, <fail> FAIL
- Refs assertions: <pass>/<total-mapped> PASS, <warn> WARN (no mapping in docs/qa/feature-qa-checklist.md)
- Verdict: PASS | FAIL (with <warn> warnings)
```

Aggregate verdict rules:

- **PASS** — every check PASS. WARNs listed but allowed (operator-verify items).
- **FAIL** — ≥1 check FAIL.
- **WARN never blocks** — surfaced for operator awareness.

Gate effect for `/said:debrief`:

- `/said:debrief` Step 0 preflight reads the most recent `review-qa-<feature-id>.md`.
- If verdict is FAIL → halt `/said:debrief` with redirect: "Resolve `/said:review-qa` failures first."
- WARNs listed in debrief preflight summary; not blocking.

## Anti-patterns

- **NEVER hardcode language-specific commands in this SKILL.md.** No literal `bunx tsc`, `go test`, `cargo run`, `npm run` actions inside skill steps. Always resolve via Step 0 #3. (Examples in the resolution chain are illustrative for the resolver, not action prescriptions.)
- **Don't run on `Status: Todo` / `Status: In progress` tasks.** BLOCK; redirect to `/said:impl`.
- **Don't auto-promote WARN → PASS.** Operator must verify each WARN. Auto-promotion defeats the gate.
- **Don't edit code, specs, or tasks.** Read-only by contract. Even when finding obvious typos.
- **Don't re-implement what `/said:accept` does.** Strict scope separation: hygiene (this skill) vs behavioral contract (sibling). Don't read `### Acceptance` sections; don't classify AC items.
- **Don't synthesize grep commands from ambiguous prose.** Q2=c — try canonical-shape extraction first; on parse failure, operator-prompt. Don't fabricate complex grep commands from prose hints.
- **Don't run partial quality gates in task-mode.** Q4=a — full umbrella always. Partial gating risks missing cross-cutting regressions; the cost is acceptable.
- **Don't strict-equal gate test counts.** Q1=b — `actual ≥ claim` is correct. Test growth is expected; deletion shows up elsewhere (failed lint, removed test files visible in diff).
- **Don't grow `docs/qa/feature-qa-checklist.md` from the skill side.** Project owns its rule corpus; skill reads. Operator adds entries as patterns earn their place per the earn-its-place-ADR. Skill stays rule-agnostic.
- **Don't run UX rules.** UX rules (`<RULE-LABEL>`, `<RULE-LABEL>`, `<RULE-LABEL>`, `<RULE-LABEL>`) live in `feature-ux-checklist.md` and are owned by `/said:review-ux` (Phase 3 task-close gate). This skill reads `feature-qa-checklist.md` only. Strict file-content split.
- **Don't extract task-IDs from prose.** Require explicit input.

## Anchors

- `docs/qa/feature-qa-checklist.md` — project-side lookup table (cited rule → mechanical assertion); operator-maintained.
- `said:impl` Step 0 #8 — command-resolution chain reference.
- `said:accept` — sibling skill (behavioral contract verification).
- `said:debrief` — Phase 4 driver this skill gates.

## Re-read self-check (acceptance)

Before exiting Phase C:

- [ ] All 3 phases distinct in transcript (Preflight + Phase A + Phase B + Phase C).
- [ ] Phase A produced `review-qa-<id>.md` plan + STOPPED for operator review.
- [ ] No hardcoded language-specific commands in execution path — all resolved via Step 0 #3.
- [ ] `<quality-gates-umbrella>` ran exactly once per invocation.
- [ ] No edits to source files, specs, or tasks — read-only confirmed.
- [ ] `Refs:` items without a mapping in `docs/qa/feature-qa-checklist.md` surfaced as WARN, not auto-promoted.
- [ ] Test count claims verified with `actual >= claim` semantics, not strict-equal.
- [ ] Grep claim parse failures triggered operator-prompt, not silent skip.
- [ ] Verdict assigned per aggregate rules.
- [ ] If verbose evidence: redirected to `review-qa-<id>.full.md`; main report stays scannable.
