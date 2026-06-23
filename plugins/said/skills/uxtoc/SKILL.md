---
name: uxtoc
description: >
  SAID/Phase 1.5 — descriptive table-of-contents for spec artifacts.
  Reads a scope.md, feature spec, screen spec, or feature working dir
  and emits a hierarchical outline (screens → header band → panes →
  fields/columns/sorts/filters/actions) with each element's attributes
  flattened to short nested bullets. Purely descriptive — no
  evaluation, no rule comparison, no gap flagging, no recommendations.
  Multi-screen features render one outline section per screen.
  Designed for fast spec-iteration: scan → spot what's wrong → edit
  the spec → re-run. Triggered ONLY by the explicit command "/said:uxtoc
  <path> [output=<file-or-dir>]". Default output is inline (chat);
  operator passes output= to write a file. NOT for spec authoring —
  that's /said:uxgen. NOT for rule-based spec evaluation — that's
  the sibling evaluator skill.
---

# UX TOC

Read-only. Emits a structured outline of what a SAID spec artifact actually says — at element granularity, with each column / field / filter / action expanded into its attributes (title, type, renderer, operator, variant, label, target, permission, …).

Purpose: tight feedback loop for spec authoring. Operator reads the TOC, spots a missing attribute or wrong shape, edits the spec, re-runs `/said:uxtoc`. No review-and-fix loop — the TOC carries no judgment, only what the spec says.

## When this fires

The operator invokes:

- `/said:uxtoc <path>` — outline to chat.
- `/said:uxtoc <path> output=<file-or-dir>` — write to that path. If a directory, the file is named `toc.md` inside it. If a file path, that exact file is written (prompt overwrite / suffix `-2` / abort if it exists).

`<path>` resolves to one of:

- `docs/screens/<SCREEN-ID>.md` — single screen.
- `docs/features/<FEAT-ID>.md` — feature spec; outline scope + every screen the spec references (inline `## Screen` sections AND linked `docs/screens/*.md` files).
- `docs/working/<feature>/scope.md` — scope only.
- `docs/working/<feature>/` — directory; glob `scope.md` + `screens/*.md` + any inline `## Screen` sections in sibling spec files.

## Out of scope

- No evaluation against ADRs or `docs/ux/*` frozen rules.
- No "should have X" recommendations.
- No proposing missing elements.
- No source-code reading — spec docs only.
- No mutation of the input spec.

## Pass 1 — Resolve + classify

1. Resolve `<path>`. If missing, abort with the path that wasn't found.
2. Classify: `screen` | `feature-spec` | `scope` | `dir`.
3. Ground in templates (one parallel-Read batch):
   - `docs/features/template.md` — feature-spec shape.
   - `said:uxgen screen-spec template (template-screen.md)` — screen-spec shape.
   - `docs/ux/lists.md`, `docs/ux/form.md`, `docs/ux/form-inline.md`, `docs/ux/form-table.md`, `docs/ux/form-custom.md` — pane-type vocabulary.

## Pass 2 — Extract

For each artifact in scope, walk in this order and capture only what the spec actually states:

**Per screen**:
- `SCREEN-ID`, title, route, declared permission gate, layout (single / tabbed / overlay-stack / …).
- Header band — Title / Badges / Description / Actions.
- For each pane:
  - Name, pane-type (list / form-basic / form-inline / form-table / custom), one-line purpose, data hook (if declared).
  - **list pane** → columns (each with title/type/render/hidden/meta/align/width/pinned), sorts (inline), filters (each with field/operator/variant/options/placeholder/note), row actions (each with label/target/permission/confirm), page actions (same shape), empty state, URL state.
  - **form pane** → sections containing fields (each with label/type/required/validation/placeholder/help), bottom actions, rail (Tip / Shortcuts), canEdit.
  - **custom pane** → blocks.

**Per scope.md**: §A purpose, §B target shape (screens listed), §C constraints — one-line gloss each.

**§C constraint filter — UX-only.** Keep only constraints that shape the UX surface:
- Affordance gating / RBAC variance.
- Layout / responsive shape / pane composition.
- Visual rules (specific component required, banner placement, empty-state semantics).
- URL state shape / shareable-URL contract.
- Loading / error / empty rendering semantics.

Drop: file-naming conventions, codebase organization (which dir an entity lives under), scope boundaries (out-of-scope notes — those belong in §B or in the scope.md's own out-of-scope section, not §C of the TOC), tech-stack picks, build-tooling.

Do not invent. If the spec is silent on a sub-attribute (e.g., column declares no `align`), omit the line entirely — do not write "align: not specified".

**Explicit-empty rule.** When the spec explicitly says a slot is empty with a reason (e.g. "no header actions in Phase 1 — create flow is Phase 2"), preserve it as `<slot>: none — <reason>`. Silent-empty (slot not mentioned) still drops per the rule above; explicit-empty is informative and survives.

## Pass 3 — Emit

```
# TOC: <feature or screen name>
Source: <input path>

## Scope  (only if scope.md is in input)
- §A Purpose — <gloss>
- §B Screens: <SCREEN-ID>, <SCREEN-ID>, ...
- §C Constraints:
  - <constraint> — <gloss>

## Screen <SCREEN-ID> — <title>
- Specs:
  - Route: <route, verbatim — e.g. /w/:wsSlug/users/:userId>
  - Permission: <gate, if declared>
  - Layout: <single | tabbed | overlay-stack | …>   (only if non-default; default = single. When tabbed, panes are the tabs in declaration order.)
- Header band:
  - Title — <gloss or ${entity.var} verbatim>
  - Badges — <gloss>
  - Description — <gloss>
  - Actions:
    - <action-key>:
      - label: <label, verbatim>
      - target: <route or mutation>
      - permission: <gate>                   (only if declared)
      - shape: <inline | dropdown | menu>    (only if declared)
    OR (explicit-empty):  Actions: none — <reason>

- Pane: <name>  (<list | form-basic | form-inline | form-table | custom>)
  - Purpose — <gloss>
  - Data hook: <hookName(args)>             (only if declared)

  [list pane]
  - Columns:
    - <field-key>:
      - title: <display title>
      - type: <string | number | date | bool | enum | relation>
      - render: <renderer — e.g. AvatarChip, StatusBadge, currency, link to /…>
      - hidden: by default                   (only if hidden by default — normalizes spec flags like `meta: advancedOnly`, `hiddenByDefault: true`, `defaultVisible: false`)
      - meta: <free-form tag>                (only if declared and not already captured by `hidden`)
      - align: <left | right | center>       (only if declared)
      - width: <fixed | flex | <px>>          (only if declared)
      - pinned: <left | right>                (only if declared)
  - Sorts: <key1> (<asc|desc> default), <key2>, <key3>
  - Filters:
    - <filter-name>:
      - field: <field>
      - operator: <eq | contains | in | between | …>
      - variant: <text | select | multiselect | date-range | …>
      - options: <inline list>               (only for select-style)
      - placeholder: <verbatim>              (only if declared)
      - note: <free-form annotation>         (only if declared — e.g. server-capability or known limitation)
  - Row actions:
    - <action-key>:
      - label: <label, verbatim>
      - target: <route or mutation>
      - permission: <gate>                   (only if declared)
      - confirm: <yes | destructive>         (only if declared)
  - Page actions:
    - <action-key>: (same shape as row actions)
  - Empty state:
    - copy: <gloss>
    - cta: <action-key, if any>
  - URL state: <param1>, <param2>, …          (only if declared)

  [form pane]
  - Sections:
    - <section-name>:
      - <field-key>:
        - label: <label, verbatim>
        - type: <text | email | select | toggle | date | …>
        - required: <yes | no>               (only if declared)
        - validation: <gloss — e.g. "email format", "1-64 chars">
        - placeholder: <verbatim>            (only if declared)
        - help: <gloss>                      (only if declared)
  - canEdit: <true | false>                  (only if declared)
  - Bottom actions:
    - <action-key>: (same shape as list row actions)
  - Rail:
    - Tip — <gloss>
    - Shortcuts — <gloss>

  [custom pane]
  - Blocks:
    - <block-name> — <gloss>

- Pane: <next-pane-name> ...

## Screen <next-SCREEN-ID> — ...
```

For multi-screen feature inputs, repeat the `## Screen` section per screen in the order the feature spec references them.

If `output=<path>`:
- Directory → write `<path>/toc.md`.
- File path → write that path. If file exists, ask: overwrite, suffix `-2`, or abort.
- After write, print the resolved path to chat and a one-line summary (N screens, M panes).

If `output=` omitted: print to chat only.

## Glossing discipline

- 2–3 words per gloss. Drop articles. Verb-led for actions ("save changes", "delete row"), noun-led for fields/columns ("user email", "created date").
- **Verbatim tokens.** When the spec uses interpolation syntax (`${entity.var}`, `:paramName`, `{{var}}`), preserve the token exactly. Don't paraphrase `${user.email}` to "user email". Applies to routes (`/users/:userId`), header titles (`Entity #${id}`), field labels, badge text, action labels.
- **Source-wording first.** Use the spec's own wording when concise; paraphrase only when the spec phrasing is long-form.
- Never editorialize ("clearly named", "needs work", "could be better").
- **Omit absent attributes.** Silence in the source becomes silence in the TOC.

## Fast-iteration discipline

The skill is designed for rapid spec editing — emit → spot → edit → re-emit. To keep diffs meaningful between runs:

- **Deterministic ordering.** Screens in spec-reference order. Within a screen: Specs → Header band → Panes in declaration order. Within a pane: attribute order is fixed (see Pass 3 template).
- **No timestamps, no run metadata.** Header is just `# TOC: <name>` + `Source: <path>` — nothing else that changes between runs.
- **No recommendations.** Re-running after an edit should show only structural diffs from the spec change, never a different verdict on the same content.
- **Stable attribute names.** Use the canonical attribute names listed in Pass 3 (`title` not `header`, `render` not `renderer` or `cell`, `target` not `action` or `link`). Same name across all panes and elements.
