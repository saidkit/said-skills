---
name: said
description: >
  Single-feature SAID orchestrator. Drives ONE feature through the full SAID phase chain — Scope -> Architect -> Implement -> Deliver — in one session, invoking the real said:* skill at each phase and self-publishing a `goal: done|continue|stop` control line every turn so a plain `/goal implement <id> as said!` runs it to closure with no hand-written condition.
  Triggered ONLY by the explicit command "/said:said <feature-id>", or by the `said!` operator macro (which calls Skill(said:said)). Do NOT trigger on general implementation, planning, or orchestration requests. For a feature spanning ≥2 SAID lanes use said:flow, not this.
---

# said:said — Single-feature SAID orchestrator

Drives one feature through its whole SAID cycle in a single session, each phase governed by its real `said:*` skill. `/said:impl` drives the *tasks* in a phase; this drives the *phases* of one feature; `said:flow` drives the *lanes* — this is its single-lane twin.

## Contract — holds every run

- **Never emulate a `said:*` skill.** Scope, architect, implement, gate, debrief through the real commands. Caught writing a spec or task by hand -> stop and invoke.
- **Reconstruct the phase by inspection, every invocation** (Step 1). Never read a stored phase/state file back as truth — re-derive from the feature's artifacts. This is what makes the skill re-entrant across compaction: a compaction is not a stop; re-enter and continue.
- **Main-context; never spawn to decide.** The governed cycle runs in the main context; verify inline. A depth-1 invocation (e.g. `said!` under `/goal` + an autonomy macro) is **tolerated, not an error**: it verifies inline, and the `said:*` skills it invokes do their own read-only spawning **one level down**. The real per-subagent limits are *no operator* (a subagent can't hold a decision) and no ability to orchestrate a background build — not "no nested spawning"; every operator question returns as data.
- **Single-lane only.** ≥2 lanes carry the feature's SAID artifacts -> **BLOCK + redirect to `flow!` / `/said:flow`** (Step-1 route guard). A mount is not a lane.
- **Classify the request first (Step 0).** A bug / tweak / follow-up that fits an existing feature takes the SHORT path (`triage -> add-task -> impl -> deliver`), never a from-scratch Scope->Architect walk. A Closed feature + a new ask is never `goal: done` — and where that change lands (reopen vs new feature) is the **operator's** decision: propose both, never pick silently.
- **Closure = footer AND gates, published as the `goal:` line every turn.** `said closed: yes` (<=> `goal: done`) ONLY when the tasks log has a `## Debrief close` footer AND every gate passed (or a recorded, operator-confirmed skip). Emit the Output contract — the `goal:` line especially — on every invocation, including `status` mode and a no-action turn.
- **Contradict a premature "done".** Never write "done"/"closed"/"nothing left" while the block says `no`; if an outer orchestrator declared the work finished and the block says `no`, say so and contradict it.
- **Loop, not one-shot.** While the `goal:` line reads `continue`, the only correct next action is to re-invoke `/said:said <feature-id>` — never tick a step done or move on.
- **`stop` is surfaced, not enforced — announce once, then hold.** `/goal`'s evaluator is binary (only *met* ends the loop); it **re-fires after a `goal: stop`** because the feature is not `done`. So an operator question the agent must not answer itself — a UAT/aesthetic sign-off, an ambiguous reopen-vs-new, any human judgment — is announced **exactly once** -- the `goal: stop` line carries the marker `OPERATOR-QUESTION-HELD` -- with the operator question, the options, and how to unblock (reply the answer, or `/goal clear` to release the loop). On every re-fire after that, **hold** — no new work, no manufactured verdict, no repeated "still waiting". Faking the judgment, or re-emitting until the Stop-hook block-cap force-kills the turn, is the failure this rule prevents (the HITL livelock).
- **Context checkpoint at a phase boundary.** The check is off by default: it runs only in a session that switched it on with the environment variable `SAID_CONTEXT_CHECKPOINT` set to `on` (read it first, with one `echo "${SAID_CONTEXT_CHECKPOINT:-unset}"` call at the boundary); unset or any other value means no check, no stop and no notice -- proceed. When it is on: at Implement->Deliver (before `review-qa`) and again before `debrief`, read `context.json` in this session's scratchpad (written by the plugin's statusline script). If its `total_input_tokens` exceeds the lane's `SAID.context-checkpoint:` (optional scalar key; default 300000 when absent), print `CONTEXT-CHECKPOINT -- safe point: /clear, then said! <feature-id> (resumes at <phase>)` and stop. A missing `context.json` (or a null value) -> skip the check and proceed, never a block; the first such skip in a session prints one line `context checkpoint inactive: run /said:setup statusline` (once, best effort: a compaction may repeat it; the notice is never a stop and never a `goal:` line); never read the file from an older session. Under `/goal` the threshold stop above is the line `goal: stop -- CONTEXT-CHECKPOINT: /clear, then re-issue the directive`: announce once, then hold on every re-fire (no new work, no repeated print). It is an operator action, not an operator question, so it carries no `OPERATOR-QUESTION-HELD`. After the `/clear`, the re-issued directive re-derives the phase from disk (Step 1) and continues; a Deliver resume starts at the first gate without a recorded pass (Step 1 **Gate results**), so a checkpoint before `debrief` resumes at `debrief` and never re-runs a passed gate.
- **The SAID map is authoritative, not this file.** Phase->skill selection, gate order, and branch points come from the plugin README + each skill's description (Step 2). Project conventions (task-id shape, tasks-file location, QA-artifact names) come from the project's `CLAUDE.md` / stencils — read them at Step 1; never assume shapes.

## Invocation

- `/said:said <feature-id>` — do the next thing for this feature, then emit the Output contract.
- `/said:said <feature-id> status` — reconstruct and report the phase only; take no action.

Preconditions — any failure BLOCKS with a named redirect:

- **Single-lane only.** Feature carries SAID artifacts (`scope.md`, spec, or task log) in ≥2 lanes — declaration-first: the lanes the root's `SAID.lanes:` registry names where one is declared, else each tree's `CLAUDE.md` `## Lane` block, glob fallback -> **BLOCK + redirect to `flow!` / `/said:flow`**. (A mount, where a lane's production lands, is not a lane; one feature may touch several mounts and stay single-lane.)
- **Pick the entry (Step 0).** Classify the directive first — a bare feature-id resumes where it sits; a change/bug/follow-up on an existing feature takes the short path; a novel capability starts at Scope.

## Output contract

Every invocation ends with this block. No exceptions — including `status` mode and a no-action turn.

```
feature: <id>
phase: <Scope|Architect|Implement|Deliver|Closed> — <n> Todo
gates: review-qa <pass|fail|—>, review-ux <pass|fail|—>, accept <pass|fail|—>, Eval <passed|pending|n/a>
said closed: yes|no
goal: done | continue | stop — <reason>   # /goal reads this line: done|stop end the run, continue = re-invoke; an operator-question stop carries OPERATOR-QUESTION-HELD
```

`said closed: yes` is permissible ONLY with the `## Debrief close` footer present AND every gate passed (or a recorded, confirmed skip). The footer is written at debrief Phase C after its Phase-3.5 gate-check clears; a `debrief.md` from debrief Phase A is NOT closure. Anything short of footer-plus-gates is `no`. **A MANUAL-PENDING accept is not a passed gate** -- it is an operator question (`accept:164` surfaces it at debrief preflight); withhold `said closed: yes` and hold (announce once, then hold) until the operator resolves it, never auto-promote it to passed. Likewise a **reviewer-gate that could-not-run** (a declared reviewer's verdict could not be produced) is not a passed gate -- withhold `said closed: yes` and hold; distinct from a ran-and-FAILed reviewer (surfaced, not blocking) and an operator `[N/A]` (passed).

The `goal:` line is the loop oracle — a plain directive (`/goal implement <id> as said!`) drives it, no hand-written condition:
- `done` = `said closed: yes` (footer present AND gates passed).
- `stop` = blocked, for one of two kinds of reason: (a) the operator owes an **answer** -- an unconfirmed omission (mandatory stage skipped without a recorded confirmation) or an operator question (e.g. a UAT skip on a UI feature); grant consumption (below) applies only to this kind; (b) blocked on an operator **action** or a gate -- a failing gate (`review-qa`/`review-ux`/`accept` FAIL), a context checkpoint (`CONTEXT-CHECKPOINT`, Contract), or a no-progress HALT (Step 5); no grant releases these. When the `stop` is specifically an **operator question** (not a failing gate or omission), the `goal: stop` line carries the marker **`OPERATOR-QUESTION-HELD`** -- a full-token string the unchanged engine never prints (identical spelling in the magic arm); it signals the held state once and keeps it derivable by `status`/`board`. A confirmation or form-choice stop carries no such marker. **Grant consumption:** before an operator question holds, check whether the directive **names** it -- a **named advance decision covers only its named class** (it pre-answers every operator question in that one named class and nothing outside it -> an in-class question proceeds, reported; any question outside the named class still holds), while a **blanket** grant (an autonomy macro naming no class) covers **how-to-build choices only** and **never covers an operator question** (it does not relax the hold; name the reserved class to pre-answer it).
- `continue` = a phase still has work.
`done` ends the `/goal` loop — the evaluator, reading the transcript, sees closure. `stop` is your **terminal intent**, but `/goal` is binary and **re-fires anyway**: phrase the `<reason>` so the evaluator can release (state the block is operator-owned and autonomous progress is exhausted) and the operator can act (reply the answer, or `/goal clear`). On a re-fire, **hold** — announce once, then no new work (Contract). `continue` re-invokes.

---

## Step 0 — Classify the request -> pick the path

Before reconstructing anything, decide which entry the directive needs (first match wins). The test that splits SHORT from NEW: **does this work need its own scope + spec, or does it fit as a task on an existing feature?**

| The directive is... | Path | Entry |
|---|---|---|
| a bare feature-id; feature **in-flight** (Todo>0 / phase < Closed) | **RESUME** | Step 1 -> drive the chain from its phase |
| a bare feature-id; feature **Closed**, no new ask | **DONE** | report Closed -> `goal: done`; take no action |
| a change / bug / follow-up that **fits an existing feature's scope** (feature **open**) | **SHORT** | `triage` -> `add-task` -> Implement (Step 3 front door); Scope + Architect skipped |
| a change / follow-up that fits an existing feature but the feature is **Closed** | **SHORT (ask)** | **operator decides where it lands** — see the note below; do not auto-pick |
| a **novel capability** needing its own scope + spec (a new frozen decision) | **NEW** | Scope -> the full chain (Step 1 enters at Scope) |
| **trivial** — one-liner, obvious named location | **TINY** | `add-task` + `impl` directly (or `impl` a known task) |

**Change to a *Closed* feature — the operator decides where it lands.** Do not pick reopen-vs-new-feature yourself. Propose both, with a recommendation:
- **(a) Reopen** — `add-task <feat>` appends the task (`Todo>0`); `debrief` re-appends a fresh `## Debrief close`. Keeps locality; append-only-safe.
- **(b) New small feature** — `scope-grill` -> light `architect`; the closed feature stays sealed.

Do as the operator decides. Under `/goal` / an autonomy macro this is a decision the skill can't self-approve -> `goal: stop — closed-feature change: (a) reopen add-task <feat> | (b) new feature; rec: <...>`, **unless the directive already names the choice**.

Interactive default: state the chosen path (SHORT vs NEW: say why) before proceeding; under `/goal` / an autonomy macro, classify-and-proceed and report the choice.

## Step 1 — Reconstruct the phase by inspection

Derive the phase, every time, from the feature's own artifacts (rooted at the feature's docs root — lane-agnostic; operate on "a feature in a docs root", never a hardcoded repo layout).

| Fact | Probe |
|---|---|
| **Lane count** (route guard) | Declaration-first: where the root declares a `SAID.lanes:` registry, count the lanes its rows name (`python3 ${CLAUDE_SKILL_DIR}/../status/said_status.py --registry --root <root>`; on `refused:` HALT with that reason) that carry this feature's SAID artifacts; else count trees whose `CLAUDE.md` declares a `## Lane` carrying this feature's SAID artifacts; glob fallback `*/docs/features/<feature>*.tasks.md` + `*/docs/working/<feature>/`. **≥ 2 -> BLOCK, redirect to `flow!`.** |
| **Feature-id** | the arg, normalized UPPERCASE; the tasks-file stem minus `.tasks` once one exists |
| **Phase** | no `scope.md` -> **Scope**, `scope.md`, no spec -> **Architect**, spec + `Status: Todo` > 0 -> **Implement**, spec, `Todo == 0`, **no** `## Debrief close` footer -> **Deliver**, footer present -> **Closed** |
| **Work remaining** | count `Status: Todo` in `docs/features/<id>.tasks.md` (bare or slug-suffixed) |
| **Gate results** | `review-qa` / `review-ux` / `accept` verdicts recorded in the tasks log / QA checklist for this feature; `—` if that gate hasn't run |
| **Eval** | `passed` when the feature's Eval result artifact (`*QA-UAT*.md` / `*QA-eval*.md` / `*evaluation*.md`) carries a pass verdict, `n/a` when scope declares no user-visible surface (Developer-Story), else `pending` |
| **Closure** | the `## Debrief close` footer in the tasks log — the single Deliver->Closed transition |

> **`Todo == 0` is ambiguous — never key an action on it alone.** A feature never architected looks identical to one that finished. Always pair the count with the phase: **Scope** and **Architect** have work; **Deliver** does not.

**Report probe results literally** — actual output, not a summary — so a later invocation or a compaction resume can reproduce the reconstruction. If two probes disagree, trust the **artifact** and say so.

## Step 2 — Emit the stage checklist (first entry)

On the first substantive turn, resolve the ordered stage sequence **from the SAID map — the said plugin README + each skill's description — not from memory** (skills self-select by phase; do not hard-code the chain). Emit it as an explicit checklist, e.g.:

```
SAID cycle for <id> — resolved from the map:
  [ ] Scope      -> /said:scope-refine (handoff) | /said:scope-grill (thin idea)
  [ ] Architect  -> /said:architect  (optional design-seed/inspect: /said:uxtoc)
  [ ] Implement  -> /said:impl (+ /said:review-ux per task on a lane with an agent-form Checker)
  [ ] Deliver    -> /said:review-qa -> /said:review-ux -> /said:accept -> /said:debrief
```

**Interactive default: confirm the checklist before proceeding.** Under `/goal` / an autonomy macro this relaxes to report-and-proceed (no wait) — but every stage and gate still runs.

## Step 3 — Drive the current phase

Deterministic: the same reconstructed phase always yields the same entry. **Never guess a phase's work; invoke its skill.** Resolve `docs/features/<id>` from the feature's own docs root.

| Phase | Entry (invoke; never emulate) |
|---|---|
| **Scope** | `/said:scope-refine <handoff>` — a discovery handoff/branch state is the input. `/said:scope-grill` only for a genuinely thin idea. -> produces `scope.md` (§D resolved). |
| **Architect** | `/said:architect <scope-path>` -> produces the spec + `*.tasks.md`. |
| **Implement** | `/said:impl <feature-id>` (whole-feature mode, serial) — **or task-level fan-out** when ≥2 `Todo` tasks are write-disjoint and the directive carries the `fan-out` opt-in word (see **Task-level fan-out** below). Compose `/said:review-ux` at task close; it resolves `SAID.reviewers:` and runs each declared Checker — Playwright walk for the `web-ux` Checker, schema/contract/invocation checks for a `cli`/`api`/`mcp` Checker. A genuine no-surface-contract skip is recorded, never silent. A `Status: Todo` task carrying an unresolved `Blocked-on question <id>` marker is held, not built: excluded from the build set (and from the fan-out partition), the run emits `goal: stop` + `OPERATOR-QUESTION-HELD` (a task-blocking operator question) -- `impl` returns it as an owed item, `said` emits the token. |
| **Deliver** | `/said:review-qa <id>` -> (FAIL -> `goal: stop`) -> `/said:review-ux <id>` (if present) -> (FAIL -> `goal: stop`) -> `/said:accept <id>` -> (FAIL -> `goal: stop`) -> **Eval** (below) -> `/said:debrief <id>` through Phase C. The `## Debrief close` footer is the Deliver->Closed transition. After a context-checkpoint `/clear`, start at the first gate whose pass is not yet recorded (Step 1 **Gate results**). |
| **Closed** | no in-flight work -> `said closed: yes` -> `goal: done`. **A new ask on a Closed feature is a Step-0 SHORT/NEW, not `done`.** |

**Task-level fan-out (opt-in) — arms build, main decides (`ADR-SAID-S09`).** When the feature at Implement has **≥2 `Status: Todo` tasks whose write-sets are disjoint** AND the operator's directive carries the opt-in word **`fan-out`** (e.g. `/goal implement <id> fan-out as said!`), drive the Implement row as a fan-out instead of serial whole-feature:
1. **Partition in main.** Compute each `Todo` task's **write-set** = its `Refs:` ∪ the files under the lane's mounts that its Approach names ∪ the spec's implementation pointers — in main, at fan-out time, never declared in the task body. Disjoint tasks fan out; any task that intersects another, or that edits the feature's own log/spec, is the **serial set** (a shared root — `said:flow`'s rule 4 applied to tasks). A task carrying an unresolved `Blocked-on question <id>` marker is excluded from both sets and held (`goal: stop` + `OPERATOR-QUESTION-HELD`), never fanned out.
2. **Spawn arms via the Workflow tool.** One `/said:impl <task> arm` **per disjoint task**, concurrent under a barrier — the Workflow tool exists only here in the main context, so this is the only place fan-out can happen. Each arm builds under forced autonomy and returns a close block (owed items included); it never writes the log and never decides.
3. **Close serially in main.** After the barrier, `/said:impl <task> close` **per task, serially in main** — apply each returned block, run Phase C, write the append-only log. Meanwhile main works the **serial set** (the intersecting + own-log tasks) itself. Compose, never emulate — every stage invokes the real `/said:impl ... arm|close` by name.
4. **The fan-out spawn turn emits `goal: continue`; the closes land on the completion turn.** The turn does **not** finish its work at the Workflow call — the tool returns a task id and completion arrives as a notification that re-invokes main. On the spawn turn, emit `goal: continue — fan-out: <N> arms building <tasks>` (spawning the workflow **is** this turn's progress, so the Step-5 no-progress HALT does **not** apply — see Step 5); the per-task closes and their own `goal:` line land on the completion turn. Then re-enter Step 1. Decisions — gate verdicts, closes, reopen-vs-new, UAT skips — stay in main.

**Without the opt-in word, or with <2 disjoint tasks, the Implement row is unchanged** (`/said:impl <feature-id>` whole-feature, serial). **Inside a subagent** (depth-1) the Workflow tool is unavailable, so a `fan-out` request is **recorded as a skip** (per the Contract's depth clause) and the feature is driven serially — never a nested-spawn attempt.

**Change front door (Step-0 SHORT / TINY).** `said:triage <what>` (skip if the location is named) -> `said:add-task <owning-feat> [bug]`. `add-task` creates the `Todo`, so Step 1 then reconstructs **Implement** and the table above drives it — **Scope + Architect skipped**. If the owning feature is **Closed**, do not take this door on your own: **ask first (Step 0)** — the operator picks reopen (`add-task`, reopens `Todo>0`; `debrief` re-appends a close) vs a new small feature.

**Eval at Deliver.** For a feature with an evaluable surface, run the surface-appropriate eval before `debrief` (a UAT/e2e via Playwright MCP where available for a `web` surface; contract/e2e checks for an `api` / `mcp` / `cli` surface; for a `doc` surface the **doc Eval** below) and record a real verdict into the eval artifact — failures as failures, never "not run". `n/a` only for a Developer-Story with no evaluable surface. An operator-confirmed **skip** is allowed only on explicit word, written as `skipped(recorded)`; under an autonomy macro that skip is a **hard blocker** (`goal: stop`) — the one wait autonomy cannot self-approve. Tooling unavailable -> do not fabricate a pass; emit `UAT pending` -> `goal: stop` naming the exact run owed.

**The doc Eval (a `doc` surface).** Spawning nothing (this skill never spawns to decide), after `accept` and at HEAD: (a) re-run the lane's umbrella inline — `SAID.commands: doc-gate`, expanded by the resolution chain's doc terminal — over every path of `SAID.mounts:` and every task log of the feature, teeing to `docs/working/<id>/doc-gate-eval-<id>.log` (its own name; `debrief`'s later re-run does not tee); (b) read `docs/working/<id>/review-doc-editorial-<id>.md` — the feature-scope verdict `/said:review-ux <id>` wrote at this Deliver row — as recorded evidence. FAIL if the umbrella is non-zero, or that verdict reads FAIL, or it is missing although review-ux ran; record both results into `docs/working/<id>/QA-eval-<id>.md` (the Eval artifact the Step-1 probe reads). Like a `cli` lane's contract re-run, this is a Deliver-time re-execution plus a read of the recorded judgment — the cross-artifact read itself is review-ux's.

**Omission is never silent.** A mandatory stage skipped or deferred without an explicit, recorded operator confirmation -> **withhold `said closed: yes` and emit `goal: stop — unconfirmed omission: <stage>`**. Never present a mandatory stage as an optional offer ("if you want..."). Under autonomy this is the one wait that cannot be dropped — it forces the confirmation.

## Step 4 — Gate before end of turn

Both hold (neither skippable under an autonomy macro — autonomy removes waits, not gates):

1. **Unfiled decisions.** Every decision made this turn is written to an artifact (task body / ADR / scope). Nothing load-bearing lives only in the conversation.
2. **Emit the Output contract block** (above), every time — the `goal:` line especially. "Genuine completion" is not a prose judgement; it is `said closed: yes`, true only with footer-plus-gates.

## Step 5 — Progress check, then re-enter

Snapshot before/after every invocation: `Status: Todo` count, artifact file list, gate verdicts, footer presence. If an invocation changes **none** of them -> **HALT** with `goal: stop — no progress: <what was attempted>`; do not re-enter. **Exception — a fan-out spawn turn:** spawning the arms via the Workflow tool is progress (the arms are building; their closes land on the async completion turn, not this one), so that turn emits `goal: continue`, never the no-progress HALT.

Otherwise return to Step 1 and continue. Stop only on: `goal: done` (footer + gates), or `goal: stop` (failing gate / unconfirmed omission / operator question / no-progress). Emit the Output contract whether or not it was asked for — if an outer orchestrator invoked this once and moved on, that block is the only thing telling it the feature is not finished.

## Never

- Emulate a `said:*` skill because invoking felt heavy.
- Drive a feature that spans ≥2 lanes — that is `said:flow`; redirect.
- Write `said closed: yes` (or `goal: done`) before the `## Debrief close` footer exists AND gates pass.
- Skip a mandatory stage silently — an unconfirmed omission is `goal: stop`, not a quiet pass.
- Carry the phase, or any decision, only in conversation across a compaction.
- Read a stored phase/state file back as truth in place of re-deriving from artifacts.
- Re-run Scope+Architect for a change that fits an existing feature — that is the short path (`triage -> add-task`).
- Answer a new ask on a Closed feature with `goal: done` — classify it (Step 0), never dismiss it.
- Silently pick reopen vs new-feature for a change to a Closed feature — propose both and let the operator decide (under autonomy: `goal: stop`, unless the directive named the choice).
- Re-do work, fake the verdict, or re-emit "still waiting" when `/goal` re-fires after you already declared `goal: stop` on an operator question — announce once, then hold; only the operator's reply or `/goal clear` releases it (the HITL livelock).
