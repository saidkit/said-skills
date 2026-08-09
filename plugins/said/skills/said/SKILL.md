---
name: said
description: >
  Single-feature SAID orchestrator. Drives ONE feature through the full SAID phase chain — Scope → Architect → Implement → gates → Debrief — in one session, invoking the real said:* skill at each phase and self-publishing a `goal: done|continue|stop` control line every turn so a plain `/goal implement <id> as said!` runs it to closure with no hand-written condition.
  Triggered ONLY by the explicit command "/said:said <feature-id>", or by the `said!` operator macro (which calls Skill(said:said)). Do NOT trigger on general implementation, planning, or orchestration requests. For a feature spanning ≥2 SAID lanes use said:flow, not this.
---

# said:said — Single-feature SAID orchestrator

Drives one feature through its whole SAID cycle in a single session, each phase governed by its real `said:*` skill. Replaces the inline `said!` macro whose closure signal was a **file** (the debrief footer) — invisible to `/goal`, which reads only the transcript.

`/said:impl <feature>` drives the *tasks* inside one phase. **This drives the *phases* of one feature.** `said:flow` drives the *lanes* of one feature — this is its single-lane twin.

## Why this is a skill and not an agent

**Claude Code does not permit nested subagent spawning.** `/said:impl`, `/said:scope-refine`, `/said:review-ux` all spawn read-only agents. A *subagent* asked to "run the cycle" hits a wall at the first phase that spawns and hand-rolls the work — the exact emulation this methodology exists to prevent. A skill is instructions loaded into the one agent that has skill reach, so **the governed cycle runs in the main context; subagents are used only for read-only work needing isolation.** This is what makes `said:said` safe when it is itself invoked from inside an outer skill (e.g. `said!` under `/goal auror!`, at depth 1): it never *requires* spawning — it verifies inline.

## Prime directives

1. **Never emulate a `said:*` skill.** Scope, architect, implement, gate, debrief through the real commands. Caught writing a spec or a task by hand? Stop and invoke.
2. **State lives in artifacts, never in conversation.** Every invocation reconstructs the phase by inspection. This is what makes the skill re-entrant across compaction.
3. **A compaction is not a stop.** Re-enter, reconstruct, continue.
4. **Closure is a printed line, never a file alone.** The `## Debrief close` footer is the durable record; the `goal:` line is what an outer `/goal` can actually see. Publish it every turn.

## Invocation

- `/said:said <feature-id>` — do the next thing for this feature, then emit the Output contract.
- `/said:said <feature-id> status` — reconstruct and report the phase only; take no action.

Preconditions. Any failure BLOCKS with a named redirect:

- **Single-lane only.** If the feature carries SAID artifacts (a `scope.md`, spec, or task log) in **≥ 2 lanes** — declaration-first per each candidate tree's `CLAUDE.md` `## Lane` block, glob fallback — this is not `said:said`'s job: **BLOCK + redirect to `flow!` / `/said:flow`**. A *mount* where code lands is not a lane; one feature may change code in several mounts and stay single-lane.
- **Has somewhere to start.** A brand-new feature with no `scope.md` enters at Scope (below); an already-architected feature (spec + `Status: Todo` tasks) may enter directly at Implement.

## Output contract

Every invocation ends with this block. No exceptions — including `status` mode and an invocation that took no action.

```
feature: <id>
phase: <Scope|Architect|Implement|Gates|Closed> — <n> Todo
gates: review-qa <pass|fail|—> · accept <pass|fail|—> · UAT <passed|pending|n/a>
said closed: yes|no
goal: done | continue | stop — <reason>   # /goal reads this line: done|stop end the run, continue = re-invoke
```

**`said closed: yes` is permissible ONLY when the tasks log carries a `## Debrief close` footer AND every gate passed** (or an operator-confirmed, recorded skip). The footer is written at debrief Phase C, *after* its Phase-3.5 gate-check clears; a `debrief.md` written at debrief Phase A is NOT closure. Anything short of footer-plus-gates is `no`.

**The `goal:` line is the loop oracle** — self-describing, so a `/goal` driving this skill needs **no** hand-written completion condition; a plain directive (`/goal implement <id> as said!`) is enough.
- `done` = `said closed: yes` (footer present AND gates passed).
- `stop` = the run is blocked or needs an operator decision — an **unconfirmed omission** (a mandatory stage skipped without a recorded confirmation), a **failing gate** (`review-qa`/`accept` FAIL), an **owed operator decision** (e.g. a UAT skip on a UI feature), or a **no-progress HALT** (Step 5).
- `continue` = everything else (a phase still has work).
`done` and `stop` both end the `/goal` loop (`stop` hands the operator the `<reason>`); `continue` is what re-invokes.

**Never write "done", "closed", "nothing left" into a resume pointer, report, or chat summary while this block says `no`. If an outer orchestrator has already declared the work finished and this block says `no`, say so and contradict it** — that contradiction is the most valuable thing this skill emits, and suppressing it is how a feature silently ships without its gates.

**This skill is a loop, not a one-shot.** A caller that invoked it once — including an outer planner such as `/magic:think-deep` that scheduled "invoke `/said:said`" as a single step — has **not** run it to completion; it has taken one step of an N-step loop. While the `goal:` line reads `continue`, the only correct next action is to **re-invoke `/said:said <feature-id>`**, never to tick a step done or move on.

---

## Step 1 — Reconstruct the phase by inspection

Never read a stored phase. Derive it, every time, from the feature's own artifacts (rooted at the feature's docs root — this skill is lane-agnostic; it operates on "a feature in a docs root", never a hardcoded repo layout).

| Fact | Probe |
|---|---|
| **Lane count** (route guard) | Declaration-first: count trees whose `CLAUDE.md` declares a `## Lane` carrying this feature's SAID artifacts; glob fallback `*/docs/features/<feature>*.tasks.md` + `*/docs/working/<feature>/`. **≥ 2 → BLOCK, redirect to `flow!`.** |
| **Feature-id** | the arg, normalized UPPERCASE; the tasks-file stem minus `.tasks` once one exists |
| **Phase** | no `scope.md` → **Scope** · `scope.md`, no spec → **Architect** · spec + `Status: Todo` > 0 → **Implement** · spec, `Todo == 0`, **no** `## Debrief close` footer → **Gates** · footer present → **Closed** |
| **Work remaining** | count `Status: Todo` in `docs/features/<id>.tasks.md` (bare or slug-suffixed) |
| **Gate results** | `review-qa` / `accept` verdicts recorded in the tasks log / QA checklist for this feature; `—` if that gate hasn't run |
| **UAT** | `passed` when the feature's UAT result artifact (`*QA-UAT*.md` / `*uat*.md`) carries a pass verdict · `n/a` when scope declares no user-visible surface (Developer-Story) · else `pending` |
| **Closure** | the `## Debrief close` footer in the tasks log — the single Gates→Closed transition |

> **`Todo == 0` is ambiguous — never key an action on it alone.** A feature with zero tasks because it
> was never architected looks identical to one that finished. Always pair the count with the phase:
> **Scope** and **Architect** have work; **Gates** does not.

**Report probe results literally** — actual output, not a summary — so a future invocation (or a compaction resume) can reproduce the reconstruction. If two probes disagree, trust the **artifact** and say so.

## Step 2 — Emit the stage checklist (first entry)

On the first substantive turn, resolve the ordered stage sequence for this feature **from the SAID map — the said plugin README + each skill's description — not from memory** (skills self-select by phase; do not hard-code the chain). Emit it as an explicit checklist so attention re-anchors on the
plan, e.g.:

```
SAID cycle for <id> — resolved from the map:
  [ ] Scope      → /said:scope-refine (handoff) | /said:scope-grill (thin idea)
  [ ] Architect  → /said:architect
  [ ] Implement  → /said:impl (+ /said:review-ux per web task)
  [ ] Gates      → /said:review-qa → /said:accept → /said:debrief
```

**Interactive default: confirm the checklist before proceeding.** Under `/goal` / `auror!` / `expelliarmus` this relaxes to report-and-proceed (no wait) — but every stage and gate still runs.

## Step 3 — Drive the current phase

Deterministic: the same reconstructed phase always yields the same entry. **Never guess a phase's work; invoke its skill.** Resolve `docs/features/<id>` from the feature's own docs root.

| Phase | Entry (invoke; never emulate) |
|---|---|
| **Scope** | `/said:scope-refine <handoff>` — a discovery handoff/branch state is the input. `/said:scope-grill` only for a genuinely thin idea. → produces `scope.md` (§D resolved). |
| **Architect** | `/said:architect <scope-path>` → produces the spec + `*.tasks.md`. |
| **Implement** | `/said:impl <feature-id>` (whole-feature mode). On a web/UI task, compose `/said:review-ux` at task close. Adapt or skip the UX gate on non-web — recorded, never silent (W9). |
| **Gates** | `/said:review-qa <id>` → (FAIL → `goal: stop`) → `/said:accept <id>` → (FAIL → `goal: stop`) → **UAT** (below) → `/said:debrief <id>` through Phase C. The `## Debrief close` footer is the Gates→Closed transition. |
| **Closed** | nothing — do not re-enter. `said closed: yes` → `goal: done`. |

**UAT at Gates.** For a feature with a user-visible surface, run the e2e/UAT (Playwright MCP where available) before `debrief` and record a real verdict into the UAT artifact — failures as failures, never "not run". `n/a` for a Developer-Story with no UI. An operator-confirmed **skip** is allowed only on explicit word, written as `skipped(recorded)`; under an autonomy macro that skip is a **hard blocker** (`goal: stop`) — the one wait autonomy cannot self-approve. Tooling unavailable → do not
fabricate a pass; emit `UAT pending` → `goal: stop` naming the exact run owed.

**Omission is never silent (W7).** A mandatory stage skipped or deferred without an explicit, recorded operator confirmation → **withhold `said closed: yes` and emit `goal: stop — unconfirmed omission: <stage>`**.
Never present a mandatory stage as an optional offer ("if you want…"). Under autonomy this is the one wait that cannot be dropped — it forces the confirmation.

## Step 4 — Gate before end of turn

Before yielding, both hold (neither skippable under an autonomy macro — autonomy removes waits, not gates):

1. **Unfiled decisions.** Every decision made this turn is written to an artifact (task body / ADR / scope). Nothing load-bearing lives only in the conversation.
2. **Emit the Output contract block** (above), every time — the `goal:` line especially. "Genuine completion" is not a prose judgement; it is `said closed: yes`, true only with footer-plus-gates.

## Step 5 — Progress check, then re-enter

Snapshot before/after every invocation: `Status: Todo` count, artifact file list, gate verdicts, footer presence. If an invocation changes **none** of them → **HALT** with `goal: stop — no progress: <what was attempted>`; do not re-enter. A loop that churns quietly is worse than one that stops loudly.

Otherwise return to Step 1 and continue — a phase boundary is where work flows, not where it waits.
Stop only on: `goal: done` (footer + gates), or `goal: stop` (a failing gate / unconfirmed omission / owed operator decision / no-progress). Emit the Output contract whether or not it was asked for — if an outer orchestrator invoked this once and moved on, that block is the only thing telling it the feature is not finished.

## Never

- Emulate a `said:*` skill because invoking felt heavy.
- Drive a feature that spans ≥2 lanes — that is `said:flow`; redirect.
- Write `said closed: yes` (or `goal: done`) before the `## Debrief close` footer exists AND gates pass.
- Skip a mandatory stage silently — an unconfirmed omission is `goal: stop`, not a quiet pass.
- Carry the phase, or any decision, only in conversation across a compaction.
- Read a stored phase/state file back as truth in place of re-deriving from artifacts.

## Known limits

- **Spawn-safe by contract.** Runs in the main context and verifies inline, so it is correct whether it is the top agent or a depth-1 subagent (e.g. inside `said!` under `auror!`). It never spawns to make a decision; the `said:*` skills it invokes do their own (read-only) spawning at depth 0.
- **The SAID map is authoritative, not this file.** Phase→skill selection, gate order, and branch points come from the plugin README + each skill's description (Step 2). If the map changes, follow the map — do not hard-code the chain here.
- **Project conventions are project-specific.** Task-id shape, tasks-file location, and QA-artifact names come from the project's `CLAUDE.md` / stencils. Read them at Step 1; do not assume shapes.
- **Per-lane engine (forward-looking).** The core is lane-agnostic on purpose: it operates on a feature in a docs root, so `said:flow` could later drive one `said:said` per lane. Until then, `said:flow` keeps its own walk — this skill does not change it.
