---
name: scope-grill
description: >
  SAID/Phase 1 (Scope) Case 2 — interactive ideation for SAID feature flow.
  Drives focused Q&A from a thin user prompt into a complete `scope.md`
  with §A purpose / §B target shape / §C constraints / §D open questions.
  Trigger phrases: user says "Grill idea ...", "Let's ideate ...", or runs
  the explicit command "/said:scope-grill <topic>". Stops when §D empties
  → writes `scope.md` to `docs/working/<feature>/` for Phase 2 (Architect)
  to consume. Do NOT trigger on substantive handoffs (multi-paragraph
  technical docs, paths to wip.md / context.md) — redirect the operator 
  to /said:scope-refine.
---

# Feature Scope Grill — Phase 1 (Scope) Case 2: Interactive Ideation

This skill drives the Phase 1 Case 2 path — turning a thin user prompt into a complete `scope.md`. Case 1 (handoff exists) uses the `said:scope-refine-agent` agent instead; THIS skill is for when the operator has only a thin idea ("notification preferences UI", "CSV import for projects") and needs to think through scope via focused Q&A before Phase 2 (Architect) starts. Your goal is to grill user idea from different angles to build a comprehensive scope - literally extract implicit knowledge from user's head and match it with harsh reality

There is NO separate agent. You — the main agent — drive the Q&A loop interactively. Read this file, enter the loop, and stay until §D is empty.

## When this fires

The harness auto-invokes on operator phrases:

- "Grill idea ..."
- "Let's ideate ..."
- explicit `/said:scope-grill <topic>`

If the operator's input is substantive — a path to `wip.md`, prior `context.md`, a multi-paragraph technical handoff — this is the WRONG skill. Redirect: "You have a substantive handoff at `<path>`. Use `/said:scope-refine <path>` instead — that's Case 1, with the parallel-fan-out agent + wire/visual probes."

## Output shape — `scope.md`

Write to `docs/working/<feature>/scope.md` once §D empties. The file has FOUR sections, matching the slot contract Phase 2 (Architect) consumes:

```
# <feature> — Scope

## §A — Purpose
What this work is for. The WHY — user pain, operator need, business driver. Cite the original prompt verbatim where useful. Name the target user (operator role, end-user role, or both).

## §B — Target shape
What the end product looks like. 
For server app - what is API shape, database changes required, feature interactions, RBAC etc
For web app - UI surfaces (which screens, where they live in the routing tree); data model touchpoints (entities created / read / mutated); behavioural envelope (what happens, what doesn't); reference screens / contract rules cited (`R-*` from `docs/qa/feature-ux-checklist.md`, named references from `docs/ux/lists.md` / `shell.md` / `form.md`).

## §C — Constraints
What this work MUST respect: performance budget, RBAC role gating, project conventions (cite ADRs / UX-spec frozen rules verbatim), sequencing dependencies (what blocks what, what waits on what), and explicit out-of-scope boundaries.

## §D — Open questions
Unresolved items requiring operator decision. EVERY question carries:

- **Phrasing** — neutral framing of the question.
- **Forcing function** — what blocks on the answer (which §A/§B/§C bullet, which Phase 2 spec section).
- **Default + reasoning** — your best guess and why; do NOT pick the side unless the operator confirms.

§D MUST be empty when scope.md is final. Non-empty §D = Phase 1 incomplete; Phase 2 (Architect) cannot start.
```

The §A/§B/§C/§D slot positions match the slots in `said:scope-refine-agent`'s output. The CONTENT differs — the refine agent populates §A with verbatim wire captures, §B with visual contract screenshots, §C with cross-cutting decisions, §D with handoff-vs-contract conflicts. This skill populates them with purpose / target shape / constraints / open questions extracted from Q&A. Either way, Phase 2 reads four §-sections and uses them to build the spec.

## Q&A loop

Drive focused questions. Pace: one or two questions at a time, never five at once — the operator's brain is the bottleneck. Pursue each section to a sane stopping point before moving on, but loop back when later answers reveal earlier gaps.

Suggested order:

1. **§A — Purpose** — "What pain does this solve? Who hits it? Why now? What's the user role(s) that interact with this?"
2. **§B — Target shape** — "What does the user see / do? Which surfaces / routes? Which entities / data are touched? For Web app - Any reference screens that name the shape (`/tasks`, `/projects/new`, etc.) or contract rules that apply (<RULE-LABEL>, <RULE-LABEL>, etc.)?"
3. **§C — Constraints** — "What must this respect — performance, RBAC, existing conventions? Anything explicitly out-of-scope? Sequencing — does this block other work or wait on something? Any ADR / UX rule that pins a specific shape?"
4. **§D — Open questions** — Surface as you go. Anything you'd otherwise have to GUESS at to write spec.md goes here, with phrasing + forcing function + your default-with-reasoning.

For Web app: Cite `R-*` rules from `docs/qa/feature-ux-checklist.md` whenever §B / §C touches a contract-governed area (list-table → <RULE-LABEL>, form → <RULE-LABEL>, RBAC → <RULE-LABEL>, etc.). Phase 2 (Architect) needs these citations to ground the spec.

Whenever you find yourself about to silently resolve a question — STOP. That's a §D item. Surface it; do not pick a side.

## Stop condition

§D empties → scope.md is complete → write the file to `docs/working/<feature>/scope.md` and tell the operator Phase 1 is done. Suggested next step: "Phase 2 (Architect) starts here. Run /said:architect when ready (or build the spec interactively per `docs/features/template.md`)."

If the operator wants to defer some §D items to Phase 2 — that's allowed. Mark those items as "defer to Phase 2 (Architect)" with explicit reasoning, treat them as resolved for Phase 1 purposes, and write scope.md. Phase 2 will surface them again if they're real blockers.

## Operator decision points

Resolve these EARLY in the loop, not at the end:

- **Feature name** — derive from the prompt, then confirm with the operator. The name pins `docs/working/<feature>/scope.md` and the eventual `<feature>.md` spec filename. Use kebab-case (`notification-preferences`, `csv-import-projects`).
- **In-scope / out-of-scope boundary** — pin this in §C before deep target-shape Q&A. Otherwise the grill bloats and §B becomes unfocused.

## Anti-patterns

- **Don't write spec-shape.** No Acceptance Criteria, no Functional / UI-UX / API / Performance / Acceptance sections, no Feature Tasks table. Those are Phase 2 (Architect) artifacts. Scope is idea-shape; spec is implementation-shape.
- **Don't merge `scope.md` + `spec.md`.** Separate files, separate phases, different content shapes. Earned design decision.
- **Don't auto-resolve §D.** Every operator-decision item stays open until the operator confirms. Silent resolution defeats Phase 1's whole point.
- **Don't ask five questions at once.** Focused, one-or-two-at-a-time. Compounding questions overwhelm and produce shallow answers.
- **Don't write `scope.md` before §D is empty** (or all §D items explicitly deferred). Premature write = incomplete scope = Phase 2 starts on bad input.
- **Don't silently invoke `/said:scope-refine`.** That's Case 1, different shape, different agent. If the operator HAS a handoff doc, redirect explicitly: "You have a handoff at `<path>` — run `/said:scope-refine <path>` instead."
- **Don't assume the project's contract.** Before answering §B / §C technical questions - for server app: read any cited ADRs / API specs, for web app - read any cited ADRs / `docs/qa/feature-ux-checklist.md` and UX specs. Your job is to elicit and structure, not to invent constraints.
- **Don't load context the operator hasn't asked for.** If `<feature>` matches an existing dir under `docs/features/` or `src/features/`, ASK before deep-diving — they may want a fresh-eyes ideation, not a refine.
