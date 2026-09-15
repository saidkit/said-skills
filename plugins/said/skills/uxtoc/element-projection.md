# uxtoc element-projection rule
UXP-R-1

The deterministic, medium-agnostic projection from an emitted `toc.md` outline to its element set.
LOADed WHOLE + VERIFY-TOKEN by `uxtoc` (to count) and by the completeness check (to derive DESIGNED).
This file owns the RULE only. The per-surface vocabulary - the container set, the attribute set, and
the scaffolding excluded from the projection - lives in the injected lane grammar
(`docs/ux/feature-ux-grammar.md`, one SC-HEADER section per surface), read via `$SAID_GRAMMAR` +
`$SAID_SURFACE`. Neither consumer re-derives the rule or the vocabulary from memory.

## Rule
- A `## <Unit> <ID> - <title>` line opens a unit; the unit key is `<ID>` (the token after
  `## <Unit> `, before ` - `). `<Unit>` is the grammar's declared unit word. `## ` is the only
  header the projection reads.
- Under a unit, each KEYED item (`<key>:`) nested directly beneath one of the grammar's declared
  containers is ONE element; its id is `<key>` (the stable key, never the gloss).
- A valueless keyed line whose key is in the grammar's closed **attribute set** is an *attribute
  group*, NOT an element, and does NOT disqualify its parent from being a leaf element. This is the
  attribute-set-aware test: a designed element carrying a nested keyed attribute (e.g. `status:` with
  a nested `filterable:` attribute) stays the element; the attribute never steals its status. This
  closes a projection bug where a nested attribute would otherwise steal element status from its
  parent, silently dropping the parent element from DESIGNED at an unchanged count.
- DESIGNED is the set of `(unit, key)` pairs.
- **Keys are unique per unit across containers.** DESIGNED is `(unit, key)`, not
  `(unit, container, key)` - so the same key under two containers on one unit, or repeated across a
  tabbed unit's sub-groups, would collapse to one element. Qualify one (e.g. `status-filter`,
  `members-name`) whenever a key would otherwise repeat on a unit, so the projection keeps the two
  distinct and a tabbed unit never silently collapses two elements into one. `uxtoc` WARNs (advisory)
  at emit when a key would collide across two of a unit's containers, so the collapse is surfaced, not
  silent.

## Scaffolding excluded from the projection
The grammar's `## Machine-readable` block declares, per surface, the `attributes:` (the closed
attribute set above) and the `not-elements:` (unkeyed scaffolding and out-of-scope groupings).
Counting scaffolding would require judgment about what is a deliverable, which crosses the mirror
boundary (the projection mirrors, it never evaluates). A unit yielding zero designed elements is a
hollow FAIL. A container legitimately emptied is written `<container>: none - <reason>` (the
explicit-empty idiom, an operator-owned outline convention).

## Determinism
Purely structural over the grammar's closed container, attribute, and not-elements sets - no selection, ranking, or
inference; byte-stable across re-runs of the same `toc.md`. The count is a projection, not an opinion.
