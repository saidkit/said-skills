#!/usr/bin/env python3
"""rule_chain.py: the no-model half of the scope chain on a large lane. Stdlib only. Every output is a function of
its inputs: the same input gives the same bytes. A model never chooses what is read: this script cuts the lane's
rule documents into items and sections, decides which sections are read, cuts the read into parts, and checks every
step a model takes. Exit 0: done or the check holds; 1: the check found faults (printed one a line); 2: refused
(an input is absent or malformed, printed on one line); 3: no rule folder (no SAID.scope-mounts and none of the
default folders; a hint is printed), or `status` finds that the chain's inputs changed. Every command that reads the lane takes --handoff
<handoff>, so a document the handoff names joins the rule documents. A command never removes a file: an output that
already holds the bytes it would write is left as it is; one that holds other bytes is set aside as
<name>.failed-<k> before the new one is written.

usage: rule_chain.py size --lane <lane> [--handoff <handoff>] [--manifest <out mounts.md>]
       rule_chain.py cut <lane> <out pieces.tsv> [--handoff <handoff>]
       rule_chain.py status <lane> <chain folder> --handoff <handoff> [--readings <K> | --single-read] [--budget <bytes>]
                           [--hint <dir>,<dir>]
       rule_chain.py readings <chain folder> <K | single>
       rule_chain.py sections <lane> <pieces.tsv> <out folder> [--cards <cards.tsv>]
       rule_chain.py card-portions <lane> <pieces.tsv> <out folder> [--cards <cards.tsv>]
       rule_chain.py cards <portion folder> --lane <lane>
       rule_chain.py cards-join <lane> <out cards.tsv> <portion folder>... [--keep <cards.tsv>]
       rule_chain.py cards-fresh <lane> <cards.tsv>
       rule_chain.py cards-agree <lane> <cards A.tsv> <cards B.tsv> <out folder>
       rule_chain.py decisions <handoff> <run folder> [--docs <pieces.tsv>]
       rule_chain.py decisions-in <chain folder>
       rule_chain.py readlist <sections folder> <out folder> --cards <kinds.tsv>
       rule_chain.py zone <lane> <pieces.tsv> <sections folder> <read-list.tsv> <out folder> [--all] --budget <bytes>
       rule_chain.py coverage <lane> <read folder>
       rule_chain.py holes <lane> <chain folder> [--budget <bytes>]
       rule_chain.py hole-join <lane> <chain folder>
       rule_chain.py reverse <sections.tsv> <out sections.tsv>
       rule_chain.py subjects <pass folder> [--fill]
       rule_chain.py join <pass 1 folder> <pass 2 folder> <out folder>
       rule_chain.py table-join <first table.tsv> <second table.tsv> <out table.tsv>
       rule_chain.py pairs <run folder> [--lane <lane> --handoff <handoff>]
       rule_chain.py pairs-subject <lane> <run folder>
       rule_chain.py pairs-deal <look folder> <fresh parts folder> [--cap 26]
       rule_chain.py pairs-merge <look folder> <parts folder>
       rule_chain.py look-copy <run folder> <look folder>
       rule_chain.py confirm-items <run folder> <lane> --handoff <handoff>
       rule_chain.py confirm-in <run folder>   (the confirm look's reply on stdin)
       rule_chain.py confirm-check <run folder>
       rule_chain.py look-join <look folder A> <look folder B> <out look.tsv> --lane <lane> --handoff <handoff>
                           --split <out split.tsv>
       rule_chain.py questions <run folder>
       rule_chain.py questions-deal <run folder> <fresh parts folder> [--cap 70] [--reverse]
       rule_chain.py question-check <folder> --look A|B --lane <lane> --handoff <handoff>
       rule_chain.py questions-merge <look folder> <parts folder>
       rule_chain.py question-join <look folder A> <look folder B> <out questions-join.tsv> --lane <lane> --handoff <handoff>
       rule_chain.py audit-dirs <lane> <run folder> --handoff <handoff> [--hint <dir>,<dir> | --hint -]
       rule_chain.py audit-check <audit folder> <audit id> --lane <lane>
       rule_chain.py cites <lane> <out cites.tsv> --handoff <handoff>
       rule_chain.py draft-in <run folder> <out folder> --lane <lane> --handoff <handoff>
       rule_chain.py trace <run folder>
       rule_chain.py carried <run folder> [--d-items]
       rule_chain.py pass-check <pass folder> --mandatory --kinds <kinds.tsv> [--net]
       rule_chain.py select <chain folder>
       rule_chain.py by-size <sections.tsv> <out sections.tsv>
       rule_chain.py zone <lane> <pieces.tsv> <sections folder> <selected.tsv> <out folder> --selected --budget <bytes>
       rule_chain.py line-check <chain folder>
       rule_chain.py pair-silent <chain folder>
       rule_chain.py pass-3 <chain folder> --round <1 | 2 | 3>
       rule_chain.py tiers <chain folder>
       rule_chain.py zone <lane> <pieces.tsv> <sections folder> <join/zone.tsv | join/band.tsv> <out folder> --selected --budget <bytes>
       rule_chain.py tier-join <chain folder>

size         the lane's rule documents: CLAUDE.md and the paths of `SAID.scope-mounts:` in its `## Lane` block (a
             path ending / is a folder read for .md files, a work folder skipped; any other path is that file),
             or with no such key the default folders adr/, ux/ and qa/ under the docs root that exist,
             with a document the handoff names outside them added for that handoff; their count and bytes, the
             top-level docs folders no path reaches, and `size: small` or `size: large` (above LARGE_BYTES);
             --manifest writes the same as a block the trace carries
cut          the rule documents into items (a list item, a paragraph, a table row, a fenced block, a heading):
             pieces.tsv (id, path, first line, last line, heading); every line lies in one item; with --handoff,
             beside it once the hash record inputs.sha256 (sha256 of the handoff, every rule document, the cut and
             this script); refused when the folder's record holds other inputs
status       where a chain folder stands, written to its status.txt and printed: `go on at <k>` (the first step of
             the chain whose outputs are missing or fail the step's own check: a script output made again in
             memory and compared byte for byte, an agent's output put to its check), each preceded output a check
             command writes and now writes otherwise as a `run first:` line; `blocked at <k>: ...` (a return round
             on record and its check still fails, exit 1); `done` (the draft passes trace and carried); or
             `new chain: <reason>` (no hash record, or the handoff, a rule document or the cut changed; exit 3).
             It writes nothing but status.txt
sections     one row a heading section (id, path, heading path, first line or card, item count): sections.tsv and
             section-items.tsv; with --cards the section's card stands in place of its first line; a lane line
             `Applies when: ...` under a heading wins over the card
card-portions  the documents that hold a section with no fresh card in <cards.tsv> (all documents without it), cut
             into portions of about 150000 bytes: <out folder>/portion-r<n>/ with portion.tsv, sections.tsv,
             section-items.tsv, pieces.tsv; prints the portions, or `nothing to card`
cards        the check of one portion's cards.tsv (section id, kind rule or no-rule, line, quote place, quote)
cards-join   the portions' cards as one table (section id, document, heading path, occurrence, kind, line, quote
             place, quote, sha256 of the section's text); with --keep, a section of no portion keeps its card from
             that table when the card is fresh; refused when a section of the lane is left with no card
cards-fresh  the sections whose text no longer matches their card (or that have none); exit 1 when any
cards-agree  kinds.tsv: a section is `no-rule` only when both builds say so; both builds fresh for every section
decisions    the check of the decision list (decisions.tsv, context.tsv, decision-pairs.tsv) against the handoff
readlist     read-list.tsv: every section whose kind is not `no-rule`; left-out.tsv: the others with both cards
zone         the text of the read-list sections (with --all; without it only those that name a decision) in parts
             of at most <bytes>: zone-r<n>.md, portion-r<n>.tsv, pieces.tsv, portions.tsv in <out folder>
coverage     the readers' files read-r<n>.tsv (and read-r<n>.r<k>.tsv of a later round) against the zone: writes
             table.tsv (the good rows) and gaps.tsv (portion, unit or row, why); exit 1 while a gap is open
reverse      the documents of a sections.tsv in reverse order (the second first pass)
subjects     the check of one first pass's subjects.tsv: every section one row, `out`, `touched` or `open`;
             --fill appends `open` for every section with no row and never removes a row
join         read-list.tsv of every section not put out by both passes, with the decisions that touch it;
             left-out.tsv of the others
table-join   a first-read row stands; a unit with only `none` rows in the first table takes the second's rows
pairs        checks.tsv (every `against` row) and pairs.tsv for the second look; when look.tsv exists, its check;
             a reason (case and spaces folded) on more than 3 lines of one part is refused
pairs-subject  subject-pairs.tsv: the pairs whose two sections share at least 5 words (4 or more letters, lower case,
             less a stop list); once it is there, pairs, pairs-deal and the draft's gap check take only these pairs
pairs-deal   the against rows and pairs dealt into parts of at most 26 pairs (a decision's together where they fit,
             else split by against rule), one folder a part with its own table, checks.tsv and pairs.tsv
pairs-merge  the parts' look.tsv and pairs-look.tsv joined into the look folder's; refused while a part has no
             look.tsv or the folder already has one
look-copy    the run folder's table, decisions, checks and pairs into a look folder
confirm-items  confirm/C<nn>.md, one item for each against row look.tsv keeps (the decision's handoff lines, the
             rule's section with the rule line marked >>, and Q1: holds, does not hold or cannot tell), and
             confirm/items.tsv (id, unit, decision, rule); nothing when the look keeps none
confirm-in   the confirm look's reply, read on stdin: kept whole as confirm/answer-<k>.txt; its answer lines
             written to confirm/confirm.tsv (one there before set aside first)
confirm-check  the check of the confirm look's confirm/confirm.tsv: one line an item, `<id> TAB Q1 TAB holds|does not
             hold|cannot tell TAB <sentence of at least 3 words>`, the items those of the look's kept rows
look-join    keep only when both looks keep; drop only when both drop; ask only when both ask; a row the looks
             split on (verdicts differ, or both keep under different decisions) goes to --split, never to
             look.tsv; each look must pass `pairs`
questions    questions.tsv: the `asks` rows of the run folder's table, each once
questions-deal  the questions dealt into parts of at most 70 rows (a decision's together where they fit), one folder
             a part with questions.tsv and decisions.tsv; --reverse writes each part's rows in the opposite order
question-check  the check of one question look's qlook.tsv (unit, decision, rule, kind, cited line or -, reason):
             the kind is choice, rule-settles, answered or no-bear; answered cites the handoff line that does it,
             rule-settles and no-bear the rule line that shows it, choice may cite none; one line a row, the cited
             line exists, a reason of at least 3 words, no reason on more than 3 lines of a part
questions-merge  the parts' qlook.tsv joined into the look folder's; refused while a part has none or the folder has one
question-join  a question becomes a rule to follow only when both looks say rule-settles, and a rule the handoff
             follows only when both say answered; every other row stays a question; both looks must pass their check
audit-dirs   the directories the handoff names in backquotes (a path ending /), or the --hint list: found from the
             lane root or as the end of exactly one lane directory path; one that is gone takes its feature directory
             found so, the ancestor two names deep, else its nearest existing ancestor (state parent); writes
             audit/dirs.tsv and a task file for each one found; an absent or ambiguous one gets a line in the
             draft and no audit. A handoff outside the lane names paths from its root: the nearest directory above
             it whose CLAUDE.md declares SAID.lanes (printed with the row count), else its own directory; a path
             under this lane is found lane-relative, one under another row's root is state other-lane (no audit).
             A path under a declared SAID.mounts route is in the lane wherever its link lands, and the walk follows
             that link; any other symlink but the docs root is not followed. A --hint directory no handoff line names
             takes the whole handoff as its target shape
cites        cites.tsv: every `#<n>` item the handoff cites in a rule document (`<name>.md`, at most three words,
             then `#<n>`, more `#<n>` after it): the handoff's words for it beside the item's first line (a line
             `<n>. ` under a heading holding the word before the first `#`, else the one such line), one row a
             cite: id, handoff line, document, n, item line, handoff words, item first line, state; the state is
             match (every word of four letters or more of the handoff's is on the item's first line), mismatch,
             ambiguous (more than one such item), no-item, no-file or no-words; an item is also a heading `#<n>`
audit-check  the check of one audit report: its heading, Coverage line, five sections in order, finding ids of its
             audit, each finding citing a lane line with words on it, or (absent)
draft-in     the drafter's folder: the run folder's decisions, looks, split rows and manifest, table-all.tsv,
             and table.tsv without the rows of split.tsv; refused (exit 2, nothing written) while an against row of
             that table has no look line or a pair of it has no pairs-look line: run the looks on the joined table;
             refused while an `asks` row has no question-join line, while audit/dirs.tsv is absent or an audit
             report fails its check; the rows that are no longer questions leave the drafter's table; while
             look.tsv keeps an against row, refused unless confirm/confirm.tsv passes confirm-check: a kept row
             the confirm says does not hold becomes a drop in the drafter's look.tsv, its sentence the why-not;
             cannot tell becomes an ask with the sentence and its table row a question row (class asks) in
             the drafter's table, named in its decision's question frame with the sentence; writes the drafter's
             cites.tsv (as cites)
trace        writes the trace of every row other than none, with its look, at the end of scope.md; the rows of
             split.tsv go in their own block, both looks' verdicts and grounds verbatim; the rules to follow and the rules the handoff
             follows each in their own block with both grounds; then the codebase audits section: the path line, a line for each directory not
             audited, each report whole
carried      the check of the draft: every row the looks do not drop is in the trace; every audit finding id is
             named in the draft (where it shapes the work, or under `Findings not carried`); every cite of
             cites.tsv not in state match is asked in section D as its item, a line that begins `- **C<k>**`, and
             each such item has a `Hint` line with a rule `path:line` (two or more for an ambiguous cite) or
             `no single item`, and a `Question:` line; with --d-items every
             conflict and question has its d-items.tsv line and is named in the draft
pass-check   the subjects check of one pass, and one line a rule section (kinds.tsv not no-rule) is mandatory: a
             `touched` row or an `out` row (on the section or its document); a rule section with neither is one
             more fault (`section <s> has no line: neither touched nor out`), exit 1. --net, after the return
             round: refused while a section is silent and the pass has no subjects-faults.txt; on no subjects
             fault writes net.tsv, the rule sections still silent (to be read)
select       join/selected.tsv: the rule sections touched by either pass, or in either pass's net.tsv, with the
             decisions the passes name (`-` for a net section); join/left-out.tsv: every other section, a no-rule
             one with its two card lines, a rule one with both passes' `out` lines; refused on a pass that fails
             pass-check, on a net.tsv that is not the pass's silent sections, and on a rule section in neither file
by-size      the documents in order of their largest section's item count, largest first (cut order on a tie),
             each document's sections together in cut order (the zone deals whole documents)
zone --selected  the zone of the selected sections: every section the list (selected.tsv, zone.tsv or band.tsv)
             names, each with all its items
line-check   every rule section has a line: a left-out line, or each of its items answered (a row or `none`) in
             table.tsv; exit 1 names each section without one. With join/band.tsv (the tiers): a rule section left
             out needs an `out` line of pass-1, pass-2 or pass-3 (its own out row), a no-rule section its card line
pair-silent  pass-3/: sections.tsv of every rule section (kinds.tsv) with no `touched` and no `out` row of pass-1
             or pass-2 (an `out` row on a document path counts for its sections), its card line as a sixth field;
             decisions.tsv as the passes had it; refused when pass-3/ exists
pass-3       --round <k>, after round k (1 to 3, in order) of the silence pass: the subjects check of pass-3, and a
             fault for every listed section with neither a `touched` nor an `out` row; the round's line in
             pass-3/rounds.tsv (round, rows, silent, other faults). Exit 0: no fault; exit 1: faults, a return
             round follows; exit 3 (stop and report): a round that adds no row to the round before, or faults
             after round 3
tiers        join/zone.tsv: the rule sections touched by pass-1 or pass-2, with the decisions they name;
             join/band.tsv: the rule sections touched by pass-3; join/left-out.tsv: every other section with its
             reason line, a rule section its `out` lines (`pass-<n> out ...`), a no-rule section its card line
             (`card ...`); refused while pass-3 holds a silent section or a fault, when its subjects changed after
             the last round, and when pass-3/sections.tsv is not the silent set of pass-1 and pass-2
tier-join    table-0.tsv: zone-1's table, a unit it found nothing in taking zone-2's rows (as table-join), then
             band-1's rows as they are; refused when a band unit is a unit of the zone. The hole round reads it
"""
import hashlib, importlib.util, math, os, re, subprocess, sys

sys.dont_write_bytecode = True

_CC = importlib.util.spec_from_file_location('said_cite_check', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'board', 'cite_check.py'))
CITES = importlib.util.module_from_spec(_CC)  # the one cite check, shared with the feature-reviewer's read
_CC.loader.exec_module(CITES)

INDEX_DIR = 'rule-index'

HEAD = re.compile('^(#{1,6})\\s+(.*)')

CLASSES = ('none', 'against', 'asks', 'same')

MIN_QUOTE = 12

NOT_A_RULE = 'not a rule:'

CONDITION = ('condition not met:', 'condition rests:')

D_KINDS = ('against', 'asks')

TRACE_HEAD = '## Trace of the checked table (written by script)'

GROUND_MAX = 240

FENCE = re.compile('^\\s*(```|~~~)')

TABLE_RULE = re.compile('^\\s*\\|?\\s*:?-{3,}:?\\s*(\\|\\s*:?-{3,}:?\\s*)*\\|?\\s*$')

VERDICTS = ('keep', 'drop', 'ask')

HANDOFF = ''

CITE_MD = re.compile('(?<![\\w./-])([\\w./-]+\\.md):(\\d+)(?!\\d)')

class Refused(Exception):
    pass

def read(path):
    with open(path, encoding='utf-8') as fh:
        return fh.read()

def tsv(path, cols):
    out = []
    for n, l in enumerate(read(path).split('\n'), 1):
        if not l:
            continue
        c = l.split('\t')
        if len(c) != cols:
            raise Refused('refused: %s:%d has %d fields, not %d' % (os.path.basename(path), n, len(c), cols))
        out.append(c)
    return out

def lane_key(lane, key, default=''):
    p = os.path.join(lane, 'CLAUDE.md')
    if os.path.isfile(p):
        m = re.search('^\\s*-?\\s*%s:[ \\t]*(\\S+)' % re.escape(key), read(p), re.M)
        if m:
            return m.group(1).strip('`')
    return default

def docs_root(lane):
    return lane_key(lane, 'SAID.docs-root', 'docs/').strip('/') or 'docs'

def lines_of(lane, path):
    t = read(os.path.join(lane, path))
    ls = t.split('\n')
    return ls[:-1] if t.endswith('\n') else ls

def cut_file(lines, max_lines):
    starts, fence, content, heading = ([], False, False, '')
    heads = {}
    for i, l in enumerate(lines, 1):
        if l.strip().startswith('```'):
            if not starts:
                starts.append(i)
            fence = not fence
            content = True
            continue
        m = None if fence else HEAD.match(l)
        if m:
            if not starts or content:
                starts.append(i)
                content = False
            heads.setdefault(starts[-1], m.group(2).strip())
        elif l.strip():
            if not starts:
                starts.append(i)
            content = True
    if not lines:
        return []
    starts = [1] + starts[1:]
    out = []
    for k, a in enumerate(starts):
        b = starts[k + 1] - 1 if k + 1 < len(starts) else len(lines)
        h = heads.get(a, '')
        while b - a + 1 > max_lines:
            blank = [j for j in range(a + max_lines // 2, a + max_lines) if not lines[j - 1].strip()]
            end = blank[-1] if blank else a + max_lines - 1
            out.append((a, end, h))
            a = end + 1
        out.append((a, b, h))
    return out

ITEM = re.compile('(\\s*)(?:[-*]|\\d+\\.)\\s')

BREAK = re.compile('^\\s*(?:-{3,}|\\*{3,}|_{3,})\\s*$')

def item_span(lines, start):
    m = ITEM.match(lines[start - 1])
    if not m:
        return None
    ind, end = (len(m.group(1)), start)
    for j in range(start, len(lines)):
        l = lines[j]
        if not l.strip():
            continue
        if l.startswith('#') or len(l) - len(l.lstrip(' ')) <= ind:
            break
        end = j + 1
    return end

def fence_end(lines, i):
    j = i + 1
    while j <= len(lines) and (not lines[j - 1].strip().startswith('```')):
        j += 1
    return min(j, len(lines))

def cut_units(lines):
    cores, heads, i, n = ([], [], 1, len(lines))
    while i <= n:
        l = lines[i - 1]
        t = l.strip()
        if t.startswith('```'):
            e = fence_end(lines, i)
            if cores:
                cores[-1] = (cores[-1][0], e, cores[-1][2])
            else:
                cores.append((i, e, heads[-1] if heads else ''))
            i = e + 1
            continue
        m = HEAD.match(l)
        if m:
            heads.append(m.group(2).strip())
        if not t or m or BREAK.match(l):
            i += 1
            continue
        h = heads[-1] if heads else ''
        e = item_span(lines, i)
        if e is not None:
            if sum((1 for j in range(i, e + 1) if lines[j - 1].strip().startswith('```'))) % 2:
                e = fence_end(lines, e)
        elif t.startswith('|'):
            e = i
            while e < n and lines[e].strip().startswith('|'):
                e += 1
        else:
            e = i
            while e < n:
                x = lines[e]
                y = x.strip()
                if not y or HEAD.match(x) or y.startswith(('```', '|')) or ITEM.match(x) or BREAK.match(x):
                    break
                e += 1
        cores.append((i, e, h))
        i = e + 1
    if not cores:
        return [(1, n, heads[0] if heads else '')] if n else []
    out, a = ([], 1)
    for k, (_, e, h) in enumerate(cores):
        out.append((a, n if k == len(cores) - 1 else e, h))
        a = e + 1
    return out

def cut(lane, max_lines=80, unit='item'):
    rows, n = ([], 0)
    for path in rule_files(lane):
        ls = lines_of(lane, path)
        for a, b, h in cut_units(ls) if unit == 'item' else cut_file(ls, max_lines):
            n += 1
            rows.append(('p%d' % n, path, a, b, re.sub('\\s+', ' ', h)[:80] or '-'))
    return rows

def read_pieces(path):
    out = {}
    for c in tsv(path, 5):
        if c[0] in out or not c[2].isdigit() or (not c[3].isdigit()) or (int(c[2]) > int(c[3])):
            raise Refused('refused: pieces.tsv row %s' % c[0])
        out[c[0]] = (c[1], int(c[2]), int(c[3]))
    return out

def deal(lane, pieces, budget=150000):
    files = []
    for p in sorted({v[0] for v in pieces.values()}):
        files.append((os.path.getsize(os.path.join(lane, p)), p))
    big = [f for f in files if f[0] > budget]
    small = [f for f in files if f[0] <= budget]
    load = [0] * max(1, math.ceil(sum((s for s, _ in small)) / budget))
    got = {}
    for s, p in sorted(small, key=lambda x: (-x[0], x[1])):
        i = min(range(len(load)), key=lambda k: (load[k], k))
        load[i] += s
        got[p] = i + 1
    for k, (s, p) in enumerate(sorted(big, key=lambda x: x[1])):
        got[p] = len(load) + k + 1
    count = {}
    for v in pieces.values():
        count[v[0]] = count.get(v[0], 0) + 1
    rows = sorted((('r%d' % got[p], p, s, count[p]) for s, p in files))
    rows.sort(key=lambda r: (int(r[0][1:]), r[1]))
    check_deal(pieces, rows)
    return rows

def check_deal(pieces, rows):
    seen = {}
    for r in rows:
        seen.setdefault(r[1], []).append(r[0])
    for p in sorted({v[0] for v in pieces.values()}):
        if len(seen.get(p, [])) != 1:
            raise Refused('refused: %s is in %d portions' % (p, len(seen.get(p, []))))

def fold(s):
    return re.sub('\\s+', ' ', s).strip()

WITHDRAWN_FILE = 'withdrawn.tsv'

WITHDRAWN_HEAD = '### Rule rows a later reading round withdrew (written by script)'

ROUND = re.compile('^read-(r\\d+)(?:\\.r(\\d+))?\\.tsv$')

def decision_rows(path):
    out = []
    for n, l in enumerate(read(path).split('\n'), 1):
        if not l:
            continue
        c = l.split('\t')
        if len(c) not in (3, 4):
            raise Refused('refused: %s:%d has %d fields, not 3 or 4' % (os.path.basename(path), n, len(c)))
        out.append((c + [None])[:4])
    return out

def coverage(lane, folder, only=None):
    pieces = read_pieces(os.path.join(folder, 'pieces.tsv'))
    decs = {c[0] for c in decision_rows(os.path.join(folder, 'decisions.tsv'))}
    portion = {}
    for c in tsv(os.path.join(folder, 'portions.tsv'), 4):
        portion[c[1]] = c[0]
    check_deal(pieces, [(v, k) for k, v in portion.items()])
    files = []
    for f in sorted(os.listdir(folder)):
        m = ROUND.match(f)
        if m:
            k = int(m.group(2) or 1)
            if k == 1 and m.group(2):
                raise Refused('refused: %s: round 1 has no suffix' % f)
            if only is None or m.group(1) == only:
                files.append((int(m.group(1)[1:]), k, f, m.group(1)))
    files.sort()
    cache, table, good, bad, good_lines, good_kind = ({}, [], set(), [], set(), set())
    for _, k, f, r in files:
        for n, l in enumerate(read(os.path.join(folder, f)).split('\n'), 1):
            if not l.strip():
                continue
            c = l.split('\t')
            why, piece = (None, c[0] if c else '')
            if len(c) != 5:
                why = '%d fields, not 5' % len(c)
            elif piece not in pieces or portion.get(pieces[piece][0]) != r:
                why = 'piece %s is not in portion %s' % (piece, r)
            elif c[1] not in CLASSES:
                why = 'class %s' % c[1]
            elif c[1] == 'none':
                if c[2:] != ['-', '-', '-']:
                    why = 'a none row carries a decision, rule or quote'
            else:
                path, a, b = pieces[piece]
                m = re.match('^(.+):(\\d+)$', c[3])
                if c[2] not in decs:
                    why = 'decision %s unknown' % c[2]
                elif not m or m.group(1) != path or (not a <= int(m.group(2)) <= b):
                    why = 'rule %s is not a line of piece %s (%s:%d-%d)' % (c[3], piece, path, a, b)
                else:
                    if path not in cache:
                        cache[path] = lines_of(lane, path)
                    q = fold(c[4])
                    if len(q) < MIN_QUOTE or q not in fold(cache[path][int(m.group(2)) - 1]):
                        why = 'quote not on %s' % c[3]
            if why:
                line = c[3] if len(c) == 5 and re.match('^.+:\\d+$', c[3]) else None
                bad.append((r, k, piece, '%s:%d' % (f, n), why, line, c[4] if len(c) == 5 else ''))
            else:
                good.add((r, k, piece))
                good_kind.add((r, k, piece, c[1] != 'none'))
                if c[1] != 'none':
                    good_lines.add((r, k, c[3]))
                table.append((r, piece, c[1], c[2], c[3], c[4]))
    gaps = []
    marked = set()
    mp = os.path.join(folder, 'marked.tsv')
    if os.path.isfile(mp):
        for c in tsv(mp, 2):
            if c[0] not in pieces:
                raise Refused('refused: marked unit %s is not a unit of pieces.tsv' % c[0])
            marked.add(c[0])
    if only is not None and only not in portion.values():
        raise Refused('refused: portion %s is not in portions.tsv' % only)
    for pid, (path, a, b) in pieces.items():
        if only is not None and portion[path] != only:
            continue
        if pid not in marked and (not any((g[2] == pid for g in good))):
            gaps.append((portion[path], pid, 'no good row for %s:%d-%d' % (path, a, b)))
    withdrawn = []
    for r, k, piece, where, why, line, quote in bad:
        later = {g[2] for g in good if g[0] == r and g[1] > k}
        units = unit_of(pieces, line, quote, lane, cache) if line is not None else set()
        mine = ({piece} if piece in pieces else set()) | units
        if piece in pieces:
            closed = bool(mine & later)
        else:
            closed = all((p in later for p, v in pieces.items() if portion.get(v[0]) == r))
        if not closed:
            gaps.append((r, where, why))
            continue
        c = read(os.path.join(folder, where.rsplit(':', 1)[0])).split('\n')[int(where.rsplit(':', 1)[1]) - 1].split('\t')
        if len(c) == 5 and c[1] in CLASSES and (c[1] != 'none') and (not any((g[0] == r and g[1] > k and g[3] and (g[2] in mine) for g in good_kind))):
            withdrawn.append((','.join(sorted(mine)) or '-', c[1], c[2], c[3], verbatim(c[4]), '%s round %d' % (r, k)))
    write(os.path.join(folder, 'table.tsv'), table)
    write(os.path.join(folder, 'gaps.tsv'), gaps)
    write(os.path.join(folder, WITHDRAWN_FILE), withdrawn)
    return (len(table), len(gaps), len(bad))

def unit_of(pieces, cite, quote, lane, cache):
    m = re.match('^(.+):(\\d+)$', cite)
    if not m:
        return set()
    path, ln = (m.group(1), int(m.group(2)))
    lines = {ln}
    if quote is not None and len(fold(quote)) >= MIN_QUOTE and os.path.isfile(os.path.join(lane, path)):
        if path not in cache:
            cache[path] = lines_of(lane, path)
        lines |= {i for i, l in enumerate(cache[path], 1) if fold(quote) in fold(l)}
    return {pid for pid, (p, a, b) in pieces.items() if p == path and any((a <= x <= b for x in lines))}

def read_table(folder):
    out = []
    for c in tsv(os.path.join(folder, 'table.tsv'), 6):
        if c[2] not in CLASSES:
            raise Refused('refused: table.tsv class %s' % c[2])
        out.append(c)
    return out

def quoted(reason, line):
    r, l = (fold(reason), fold(line))
    return any((r[i:i + MIN_QUOTE] in l for i in range(0, len(r) - MIN_QUOTE + 1)))

def look_lines(lp):
    out = []
    for n, l in enumerate(read(lp).split('\n'), 1):
        if not l:
            continue
        c = l.split('\t')
        if len(c) not in (5, 6):
            raise Refused('refused: look.tsv:%d has %d fields, not 5 or 6' % (n, len(c)))
        out.append((n, c[:5], c[5] if len(c) == 6 else None))
    return out

def decision_ids(folder):
    dp = os.path.join(folder, 'decisions.tsv')
    return {l.split('\t')[0] for l in read(dp).split('\n') if l} if os.path.isfile(dp) else set()

def recited(folder):
    ids, out = (decision_ids(folder), {})
    lp = os.path.join(folder, 'look.tsv')
    if os.path.isfile(lp):
        for n, c, x in look_lines(lp):
            if x is not None:
                if x not in ids or c[3] != 'keep' or x == c[1]:
                    raise Refused('refused: look.tsv:%d names decision %s, not a re-cite of a keep to a known decision' % (n, x))
                out[c[0], c[1], c[2]] = x
    return out

PART_PAIRS = 26
QUESTION_PART = 70  # rows a question part: one part a look
SUBJECT_FILE = 'subject-pairs.tsv'
SUBJECT_MIN = 5  # shared words that make one subject
SUBJECT_STOP = set("""this that with from when must never always should only each every rule rules file files line lines section
feature features component components data table tables list lists page pages the and for not are use used will have been
into than then them they what which your more also same""".split())

def pair_rows(t, keep=None):
    ag = [(c[1], c[3], c[4]) for c in t if c[2] == 'against']
    ag = sorted(set(ag), key=ag.index)
    pr = []
    for d in sorted({c[3] for c in t if c[2] == 'against'}, key=lambda x: int(x[1:])):
        for s in [c for c in t if c[3] == d and c[2] == 'same']:
            for a in [c for c in t if c[3] == d and c[2] == 'against' and (c[1] != s[1])]:
                if (d, s[4], a[4]) not in pr:
                    pr.append((d, s[4], a[4]))
    if keep is not None:
        pr = [p for p in pr if p in keep]
    return (ag, pr)

def keep_of(folder):
    p = os.path.join(folder, SUBJECT_FILE)
    return {tuple(c) for c in tsv(p, 3)} if os.path.isfile(p) else None

def subject_words(s):
    return set(re.findall('[A-Za-z][A-Za-z-]{3,}', s.lower())) - SUBJECT_STOP

def subject_pairs(lane, run):
    """subject-pairs.tsv: a pair is kept when its two sections share SUBJECT_MIN words; a section's text is the lines of
    its items in the lane file of its first item"""
    import csv
    _, pr = pair_rows(read_table(run))
    with open(os.path.join(run, 'pieces.tsv'), encoding='utf-8') as fh:
        pieces = {r[0]: (r[1], int(r[2]), int(r[3])) for r in csv.reader(fh, delimiter='\t') if r}
    with open(os.path.join(run, 'sec', 'section-items.tsv'), encoding='utf-8') as fh:
        sec_of = {r[1]: r[0] for r in csv.reader(fh, delimiter='\t') if r}
    cache = {}
    def sec(ref):
        f, l = ref.rsplit(':', 1)
        for p, (pf, a, b) in pieces.items():
            if pf == f and a <= int(l) <= b:
                return sec_of.get(p)
        return None
    def text(s):
        if s not in cache:
            ps = [p for p, x in sec_of.items() if x == s and p in pieces]
            if s is None or not ps:
                raise Refused('refused: a pair line is in no section of pieces.tsv')
            f = pieces[ps[0]][0]
            a, b = min(pieces[p][1] for p in ps), max(pieces[p][2] for p in ps)
            cache[s] = subject_words('\n'.join(read(os.path.join(lane, f)).split('\n')[a - 1:b]))
        return cache[s]
    kept = [p for p in pr if len(text(sec(p[1])) & text(sec(p[2]))) >= SUBJECT_MIN]
    write(os.path.join(run, SUBJECT_FILE), kept)
    return (len(pr), len(kept))

def pair_parts(t, cap=PART_PAIRS, keep=None):
    ag, pr = pair_rows(t, keep)
    items = []
    for d in sorted({k[1] for k in ag}, key=lambda x: int(x[1:])):
        rules = []
        for k in ag:
            if k[1] == d and k[2] not in rules:
                rules.append(k[2])
        groups = [([k for k in ag if k[1] == d and k[2] == r], [p for p in pr if p[0] == d and p[2] == r]) for r in rules]
        if sum([len(g[1]) for g in groups]) <= cap:
            items.append(([k for k in ag if k[1] == d], [p for p in pr if p[0] == d]))
        else:
            items += groups
    parts, cur = ([], ([], []))
    for ks, ps in items:
        if (cur[0] or cur[1]) and len(cur[1]) + len(ps) > cap:
            parts.append(cur)
            cur = ([], [])
        cur = (cur[0] + ks, cur[1] + ps)
    if cur[0]:
        parts.append(cur)
    return [(sorted(a, key=ag.index), sorted(p, key=pr.index)) for a, p in parts]

def norm_reason(s):
    return ' '.join(s.lower().split())

def deal_pairs(folder, out, cap=PART_PAIRS):
    if os.path.exists(out):
        raise Refused('refused: %s exists; name a fresh folder' % out)
    t = read_table(folder)
    parts = pair_parts(t, cap, keep_of(folder))
    os.makedirs(out)
    res = []
    for k, (ks, ps) in enumerate(parts, 1):
        pd = os.path.join(out, 'part-%d' % k)
        os.makedirs(pd)
        ds = {x[1] for x in ks}
        kk = set(ks)
        write(os.path.join(pd, 'table.tsv'), [c for c in t if c[3] in ds and (c[2] != 'against' or (c[1], c[3], c[4]) in kk)])
        for f in ('decisions.tsv', 'decision-pairs.tsv', 'pieces.tsv', SUBJECT_FILE):
            if os.path.isfile(os.path.join(folder, f)):
                with open(os.path.join(folder, f), 'rb') as a, open(os.path.join(pd, f), 'wb') as b:
                    b.write(a.read())
        n, p, _ = pairs(pd)
        if (n, p) != (len(ks), len(ps)):
            raise Refused('refused: part-%d checks %d of %d, pairs %d of %d' % (k, n, len(ks), p, len(ps)))
        res.append(('part-%d' % k, sorted(ds, key=lambda x: int(x[1:])), n, p))
    return res

def merge_pairs(folder, parts_dir):
    for f in ('look.tsv', 'pairs-look.tsv'):
        if os.path.exists(os.path.join(folder, f)):
            raise Refused('refused: %s already has %s' % (folder, f))
    names = sorted((x for x in os.listdir(parts_dir) if re.match('part-\\d+$', x)), key=lambda x: int(x[5:]))
    if not names:
        raise Refused('refused: %s holds no part folder' % parts_dir)
    look, pl = ([], [])
    for x in names:
        pd = os.path.join(parts_dir, x)
        if not os.path.isfile(os.path.join(pd, 'look.tsv')):
            raise Refused('refused: %s has no look.tsv' % x)
        look += [l for l in open(os.path.join(pd, 'look.tsv'), encoding='utf-8').read().split('\n') if l.strip()]
        pp = os.path.join(pd, 'pairs-look.tsv')
        if os.path.isfile(pp):
            pl += [l for l in open(pp, encoding='utf-8').read().split('\n') if l.strip()]
        elif os.path.getsize(os.path.join(pd, 'pairs.tsv')) > 0:
            raise Refused('refused: %s has pairs and no pairs-look.tsv' % x)
    for f, rows in (('look.tsv', look), ('pairs-look.tsv', pl)):
        with open(os.path.join(folder, f), 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(''.join((l + '\n' for l in rows)))
    return (len(names), len(look), len(pl))

def repeats(t, look_rows, pair_rows_, keep=None):
    where = {}
    for k, (ks, ps) in enumerate(pair_parts(t, keep=keep), 1):
        where.update({x: k for x in ks})
        where.update({('p',) + x: k for x in ps})
    n = {}
    for key, reason in [(tuple(c[:3]), c[4]) for c in look_rows] + [(('p',) + tuple(c[:3]), c[4]) for c in pair_rows_]:
        if key in where:
            n.setdefault((where[key], norm_reason(reason)), []).append(key)
    return ['reason on more than 3 lines of part %d (%d lines): %s' % (k, len(v), r[:80]) for (k, r), v in sorted(n.items()) if len(v) > 3]

def pairs(folder, lane=None):
    t = read_table(folder)
    keep = keep_of(folder)
    ag, pr = pair_rows(t, keep)
    write(os.path.join(folder, 'checks.tsv'), ag)
    write(os.path.join(folder, 'pairs.tsv'), pr)
    lp = os.path.join(folder, 'look.tsv')
    faults = []
    if not os.path.isfile(lp):
        return (len(ag), len(pr), faults)
    rules = set(rule_files(lane)) if lane else None
    seen, ids = ({}, decision_ids(folder))
    for n, c, x in look_lines(lp):
        k = (c[0], c[1], c[2])
        if x is not None:
            if c[3] != 'keep':
                faults.append('look.tsv:%d names decision %s on a %s: only a keep is re-cited' % (n, x, c[3]))
            elif x == c[1]:
                faults.append('look.tsv:%d names its own decision %s' % (n, x))
            elif x not in ids:
                faults.append('look.tsv:%d names decision %s, not in decisions.tsv' % (n, x))
        seen[k] = seen.get(k, 0) + 1
        if k not in ag:
            faults.append('look.tsv:%d names no against row: %s %s %s' % ((n,) + k))
        if c[3] == 'keep':
            if len(c[4].split()) < 3:
                faults.append('look.tsv:%d keep reason under 3 words' % n)
        elif c[3] == 'drop':
            m = re.search('(?<![\\w./-])([\\w./-]+\\.md):(\\d+)(?!\\d)', c[4])
            if rules is None:
                faults.append('look.tsv:%d drop not checked: no --lane' % n)
            elif c[4].startswith(NOT_A_RULE):
                if len(c[4][len(NOT_A_RULE):].split()) < 3:
                    faults.append('look.tsv:%d not a rule: says under 3 words what the line is' % n)
            elif m and '%s:%s' % (m.group(1), int(m.group(2))) == c[2] and (not c[4].startswith(CONDITION[0])):
                faults.append('look.tsv:%d drop names its own rule line %s' % (n, c[2]))
            elif not m or m.group(1) not in rules:
                faults.append('look.tsv:%d drop names no rule line of the lane' % n)
            else:
                ls = lines_of(lane, m.group(1))
                i = int(m.group(2))
                if not 1 <= i <= len(ls) or not quoted(c[4][m.end():], ls[i - 1]):
                    faults.append('look.tsv:%d drop quotes no %d characters of %s' % (n, MIN_QUOTE, m.group(0)))
        elif c[3] == 'ask':
            if rules is None:
                faults.append('look.tsv:%d ask not checked: no --lane' % n)
                continue
            ex = exception(c[4], rules)
            if ex is None:
                faults.append('look.tsv:%d ask names no exception line of the lane or the handoff' % n)
            elif ex[0] == HANDOFF:
                faults.append("look.tsv:%d ask cites a handoff line: the handoff's own reason is keep" % n)
            elif '%s:%d' % (ex[0], ex[1]) == c[2] and (not c[4].startswith(CONDITION[1])):
                faults.append('look.tsv:%d ask names its own rule line %s' % (n, c[2]))
            else:
                ls = lines_of(lane, ex[0])
                if not 1 <= ex[1] <= len(ls) or not quoted(c[4][ex[2]:], ls[ex[1] - 1]):
                    faults.append('look.tsv:%d ask quotes no %d characters of %s:%d' % (n, MIN_QUOTE, ex[0], ex[1]))
        else:
            faults.append('look.tsv:%d verdict %s' % (n, c[3]))
    for k, v in seen.items():
        if v > 1:
            faults.append('look.tsv: %d lines for %s %s %s' % ((v,) + k))
    faults += ['no check: %s %s %s' % a for a in ag if a not in seen]
    pp = os.path.join(folder, 'pairs-look.tsv')
    if pr and (not os.path.isfile(pp)):
        faults.append('pairs-look.tsv absent, pairs %d' % len(pr))
    elif os.path.isfile(pp):
        got = {}
        for n, c in enumerate(tsv(pp, 5), 1):
            k = (c[0], c[1], c[2])
            got[k] = got.get(k, 0) + 1
            if k not in pr:
                faults.append('pairs-look.tsv:%d names no pair: %s %s %s' % ((n,) + k))
            if c[3] not in ('agree', 'disagree'):
                faults.append('pairs-look.tsv:%d verdict %s' % (n, c[3]))
            if len(c[4].split()) < 3:
                faults.append('pairs-look.tsv:%d reason under 3 words' % n)
        faults += ['pairs-look.tsv: %d lines for %s %s %s' % ((v,) + k) for k, v in got.items() if v > 1]
        faults += ['no pair check: %s %s %s' % k for k in pr if k not in got]
    pl_rows = tsv(pp, 5) if os.path.isfile(pp) else []
    faults += repeats(t, [c for _, c, _ in look_lines(lp)], pl_rows, keep)
    return (len(ag), len(pr), faults)

def exception(reason, rules=None):
    for m in CITE_MD.finditer(reason):
        p = m.group(1)
        if HANDOFF and os.path.basename(p) == os.path.basename(HANDOFF) and (p == os.path.basename(HANDOFF) or p.endswith(HANDOFF)):
            return (HANDOFF, int(m.group(2)), m.end())
        if rules is None or p in rules:
            return (p, int(m.group(2)), m.end())
    return None

def names(text, path, line):
    return any((re.search('(?<![\\w.-])%s:%d(?!\\d)' % (re.escape(x), line), text) for x in (path, os.path.basename(path))))

def ground(t):
    t = ' '.join(''.join((ch if ch >= ' ' and ch != '\x7f' else ' ' for ch in t)).split())
    return t if len(t) <= GROUND_MAX else t[:GROUND_MAX - 3] + '...'

JOIN_HEAD, JOIN_B = ('two looks: A ', ' || B ')

def look_join(pa, pb):
    looks = []
    for p in (pa, pb):
        d = {}
        for n, c, x in look_lines(p):
            if c[3] not in VERDICTS:
                raise Refused('refused: %s:%d verdict %s' % (os.path.basename(p), n, c[3]))
            k = (c[0], c[1], c[2])
            if k in d:
                raise Refused('refused: %s:%d row twice: %s' % (os.path.basename(p), n, ' '.join(k)))
            d[k] = (c, x)
        looks.append(d)
    a, b = looks
    odd = sorted(set(a) ^ set(b))
    if odd:
        raise Refused('refused: row in one look only: ' + '; '.join((' '.join(k) for k in odd)))
    out = []
    for k in a:
        (ca, xa), (cb, xb) = (a[k], b[k])
        va, vb = (ca[3], cb[3])
        why = '%s%s: %s%s%s: %s' % (JOIN_HEAD, va, ' '.join(ca[4].split()), JOIN_B, vb, ' '.join(cb[4].split()))
        if va == vb == 'keep':
            named = {x for x in (xa, xb) if x is not None}
            if len(named) > 1:
                out.append(list(k) + ['split', why + ' (the looks name different decisions: %s)' % ', '.join(sorted(named))])
            else:
                out.append(list(k) + ['keep', why] + sorted(named))
        elif va == vb:
            out.append(list(k) + [va, why])
        else:
            out.append(list(k) + ['split', why])
    return out

SPLIT_FILE = 'split.tsv'

SPLIT_HEAD = '### Questions the two looks split on (written by script)'

def split_rows(folder):
    p = os.path.join(folder, SPLIT_FILE)
    if not os.path.isfile(p):
        return []
    out = []
    for c in tsv(p, 5):
        if c[3] != 'split' or not c[4].startswith(JOIN_HEAD) or JOIN_B not in c[4]:
            raise Refused('refused: %s row %s %s %s is not a split row of look-join' % (SPLIT_FILE, c[0], c[1], c[2]))
        out.append(c)
    return out

def verbatim(t):
    return ' '.join(''.join((ch if ch >= ' ' and ch != '\x7f' else ' ' for ch in t)).split())

def join_ground(t):
    if not t.startswith(JOIN_HEAD) or JOIN_B not in t:
        return ground(t)
    a, _, b = t[len(JOIN_HEAD):].partition(JOIN_B)
    half = (GROUND_MAX - 10) // 2
    cut = lambda x: (lambda g: g if len(g) <= half else g[:half - 3] + '...')(' '.join(''.join((ch if ch >= ' ' and ch != '\x7f' else ' ' for ch in x)).split()))
    return 'A %s; B %s' % (cut(a), cut(b))

def trace_text(folder):
    t = read_table(folder)
    look = {}
    lp = os.path.join(folder, 'look.tsv')
    if os.path.isfile(lp):
        for _, c, _x in look_lines(lp):
            if c[3] not in VERDICTS:
                raise Refused('refused: look.tsv verdict %s' % c[3])
            look[c[0], c[1], c[2]] = (c[3], c[4])
    rc = recited(folder)
    sp = split_rows(folder)
    sk = {(c[0], c[1], c[2]) for c in sp}
    out, seen = ([], set())
    for c in t:
        if c[2] == 'none' or (c[1], c[3], c[4]) in sk:
            continue
        v, d = ('', c[3])
        lc = look.get((c[1], c[3], c[4]))
        if c[2] == 'asks' and lc is not None and lc[0] == 'ask' and lc[1].startswith(CONFIRM_NOTE):
            c = c[:2] + ['against'] + c[3:]
            v = ', ask: %s' % ground(lc[1])
        elif c[2] == 'against':
            lv = look.get((c[1], c[3], c[4]))
            v = ', not looked at' if lv is None else ', drop: %s' % join_ground(lv[1]) if lv[0] == 'drop' else ', %s' % lv[0]
            if lv is not None and lv[0] == 'ask' and lv[1].startswith(JOIN_HEAD):
                v += ': %s' % join_ground(lv[1])
            if (c[1], c[3], c[4]) in rc:
                d = rc[c[1], c[3], c[4]]
                v += ' (re-cited from %s)' % c[3]
        line = '- %s `%s` %s%s' % (d, c[4], c[2], v)
        if line not in seen:
            seen.add(line)
            out.append(line)
    tail = ''
    if sp:
        tail = "\n%s\n\nThe two second looks did not agree on these conflicts: each is an open question for the operator, with both looks' verdicts and grounds as written. Questions %d.\n\n%s" % (SPLIT_HEAD, len(sp), ''.join(('- %s `%s` %s\n' % (c[1], c[2], verbatim(c[4])) for c in sp)))
    wp = os.path.join(folder, WITHDRAWN_FILE)
    wd = [l.split('\t') for l in read(wp).split('\n') if l.strip()] if os.path.isfile(wp) else []
    if wd:
        tail += "\n%s\n\nA reader's first-round row named a rule; its return round read the same unit and gave it no rule. The table holds the later reading; each withdrawn row is listed here. Rows %d.\n\n%s" % (WITHDRAWN_HEAD, len(wd), ''.join(('- %s %s, unit %s: %s `%s` %s "%s"\n' % (c[0], c[6], c[1], c[3], c[4], c[2], verbatim(c[5])) for c in wd)))
    tail += audit_text(folder)
    return "%s\n\nEvery row of the checked table other than `none`: decision, rule line, class, and for a conflict the second look's verdict (a drop with its ground). Rows %d.\n\n%s%s" % (TRACE_HEAD, len(out), ''.join((l + '\n' for l in out)), tail) + mounts_block(folder)

def lists_text(folder):
    out = []
    for dest, head, say in (('rules', RULES_HEAD, 'No question look found a choice here and the rule settles it; the handoff does not state it: each is a rule the work follows, not a question for the operator. Rules %d.'), ('same', SAME_HEAD, 'No question look found a choice here and the handoff already does what the rule asks: each is a rule the handoff follows, not a question for the operator. Rules %d.'), ('notbear', NOTBEAR_HEAD, 'Both question looks read the rule and found that it does not bear on the decision, each with its ground: not a rule the work keeps, not a question. Rows %d.')):
        qa = [c for c in qjoin_rows(folder) if c[3] == dest]
        if qa:
            out.append('%s\n\n%s\n\n%s' % (head, say % len(qa), ''.join(('- %s `%s` %s\n' % (c[1], c[2], verbatim(c[4])) for c in qa))))
    framed = {f[0] for f in frame_list(folder)}
    qa = [c for c in qjoin_rows(folder) if c[3] == 'onelook' and c[1] not in framed]
    if qa:
        out.append('%s\n\n%s\n\n%s' % (ONELOOK_HEAD, ONELOOK_SAY % len(qa), ''.join(('- %s `%s` %s\n' % (c[1], c[2], verbatim(c[4])) for c in qa))))
    return '\n'.join(out)

def d_heading(lines):
    at = [i for i, l in enumerate(lines) if D_HEAD.match(l)]
    if len(at) != 1:
        raise Refused('refused: the draft has %d lines that begin `## D.`; section D needs exactly one heading line that begins `## D.` so the script can write the rules lists directly before it' % len(at))
    return at[0]

MARKS = ('open', 'stated')

ONELOOK_HEAD = "### One look of two saw an owner's choice (not asked) (written by script)"

ONELOOK_SAY = "One question look found an owner's choice here and the other did not, and the decision has no question frame: not asked, each with both looks' grounds as written. Rows %d."

FRAMES_HEAD = '### Questions by decision (frames written by script)'

FRAMES_END = 'End of the question frames (written by script).'

FRAMES_FILE = 'frames.md'

FRAME_LINE = re.compile('^#### Question frame (D\\d+) \\((open|stated)\\)$')

QUESTION = 'Question:'

def frame_list(folder):
    decs = decision_rows(os.path.join(folder, 'decisions.tsv'))
    if all((c[3] is None for c in decs)):
        return []
    if any((c[3] not in MARKS for c in decs)):
        raise Refused('refused: decisions.tsv: a row without the mark `open` or `stated`')
    qj = qjoin_rows(folder)
    ta = os.path.join(folder, 'table-all.tsv')
    full = tsv(ta, 6) if os.path.isfile(ta) else read_table(folder)
    looked = {(c[1], c[2]) for c in qj}
    bare = [c for c in read_table(folder) if c[2] == 'asks' and (c[3], c[4]) not in looked]
    moved = confirm_moved(folder)
    out = []
    for d, ranges, text, m in decs:
        rows = []
        for c in qj:
            if c[1] == d and c[3] in ('question', 'onelook'):
                a, _, b = c[4][len(JOIN_HEAD):].partition(JOIN_B)
                r = (c[2], a.split(' ', 1)[0], b.split(' ', 1)[0], c[3])
                if r not in rows:
                    rows.append(r)
        for c in bare:
            if c[3] == d and (c[1], c[3], c[4]) in moved:
                r = (c[4], CONFIRM_NOTE, moved[c[1], c[3], c[4]], 'question')
                if r not in rows:
                    rows.append(r)
            elif c[3] == d and (c[4], '-', '-', 'question') not in rows:
                rows.append((c[4], '-', '-', 'question'))
        if m == 'stated' and (not any((r[3] == 'question' for r in rows))):
            continue
        cites = []
        for c in full:
            if c[3] == d and c[2] != 'none' and (c[4] not in cites):
                cites.append(c[4])
        out.append((d, m, text, ranges, rows, cites))
    return out

def frames_text(folder, words=None):
    words = words or {}
    fl = frame_list(folder)
    if not fl:
        return ''
    out = []
    for d, m, text, ranges, rows, cites in fl:
        ls = ['#### Question frame %s (%s)' % (d, m), '- decision: %s (handoff lines %s)' % (verbatim(text), ranges)]
        ls += ['- question row `%s`: %s%s' % (r[0], r[1], verbatim(r[2])) if r[1] == CONFIRM_NOTE else '- %s `%s`: look A %s, look B %s' % ('question row' if r[3] == 'question' else 'one look row', r[0], r[1], r[2]) for r in rows]
        ls.append('- rules its rows cite: %s' % (', '.join(('`%s`' % x for x in cites)) or 'none'))
        ls.append('%s %s' % (QUESTION, words[d]) if words.get(d) else QUESTION)
        out.append('\n'.join(ls))
    say = "One frame a decision the handoff leaves open, and one a stated decision both question looks found an owner's choice on; a row only one look found a choice on is named in its decision's frame as a one look row; the drafter writes the question after `Question:`. Frames %d." % len(fl)
    return '%s\n\n%s\n\n%s\n\n%s' % (FRAMES_HEAD, say, '\n\n'.join(out), FRAMES_END)

def frames_in(lines):
    at = [i for i, l in enumerate(lines) if l == FRAMES_HEAD]
    if not at:
        return None
    end = [i for i, l in enumerate(lines) if l == FRAMES_END and i > at[0]]
    if len(at) > 1 or not end:
        raise Refused('refused: the draft holds %d frame headings and %d ends; section D needs one frames block' % (len(at), len(end)))
    return (at[0], end[0])

def frame_words(lines, span):
    out, cur = ({}, None)
    for l in lines[span[0]:span[1]]:
        m = FRAME_LINE.match(l)
        if m:
            cur = m.group(1)
        elif cur and l.startswith(QUESTION) and (cur not in out):
            out[cur] = ' '.join(l[len(QUESTION):].split())
    return out

def place_frames(body, folder):
    ft = frames_text(folder)
    ls = body.split('\n')
    span = frames_in(ls)
    if not ft:
        return body
    words = frame_words(ls, span) if span else {}
    if span:
        ls = ls[:span[0]] + ls[span[1] + 1:]
        while span[0] < len(ls) and span[0] > 0 and (not ls[span[0]].strip()) and (not ls[span[0] - 1].strip()):
            del ls[span[0]]
    d = d_heading(ls)
    rest = ls[d + 1:]
    while rest and (not rest[0].strip()):
        rest.pop(0)
    return '\n'.join(ls[:d + 1] + [''] + frames_text(folder, words).split('\n') + [''] + rest)

def place_lists(body, folder):
    ls = body.split('\n')
    d = d_heading(ls)
    heads = [i for i, l in enumerate(ls[:d]) if l in (RULES_HEAD, SAME_HEAD, NOTBEAR_HEAD, ONELOOK_HEAD)]
    a = heads[0] if heads else d
    pre = ls[:a]
    while pre and (not pre[-1].strip()):
        pre.pop()
    lt = lists_text(folder)
    return '\n'.join(pre + [''] + ([lt] if lt else []) + ls[d:])

def split_trace(text):
    ls = text.split('\n')
    at = [i for i, l in enumerate(ls) if l == TRACE_HEAD]
    if not at:
        return (text, None, 0)
    return ('\n'.join(ls[:at[0]]), '\n'.join(ls[at[0]:]), len(at))

def trace(folder):
    dp = os.path.join(folder, 'scope.md')
    if not os.path.isfile(dp):
        raise Refused('refused: no scope.md in %s' % folder)
    body, _, _ = split_trace(read(dp))
    body = place_lists(body, folder)
    body = place_frames(body, folder)
    tr = trace_text(folder)
    with open(dp, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(body.rstrip('\n') + '\n\n' + tr)
    return tr.count('\n- ')

CITE_ITEM = re.compile('^- \\*\\*(C\\d+)\\*\\*')
HINT_LINE = re.compile("^\\s*Hint \\(the drafter's reading\\):")


def rule_docs_read(folder):
    """the rule documents the manifest of the folder names under `Files read:`; none without a manifest"""
    p = os.path.join(folder, MANIFEST_FILE)
    m = re.search('(?m)^Files read: (.*)$', read(p)) if os.path.isfile(p) else None
    return set(re.findall('`([^`]+)`', m.group(1))) if m else set()


def cite_hint_faults(dpart, docs, amb):
    """the faults of the cite items of section D (a line that begins `- **C<k>**`, up to the next such line or a
    blank line): an item with no `Hint` line naming `no single item` or a `path:line` of a rule document; an item of
    a cite in `amb` (state ambiguous) whose `Hint` line names fewer than two such `path:line`, without `no single item`;
    an item with no `Question:` line"""
    out, cur, best, ask = [], None, -1, False
    for l in dpart.split('\n') + ['']:
        m = CITE_ITEM.match(l)
        if m or not l.strip():
            if cur and best < 1:
                out.append('cite without hint: %s' % cur)
            elif cur and cur in amb and best < 2:
                out.append('cite hint names one item: %s' % cur)
            if cur and not ask:
                out.append('cite without question: %s' % cur)
            cur, best, ask = (m.group(1), -1, False) if m else (None, -1, False)
            continue
        if cur and l.lstrip().startswith('Question:'):
            ask = True
        if cur and HINT_LINE.match(l):
            n = len({p for p in re.findall('([\\w./-]+\\.md:\\d+)', l)
                     if p.rsplit(':', 1)[0] in docs or any(d.endswith('/' + p.rsplit(':', 1)[0]) for d in docs)})
            best = max(best, 2 if 'no single item' in l else n)
    return out


def carried(folder, d_items=False):
    dp = os.path.join(folder, 'scope.md')
    if not os.path.isfile(dp):
        raise Refused('refused: no scope.md in %s' % folder)
    t = read_table(folder)
    drop, asked = (set(), {})
    lp = os.path.join(folder, 'look.tsv')
    if os.path.isfile(lp):
        for _, c, _x in look_lines(lp):
            if c[3] not in VERDICTS:
                raise Refused('refused: look.tsv verdict %s' % c[3])
            if c[3] == 'drop':
                drop.add((c[0], c[1], c[2]))
            elif c[3] == 'ask':
                ex = exception(c[4])
                asked[c[0], c[1], c[2]] = (os.path.basename(ex[0]), ex[1]) if ex else None
    text = read(dp)
    body, tr, heads = split_trace(text)
    lost = []
    want = trace_text(folder)
    if tr is None:
        lost.append('no trace section: run the trace command')
    elif heads > 1:
        lost.append('trace heading %d times' % heads)
    elif tr != want:
        lost.append('trace section differs from what the trace command writes')
    try:
        if place_lists(body, folder) != body:
            lost.append('the rules lists before section D differ from what the trace command writes')
    except Refused as e:
        lost.append(str(e))
    fl = frame_list(folder)
    if fl:
        ls = body.split('\n')
        try:
            span = frames_in(ls)
        except Refused as e:
            span = None
            lost.append(str(e))
        have = [FRAME_LINE.match(l).group(1) for l in ls[span[0]:span[1]] if FRAME_LINE.match(l)] if span else []
        owe = [f[0] for f in fl]
        lost += ['frame dropped: %s' % x for x in owe if x not in have]
        lost += ['frame added: %s' % x for x in have if x not in owe]
        lost += ['frame twice: %s' % x for x in sorted(set(have)) if have.count(x) > 1]
        words = frame_words(ls, span) if span else {}
        lost += ['frame %s: no question words after `Question:`' % x for x in owe if x in have and len(words.get(x, '').split()) < 3]
        try:
            if span and place_frames(body, folder) != body:
                lost.append('the question frames differ from what the trace command writes')
        except Refused as e:
            lost.append(str(e))
    cited = want.count('\n- ') if not lost else 0
    pp = os.path.join(folder, 'pairs-look.tsv')
    if os.path.isfile(pp):
        for c in tsv(pp, 5):
            if c[3] == 'disagree' and (not all((names(body, *x.rsplit(':', 1)[:1], int(x.rsplit(':', 1)[1])) for x in (c[1], c[2])))):
                lost.append('disagree pair not carried: %s %s %s' % (c[0], c[1], c[2]))
    dn = None
    if d_items:
        ip = os.path.join(folder, 'd-items.tsv')
        if not os.path.isfile(ip):
            raise Refused('refused: no d-items.tsv in %s' % folder)
        items = []
        for l in read(ip).split('\n'):
            if not l.strip():
                continue
            c = l.split('\t')
            ok = re.match('^D\\d+$', c[0]) and len(c) >= 3 and re.match('^.+:\\d+$', c[1])
            if ok and len(c) == 3 and (c[2] in D_KINDS):
                items.append((c[0], c[1], c[2]))
            elif ok and len(c) == 4 and (c[2] == 'question') and re.match('^.+:\\d+$', c[3]):
                p, ln = c[3].rsplit(':', 1)
                items.append((c[0], c[1], 'question %s:%d' % (os.path.basename(p), int(ln))))
            else:
                raise Refused('refused: d-items.tsv row %s' % '\t'.join(c)[:80])

        def kind(c):
            k = (c[1], c[3], c[4])
            if c[2] == 'against' and k in asked:
                return 'question %s:%d' % asked[k] if asked[k] else 'question -'
            return c[2]
        rc = recited(folder)
        dec = lambda c: rc.get((c[1], c[3], c[4]), c[3])
        rows_all = {(dec(c), c[4], kind(c)) for c in t if c[2] != 'none'}
        sk = {(c[0], c[1], c[2]) for c in split_rows(folder)}
        need = {(dec(c), c[4], kind(c)) for c in t if c[2] in D_KINDS and (c[1], c[3], c[4]) not in drop | sk and (not (fl and c[2] == 'asks'))}
        for k in sorted(set(items)):
            if items.count(k) > 1:
                lost.append('d item twice: %s %s %s' % k)
        for k in items:
            if k not in rows_all:
                lost.append('d item names no row: %s %s %s' % k)
            elif not names(body, k[1].rsplit(':', 1)[0], int(k[1].rsplit(':', 1)[1])):
                lost.append('d item not named in the draft: %s %s' % (k[0], k[1]))
        lost += ['no d item: %s %s %s' % k for k in sorted(need) if k not in items]
        dn = (len(items), sum((1 for k in items if k[2] == 'against')), sum((1 for k in items if k[2] == 'asks')), sum((1 for k in items if k[2].startswith('question'))))
    for fid in audit_ids(folder):
        if not re.search('(?<![\\w-])%s(?!\\d)' % re.escape(fid), body):
            lost.append('audit finding not named in the draft: %s' % fid)
    cp = os.path.join(folder, CITES_FILE)
    bl = body.split('\n')
    da = [i for i, l in enumerate(bl) if D_HEAD.match(l)]
    dpart = '\n'.join(bl[da[0]:]) if da else ''  # section D: from its heading to the trace
    crows = tsv(cp, 8) if os.path.isfile(cp) else []
    for c in crows:
        cid = '(?<![\\w-])%s(?!\\d)' % c[0]
        if c[7] in CITE_CARRY and not re.search(cid, dpart):
            lost.append(('cite not asked: %s' if re.search(cid, body) else 'cite not carried: %s') % c[0])
        elif c[7] in CITE_CARRY and not re.search('(?m)^- \\*\\*%s\\*\\*' % c[0], dpart):
            lost.append('cite not in item form: %s' % c[0])
    lost += cite_hint_faults(dpart, rule_docs_read(folder) | {c[2] for c in crows if c[2] != '-'}, {c[0] for c in crows if c[7] == 'ambiguous'})
    dp2 = os.path.join(folder, 'decision-pairs.tsv')
    if os.path.isfile(dp2):
        for c in tsv(dp2, 3):
            if not any((re.search('(?<![\\w-])%s(?!\\d)' % c[0], l) and re.search('(?<![\\w-])%s(?!\\d)' % c[1], l) for l in body.split('\n'))):
                lost.append('decision pair not carried: %s %s' % (c[0], c[1]))
    return (cited, lost, dn)

FIRST_MAX = 100

APPLIES = 'Applies when:'

OUT_CLASSES = ('no-rule', 'not-built')

WORD = re.compile("[A-Za-z0-9][A-Za-z0-9'_-]*")

def heading_lines(lines):
    out, fence = ({}, False)
    for i, l in enumerate(lines, 1):
        if l.strip().startswith('```'):
            fence = not fence
            continue
        m = None if fence else HEAD.match(l)
        if m:
            out[i] = (len(m.group(1)), fold(m.group(2)))
    return out

def core_line(lines, a, b, heads):
    for i in range(a, b + 1):
        l = lines[i - 1]
        if l.strip() and i not in heads and (not BREAK.match(l)):
            return i
    return a

def sections(lane, pieces):
    by_path, order = ({}, [])
    for pid, (path, a, b) in pieces.items():
        if path not in by_path:
            by_path[path] = []
            order.append(path)
        by_path[path].append((a, b, pid))
    rows, items, n = ([], [], 0)
    for path in order:
        ls = lines_of(lane, path)
        heads = heading_lines(ls)
        hl = sorted(heads)
        paths, stack = ({}, [])
        for h in hl:
            lv, t = heads[h]
            while stack and stack[-1][0] >= lv:
                stack.pop()
            stack.append((lv, t))
            paths[h] = ' > '.join((x[1] for x in stack))
        cur, got = (None, {})
        for a, b, pid in sorted(by_path[path]):
            c = core_line(ls, a, b, heads)
            h = max([x for x in hl if x < c], default=0)
            if h not in got:
                n += 1
                first = fold(ls[c - 1])[:FIRST_MAX]
                if h:
                    nxt = next((fold(ls[j - 1]) for j in range(h + 1, len(ls) + 1) if ls[j - 1].strip()), '')
                    if nxt.startswith(APPLIES):
                        first = nxt
                got[h] = ['s%d' % n, path, paths.get(h, '-') or '-', first or '-', 0]
                rows.append(got[h])
            got[h][4] += 1
            items.append((got[h][0], pid))
    return ([tuple(r) for r in rows], items)

def check_sections(pieces, rows, items):
    bad, seen, count = ([], {}, {})
    ids = {r[0] for r in rows}
    for s, p in items:
        seen.setdefault(p, []).append(s)
        count[s] = count.get(s, 0) + 1
        if s not in ids:
            bad.append('item %s in an unknown section %s' % (p, s))
    for p in pieces:
        k = len(seen.get(p, []))
        if k != 1:
            bad.append('item %s in %s sections' % (p, 'no' if k == 0 else k))
    for p in seen:
        if p not in pieces:
            bad.append('item %s is not an item of the cut' % p)
    for r in rows:
        if count.get(r[0], 0) != int(r[4]) or int(r[4]) < 1:
            bad.append('section %s holds %d items, its row says %s' % (r[0], count.get(r[0], 0), r[4]))
    return bad

def read_sections(folder):
    p = os.path.join(folder, 'sections.tsv')
    rows = tsv(p, 6 if next((l for l in read(p).split('\n') if l), '').count('\t') == 5 else 5)
    if len({r[0] for r in rows}) != len(rows):
        raise Refused('refused: sections.tsv repeats a section id')
    return rows

def reverse_docs(rows):
    docs = []
    for r in rows:
        if r[1] not in docs:
            docs.append(r[1])
    return [r for d in reversed(docs) for r in rows if r[1] == d]

EVERY = 'EVERY'

def opens(folder):
    out = {}
    if os.path.isfile(os.path.join(folder, EVERY)) and os.path.isfile(os.path.join(folder, 'subjects.tsv')):
        for k, l in enumerate(read(os.path.join(folder, 'subjects.tsv')).split('\n'), 1):
            c = l.split('\t')
            if c[0] == 'open' and len(c) == 2:
                out.setdefault(c[1], []).append(k)
    return out

def subjects(folder):
    every = os.path.isfile(os.path.join(folder, EVERY))
    secs = read_sections(folder)
    sid = {r[0]: r[1] for r in secs}
    docs = {r[1] for r in secs}
    dec = {c[0] for c in decision_rows(os.path.join(folder, 'decisions.tsv'))}
    p = os.path.join(folder, 'subjects.tsv')
    if not os.path.isfile(p):
        raise Refused('refused: no subjects.tsv')
    bad, outs, touched = ([], {}, {})
    no, nt = (0, 0)
    for k, l in enumerate(read(p).split('\n'), 1):
        if not l.strip():
            continue
        c = l.split('\t')
        if c[0] == 'out' and len(c) == 4:
            no += 1
            if c[1] not in sid and c[1] not in docs:
                bad.append('subjects.tsv:%d out row names no known section or document: %s' % (k, c[1]))
            if c[2] not in OUT_CLASSES:
                bad.append('subjects.tsv:%d class %s is not no-rule or not-built' % (k, c[2]))
            if len(WORD.findall(c[3])) < 2:
                bad.append('subjects.tsv:%d subject of fewer than two words' % k)
            for s in [c[1]] if c[1] in sid else [x for x in sid if sid[x] == c[1]]:
                outs.setdefault(s, []).append((k, c[1] in docs and c[1] not in sid))
        elif c[0] == 'touched' and len(c) == 3:
            nt += 1
            ds = [x for x in re.split('[,\\s]+', c[2]) if x]
            if c[1] not in sid:
                bad.append('subjects.tsv:%d touched row names an unknown section: %s' % (k, c[1]))
            if not ds:
                bad.append('subjects.tsv:%d touched row names no decision' % k)
            for d in ds:
                if d not in dec:
                    bad.append('subjects.tsv:%d touched row cites an unknown decision: %s' % (k, d))
            touched.setdefault(c[1], []).append((k, ds))
        elif every and c[0] == 'open' and (len(c) == 2):
            if c[1] not in sid:
                bad.append('subjects.tsv:%d open row names an unknown section: %s' % (k, c[1]))
        else:
            bad.append('subjects.tsv:%d is neither `out` with 4 fields nor `touched` with 3%s' % (k, ' nor `open` with 2' if every else ''))
    for s in sorted(touched, key=lambda x: (x not in sid, int(x[1:]) if x[1:].isdigit() else 0)):
        for k, whole in outs.get(s, []):
            bad.append(('subjects.tsv:%d section %s is touched inside a document put out whole (row %d)' if whole else 'subjects.tsv:%d section %s is both out and touched (row %d)') % (touched[s][0][0], s, k))
    if every:
        op = opens(folder)
        for r in secs:
            n = len(outs.get(r[0], [])) + len(touched.get(r[0], [])) + len(op.get(r[0], []))
            if n != 1:
                bad.append('section %s has %s' % (r[0], 'no row' if n == 0 else '%d rows' % n))
    return (no, nt, bad, outs, touched)

def fill_open(folder):
    if not os.path.isfile(os.path.join(folder, EVERY)):
        raise Refused('refused: fill needs the EVERY mark')
    no, nt, bad, outs, touched = subjects(folder)
    op = opens(folder)
    miss = [r[0] for r in read_sections(folder) if r[0] not in outs and r[0] not in touched and (r[0] not in op)]
    if miss:
        p = os.path.join(folder, 'subjects.tsv')
        t = read(p)
        with open(p, 'a', encoding='utf-8') as fh:
            fh.write(('' if not t or t.endswith('\n') else '\n') + ''.join(('open\t%s\n' % m for m in miss)))
    return miss

def out_line(folder, rows):
    ls = read(os.path.join(folder, 'subjects.tsv')).split('\n')
    return {s: '; '.join((fold(' '.join(ls[k - 1].split('\t')[1:3])) + ': ' + fold(ls[k - 1].split('\t')[3]) for k, _ in v)) for s, v in rows.items()}

def join(p1, p2):
    res = []
    for f in (p1, p2):
        no, nt, bad, outs, touched = subjects(f)
        if bad:
            raise Refused('refused: %s fails the subjects check (%d faults)' % (f, len(bad)))
        res.append((outs, touched, out_line(f, outs)))
    s1, s2 = (read_sections(p1), read_sections(p2))
    if sorted(s1) != sorted(s2):
        raise Refused('refused: the two passes have different section lists')
    read_list, left = ([], [])
    for r in s1:
        s = r[0]
        if s in res[0][0] and s in res[1][0]:
            left.append((s, res[0][2][s], res[1][2][s]))
        else:
            ds = sorted({d for x in res for _, dd in x[1].get(s, []) for d in dd}, key=lambda d: int(d[1:]) if d[1:].isdigit() else 0)
            read_list.append((s, r[4], ','.join(ds) or '-'))
    return (read_list, left)

def zone(lane, pieces_path, secdir, read_list, parts=1, every=False, budget=None, mark=None):
    full = {c[0]: c for c in tsv(pieces_path, 5)}
    secs = read_sections(secdir)
    items = {}
    for s, p in tsv(os.path.join(secdir, 'section-items.tsv'), 2):
        items.setdefault(s, []).append(p)
    want = {}
    for c in tsv(read_list, 3):
        if every or c[2] not in ('-', ''):
            want[c[0]] = c[2]
    known = {r[0] for r in secs}
    for s in want:
        if s not in known or not items.get(s):
            raise Refused('refused: read-list section %s is not a section with items' % s)
    text, zp, named, size, count, cache, docs = ({}, [], [], {}, {}, {}, [])
    order, chunk = ([], {})
    for r in secs:
        if r[0] not in want:
            continue
        order.append((r[0], r[1]))
        ps = sorted(items[r[0]], key=lambda p: (int(full[p][2]), int(full[p][3])))
        path = r[1]
        if path not in docs:
            docs.append(path)
            text[path] = []
        if path not in cache:
            cache[path] = lines_of(lane, path)
        ls = cache[path]
        a, b = (int(full[ps[0]][2]), max((int(full[p][3]) for p in ps)))
        start = len(text[path])
        text[path].append('== %s | %s | lines %d-%d | %s' % (r[0], path, a, b, r[2]))
        last = None
        for p in ps:
            x, y = (int(full[p][2]), int(full[p][3]))
            if last is not None and x > last + 1:
                text[path].append('...')
            if mark and p in mark:
                text[path].append('-- unit %s already has a row: %s' % (p, mark[p]))
            for i in range(max(x, (last or 0) + 1), y + 1):
                text[path].append('%d: %s' % (i, ls[i - 1]))
                size[path] = size.get(path, 0) + len(ls[i - 1].encode('utf-8')) + 1
            last = max(last or 0, y)
            zp.append(full[p])
            named.append(full[p] + [want[r[0]]])
            count[path] = count.get(path, 0) + 1
        text[path].append('')
        chunk[r[0]] = (text[path][start:], [x[0] for x in zp[len(zp) - len(ps):]])
    if budget is not None:
        return zone_budget(order, chunk, full, named, budget)
    part, run, total = ({}, 0, sum(size.values()))
    for d in docs:
        part[d] = 'r2' if parts == 2 and (run * 2 + size.get(d, 0) >= total or 'r2' in part.values()) else 'r1'
        run += size.get(d, 0)
    portions = sorted(((part[p], p, size.get(p, 0), count[p]) for p in count))
    bundles = {}
    for d in docs:
        bundles.setdefault(part[d], []).extend(text[d])
    zp_by = {r: [x for x in zp if part[x[1]] == r] for r in bundles}
    named_by = {r: [x for x in named if part[x[1]] == r] for r in bundles}
    return ({r: '\n'.join(t) + '\n' for r, t in bundles.items()}, zp, portions, zp_by, named_by)

def table_join(first, second):
    t1, t2 = (tsv(first, 6), tsv(second, 6))
    has = {c[1] for c in t1 if c[2] != 'none'}
    units = {c[1] for c in t1}
    new, skipped = ({}, 0)
    for c in t2:
        if c[1] not in units:
            raise Refused('refused: unit %s of the second table is not in the first' % c[1])
        if c[2] == 'none':
            continue
        if c[1] in has:
            skipped += 1
        else:
            new.setdefault(c[1], []).append(c)
    out, done = ([], set())
    for c in t1:
        if c[1] in new:
            if c[1] not in done:
                out.extend(new[c[1]])
                done.add(c[1])
            continue
        out.append(c)
    return (out, t1, new, skipped)

def zone_budget(order, chunk, full, named, budget):
    nb = lambda ls: len(('\n'.join(ls) + '\n').encode('utf-8'))
    docs = []
    for sid, path in order:
        if not docs or docs[-1][0] != path:
            docs.append((path, []))
        docs[-1][1].append(sid)
    parts, cur, cb = ([], [], 0)
    for path, sids in docs:
        db = nb([l for x in sids for l in chunk[x][0]])
        if cur and cb + db > budget:
            parts.append(cur)
            cur, cb = ([], 0)
        if db <= budget:
            cur += sids
            cb += db
            continue
        for x in sids:
            xb = nb(chunk[x][0])
            if cur and cb + xb > budget:
                parts.append(cur)
                cur, cb = ([], 0)
            cur.append(x)
            cb += xb
    if cur:
        parts.append(cur)
    seen = {}
    for k, ps in enumerate(parts, 1):
        for x in ps:
            seen.setdefault(x, []).append(k)
    bad = [x for x, _ in order if len(seen.get(x, [])) != 1]
    if bad:
        raise Refused('refused: sections in no part or in two: %s' % ', '.join(bad))
    path_of = dict(order)
    texts, zp_by, named_by, portions = ({}, {}, {}, [])
    nm = {x[0]: x for x in named}
    for k, ps in enumerate(parts, 1):
        r = 'r%d' % k
        texts[r] = '\n'.join((l for x in ps for l in chunk[x][0])) + '\n'
        zp_by[r] = [full[p] for x in ps for p in chunk[x][1]]
        named_by[r] = [nm[p] for x in ps for p in chunk[x][1]]
        for d in dict.fromkeys((path_of[x] for x in ps)):
            its = [p for x in ps if path_of[x] == d for p in chunk[x][1]]
            portions.append((r, d, nb([l for x in ps if path_of[x] == d for l in chunk[x][0]]), len(its)))
    zp = [full[p] for x, _ in order for p in chunk[x][1]]
    return (texts, zp, portions, zp_by, named_by)

def cards_agree(lane, a, b):
    bad = []
    for name, c in (('A', a), ('B', b)):
        for r in cards_fresh(lane, c):
            bad.append('build %s: %s %s %s: %s' % (name, r[0], r[1], r[2], r[3]))
    if bad:
        return ([], bad)
    pieces = {r[0]: (r[1], r[2], r[3]) for r in cut(lane, 80, 'item')}
    rows, items = sections(lane, pieces)
    keys = card_keys(rows)
    ba, bb = (read_cards(a), read_cards(b))
    out = []
    for r in rows:
        ca, cb = (ba[keys[r[0]]], bb[keys[r[0]]])
        kind = 'no-rule' if ca[4] == 'no-rule' and cb[4] == 'no-rule' else 'rule'
        out.append((r[0], kind, '%s: %s' % (ca[4], ca[5]), '%s: %s' % (cb[4], cb[5])))
    return (out, [])

def readlist(secdir, kinds_path):
    secs = read_sections(secdir)
    k = {c[0]: c for c in tsv(kinds_path, 4)}
    if sorted(k) != sorted((r[0] for r in secs)):
        raise Refused('refused: the kinds are not the sections of %s' % secdir)
    rl = [(r[0], r[4], '-') for r in secs if k[r[0]][1] != 'no-rule']
    lo = [(r[0], k[r[0]][2], k[r[0]][3]) for r in secs if k[r[0]][1] == 'no-rule']
    return (rl, lo, sum((int(r[4]) for r in secs)))

KINDS = ('rule', 'no-rule')

CARD_START = 'applies when a piece of work'

CARD_MAX = 400

def section_lines(pieces, items):
    out = {}
    for s, p in items:
        path, a, b = pieces[p]
        out.setdefault(s, (path, set()))[1].update(range(a, b + 1))
    return {s: (v[0], sorted(v[1])) for s, v in out.items()}

def section_hash(ls, lines):
    return hashlib.sha256('\n'.join((ls[i - 1] for i in lines)).encode('utf-8')).hexdigest()

def check_cards(lane, folder):
    pieces = read_pieces(os.path.join(folder, 'pieces.tsv'))
    secs = {r[0]: r for r in read_sections(folder)}
    sl = section_lines(pieces, tsv(os.path.join(folder, 'section-items.tsv'), 2))
    p = os.path.join(folder, 'cards.tsv')
    if not os.path.isfile(p):
        return (0, ['cards.tsv is missing'])
    bad, seen, n, cache = ([], {}, 0, {})
    for k, l in enumerate(read(p).split('\n'), 1):
        if not l.strip():
            continue
        n += 1
        c = l.split('\t')
        if len(c) != 5:
            bad.append('row %d: %d fields, not 5' % (k, len(c)))
            continue
        sid, kind, line, place, quote = c
        if sid not in secs:
            bad.append('row %d: %s is not a section of the portion' % (k, sid))
            continue
        seen[sid] = seen.get(sid, 0) + 1
        if kind not in KINDS:
            bad.append('row %d: kind %s, not rule or no-rule' % (k, kind))
        if len(line) > CARD_MAX:
            bad.append('row %d: line of %d characters, over %d' % (k, len(line), CARD_MAX))
        words = len(WORD.findall(line))
        if kind == 'rule':
            if not fold(line).lower().startswith(CARD_START):
                bad.append('row %d: a rule line starts `%s`' % (k, CARD_START))
            if words < 6:
                bad.append('row %d: a rule line of %d words, under 6' % (k, words))
        elif kind == 'no-rule' and words < 3:
            bad.append('row %d: a no-rule line of %d words, under 3' % (k, words))
        if kind == 'rule' or place != '-' or quote != '-':
            m = re.match('^(.+):(\\d+)$', place)
            path, lines = sl[sid]
            if not m or m.group(1) != path or int(m.group(2)) not in lines:
                bad.append('row %d: quote place %s is not a line of %s' % (k, place, sid))
            else:
                if path not in cache:
                    cache[path] = lines_of(lane, path)
                q = fold(quote)
                if len(q) < MIN_QUOTE or q not in fold(cache[path][int(m.group(2)) - 1]):
                    bad.append('row %d: quote not on %s' % (k, place))
    for sid in secs:
        if seen.get(sid, 0) != 1:
            bad.append('%s: %d cards, not 1' % (sid, seen.get(sid, 0)))
    return (n, bad)

def card_keys(rows):
    k, out = ({}, {})
    for r in rows:
        x = (r[1], r[2])
        k[x] = k.get(x, 0) + 1
        out[r[0]] = (r[1], r[2], str(k[x]))
    return out

def cards_join(lane, folders):
    got, allsec, pieces, items = ({}, {}, {}, [])
    for f in folders:
        n, bad = check_cards(lane, f)
        if bad:
            raise Refused('refused: %s fails the cards check (%d faults)' % (f, len(bad)))
        for r in read_sections(f):
            allsec[r[0]] = r
        pieces.update(read_pieces(os.path.join(f, 'pieces.tsv')))
        items += tsv(os.path.join(f, 'section-items.tsv'), 2)
        for c in tsv(os.path.join(f, 'cards.tsv'), 5):
            if c[0] in got:
                raise Refused('refused: %s has cards in two portions' % c[0])
            got[c[0]] = c
    sl = section_lines(pieces, items)
    order = sorted(allsec, key=lambda x: int(x[1:]))
    keys = card_keys([allsec[x] for x in order])
    out, cache = ([], {})
    for sid in order:
        path, lines = sl[sid]
        if path not in cache:
            cache[path] = lines_of(lane, path)
        c = got[sid]
        out.append((sid,) + keys[sid] + (c[1], c[2], c[3], c[4], section_hash(cache[path], lines)))
    return out

def read_cards(path):
    rows = tsv(path, 9)
    by = {}
    for r in rows:
        if r[4] not in KINDS:
            raise Refused('refused: cards row %s: kind %s' % (r[0], r[4]))
        by[r[1], r[2], r[3]] = r
    return by

def cards_fresh(lane, cards_path):
    pieces = {r[0]: (r[1], r[2], r[3]) for r in cut(lane, 80, 'item')}
    rows, items = sections(lane, pieces)
    sl = section_lines(pieces, items)
    keys = card_keys(rows)
    by = read_cards(cards_path)
    out, cache = ([], {})
    for r in rows:
        c = by.get(keys[r[0]])
        path, lines = sl[r[0]]
        if path not in cache:
            cache[path] = lines_of(lane, path)
        if c is None:
            out.append((r[0], r[1], r[2], 'no card'))
        elif c[8] != section_hash(cache[path], lines):
            out.append((r[0], r[1], r[2], 'text changed'))
    return out

def with_cards(rows, cards_path):
    by = read_cards(cards_path)
    keys = card_keys(rows)
    out = []
    for r in rows:
        c = by[keys[r[0]]]
        first = r[3] if r[3].startswith(APPLIES) else '%s: %s' % (c[4], c[5])
        out.append((r[0], r[1], r[2], first, r[4]))
    return out

def handoff_lines(path):
    t = read(path)
    ls = t.split('\n')
    return ls[:-1] if t.endswith('\n') else ls

def named_lines(handoff, docs):
    base = sorted({os.path.basename(d) for d in docs})
    out = []
    for i, l in enumerate(handoff_lines(handoff), 1):
        for b in base:
            if re.search('(?<![\\w.\\-])(?:[\\w.\\-]+/)*' + re.escape(b) + '(?![\\w.\\-/])', l):
                out.append((i, b))
    return out

def check_decisions(handoff, folder, docs=None):
    n = len(handoff_lines(handoff))
    bad, ids, spans = ([], [], [])
    for k, c in enumerate(decision_rows(os.path.join(folder, 'decisions.tsv')), 1):
        if c[0] != 'D%d' % k:
            bad.append('row %d: id %s, not D%d' % (k, c[0], k))
        if c[3] not in MARKS:
            bad.append('row %s: no mark `open` or `stated` in field 4' % c[0])
        ids.append(c[0])
        for r in c[1].split(','):
            m = re.match('^(\\d+)-(\\d+)$', r)
            if not m or not 1 <= int(m.group(1)) <= int(m.group(2)) <= n:
                bad.append("row %s: range %s is not inside the handoff's %d lines" % (c[0], r, n))
            else:
                spans.append((int(m.group(1)), int(m.group(2))))
        if len(c[2].split()) < 3:
            bad.append('row %s: text of fewer than 3 words' % c[0])
    pp = os.path.join(folder, 'decision-pairs.tsv')
    if os.path.isfile(pp):
        for c in tsv(pp, 3):
            if c[0] not in ids or c[1] not in ids or c[0] == c[1] or (len(c[2].split()) < 3):
                bad.append('pair %s %s: unknown or same id, or a why of fewer than 3 words' % (c[0], c[1]))
    if docs is not None:
        for i, b in named_lines(handoff, docs):
            if not any((a <= i <= z for a, z in spans)):
                bad.append('line %d names %s and lies in no decision' % (i, b))
    ctx = []
    cp = os.path.join(folder, 'context.tsv')
    if os.path.isfile(cp):
        for k, c in enumerate(tsv(cp, 2), 1):
            for r in c[0].split(','):
                m = re.match('^(\\d+)-(\\d+)$', r)
                if not m or not 1 <= int(m.group(1)) <= int(m.group(2)) <= n:
                    bad.append("context row %d: range %s is not inside the handoff's %d lines" % (k, r, n))
                else:
                    ctx.append((int(m.group(1)), int(m.group(2))))
            if len(c[1].split()) < 3:
                bad.append('context row %d: reason of fewer than 3 words' % k)
    for i, l in enumerate(handoff_lines(handoff), 1):
        if not l.strip() or HEAD.match(l) or FENCE.match(l) or TABLE_RULE.match(l):
            continue
        if not any((a <= i <= z for a, z in spans + ctx)):
            bad.append('line %d lies in no decision and no context row' % i)
    return (len(ids), bad)

QUESTIONS_FILE = 'questions.tsv'

QLOOK_FILE = 'qlook.tsv'

QJOIN_FILE = 'questions-join.tsv'

QKINDS = ('choice', 'rule-settles', 'answered', 'no-bear')

QDEST = {'rule-settles': 'rules', 'answered': 'same'}

RULES_HEAD = '### Rules to follow (not stated in the handoff) (written by script)'

SAME_HEAD = '### Rules the handoff follows (written by script)'

NOTBEAR_HEAD = '### Read and judged not to bear (written by script)'

D_HEAD = re.compile('^## D\\.')

AUDIT_DIR = 'audit'

AUDIT_HEAD = '## Codebase audits (written by script)'

AUDIT_SECTIONS = ('file inventory', 'consumers', 'gaps', 'runtime', 'abstractions')

AUDIT_SHAPE = '### Codebase audit - <dir-path>\nCoverage: <files read whole> of <files in the dir> files read whole\n\n#### File inventory\n- <path> - <what the file is>\n\n#### Imports / consumers (cross-feature)\n#### Gaps vs target shape\n#### Runtime issues\n#### Key abstractions worth preserving\n\nEvery section holds bullets only, `- none` when it has nothing. A finding is one line:\n`- <audit-id>-<n> <path>:<line> "<the words of that line>" - <the statement>`, or `(absent)` in place of the line\nand the words for something that is not there.'

FINDING_LINE = re.compile('^\\s*[-*]\\s+(A\\d+)-(\\d+)\\b(.*)$')

FINDING_CITE = re.compile('^\\s*([\\w./\\[\\]()@-]+\\.[A-Za-z]\\w*):(\\d+)\\s+\\"([^\\"]+)\\"|^\\s*\\S+\\s+\\(absent\\)|^\\s*\\(absent\\)')

DIR_TOKEN = re.compile('`([^`\\s]+/)`')

def question_rows(folder):
    out = []
    for c in read_table(folder):
        k = (c[1], c[3], c[4])
        if c[2] == 'asks' and k not in out:
            out.append(k)
    return out

def question_parts(rows, cap=QUESTION_PART):
    groups = []
    for r in rows:
        g = next((g for g in groups if g[0] == r[1]), None)
        if g:
            g[1].append(r)
        else:
            groups.append((r[1], [r]))
    parts, cur = ([], [])
    for _, g in groups:
        while len(g) > cap:
            if cur:
                parts.append(cur)
                cur = []
            parts.append(g[:cap])
            g = g[cap:]
        if len(cur) + len(g) > cap:
            parts.append(cur)
            cur = []
        cur = cur + g
    if cur:
        parts.append(cur)
    return parts

def deal_questions(folder, out, cap=QUESTION_PART, reverse=False):
    if os.path.exists(out):
        raise Refused('refused: %s exists; name a fresh folder' % out)
    rows = [tuple(c) for c in tsv(os.path.join(folder, QUESTIONS_FILE), 3)]
    os.makedirs(out)
    res = []
    for k, p in enumerate(question_parts(rows, cap), 1):
        d = os.path.join(out, 'part-%d' % k)
        os.makedirs(d)
        write(os.path.join(d, QUESTIONS_FILE), p[::-1] if reverse else p)
        with open(os.path.join(folder, 'decisions.tsv'), 'rb') as a, open(os.path.join(d, 'decisions.tsv'), 'wb') as b:
            b.write(a.read())
        res.append(('part-%d' % k, sorted({r[1] for r in p}, key=lambda x: int(x[1:])), len(p)))
    return res

def declared_handoff(lane, path):
    """True when a relative path outside the lane names the declared --handoff file, compared physically, and that
    file is itself outside the lane"""
    if not HANDOFF or path.startswith('/') or CITES.inside(path):
        return False
    real = lambda p: os.path.realpath(os.path.join(lane, p))
    top = os.path.realpath(lane)
    out = os.path.relpath(real(HANDOFF), top).split(os.sep)[0] == '..'  # an inside handoff keeps its inside cite only
    return out and real(path) == real(HANDOFF) and os.path.isfile(real(path))

def recorded_handoff(run):
    """the --handoff value step 1 wrote to the run's hash record, else ''"""
    rec = os.path.join(run, INPUTS_FILE)
    return next((c[1] for c in tsv(rec, 3) if c[0] == 'handoff'), '') if os.path.isfile(rec) else ''

def cite_line(lane, cite):
    m = CITES.CITE.match(cite)
    if m and declared_handoff(lane, m.group(1)):  # the Scope input is the one outside path a record may cite
        n = int(m.group(2))
        return (m.group(1), n) if 1 <= n <= len(lines_of(lane, m.group(1))) else None
    return CITES.cite_line(lane, cite, lambda p: os.path.isfile(p), lambda p: lines_of(lane, p))

def is_handoff(path, lane=None):
    return bool(HANDOFF) and (path == HANDOFF or (os.path.basename(path) == os.path.basename(HANDOFF) and HANDOFF.endswith(path))
                              or (lane is not None and declared_handoff(lane, path)))

def question_check(folder, who, lane):
    if who not in ('A', 'B'):
        raise Refused('refused: --look takes A or B')
    rows = [tuple(c) for c in tsv(os.path.join(folder, QUESTIONS_FILE), 3)]
    lp = os.path.join(folder, QLOOK_FILE)
    if not os.path.isfile(lp):
        raise Refused('refused: %s has no %s' % (folder, QLOOK_FILE))
    rules, faults, seen, reasons = (set(rule_files(lane)), [], {}, [])
    for n, c in enumerate(tsv(lp, 6), 1):
        k = (c[0], c[1], c[2])
        seen[k] = seen.get(k, 0) + 1
        if k not in rows:
            faults.append('%s:%d names no question row: %s %s %s' % ((QLOOK_FILE, n) + k))
        if c[3] not in QKINDS:
            faults.append('%s:%d kind %s, not one of %s' % (QLOOK_FILE, n, c[3], ', '.join(QKINDS)))
        if len(c[5].split()) < 3:
            faults.append('%s:%d reason under 3 words' % (QLOOK_FILE, n))
        reasons.append((k, c[5]))
        if c[4] == '-':
            if c[3] != 'choice':
                faults.append('%s:%d %s names no line' % (QLOOK_FILE, n, c[3]))
            continue
        at = cite_line(lane, c[4])
        if at is None:
            faults.append('%s:%d cites %s: no line of a lane file' % (QLOOK_FILE, n, c[4]))
        elif c[3] == 'answered' and (not is_handoff(at[0], lane)):
            faults.append('%s:%d answered cites %s, not the handoff' % (QLOOK_FILE, n, c[4]))
        elif c[3] in ('rule-settles', 'no-bear') and at[0] not in rules:
            faults.append('%s:%d %s cites %s, not a rule document' % (QLOOK_FILE, n, c[3], c[4]))
    faults += ['%s: %d lines for %s %s %s' % ((QLOOK_FILE, v) + k) for k, v in seen.items() if v > 1]
    faults += ['no question look line: %s %s %s' % k for k in rows if k not in seen]
    where = {}
    for i, p in enumerate(question_parts(rows), 1):
        where.update({x: i for x in p})
    cnt = {}
    for k, r in reasons:
        if k in where:
            cnt.setdefault((where[k], norm_reason(r)), []).append(k)
    faults += ['reason on more than 3 lines of part %d (%d lines): %s' % (i, len(v), r[:80]) for (i, r), v in sorted(cnt.items()) if len(v) > 3]
    return (len(rows), faults)

def merge_questions(folder, parts_dir):
    if os.path.exists(os.path.join(folder, QLOOK_FILE)):
        raise Refused('refused: %s already has %s' % (folder, QLOOK_FILE))
    parts = sorted([p for p in os.listdir(parts_dir) if re.match('^part-\\d+$', p)], key=lambda x: int(x[5:]))
    out = []
    for p in parts:
        f = os.path.join(parts_dir, p, QLOOK_FILE)
        if not os.path.isfile(f):
            raise Refused('refused: %s has no qlook.tsv' % p)
        out += tsv(f, 6)
    write(os.path.join(folder, QLOOK_FILE), out)
    return (len(parts), len(out))

def question_join(fa, fb, lane):
    looks = []
    for who, f in (('A', fa), ('B', fb)):
        n, faults = question_check(f, who, lane)
        if faults:
            raise Refused('refused: question look %s did not pass its check: %s' % (who, '; '.join(faults[:5])))
        looks.append({(c[0], c[1], c[2]): c for c in tsv(os.path.join(f, QLOOK_FILE), 6)})
    a, b = looks
    if set(a) != set(b):
        raise Refused('refused: the two question looks name different rows')
    out = []
    for k in [tuple(c) for c in tsv(os.path.join(fa, QUESTIONS_FILE), 3)]:
        ca, cb = (a[k], b[k])
        if ca[3] == cb[3] == 'choice':
            v = 'question'
        elif 'choice' in (ca[3], cb[3]):
            v = 'onelook'
        elif ca[3] in QDEST or cb[3] in QDEST:
            v = QDEST[ca[3]] if ca[3] in QDEST else QDEST[cb[3]]
        else:
            v = 'notbear'
        out.append(list(k) + [v, '%s%s (%s): %s%s%s (%s): %s' % (JOIN_HEAD, ca[3], ca[4], verbatim(ca[5]), JOIN_B, cb[3], cb[4], verbatim(cb[5]))])
    return out

def qjoin_rows(folder):
    p = os.path.join(folder, QJOIN_FILE)
    if not os.path.isfile(p):
        return []
    out = []
    for c in tsv(p, 5):
        if c[3] not in ('rules', 'same', 'notbear', 'question', 'onelook') or not c[4].startswith(JOIN_HEAD) or JOIN_B not in c[4]:
            raise Refused('refused: %s row %s %s %s is not a row of question-join' % (QJOIN_FILE, c[0], c[1], c[2]))
        out.append(c)
    return out

def moved_keys(folder):
    return {(c[0], c[1], c[2]) for c in qjoin_rows(folder) if c[3] in ('rules', 'same', 'notbear', 'onelook')}

def declared_mounts(lane):
    """the `SAID.mounts:` routes of the ## Lane block, read whole, each without its slashes"""
    if not os.path.isfile(os.path.join(lane, 'CLAUDE.md')):
        return ()
    key = re.compile('^\\s*-?\\s*`?SAID\\.mounts`?:(.*)$')
    hits = [m.group(1).strip().strip('`') for m in (key.match(l) for l in lane_block(lane)) if m]
    v = hits[0].strip() if hits else 'none'
    if v == 'none':
        return ()
    v = v[1:-1] if v.startswith('[') and v.endswith(']') else v
    names = [x.strip().strip('`') for x in v.split(',')]
    return tuple(p for p in ((x[2:] if x.startswith('./') else x).strip('/') for x in names) if p)

def link_allowed(lane, rel):
    """True for the docs-root link and a declared mount's link; never a link to the lane or a folder above it"""
    rel = rel.strip('/')
    if rel == docs_root(lane):
        return True
    return rel in declared_mounts(lane) and not path_under(os.path.realpath(lane), os.path.realpath(os.path.join(lane, rel)))

def route_blocked(lane, rel):
    """True when any symlink on the lane-relative route is neither the docs root nor a declared mount"""
    at = ''
    for part in rel.strip('/').split('/'):
        at = at + '/' + part if at else part
        if os.path.islink(os.path.join(lane, at)) and not link_allowed(lane, at):
            return True
    return False

def lane_walk(lane, start, keep):
    """os.walk from start, also through a declared mount's link that leaves the lane, each real folder once"""
    top, seen, todo = os.path.realpath(lane), set(), [start]
    mounts = declared_mounts(lane)
    while todo:
        t = todo.pop(0)
        real = os.path.realpath(t)
        if real in seen:
            continue
        seen.add(real)
        for base, dirs, files in os.walk(t):
            dirs[:] = sorted(d for d in dirs if keep(d))
            yield base, dirs, files
            for d in dirs:
                p = os.path.join(base, d)
                rel = os.path.relpath(p, lane).replace(os.sep, '/')
                if os.path.islink(p) and rel in mounts and link_allowed(lane, rel) and not path_under(os.path.realpath(p), top):
                    todo.append(p)

def lane_dirs(lane):
    out = []
    keep = lambda d: not d.startswith('.') and d != 'node_modules' and not ASIDE.search(d)
    for base, dirs, _ in lane_walk(lane, lane, keep):
        for d in dirs:
            rel = os.path.relpath(os.path.join(base, d), lane).replace(os.sep, '/')
            if not route_blocked(lane, rel):
                out.append(rel + '/')
    return out

STATUS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'board', 'said_status.py')

def path_under(p, top):
    return p == top or p.startswith(top.rstrip(os.sep) + os.sep)

def registry_rows(d):
    """the SAID.lanes rows of d/CLAUDE.md as [(token, physical root)], read whole by the board's registry reader with
    its count; [] when the file declares none"""
    r = subprocess.run([sys.executable, '-I', '-B', STATUS, '--registry', '--root', d], capture_output=True, text=True)
    ls = r.stdout.splitlines()
    m = re.match('^count: (\\d+)$', ls[-1]) if ls else None
    rows = [l.split(':root=', 1) for l in ls[:-1]]
    if r.returncode != 0 or not m or int(m.group(1)) != len(rows) or any(len(x) != 2 for x in rows):
        raise Refused('refused: the SAID.lanes registry of %s: %s' % (os.path.join(d, 'CLAUDE.md'), (ls or [r.stderr.strip() or 'no output'])[-1]))
    return [(k, os.path.realpath(os.path.join(d, v))) for k, v in rows]

def handoff_root(lane):
    """(root, rows, registry file or None) the directory tokens of a handoff outside the lane resolve from: the nearest
    directory at or above the handoff whose CLAUDE.md declares SAID.lanes, else the handoff's own directory; None for a
    handoff inside the lane or its docs root"""
    top = os.path.realpath(lane)
    hp = os.path.realpath(os.path.join(top, HANDOFF))
    if path_under(hp, top) or path_under(hp, os.path.realpath(os.path.join(top, docs_root(top)))):
        return None
    d = os.path.dirname(hp)
    while True:
        if os.path.isfile(os.path.join(d, 'CLAUDE.md')):
            rows = registry_rows(d)
            if rows:
                return d, rows, os.path.join(d, 'CLAUDE.md')
        if os.path.dirname(d) == d:
            return os.path.dirname(hp), [], None
        d = os.path.dirname(d)

def token_place(lane, root, t):
    """(lane-relative token, 'lane') under this lane or its docs root, (None, 'other-lane') under another registry
    row, (t, None) under neither; all compared physically, the longest root that holds the token wins, this lane on a
    tie"""
    top = os.path.realpath(lane)
    dr = docs_root(top)
    route = os.path.relpath(os.path.normpath(os.path.join(root[0], t)), top).replace(os.sep, '/')
    if any((route == m or route.startswith(m + '/')) and link_allowed(top, m) for m in declared_mounts(top)):
        return route + '/', 'lane'  # the declared route decides, wherever the link lands
    full = os.path.realpath(os.path.join(root[0], t))  # a link on the way, the lane's own docs link included
    mine = [(top, ''), (os.path.realpath(os.path.join(top, dr)), dr + '/')]
    cands = [(r, p) for r, p in mine if path_under(full, r)] + [(r, None) for k, r in root[1] if path_under(full, r)]
    if not cands:
        return t, None
    best = max(cands, key=lambda c: len(c[0]))
    if best[1] is None:
        return None, 'other-lane'
    sub = os.path.relpath(full, best[0]).replace(os.sep, '/')
    return (best[1] + ('' if sub == '.' else sub + '/')) or './', 'lane'

def named_dirs(lane, handoff_text, hint=None, root=None):
    if hint is not None:
        toks = [] if hint.strip() == '-' else [t.strip() for t in hint.split(',') if t.strip()]
        toks = [t if t.endswith('/') else t + '/' for t in toks]
    else:
        toks = []
        for m in DIR_TOKEN.finditer(handoff_text):
            t = m.group(1)
            if t.startswith('/') or '://' in t or '..' in t.split('/') or (t in toks):
                continue
            toks.append(t)
    every = None
    out = []
    for t in toks:
        look = t
        if root is not None and hint is None:  # a handoff outside the lane names paths from its own root
            look, where = token_place(lane, root, t)
            if where == 'other-lane':
                out.append((t, '-', 'other-lane', []))
                continue
        if os.path.isdir(os.path.join(lane, look)) and not route_blocked(lane, look):
            out.append((t, look, 'audit', []))
            continue
        if every is None:
            every = lane_dirs(lane)
        m = [d for d in every if d.endswith('/' + look)]
        up = None if m else parent_dir(lane, look, every)
        if up:
            out.append((t, up, 'parent', [up]))
            continue
        out.append((t, m[0], 'audit', m) if len(m) == 1 else (t, '-', 'ambiguous' if m else 'absent', m))
    return out

def parent_dir(lane, t, every):
    """the ancestor audited for a named directory that is gone: its feature directory, the ancestor two names deep,
    else the nearest existing ancestor of three names or more; each from the lane root or the end of exactly one lane
    directory path (an ambiguous one is passed over); none when no ancestor is found"""
    parts = t.strip('/').split('/')
    for n in [2] * (len(parts) > 2) + list(range(len(parts) - 1, 2, -1)):
        p = '/'.join(parts[:n]) + '/'
        if os.path.isdir(os.path.join(lane, p)) and not route_blocked(lane, p):
            return p
        m = [d for d in every if d.endswith('/' + p)]
        if len(m) == 1:
            return m[0]
    return None

def dir_files(lane, d):
    fs = []
    for base, _, files in lane_walk(lane, os.path.join(lane, d), lambda x: not x.startswith('.') and x != 'node_modules'):
        fs += [os.path.join(base, f) for f in sorted(files)]
    return (len(fs), sum((os.path.getsize(f) for f in fs)))

def audit_dirs(lane, run, hint=None, root=None):
    out = os.path.join(run, AUDIT_DIR)
    if os.path.exists(out):
        raise Refused('refused: %s exists; the audit list is written once a run' % out)
    hl = lines_of(lane, HANDOFF)
    found = named_dirs(lane, '\n'.join(hl), hint, root)
    table = read_table(run) if os.path.isfile(os.path.join(run, 'table.tsv')) else []
    decs = {}
    dp = os.path.join(run, 'decisions.tsv')
    if os.path.isfile(dp):
        for l in read(dp).split('\n'):
            c = l.split('\t')
            if len(c) >= 2:
                s = set()
                for part in c[1].split(','):
                    a, _, b = part.partition('-')
                    if a.strip().isdigit():
                        s |= set(range(int(a), int(b or a) + 1))
                decs[c[0]] = s
    os.makedirs(out)
    rows, k = ([], 0)
    for named, path, state, matches in found:
        if state not in ('audit', 'parent'):
            rows.append(['-', named, '-', state, '0', '0'])
            continue
        k += 1
        aid = 'A%d' % k
        nf, nb = dir_files(lane, path)
        rows.append([aid, named, path, state, str(nf), str(nb)])
        at = [i for i, l in enumerate(hl, 1) if '`%s`' % named in l or '`%s`' % path in l]
        touched = {d for d, s in decs.items() if s & set(at)}
        clauses = []
        for c in table:
            if c[2] in ('same', 'against', 'asks') and c[3] in touched and (c[4] not in clauses):
                clauses.append(c[4])
        cl = []
        for r in clauses[:40]:
            p, _, n = r.rpartition(':')
            if os.path.isfile(os.path.join(lane, p)) and n.isdigit() and (1 <= int(n) <= len(lines_of(lane, p))):
                cl.append('  - %s "%s"' % (r, ' '.join(lines_of(lane, p)[int(n) - 1].split())))
        task = ['# Audit task %s' % aid, '', '- dir-path: %s' % path, '- audit-id: %s' % aid, "- target-shape: the handoff's lines that name this directory (%s), verbatim:" % HANDOFF]
        shape = at
        if not at and hint is not None:  # a hinted directory the handoff never names: the whole handoff is its target
            shape = [i for i, l in enumerate(hl, 1) if l.strip()]
            task[-1] = "- target-shape: no line of the handoff (%s) names this directory, so the whole handoff, verbatim:" % HANDOFF
        task += ['  %d: %s' % (i, hl[i - 1]) for i in shape]
        if state == 'parent':
            task.append('- named: %s, no such directory in the lane; this ancestor is audited in its place' % named)
        task += ['- contract-clauses: %s' % ('the rule lines the checked table holds for the decisions on those lines:' if cl else 'none')] + cl
        task += ['- report-shape:', ''] + ['    ' + l if l else '' for l in AUDIT_SHAPE.split('\n')]
        with open(os.path.join(out, aid + '.task.md'), 'w', encoding='utf-8', newline='\n') as fh:
            fh.write('\n'.join(task) + '\n')
    write(os.path.join(out, 'dirs.tsv'), rows)
    return rows

def audit_rows(folder):
    p = os.path.join(folder, AUDIT_DIR, 'dirs.tsv')
    if not os.path.isfile(p):
        return None
    return tsv(p, 6)

def audit_report_check(audit, aid, lane):
    rows = {c[0]: c for c in tsv(os.path.join(audit, 'dirs.tsv'), 6) if c[0] != '-'}
    if aid not in rows:
        raise Refused('refused: %s is not an audit of dirs.tsv' % aid)
    p = os.path.join(audit, aid + '.md')
    if not os.path.isfile(p):
        return ['%s.md: no report' % aid]
    ls = [l.rstrip() for l in read(p).split('\n')]
    body = [l for l in ls if l.strip()]
    faults = []
    if not body or body[0] != '### Codebase audit - %s' % rows[aid][2]:
        faults.append('%s.md: the first line is not `### Codebase audit - %s`' % (aid, rows[aid][2]))
    if not any((l.startswith('Coverage:') for l in body)):
        faults.append('%s.md: no Coverage line' % aid)
    heads = [l.lower() for l in body if l.startswith('#### ')]
    at = 0
    for s in AUDIT_SECTIONS:
        hit = next((j for j in range(at, len(heads)) if s in heads[j]), None)
        if hit is None:
            faults.append('%s.md: the five sections are not all there in order (%s)' % (aid, s))
            break
        at = hit + 1
    ids = []
    for l in body:
        m = FINDING_LINE.match(l)
        if not m:
            continue
        fid = '%s-%s' % (m.group(1), m.group(2))
        if m.group(1) != aid:
            faults.append('%s.md: finding id %s is not of audit %s' % (aid, fid, aid))
        if fid in ids:
            faults.append('%s.md: finding id %s twice' % (aid, fid))
        ids.append(fid)
        c = FINDING_CITE.match(m.group(3))
        if not c:
            faults.append('%s.md: %s has no cite `path:line "words"` or `(absent)`' % (aid, fid))
        elif c.group(1):
            at_ = cite_line(lane, '%s:%s' % (c.group(1), c.group(2)))
            if at_ is None:
                faults.append('%s.md: %s cites %s:%s, no such line' % (aid, fid, c.group(1), c.group(2)))
            elif not CITES.quote_at(lines_of(lane, at_[0])[at_[1] - 1], c.group(3)):
                faults.append('%s.md: %s quotes words not on %s:%s' % (aid, fid, c.group(1), c.group(2)))
    return faults

def audit_ids(folder):
    rows = audit_rows(folder) or []
    out = []
    for c in rows:
        if c[0] == '-':
            continue
        p = os.path.join(folder, AUDIT_DIR, c[0] + '.md')
        if os.path.isfile(p):
            for l in read(p).split('\n'):
                m = FINDING_LINE.match(l)
                if m:
                    out.append('%s-%s' % (m.group(1), m.group(2)))
    return out

def audit_text(folder):
    rows = audit_rows(folder)
    if rows is None:
        return ''
    au = [c for c in rows if c[0] != '-']
    ol = [c for c in rows if c[3] == 'other-lane']
    lines_ = ['', AUDIT_HEAD, '', 'Audit path: spawn; dirs %d; absent or ambiguous %d%s' % (len(au), len(rows) - len(au) - len(ol),
              '; other lanes %d' % len(ol) if ol else ''), '']
    if not rows:
        lines_.append('The handoff names no directory, or the scope-hint names none: no audit ran.')
    for c in rows:
        if c[3] == 'absent':
            lines_.append('- `%s`: named in the handoff, no such directory in the lane; not audited.' % c[1])
        elif c[3] == 'ambiguous':
            lines_.append('- `%s`: named in the handoff, more than one lane directory ends so; not audited.' % c[1])
        elif c[3] == 'other-lane':
            lines_.append('- `%s`: named in the handoff, a directory of another lane of the registry; not audited.' % c[1])
        elif c[3] == 'parent':
            lines_.append('- `%s`: named in the handoff, no such directory in the lane; its ancestor `%s` is audited (%s).' % (c[1], c[2], c[0]))
    for c in au:
        lines_ += ['', read(os.path.join(folder, AUDIT_DIR, c[0] + '.md')).strip()]
    return '\n'.join(lines_) + '\n'

CITES_FILE = 'cites.tsv'
CITE_DOC = re.compile('`?([\\w./-]+\\.md)`?')
CITE_NUM = re.compile('#(\\d+)(?![\\w])')
ITEM_LINE = re.compile('^(\\d+)\\.\\s+(.*)')
HEAD_ITEM = re.compile('^#?(\\d+)(?:[.:)]|\\s)\\s*(?:(?:-|:|\\u2014)\\s*)?(.*)')
CITE_STOP = ('also', 'each', 'every', 'from', 'into', 'must', 'only', 'than', 'that', 'then', 'this', 'when', 'with')
CITE_CARRY = ('mismatch', 'ambiguous', 'no-item', 'no-file', 'no-words')

def cite_words(s):
    ws = []
    for w in re.findall('[a-z0-9]+', s.lower()):
        w = w[:-1] if len(w) > 4 and w.endswith('s') else w
        if len(w) >= 4 and w not in CITE_STOP and w not in ws:
            ws.append(w)
    return ws

def cite_label(r):
    """(the handoff's words for one cite, whether more cites follow): a parenthesis right after `#<n>`, else the
    text up to the end of the clause"""
    s = r.strip()
    if s.startswith('('):
        d = 0
        for i, ch in enumerate(s):
            d += {'(': 1, ')': -1}.get(ch, 0)
            if d == 0:
                return s[1:i].strip(), s[i + 1:].strip(' ,;') in ('', 'and', 'or')
        return s[1:].strip(), False
    head = re.split('[.;](?:\\s|$)', s, maxsplit=1)
    return head[0].strip(' ,'), len(head) == 1

def cite_item(lane, doc, word, n):
    """(line, text) of item <n> of a rule document, a line `<n>. ` or a heading `#<n>` or `<n>.`: under a heading
    that holds the word, else the one such item; `ambiguous` when more than one"""
    hits, stack, fence = ([], []), [], False
    for i, l in enumerate(lines_of(lane, doc), 1):
        if FENCE.match(l):
            fence = not fence
            continue
        if fence:
            continue
        h = HEAD.match(l)
        if h:
            stack = [x for x in stack if x[0] < len(h.group(1))]
        m = HEAD_ITEM.match(h.group(2)) if h else ITEM_LINE.match(l)
        if m and int(m.group(1)) == n:
            hits[1].append((i, m.group(2)))
            if word and any(word.lower() in x[1] for x in stack):
                hits[0].append((i, m.group(2)))
        if h:
            stack.append((len(h.group(1)), h.group(2).lower()))
    for x in hits:
        if x:
            return x[0] if len(x) == 1 else 'ambiguous'
    return None

def cites(lane):
    hl = lines_of(lane, HANDOFF)
    docs = rule_files(lane)
    rows = []
    for ln, l in enumerate(hl, 1):
        ds = list(CITE_DOC.finditer(l))
        for j, d in enumerate(ds):
            seg = l[d.end():ds[j + 1].start() if j + 1 < len(ds) else len(l)]
            ns = list(CITE_NUM.finditer(seg))
            if not ns or len(seg[:ns[0].start()].split()) > 3:
                continue
            lead = seg[:ns[0].start()].split()
            word = lead[-1] if lead and re.match('^[A-Za-z][\\w-]*$', lead[-1]) else ''
            name = d.group(1)
            hit = [f for f in docs if f == name or f.endswith('/' + name)]
            doc = hit[0] if len(hit) == 1 else None
            for k, nm in enumerate(ns):
                words, more = cite_label(seg[nm.end():ns[k + 1].start() if k + 1 < len(ns) else len(seg)])
                it = cite_item(lane, doc, word, int(nm.group(1))) if doc else None
                state = 'no-file' if not doc else 'no-item' if not it else it if it == 'ambiguous' else 'no-words' if \
                    not cite_words(words) else 'match' if all(w in cite_words(it[1]) for w in cite_words(words)) else 'mismatch'
                it = it if isinstance(it, tuple) else None
                rows.append(['C%d' % (len(rows) + 1), '%s:%d' % (HANDOFF, ln), doc or '-', nm.group(1),
                             '%s:%d' % (doc, it[0]) if it else '-', fold(words.replace('\t', ' ')) or '-',
                             fold(it[1].replace('\t', ' ')) if it else '-', state])
                if not more:
                    break
    return rows

LARGE_BYTES = 170000  # the largest size measured good for one agent
PORTION_BYTES = 150000

MOUNTS_KEY = 'SAID.scope-mounts'
DEFAULT_MOUNTS = ('adr', 'ux', 'qa')  # under the docs root, in this order
NO_MOUNTS_EXIT = 3
MANIFEST_FILE = 'mounts.md'
MANIFEST_HEAD = '### Rule documents read (written by script)'


class NoMounts(Exception):
    pass


def lane_block(lane):
    p = os.path.join(lane, 'CLAUDE.md')
    if not os.path.isfile(p):
        raise Refused('refused: the lane has no CLAUDE.md')
    out, on = [], False
    for l in read(p).split('\n'):
        if l.startswith('## ') or l.startswith('# '):
            on = l.strip() == '## Lane'
            continue
        if on:
            out.append(l)
    return out


def default_mounts(lane):
    """the folders read with no key: adr/, ux/, qa/ under the docs root, those that exist"""
    root = docs_root(lane)
    names = ['%s/%s/' % (root, d) for d in DEFAULT_MOUNTS]
    have = [n for n in names if os.path.isdir(os.path.join(lane, n))]
    if not have:
        raise NoMounts('stopped: the lane declares no %s in its ## Lane block of CLAUDE.md and has none of the default '
                       'rule folders %s. Declare the folders and files a scope reads as rules, e.g. `- %s: [%s]` '
                       '(or `none` for CLAUDE.md alone), or add one of the default folders.' % (
                           MOUNTS_KEY, ', '.join(names), MOUNTS_KEY, ', '.join(names[:2])))
    return have


def mounts_declared(lane):
    key = re.compile('^\\s*-?\\s*`?%s`?:(.*)$' % re.escape(MOUNTS_KEY))
    return any(key.match(l) for l in lane_block(lane))


def mount_list(lane):
    key = re.compile('^\\s*-?\\s*`?%s`?:(.*)$' % re.escape(MOUNTS_KEY))
    hits = [m.group(1).strip() for m in (key.match(l) for l in lane_block(lane)) if m]
    if not hits:
        return default_mounts(lane)
    if len(hits) > 1:
        raise Refused('refused: %s stands twice in the ## Lane block' % MOUNTS_KEY)
    v = hits[0].strip('`').strip()
    if v == 'none':
        return []
    if not (v.startswith('[') and v.endswith(']')):
        raise Refused('refused: %s is `none` or a list in brackets, not: %s' % (MOUNTS_KEY, v))
    items = [x.strip().strip('`').strip() for x in v[1:-1].split(',')]
    if not v[1:-1].strip() or any(not x for x in items):
        raise Refused('refused: %s holds an empty entry; write `none` for CLAUDE.md alone' % MOUNTS_KEY)
    if len(set(items)) != len(items):
        raise Refused('refused: %s names a path twice' % MOUNTS_KEY)
    if 'CLAUDE.md' in items:
        raise Refused('refused: %s lists CLAUDE.md; it is always read and is not listed' % MOUNTS_KEY)
    return items


def work_dirs(lane):
    root = docs_root(lane)
    out = {root + '/working/', root + '/features/', root + '/' + INDEX_DIR + '/'}
    for key in ('SAID.working', 'SAID.feature-spec', 'SAID.task-log'):
        v = lane_key(lane, key).split('<')[0].strip('/')
        if v:
            out.add(v + '/')
    return out


def under(rel, dirs):
    return any((rel + '/').startswith(d) for d in dirs)


def md_walk(lane, rel, dirs):
    out = []
    for base, ds, fs in os.walk(os.path.join(lane, rel)):
        b = os.path.relpath(base, lane).replace(os.sep, '/')
        ds[:] = sorted(d for d in ds if not d.startswith('.') and not under((b + '/' + d).lstrip('./'), dirs))
        out += [(b + '/' + f).lstrip('./') if b != '.' else f for f in sorted(fs) if f.endswith('.md')]
    return out


def lane_rel(item):
    """The lane-relative form of a path as written; None for an absolute path or one that climbs out with `..`.
    A link inside the lane is followed wherever it points (a docs root may link to a sibling folder)."""
    if os.path.isabs(item):
        return None
    n = os.path.normpath(item).replace(os.sep, '/')
    return None if n == '..' or n.startswith('../') else n


def mounts(lane):
    real, dirs, out = os.path.realpath(lane), work_dirs(lane), []
    for item in mount_list(lane):
        rel = lane_rel(item)
        if rel is None:
            raise Refused('refused: %s path %s is outside the lane' % (MOUNTS_KEY, item))
        p = os.path.join(real, rel)
        if not os.path.exists(p):
            raise Refused('refused: %s path %s does not exist' % (MOUNTS_KEY, item))
        if rel != '.' and under(rel, dirs):
            raise Refused('refused: %s path %s is under a work folder (%s)' % (MOUNTS_KEY, item, ', '.join(sorted(dirs))))
        if item.endswith('/'):
            if not os.path.isdir(p):
                raise Refused('refused: %s path %s ends with / but is a file' % (MOUNTS_KEY, item))
            out.append((item, md_walk(real, rel, dirs)))
        else:
            if os.path.isdir(p):
                raise Refused('refused: %s path %s is a folder: a folder path ends with /' % (MOUNTS_KEY, item))
            if not rel.endswith('.md'):
                raise Refused('refused: %s path %s is not a .md file' % (MOUNTS_KEY, item))
            out.append((item, [rel]))
    return out


def walk_key(path):
    parts = path.split('/')
    return tuple((1, x) for x in parts[:-1]) + ((0, parts[-1]),)


def handoff_docs(lane, have):
    if not HANDOFF:
        return []
    real, dirs = os.path.realpath(lane), work_dirs(lane)
    hp = HANDOFF if os.path.isabs(HANDOFF) else os.path.join(real, HANDOFF)
    if not os.path.isfile(hp):
        return []
    hrel = os.path.relpath(os.path.realpath(hp), real).replace(os.sep, '/')
    out = []
    for tok in re.findall('[A-Za-z0-9_./-]+\\.md\\b', read(hp)):
        tok = tok[2:] if tok.startswith('./') else tok
        for base in ('', docs_root(lane) + '/'):
            rel = lane_rel(base + tok)
            if rel is None or not os.path.isfile(os.path.join(real, rel)):
                continue
            if rel not in have and rel not in out and rel not in ('CLAUDE.md', hrel) and not under(rel, dirs):
                out.append(rel)
            break
    return out


def rule_set(lane):
    ms = mounts(lane)
    have = []
    for _, fs in ms:
        have += [f for f in fs if f not in have]
    extra = handoff_docs(lane, set(have))
    return ms, sorted(have + extra, key=walk_key) + ['CLAUDE.md'], extra


def rule_files(lane):
    return rule_set(lane)[1]


def manifest(lane):
    ms, files, extra = rule_set(lane)
    size = lambda f: os.path.getsize(os.path.join(lane, f))
    root, dirs = docs_root(lane), work_dirs(lane)
    rows = ['| `%s` | %d | %d |' % (item, len(fs), sum(size(f) for f in fs)) for item, fs in ms]
    rows.append('| `CLAUDE.md` | 1 | %d |' % size('CLAUDE.md'))
    rows += ['| `%s` (added for this handoff: it names the document) | 1 | %d |' % (f, size(f)) for f in extra]
    read_set, loose = set(files), []
    top = os.path.join(lane, root)
    for d in sorted(os.listdir(top)) if os.path.isdir(top) else []:
        rel = root + '/' + d
        if d.startswith('.') or not os.path.isdir(os.path.join(top, d)) or under(rel, dirs):
            continue
        n = [f for f in md_walk(lane, rel, dirs) if f not in read_set]
        if n:
            loose.append('`%s/` (.md files %d)' % (rel, len(n)))
    text = '%s\n\n%s `%s`: %d paths; `CLAUDE.md` is always read. Files %d, bytes %d.\n\n| path | files | bytes |\n' \
           '|---|---|---|\n%s\n\nNot read: the top-level folders of the docs root that hold .md files no declared path ' \
           'reaches: %s.\n\nFiles read: %s.\n' % (
               MANIFEST_HEAD, 'Declared in' if mounts_declared(lane) else 'Default folders, no', MOUNTS_KEY, len(ms), len(files), sum(size(f) for f in files), '\n'.join(rows),
               ', '.join(loose) or 'none', ', '.join('`%s`' % f for f in files))
    return len(ms), files, loose, extra, text


def mounts_block(folder):
    p = os.path.join(folder, MANIFEST_FILE)
    if not os.path.isfile(p):
        return ''
    t = read(p)
    if not t.startswith(MANIFEST_HEAD):
        raise Refused('refused: %s is not a manifest the size command wrote' % MANIFEST_FILE)
    return '\n' + t


def look_gaps(run, held):
    """every against row the drafter gets has a look line, every pair of its table a pairs-look line"""
    t = [c for c in tsv(os.path.join(run, 'table.tsv'), 6) if (c[1], c[3], c[4]) not in held]
    ag = []
    for c in t:
        if c[2] == 'against' and (c[1], c[3], c[4]) not in ag:
            ag.append((c[1], c[3], c[4]))
    pr = []
    for d in sorted({c[3] for c in t if c[2] == 'against'}, key=lambda x: int(x[1:])):
        for s in [c for c in t if c[3] == d and c[2] == 'same']:
            for a in [c for c in t if c[3] == d and c[2] == 'against' and c[1] != s[1]]:
                if (d, s[4], a[4]) not in pr:
                    pr.append((d, s[4], a[4]))
    keep = keep_of(run)
    if keep is not None:
        pr = [p for p in pr if p in keep]
    keys = lambda f: {tuple(l.split('\t')[:3]) for l in open(f, encoding='utf-8').read().split('\n') if l.strip()} if os.path.isfile(f) else set()
    lk, pl = keys(os.path.join(run, 'look.tsv')), keys(os.path.join(run, 'pairs-look.tsv'))
    return ['no look line: %s %s %s' % k for k in ag if k not in lk] + ['no pair check: %s %s %s' % k for k in pr if k not in pl]


CONFIRM_DIR = 'confirm'
CONFIRM_VERDICTS = ('holds', 'does not hold', 'cannot tell')
CONFIRM_DROP, CONFIRM_NOTE = ('confirm: does not hold: ', 'confirm: cannot tell: ')
CONFIRM_HEAD = ['id', 'unit', 'decision', 'rule']
CONFIRM_ANSWER = re.compile(r'^\s*`?(C\d{2})`?\s*(?:\t|\bTAB\b|\|)\s*Q1\s*(?:\t|\bTAB\b|\|)\s*(holds|does not hold|cannot tell)\s*'
                            r'(?:\t|\bTAB\b|\|)\s*(.*?)\s*`?$')


def look_keeps(run):
    lp = os.path.join(run, 'look.tsv')
    out = []
    if os.path.isfile(lp):
        for _, c, _x in look_lines(lp):
            if c[3] == 'keep' and tuple(c[:3]) not in out:
                out.append(tuple(c[:3]))
    return out


def confirm_items(run, lane, handoff):
    """confirm/C<nn>.md, one item a kept against row of look.tsv (the decision's handoff lines, the rule's section with
    the rule line marked >>, Q1), and confirm/items.tsv (id, unit, decision, rule); nothing when the look keeps none"""
    import csv
    keeps = look_keeps(run)
    if not keeps:
        return 0
    dec = {c[0]: c for c in decision_rows(os.path.join(run, 'decisions.tsv'))}
    with open(os.path.join(run, 'pieces.tsv'), encoding='utf-8') as fh:
        pieces = {r[0]: (r[1], int(r[2]), int(r[3])) for r in csv.reader(fh, delimiter='\t') if r}
    items_of = {}
    with open(os.path.join(run, 'sec', 'section-items.tsv'), encoding='utf-8') as fh:
        for r in csv.reader(fh, delimiter='\t'):
            if r:
                items_of.setdefault(r[0], []).append(r[1])
    hname = os.path.relpath(handoff, lane).replace(os.sep, '/')
    hand = read(handoff).split('\n')
    cf = os.path.join(run, CONFIRM_DIR)
    os.makedirs(cf, exist_ok=True)
    rows = [CONFIRM_HEAD]
    for i, (u, d, rule) in enumerate(keeps, 1):
        cid = 'C%02d' % i
        if d not in dec:
            raise Refused('refused: look.tsv keeps a row of decision %s, not in decisions.tsv' % d)
        f, l = rule.rsplit(':', 1)
        l = int(l)
        sid = next((s for s, ps in items_of.items() if any(pieces[p][0] == f and pieces[p][1] <= l <= pieces[p][2] for p in ps if p in pieces)), None)
        if sid is None:
            raise Refused('refused: the rule line %s is in no section of pieces.tsv' % rule)
        ls = [pieces[p] for p in items_of[sid] if p in pieces]
        a, b = min(x[1] for x in ls), max(x[2] for x in ls)
        text = read(os.path.join(lane, f)).split('\n')
        lines = []
        for r in dec[d][1].split(','):
            x, y = (int(v) for v in r.split('-'))
            lines += ['  %d: %s' % (n, hand[n - 1]) for n in range(x, y + 1)]
        body = ['Item %s' % cid, '', 'Decision %s: %s' % (d, dec[d][2]), 'Its handoff lines (%s):' % hname] + lines + ['',
                'Rule: %s, line %d (marked >>), in its section, lines %d to %d; you may open the file whole:' % (f, l, a, b)]
        body += ['%s %d: %s' % ('>>' if n == l else '  ', n, text[n - 1]) for n in range(a, b + 1)]
        body += ['', 'The row: the rule at %s and decision %s.' % (rule, d), '',
                 "Q1. Does the conflict hold: does the handoff's decision do what this rule line forbids, or leave out what it requires? Answer `holds` if it does, `does not hold` if it does not, `cannot tell` if the text given does not decide it. Give one sentence of reason.", '',
                 'Answer in one line: %s TAB Q1 TAB holds|does not hold|cannot tell TAB one sentence.' % cid]
        put(os.path.join(cf, cid + '.md'), '\n'.join(body) + '\n')
        rows.append([cid, u, d, rule])
    write(os.path.join(cf, 'items.tsv'), rows)
    return len(keeps)


def confirm_faults(run):
    """the confirm look's confirm/confirm.tsv against confirm/items.tsv and the look's kept rows: (faults, {row: (verdict,
    sentence)}); one line an item: id TAB Q1 TAB holds|does not hold|cannot tell TAB a sentence of at least 3 words"""
    cf = os.path.join(run, CONFIRM_DIR)
    keeps = look_keeps(run)
    ip, cp = os.path.join(cf, 'items.tsv'), os.path.join(cf, 'confirm.tsv')
    if not os.path.isfile(ip):
        return (['no %s/items.tsv: run confirm-items' % CONFIRM_DIR] if keeps else [], {})
    it = [l.split('\t') for l in read(ip).split('\n') if l.strip()]
    if not it or it[0] != CONFIRM_HEAD or any(len(c) != 4 for c in it[1:]) or [tuple(c[1:]) for c in it[1:]] != keeps:
        return (["%s/items.tsv is not the look's kept rows: run confirm-items again" % CONFIRM_DIR], {})
    row = {c[0]: tuple(c[1:]) for c in it[1:]}
    if not os.path.isfile(cp):
        return (['no %s/confirm.tsv: the confirm look has not answered' % CONFIRM_DIR], {})
    faults, got = [], {}
    for n, l in enumerate(read(cp).split('\n'), 1):
        if not l.strip():
            continue
        c = l.split('\t')
        if len(c) != 4:
            faults.append('confirm.tsv:%d has %d fields, not 4' % (n, len(c)))
        elif c[0] not in row:
            faults.append('confirm.tsv:%d names no item: %s' % (n, c[0][:20]))
        elif c[1] != 'Q1':
            faults.append('confirm.tsv:%d field 2 is not Q1' % n)
        elif c[2] not in CONFIRM_VERDICTS:
            faults.append('confirm.tsv:%d verdict %s: not holds, does not hold or cannot tell' % (n, c[2][:30]))
        elif len(c[3].split()) < 3:
            faults.append('confirm.tsv:%d reason under 3 words' % n)
        elif c[0] in got:
            faults.append('confirm.tsv:%d item %s twice' % (n, c[0]))
        else:
            got[c[0]] = (c[2], ' '.join(c[3].split()))
    faults += ['no answer: %s' % k for k in row if k not in got]
    return (faults, {row[k]: v for k, v in got.items()} if not faults else {})


def confirm_in(run, text):
    """the confirm look's reply: kept whole as confirm/answer-<k>.txt; each line in the answer form written to
    confirm/confirm.tsv as `Cnn TAB Q1 TAB verdict TAB sentence`, a confirm.tsv there before set aside first.
    (k, answer lines, reply lines)"""
    cf = os.path.join(run, CONFIRM_DIR)
    if not os.path.isdir(cf):
        raise Refused('refused: no %s: run confirm-items first' % cf)
    k = 1
    while os.path.lexists(os.path.join(cf, 'answer-%d.txt' % k)):
        k += 1
    with builtins.open(os.path.join(cf, 'answer-%d.txt' % k), 'wb') as fh:
        fh.write(text.encode('utf-8'))
    got = []
    for l in text.split('\n'):
        m = CONFIRM_ANSWER.match(l)
        if m:
            got.append('%s\tQ1\t%s\t%s' % (m.group(1), m.group(2), ' '.join(m.group(3).split())))
    cp = os.path.join(cf, 'confirm.tsv')
    if os.path.lexists(cp):
        set_aside(cp)
    if got:
        with builtins.open(cp, 'wb') as fh:
            fh.write(('\n'.join(got) + '\n').encode('utf-8'))
    return k, len(got), len([l for l in text.split('\n') if l.strip()])


def confirm_moved(folder):
    """the rows the confirm moved to the questions: (unit, decision, rule) -> the confirm's sentence"""
    lp = os.path.join(folder, 'look.tsv')
    if not os.path.isfile(lp):
        return {}
    return {(c[0], c[1], c[2]): c[4][len(CONFIRM_NOTE):] for _, c, _x in look_lines(lp) if c[3] == 'ask' and c[4].startswith(CONFIRM_NOTE)}


def confirmed_look(run):
    """look.tsv with the confirm look applied: a kept row the confirm says does not hold is a drop, its sentence the
    why-not; cannot tell is an ask with the sentence (draft-in makes its table row a question row); holds stays as the
    look wrote it"""
    ans = confirm_faults(run)[1]
    out = []
    for l in read(os.path.join(run, 'look.tsv')).split('\n'):
        if not l:
            continue
        c = l.split('\t')
        v = ans.get(tuple(c[:3])) if c[3] == 'keep' else None
        if v and v[0] == 'does not hold':
            c = c[:3] + ['drop', CONFIRM_DROP + v[1]]
        elif v and v[0] == 'cannot tell':
            c = c[:3] + ['ask', CONFIRM_NOTE + v[1]] + c[5:]
        out.append('\t'.join(c))
    return '\n'.join(out) + '\n'


def draft_in(run, out, lane=None):
    if os.path.exists(out):
        raise Refused('refused: %s exists; name a fresh folder' % out)
    if lane is None or not HANDOFF:
        raise Refused('refused: draft-in needs --lane and --handoff (it writes the cites)')
    for f in ('decisions.tsv', 'table.tsv'):
        if not os.path.isfile(os.path.join(run, f)):
            raise Refused('refused: the run folder has no %s' % f)
    sp = split_rows(run)
    sk = {(c[0], c[1], c[2]) for c in sp}
    gaps = look_gaps(run, sk)
    if gaps:
        raise Refused('refused: the looks do not cover the table; run the looks on this table:\n' + '\n'.join(gaps))
    keeps = look_keeps(run)
    cfaults = confirm_faults(run)[0] if keeps else []
    if keeps and not os.path.isfile(os.path.join(run, CONFIRM_DIR, 'confirm.tsv')):
        raise Refused('refused: the look keeps %d against rows and the run folder has no %s/confirm.tsv: run confirm-items and the confirm look' % (len(keeps), CONFIRM_DIR))
    if cfaults:
        raise Refused('refused: the confirm look does not answer the kept against rows (confirm-check):\n' + '\n'.join(cfaults))
    qj = {(c[0], c[1], c[2]) for c in qjoin_rows(run)}
    qmiss = [k for k in question_rows(run) if k not in qj]
    if qmiss:
        raise Refused('refused: %d question rows have no line of the question looks; run the question check on this table:\n' % len(qmiss) + '\n'.join(' '.join(k) for k in qmiss[:20]))
    au = audit_rows(run)
    if au is None:
        raise Refused('refused: the run folder has no %s/dirs.tsv; run audit-dirs' % AUDIT_DIR)
    if any(c[0] != '-' for c in au) and lane is None:
        raise Refused('refused: draft-in checks the audit reports against the lane: give --lane')
    bad = [m for c in au if c[0] != '-' for m in audit_report_check(os.path.join(run, AUDIT_DIR), c[0], lane)]
    if bad:
        raise Refused('refused: an audit report fails its check (audit-check):\n' + '\n'.join(bad))
    os.makedirs(out)
    os.makedirs(os.path.join(out, AUDIT_DIR))
    for f in ['dirs.tsv'] + [c[0] + '.md' for c in au if c[0] != '-']:
        with open(os.path.join(run, AUDIT_DIR, f), 'rb') as a, open(os.path.join(out, AUDIT_DIR, f), 'wb') as b:
            b.write(a.read())
    for f in ('decisions.tsv', 'decision-pairs.tsv', 'look.tsv', 'pairs-look.tsv', 'pieces.tsv', SPLIT_FILE, MANIFEST_FILE, QJOIN_FILE):
        if os.path.isfile(os.path.join(run, f)) and not (keeps and f == 'look.tsv'):
            with open(os.path.join(run, f), 'rb') as a, open(os.path.join(out, f), 'wb') as b:
                b.write(a.read())
    wd = []
    for d in sorted(os.listdir(run)):
        if not ASIDE.search(d) and os.path.isfile(os.path.join(run, d, WITHDRAWN_FILE)):
            wd += [[d] + c for c in tsv(os.path.join(run, d, WITHDRAWN_FILE), 6)]
    if wd:
        write(os.path.join(out, WITHDRAWN_FILE), wd)
    if keeps:
        put(os.path.join(out, 'look.tsv'), confirmed_look(run))
        os.makedirs(os.path.join(out, CONFIRM_DIR))
        for f in ('items.tsv', 'confirm.tsv'):
            with open(os.path.join(run, CONFIRM_DIR, f), 'rb') as a, open(os.path.join(out, CONFIRM_DIR, f), 'wb') as b:
                b.write(a.read())
    t = tsv(os.path.join(run, 'table.tsv'), 6)
    write(os.path.join(out, 'table-all.tsv'), t)
    sk = sk | moved_keys(run)
    keep = [c for c in t if (c[1], c[3], c[4]) not in sk]
    mv = confirm_moved(out)
    keep = [c[:2] + ['asks'] + c[3:] if c[2] == 'against' and (c[1], c[3], c[4]) in mv else c for c in keep]
    write(os.path.join(out, 'table.tsv'), keep)
    ft = frames_text(out)
    if ft:
        put(os.path.join(out, FRAMES_FILE), ft + '\n')
    write(os.path.join(out, CITES_FILE), cites(lane))
    return len(t), len(t) - len(keep), len(sp)


def lane_size(lane):
    files = rule_files(lane)
    n = sum(os.path.getsize(os.path.join(lane, f)) for f in files)
    return files, n, n > LARGE_BYTES


def lane_sections(lane):
    pieces = {r[0]: (r[1], r[2], r[3]) for r in cut(lane, 80, 'item')}
    rows, items = sections(lane, pieces)
    return pieces, rows, items


def card_portions(lane, pieces_path, out, cards_path=None):
    full = read_pieces(pieces_path)
    pieces, rows, items = lane_sections(lane)
    if sorted(full.items()) != sorted(pieces.items()):
        raise Refused('refused: pieces.tsv is not the cut of the lane as it stands')
    if cards_path and os.path.isfile(cards_path):
        docs = {r[1] for r in cards_fresh(lane, cards_path)}
    else:
        docs = {r[1] for r in rows}
    if not docs:
        return []
    mine = {k: v for k, v in pieces.items() if v[0] in docs}
    portions = deal(lane, mine, PORTION_BYTES)
    for r in sorted({p[0] for p in portions}, key=lambda x: int(x[1:])):
        f = os.path.join(out, 'portion-%s' % r)
        os.makedirs(f, exist_ok=True)
        ds = {p[1] for p in portions if p[0] == r}
        write(os.path.join(f, 'portion.tsv'), [p for p in portions if p[0] == r])
        sec = [s for s in rows if s[1] in ds]
        ids = {s[0] for s in sec}
        write(os.path.join(f, 'sections.tsv'), sec)
        write(os.path.join(f, 'section-items.tsv'), [i for i in items if i[0] in ids])
        write(os.path.join(f, 'pieces.tsv'), [(k,) + tuple(v) + (h,) for k, v, h in
                                             ((c[0], (c[1], int(c[2]), int(c[3])), c[4]) for c in tsv(pieces_path, 5))
                                             if v[0] in ds])
    return portions


def cards_keep(lane, new_rows, old_path):
    pieces, rows, items = lane_sections(lane)
    keys = card_keys(rows)
    sl = section_lines(pieces, items)
    newk = {tuple(r[1:4]): r for r in new_rows}
    old = read_cards(old_path) if old_path and os.path.isfile(old_path) else {}
    out, cache, miss = [], {}, []
    for r in rows:
        k = keys[r[0]]
        path, lines = sl[r[0]]
        if path not in cache:
            cache[path] = lines_of(lane, path)
        if k in newk:
            out.append((r[0],) + tuple(newk[k][1:]))
        elif k in old and old[k][8] == section_hash(cache[path], lines):
            out.append((r[0],) + tuple(old[k][1:]))
        else:
            miss.append(r[0])
    if miss:
        raise Refused('refused: %d sections have no fresh card: %s' % (len(miss), ', '.join(miss[:10])))
    return out


LOOK_FILES = ('table.tsv', 'decisions.tsv', 'decision-pairs.tsv', 'checks.tsv', 'pairs.tsv', 'pieces.tsv', SUBJECT_FILE)


def look_copy(run, out):
    if not os.path.isfile(os.path.join(run, 'checks.tsv')):
        raise Refused('refused: run `pairs` on the run folder first: no checks.tsv')
    os.makedirs(out, exist_ok=True)
    if os.path.exists(os.path.join(out, 'look.tsv')):
        raise Refused('refused: %s already holds a look.tsv' % out)
    n = 0
    for f in LOOK_FILES:
        if os.path.isfile(os.path.join(run, f)):
            with open(os.path.join(run, f), 'rb') as a, open(os.path.join(out, f), 'wb') as b:
                b.write(a.read())
            n += 1
    return n


import builtins, io
import os as _os

INPUTS_FILE = 'inputs.sha256'
STATUS_FILE = 'status.txt'
READINGS_FILE = 'readings.txt'
NEW_CHAIN_EXIT = 3
LOOK_PART = 60  # pairs a part of the one look (step 8)
ZONE_BUDGET = 92000
OVERLAY = None


def rows_text(rows):
    return ''.join('\t'.join(str(x) for x in r) + '\n' for r in rows)


def disk_bytes(path):
    try:
        with builtins.open(path, 'rb') as fh:
            return fh.read()
    except OSError:
        return None


def set_aside(path):
    k = 1
    while _os.path.lexists('%s.failed-%d' % (path, k)):
        k += 1
    _os.rename(path, '%s.failed-%d' % (path, k))
    return '%s.failed-%d' % (path, k)


def put(path, text):
    """write a file; the same bytes already there: nothing written; other bytes there: that file set aside first"""
    data = text.encode('utf-8')
    if OVERLAY is not None:
        OVERLAY.files[OVERLAY.key(path)] = data
        return
    if _os.path.lexists(path):
        if _os.path.isfile(path) and disk_bytes(path) == data:
            return
        set_aside(path)
    with builtins.open(path, 'wb') as fh:
        fh.write(data)


def write(path, rows):
    put(path, rows_text(rows))


class Overlay(object):
    """a command run for its outputs alone: what it writes is kept in memory; a masked path reads as absent"""
    def __init__(self, masks):
        self.masks = [_os.path.abspath(m) for m in masks]
        self.files, self.dirs = {}, set()

    def key(self, p):
        return _os.path.abspath(p)

    def hidden(self, k):
        if k in self.files or k in self.dirs:
            return False
        return any(k == m or k.startswith(m + _os.sep) for m in self.masks)

    def exists(self, p):
        k = self.key(p)
        return k in self.files or k in self.dirs or (not self.hidden(k) and _os.path.exists(k))

    def isfile(self, p):
        k = self.key(p)
        return k in self.files or (k not in self.dirs and not self.hidden(k) and _os.path.isfile(k))

    def isdir(self, p):
        k = self.key(p)
        return k in self.dirs or (k not in self.files and not self.hidden(k) and _os.path.isdir(k))


class _Kept(object):
    def __init__(self, ov, k, binary, start):
        self.ov, self.k, self.binary, self.buf = ov, k, binary, [start]

    def write(self, s):
        self.buf.append(s if self.binary else s.encode('utf-8'))
        return len(s)

    def close(self):
        self.ov.files[self.k] = b''.join(self.buf)

    def __enter__(self):
        return self

    def __exit__(self, *e):
        self.close()


class _PathShim(object):
    def __init__(self, ov):
        self._ov = ov

    def __getattr__(self, n):
        return getattr(_os.path, n)

    def exists(self, p):
        return self._ov.exists(p)

    def lexists(self, p):
        return self._ov.exists(p)

    def isfile(self, p):
        return self._ov.isfile(p)

    def isdir(self, p):
        return self._ov.isdir(p)

    def getsize(self, p):
        k = self._ov.key(p)
        if k in self._ov.files:
            return len(self._ov.files[k])
        if self._ov.hidden(k):
            raise FileNotFoundError(2, 'No such file or directory', p)
        return _os.path.getsize(k)


class _OsShim(object):
    def __init__(self, ov):
        self._ov, self.path = ov, _PathShim(ov)

    def __getattr__(self, n):
        return getattr(_os, n)

    def makedirs(self, p, exist_ok=False):
        k = self._ov.key(p)
        if self._ov.exists(k):
            if not exist_ok or not self._ov.isdir(k):
                raise FileExistsError(17, 'File exists', p)
            return
        while not self._ov.exists(k):
            self._ov.dirs.add(k)
            k = _os.path.dirname(k)

    def mkdir(self, p, *a, **kw):
        if self._ov.exists(p):
            raise FileExistsError(17, 'File exists', p)
        self._ov.dirs.add(self._ov.key(p))

    def listdir(self, p):
        k = self._ov.key(p)
        if not self._ov.isdir(k):
            raise FileNotFoundError(2, 'No such file or directory', p)
        names = set()
        if not self._ov.hidden(k) and _os.path.isdir(k):
            names |= {n for n in _os.listdir(k) if not self._ov.hidden(_os.path.join(k, n))}
        for x in list(self._ov.files) + list(self._ov.dirs):
            if x.startswith(k + _os.sep):
                names.add(x[len(k) + 1:].split(_os.sep)[0])
        return sorted(names)

    def rename(self, *a, **kw):
        raise Refused('refused: a check moves no file')

    def remove(self, *a, **kw):
        raise Refused('refused: a check removes no file')


def _open_in(ov):
    def op(p, mode='r', *a, **kw):
        k = ov.key(p)
        if any(c in mode for c in 'wax+'):
            start = b''
            if 'a' in mode and ov.isfile(k):
                start = ov.files[k] if k in ov.files else (disk_bytes(k) or b'')
            return _Kept(ov, k, 'b' in mode, start)
        if k in ov.files:
            if 'b' in mode:
                return io.BytesIO(ov.files[k])
            return io.StringIO(ov.files[k].decode(kw.get('encoding') or 'utf-8', kw.get('errors') or 'strict'), newline=None)
        if ov.hidden(k):
            raise FileNotFoundError(2, 'No such file or directory', p)
        return builtins.open(p, mode, *a, **kw)
    return op


def remake(masks, fn, *a, **kw):
    """fn run with its writes kept in memory and the masked paths absent: (result, error, {path: bytes})"""
    global OVERLAY, os
    ov = Overlay(masks)
    g = globals()
    OVERLAY, os = ov, _OsShim(ov)
    g['open'] = _open_in(ov)
    try:
        res, err = fn(*a, **kw), None
    except Exception as e:
        res, err = None, e
    finally:
        OVERLAY, os = None, _os
        g.pop('open', None)
    return res, err, ov.files


def again(targets, fn, *a):
    """a command that writes its outputs once: when they are there and it would write the same bytes, nothing is
    written; when it would write other bytes, the outputs there are set aside first. (result, unchanged)"""
    targets = [_os.path.abspath(t) for t in targets]
    if not any(_os.path.lexists(t) for t in targets):
        return fn(*a), False
    res, err, files = remake(targets, fn, *a)
    if err is not None:
        raise err
    if all(disk_bytes(p) == d for p, d in files.items()):
        return res, True
    for t in targets:
        if _os.path.lexists(t):
            set_aside(t)
    return fn(*a), False


def zone_files(lane, pieces_path, secdir, rl, out, every, budget, within=None):
    lines = []
    if within:
        wl = {c[0] for c in tsv(within, 3)}
        rows = tsv(rl, 3)
        gone = [c for c in rows if c[0] not in wl and (every or c[2] not in ('-', ''))]
        rl = os.path.join(out, 'within-list.tsv')
        os.makedirs(out, exist_ok=True)
        write(rl, [c for c in rows if c[0] in wl])
        lines.append('outside the read list: %d sections left out' % len(gone))
    texts, zp, portions, zp_by, named_by = zone(lane, pieces_path, secdir, rl, 1, every, budget)
    os.makedirs(out, exist_ok=True)
    write(os.path.join(out, 'pieces.tsv'), zp)
    write(os.path.join(out, 'portions.tsv'), portions)
    for r in sorted(texts):
        put(os.path.join(out, 'zone-%s.md' % r), texts[r])
        write(os.path.join(out, 'portion-%s.tsv' % r), zp_by[r])
        lines.append('zone %s: sections %d, items %d, documents %d, bytes %d' % (
            r, sum(1 for l in texts[r].split('\n') if l.startswith('== ')), len(zp_by[r]),
            sum(1 for x in portions if x[0] == r), len(texts[r].encode('utf-8'))))
    if not texts:
        lines.append('zone: no section to read')
    return lines


HOLES_DIR = 'holes'
HOLE_HEAD = 'Hole rows of the zone readings (written by script).'
ASIDE = re.compile(r'\.failed-\d+$')
HOLE_LATER = ('table.tsv', 'checks.tsv', 'pairs.tsv', 'look-a', 'look-b', 'look.tsv', 'pairs-look.tsv', 'split.tsv',
              'qlook-a', 'qlook-b', 'questions.tsv', 'questions-join.tsv', 'draft')


def hole_base(run):
    """the table the hole round reads: table-<K>.tsv of zone-read (no hole round in single-read)"""
    if os.path.isfile(os.path.join(run, JOIN_DIR, 'band.tsv')):
        return os.path.join(run, 'table-0.tsv')
    rec = readings_of(run)
    if rec is None or rec == 'single':
        raise Refused('refused: the hole round is the tail of step 7 in mode zone-read; %s holds %s' % (
            READINGS_FILE, rec or 'nothing'))
    return os.path.join(run, 'table-%s.tsv' % rec)


def hole_sections(run):
    """(sections in cut order, {section: its units in the table, in cut order}, {unit: table rows}); a section is one
    heading of one document (sec/section-items.tsv)"""
    sec_of = {c[1]: c[0] for c in tsv(os.path.join(run, 'sec', 'section-items.tsv'), 2)}
    by = {}
    for c in tsv(hole_base(run), 6):
        by.setdefault(c[1], []).append(c)
    order, members = [], {}
    for c in tsv(os.path.join(run, 'pieces.tsv'), 5):
        if c[0] not in by:
            continue
        if c[0] not in sec_of:
            raise Refused('refused: unit %s has no section in sec/section-items.tsv' % c[0])
        s = sec_of[c[0]]
        if s not in members:
            order.append(s)
            members[s] = []
        members[s].append(c[0])
    return order, members, by


def hole_list(run):
    """(unit, section, decisions): a unit whose table rows are all `none`, in a section where at least two other units
    carry a rule row on one same decision; decisions: those two units or more carry, in id order"""
    order, members, by = hole_sections(run)
    rule = lambda u: {c[3] for c in by.get(u, []) if c[2] != 'none'}
    out = []
    for s in order:
        for u in members[s]:
            if rule(u):
                continue
            cnt = {}
            for w in members[s]:
                if w != u:
                    for d in rule(w):
                        cnt[d] = cnt.get(d, 0) + 1
            ds = sorted((d for d, n in cnt.items() if n >= 2), key=lambda x: int(x[1:]))
            if ds:
                out.append((u, s, ds))
    return out


def hole_files(lane, run, budget=ZONE_BUDGET):
    """holes/holes.md (one block a section), holes/holes-<part>.md (the blocks dealt into parts by the budget, a block
    never cut) and holes/holes.tsv (unit, section, part, decisions); (rows, [(part, holes, sections, bytes)])"""
    holes = hole_list(run)
    order, members, by = hole_sections(run)
    pieces = read_pieces(os.path.join(run, 'pieces.tsv'))
    heads = {c[0]: c for c in tsv(os.path.join(run, 'sec', 'sections.tsv'), 5)}
    head = ['# Holes: units no reading gave a row, in a section where at least two other units carry a rule row on one',
            'same decision', '',
            'One block a section: its heading, the rows the other units of the section carry, then each hole unit with',
            'its lines. Answer each hole unit once in the read file: rows on any decision of decisions.tsv, or one',
            '`none` row.', '']
    hs = {}
    for u, s, ds in holes:
        hs.setdefault(s, []).append((u, ds))
    blocks = []
    for s in order:
        if s not in hs:
            continue
        b = ['== section %s %s | %s' % (s, heads[s][1], heads[s][2])]
        b.append('- rows the other units of the section carry:')
        for w in members[s]:
            for c in by[w]:
                if c[2] != 'none':
                    b.append('- %s %s %s `%s`: %s' % (w, c[2], c[3], c[4], c[5]))
        for u, _ in hs[s]:
            path, x, y = pieces[u]
            ls = lines_of(lane, path)
            b.append('-- hole %s %s:%d-%d' % (u, path, x, y))
            b += ['%d: %s' % (n, ls[n - 1]) for n in range(x, y + 1)]
        b.append('')
        blocks.append((s, '\n'.join(b) + '\n'))
    top = '\n'.join(head) + '\n'
    parts = []
    for s, text in blocks:
        n = len(text.encode('utf-8'))
        if parts and parts[-1][1] + n <= budget:
            parts[-1][0].append((s, text))
            parts[-1][1] += n
        else:
            parts.append([[(s, text)], len(top.encode('utf-8')) + n])
    part_of, info = {}, []
    HD = os.path.join(run, HOLES_DIR)
    os.makedirs(HD, exist_ok=True)
    for k, (bl, size) in enumerate(parts, 1):
        p = 'r%d' % k
        for s, _ in bl:
            part_of[s] = p
        put(os.path.join(HD, 'holes-%s.md' % p), top + ''.join(text for _, text in bl))
        info.append((p, sum(len(hs[s]) for s, _ in bl), len(bl), size))
    rows = [(u, s, part_of[s], ','.join(ds)) for u, s, ds in holes]
    write(os.path.join(HD, 'holes.tsv'), rows)
    put(os.path.join(HD, 'holes.md'), top + ''.join(text for _, text in blocks))
    return rows, info


def holes_in(lane, run, budget=ZONE_BUDGET):
    """holes; when holes/ holds another hole list, holes/ and the outputs made on the table (steps 8, 9 and 11, and
    table.tsv) are set aside first. (rows, part info, unchanged, names set aside)"""
    HD = os.path.join(run, HOLES_DIR)
    aside = []
    if _os.path.lexists(HD):
        res, err, files = remake([HD], hole_files, lane, run, budget)
        if err is not None:
            raise err
        if all(disk_bytes(p) == d for p, d in files.items()):
            return res[0], res[1], True, []
        aside = [_os.path.basename(set_aside(os.path.join(run, f))) for f in (HOLES_DIR,) + HOLE_LATER
                 if _os.path.lexists(os.path.join(run, f))]
    rows, info = hole_files(lane, run, budget)
    return rows, info, False, aside


def hole_fault_parts(holes, faults):
    """the parts a list of hole faults names"""
    part = {c[0]: c[2] for c in holes}
    out = set()
    for f in faults:
        m = re.match(r'^read-(r\d+)(?:\.r2)?\.tsv:', f)
        if m:
            out.add(m.group(1))
        for u in re.findall(r'\b(?:hole|unit) (p\d+)', f):
            if u in part:
                out.add(part[u])
    return sorted(out, key=lambda r: int(r[1:]))


def hole_check(lane, run):
    """(table rows with the hole rows joined, new rows, faults); each part's answers are read from read-<part>.tsv,
    and from read-<part>.r2.tsv for the units that file answers"""
    HD = os.path.join(run, HOLES_DIR)
    holes = tsv(os.path.join(HD, 'holes.tsv'), 4)
    base = tsv(hole_base(run), 6)
    if not holes:
        return base, [], []
    pieces = read_pieces(os.path.join(run, 'pieces.tsv'))
    decs = {c[0] for c in decision_rows(os.path.join(run, 'decisions.tsv'))}
    units = {c[0]: c for c in holes}
    rows, faults = {}, []
    for p in sorted({c[2] for c in holes}, key=lambda r: int(r[1:])):
        got = {}
        for f in ('read-%s.tsv' % p, 'read-%s.r2.tsv' % p):
            path = os.path.join(HD, f)
            if not os.path.isfile(path):
                if f.endswith('.r2.tsv'):
                    continue
                raise Refused('refused: missing input: %s' % path)
            one = {}
            for n, l in enumerate(read(path).split('\n'), 1):
                if not l.strip():
                    continue
                c = l.split('\t')
                one.setdefault(c[0], []).append((f, n, c))
            got.update(one)
        for u, ans in got.items():
            if u in rows:
                faults.append('%s:%d: hole %s: answered in two read files (%s and %s)' % (
                    ans[0][0], ans[0][1], u, rows[u][0][0], ans[0][0]))
                continue
            rows[u] = ans
    cache = {}
    for u, h in units.items():
        ans = rows.get(u, [])
        if not ans:
            faults.append('hole %s: not answered (part %s)' % (u, h[2]))
            continue
        kinds = [c[1] if len(c) == 5 else '?' for _, _, c in ans]
        if 'none' in kinds and len(ans) > 1:
            faults.append('hole %s: a `none` row beside other rows' % u)
        seen = set()
        for f, n, c in ans:
            path, a, b = pieces[u]
            m = re.match(r'^(.+):(\d+)$', c[3]) if len(c) == 5 else None
            if len(c) != 5:
                why = '%d fields, not 5' % len(c)
            elif c[1] not in CLASSES:
                why = 'class %s' % c[1]
            elif c[1] == 'none':
                why = None if c[2:] == ['-', '-', '-'] else 'a none row carries a decision, rule or quote'
            elif c[2] not in decs:
                why = 'decision %s unknown' % c[2]
            elif c[2] in seen:
                why = 'answered twice on %s' % c[2]
            elif not m or m.group(1) != path or not a <= int(m.group(2)) <= b:
                why = 'rule %s is not a line of %s (%s:%d-%d)' % (c[3], u, path, a, b)
            else:
                if path not in cache:
                    cache[path] = lines_of(lane, path)
                q = fold(c[4])
                why = None if len(q) >= MIN_QUOTE and q in fold(cache[path][int(m.group(2)) - 1]) else 'quote not on %s' % c[3]
            seen.add(c[2] if len(c) == 5 else None)
            if why:
                faults.append('%s:%d: hole %s: %s' % (f, n, u, why))
    for u in sorted(set(rows) - set(units), key=lambda x: int(x[1:]) if x[1:].isdigit() else 0):
        faults.append('%s:%d: unit %s is not a hole' % (rows[u][0][0], rows[u][0][1], u))
    if faults:
        return None, [], faults
    out, new = [], []
    for c in base:
        if c[1] in units and c[2] == 'none':
            add = [(c[0], u2, k, d, r, q) for _, _, (u2, k, d, r, q) in rows[c[1]] if k != 'none']
            if add:
                out += add
                new += add
                continue
        out.append(tuple(c))
    return out, new, []


def hole_join(lane, run):
    out, new, faults = hole_check(lane, run)
    if faults:
        put(os.path.join(run, HOLES_DIR, 'faults.txt'), '\n'.join('fault: ' + f for f in faults) + '\n')
        return None, new, faults
    write(os.path.join(run, 'table.tsv'), out)
    return out, new, []


LATER = re.compile(r'^(read-1|readings\.txt|pass-\d+|passes|zsec-\d+|zone-\d+|table(-\d+)?\.tsv|holes|checks\.tsv|pairs\.tsv'
                   r'|look-[ab]|look\.tsv|pairs-look\.tsv|split\.tsv|qlook-[ab]|questions(-join)?\.tsv|audit|draft)$')


MADE_ON_FILE = 'made-on.tsv'


def made_on(lane, run):
    """what read-1 is made on: the decision list, the kinds file and both card sets of the lane, each by sha256"""
    cards = os.path.join(lane, docs_root(lane), INDEX_DIR)
    return rows_text([(n, hashlib.sha256(need_bytes(p)).hexdigest()) for n, p in (
        ('decisions.tsv', os.path.join(run, 'decisions.tsv')), ('kinds.tsv', os.path.join(run, 'kinds.tsv')),
        ('cards-a.tsv', os.path.join(cards, 'cards-a.tsv')), ('cards-b.tsv', os.path.join(cards, 'cards-b.tsv')))])


def later_aside(run):
    """every output of steps 6 to 11 in the chain folder set aside (<name>.failed-<k>); the names set aside"""
    return [os.path.basename(set_aside(os.path.join(run, f))) for f in sorted(os.listdir(run)) if LATER.match(f)]


def read1_new(lane, run):
    z = os.path.join(run, 'read-1')
    os.makedirs(z, exist_ok=True)
    for name, data in (('decisions.tsv', need_bytes(os.path.join(run, 'decisions.tsv'))),
                       (MADE_ON_FILE, made_on(lane, run).encode('utf-8'))):
        with builtins.open(os.path.join(z, name), 'wb') as fh:
            fh.write(data)


def decisions_in(run, lane='.'):
    """step 5's entry: the decision list into read-1, with made-on.tsv (the hashes of the list, the kinds file and both
    card sets). read-1 made on another list, kinds file or card set, or with no made-on.tsv: every output of steps 6
    to 11 in the chain folder is set aside first (<name>.failed-<k>), so each later step is made again.
    (names set aside, unchanged)"""
    z = os.path.join(run, 'read-1')
    stamp = made_on(lane, run).encode('utf-8')
    if (disk_bytes(os.path.join(z, 'decisions.tsv')) == need_bytes(os.path.join(run, 'decisions.tsv'))
            and disk_bytes(os.path.join(z, MADE_ON_FILE)) == stamp):
        return [], True
    aside = later_aside(run)
    read1_new(lane, run)
    return aside, False


def zone_in(lane, pieces_path, secdir, rl, out, every, budget, within=None):
    """zone; into a chain's read-1 (its folder holds the hash record) that holds read files or later outputs, a zone
    other than the one there first sets aside every output of steps 6 to 11 and starts read-1 again.
    (zone's lines, names set aside)"""
    o = os.path.abspath(out)
    run = os.path.dirname(o)
    aside = []
    if os.path.basename(o) == 'read-1' and os.path.isfile(os.path.join(run, INPUTS_FILE)) and os.path.isdir(o):
        _, err, files = remake([o], zone_files, lane, pieces_path, secdir, rl, out, every, budget, within)
        if err is None:
            extra = [f for f in os.listdir(o) if re.match(r'^(zone-r\d+\.md|portion-r\d+\.tsv)$', f)
                     and os.path.join(o, f) not in files]
            diff = [q for q in files if disk_bytes(q) != files[q]]
            later = [f for f in os.listdir(run) if LATER.match(f) and f != 'read-1'] + [f for f in os.listdir(o) if f.startswith('read-r') and not ASIDE.search(f)]
            if (diff or extra) and later:
                aside = later_aside(run)
                read1_new(lane, run)
    return zone_files(lane, pieces_path, secdir, rl, out, every, budget, within), aside


def need_bytes(path):
    b = disk_bytes(path)
    if b is None:
        raise Refused('refused: missing input: %s' % path)
    return b


def input_hashes(lane, cut_rows=None):
    """the record of step 1: the handoff, every rule document, the cut and this script, each by sha256"""
    if not HANDOFF:
        raise Refused('refused: the hash record needs --handoff')
    sha = lambda b: hashlib.sha256(b).hexdigest()
    if cut_rows is None:
        cut_rows = cut(lane, 80, 'item')
    rows = [('handoff', HANDOFF, sha(need_bytes(_os.path.join(lane, HANDOFF))))]
    rows += [('rule', f, sha(need_bytes(_os.path.join(lane, f)))) for f in rule_files(lane)]
    rows.append(('cut', 'pieces.tsv', sha(rows_text(cut_rows).encode('utf-8'))))
    rows.append(('script', _os.path.basename(__file__), sha(need_bytes(_os.path.abspath(__file__)))))
    return rows


def inputs_changed(old, now):
    get = lambda rows, kind: [(c[1], c[2]) for c in rows if c[0] == kind]
    oh, nh = get(old, 'handoff'), get(now, 'handoff')
    if [x[0] for x in oh] != [x[0] for x in nh]:
        return 'the handoff is another file (%s; the chain was made for %s)' % (
            ', '.join(x[0] for x in nh), ', '.join(x[0] for x in oh) or 'none')
    if oh != nh:
        return 'the handoff changed since step 1: %s' % nh[0][0]
    orl, nrl = dict(get(old, 'rule')), dict(get(now, 'rule'))
    for f in sorted(set(orl) | set(nrl), key=walk_key):
        if f not in nrl:
            return 'a rule document is gone since step 1: %s' % f
        if f not in orl:
            return 'a rule document was added since step 1: %s' % f
        if orl[f] != nrl[f]:
            return 'a rule document changed since step 1: %s' % f
    if get(old, 'cut') != get(now, 'cut'):
        return 'the cut of the lane differs from the cut at step 1'
    return None


class _Stop(Exception):
    def __init__(self, step, kind, why):
        Exception.__init__(self, why)
        self.step, self.kind, self.why = step, kind, why


def readings_value(v):
    if v != 'single' and not (v.isdigit() and int(v) >= 1):
        raise Refused('refused: readings takes a whole number, 1 or more, or `single`, not: %s' % v)
    return v


def readings_record(run, v):
    put(_os.path.join(run, READINGS_FILE), readings_value(v) + '\n')
    return v


def readings_of(run):
    p = _os.path.join(run, READINGS_FILE)
    if not _os.path.isfile(p):
        return None
    v = open(p, encoding='utf-8').read().strip()
    readings_value(v)
    return v


def status(lane, run, readings=None, single=False, budget=ZONE_BUDGET, hint=None):
    """(first line, run-first commands, notes, exit): `go on at <k>`, `blocked at <k>: ...`, `done` or `new chain: ...`;
    every check runs with its writes kept in memory: status writes nothing"""
    if not _os.path.isdir(run):
        return 'new chain: no chain folder %s' % run, [], [], NEW_CHAIN_EXIT
    rec = _os.path.join(run, INPUTS_FILE)
    if not _os.path.isfile(rec):
        return ('new chain: no hash record (%s): the folder was made before step 1 wrote one' % INPUTS_FILE, [], [],
                NEW_CHAIN_EXIT)
    old = tsv(rec, 3)
    cut_rows = cut(lane, 80, 'item')
    why = inputs_changed(old, input_hashes(lane, cut_rows))
    if why:
        return 'new chain: ' + why, [], [], NEW_CHAIN_EXIT
    rec = readings_of(run)
    if rec is not None:
        if (rec == 'single') != bool(single) and (single or readings is not None):
            raise Refused('refused: the chain was read in mode %s (%s); start a new chain to change it' % (
                'single-read' if rec == 'single' else 'zone-read K = ' + rec, READINGS_FILE))
        if rec != 'single' and readings is not None and readings != int(rec):
            raise Refused('refused: --readings %d: the chain holds K = %s (%s); start a new chain to change it' % (
                readings, rec, READINGS_FILE))
        single, readings = rec == 'single', (int(rec) if rec != 'single' else 1)
    elif readings is None:
        readings = 2
    notes, first = [], []
    if [c[2] for c in old if c[0] == 'script'] != [c[2] for c in input_hashes(lane, cut_rows) if c[0] == 'script']:
        notes.append('the script changed since step 1: every check below ran under this script')
    try:
        _steps(lane, run, cut_rows, readings, single, budget, hint, notes, first)
    except _Stop as s:
        notes.append('step %d: %s' % (s.step, s.why))
        if s.kind == 'blocked':
            return 'blocked at %d: %s' % (s.step, s.why), first, notes, 1
        return 'go on at %d' % s.step, first, notes, 0
    return 'done', first, notes, 0


def _steps(lane, run, cut_rows, readings, single, budget, hint, notes, first):
    J = _os.path.join
    rel = lambda p: _os.path.relpath(p, lane).replace(_os.sep, '/')
    eff, stale_tables = {}, []

    def go(k, why):
        raise _Stop(k, 'go', why)

    def same(p, data):
        return disk_bytes(p) == (data if isinstance(data, bytes) else data.encode('utf-8'))

    def chk(fn, *a):
        res, err, _ = remake([], fn, *a)
        if err is not None:
            raise err
        return res

    def kept(k, masks, fn, *a):
        """fn's outputs made again in memory equal the files there; the list of the files that differ"""
        res, err, files = remake(masks, fn, *a)
        if err is not None:
            go(k, '%s refused: %s' % (fn.__name__, ' '.join(str(err).split())))
        return res, files, [rel(p) for p in sorted(files) if disk_bytes(p) != files[p]]

    def round2(k, out, faults, why):
        if _os.path.isfile(faults) and _os.path.isfile(out) and _os.stat(out).st_mtime_ns > _os.stat(faults).st_mtime_ns:
            raise _Stop(k, 'blocked', '%s; its return round is on record (%s)' % (why, rel(faults)))
        go(k, why)

    def reading(k, z):
        parts = sorted({c[0] for c in tsv(J(z, 'portions.tsv'), 4)}, key=lambda r: int(r[1:]))
        miss = [r for r in parts if not _os.path.isfile(J(z, 'read-%s.tsv' % r))]
        if miss:
            go(k, '%s: no read file for %s' % (rel(z), ', '.join(miss)))
        res, files, diff = kept(k, [], coverage, lane, z)
        n, g, b = res
        if g:
            gl = files.get(_os.path.abspath(J(z, 'gaps.tsv')), b'').decode('utf-8').split('\n')
            gp = sorted({l.split('\t')[0] for l in gl if l})
            done2 = [r for r in gp if _os.path.isfile(J(z, 'read-%s.r2.tsv' % r))]
            if gp and len(done2) == len(gp):
                raise _Stop(k, 'blocked', '%s: coverage open gaps %d after the return round' % (rel(z), g))
            go(k, '%s: coverage open gaps %d; the return round of %s' % (rel(z), g, ', '.join(r for r in gp if r not in done2)))
        if diff:
            first.append('coverage . %s' % rel(z))
            t = _os.path.abspath(J(z, 'table.tsv'))
            eff[t] = files[t]
            if disk_bytes(t) != files[t]:
                stale_tables.append(rel(z))
        notes.append('%s: read files %d, coverage open gaps 0%s' % (rel(z), len(parts), '; run first: coverage' if diff else ''))

    def table_of(p):
        return eff.get(_os.path.abspath(p), disk_bytes(p))

    def zone_ok(k, out, *a):
        _, files, diff = kept(k, [out], zone_files, lane, *a)
        extra = [f for f in sorted(_os.listdir(out)) if re.match(r'^(zone-r\d+\.md|portion-r\d+\.tsv)$', f)
                 and _os.path.abspath(J(out, f)) not in files] if _os.path.isdir(out) else []
        if diff or extra:
            go(k, '%s is not what zone writes: %s' % (rel(out), ', '.join(diff + extra)))

    def s1():
        if not same(J(run, 'pieces.tsv'), rows_text(cut_rows)):
            go(1, 'pieces.tsv is not the cut of the lane')

    def s2():
        cards = J(lane, docs_root(lane), INDEX_DIR)
        for x in 'ab':
            cf = J(cards, 'cards-%s.tsv' % x)
            if not _os.path.isfile(cf):
                go(2, 'no %s' % rel(cf))
            if chk(cards_fresh, lane, cf):
                go(2, '%s is not fresh' % rel(cf))

    def s3():
        cards = J(lane, docs_root(lane), INDEX_DIR)
        rows, bad = chk(cards_agree, lane, J(cards, 'cards-a.tsv'), J(cards, 'cards-b.tsv'))
        if bad or not same(J(run, 'kinds.tsv'), rows_text(rows)):
            go(3, 'kinds.tsv is not what cards-agree writes')

    def s4():
        dp = J(run, 'decisions.tsv')
        if not _os.path.isfile(dp):
            go(4, 'no decisions.tsv: the lister')
        docs = sorted({c[1] for c in tsv(J(run, 'pieces.tsv'), 5)})
        try:
            n, bad = chk(check_decisions, J(lane, HANDOFF), run, docs)
        except Exception as e:
            n, bad = 0, [' '.join(str(e).split())]
        if bad:
            round2(4, dp, J(run, 'decisions-faults.txt'), 'the decisions check: faults %d' % len(bad))

    def s5():
        z, dec = J(run, 'read-1'), need_bytes(J(run, 'decisions.tsv'))
        if not same(J(z, 'decisions.tsv'), dec):
            go(5, 'read-1/decisions.tsv is not decisions.tsv (decisions-in)')
        if not same(J(z, MADE_ON_FILE), made_on(lane, run)):
            go(5, 'read-1 was made on another decision list, kinds file or card set (%s; decisions-in)' % MADE_ON_FILE)
        pieces = read_pieces(J(run, 'pieces.tsv'))
        rows, items = chk(sections, lane, pieces)
        if not (same(J(run, 'sec', 'sections.tsv'), rows_text(rows)) and same(J(run, 'sec', 'section-items.tsv'), rows_text(items))):
            go(5, 'sec/ is not what sections writes')
        sec = need_bytes(J(run, 'sec', 'sections.tsv'))
        rev = rows_text(reverse_docs(tsv(J(run, 'sec', 'sections.tsv'), 5))).encode('utf-8')
        for p, want in (('pass-1', sec), ('pass-2', rev)):
            P = J(run, p)
            if not (same(J(P, 'sections.tsv'), want) and same(J(P, 'decisions.tsv'), dec)):
                go(5, '%s is not made: sections.tsv and decisions.tsv' % p)
            if not _os.path.isfile(J(P, 'subjects.tsv')):
                go(5, '%s: no subjects.tsv (the heading pass)' % p)
            try:
                bad = chk(subjects, P)[2]
            except Exception as e:
                bad = [' '.join(str(e).split())]
            if bad:
                round2(5, J(P, 'subjects.tsv'), J(P, 'subjects-faults.txt'), '%s: the subjects check: faults %d' % (p, len(bad)))
        P3 = J(run, PASS3)
        if not _os.path.isdir(P3):
            go(5, 'no %s (pair-silent)' % PASS3)
        if kept(5, [P3], pair_silent, run)[2]:
            go(5, '%s/sections.tsv or decisions.tsv is not what pair-silent writes' % PASS3)
        if not _os.path.isfile(J(P3, 'subjects.tsv')):
            go(5, '%s: no subjects.tsv (the silence pass)' % PASS3)
        if not _os.path.isfile(J(P3, ROUNDS_FILE)):
            go(5, '%s: no %s (pass-3 --round 1)' % (PASS3, ROUNDS_FILE))
        try:
            zone_, band, left = chk(tiers, run)
        except Exception as e:
            go(5, 'the silence pass is not closed: %s' % ' '.join(str(e).split()))
        audit(5)
        if not (same(J(run, JOIN_DIR, 'zone.tsv'), rows_text(zone_)) and same(J(run, JOIN_DIR, 'band.tsv'), rows_text(band))
                and same(J(run, JOIN_DIR, 'left-out.tsv'), rows_text(left))):
            go(5, '%s/ is not what tiers writes' % JOIN_DIR)

    def s6():
        if readings_of(run) is None:
            go(6, 'no readings record (%s): step 6 starts with `readings`' % READINGS_FILE)
        sec = need_bytes(J(run, 'sec', 'sections.tsv'))
        rev = rows_text(reverse_docs(tsv(J(run, 'sec', 'sections.tsv'), 5))).encode('utf-8')
        items, dec = need_bytes(J(run, 'sec', 'section-items.tsv')), need_bytes(J(run, 'decisions.tsv'))
        for t, want, lst in (('zone-1', sec, 'zone.tsv'), ('zone-2', rev, 'zone.tsv'), ('band-1', sec, 'band.tsv')):
            zs, z = J(run, 'zsec-' + t), J(run, t)
            if not (same(J(zs, 'sections.tsv'), want) and same(J(zs, 'section-items.tsv'), items)):
                go(6, 'zsec-%s is not made' % t)
            zone_ok(6, z, J(run, 'pieces.tsv'), zs, J(run, JOIN_DIR, lst), z, True, budget)
            if not same(J(z, 'decisions.tsv'), dec):
                go(6, '%s/decisions.tsv is not decisions.tsv' % t)
            reading(6, z)

    def s7():
        if stale_tables:
            go(7, 'the tables are joined again on what coverage writes now: %s' % ', '.join(stale_tables))
        if not same(J(run, 'table-0.tsv'), rows_text(chk(tier_join, run)[0])):
            go(7, 'table-0.tsv is not what tier-join writes')
        HD = J(run, HOLES_DIR)  # the hole round
        _, files, diff = kept(7, [HD], hole_files, lane, run, budget)
        if not _os.path.isfile(J(HD, 'holes.tsv')) or diff:
            go(7, 'holes/ is not what holes writes (the hole round)')
        hl = tsv(J(HD, 'holes.tsv'), 4)
        hp = sorted({c[2] for c in hl}, key=lambda r: int(r[1:]))
        miss = [p for p in hp if not _os.path.isfile(J(HD, 'read-%s.tsv' % p))]
        if miss:
            go(7, 'holes: %d holes in %d parts, no read file for %s (the hole readers)' % (len(hl), len(hp), ', '.join(miss)))
        out, _, faults = chk(hole_check, lane, run)
        if faults:
            fp, fl = hole_fault_parts(hl, faults), J(HD, 'faults.txt')
            r2 = [J(HD, 'read-%s.r2.tsv' % p) for p in fp]
            if fp and _os.path.isfile(fl) and all(_os.path.isfile(r) and _os.stat(r).st_mtime_ns > _os.stat(fl).st_mtime_ns for r in r2):
                raise _Stop(7, 'blocked', 'holes: the hole check: faults %d; its return round is on record (%s)' % (len(faults), rel(fl)))
            go(7, 'holes: the hole check: faults %d; the return round of %s' % (len(faults), ', '.join(fp) or 'every part'))
        if not same(J(run, 'table.tsv'), rows_text(out)):
            go(7, 'table.tsv is not what hole-join writes')
        bad = chk(tier_line_check, run)[0]
        if bad:
            raise _Stop(7, 'blocked', 'line-check: sections without a line %d' % len(bad))

    def s8():
        if kept(8, [J(run, SUBJECT_FILE)], subject_pairs, lane, run)[2]:
            go(8, '%s is not what pairs-subject writes' % SUBJECT_FILE)
        res, files, diff = kept(8, [J(run, 'checks.tsv'), J(run, 'pairs.tsv'), J(run, 'look.tsv')], pairs, run)
        if diff:
            go(8, 'checks.tsv or pairs.tsv is not what pairs writes')
        if res[0] == 0:
            notes.append('step 8: against rows 0, no look')
            return
        L, P = J(run, 'look-a'), J(run, 'look-a', 'parts')
        if not _os.path.isdir(L):
            go(8, 'no look-a')
        if kept(8, [J(L, f) for f in LOOK_FILES + ('look.tsv',)], look_copy, run, L)[2]:
            go(8, 'look-a is not what look-copy writes')
        if not _os.path.isdir(P):
            go(8, 'no look-a/parts')
        _, files, diff = kept(8, [P], deal_pairs, L, P, LOOK_PART)
        if diff:
            go(8, 'look-a/parts is not what pairs-deal --cap %d writes: %s' % (LOOK_PART, ', '.join(diff[:5])))
        names = sorted({_os.path.relpath(f, P).split(_os.sep)[0] for f in files}, key=lambda s: int(s[5:]))
        miss = [n for n in names if not _os.path.isfile(J(P, n, 'look.tsv'))]
        if miss:
            go(8, 'look-a: no look.tsv in %s' % ', '.join(miss))
        for n in names:
            try:
                bad = chk(pairs, J(P, n), lane)[2]
            except Exception as e:
                bad = [' '.join(str(e).split())]
            if bad:
                round2(8, J(P, n, 'look.tsv'), J(P, n, 'pairs-faults.txt'), 'look-a/parts/%s: the pairs check: faults %d' % (n, len(bad)))
        if not _os.path.isfile(J(L, 'look.tsv')):
            go(8, 'look-a: the parts are not merged')
        if kept(8, [J(L, 'look.tsv'), J(L, 'pairs-look.tsv')], merge_pairs, L, P)[2]:
            go(8, 'look-a/look.tsv is not what pairs-merge writes')
        if chk(pairs, L, lane)[2]:
            raise _Stop(8, 'blocked', 'look-a: the merged look fails the pairs check')
        for f in ('look.tsv', 'pairs-look.tsv'):
            if disk_bytes(J(run, f)) != need_bytes(J(L, f)):
                go(8, '%s is not look-a/%s' % (f, f))
        if chk(pairs, run, lane)[2]:
            raise _Stop(8, 'blocked', 'the run folder with the look fails the pairs check')
        if not chk(look_keeps, run):
            notes.append('step 8: kept rows 0, no confirm look')
            return
        C = J(run, CONFIRM_DIR)
        if not _os.path.isdir(C):
            go(8, 'no %s (confirm-items)' % CONFIRM_DIR)
        if kept(8, [C], confirm_items, run, lane, J(lane, HANDOFF))[2]:
            go(8, '%s/ items are not what confirm-items writes' % CONFIRM_DIR)
        if not _os.path.isfile(J(C, 'confirm.tsv')):
            go(8, 'no %s/confirm.tsv: the confirm look (confirm-in)' % CONFIRM_DIR)
        bad = chk(confirm_faults, run)[0]
        if bad:
            round2(8, J(C, 'confirm.tsv'), J(C, 'confirm-faults.txt'), 'the confirm check: faults %d' % len(bad))

    def s9():
        q = chk(question_rows, run)
        if not same(J(run, QUESTIONS_FILE), rows_text(q)):
            go(9, 'questions.tsv is not what questions writes')
        if not q:
            notes.append('step 9: questions 0, no question look')
            return
        qs, dec = need_bytes(J(run, QUESTIONS_FILE)), need_bytes(J(run, 'decisions.tsv'))
        for x, who in (('a', 'A'), ('b', 'B')):
            Q, P = J(run, 'qlook-' + x), J(run, 'qlook-%s' % x, 'parts')
            if not (same(J(Q, QUESTIONS_FILE), qs) and same(J(Q, 'decisions.tsv'), dec)):
                go(9, 'qlook-%s is not made' % x)
            if not _os.path.isdir(P):
                go(9, 'no qlook-%s/parts' % x)
            _, files, diff = kept(9, [P], deal_questions, run, P, QUESTION_PART, x == 'b')
            if diff:
                go(9, 'qlook-%s/parts is not what questions-deal writes' % x)
            names = sorted({_os.path.relpath(f, P).split(_os.sep)[0] for f in files}, key=lambda s: int(s[5:]))
            miss = [n for n in names if not _os.path.isfile(J(P, n, QLOOK_FILE))]
            if miss:
                go(9, 'qlook-%s: no qlook.tsv in %s' % (x, ', '.join(miss)))
            for n in names:
                try:
                    bad = chk(question_check, J(P, n), who, lane)[1]
                except Exception as e:
                    bad = [' '.join(str(e).split())]
                if bad:
                    round2(9, J(P, n, QLOOK_FILE), J(P, n, 'qlook-faults.txt'), 'qlook-%s/parts/%s: the question check: faults %d' % (x, n, len(bad)))
            if not _os.path.isfile(J(Q, QLOOK_FILE)):
                go(9, 'qlook-%s: the parts are not merged' % x)
            if kept(9, [J(Q, QLOOK_FILE)], merge_questions, Q, P)[2]:
                go(9, 'qlook-%s/qlook.tsv is not what questions-merge writes' % x)
        rows = chk(question_join, J(run, 'qlook-a'), J(run, 'qlook-b'), lane)
        if not same(J(run, QJOIN_FILE), rows_text(rows)):
            go(9, 'questions-join.tsv is not what question-join writes')

    def audit(k):  # the code audit: run inside step 5, checked again at step 10
        A = J(run, AUDIT_DIR)
        if not _os.path.isfile(J(A, 'dirs.tsv')):
            go(k, 'no audit/dirs.tsv')
        _, files, diff = kept(k, [A, J(run, 'table.tsv')], audit_dirs, lane, run, hint,
                            None if hint is not None else handoff_root(lane))  # made before the table (step 5)
        if diff:
            go(k, 'audit/ is not what audit-dirs writes: %s' % ', '.join(diff))
        ids = [c[0] for c in tsv(J(A, 'dirs.tsv'), 6) if c[0] != '-']
        miss = [i for i in ids if not _os.path.isfile(J(A, i + '.md'))]
        if miss:
            go(k, 'no audit report %s' % ', '.join(miss))
        for i in ids:
            try:
                bad = chk(audit_report_check, A, i, lane)
            except Exception as e:
                bad = [' '.join(str(e).split())]
            if bad:
                round2(k, J(A, i + '.md'), J(A, i + '-faults.txt'), 'audit %s: faults %d' % (i, len(bad)))

    def s10():
        audit(10)

    def s11():
        D = J(run, 'draft')
        if not _os.path.isdir(D):
            go(11, 'no draft folder')
        if kept(11, [D], draft_in, run, D, lane)[2]:
            go(11, 'draft/ is not what draft-in writes')
        if not _os.path.isfile(J(D, 'scope.md')):
            go(11, 'no draft/scope.md: the drafter')
        if kept(11, [], trace, D)[2]:
            go(11, 'draft/scope.md does not end with what trace writes')
        try:
            lost = chk(carried, D, True)[1]
        except Exception as e:
            lost = [' '.join(str(e).split())]
        if lost:
            round2(11, J(D, 'scope.md'), J(D, 'carried-faults.txt'), 'carried: faults %d' % len(lost))

    for k, fn in enumerate((s1, s2, s3, s4, s5, s6, s7, s8, s9, s10, s11), 1):
        try:
            fn()
        except _Stop:
            raise
        except Exception as e:
            go(k, 'its check could not run: %s' % ' '.join(str(e).split()))
        notes.append('step %d: passes' % k)


SILENT_FAULT = 'section %s has no line: neither touched nor out'


def pass_lines(folder, kinds_path):
    """(subjects faults, silent rule sections, outs, touched) of one pass; the rule sections are kinds.tsv's"""
    no, nt, bad, outs, touched = subjects(folder)
    ids = [r[0] for r in read_sections(folder)]
    k = {c[0]: c for c in tsv(kinds_path, 4)}
    if sorted(k) != sorted(ids):
        raise Refused('refused: the kinds are not the sections of %s' % folder)
    silent = [s for s in ids if k[s][1] != 'no-rule' and s not in outs and s not in touched]
    return bad, silent, outs, touched


def pass_check(folder, kinds_path, net=False):
    bad, silent, outs, touched = pass_lines(folder, kinds_path)
    faults = bad + [SILENT_FAULT % s for s in silent]
    if not net:
        return faults, silent
    if bad:
        return bad, silent
    if silent and not os.path.isfile(os.path.join(folder, 'subjects-faults.txt')):
        raise Refused('refused: %d sections are silent and the pass has no subjects-faults.txt: the return round '
                      'has not run' % len(silent))
    write(os.path.join(folder, 'net.tsv'), [(s,) for s in silent])
    return [], silent


def select(run):
    secs = read_sections(os.path.join(run, 'sec'))
    kp = os.path.join(run, 'kinds.tsv')
    k = {c[0]: c for c in tsv(kp, 4)}
    res = []
    for p in ('pass-1', 'pass-2'):
        f = os.path.join(run, p)
        bad, silent, outs, touched = pass_lines(f, kp)
        if bad:
            raise Refused('refused: %s fails the subjects check (%d faults)' % (p, len(bad)))
        np_ = os.path.join(f, 'net.tsv')
        if not os.path.isfile(np_):
            raise Refused('refused: %s has no net.tsv: run pass-check --net first' % p)
        net = [c[0] for c in tsv(np_, 1)]
        if sorted(net) != sorted(silent):
            raise Refused('refused: %s/net.tsv is not the silent sections of the pass' % p)
        res.append((outs, touched, set(net), out_line(f, outs)))
    if sorted(r[0] for r in read_sections(os.path.join(run, 'pass-1'))) != sorted(r[0] for r in secs):
        raise Refused('refused: the passes do not list the sections of sec/')
    selected, left = [], []
    for r in secs:
        s = r[0]
        if k[s][1] == 'no-rule':
            left.append((s, k[s][2], k[s][3]))
        elif any(s in x[1] or s in x[2] for x in res):
            ds = sorted({d for x in res for _, dd in x[1].get(s, []) for d in dd}, key=lambda d: int(d[1:]) if d[1:].isdigit() else 0)
            selected.append((s, r[4], ','.join(ds) or '-'))
        elif all(s in x[0] for x in res):
            left.append((s, res[0][3][s], res[1][3][s]))
    have = {x[0] for x in selected} | {x[0] for x in left}
    miss = [r[0] for r in secs if r[0] not in have]
    if miss:
        raise Refused('refused: sections in neither selected.tsv nor left-out.tsv: %s' % ', '.join(miss))
    return selected, left, sum(len(x[2]) for x in res)


def by_size(rows):
    """documents by their largest section's item count, largest first (cut order on a tie); a document's sections
    stay together in cut order, since the zone deals whole documents"""
    docs, big = [], {}
    for r in rows:
        if r[1] not in big:
            docs.append(r[1])
        big[r[1]] = max(big.get(r[1], 0), int(r[4]))
    order = sorted(range(len(docs)), key=lambda i: (-big[docs[i]], i))
    return [r for i in order for r in rows if r[1] == docs[i]]


def line_check(run):
    secs = read_sections(os.path.join(run, 'sec'))
    items = {}
    for s, p in tsv(os.path.join(run, 'sec', 'section-items.tsv'), 2):
        items.setdefault(s, []).append(p)
    k = {c[0]: c for c in tsv(os.path.join(run, 'kinds.tsv'), 4)}
    left = {c[0] for c in tsv(os.path.join(run, 'join', 'left-out.tsv'), 3)}
    units = {c[1] for c in tsv(os.path.join(run, 'table.tsv'), 6)}
    faults, n_left, n_read = [], 0, 0
    for r in secs:
        s = r[0]
        if s in left:
            n_left += 1
            continue
        if k[s][1] == 'no-rule':
            faults.append('section %s has no line: a no-rule section not in left-out.tsv' % s)
            continue
        miss = [p for p in items.get(s, []) if p not in units]
        if miss or not items.get(s):
            faults.append('section %s has no line: items with no row and no none in table.tsv: %s' % (s, ', '.join(miss) or 'no item'))
        else:
            n_read += 1
    return faults, n_left, n_read, len(secs)


JOIN_DIR = 'join'
PASS3 = 'pass-3'
ROUNDS_FILE = 'rounds.tsv'
MAX_ROUNDS = 3


def card_lines(run):
    out = {}
    for c in tsv(os.path.join(run, 'kinds.tsv'), 4):
        out[c[0]] = fold(c[2]) or fold(c[3])
    return out


def kinds_of(run):
    return {c[0]: c[1] for c in tsv(os.path.join(run, 'kinds.tsv'), 4)}


def pass_rows(run, f):
    no, nt, bad, outs, touched = subjects(os.path.join(run, f))
    if bad:
        raise Refused('refused: %s fails the subjects check (%d faults)' % (f, len(bad)))
    return outs, touched


def heading_silent(run):
    """the rule sections with no touched and no out row of pass-1 or pass-2, in cut order"""
    secs = read_sections(os.path.join(run, 'sec'))
    kinds = kinds_of(run)
    said = set()
    for f in ('pass-1', 'pass-2'):
        outs, touched = pass_rows(run, f)
        said |= set(outs) | set(touched)
    for r in secs:
        if r[0] not in kinds:
            raise Refused('refused: section %s is not in kinds.tsv' % r[0])
    return [r for r in secs if kinds[r[0]] == 'rule' and r[0] not in said], secs, kinds


def pair_silent(run):
    p3 = os.path.join(run, PASS3)
    if os.path.lexists(p3):
        raise Refused('refused: %s exists; the silence pass runs once a chain' % p3)
    silent, secs, kinds = heading_silent(run)
    cards = card_lines(run)
    d1, d2 = (read(os.path.join(run, f, 'decisions.tsv')) for f in ('pass-1', 'pass-2'))
    if d1 != d2:
        raise Refused('refused: pass-1 and pass-2 have different decisions.tsv')
    rows = []
    for r in silent:
        if not cards.get(r[0]):
            raise Refused('refused: section %s has no card line' % r[0])
        rows.append(list(r[:5]) + [cards[r[0]]])
    os.makedirs(p3)
    write(os.path.join(p3, 'sections.tsv'), rows)
    put(os.path.join(p3, 'decisions.tsv'), d1)
    return rows, len([r for r in secs if kinds.get(r[0]) == 'rule'])


def pass3_round(run, k):
    """(rows, rows of the round before, silent sections, other faults, the stop reason or None); writes the round's
    line in pass-3/rounds.tsv (a check of the same round again replaces its line)"""
    p3 = os.path.join(run, PASS3)
    if not os.path.isdir(p3):
        raise Refused('refused: no %s; run pair-silent first' % p3)
    rf = os.path.join(p3, ROUNDS_FILE)
    done = tsv(rf, 4) if os.path.isfile(rf) else []
    last = int(done[-1][0]) if done else 0
    if k not in (last, last + 1) or (k == last and k == 0):
        raise Refused('refused: round %d after round %d: the rounds go 1, 2, 3 in order' % (k, last))
    if k == last:
        done = done[:-1]
    no, nt, bad, outs, touched = subjects(p3)
    silent = [r[0] for r in read_sections(p3) if r[0] not in outs and r[0] not in touched]
    prev = int(done[-1][1]) if done else None
    halt = None
    if prev is not None and no + nt <= prev:
        halt = 'round %d added no row (rows %d; round %d: %d): a fault, not a round' % (k, no + nt, k - 1, prev)
    elif (bad or silent) and k == MAX_ROUNDS:
        halt = 'silent after %d rounds: %d sections with no row, %d other faults' % (MAX_ROUNDS, len(silent), len(bad))
    write(rf, done + [(str(k), str(no + nt), str(len(silent)), str(len(bad)))])
    return no + nt, prev, silent, bad, halt


def by_id(ds):
    return sorted(ds, key=lambda d: int(d[1:]) if d[1:].isdigit() else 0)


def tiers(run):
    p3 = os.path.join(run, PASS3)
    rf = os.path.join(p3, ROUNDS_FILE)
    if not os.path.isfile(rf):
        raise Refused('refused: no %s/%s: run the silence pass and pass-3 --round first' % (PASS3, ROUNDS_FILE))
    no, nt, bad, outs3, touched3 = subjects(p3)
    listed = [r[0] for r in read_sections(p3)]
    silent = [s for s in listed if s not in outs3 and s not in touched3]
    if bad or silent:
        raise Refused('refused: pass-3 has %d sections with no row and %d other faults: the silence pass is not closed' % (
            len(silent), len(bad)))
    if int(tsv(rf, 4)[-1][1]) != no + nt:
        raise Refused('refused: pass-3/subjects.tsv holds %d rows, its last round %s: it changed after the last round' % (
            no + nt, tsv(rf, 4)[-1][1]))
    want, secs, kinds = heading_silent(run)
    if [r[0] for r in want] != listed:
        raise Refused('refused: pass-3/sections.tsv is not the silent set of pass-1 and pass-2 (%d listed, %d silent)' % (
            len(listed), len(want)))
    cards = card_lines(run)
    heads = []
    for f in ('pass-1', 'pass-2'):
        outs, t = pass_rows(run, f)
        heads.append((f, outs, t, out_line(os.path.join(run, f), outs)))
    ol3 = out_line(p3, outs3)
    zone_, band, left = [], [], []
    for r in secs:
        s = r[0]
        if kinds[s] == 'no-rule':
            if not cards.get(s):
                raise Refused('refused: section %s has no card line' % s)
            left.append((s, 'card %s' % cards[s]))
        elif any(s in h[2] for h in heads):
            zone_.append((s, r[4], ','.join(by_id({d for h in heads for _, dd in h[2].get(s, []) for d in dd}))))
        elif s in touched3:
            band.append((s, r[4], ','.join(by_id({d for _, dd in touched3[s] for d in dd}))))
        else:
            ls = ['%s out %s' % (f, ol[s]) for f, o, _, ol in heads if s in o]
            if s in outs3:
                ls.append('%s out %s' % (PASS3, ol3[s]))
            if not ls:
                raise Refused('refused: rule section %s has no line of any pass' % s)
            left.append((s, '; '.join(ls)))
    return zone_, band, left


def tier_join(run):
    out, t1, new, skipped = table_join(os.path.join(run, 'zone-1', 'table.tsv'), os.path.join(run, 'zone-2', 'table.tsv'))
    tb = tsv(os.path.join(run, 'band-1', 'table.tsv'), 6)
    zu = {c[1] for c in t1}
    clash = sorted({c[1] for c in tb if c[1] in zu})
    if clash:
        raise Refused('refused: band-1 units are units of the zone: %s' % ', '.join(clash[:20]))
    return [tuple(c) for c in out] + [tuple(c) for c in tb], sum(len(v) for v in new.values()), skipped, len(tb)


def tier_line_check(run):
    secs = read_sections(os.path.join(run, 'sec'))
    items = {}
    for s, p in tsv(os.path.join(run, 'sec', 'section-items.tsv'), 2):
        items.setdefault(s, []).append(p)
    kinds, cards = kinds_of(run), card_lines(run)
    left = {c[0]: c[1] for c in tsv(os.path.join(run, JOIN_DIR, 'left-out.tsv'), 2)}
    outs = set()
    for f in ('pass-1', 'pass-2', PASS3):
        outs |= set(pass_rows(run, f)[0])
    units = {c[1] for c in tsv(os.path.join(run, 'table.tsv'), 6)}
    faults, n_left, n_read = [], 0, 0
    for r in secs:
        s = r[0]
        if s in left:
            if kinds[s] == 'no-rule' and left[s].startswith('card ') and cards.get(s):
                n_left += 1
            elif kinds[s] != 'no-rule' and re.match(r'^pass-[123] out ', left[s]) and s in outs:
                n_left += 1
            else:
                faults.append('section %s has no line: left out on %s, not %s' % (
                    s, left[s][:60], 'its card line' if kinds[s] == 'no-rule' else 'an out line of a pass'))
            continue
        if kinds[s] == 'no-rule':
            faults.append('section %s has no line: a no-rule section not in left-out.tsv' % s)
            continue
        miss = [p for p in items.get(s, []) if p not in units]
        if miss or not items.get(s):
            faults.append('section %s has no line: items with no row and no none in table.tsv: %s' % (s, ', '.join(miss) or 'no item'))
        else:
            n_read += 1
    return faults, n_left, n_read, len(secs)


def main(argv):
    global HANDOFF
    opt, rest = {}, []
    i = 0
    while i < len(argv):
        if argv[i] in ('--d-items', '--fill', '--all', '--reverse', '--single-read', '--mandatory', '--net', '--selected'):
            opt[argv[i]] = True
            i += 1
        elif argv[i].startswith('--'):
            if i + 1 >= len(argv):
                print('refused: %s takes a value' % argv[i])
                return 2
            opt[argv[i]] = argv[i + 1]
            i += 2
        else:
            rest.append(argv[i])
            i += 1
    if not rest:
        print(__doc__)
        return 2
    cmd, a = rest[0], [os.path.realpath(os.path.abspath(x)) for x in rest[1:]]
    ab = lambda k: os.path.realpath(os.path.abspath(opt[k]))
    if '--handoff' in opt:
        HANDOFF = os.path.relpath(ab('--handoff'), ab('--lane')).replace(os.sep, '/') if '--lane' in opt else \
            os.path.relpath(ab('--handoff'), a[0]).replace(os.sep, '/') if cmd in ('audit-dirs', 'cites') and a else opt['--handoff']
    try:
        if cmd == 'size' and not a and '--lane' in opt:
            npaths, _, loose, extra, text = manifest(ab('--lane'))
            files, n, big = lane_size(ab('--lane'))
            if not mounts_declared(ab('--lane')):
                print('mounts: default, no %s: %s' % (MOUNTS_KEY, ', '.join(default_mounts(ab('--lane')))))
                print('scope-mounts: none declared, %d default paths; not read: %s' % (npaths, ', '.join(loose) or 'none'))
            else:
                print('scope-mounts: %d paths declared; not read: %s' % (npaths, ', '.join(loose) or 'none'))
            if extra:
                print('added for this handoff: %s' % ', '.join(extra))
            if '--manifest' in opt:
                put(ab('--manifest'), text)
            print('rule documents: %d, %d bytes, about %d tokens; size: %s (the line is %d bytes)' % (
                len(files), n, n // 4, 'large' if big else 'small', LARGE_BYTES))
            return 0
        if cmd == 'questions' and len(a) == 1:
            rows = question_rows(a[0])
            write(os.path.join(a[0], QUESTIONS_FILE), rows)
            print('questions %d' % len(rows))
            return 0
        if cmd == 'questions-deal' and len(a) == 2:
            cap = opt.get('--cap', str(QUESTION_PART))
            if not str(cap).isdigit() or int(cap) < 1:
                raise Refused('refused: --cap takes a whole number, 1 or more')
            res, same = again([a[1]], deal_questions, a[0], a[1], int(cap), '--reverse' in opt)
            for name, ds, n in res:
                print('%s: decisions %s; questions %d' % (name, ', '.join(ds), n))
            if same:
                print('unchanged: %s holds what this command writes' % a[1])
            return 0
        if cmd == 'question-check' and len(a) == 1:
            if '--lane' not in opt or '--handoff' not in opt or '--look' not in opt:
                raise Refused('refused: question-check needs --look A|B, --lane and --handoff')
            n, faults = question_check(a[0], opt['--look'], os.path.realpath(os.path.abspath(opt['--lane'])))
            print('question look %s: rows %d, faults %d' % (opt['--look'], n, len(faults)))
            for m in faults:
                print(m)
            return 1 if faults else 0
        if cmd == 'questions-merge' and len(a) == 2:
            res, same = again([os.path.join(a[0], QLOOK_FILE)], merge_questions, a[0], a[1])
            print('questions-merge: parts %d, lines %d%s' % (res + ('; unchanged' if same else '',)))
            return 0
        if cmd == 'question-join' and len(a) == 3:
            if '--lane' not in opt or '--handoff' not in opt:
                raise Refused('refused: question-join needs --lane and --handoff')
            rows = question_join(a[0], a[1], os.path.realpath(os.path.abspath(opt['--lane'])))
            write(a[2], rows)
            print('question-join: rows %d, rules %d, same %d, not to bear %d, questions %d, one look %d' % (len(rows), sum(r[3] == 'rules' for r in rows),
                  sum(r[3] == 'same' for r in rows), sum(r[3] == 'notbear' for r in rows), sum(r[3] == 'question' for r in rows),
                  sum(r[3] == 'onelook' for r in rows)))
            return 0
        if cmd == 'audit-dirs' and len(a) == 2:
            if '--handoff' not in opt:
                raise Refused('refused: audit-dirs needs --handoff')
            hr = None if opt.get('--hint') is not None else handoff_root(a[0])
            if hr is not None:
                rel = lambda x: os.path.relpath(x, a[0]).replace(os.sep, '/')
                print('handoff root: %s (%s)' % (rel(hr[0]), 'registry %s, rows %d' % (rel(hr[2]), len(hr[1])) if hr[2] else 'no registry'))
            rows, same = again([os.path.join(a[1], AUDIT_DIR)], audit_dirs, a[0], a[1], opt.get('--hint'), hr)
            if same:
                print('unchanged: %s holds what this command writes' % os.path.join(a[1], AUDIT_DIR))
            if not rows:
                print('audit: no directory named; no audit runs')
            for c in rows:
                print('%s\t%s\t%s\t%s\tfiles %s\tbytes %s' % tuple(c))
            return 0
        if cmd == 'audit-check' and len(a) == 2:
            lane = os.path.realpath(os.path.abspath(opt['--lane'])) if '--lane' in opt else os.getcwd()
            if '--handoff' not in opt:
                HANDOFF = recorded_handoff(os.path.dirname(a[0]))  # step 10 runs it without --handoff
            faults = audit_report_check(a[0], os.path.basename(a[1]), lane)
            print('audit %s: faults %d' % (os.path.basename(a[1]), len(faults)))
            for m in faults:
                print('fault: ' + m)
            return 1 if faults else 0
        if cmd == 'cites' and len(a) == 2:
            if '--handoff' not in opt:
                raise Refused('refused: cites needs --handoff')
            rows = cites(a[0])
            write(a[1], rows)
            n = lambda s: sum(1 for c in rows if c[7] == s)
            print('cites %d: match %d, mismatch %d, ambiguous %d, no-item %d, no-file %d, no-words %d' % (
                len(rows), n('match'), n('mismatch'), n('ambiguous'), n('no-item'), n('no-file'), n('no-words')))
            for c in rows:
                if c[7] in CITE_CARRY:
                    print('%s\t%s\t%s #%s\t%s' % (c[0], c[1], c[2], c[3], c[7]))
            return 0
        if cmd == 'draft-in' and len(a) == 2:
            (n, out, sp), same = again([a[1]], draft_in, a[0], a[1], ab('--lane') if '--lane' in opt else None)
            print('draft-in: table rows %d, split rows out %d (split.tsv rows %d)%s' % (n, out, sp, '; unchanged' if same else ''))
            return 0
        if cmd == 'cut' and len(a) == 2:
            rows = cut(a[0], 80, 'item')
            rec = os.path.join(os.path.dirname(a[1]), INPUTS_FILE)
            now = input_hashes(a[0], rows) if '--handoff' in opt else None
            if now is not None and os.path.isfile(rec):
                why = inputs_changed(tsv(rec, 3), now)
                if why:
                    raise Refused('refused: %s; this chain folder stands as it is: start a new one' % why)
            write(a[1], rows)
            print('pieces %d of %d files' % (len(rows), len({r[1] for r in rows})))
            if now is not None and not os.path.isfile(rec):
                write(rec, now)
                print('hash record: %s (handoff, rule documents %d, cut, script)' % (INPUTS_FILE, sum(r[0] == 'rule' for r in now)))
            return 0
        if cmd == 'status' and len(a) == 2:
            if '--handoff' not in opt:
                raise Refused('refused: status needs --handoff')
            k, b = opt.get('--readings', '2'), opt.get('--budget', str(ZONE_BUDGET))
            if not k.isdigit() or int(k) < 1 or not b.isdigit() or int(b) < 1:
                raise Refused('refused: --readings and --budget take a whole number, 1 or more')
            if '--readings' in opt and '--single-read' in opt:
                raise Refused('refused: --readings and --single-read go apart')
            line, first, notes, code = status(a[0], a[1], int(k) if '--readings' in opt else None, '--single-read' in opt,
                                              int(b), opt.get('--hint'))
            text = '\n'.join([line] + ['run first: ' + x for x in first] + notes) + '\n'
            if os.path.isdir(a[1]):
                with builtins.open(os.path.join(a[1], STATUS_FILE), 'w', encoding='utf-8', newline='\n') as fh:
                    fh.write(text)
            print(text, end='')
            return code
        if cmd == 'decisions-in' and len(a) == 1:
            aside, same = decisions_in(a[0], opt.get('--lane', '.'))
            print('decisions-in: %s' % ('unchanged' if same else 'read-1/decisions.tsv and read-1/%s written' % MADE_ON_FILE))
            if aside:
                print('a new decision list, kinds file or card set: the outputs of steps 6 to 11 set aside: %s' % ', '.join(aside))
            return 0
        if cmd == 'holes' and len(a) == 2:
            bud = opt.get('--budget', str(ZONE_BUDGET))
            if not bud.isdigit() or int(bud) < 1:
                raise Refused('refused: --budget takes a positive number of bytes')
            holes, info, same, aside = holes_in(a[0], a[1], int(bud))
            if aside:
                print('another hole list: set aside: %s' % ', '.join(aside))
            print('holes %d (sections %d, parts %d)%s' % (len(holes), len({h[1] for h in holes}), len(info), '; unchanged' if same else ''))
            for p, nh, ns, nb in info:
                print('part %s: holes %d, sections %d, bytes %d' % (p, nh, ns, nb))
            if not holes:
                print('no hole: run hole-join; no reader call')
            return 0
        if cmd == 'hole-join' and len(a) == 2:
            out, new, faults = hole_check(a[0], a[1])
            if faults:
                put(os.path.join(a[1], HOLES_DIR, 'faults.txt'), '\n'.join('fault: ' + f for f in faults) + '\n')
                print('hole-join: faults %d (%s)' % (len(faults), os.path.join(a[1], HOLES_DIR, 'faults.txt')))
                for f in faults:
                    print('fault: ' + f)
                return 1
            res, same = again([os.path.join(a[1], 'table.tsv')], hole_join, a[0], a[1])
            kinds = {}
            for c in new:
                kinds[c[2]] = kinds.get(c[2], 0) + 1
            print('hole-join: holes %d, new rows %d (%s), table rows %d%s' % (
                len(tsv(os.path.join(a[1], HOLES_DIR, 'holes.tsv'), 4)), len(new),
                ', '.join('%s %d' % x for x in sorted(kinds.items())) or 'none', len(out), '; unchanged' if same else ''))
            return 0
        if cmd == 'readings':
            if len(a) != 2:
                raise Refused('refused: readings takes <chain folder> and <K | single>')
            v = readings_value(rest[2])
            res, same = again([os.path.join(a[0], READINGS_FILE)], readings_record, a[0], v)
            print('readings: %s%s' % (res, '; unchanged' if same else ''))
            return 0
        if cmd == 'sections' and len(a) == 3:
            pieces = read_pieces(a[1])
            rows, items = sections(a[0], pieces)
            bad = check_sections(pieces, rows, items)
            if bad:
                print('refused: ' + '; '.join(bad[:5]))
                return 2
            if '--cards' in opt:
                stale = cards_fresh(a[0], ab('--cards'))
                if stale:
                    print('refused: %d sections have no fresh card (cards-fresh)' % len(stale))
                    return 2
                rows = with_cards(rows, ab('--cards'))
            os.makedirs(a[2], exist_ok=True)
            write(os.path.join(a[2], 'sections.tsv'), rows)
            write(os.path.join(a[2], 'section-items.tsv'), items)
            print('sections %d of %d documents, items %d' % (len(rows), len({r[1] for r in rows}), len(items)))
            return 0
        if cmd == 'card-portions' and len(a) == 3:
            ps = card_portions(a[0], a[1], a[2], ab('--cards') if '--cards' in opt else None)
            if not ps:
                print('nothing to card')
                return 0
            for r in sorted({p[0] for p in ps}, key=lambda x: int(x[1:])):
                rs = [p for p in ps if p[0] == r]
                print('portion-%s\tdocuments %d\tbytes %d' % (r, len(rs), sum(p[2] for p in rs)))
            return 0
        if cmd == 'cards' and len(a) == 1:
            n, bad = check_cards(ab('--lane') if '--lane' in opt else os.getcwd(), a[0])
            print('cards: rows %d, faults %d' % (n, len(bad)))
            for b in bad:
                print('fault: ' + b)
            return 1 if bad else 0
        if cmd == 'cards-join' and len(a) >= 3:
            rows = cards_join(a[0], a[2:])
            if '--keep' in opt:
                rows = cards_keep(a[0], rows, ab('--keep'))
            write(a[1], rows)
            kinds = {}
            for r in rows:
                kinds[r[4]] = kinds.get(r[4], 0) + 1
            print('cards: %d sections; %s' % (len(rows), ', '.join('%s %d' % x for x in sorted(kinds.items()))))
            return 0
        if cmd == 'cards-fresh' and len(a) == 2:
            out = cards_fresh(a[0], a[1])
            print('cards-fresh: %d sections to card again' % len(out))
            for r in out:
                print('\t'.join(r))
            return 1 if out else 0
        if cmd == 'cards-agree' and len(a) == 4:
            rows, bad = cards_agree(a[0], a[1], a[2])
            if bad:
                print('cards-agree: faults %d' % len(bad))
                for b in bad:
                    print('fault: ' + b)
                return 1
            os.makedirs(a[3], exist_ok=True)
            write(os.path.join(a[3], 'kinds.tsv'), rows)
            print('cards-agree: sections %d; rule %d, no-rule %d (both builds)' % (
                len(rows), sum(r[1] == 'rule' for r in rows), sum(r[1] == 'no-rule' for r in rows)))
            return 0
        if cmd == 'decisions' and len(a) == 2:
            docs = sorted({c[1] for c in tsv(ab('--docs'), 5)}) if '--docs' in opt else None
            n, bad = check_decisions(a[0], a[1], docs)
            print('decisions %d, faults %d' % (n, len(bad)))
            for b in bad:
                print('fault: ' + b)
            return 1 if bad else 0
        if cmd == 'readlist' and len(a) == 2 and '--cards' in opt:
            rl, lo, n = readlist(a[0], ab('--cards'))
            os.makedirs(a[1], exist_ok=True)
            write(os.path.join(a[1], 'read-list.tsv'), rl)
            write(os.path.join(a[1], 'left-out.tsv'), lo)
            nr = sum(int(r[1]) for r in rl)
            print('read list: sections %d of %d, items %d of %d (share %.4f); left out %d' % (
                len(rl), len(rl) + len(lo), nr, n, nr / n if n else 0, len(lo)))
            return 0
        if cmd == 'zone' and len(a) == 5:
            if not opt.get('--budget', '').isdigit() or int(opt['--budget']) < 1:
                print('refused: --budget takes a positive number of bytes')
                return 2
            if '--selected' in opt and ('--all' in opt or '--within' in opt or os.path.basename(a[3]) not in ('selected.tsv', 'zone.tsv', 'band.tsv')):
                print('refused: --selected takes a selected.tsv, zone.tsv or band.tsv, without --all or --within')
                return 2
            lines, aside = zone_in(a[0], a[1], a[2], a[3], a[4], '--all' in opt or '--selected' in opt, int(opt['--budget']),
                                   ab('--within') if '--within' in opt else None)
            for l in lines:
                print(l)
            if aside:
                print('a zone other than the one read: the outputs of steps 6 to 11 set aside: %s' % ', '.join(aside))
            return 0
        if cmd == 'coverage' and len(a) == 2:
            n, g, b = coverage(a[0], a[1])
            print('coverage: good rows %d, bad rows %d, open gaps %d' % (n, b, g))
            print('withdrawn rule rows: %d (%s)' % (len(tsv(os.path.join(a[1], WITHDRAWN_FILE), 6)), WITHDRAWN_FILE))
            return 0 if g == 0 else 1
        if cmd == 'reverse' and len(a) == 2:
            rows = reverse_docs(tsv(a[0], 5))
            write(a[1], rows)
            print('sections %d, documents in reverse order' % len(rows))
            return 0
        if cmd == 'subjects' and len(a) == 1:
            if '--fill' in opt:
                miss = fill_open(a[0])
                print('filled open %d: %s' % (len(miss), ', '.join(miss)))
            no, nt, bad, outs, touched = subjects(a[0])
            ev = os.path.isfile(os.path.join(a[0], EVERY))
            print('subjects: out rows %d (sections out %d), touched rows %d, %sfaults %d' % (
                no, len(outs), nt, 'open rows %d, ' % sum(len(v) for v in opens(a[0]).values()) if ev else '', len(bad)))
            for b in bad:
                print('fault: ' + b)
            return 1 if bad else 0
        if cmd == 'join' and len(a) == 3:
            rl, left = join(a[0], a[1])
            os.makedirs(a[2], exist_ok=True)
            write(os.path.join(a[2], 'read-list.tsv'), rl)
            write(os.path.join(a[2], 'left-out.tsv'), left)
            ni, nr = sum(int(r[4]) for r in read_sections(a[0])), sum(int(r[1]) for r in rl)
            print('read list: sections %d of %d, items %d of %d (share %.4f); left out %d' % (
                len(rl), len(rl) + len(left), nr, ni, nr / ni if ni else 0, len(left)))
            return 0
        if cmd == 'table-join' and len(a) == 3:
            out, t1, new, skipped = table_join(a[0], a[1])
            write(a[2], out)
            nr = [c for v in new.values() for c in v]
            cls = {}
            for c in nr:
                cls[c[2]] = cls.get(c[2], 0) + 1
            print('table-join: first rows other than none %d, new rows other than none %d (%s) on %d units; '
                  'second rows on a unit that has a row %d (not taken)' % (
                      sum(c[2] != 'none' for c in t1), len(nr), ', '.join('%s %d' % x for x in sorted(cls.items())),
                      len(new), skipped))
            return 0
        if cmd == 'pairs' and len(a) == 1:
            n, p, faults = pairs(a[0], ab('--lane') if '--lane' in opt else None)
            print('against rows %d, pairs %d, faults %d' % (n, p, len(faults)))
            for m in faults:
                print(m)
            return 1 if faults else 0
        if cmd == 'confirm-items' and len(a) == 2:
            if '--handoff' not in opt:
                raise Refused('refused: confirm-items needs --handoff <handoff>')
            n, same = again([os.path.join(a[0], CONFIRM_DIR, f) for f in ('items.tsv',)], confirm_items, a[0], a[1], ab('--handoff'))
            print('confirm-items: items %d%s' % (n, '; unchanged' if same else ''))
            return 0
        if cmd == 'confirm-in' and len(a) == 1:
            k, n, nl = confirm_in(a[0], sys.stdin.buffer.read().decode('utf-8'))
            print('confirm-in: the reply kept as %s/answer-%d.txt (lines %d); answer lines %d; %s' % (
                CONFIRM_DIR, k, nl, n, 'confirm.tsv written' if n else 'no answer line: no confirm.tsv'))
            return 0
        if cmd == 'confirm-check' and len(a) == 1:
            faults, ans = confirm_faults(a[0])
            print('confirm-check: kept rows %d, answers %d, faults %d' % (len(look_keeps(a[0])), len(ans), len(faults)))
            for m in faults:
                print('fault: ' + m)
            return 1 if faults else 0
        if cmd == 'pairs-subject' and len(a) == 2:
            res, same = again([os.path.join(a[1], SUBJECT_FILE)], subject_pairs, a[0], a[1])
            print('pairs-subject: pairs %d, kept %d%s' % (res + ('; unchanged' if same else '',)))
            return 0
        if cmd == 'pairs-deal' and len(a) == 2:
            cap = opt.get('--cap', str(PART_PAIRS))
            if not str(cap).isdigit() or int(cap) < 1:
                raise Refused('refused: --cap takes a whole number, 1 or more')
            res, same = again([a[1]], deal_pairs, a[0], a[1], int(cap))
            for name, ds, n, p in res:
                print('%s: decisions %s; against rows %d; pairs %d' % (name, ', '.join(ds), n, p))
            if same:
                print('unchanged: %s holds what this command writes' % a[1])
            return 0
        if cmd == 'pairs-merge' and len(a) == 2:
            res, same = again([os.path.join(a[0], 'look.tsv'), os.path.join(a[0], 'pairs-look.tsv')], merge_pairs, a[0], a[1])
            print('pairs-merge: parts %d, look lines %d, pairs-look lines %d%s' % (res + ('; unchanged' if same else '',)))
            return 0
        if cmd == 'look-copy' and len(a) == 2:
            res, same = again([os.path.join(a[1], f) for f in LOOK_FILES + ('look.tsv',)], look_copy, a[0], a[1])
            print('look-copy: %d files%s' % (res, '; unchanged' if same else ''))
            return 0
        if cmd == 'look-join' and len(a) == 3:
            if '--lane' not in opt or '--handoff' not in opt:
                raise Refused('refused: look-join needs --lane and --handoff')
            if '--split' not in opt:
                raise Refused('refused: look-join needs --split <file> for the rows the looks split on')
            n = []
            for who, f in (('look A', a[0]), ('look B', a[1])):
                if not os.path.isfile(os.path.join(f, 'look.tsv')):
                    raise Refused('refused: %s has no look.tsv' % who)
                _, _, faults = pairs(f, ab('--lane'))
                if faults:
                    raise Refused('refused: %s did not pass the pairs check: %s' % (who, '; '.join(faults)))
                n.append(len(faults))
            print('pairs check: look A faults %d, look B faults %d' % tuple(n))
            rows = look_join(os.path.join(a[0], 'look.tsv'), os.path.join(a[1], 'look.tsv'))
            write(a[2], [r for r in rows if r[3] != 'split'])
            write(ab('--split'), [r for r in rows if r[3] == 'split'])
            print('look-join: rows %d, keep %d, drop %d, ask %d, split %d, moved %d' % (
                len(rows), sum(r[3] == 'keep' for r in rows), sum(r[3] == 'drop' for r in rows),
                sum(r[3] == 'ask' for r in rows), sum(r[3] == 'split' for r in rows), sum(len(r) > 5 for r in rows)))
            return 0
        if cmd == 'trace' and len(a) == 1:
            print('trace: %d rows written to scope.md' % trace(a[0]))
            return 0
        if cmd == 'pass-check' and len(a) == 1:
            if '--mandatory' not in opt or '--kinds' not in opt:
                print('refused: pass-check takes --mandatory and --kinds <kinds.tsv>')
                return 2
            faults, silent = pass_check(a[0], ab('--kinds'), '--net' in opt)
            if '--net' in opt and not faults:
                print('net: sections %d (silent after the return round, to be read)' % len(silent))
                return 0
            print('pass-check: silent rule sections %d, faults %d' % (len(silent), len(faults)))
            for f in faults:
                print('fault: ' + f)
            return 1 if faults else 0
        if cmd == 'select' and len(a) == 1:
            sel, left, nn = select(a[0])
            os.makedirs(os.path.join(a[0], 'join'), exist_ok=True)
            write(os.path.join(a[0], 'join', 'selected.tsv'), sel)
            write(os.path.join(a[0], 'join', 'left-out.tsv'), left)
            print('select: selected sections %d (items %d; net rows of both passes %d; no decision named %d), left out %d' % (
                len(sel), sum(int(x[1]) for x in sel), nn, sum(1 for x in sel if x[2] == '-'), len(left)))
            return 0
        if cmd == 'by-size' and len(a) == 2:
            rows = by_size(tsv(a[0], 5))
            write(a[1], rows)
            print('sections %d, documents by their largest section, largest first' % len(rows))
            return 0
        if cmd == 'pair-silent' and len(a) == 1:
            rows, nr = pair_silent(a[0])
            print('silence pass: rule sections %d, silent %d (no touched and no out row of pass-1 or pass-2), '
                  'listed in %s/sections.tsv with their card lines' % (nr, len(rows), PASS3))
            return 0
        if cmd == 'pass-3' and len(a) == 1:
            if '--round' not in opt or '--net' in opt or '--check' in opt:
                print('refused: pass-3 takes --round <1 | 2 | 3> (no net: rounds until no section is silent)')
                return 2
            if opt['--round'] not in ('1', '2', '3'):
                print('refused: --round takes 1, 2 or 3 (at most %d rounds)' % MAX_ROUNDS)
                return 2
            k = int(opt['--round'])
            nrows, prev, silent, bad, halt = pass3_round(a[0], k)
            print('pass-3 round %d: rows %d (round before: %s), silent %d, faults %d' % (
                k, nrows, '-' if prev is None else prev, len(silent), len(bad) + len(silent)))
            for b in bad:
                print('fault: ' + b)
            for s in silent:
                print('fault: section %s has no row: neither touched nor out' % s)
            if halt:
                print('STOP: ' + halt)
                return 3
            return 1 if bad or silent else 0
        if cmd == 'tiers' and len(a) == 1:
            zone_, band, left = tiers(a[0])
            os.makedirs(os.path.join(a[0], JOIN_DIR), exist_ok=True)
            write(os.path.join(a[0], JOIN_DIR, 'zone.tsv'), zone_)
            write(os.path.join(a[0], JOIN_DIR, 'band.tsv'), band)
            write(os.path.join(a[0], JOIN_DIR, 'left-out.tsv'), left)
            nrl = sum(1 for c in left if not c[1].startswith('card '))
            print('tiers: zone sections %d, items %d; band sections %d, items %d; left out %d (rule %d on an out line, '
                  'no-rule %d on the card line)' % (len(zone_), sum(int(c[1]) for c in zone_), len(band),
                                                     sum(int(c[1]) for c in band), len(left), nrl, len(left) - nrl))
            return 0
        if cmd == 'tier-join' and len(a) == 1:
            out, nnew, skipped, nb = tier_join(a[0])
            write(os.path.join(a[0], 'table-0.tsv'), out)
            print('tier-join: table-0.tsv rows %d: zone-1 stands, units filled from zone-2 %d (zone-2 rows on units with a '
                  'row %d not taken), band-1 rows %d' % (len(out), nnew, skipped, nb))
            return 0
        if cmd == 'line-check' and len(a) == 1:
            faults, nl, nr, n = (tier_line_check if os.path.isfile(os.path.join(a[0], JOIN_DIR, 'band.tsv')) else line_check)(a[0])
            print('line-check: sections %d: left out %d, read whole %d, without a line %d' % (n, nl, nr, len(faults)))
            for f in faults:
                print('fault: ' + f)
            return 1 if faults else 0
        if cmd == 'carried' and len(a) == 1:
            c, lost, dn = carried(a[0], '--d-items' in opt)
            print('rows carried: %d in the trace, %d faults' % (c, len(lost)))
            if dn is not None:
                print(('d items %d (against %d, asks %d, question %d)' if dn[3] else 'd items %d (against %d, asks %d)') % (dn if dn[3] else dn[:3]))
            for l in lost:
                print(l)
            return 1 if lost else 0
    except NoMounts as e:
        print(e)
        return NO_MOUNTS_EXIT
    except Refused as e:
        print(e)
        return 2
    except FileNotFoundError as e:
        print('refused: missing input: %s' % (e.filename or ' '.join(str(e).split())))
        return 2
    except Exception as e:
        print('refused: %s: %s' % (type(e).__name__, ' '.join(str(e).split())))
        return 2
    print(__doc__)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
