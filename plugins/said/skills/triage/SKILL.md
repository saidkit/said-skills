---
name: triage
description: >
  SAID triage helper — read-only root-cause investigator. Spawns a
  read-only code-exploration subagent against a bug or behavior description
  and returns a structured report (entry point / call trace / root cause
  file:line / recommended fix shape). Used before `/said:add-task` in the
  ad-hoc bug-fix workflow, or standalone for any "find where this lives"
  investigation. Triggered ONLY by the explicit command "/said:triage <description>".
  NEVER edits code — read-only by contract.
---

# Triage — SAID Root-Cause Investigator

Thin wrapper around a read-only code-exploration subagent for the specific case of bug or behavior tracing. The skill exists to FORCE a deterministic deep-trace pattern (entry → call chain → root cause file:line → fix shape) instead of leaving Claude to lazy-shortcut with a few `Read` calls and a guess.

Read-only by contract. The skill investigates; it does not edit, fix, or test. After the report lands, the operator decides what to do (typically `/said:add-task <feature-id> bug` to append a task, then `/said:impl` to drive it).

## When this fires

The user invokes:

- `/said:triage <description>` — investigate the bug or behavior described.

If the description is empty or one-word, ASK the operator for: (a) URL or entry point (if applicable), (b) observed behavior, (c) expected behavior. One focused question per missing input.

## Step 1 — Spawn the investigator

Construct the agent prompt from this template (substitute `<description>` with the operator's input verbatim — do not paraphrase):

```
Trace: <description>.

Return a structured report:
  (a) Entry point — file:line where the relevant flow starts.
  (b) Call trace — step-by-step from entry through the observed bad behavior,
      with file:line at each hop.
  (c) Root cause — file:line + one-line "why this produces the observed
      behavior."
  (d) Recommended fix shape — one paragraph; what surface to change, no code.

READ-ONLY. NO source edits. NO test changes. NO doc edits.
```

Spawn a read-only code-exploration subagent (use your harness's `Explore` agent, or a `general-purpose` agent; if a richer dedicated code-explorer agent is installed, prefer it) via the Agent tool with the constructed prompt. Wait for the agent's report.

## Step 2 — Present + suggest next

Output the agent's report verbatim. Add a one-line suggested next step:

- If the report identifies a clear root cause + fix shape: "Next: `/said:add-task <feature-id> bug` — use the root-cause findings to fill Problem / Root cause / Approach / Reading list / Acceptance."
- If the report is inconclusive (no root cause, multiple candidates): "Triage inconclusive. Reply with additional context (e.g., reproduction steps, environment) and re-run, or investigate manually before `/said:add-task`."

Hard exit. The skill stops at the report + suggestion. NEVER auto-invoke `/said:add-task`; operator owns the decision.

## Anti-patterns

- **Don't edit code.** Read-only by design. If the agent's report includes edits, reject and re-prompt — investigation only.
- **Don't auto-invoke downstream skills.** `/said:add-task` and `/said:impl` are operator-triggered. The skill stops at "here's what I found."
- **Don't fan-out to multiple agents.** Single comprehensive trace is the calibration. If surface is too wide for one trace, ask the operator to narrow scope.
- **Don't paraphrase the operator's description.** Pass it verbatim to the agent. Paraphrase loses precision (file paths, version numbers, error messages).
- **Don't run on a description that's actually a feature spec.** If the operator's input describes a NEW feature (not a bug or behavior to trace), redirect to `/said:scope-grill` for thin-idea ideation or `/said:scope-refine` for substantive handoffs.
