# Upgrade playbook v.0.4 -- the keyed lane block, the surface contract and earned rules

- rollout: v.0.4
- plugin: said >=0.8.0
- from: unversioned
- to: said@0.8.0
- after: none

One ordered pass that brings a lane written before the keyed lane block (a `## Lane` section in prose, or none at
all) up to the shape the `said` plugin reads: the keyed lane block, the surface-contract registry, the surface and
its reviewers, the per-feature `Surface:` field, and the `## Earned rules` section with the lane's profile.
**Config and docs only: no engine edit, no new skill, no commit unless the lane's owner asks.**

## Preconditions

- **Engine floor:** the installed `said` plugin is 0.8.0 or later. At or above it `/said:impl` halts on a lane that
  has no `## Earned rules` heading or no `SAID.profile:` key, so a lane left un-rolled is stopped, not degraded.
  Check the version, not presence (block V1).
- **The lane has a `CLAUDE.md`.** A lane with no lane block at all starts at Step 1, which writes one from scratch.
- **Resolve companion symlinks before editing.** A plugin lane's `docs/`, and sometimes its `CLAUDE.md`, may be a
  symlink into a private companion repository. Edit the target file, never the link.

## Order (each step presupposes the prior)

**Lane block -> registry -> surface and reviewers -> per-feature surface -> earned rules -> verify.** The registry
is resolved from the lane block's `SAID.docs-root:`; the reviewers gate the registry; the per-feature surface field
presupposes the lane surface. Step 5 depends on Step 1 alone, so a lane already rolled through Step 4 can take it on
its own. Never skip a step to reach a later one.

## Step 1 -- The lane block: prose form to `SAID.<key>:` lines

First settle what the lane is: an **instance** (built on a starter), a **starter** (a kit others clone) or a
**standalone** lane (built on no starter). The answer decides the version stamp and how Step 5 treats rules.

Write the `## Lane` block with every key, or convert the prose form to it:

```markdown
## Lane
- SAID.lane:         <name>
- SAID.version:      said@<semver>
- SAID.docs-root:    docs/
- SAID.mounts:       [<src/>]
- SAID.feature-spec: docs/features/<id>.md
- SAID.task-log:     docs/features/<id>.tasks.md
- SAID.working:      docs/working/<id>/
- SAID.id-shape:     PROJ-<NN>
- SAID.adr-prefix:   ADR-<PREFIX>-*
- SAID.surface:      <medium | none>
- SAID.reviewers:    [<checker>]
- SAID.commands:     <the lane's gate command>
```

- **The key list carries key lines and nothing else.** Between the first key and the last there is no sub-bullet,
  no note and nothing after a value; a scalar key is named once, on its own line. Prose about the lane goes above
  the keys or in the lane's own docs.
- **`SAID.surface:` has no default** and halts if omitted. Every other key falls back to its documented default;
  declare them all.
- **Record the lane's own id shape verbatim.** A project keeps its own task-id convention; `PROJ-<NN>` above is a
  placeholder.
- **`SAID.mounts:`** is a bracketed list of the roots where the lane's production lands, relative to the lane root
  (`[src/]` for one path); a lane that ships nothing writes the bare word `none`.
- **A multi-lane root** adds one key line to its own block, `- SAID.lanes: [WEB=web/, API=api/, APP=./]`: each
  pair is a token (a letter, then letters and digits) and that lane's directory relative to this file, ending in
  `/`. `/said:setup --fix` at the root proposes the line from the lanes beneath it.
- **The version stamp.** `SAID.version:` sits directly under `SAID.lane:` and names the release the lane is at,
  with its id. An absent key means unversioned, never a halt. A starter also keeps a root `CHANGELOG.md`.
- Remove any older project-type flag and every branch keyed on it.

## Step 2 -- The consume-contract registry

Author only the surface-contract artifacts the lane consumes, at their fixed leaves under `SAID.docs-root:`:
`ux/feature-ux-rules.md`, `ux/feature-ux-checklist.md`, `qa/feature-qa-checklist.md`, `ux/feature-ux-grammar.md`.
Keep the leaf names verbatim; a renamed leaf is missed silently. Give every mapping artifact an `SC-HEADER` line
carrying a token and an honest rule count. A lane that reasons over no surface-shape rules ships none; never write
an empty registry to pass a check. A UX checklist kept under `docs/qa/` moves to `docs/ux/`, with every reference
fixed. Describe the checker model in the lane's own words.

## Step 3 -- `SAID.surface:` and `SAID.reviewers:`

`SAID.surface:` is the medium (`web`, `api`, `mcp`, `cli`, `native`, `doc` or `none`); `SAID.reviewers:` names the
checkers that gate it, read whole. A surface-bearing lane names at least one checker, authoring it where the plugin
does not ship one for that medium; a lane with no checker for its medium declares `none`, never a hollow gate. A
checker's `said-governs:` line carries a concrete medium (`surface=web`), never a template placeholder.

## Step 4 -- The per-feature `Surface:` field and the completeness checker

Add a `**Surface:**` field to `docs/features/template.md` (a medium or `none`); the architect skill fills it from
the lane surface, `none` for a screenless feature. The completeness checker compares a feature's designed screen
outline (`docs/working/<feature>/toc.md`) with what was built, so it applies only to a lane whose features carry a
screen outline (a `web` lane). Such a lane names it beside its surface checker (`[web-ux, completeness]`); an `api`,
`mcp`, `cli` or surface-less lane does not.

## Step 5 -- `## Earned rules` and `SAID.profile:`

- Add a `## Earned rules` section to `CLAUDE.md`: one rule per `- ` line, each with an `R-<LANE>-<NN>` id and a
  link to the record that holds its rationale. A heading with zero rules is valid.
- Add `SAID.profile:` naming the family of deliverable the lane produces (`code`, `doc` or `work`). Never derive it
  from `SAID.surface:`: a code lane with no UI and a work lane both declare `none`.
- The lane's `docs/adr/README.md` lists only records that exist and states the threshold for promoting a decision
  to a record.
- **An instance copies its starter's rules** into its own section, each keeping its starter id, with links that
  resolve from the instance's root, above the lane's own rules; it then amends them (adds, removes with a reason,
  adjusts). A starter or a standalone lane authors its own rules.

## Verify

**V1 -- plugin version.** Expect `said@<marketplace> 0.8.0` or later, one line per install scope.

```bash
claude plugin list 2>/dev/null | awk '/ said@/{p=$2} /Version:/{if(p){print p, $2; p=""}}'
```

**V2 -- the lane block.** Expect no `[BLOCKER]` line and a ledger with `0 BLOCKER`.

```bash
SAID_PLUGIN="${SAID_PLUGIN:?set to the installed said plugin directory}"
LANE="${LANE:-.}"
python3 "$SAID_PLUGIN/skills/setup/setup_check.py" --root "$LANE" | grep -E '\[BLOCKER\]|^ledger'
```

**V3 -- earned rules.** Expect a rule count and no `uncitable:` line.

```bash
SAID_PLUGIN="${SAID_PLUGIN:?set to the installed said plugin directory}"
LANE="${LANE:-.}"
python3 "$SAID_PLUGIN/skills/review-qa/earned-rules.py" count "$LANE/CLAUDE.md"
```

Then set `SAID.version: said@0.8.0` by hand.

## What you do NOT do

- **No new rule.** This playbook orders existing contracts; it adds none.
- **No engine edit, no new skill.** Config and docs against the lane.
- **No checker invented to pass a check.** A medium with no checker declares `none`.
- **No commit** unless the lane's owner asks.
