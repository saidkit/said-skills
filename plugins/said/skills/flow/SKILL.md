---
name: flow
description: >
  Multi-lane SAID orchestrator. Drives a feature that spans two or more lanes
  (parts of multi-repository project: frontend / backend / apps) 
  through every lane's own SAID cycle in one session — inspecting on-disk artifacts 
  to decide the next action, forking independent arms, and batching cross-lane 
  handovers so lanes don't serialize.
  Triggered ONLY by the explicit command "/said:flow <feature-id>". Do NOT trigger
  on general implementation, planning, or orchestration requests. Only the exact
  command "/said:flow" activates this skill.
---

# said:flow — Multi-lane SAID orchestrator

Drives one feature across every lane it touches, in a single session, with each lane governed
by its real SAID skills. Replaces the pattern where an operator manually launches a session per
lane and hand-carries handovers between them.

`/said:impl <feature>` drives tasks within a lane. **This drives lanes within a feature.**

## Why this is a skill and not an agent

**Claude Code does not permit nested subagent spawning** 
(`said/skills/impl/SKILL.md` — *"Claude Code constraint: no nested subagent spawning"*).
`/said:impl`, `/said:triage`, `/said:scope-refine` and `/said:review-ux` all spawn agents. A
subagent asked to "be the backend lane" hits a wall at the first gate and hand-rolls the chain —
the exact emulation failure the methodology exists to prevent.
Skills compose freely: a skill is instructions loaded into the one agent that has skill reach.
**So every governed lane cycle runs in the main context, and subagents are used only for
read-only work needing genuine context isolation.**

## Prime directives

1. **Never emulate a `said:` skill.** Architect, implement, gate, debrief through the real
   commands. Caught writing a spec by hand? Stop and invoke.
2. **State lives in artifacts, never in conversation.** Every invocation reconstructs by
   inspection. This is what makes the skill re-entrant across compaction.
3. **A compaction is not a stop.** Re-enter and continue.
4. **Minimize crossings, don't schedule around them.** Most cross-lane items are mechanical
   consequences of decisions already made.

## Invocation

- `/said:flow <feature-id>` — do the next thing.
- `/said:flow <feature-id> plan` — author the lane DAG (Step 2), then stop.
- `/said:flow <feature-id> status` — report Step 1 only, take no action.

Preconditions. Any failure BLOCKS with a named redirect:

- A `scope.md` exists for the feature in at least one lane, §D resolved. Else →
  `/said:scope-refine` or `/said:scope-grill`.
- The feature spans **≥ 2 lanes carrying their own SAID artifacts (a `scope.md`, spec, or
  task log) — not ≥ 2 repos, and NOT counted by task-log presence**. Count lanes by the
  Step-1 declaration-first enumeration: a lane still at Scope or Architect has no task log
  yet but is a full lane. A lane owns a full SAID cycle (its own feature specs, task log,
  working dir, ADRs); a mount is where code lands. One feature may change code in several
  mounts and remain single-lane. Single-lane → `/said:impl`.

## Output contract

Every invocation ends with this block. No exceptions — including `plan` and `status` modes,
and including an invocation that took no action.

```
feature: <id>
lanes:
  <lane> — <feature-id> — phase <Scope|Architect|Implement|Gates|Closed> — <n> Todo
crossings: <name> — open|replied|consumed
feature e2e/UAT: passed|pending|skipped(recorded)|n/a(no UI)
feature closed: yes|no
goal: done | continue | stop — <reason>   # /goal reads this line: done|stop end the run, continue = re-invoke
```

**`feature closed: yes` is permissible only when every lane's phase reads `Closed` AND `feature e2e/UAT` is not `pending`.** A lane
is `Closed` only when its own `debrief.md` exists in its working dir, its task log carries a
`## Debrief close` footer, **and** no crossing addressed to it is still open. `debrief.md`
alone is NOT `Closed` — it is written at debrief Phase A, before the footer. **`feature e2e/UAT`** is the integrated, cross-lane run that only becomes possible once every lane is `Closed` — per-lane `accept` verified each lane in isolation and cannot cover it: `passed` when the feature's UAT result artifact carries a pass verdict, `skipped(recorded)` when an operator-confirmed skip is written into that artifact, `n/a(no UI)` for a feature with no user-visible surface, `pending` otherwise — and a `pending` UAT holds the feature open exactly as an unclosed lane does. Anything short of all of this is `no`.

**The `goal:` line is the loop oracle** — self-describing, so a `/goal` driving this skill needs **no** hand-written completion condition; a plain directive (`/goal flow! implement <id>`) is enough. `done` = `feature closed: yes`. `stop` = the run is blocked or needs an operator decision — an externally-owned open crossing (Rule 8), a no-progress HALT (Step 6 / Rule 9), a failing lane gate, or an owed operator decision (e.g. a UAT skip). `continue` = everything else. `done` and `stop` both end the `/goal` loop (`stop` hands the operator the `<reason>`); `continue` is what re-invokes.

Never write "closed", "done", "nothing left" or equivalent into a resume pointer, a report or
a chat summary while this block says `no`. **If an outer orchestrator has already declared the
work finished and this block says `no`, say so and contradict it** — that contradiction is the
most valuable thing this skill emits, and suppressing it is how a lane silently ships without
its gates.

**This skill is a loop, not a one-shot.** A caller that invoked it once — including an outer
planner such as `/magic:think-deep` that scheduled "invoke `/said:flow`" as a single step —
has **not** run it to completion; it has taken one step of an N-step loop. While the `goal:`
line reads `continue`, the only correct next action is to **re-invoke `/said:flow
<feature-id>`**, never to tick a step done or move on.

---

## Step 1 — Reconstruct state by inspection

Never read a state file. Derive everything, every time.

| Fact | Probe |
|---|---|
| Lanes involved | **Declaration first:** read each candidate tree's `CLAUDE.md` for a `## Lane` block and take its declared docs root, task-log path, working dir, task-id shape and ADR prefix verbatim. **Fallback:** where no block exists, glob `*/docs/features/<feature>*.tasks.md` and `*/docs/working/<feature>/`. A repo root's `CLAUDE.md` may carry a lane registry naming where each lane starts — enumerate from it when present |
| **Feature-id per lane** | the matched `*.tasks.md` filename stem minus `.tasks` — e.g. `PROJ-01` (front), `PROJ-01-BE` (server), `PROJ-02-BE-widgets`. **Record it. Every later invocation targeting that lane uses the lane's own id, never the umbrella id.** A lane's suffix is what makes its id globally unique; assuming the umbrella id silently addresses the wrong lane's log |
| Lane phase | no `scope.md` → **Scope** · scope, no spec → **Architect** · spec+tasks, `Status: Todo` > 0 → **Implement** · spec+tasks, Todo == 0, no `## Debrief close` footer in the tasks log → **Gates** (a `debrief.md` may already exist mid-debrief — it is written at debrief Phase A, before the footer; `debrief.md` presence alone is NOT `Closed`) · `## Debrief close` footer present **and no open inbound crossing addressed to the lane** → **Closed** |
| Work remaining | count `Status: Todo` in that lane's `*.tasks.md` |
| Crossings | `BE-handover-*.md` (or lane equivalent) — **open** iff no sibling `*-reply.md` and no `## Reply` section appended (match the heading **case-insensitively** — canonical form is `## Reply`) |
| Blocked tasks | task entries whose Approach or Out-of-scope names an open crossing |
| Shared root | does scope name an upstream both lanes clone (e.g. an engine étalon)? is it complete? |
| **Feature e2e/UAT** | the integrated cross-lane run (only meaningful once **all** lanes `Closed`). **Declaration first:** honor a feature-UAT artifact location declared in the repo-root `CLAUDE.md`. **Fallback:** glob the feature working dir(s) for a UAT result artifact (`*QA-UAT*.md` / `*uat*.md`) carrying a filled result matrix. `passed` = pass verdict present · `skipped(recorded)` = an operator skip recorded in it · `n/a` = scope declares no UI behavior (Developer-Story) · else `pending` |

> **`Todo == 0` is ambiguous — never key an action on it alone.** A lane with zero tasks
> because it was never architected looks identical to one that finished. Always pair the count
> with the phase: **Scope** and **Architect** have work, **Gates** does not. This is why Step 3
> rules 3, 5, 6 and 7 all key on phase, and why "has work" means the same thing for the loaded
> lane as for any other — the asymmetry between them was a bug.

**Report probe results literally** — actual output, not a summary. A future invocation must be
able to reproduce the reconstruction. If two probes disagree (a task says blocked but its
crossing has a reply), trust the **artifact** and say so.

## Step 2 — Author or read the lane DAG

**Re-run only when** scope §5 (or the equivalent sequencing section) lacks lane tags, or the
scope itself changed. An existing DAG is read, not re-authored — re-deriving it each invocation
makes the skill non-deterministic across compaction.

Tag every piece `[lane: FE | BE | shared-root]`, **written into scope §5 itself** — never a
parallel state file, which drifts. Then classify every item where one lane needs something from
another:

> **Classification test.** *Could the other lane legitimately answer "no, and here is why",
> citing a contract, schema reality or physical constraint I do not hold?*
>
> **Yes → NEGOTIATION.** Needs a crossing.
> **No → MECHANICAL.** Belongs in the owning lane's own task log. No crossing.

**Where a MECHANICAL item lives before the receiving lane has a task log.** It does not become a
task by being classified. The receiving lane authors its own tasks at its Architect phase
(§4.1) — this skill never writes into another lane's log, because that is the lane's authority,
not the orchestrator's.

Until then, carry mechanical items in the handover as a **manifest**, stated in the future
tense and clearly marked as not part of the negotiation:

> The following are mechanical — every design decision is already fixed in scope at verified
> `file:line`. They are **not** part of this negotiation and need no reply. They will be
> authored into `<lane>`'s task log when that lane runs its Architect phase.

**Never write that they "are authored into" a log that does not exist.** That claim sends the
receiving lane looking for a file that is not there, and leaves the items in neither the
handover nor a log. If the receiving lane has no task log yet, say so in the manifest.

Most items are MECHANICAL: a migration whose column type, nullability and target tables are
already fixed in scope; cloning a shared engine at a determined version; appending a field to
three known lists. A NEGOTIATION is where the other lane owns the *design* — which columns a
report carries, what shape an endpoint takes, whether a rule belongs server-side at all.

**Getting this wrong is the main failure mode.** Over-classifying manufactures serialization —
five crossings where one was needed. Under-classifying loses the check that catches *"your
handover asks for full precision but the column rounds to 2dp"*.

Then mark **joins** — where an arm cannot proceed until a reply lands.

**If classification contradicts a handover already on disk**, do not silently rewrite or
silently proceed. Report:

> `BE-handover-X.md` contains N items; classification makes M of them MECHANICAL (they belong
> in `<lane>`'s own task log). Recommend narrowing the handover to the NEGOTIATION items.

Then act on the answer, or under an autonomy macro adopt the narrowed reading and say so.

## Step 3 — Select the next action

Deterministic: the same reconstructed state must always yield the same action.

Rules 1–3 are **non-blocking** — act, then keep evaluating in the same turn. Rules 4+ are
**terminal for the turn** — first match wins, then re-enter at Step 1.

| # | Condition | Action | Blocking? |
|---|---|---|---|
| 1 | A crossing has a reply not yet consumed | **JOIN** — read reply, unblock its tasks, record any pushback in the receiving lane's log | no |
| 2 | NEGOTIATION items with **no handover sent**, arm ready | **SEND ONE BATCHED HANDOVER** + spawn the audit (§4.3) | no |
| 3 | Another lane has work (phase ∈ {Scope, Architect} **or** unblocked `Todo` > 0), fork available, preconditions hold | **FORK now** — starts that arm's clock at zero cost | no |
| 4 | Shared root incomplete | **DO IT** in main context — it blocks every arm | yes |
| 5 | Loaded lane **has work** — phase ∈ {Scope, Architect} **or** unblocked `Todo` > 0 | enter at its §4.1 entry point (`scope-refine` / `architect` / `impl`) | yes |
| 6 | Another lane has work, fork **unavailable** | **ROTATE** (§4.2) | yes |
| 7 | **Every** lane's phase ∈ {Gates, Closed}, no open crossings | **CLOSE — two stages.** (i) **Lanes:** for each lane not yet `Closed`, from that lane's own docs root with its recorded feature-id, run its **Gates entry (§4.1)** — halt on any FAIL. (ii) **Feature:** once **every** lane reads `Closed`, if `feature e2e/UAT` is still `pending`, run the **feature-level e2e/UAT (§4.4)** — the integrated cross-lane gate per-lane `accept` cannot be. **Not discharged until every lane reads `Closed` AND `feature e2e/UAT` ∈ {`passed`, `skipped(recorded)`, `n/a`}** — one pass over one lane, or a `pending` UAT, does not satisfy this rule | yes |
| 8 | Only externally-owned open crossings remain | **REPORT WAITING** — the one legitimate stop | yes |
| 9 | Nothing matched | **HALT**, report the reconstruction that produced no action | yes |

**Rule 3 sits above the work rules** because forking is non-blocking — it starts the other arm
and returns. Evaluating it after local work means the second arm begins only once the first is
exhausted, which is the serialization this skill exists to remove.

**Rule 4 below rule 3 is safe** because §4.2's preconditions forbid forking an arm that shares
an incomplete root — so rule 3 cannot fire for a root-dependent arm. Root-independent arms fork
immediately; root-dependent ones fork on the next pass.

**A crossing addressed to a lane that has otherwise reached `Gates`/`Closed` reopens that
lane.** An open inbound crossing is an owed reply — real work, not an external wait. Such a
lane is not `Closed` (per the Output-contract definition); treat it as a lane with work for
Rules 3/5/6 (an owed reply is unblocked work) and route it to its §4.1 entry (or a JOIN/reply). An open *internal* crossing must never fall
through to Rule 9 HALT.

## Step 4 — Execute the selected action

### 4.1 Lane entry points

Entering a lane — by fork, rotation, or because it is already loaded — the phase determines
which skill starts it. **Never guess, never hand-roll the phase's work.**

**Invoke every lane skill from that lane's own docs root** (the docs root recorded in Step 1
from its `## Lane` block) — `cd` into it or pass lane-rooted paths. `impl` / `review-qa` /
`accept` / `debrief` resolve `docs/features/<id>` from the current working directory and take
no path argument, so an invocation from the umbrella root (or another lane's root) resolves
against the wrong tree — silently the wrong lane's files, or none.

| Lane phase | Entry point |
|---|---|
| **Scope** | `/said:scope-refine <handoff-path>` — the handover plus audit findings are the handoff. `/said:scope-grill` only for a genuinely thin idea |
| **Architect** | `/said:architect <scope-path>` |
| **Implement** | `/said:impl <feature-id>` — whole-feature mode |
| **Gates** | `/said:review-qa <feature-id>` → (halt on FAIL) → `/said:accept <feature-id>` → (halt on FAIL) → `/said:debrief <feature-id>` through Phase C — the `## Debrief close` footer is the Gates→Closed transition. **This is the single source for the per-lane gate chain; Rule 7 invokes it per lane** |
| **Closed** | nothing — do not re-enter |

### 4.2 Fork vs rotate

**FORK** — launch the lane as a *peer session* (one-time scheduled/cloud agent): a main agent
with full skill reach and its own context budget. It runs that lane's cycle and writes the
reply; you continue the current arm. Wall-clock becomes `max(arms)`, not `sum(arms)`.

Fork only when **all** hold:
- the arms share no incomplete root,
- they write to different mounts,
- no open crossing blocks the forked arm.

The peer session starts with **no memory of this conversation** — name its entry point
explicitly. *"Run the BE lane"* is not actionable; *"run `/said:scope-refine
<path>/BE-handover-<topic>.md`, then continue the chain"* is.

**ROTATE** — degraded mode when forking is unavailable. Finish what the current lane can do,
then load the other lane's `CLAUDE.md`, drop the previous working set, and run its cycle here.
Correct but serial.

Peer-session availability is environment-dependent. **Probe once, cache for the session, degrade
to rotate, and state which mode you are in.** Never block on it.

### 4.3 The background contract audit

Sending a handover: spawn a **read-only** subagent and **do not wait** — subagents run in the
background; keep working the current arm.

Give it only the target lane's `CLAUDE.md`, that lane's ADRs, the relevant schema, and the
handover text. Nothing from your reasoning.

Its instruction is adversarial, not assistive:

> You own these contracts. Review this handover against them. Find what it gets wrong, what
> your ADRs forbid, and what is physically impossible in your schema. Do not implement
> anything. Report findings only.

Findings feed the **receiving** lane's Scope phase (§4.1). Context isolation is what makes the
pushback real — an agent that never saw your reasoning cannot rubber-stamp it.

Skip the audit only for a purely MECHANICAL handover — then ask why it is a crossing at all.

### 4.4 Feature-level e2e/UAT (the integrated close)

Runs **once, after every lane reads `Closed`** — never before: the integrated feature does not exist until then, and per-lane `accept` verified each lane only in isolation. This is the cross-lane gate the per-lane gates cannot be.

Drive it in main context where the environment provides the tooling (Playwright MCP where there is UI): exercise the feature end-to-end across all lanes and record **real** results — failures recorded as failures, never as "not run" — into the feature's UAT result artifact (the one Step 1 probes).

- **Pass** → the probe reads `passed`; the feature may close.
- **Fail** → record it; re-open the owning lane via `/said:add-task` + `/said:impl`, which drops that lane out of `Closed` — the loop reconverges.
- **No UI behavior** (scope declares a Developer-Story / no user-visible surface) → `n/a`.
- **Operator-confirmed skip** → allowed only on explicit operator word, written into the UAT artifact as `skipped(recorded)`, never silent. Under an autonomy macro this skip is a **hard blocker** — the one wait autonomy cannot self-approve.
- **Tooling unavailable** (environment-gated, like peer-session forking) → do not fabricate a pass; REPORT the owed UAT (`feature e2e/UAT: pending` → `feature closed: no`) and name the exact run to perform, as Rule 8 reports an external wait.

Never emit `feature closed: yes` while this reads `pending`.

## Step 5 — Gate before any fork, rotation, or end of turn

Both hard. Neither skippable under an autonomy macro — autonomy removes waits, not gates.

1. **Unfiled decisions.** Every decision made this turn is written to an artifact. The resume
   pointer's last line must read `decisions not yet in a file: none`. If it does not, file them
   before doing anything else.
2. **Resume pointer refreshed** at `<lane>/docs/working/<feature>/_resume.md` — **write-only output**: a human / outer-orchestrator pointer, re-derived from inspection every turn and **never read back as state** (Step 1: *"Never read a state file"*). It is not the parallel state file the Never-list forbids — that means a file the skill would *trust in place of re-deriving*:

```markdown
# <feature> — resume pointer
Reconstructed: <date>
Lanes:     FE <phase, n Todo> · BE <phase, n Todo>
Crossings: <name> — open|replied|consumed
Next:      <the exact command to run>
Blocked:   <task → crossing it waits on, or none>
decisions not yet in a file: none
```

## Step 6 — Progress check, then re-enter

Snapshot before and after every invocation: per-lane `Status` counts, artifact file list,
crossing states. If an invocation changes **none** of them → **HALT**, report what was
attempted and what the reconstruction says, do not re-enter. A loop that churns quietly is
worse than one that stops loudly.

Otherwise return to Step 1 and continue. Do not report a phase boundary as a stopping point —
boundaries are where work flows, not where it waits.

Stop only on: rule 8 (external crossing), a no-progress halt, a failing quality gate needing an
operator decision, or genuine completion (all lanes Closed).

**Then emit the Output contract block**, every time, before yielding. "Genuine completion" is
not a judgement you make in prose — it is `feature closed: yes`, and that is only true when
every lane's probe reads `Closed`. If you are being driven by an outer orchestrator that
invoked this skill once and moved on, the block is the only thing that will tell it the
feature is not finished; emit it whether or not it was asked for.

## Never

- Emulate a `said:` skill because invoking felt heavy.
- Fork an arm sharing an incomplete root with in-flight work.
- Classify a mechanical item as NEGOTIATION to defer a decision.
- Write into another lane's task log — that lane's Architect phase owns it.
- Claim in a handover that work "is authored into" a file that does not exist. Future tense,
  or name the gap.
- Carry a decision only in conversation across a compaction.
- Maintain a state file the skill **reads back** as truth parallel to the artifacts (`_resume.md` is write-only output, re-derived each turn — Step 5.2 — not this).
- Treat "context is getting long" as a stage boundary.

## Known limits

- **Peer-session forking is environment-gated.** Where unavailable the skill is correct but
  serial. Say which mode you are in.
- **The classification test is judgment** with no mechanical check. When unsure prefer
  MECHANICAL and let the audit catch it — an audit finding is cheap, a manufactured crossing
  is not.
- **Lane conventions are project-specific.** Handover filenames, task-ID shapes and directory
  layout come from the project's `CLAUDE.md` files. Read them at Step 1; do not assume the
  shapes in this document.
- **The glob is a fallback, not the primary path — do not "simplify" back to it.** It encodes
  one convention (`docs/features/*.tasks.md` + `docs/working/<id>/`) and returns *nothing*,
  silently, for a lane that keeps its logs elsewhere. Observed in the wild: a lane whose task
  logs live at `docs/wip/<feature>/*.tasks.md` stayed invisible to this skill for a whole
  feature, so its work was absorbed into a neighbouring lane's task by default rather than by
  decision. A declared `## Lane` block is what makes a differently-shaped lane visible.
