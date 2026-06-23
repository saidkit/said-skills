---
name: review-ux
description: >
  SAID/Phase 3 (Implement) per-task UX verification gate for <PROJECT> feature work.
  Spawns the `said:review-ux-agent` agent against `docs/qa/feature-ux-checklist.md` with the task's screen-shape and changed-file context, returning a structured pass/fail report. Triggered ONLY by the explicit command "/said:review-ux". Do NOT trigger on general review / verify / check requests — only the exact command "/said:review-ux" activates this skill.
---

# Feature Review UX — Phase 3 (Implement) per-task Verification Gate

Run the `said:review-ux-agent` agent on a just-completed feature task, **before** the task is closed in the FEATURE.tasks.md log file. The QA agent reads `docs/qa/feature-ux-checklist.md`, filters rules by screen shape, runs each `verify:` action, and returns a structured report.

**Project-type note.** Web-app only. This skill gates UX verification for <PROJECT> (React + Vite) feature work; server-app SAID features will have a sibling review tool (TBD).

## When this fires

The user invokes one of:

- `/said:review-ux <task-id>` — run QA on the named task.
- `/said:review-ux` — run QA on the most recently touched task; resolve from the latest entry in `docs/features/{FEATURE}.tasks.md` (or whichever task log is current).

## Step 1: Gather inputs

Before spawning the agent, collect — by reading sources, NOT by asking the user — these five inputs:

1. **task-id** — from the slash-command argument or, if absent, the most recent task in `docs/features/{FEATURE}.tasks.md` whose status is "In Progress" or "Pending Review".
2. **entity** — the feature directory NAME (e.g., `<entity>`). Resolve from the task's spec entry or extract from `git log --name-only <task-range>` — look for `*/src/features/<name>/` paths and take the leaf segment. The actual project-root prefix (`<feature-path>/`, `web/`, etc.) lives in the QA checklist's `verify:` actions; the agent doesn't need it here.
3. **screen-shape** — pick from `list-table`, `form`, `detail-with-tabs`, `embedded-list-in-tab`, `data-layer-only`. Infer from the task's spec entry or ask user if unknown or vague. If the task has multiple shapes, run QA once per shape.
4. **feature-url** — from the task's spec or, if missing, infer from the entity name (`/<entity>s`, `/app/<entity>`, etc.). Confirm by `curl -sI <url>` returning 200 from the running dev server. If the dev server is down, ask the user to start it before proceeding.
5. **reference-url** — the named reference screen for visual parity. These are the <PROJECT> reference fixtures mounted under `/app/reference/*` in a repo:
   - list-table → `/app/reference/tasks`
   - form (create) → `/app/reference/projects/new`
   - detail-with-tabs → `/app/reference/projects/<id>`
   - dashboard / cards → `/app/reference/dashboard`
  If the task spec names a different reference, use that instead.

If any input cannot be resolved without guessing, ask the user **one focused question per missing input** (not five at once). Wait for the answer before spawning the agent.

## Step 1.5: Pre-stage artifacts (the speedup)

The agent is configured to trust pre-staged artifacts so it skips the auth dance, the quality-gate re-runs, the checklist git-log lookup, and the rules already covered by the task's `### Fix` evidence. The skill does all of that work in parallel BEFORE spawning the agent. This is the single biggest speedup lever; do not skip it.

Run all four sub-steps in parallel (one assistant message, four Bash tool calls):

1. **Mint JWT to `/tmp/qa-jwt.txt`.** Reuse if the file exists and is < 8 hours old; else mint via the dev-bypass endpoint. The minting command depends on the project (typically `curl -X POST http://localhost:3001/api/v1/auth/dev-bypass` after setting an `email` payload, or a local seed script). If the project has no documented dev-bypass path, write an empty file so the agent reports `BLOCKED` for `R-WIRE-*` instead of hanging.

   ```bash
   if [ ! -f /tmp/qa-jwt.txt ] || [ -n "$(find /tmp/qa-jwt.txt -mmin +480 2>/dev/null)" ]; then
     # Project-specific JWT mint — adjust per project. Example for <PROJECT>:
     curl -s -X POST -H 'Content-Type: application/json' \
       -d '{"email":"<dev-bypass-email>"}' \
       http://localhost:3001/auth/token | jq -r '.accessToken // empty' > /tmp/qa-jwt.txt
   fi
   ```

2. **Run quality gates in parallel; capture exit codes to `/tmp/qa-gates.json`.** All four gate commands run as background jobs; the skill waits for all and writes the consolidated result. ~20s wall-clock for the slowest gate (typecheck) — fully overlapped with the JWT mint and other pre-stage work. Resolve each concrete gate command (typecheck / test / lint / knip) at runtime via the same chain as `/said:review-qa` Step 0 (`CLAUDE.md` Development-Commands → `Makefile` → `package.json` scripts, per lockfile → ask operator); the `<gate-cmd>` tokens below stand in for those resolved commands.

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
   git -C $(git rev-parse --show-toplevel) log -1 --format=%h docs/qa/feature-ux-checklist.md > /tmp/qa-checklist-sha.txt
   ```

4. **Build skip list from task evidence to `/tmp/qa-skip.txt`.** Read the task's entry in `docs/features/{FEATURE}.tasks.md` for the `### Fix` block. If the entry explicitly cites quality-gate exit codes ("tests N → M pass", "typecheck clean", "knip no new regressions"), append `R-GATE-TYPECHECK` / `R-GATE-TESTS` / `R-GATE-LINT` / `R-GATE-KNIP` to the skip list as appropriate. The agent will record these as PASS with evidence "pre-cleared by skill from task entry" without re-checking. This list is conservative — only skip rules whose evidence is unambiguous in the task entry.

   ```bash
   FIX_BLOCK=$(awk "/^## ${TASK_ID}:/,/^## /" docs/features/{FEATURE}.tasks.md | awk "/^### Fix/,/^### /")
   {
     echo "$FIX_BLOCK" | grep -qiE "typecheck.*(clean|green|pass)|tsc.*clean" && echo R-GATE-TYPECHECK
     echo "$FIX_BLOCK" | grep -qiE "tests? [0-9]+ ?(→|->) [0-9]+|test:src.*pass" && echo R-GATE-TESTS
     echo "$FIX_BLOCK" | grep -qiE "lint.*(clean|green|pass)|biome.*clean" && echo R-GATE-LINT
     echo "$FIX_BLOCK" | grep -qiE "knip.*(no new|green|pass|clean)" && echo R-GATE-KNIP
   } > /tmp/qa-skip.txt
   ```

If pre-staging fails for one artifact (e.g. JWT mint fails because the backend is down), continue with the others — the agent handles missing artifacts by reporting BLOCKED on the dependent rules. Do not block the QA run on pre-stage failures.

## Step 2: Spawn the QA agent

Spawn `said:review-ux-agent` (which now runs on Sonnet by default — ~2× faster output than Opus) with the five resolved inputs PLUS pointers to the pre-staged artifacts. The agent reads the checklist, filters by screen-shape, runs every `verify:` action that isn't pre-cleared, and returns its structured report. Pass the inputs as a self-contained prompt — the agent has no memory of this conversation.

Example prompt to the agent:

```
Run feature QA against docs/qa/feature-ux-checklist.md for this task.

- task-id: <task-id>
- entity: <entity-name>
- screen-shape: <screen-shape>
- feature-url: <feature-url>
- reference-url: <reference-url>

Pre-staged artifacts (read, do not recompute):
- /tmp/qa-jwt.txt — bearer token for /api/v1/* against the real backend
- /tmp/qa-gates.json — {tsc,test,lint,knip} exit codes + log paths
- /tmp/qa-checklist-sha.txt — git short-sha for the report header
- /tmp/qa-skip.txt — rule IDs pre-cleared by the skill (record as PASS)

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

- a one-paragraph operator summary distilling the verdict (READY-TO-CLOSE / BLOCKED-ON-FIXES / NEEDS-OPERATOR-DECISION),
- a numbered FAIL list with file:line pointers (so the operator can click straight to each finding),
- the recommended next step:
  - all PASS → "Task is ready to close. Update status in `docs/features/{FEATURE}.tasks.md` and add a `### Fix` line."
  - any FAIL on a hard rule → "Fix the FAIL list, then re-run /said:review-ux <task-id>."
  - SOFT-FLAGs only → "Soft flags do not block close. Decide whether to address now or defer."

## Step 4: Do NOT auto-fix

The skill stops at the report. If the user wants the FAILs fixed, they re-run feature-dev or invoke a normal edit pass. The QA agent and this skill are deliberately read-only — the bug pattern this guards against is "implementation agent declares done, QA agent rubber-stamps, regression ships." Separating verification from implementation keeps the gate honest.

## Anti-patterns

- **Skipping pre-stage (Step 1.5).** This is the speedup. Spawning the agent without pre-staged artifacts forces it to mint its own JWT, re-run quality gates, and grep the task log itself — easily adds 4-5 minutes of wall-clock per run.
- **Pre-staging sequentially.** The four sub-steps in 1.5 are independent — run them in one assistant message with four parallel Bash tool calls. Sequential pre-stage defeats the purpose.
- **Trusting `/tmp/qa-*` from a previous run blindly.** JWTs expire (8h TTL); quality gates go stale on every commit. Always re-run quality gates as part of pre-stage — they're fast in parallel.
- Inferring screen-shape from filename guesses without consulting the task's spec entry.
- Spawning the agent before the dev server is up — wire probes will BLOCK and the report will be uninformative.
- Editing the checklist file itself during a QA run — the checklist is versioned; updates go through a normal commit, not a QA pass.
- Asking the user the full five-input questionnaire when most inputs are resolvable from the task log and `git log`.
