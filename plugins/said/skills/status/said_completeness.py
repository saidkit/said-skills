#!/usr/bin/env python3
"""Completeness recompute — the uxtoc basis->contract lifecycle's accept-time check.

A recipe-form Checker's `said-recompute` (said-judge: oracle). Deterministic and
bluff-proof. DESIGNED is re-derived from the persisted NORMALIZED element list
($SAID_WORKDIR/toc-elements.md), a flat artifact chosen (over parsing uxtoc's rich
toc.md) to avoid grammar ambiguity. Parse rule — `## <Screen>` lines are the ONLY
headers; EVERY other non-blank line is one designed element id (an optional leading
`- `/`* ` is stripped). Each element is qualified by its screen, so DESIGNED is a set of
`(screen, id)` pairs: the same label on two screens (email on Login AND Signup) is two
distinct designed elements and cannot collapse, and because nothing but a `## ` header is
skipped, no element — even a single-`#`-leading id — is silently dropped (one contract
caveat: an element id that itself begins with `## ` must be bulleted, `- ## x`, or it
reads as a screen header — `## ` is the only header). Note the bluff-proofing is against a
fabricated *verdict* and an omitted *build*; it does not defend against tampering with the
design list itself (the operator-owned source of truth), matching the Done-when's scope.

The capture manifest ($SAID_CAPTURE) uses the SAME `## <Screen>` grouping:
    ## <Screen>
    built: <id>
    dropped: <id> :: <reason>          # reason required + non-empty; delimiter ` :: `
so BUILT and DROPPED are also `(screen, id)` pairs. Exit 0 iff designed is-subset-of
(built union dropped) AND the list is non-empty; else 1; exit 2 on a usage / missing
input error. The raw uxtoc `toc.md` is the upstream design aid the operator normalizes
from; uxtoc is untouched.

Invoked by the L2 oracle (said_status.py --reviewer-gate) from the lane root with
SAID_WORKDIR (the feature working dir holding toc-elements.md) and SAID_CAPTURE (the
manifest) in the environment.
"""
import os
import sys


def die(msg, code):
    sys.stderr.write("completeness: " + msg + "\n")
    sys.exit(code)


def strip_bullet(s):
    return s[2:].strip() if (s.startswith("- ") or s.startswith("* ")) else s


wd = os.environ.get("SAID_WORKDIR")
cap = os.environ.get("SAID_CAPTURE")
if not wd or not cap:
    die("SAID_WORKDIR and SAID_CAPTURE are required in the environment", 2)

elements = os.path.join(wd, "toc-elements.md")
if not os.path.isfile(elements):
    die("no normalized element list at %s" % elements, 2)
if not os.path.isfile(cap):
    die("no capture manifest at %s" % cap, 2)

# DESIGNED — (screen, id) pairs. `## <Screen>` is the only header; every other non-blank
# line is one designed element id. Screen-qualifying keeps a label shared across screens
# distinct; skipping only `## ` headers means no element can be silently dropped.
designed = set()
screen = ""
with open(elements, encoding="utf-8") as fh:
    for raw in fh:
        line = raw.strip()
        if not line:
            continue
        if line.startswith("## "):
            screen = line[3:].strip()
            continue
        eid = strip_bullet(line)
        if eid:
            designed.add((screen, eid))

if not designed:
    die("FAIL: normalized element list is empty (hollow — nothing to certify complete; "
        "list the designed elements under `## <Screen>` headers, or set Surface: none)", 1)

# BUILT + DROPPED — (screen, id) pairs from the manifest (same `## <Screen>` grouping).
built, dropped = set(), set()
screen = ""
with open(cap, encoding="utf-8") as fh:
    for raw in fh:
        line = raw.strip()
        if not line:
            continue
        if line.startswith("## "):
            screen = line[3:].strip()
            continue
        if line.startswith("built:"):
            built.add((screen, line[len("built:"):].strip()))
        elif line.startswith("dropped:"):
            rest = line[len("dropped:"):].strip()
            if " :: " not in rest:
                die("FAIL: dropped element '%s' has no recorded reason (use 'dropped: <id> :: <reason>')" % rest, 1)
            eid, _, reason = rest.partition(" :: ")
            if not reason.strip():
                die("FAIL: dropped element '%s' has an empty reason" % eid.strip(), 1)
            dropped.add((screen, eid.strip()))

missing = sorted(s + " / " + e for (s, e) in designed if (s, e) not in built and (s, e) not in dropped)
if missing:
    die("FAIL: designed elements neither built nor dropped: %s" % ", ".join(missing), 1)
print("completeness PASS: %d designed <= %d built + %d dropped" % (len(designed), len(built), len(dropped)))
sys.exit(0)
