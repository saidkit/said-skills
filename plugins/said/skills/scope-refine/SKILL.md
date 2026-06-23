---
name: scope-refine
description: >
  SAID/Phase 1 (Scope) Case 1 — refines a substantive technical handoff
  (handoff doc OR current branch state) into a `scope.md` for Phase 2
  (Architect). Resolves input from operator argument, spawns the
  `said:scope-refine-agent` agent (parallel codebase audit + curl-first
  wire/visual probes), relays §A/§B/§C/§D draft + §D conflicts to operator.
  Triggered ONLY by the explicit command "/said:scope-refine
  [<handoff-path>] [probe-mode=skip|curl|full]". Default probe-mode is
  curl. NOT for thin-input ideation — that's `/said:scope-grill` Case 2.
---

# Feature Scope Refine — Phase 1 (Scope) Case 1: Handoff or Branch-State Refinement

This skill drives the Phase 1 Case 1 path — turning a substantive handoff into a refined `scope.md`. Case 2 (thin idea, no handoff) uses `/said:scope-grill` instead; THIS skill is for branch continuation, refactoring, or any work where a real handoff doc OR current git state already carries the substance.

The skill itself is a thin wrapper. The `said:scope-refine-agent` agent does the substantive work — Stage 0 contract reads, Stage 1 handoff index, Stage 2 parallel codebase audit (via `said:scope-audit` subagents, one per in-scope dir, all batched), Stage 3 mode-gated wire/visual probes (curl-first by default), Stage 4 contract classification, Stage 5 scope.md write, Stage 6 self-check. Your job here is to resolve inputs, spawn the agent, and carry §D items visibly back to the operator.

**Project-type note.** Works for both web-app and server-app SAID features. The agent handles the variation internally — Stage 0 reads whichever contract docs the project's `CLAUDE.md` names; Stage 3a (wire probes) applies to both (HTTP is HTTP); Stage 3b (visual walk) auto-skips for server-app refines and pure data-layer migrations because there's no UI surface. §B in the output `scope.md` is empty / omitted for server-app refines accordingly. The skill itself is project-type-agnostic — it just resolves inputs and spawns.

## When this fires

The user invokes one of:

- `/said:scope-refine <handoff-path>` — refine the named handoff doc.
- `/said:scope-refine` — no path given; skill synthesizes a minimal handoff from current branch state.
- `/said:scope-refine <handoff-path> probe-mode=full` — explicit probe-mode override.
- `/said:scope-refine probe-mode=skip` — branch-state synth, no live probes.

Args parse as: any token containing `=` is a flag (`probe-mode=...`); the remaining token (at most one) is the handoff path.

If the operator's input is a thin idea ("Let's ideate a notification preferences UI") rather than a handoff path or a real branch state, this is the WRONG skill. Redirect: "That's Case 2 — use `/said:scope-grill` for interactive ideation. This skill (`/said:scope-refine`) is Case 1, requires either a handoff doc path or substantive current-branch state."

## Step 1: Resolve inputs

Resolve five inputs — by reading sources, not by asking — except where explicitly noted:

1. **handoff-path** — depends on the operator's argument:
   - **Path given** — verify it exists via `ls <path>`. If missing, BLOCK with `handoff path not found: <path>` and ask the operator for the correct path.
   - **No path given (branch-state synth)** — synthesize a minimal handoff from git state:
     - Branch name: `git branch --show-current`.
     - Recent commits: `git log -10 --oneline`.
     - Uncommitted changes: `git status --short`.
     - Any `docs/working/**/wip*.md` files (via Glob).
     - Concatenate into a markdown handoff doc with sections `## Branch state`, `## Recent commits`, `## Uncommitted changes`, `## Wip notes`.
     - Write to `docs/working/<feature>/_branch-state.md` (you'll need feature name first — see input 4). This file lives alongside `scope.md` as audit-trail; the agent's boundary rule treats only the named handoff path as authoritative, so co-located peer files don't pollute the audit.

2. **output-path** — `docs/working/<feature>/scope.md`. The agent writes here. If `scope.md` already exists at that path, append `-N` (`scope-1.md`, `scope-2.md`, …) so prior versions stay as history.

3. **probe-mode** — explicit flag value, or default `curl`. Validate: must be `skip | curl | full`. The default is curl-first because typical case shrinks 2–3 min playwright to <10s curl. Reach for `full` only when the dev backend is known auth-gated end-to-end (curl can't reach the endpoints) or — for web-app refines — when the visual walk is mandatory. **For server-app refines, `full` forces playwright on wire probes ONLY**; Stage 3b (visual walk) auto-skips regardless of mode because there's no UI surface. Reach for `skip` only when the handoff already cites every needed wire capture and (web-app) screenshot.

4. **feature name** — needed to construct paths in inputs 1 and 2. Derive from:
   - The operator's path argument: if it's under `docs/working/<feature>/...`, take the leaf segment.
   - The current branch name: convention varies (`feature/foo` → `foo`; canonical task IDs matching `^([A-Z]+)(\d+)-.+$` derive to feature `${1}-${2}`; bare slugs like `said-01` pass through).
   - If still ambiguous (e.g., on `main`), ASK the operator: "What feature name should I use for the scope.md output? Suggest: `<best-guess>`."

5. **scope-hint** (optional) — comma-separated list of feature dirs to audit, overriding the dir list extracted from the handoff. Pass through if the operator gave it; otherwise omit and let the agent derive from Stage 1.

If any required resolution would force a guess, ASK the operator one focused question per gap — never the full questionnaire at once.

## Step 2: Spawn the agent

Spawn `said:scope-refine-agent` via the Agent tool with the resolved inputs. The agent is generic — pass everything in the prompt; it has no memory of this conversation.

Example spawn prompt:

```
Run Phase 1 (Scope) refinement.

- handoff-path: docs/working/<wip-path>.md
- output-path: docs/working/scope-refine/scope.md
- probe-mode: curl
- scope-hint: (none)

Read the handoff in full. Run Stage 0 (project-contract reads), Stage 1 (handoff decision index), Stage 2 (parallel audit via said:scope-audit subagents — one per in-scope dir, all batched in one assistant message), Stage 3 (mode-gated wire/visual probes — curl-first by default; per-endpoint playwright fallback on auth/UI-only triggering; visual walk conditional on UI-shape change), Stage 4 (classify decisions vs contract: CONFIRMED / CONFLICT / EXTENDS / SILENT), Stage 5 (write scope.md to output-path), Stage 6 (self-check).

Output: write scope.md to output-path. Reply with the §D — Conflicts and open questions section verbatim so the operator can resolve.
```

The agent batches Stage 2 subagents (parallel) and runs Stage 3 sequentially when probes escalate to playwright. You don't manage that — the agent does.

## Step 3: Present the output

After the agent returns:

- **scope.md path** — confirm where the file landed.
- **§D — Conflicts and open questions** — print the section verbatim. Each entry names a conflict (handoff vs contract divergence) or an open question (handoff residual or checklist gap).
- **Recommended next step** — depends on §D state:
  - **§D empty** → "Phase 1 (Scope) is done. Phase 2 (Architect) starts. Run `/said:architect` when ready, or build the spec interactively per `docs/features/template.md`."
  - **§D non-empty** → "Phase 1 (Scope) is BLOCKED on §D. Resolve each item, then either re-run `/said:scope-refine` to regenerate, or hand-edit `scope.md` so §D is empty before proceeding to `/said:architect`."

DO NOT silently resolve §D items. The agent surfaces conflicts in §D deliberately; this skill carries them through to the operator unchanged.

## Step 4: Do NOT auto-fix or auto-architect

The skill stops after presenting §D. If the operator wants conflicts resolved or wants Phase 2 to start, that's a separate explicit invocation. Phase 1 only writes `scope.md`; it does NOT write `spec.md`, task lists, or code.

## Anti-patterns

- **Don't bypass the agent and run probes inline.** The agent owns Stages 0–6 and enforces parallel-audit + sequential-probe sequencing. Reaching for curl / playwright in the skill body breaks that.
- **Don't merge with `/said:scope-grill`.** Different cases (Case 1 = handoff exists, Case 2 = thin idea), different drivers (this spawns the agent; grill is interactive and agent-less), different content shapes inside §A/§B/§C/§D. Conflating them produces shape-incoherent `scope.md`.
- **Don't auto-resolve §D.** Conflicts and open questions are operator-decision items by design. Carry them visibly to the operator; never pick the side yourself.
- **Don't write `spec.md`.** This is Phase 1. `spec.md` is Phase 2 (Architect). The earned-design-decision splits them deliberately.
- **Don't ask the operator the full input questionnaire** when most inputs resolve from path / branch / git state. Reach for an `ASK` only on the gap that genuinely can't be derived.
- **Don't auto-pick `probe-mode=full`** to "be safe". Default is `curl` for a reason — typical case shrinks 2–3 min playwright to <10s curl. `full` is operator-forced for known auth-gated dev backends or mandatory visual walks.
- **Don't skip the existence check** on operator-given handoff paths. Spawning the agent with a non-existent path wastes a parallel-audit run and confuses Stage 1.
- **Don't reuse a prior `_branch-state.md`** across runs. Branch state evolves; each branch-synth invocation overwrites the file with fresh git output.
