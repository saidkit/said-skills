---
name: said
description: >
  Single-feature SAID orchestrator. Drives ONE feature through the full SAID phase chain — Scope → Architect → Implement → Deliver — in one session, invoking the real said:* skill at each phase and self-publishing a `goal: done|continue|stop` control line every turn so a plain `/goal implement <id> as said!` runs it to closure with no hand-written condition.
  Triggered ONLY by the explicit command "/said:said <feature-id>", or by the `said!` operator macro (which calls Skill(said:said)). Do NOT trigger on general implementation, planning, or orchestration requests. For a feature spanning ≥2 SAID lanes use said:flow, not this.
---

# said:said — Single-feature SAID orchestrator

Drives one feature through its whole SAID cycle in a single session, each phase governed by its real `said:*` skill. `/said:impl` drives the *tasks* in a phase; this drives the *phases* of one feature; `said:flow` drives the *lanes* — this is its single-lane twin.

## Contract — holds every run

- **Never emulate a `said:*` skill.** Scope, architect, implement, gate, debrief through the real commands. Caught writing a spec or task by hand → stop and invoke.
- **Reconstruct the phase by inspection, every invocation** (Step 1). Never read a stored phase/state file back as truth — re-derive from the feature's artifacts. This is what makes the skill re-entrant across compaction: a compaction is not a stop; re-enter and continue.
- **Main-context; never spawn to decide.** The governed cycle runs in the main context; verify inline. Correct whether the top agent or a depth-1 subagent (e.g. `said!` under `/goal auror!`); the `said:*` skills it invokes do their own read-only spawning at depth 0.
- **Single-lane only.** ≥2 lanes carry the feature's SAID artifacts → **BLOCK + redirect to `flow!` / `/said:flow`** (Step-1 route guard). A mount is not a lane.
- **Classify the request first (Step 0).** A bug / tweak / follow-up that fits an existing feature takes the SHORT path (`triage → add-task → impl → deliver`), never a from-scratch Scope→Architect walk. A Closed feature + a new ask is never `goal: done` — and where that change lands (reopen vs new feature) is the **operator's** decision: propose both, never pick silently.
- **Closure = footer AND gates, published as the `goal:` line every turn.** `said closed: yes` (⇔ `goal: done`) ONLY when the tasks log has a `## Debrief close` footer AND every gate passed (or a recorded, operator-confirmed skip). Emit the Output contract — the `goal:` line especially — on every invocation, including `status` mode and a no-action turn.
- **Contradict a premature "done".** Never write "done"/"closed"/"nothing left" while the block says `no`; if an outer orchestrator declared the work finished and the block says `no`, say so and contradict it.
- **Loop, not one-shot.** While the `goal:` line reads `continue`, the only correct next action is to re-invoke `/said:said <feature-id>` — never tick a step done or move on.
- **`stop` is surfaced, not enforced — announce once, then hold.** `/goal`'s evaluator is binary (only *met* ends the loop); it **re-fires after a `goal: stop`** because the feature is not `done`. So an owed operator decision the agent must not fake — a UAT/aesthetic sign-off, an ambiguous reopen-vs-new, any human judgment — is announced **exactly once**: the owed verdict, the options, and how to unblock (reply the verdict, or `/goal clear` to release the loop). On every re-fire after that, **hold** — no new work, no manufactured verdict, no repeated "still waiting". Faking the judgment, or re-emitting until the Stop-hook block-cap force-kills the turn, is the failure this rule prevents (the HITL livelock).
- **The SAID map is authoritative, not this file.** Phase→skill selection, gate order, and branch points come from the plugin README + each skill's description (Step 2). Project conventions (task-id shape, tasks-file location, QA-artifact names) come from the project's `CLAUDE.md` / stencils — read them at Step 1; never assume shapes.

## Invocation

- `/said:said <feature-id>` — do the next thing for this feature, then emit the Output contract.
- `/said:said <feature-id> status` — reconstruct and report the phase only; take no action.

Preconditions — any failure BLOCKS with a named redirect:

- **Single-lane only.** Feature carries SAID artifacts (`scope.md`, spec, or task log) in ≥2 lanes — declaration-first per each tree's `CLAUDE.md` `## Lane` block, glob fallback → **BLOCK + redirect to `flow!` / `/said:flow`**. (A mount where code lands is not a lane; one feature may touch several mounts and stay single-lane.)
- **Pick the entry (Step 0).** Classify the directive first — a bare feature-id resumes where it sits; a change/bug/follow-up on an existing feature takes the short path; a novel capability starts at Scope.

## Output contract

Every invocation ends with this block. No exceptions — including `status` mode and a no-action turn.

```
feature: <id>
phase: <Scope|Architect|Implement|Deliver|Closed> — <n> Todo
gates: review-qa <pass|fail|—> · review-ux <pass|fail|—> · accept <pass|fail|—> · Eval <passed|pending|n/a>
said closed: yes|no
goal: done | continue | stop — <reason>   # /goal reads this line: done|stop end the run, continue = re-invoke
```

`said closed: yes` is permissible ONLY with the `## Debrief close` footer present AND every gate passed (or a recorded, confirmed skip). The footer is written at debrief Phase C after its Phase-3.5 gate-check clears; a `debrief.md` from debrief Phase A is NOT closure. Anything short of footer-plus-gates is `no`.

The `goal:` line is the loop oracle — a plain directive (`/goal implement <id> as said!`) drives it, no hand-written condition:
- `done` = `said closed: yes` (footer present AND gates passed).
- `stop` = blocked / needs an operator decision — an unconfirmed omission (mandatory stage skipped without a recorded confirmation), a failing gate (`review-qa`/`review-ux`/`accept` FAIL), an owed operator decision (e.g. a UAT skip on a UI feature), or a no-progress HALT (Step 5).
- `continue` = a phase still has work.
`done` ends the `/goal` loop — the evaluator, reading the transcript, sees closure. `stop` is your **terminal intent**, but `/goal` is binary and **re-fires anyway**: phrase the `<reason>` so the evaluator can release (state the block is operator-owned and autonomous progress is exhausted) and the operator can act (reply the verdict, or `/goal clear`). On a re-fire, **hold** — announce once, then no new work (Contract). `continue` re-invokes.

---

## Step 0 — Classify the request → pick the path

Before reconstructing anything, decide which entry the directive needs (first match wins). The test that splits SHORT from NEW: **does this work need its own scope + spec, or does it fit as a task on an existing feature?**

| The directive is… | Path | Entry |
|---|---|---|
| a bare feature-id; feature **in-flight** (Todo>0 / phase < Closed) | **RESUME** | Step 1 → drive the chain from its phase |
| a bare feature-id; feature **Closed**, no new ask | **DONE** | report Closed → `goal: done`; take no action |
| a change / bug / follow-up that **fits an existing feature's scope** (feature **open**) | **SHORT** | `triage` → `add-task` → Implement (Step 3 front door); Scope + Architect skipped |
| a change / follow-up that fits an existing feature but the feature is **Closed** | **SHORT (ask)** | **operator decides where it lands** — see the note below; do not auto-pick |
| a **novel capability** needing its own scope + spec (a new frozen decision) | **NEW** | Scope → the full chain (Step 1 enters at Scope) |
| **trivial** — one-liner, obvious named location | **TINY** | `add-task` + `impl` directly (or `impl` a known task) |

**Change to a *Closed* feature — the operator decides where it lands.** Do not pick reopen-vs-new-feature yourself. Propose both, with a recommendation:
- **(a) Reopen** — `add-task <feat>` appends the task (`Todo>0`); `debrief` re-appends a fresh `## Debrief close`. Keeps locality; append-only-safe.
- **(b) New small feature** — `scope-grill` → light `architect`; the closed feature stays sealed.

Do as the operator decides. Under `/goal` / `auror!` / `expelliarmus` this is a decision the skill can't self-approve → `goal: stop — closed-feature change: (a) reopen add-task <feat> | (b) new feature; rec: <…>`, **unless the directive already names the choice**.

Interactive default: state the chosen path (SHORT vs NEW: say why) before proceeding; under `/goal` / `auror!` / `expelliarmus`, classify-and-proceed and report the choice.

## Step 1 — Reconstruct the phase by inspection

Derive the phase, every time, from the feature's own artifacts (rooted at the feature's docs root — lane-agnostic; operate on "a feature in a docs root", never a hardcoded repo layout).

| Fact | Probe |
|---|---|
| **Lane count** (route guard) | Declaration-first: count trees whose `CLAUDE.md` declares a `## Lane` carrying this feature's SAID artifacts; glob fallback `*/docs/features/<feature>*.tasks.md` + `*/docs/working/<feature>/`. **≥ 2 → BLOCK, redirect to `flow!`.** |
| **Feature-id** | the arg, normalized UPPERCASE; the tasks-file stem minus `.tasks` once one exists |
| **Phase** | no `scope.md` → **Scope** · `scope.md`, no spec → **Architect** · spec + `Status: Todo` > 0 → **Implement** · spec, `Todo == 0`, **no** `## Debrief close` footer → **Deliver** · footer present → **Closed** |
| **Work remaining** | count `Status: Todo` in `docs/features/<id>.tasks.md` (bare or slug-suffixed) |
| **Gate results** | `review-qa` / `review-ux` / `accept` verdicts recorded in the tasks log / QA checklist for this feature; `—` if that gate hasn't run |
| **Eval** | `passed` when the feature's Eval result artifact (`*QA-UAT*.md` / `*QA-eval*.md` / `*evaluation*.md`) carries a pass verdict · `n/a` when scope declares no user-visible surface (Developer-Story) · else `pending` |
| **Closure** | the `## Debrief close` footer in the tasks log — the single Deliver→Closed transition |

> **`Todo == 0` is ambiguous — never key an action on it alone.** A feature never architected looks identical to one that finished. Always pair the count with the phase: **Scope** and **Architect** have work; **Deliver** does not.

**Report probe results literally** — actual output, not a summary — so a later invocation or a compaction resume can reproduce the reconstruction. If two probes disagree, trust the **artifact** and say so.

## Step 2 — Emit the stage checklist (first entry)

On the first substantive turn, resolve the ordered stage sequence **from the SAID map — the said plugin README + each skill's description — not from memory** (skills self-select by phase; do not hard-code the chain). Emit it as an explicit checklist, e.g.:

```
SAID cycle for <id> — resolved from the map:
  [ ] Scope      → /said:scope-refine (handoff) | /said:scope-grill (thin idea)
  [ ] Architect  → /said:architect
  [ ] Implement  → /said:impl (+ /said:review-ux per web task)
  [ ] Deliver    → /said:review-qa → /said:review-ux → /said:accept → /said:debrief
```

**Interactive default: confirm the checklist before proceeding.** Under `/goal` / `auror!` / `expelliarmus` this relaxes to report-and-proceed (no wait) — but every stage and gate still runs.

## Step 3 — Drive the current phase

Deterministic: the same reconstructed phase always yields the same entry. **Never guess a phase's work; invoke its skill.** Resolve `docs/features/<id>` from the feature's own docs root.

| Phase | Entry (invoke; never emulate) |
|---|---|
| **Scope** | `/said:scope-refine <handoff>` — a discovery handoff/branch state is the input. `/said:scope-grill` only for a genuinely thin idea. → produces `scope.md` (§D resolved). |
| **Architect** | `/said:architect <scope-path>` → produces the spec + `*.tasks.md`. |
| **Implement** | `/said:impl <feature-id>` (whole-feature mode). On a web/UI task, compose `/said:review-ux` at task close. Adapt or skip the UX gate on non-web — recorded, never silent. |
| **Deliver** | `/said:review-qa <id>` → (FAIL → `goal: stop`) → `/said:review-ux <id>` (if present) → (FAIL → `goal: stop`) → `/said:accept <id>` → (FAIL → `goal: stop`) → **Eval** (below) → `/said:debrief <id>` through Phase C. The `## Debrief close` footer is the Deliver→Closed transition. |
| **Closed** | no in-flight work → `said closed: yes` → `goal: done`. **A new ask on a Closed feature is a Step-0 SHORT/NEW, not `done`.** |

**Change front door (Step-0 SHORT / TINY).** `said:triage <what>` (skip if the location is named) → `said:add-task <owning-feat> [bug]`. `add-task` creates the `Todo`, so Step 1 then reconstructs **Implement** and the table above drives it — **Scope + Architect skipped**. If the owning feature is **Closed**, do not take this door on your own: **ask first (Step 0)** — the operator picks reopen (`add-task`, reopens `Todo>0`; `debrief` re-appends a close) vs a new small feature.

**Eval at Deliver.** For a feature with a user-visible surface, run the UAT/eval/e2e (Playwright MCP where available) before `debrief` and record a real verdict into the eval artifact — failures as failures, never "not run". `n/a` for a Developer-Story with no UI. An operator-confirmed **skip** is allowed only on explicit word, written as `skipped(recorded)`; under an autonomy macro that skip is a **hard blocker** (`goal: stop`) — the one wait autonomy cannot self-approve. Tooling unavailable → do not fabricate a pass; emit `UAT pending` → `goal: stop` naming the exact run owed.

**Omission is never silent.** A mandatory stage skipped or deferred without an explicit, recorded operator confirmation → **withhold `said closed: yes` and emit `goal: stop — unconfirmed omission: <stage>`**. Never present a mandatory stage as an optional offer ("if you want…"). Under autonomy this is the one wait that cannot be dropped — it forces the confirmation.

## Step 4 — Gate before end of turn

Both hold (neither skippable under an autonomy macro — autonomy removes waits, not gates):

1. **Unfiled decisions.** Every decision made this turn is written to an artifact (task body / ADR / scope). Nothing load-bearing lives only in the conversation.
2. **Emit the Output contract block** (above), every time — the `goal:` line especially. "Genuine completion" is not a prose judgement; it is `said closed: yes`, true only with footer-plus-gates.

## Step 5 — Progress check, then re-enter

Snapshot before/after every invocation: `Status: Todo` count, artifact file list, gate verdicts, footer presence. If an invocation changes **none** of them → **HALT** with `goal: stop — no progress: <what was attempted>`; do not re-enter.

Otherwise return to Step 1 and continue. Stop only on: `goal: done` (footer + gates), or `goal: stop` (failing gate / unconfirmed omission / owed operator decision / no-progress). Emit the Output contract whether or not it was asked for — if an outer orchestrator invoked this once and moved on, that block is the only thing telling it the feature is not finished.

## Never

- Emulate a `said:*` skill because invoking felt heavy.
- Drive a feature that spans ≥2 lanes — that is `said:flow`; redirect.
- Write `said closed: yes` (or `goal: done`) before the `## Debrief close` footer exists AND gates pass.
- Skip a mandatory stage silently — an unconfirmed omission is `goal: stop`, not a quiet pass.
- Carry the phase, or any decision, only in conversation across a compaction.
- Read a stored phase/state file back as truth in place of re-deriving from artifacts.
- Re-run Scope+Architect for a change that fits an existing feature — that is the short path (`triage → add-task`).
- Answer a new ask on a Closed feature with `goal: done` — classify it (Step 0), never dismiss it.
- Silently pick reopen vs new-feature for a change to a Closed feature — propose both and let the operator decide (under autonomy: `goal: stop`, unless the directive named the choice).
- Re-do work, fake the verdict, or re-emit "still waiting" when `/goal` re-fires after you already declared `goal: stop` on an owed operator decision — announce once, then hold; only the operator's reply or `/goal clear` releases it (the HITL livelock).
