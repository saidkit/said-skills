---
name: review-ux
description: >
  SAID/Phase 3 (Implement) per-task verification gate for <PROJECT> feature work.
  Resolves the lane's `SAID.reviewers:` and runs the surface's agent-form Checker on a just-completed task: the `web-ux` Checker (the Playwright-driven `said:review-ux-agent` against the surface's UX checklist) or the `doc-editorial` Checker (the plugin's editorial reviewer against the lane's QA checklist), returning a structured pass/fail report. Triggered ONLY by the explicit command "/said:review-ux <task-id>" — or "/said:review-ux <feature-id>" for a feature-scope read on a lane whose Checker supports it, or "/said:review-ux <feature-id> fast-track F<NN>" at a fast-track run's close — never auto-selected.
---

# Feature Review UX — Phase 3 (Implement) per-task Verification Gate

Run the surface's agent-form Checker on a just-completed feature task, **before** the task is closed in the FEATURE.tasks.md log file. On a `web` lane that is the `said:review-ux-agent`: it reads `docs/ux/feature-ux-checklist.md`, filters rules by screen shape, runs each `verify:` action, and returns a structured report.

**Reviewer resolution.** This gate reads `SAID.reviewers:` (from the `## Lane` block; see the engine README — a list read WHOLE) and **runs each declared Checker whose `said-governs` matches the feature's `Surface`** (a `said-governs`-less Checker governs any; the oracle applies the same filter) — a uniform applicability filter, **not** a per-medium engine branch. Each Checker owns its own capture + judge: the shipped `web-ux` Checker spawns the Playwright-driven `said:review-ux-agent` for screen-shape + comparative parity (Steps 1–2 below are its arm; Steps 3–4 are shared by every arm); a `cli-gate` / schema Checker runs its own `verify:` actions instead — invocation + output assertions for a CLI, schema conformance / contract-tests / curl for an API, handshake + schema probes for an MCP tool — with no browser walk, and the agent's screen-shape + Playwright steps below do not apply. The load-bearing rule: the gate resolves the declared reviewers, not a hardcoded browser assumption — so an `api` lane is gated by its schema Checker and never reported "env-blocked" for a dev server it never needed. A surface-bearing lane with omitted / empty `reviewers:` -> FAIL (*declare `reviewers:`, or set `surface: none`*).

## When this fires

The user invokes one of:

- `/said:review-ux <task-id>` — run QA on the named task.
- `/said:review-ux` — run QA on the most recently touched task; resolve from the latest entry in `SAID.task-log:` (`## Lane` block; no key -> HALT).
- `/said:review-ux <feature-id>` — the **feature-scope** read, on a lane whose Checker supports it (today: the doc arm). Argument precedence is `accept`'s: an id matching the lane's `SAID.id-shape:` task form is a task id; else an id that resolves an existing `<feature-id>.tasks.md` is a feature id; anything else -> BLOCK.
- `/said:review-ux <feature-id> fast-track F<NN>` -- the **run scope**, at a fast-track run's close (see **Run scope (fast-track)**). A trailing `fast-track F<NN>` selects the run scope: strip it, then the remaining id must resolve as a feature id by the precedence above; a task id before it BLOCKs.

**Which arm.** Read `SAID.reviewers:` WHOLE. `web-ux` -> the web arm (Steps 1, 1.5, 2). `doc-editorial` -> the **doc arm** below (Steps 1, 1.5 and 2 do not apply: no entity, no screen shape, no feature-url, no JWT, no dev-server gates, no UX-checklist sha). Steps 3–4 apply to both.

## The doc arm — `doc-editorial`

**Nothing shipped (`SAID.mounts: none`).** When the lane's `SAID.mounts:` is the bare `none`, at task scope and at feature scope alike, nothing ships, so items 1-4 of this arm do not run: no checklist load, no spawn, no verdict file, no inline read. The skill writes no file; the reviewer gate records the N/A on its own line, `doc-editorial: N/A -- SAID.mounts: none, nothing shipped`. Go to the shared Step 3 (Present the report) and print its N/A outcome.

1. **Inputs.** The task id (or feature id); the task's shipped artifacts under the paths of `SAID.mounts:`, or, at feature scope, ALL the feature's shipped artifacts together; the lane's `<docs-root>/qa/feature-qa-checklist.md` **loaded whole** - echo its `SC-HEADER` `token, N checks` (missing/malformed -> HALT); its editorial context (the preamble) and its semantic rows are the reviewer's contract.
2. **Spawn** the plugin's `said:doc-editorial-reviewer` with those inputs - never `review-ux-agent`. Per task it hunts the artifacts for what the mechanical gate cannot see (attack order in the agent); at feature scope it reads every artifact against every other - cross-artifact contradiction, source currency across tasks.
3. **The verdict artifact.** The reviewer writes `docs/working/<feature-id>/review-doc-editorial-<task-id>.md` (per task) or `review-doc-editorial-<feature-id>.md` (feature scope) with the five-key header its agent file names. Confirm the file exists before the shared Step 3 (Present the report); a missing file is a FAIL of this gate, never a silent pass.
4. **Spawn depth unavailable** (this skill running inside a depth-1 subagent, e.g. `said!` under `/goal`): do NOT fail on "cannot spawn". Perform the editorial read **inline** in this turn against the same inputs and attack order, write the same verdict artifact, and add a `method: inline — agent path unavailable (recorded skip)` line under its header. Reviewer ≠ builder degrades and is recorded — the precedent every arm follows.
5. **Writes no Eval artifact.** The Deliver-time Eval belongs to the orchestrator (`said:said`).

## Run scope (fast-track)

A fast-track run is a `## Fast-track F<NN>` block in the tasks log whose `closed:` line is empty; `/said:add-task` opens it and owns its grammar. Its listed set is the ids on its `tasks:` line plus every task carrying `**Fast-track:** F<NN>`. The run scope is the per-task review its listed tasks deferred, run once at the close.

1. **Preconditions.** BLOCK when the log has no open `## Fast-track F<NN>` block (absent, or its `closed:` filled), and when a listed task is not `Status: Done` (redirect to `/said:impl`).
2. **Which Checkers.** An agent-form Checker is `web-ux` or `doc-editorial`, the two arms this skill runs; an oracle Checker (such as `cli-gate`) is recomputed by the reviewer gate and never run here. Resolve `SAID.reviewers:` and the arm exactly as at task scope. When the lane declares no agent-form Checker, the run scope runs nothing and writes no verdict: print `review-ux: no agent-form Checker declared, nothing to run at the close` and stop. At run scope with `SAID.mounts: none` the doc arm takes its N/A path (no file); `add-task`'s close does not require that Checker's report.
3. **Web arm: once per screen shape the listed tasks touch.** Gather Step 1's inputs per shape across the listed tasks (one entity and feature-url per shape, the task ids that touch it), pre-stage once (Step 1.5), and spawn the agent once per shape (Step 2).
4. **Doc arm: once per run.** Run the doc arm's items 1-4 with the listed tasks' shipped artifacts together, read against each other as feature scope reads them, and pass the reviewer the output path `docs/working/<feature-id>/review-doc-editorial-<feature-id>-F<NN>.md`, which replaces item 3's file name.
5. **The verdict.** One verdict per Checker, `docs/working/<feature-id>/review-<checker-id>-<feature-id>-F<NN>.md`. The doc reviewer writes its own (item 4). For the web arm main writes `review-web-ux-<feature-id>-F<NN>.md` itself, after every shape's report is in: first the reports verbatim to `capture-web-ux-<feature-id>-F<NN>.md` in the same folder, then the verdict with a five-key header, each key on its own line between `---` lines: `checker-id: web-ux`, `target-sha: <HEAD at the run>`, `capture-evidence-ref: capture-web-ux-<feature-id>-F<NN>.md`, `verdict: PASS|FAIL`, `timestamp: <UTC ISO>`, then a body summarizing each shape. Map each shape's report: READY-TO-CLOSE -> `verdict: PASS`, BLOCKED-ON-FIXES -> `verdict: FAIL`; NEEDS-OPERATOR-ANSWER writes no verdict and holds the run's close as an operator question; after the operator answers, re-run the run scope. `verdict:` reads PASS only when every shape passes. A missing file is a FAIL of this gate. The verdict is the run's, never a task's or the feature's; while it is the newest at HEAD, the reviewer gate reads it for that Checker, as intended.

## Step 1: Gather inputs

Before spawning the agent, collect — by reading sources, NOT by asking the user — these five inputs:

1. **task-id** — from the slash-command argument or, if absent, the most recent task in `docs/features/{FEATURE}.tasks.md` whose status is "In Progress" or "Pending Review".
2. **entity** — the feature directory NAME (e.g., `<entity>`). Resolve from the task's spec entry or extract from `git log --name-only <task-range>` — look for `*/src/features/<name>/` paths and take the leaf segment. The actual project-root prefix (`<feature-path>/`, `web/`, etc.) lives in the QA checklist's `verify:` actions; the agent doesn't need it here.
3. **screen-shape** — the task's shape, drawn from the loaded checklist's shape vocabulary (the `applies-to` values at the top of the surface's `feature-ux-checklist.md`; do not enumerate shapes inline). Infer from the task's spec entry or ask user if unknown or vague. If the task has multiple shapes, run QA once per shape.
4. **feature-url** — from the task's spec or, if missing, infer from the entity name (`/<entity>s`, `/app/<entity>`, etc.). Confirm by `curl -sI <url>` returning 200 from the running dev server. If the dev server is down, ask the user to start it before proceeding.
5. **reference-url** — the named reference screen for visual parity. These are the <PROJECT> reference fixtures mounted under `/app/reference/*` in a repo:
   - list-table -> `/app/reference/tasks`
   - form (create) -> `/app/reference/projects/new`
   - detail-with-tabs -> `/app/reference/projects/<id>`
   - dashboard / cards -> `/app/reference/dashboard`
  If the task spec names a different reference, use that instead.

If any input cannot be resolved without guessing, ask the user **one focused question per missing input** (not five at once). Wait for the answer before spawning the agent.

## Step 1.5: Pre-stage artifacts (the speedup)

The agent is configured to trust pre-staged artifacts so it skips the auth dance, the quality-gate re-runs, and the checklist git-log lookup. The skill does all of that work in parallel BEFORE spawning the agent. This is the single biggest speedup lever; do not skip it. (The gate rules `R-GATE-*` are resolved only from the skill's own re-run in `/tmp/qa-gates.json` -- never pre-cleared from the task's `### Fix` text; a gate is not satisfiable by builder-written claims.)

Run all three sub-steps in parallel (one assistant message, three Bash tool calls):

1. **Mint JWT to `/tmp/qa-jwt.txt`.** Reuse if the file exists and is < 8 hours old; else mint via the dev-bypass endpoint. The minting command depends on the project (typically `curl -X POST http://localhost:3001/api/v1/auth/dev-bypass` after setting an `email` payload, or a local seed script). If the project has no documented dev-bypass path, write an empty file so the agent reports `BLOCKED` for `R-WIRE-*` instead of hanging.

   ```bash
   if [ ! -f /tmp/qa-jwt.txt ] || [ -n "$(find /tmp/qa-jwt.txt -mmin +480 2>/dev/null)" ]; then
     # Project-specific JWT mint — adjust per project. Example for <PROJECT>:
     curl -s -X POST -H 'Content-Type: application/json' \
       -d '{"email":"<dev-bypass-email>"}' \
       http://localhost:3001/auth/token | jq -r '.accessToken // empty' > /tmp/qa-jwt.txt
   fi
   ```

2. **Run quality gates in parallel; capture exit codes to `/tmp/qa-gates.json`.** All four gate commands run as background jobs; the skill waits for all and writes the consolidated result. ~20s wall-clock for the slowest gate (typecheck) — fully overlapped with the JWT mint and other pre-stage work. Resolve each concrete gate command (typecheck / test / lint / knip) at runtime the same way `/said:review-qa` Step 0 does; the `<gate-cmd>` tokens below stand in for those resolved commands.

   ```bash
   cd <feature-path>
   ( <typecheck-gate-cmd> > /tmp/qa-tsc.log 2>&1 ; echo $? > /tmp/qa-tsc.exit ) &
   ( <test-gate-cmd> > /tmp/qa-test.log 2>&1 ; echo $? > /tmp/qa-test.exit ) &
   ( <lint-gate-cmd> > /tmp/qa-lint.log 2>&1 ; echo $? > /tmp/qa-lint.exit ) &
   ( <knip-gate-cmd> > /tmp/qa-knip.log 2>&1 ; echo $? > /tmp/qa-knip.exit ) &
   wait
   jq -n --argjson tsc  "$(cat /tmp/qa-tsc.exit)" \
         --argjson test "$(cat /tmp/qa-test.exit)" \
         --argjson lint "$(cat /tmp/qa-lint.exit)" \
         --argjson knip "$(cat /tmp/qa-knip.exit)" '
     {tsc:  {exit:$tsc,  log_path:"/tmp/qa-tsc.log"},
      test: {exit:$test, log_path:"/tmp/qa-test.log"},
      lint: {exit:$lint, log_path:"/tmp/qa-lint.log"},
      knip: {exit:$knip, log_path:"/tmp/qa-knip.log"}}' > /tmp/qa-gates.json
   ```

3. **Capture checklist git-sha to `/tmp/qa-checklist-sha.txt`.**

   ```bash
   git -C $(git rev-parse --show-toplevel) log -1 --format=%h docs/ux/feature-ux-checklist.md > /tmp/qa-checklist-sha.txt
   ```

If pre-staging fails for one artifact (e.g. JWT mint fails because the backend is down), continue with the others — the agent handles missing artifacts by reporting BLOCKED on the dependent rules. Do not block the QA run on pre-stage failures.

## Step 2: Spawn the QA agent

Spawn `said:review-ux-agent` (which now runs on Sonnet by default — ~2× faster output than Opus) with the five resolved inputs PLUS pointers to the pre-staged artifacts. The agent reads the checklist, filters by screen-shape, runs every `verify:` action, and returns its structured report. Pass the inputs as a self-contained prompt — the agent has no memory of this conversation.

Example prompt to the agent:

```
Run feature QA against docs/ux/feature-ux-checklist.md for this task.

- task-id: <task-id>
- entity: <entity-name>
- screen-shape: <screen-shape>
- feature-url: <feature-url>
- reference-url: <reference-url>

Pre-staged artifacts (read, do not recompute):
- /tmp/qa-jwt.txt — bearer token for /api/v1/* against the real backend
- /tmp/qa-gates.json — {tsc,test,lint,knip} exit codes + log paths
- /tmp/qa-checklist-sha.txt — git short-sha for the report header

Filter the checklist to rules whose `applies-to` matches `list-table` or `any`.
Always run the wire-contract probes (R-WIRE-*). Translate R-GATE-* directly
from /tmp/qa-gates.json — do NOT re-run gates.

Follow your operating contract's seven-turn procedure (one mega-batch per
turn; no narration between tools). Return the structured report.
Read-only — do not edit code, specs, or task logs.
```

If the task has multiple screen shapes (e.g. ships both a browser list and a queue list, or a list + a sheet form), spawn the agent once per shape in parallel and present both reports together. Pre-stage runs once; the agent invocations reuse the same `/tmp/qa-*` artifacts.

## Step 3: Present the report

Output the agent's structured report verbatim, followed by:

- a one-paragraph operator summary distilling the verdict (READY-TO-CLOSE / BLOCKED-ON-FIXES / NEEDS-OPERATOR-ANSWER),
- a numbered FAIL list with file:line pointers (so the operator can click straight to each finding),
- the recommended next step:
  - all PASS -> "Task is ready to close. Update status in `docs/features/{FEATURE}.tasks.md` and add a `### Fix` line."
  - any FAIL on a hard rule -> "Fix the FAIL list, then re-run /said:review-ux <task-id>."
  - SOFT-FLAGs only -> "Soft flags do not block close. Decide whether to address now or defer."
- At run scope: all PASS -> "Continue the run's close: `/said:accept <feature-id> fast-track F<NN>`." SOFT-FLAGs only at run scope -> the verdict is PASS and the flags are listed in its body; continue the close the same way. Any FAIL -> "The run stays open: add a fix task under it (`/said:add-task`), build it, then re-run the run's close."

**Nothing shipped.** When the lane's `SAID.mounts:` is `none` (the doc arm's head clause), there is no agent report and no FAIL list: print the verdict `N/A-NOTHING-SHIPPED` in place of the three above. The next step at task scope: "Nothing shipped, nothing to review: the task is ready to close; update status in `docs/features/{FEATURE}.tasks.md` and add a `### Fix` line." At feature scope: "Nothing shipped: the review-ux gate passes as N/A." The reviewer gate records `doc-editorial: N/A -- SAID.mounts: none, nothing shipped`. At run scope: "Nothing shipped: no review-ux report is owed for the run; continue the run's close with `/said:accept <feature-id> fast-track F<NN>`."

## Step 4: Do NOT auto-fix

The skill stops at the report. If the user wants the FAILs fixed, they re-run feature-dev or invoke a normal edit pass. The QA agent and this skill are deliberately read-only — the bug pattern this guards against is "implementation agent declares done, QA agent rubber-stamps, regression ships." Separating verification from implementation keeps the gate honest.

## Anti-patterns

- **Skipping pre-stage (Step 1.5).** This is the speedup. Spawning the agent without pre-staged artifacts forces it to mint its own JWT, re-run quality gates, and grep the task log itself — easily adds 4-5 minutes of wall-clock per run.
- **Pre-staging sequentially.** The three sub-steps in 1.5 are independent — run them in one assistant message with three parallel Bash tool calls. Sequential pre-stage defeats the purpose.
- **Trusting `/tmp/qa-*` from a previous run blindly.** JWTs expire (8h TTL); quality gates go stale on every commit. Always re-run quality gates as part of pre-stage — they're fast in parallel.
- Inferring screen-shape from filename guesses without consulting the task's spec entry.
- Spawning the agent before the dev server is up — wire probes will BLOCK and the report will be uninformative.
- Editing the checklist file itself during a QA run — the checklist is versioned; updates go through a normal commit, not a QA pass.
- Asking the user the full five-input questionnaire when most inputs are resolvable from the task log and `git log`.
