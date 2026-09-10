# uxtoc element-projection taxonomy
UXP-V-1 · 7 containers

Deterministic, exhaustive projection from an emitted `toc.md` outline to its element set.
LOADed WHOLE + VERIFY-TOKEN by `uxtoc` (to count for `toc-checksum:`) and by the completeness
check (to derive DESIGNED). One source; neither consumer re-derives the container set.

## Machine-readable
containers: Columns,Filters,Row actions,Page actions,Sections,Bottom actions,Actions

## Rule
- A `## Screen <SCREEN-ID> — <title>` line opens a screen; the screen key is `<SCREEN-ID>`
  (the token after `## Screen `, before ` — `). `## ` is the only header the projection reads.
- Under a screen, each KEYED item (`<key>:`) nested directly beneath one of the containers above
  is ONE element; its id is `<key>` — the stable key, never the gloss.
  (`Sections:` nests fields under a `<section-name>:`; each `<field-key>:` is an element.)
- DESIGNED is the set of `(screen, key)` pairs. `toc-checksum: total=<N>,<SCREEN-ID>=<n>,…`
  states `|DESIGNED|` as the grand total and per screen.
- **Keys are unique per screen across containers.** DESIGNED is `(screen, key)`, not
  `(screen, container, key)` — so the same key under two containers on one screen (e.g. a `status`
  column AND a `status` filter) collapses to a single element. Qualify one (e.g. `status-filter`)
  whenever a key would otherwise repeat on a screen, so the projection keeps the two distinct.

## NOT elements (unkeyed scaffolding / attributes)
`Sorts:`, `Empty state:`, `URL state:`, `Badges`, `Title`, `Description`, `Rail`, `Specs:`,
`Purpose`, `Data hook:`, and every attribute line under an element (`title:`, `type:`, `render:`,
`label:`, `target:`, `permission:`, `shape:`, `confirm:`, `required:`, `validation:`, `placeholder:`,
`help:`, `options:`, `note:`, `align:`, `width:`, `pinned:`, `hidden:`, `meta:`). Counting these
would require judgment about what is a deliverable — which crosses W2.

**Custom-pane `Blocks` are out of completeness scope.** A custom pane emits blocks as
`- <block-name> — <gloss>` (non-keyed prose), so they carry no keyed element and are not counted —
`Blocks` is deliberately NOT a projection container. A custom-only screen therefore has zero designed
elements (it is freeform, not a checkable element set); a feature whose only surface is such a screen
sets `Surface: none` or accepts no completeness coverage for it.

## Determinism
Purely structural over the closed container set — no selection, ranking, or inference; byte-stable
across re-runs of the same `toc.md`. The count is a projection, not an opinion.
