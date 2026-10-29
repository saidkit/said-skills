"""said:board, the backlog board: the backlog file's entries as an outline of cards, or as cards by section, stage or priority.

A board is one page module over one thing. This one renders the view model `said_backlog.board_view()` builds,
the same model `said_backlog.py --board backlog` prints as text and `--json`, so the page and the terminal carry
the same numbers. It writes nothing (the add button posts to the one writer); every string goes through `esc`. One fragment carries every entry once, in
the shape of the chosen view, with its sheet as a hidden template; the toolbar, the filter row and the folds are
the shared list client (lists.js), which hides what the filters leave out. A card's stage is the reader's own.
"""
import datetime
import os

import said_backlog
from serve import esc  # the shell's helper
from boards import lists as L

VIEWS = ("outline", "section", "stage", "priority")
VIEW_LABEL = {"outline": "Outline", "section": "By section", "stage": "By stage", "priority": "By priority"}
STATE_WORD = {"open": "open", "wip": "in progress", "done": "done"}
STAGE_COLOR = {"Entry": "var(--st-entry)", "Record": "var(--st-record)", "Promoted": "var(--st-promoted)"}
STAGE_ORDER = CHAIN = ("Entry", "Record", "Promoted")
RANK = {"A": 0, "B": 1, "C": 2}


def stage_color(stage):
    return STAGE_COLOR.get(stage, "var(--st-entry)")


def mark(row):
    return row["feature"] or row["record"]


def formed(row):
    return bool(row["record"] or row["feature"])


def chain_at(row):
    return 2 if row["feature"] else 1 if row["record"] else 0


def notes(row):
    """The entry's own notes: a sub-bullet that is only the record or feature link is the mark, not a note."""
    out = []
    for note in row.get("notes") or []:
        n = note["text"]
        label = n[1:n.find("]")] if n.startswith("[") and n.endswith(")") and "](" in n else ""
        if label and (label == row["record"] or label == row["feature"] or (row["feature"] and label.startswith(row["feature"]))):
            continue
        out.append(note)
    return out


def _note_list(ns, edit=False):
    """The notes as nested lists, one level per depth (a note never skips a level); the sheet's carry the editor's
    attributes, except a note with a link in it, which is read-only."""
    html, depth = [], -1
    for n in ns:
        d = min(n["depth"], depth + 1)
        while depth > d:
            html.append("</li></ul>")
            depth -= 1
        if depth == d:
            html.append("</li>")
        else:
            html.append('<ul class="subs">')
            depth += 1
        if edit and "](" not in n["text"] and L.editable(n["raw"]):
            html.append('<li class="sub" %s><span class="nt" tabindex="0" role="button" title="click to edit">%s</span>'
                        '<button type="button" class="nx" %s aria-label="remove this note" title="remove">x</button>'
                        % (L.ed_attrs("note", n["line"], n["raw"], value=n["text"]), L.inline(n["text"]), L.ed_attrs("note-del", n["line"], n["raw"])))
        else:
            html.append('<li class="sub">%s' % L.inline(n["text"]))
    html.append("</li></ul>" * (depth + 1))
    return "".join(html)


def words(row):
    return " ".join(row["text"].replace('"', "").split()[:5])


def who(row):
    return "[%s]" % row["date"] if row["date"] else '"%s"' % words(row)


def next_step(row):
    """(command, what it does) for the entry sheet's Next row."""
    if row["state"] == "done":
        return "", "done: kept for the record, shown with show done"
    if row["feature"]:
        miss = [t for t in row["trail"] if not t["exists"]]
        kinds = [t["kind"] for t in miss]
        scope = next((t["path"] for t in row["trail"] if t["kind"] == "scope"), "")
        if "scope" in kinds:
            return ("/said:scope-refine " + (os.path.dirname(scope) or scope)), "the feature has no scope yet"
        if miss:
            return "/said:architect " + scope, "the feature is missing its " + ", ".join(kinds)
        return "/said:board " + row["feature"], ('shows its phase and the command that advances it, or open the <a class="flink" href="/#%s">Features board, %s</a>'
                                                  % (esc(row["feature"]), esc(row["feature"])))
    if row["record"]:
        return "/said:backlog promote " + who(row), "plans its move to a feature of a lane, then asks you to confirm once"
    return "/said:backlog move " + who(row), "gives it a record folder (idea, handover or bugfix) and moves its notes there"


def _sheet(row, path, today):
    """The sheet on the feature sheet's anatomy, from the entry's own data; the page moves it into the drawer."""
    mk = mark(row)
    head = ""
    if mk:
        big = ("rid big long" if len(mk) > 16 else "rid big")
        head = (('<a class="flink %s" href="/#%s" title="open %s on the Features board">%s</a>' % (big, esc(mk), esc(mk), esc(mk))) if row["feature"]
                else '<span class="%s">%s</span>' % (big, esc(mk)))
    head += ('<span class="ph es" style="--pc:%s" data-stage="%s">%s</span><span class="estate" data-state="%s">%s</span>'
             % (stage_color(row["stage"]), esc(row["stage"]), esc(row["stage"]), esc(row["state"]), esc(STATE_WORD.get(row["state"], row["state"]))))
    crumb = " / ".join(esc(x) for x in (row["section"], row["group"], row["subgroup"]) if x)
    cmd, why = next_step(row)
    dates = "raised %s%s" % (esc(row["date"] or "-"), (", age " + L.age(row["date"], today)) if row["date"] and L.age(row["date"], today) else "")
    text, _ident = said_backlog.strip_id(row["text"])
    ed = L.editable(row["raw"])
    out = ['<div class="d-head">%s</div><div class="ecrumb">%s</div><div class="d-name%s"%s>%s</div>'
           % (head, crumb, "" if mk else " solo",
              (' %s tabindex="0" role="button" title="click to edit"' % L.ed_attrs("text", row["line"], row["raw"], value=text)) if ed else "", L.inline(text)),
           L.steps(CHAIN, chain_at(row)), L.next_row(cmd, why), L.prio_switch(row["priority"]), '<div class="d-dates">%s</div>' % dates]
    ns = notes(row)
    every = row.get("notes") or []
    last = every[-1] if every else {"line": row["line"], "raw": row["raw"], "depth": -1}
    out.append(L.esec("Notes", (_note_list(ns, True) if ns else '<div class="eempty">No notes.</div>')
                      + ('<button type="button" class="addnote" %s>+ add note</button>' % L.ed_attrs("note-add", last["line"], last["raw"], depth=last["depth"])
                         if L.editable(last["raw"]) else "")))
    chips = "".join('<span class="tagc">#%s%s</span>' % (esc(t), ('<button type="button" class="tagx" %s aria-label="remove tag %s" title="remove">x</button>'
                                                                  % (L.ed_attrs("tag-del", row["line"], row["raw"], tag=t), esc(t))) if ed else "") for t in row["tags"])
    out.append(L.esec("Tags", '<div class="tagrow">%s%s</div>' % (chips, ('<input type="text" class="tag-in" %s maxlength="60" placeholder="+ tag" aria-label="add a tag">'
                                                                         % L.ed_attrs("tag-add", row["line"], row["raw"])) if ed else "")))
    if row["trail"]:
        files = "".join('<div class="erow %s"><span class="t-dot"></span><code class="t-id">%s</code><span class="ep">%s</span><span class="t-status">%s</span></div>'
                        % ("ok" if t["exists"] else "miss", esc(t["kind"]), esc(t["path"]), "present" if t["exists"] else "missing") for t in row["trail"])
    else:
        files = '<div class="eempty">No record yet: this entry is the line alone.</div>'
    out.append(L.esec("Feature files" if row["feature"] else "Record", files))
    out.append(L.esec("Source", '<div class="esrc"><code>%s:%d</code><span>position %d in the file</span></div>' % (esc(path), row["line"], row["position"])))
    return '<template class="lb-detail">%s</template>' % "".join(out)


def _attrs(row, cid, path):
    q = " ".join([row["text"], row["section"], row["group"], row["subgroup"], row["record"], row["feature"], row["stamp"], row["stage"]]
                 + ["#" + t for t in row["tags"]] + [n["text"] for n in row.get("notes") or []]).lower()
    return ('data-key="%s" data-line="%d" data-position="%d" data-cid="%s" data-state="%s" data-stage="%s" data-priority="%s" '
            'data-section="%s" data-formed="%d" data-done="%d" data-q="%s" tabindex="0" role="button" style="--sc:%s" aria-label="%s"'
            % (esc(row["key"]), row["line"], row["position"], esc(cid), esc(row["state"]), esc(row["stage"]), esc(row["priority"]),
               esc(row["section"]), formed(row), row["state"] == "done", esc(q), stage_color(row["stage"]), esc(row["text"][:80])))


def _subs(row):
    ns = notes(row)
    return _note_list(ns) if ns else ""


def _outline_card(row, cid, path, today):
    right = "%s%s" % (('<span class="st">%s</span>' % esc(STATE_WORD.get(row["state"], row["state"]))) if row["state"] != "open" else "",
                      ('<span class="dt">%s</span>' % esc(row["date"])) if row["date"] else "")
    drag = row["position"] >= 1
    return ('<li class="bl-row ecard%s" %s><div class="er"><span class="lead">%s%s</span><span class="tx">%s</span>%s%s</div>%s%s</li>'
            % (" dnd" if drag else "", _attrs(row, cid, path), L.GRIP if drag else "", L.pslot(row["priority"]), L.inline(row["text"]),
               ('<span class="mk">%s</span>' % esc(mark(row))) if mark(row) else "", right, _subs(row), _sheet(row, path, today)))


def _card(row, path, today, drop):
    trail = ", ".join('<span class="%s">%s%s</span>' % ("ok" if t["exists"] else "miss", esc(t["kind"]), "" if t["exists"] else " (missing)") for t in row["trail"])
    return ('<li class="bl-row bcard" %s%s><div class="h">%s<span>%s</span><span class="badge2">%s</span>%s%s</div><div class="t">%s</div>%s%s%s%s</li>'
            % (_attrs(row, "", path), ' draggable="true"' if drop else "", L.pslot(row["priority"]), esc(row["stage"]), esc(row["section"]),
               ('<span>%s</span>' % esc(row["date"])) if row["date"] else "",
               ('<span class="wip">%s</span>' % esc(STATE_WORD[row["state"]])) if row["state"] == "wip" else "",
               L.inline(row["text"]), ('<div class="m">%s</div>' % esc(" / ".join(x for x in (row["group"], row["subgroup"]) if x))) if row["group"] else "",
               ('<div class="m">%s</div>' % trail) if trail else "", ('<div class="mkr"><span class="mk">%s</span></div>' % esc(mark(row))) if mark(row) else "",
               _sheet(row, path, today)))


def _entries(rows, cid, path, today):
    return '<ul class="entries">%s</ul>' % "".join(_outline_card(r, cid, path, today) for r in rows)


def _add_control(label, section, topic, subtopic=None):
    """The heading's add button: it names the topic (and subtopic) it adds to; the page shows it on hover or focus."""
    return (' <button type="button" class="qa" data-qs="%s" data-qt="%s"%s title="add an entry to %s" aria-label="add an entry to %s">+ add</button>'
            % (esc(section), esc(topic), (' data-qu="%s"' % esc(subtopic)) if subtopic is not None else "", esc(label), esc(label)))


def _outline(rows, outline, path, today, targets):
    """The headings come from the file's own sections, so a topic with no entry still shows its heading and add control."""
    tree = {}
    for r in rows:
        sec = tree.setdefault(r["section"], {"direct": [], "topics": {}})
        if not r["group"]:
            sec["direct"].append(r)
        else:
            tp = sec["topics"].setdefault(r["group"], {"direct": [], "subs": {}})
            (tp["subs"].setdefault(r["subgroup"], []) if r["subgroup"] else tp["direct"]).append(r)
    shape = {o["title"]: {t["title"]: t["subtopics"] for t in o["topics"]} for o in outline}
    out = []
    for name in dict.fromkeys([o["title"] for o in outline] + list(tree)):
        sec = tree.get(name, {"direct": [], "topics": {}})
        n = len(sec["direct"]) + sum(len(t["direct"]) + sum(len(u) for u in t["subs"].values()) for t in sec["topics"].values())
        out.append('<div class="grp%s">%s' % (" tgt" if name in targets else "", L.heading("h2", "sec:" + name, name, L.count(n))))
        if sec["direct"]:
            out.append(_entries(sec["direct"], name + "|", path, today))
        for g in dict.fromkeys(list(shape.get(name, {})) + list(sec["topics"])):
            tp = sec["topics"].get(g, {"direct": [], "subs": {}})
            m = len(tp["direct"]) + sum(len(u) for u in tp["subs"].values())
            subs = list(dict.fromkeys(shape.get(name, {}).get(g, []) + list(tp["subs"])))
            body = _entries(tp["direct"], "%s|%s" % (name, g), path, today) if tp["direct"] else ""
            for sg in subs:
                urows = tp["subs"].get(sg, [])
                body += '<div class="topic sub2">%s%s</div>' % (
                    L.heading("h4", "sub:%s|%s|%s" % (name, g, sg), sg, '<small data-of="%d">%d</small>' % (len(urows), len(urows)), tail=_add_control(sg, name, g, sg)),
                    _entries(urows, "%s|%s|%s" % (name, g, sg), path, today) if urows else "")
            out.append('<div class="topic">%s%s</div>' % (L.heading("h3", "grp:%s|%s" % (name, g), g, '<small data-of="%d">%d</small>' % (m, m),
                                                                    tail="" if subs else _add_control(g, name, g)), body))
        out.append("</div>")
    return "".join(out)


def _by(rows, by, path, today):
    if by == "section":
        names = list(dict.fromkeys(r["section"] for r in rows))
        groups = [(n, "", "", lambda r, n=n: r["section"] == n, False) for n in names]
    elif by == "stage":
        names = [s for s in STAGE_ORDER if any(r["stage"] == s for r in rows)]
        groups = [(n, '<i style="--sc:%s"></i>' % stage_color(n), "", lambda r, n=n: r["stage"] == n, False) for n in names]
    else:
        groups = [("Priority #" + p if p != "none" else "No priority", "", p, lambda r, p=p: (r["priority"] or "none") == p, True) for p in L.PRIORITIES]
    out = []
    for name, dot, p, test, drop in groups:
        mine = [r for r in rows if test(r)]
        if by != "priority":
            mine.sort(key=lambda r: (RANK.get(r["priority"], 3), r["line"]))
        out.append('<div class="sect%s" %s><h2>%s%s %s</h2><ul class="grid">%s%s</ul></div>'
                   % (" pdrop" if drop else "", ('data-drop="%s"' % p) if drop else "", dot, esc(name), L.count(len(mine)),
                      "".join(_card(r, path, today, drop) for r in mine),
                      ('<li class="dzone">drop a card here to %s</li>' % ("clear its priority" if p == "none" else "set #" + p)) if drop else ""))
    return "".join(out)


def _toolbar(rows, by, targets):
    secs = list(dict.fromkeys(r["section"] for r in rows))
    live = lambda r: r["state"] != "done"  # noqa: E731  the default card set hides done
    tabs = [("", 'All <span class="tn" data-n="">%d</span>' % sum(1 for r in rows if live(r)), "", "")]
    tabs += [(s, '%s <span class="tn" data-n="%s">%d</span>' % ('<em class="tgt" title="declared target, not a lane">%s</em>' % esc(s) if s in targets else esc(s), esc(s),
                                                              sum(1 for r in rows if r["section"] == s and live(r))), "", "") for s in secs]
    return ('<div class="btool"><div class="bt-l%s"%s><span class="lbl">section</span>%s</div>'
            '<div class="bt-m"><label class="switch"><input type="checkbox" class="toggle toggle-sm bb-done">show done</label>'
            '<span class="lbl">cards</span>%s</div><div class="bt-r">%s</div></div>'
            % (" off" if by == "section" else "", ' title="By section shows every section; the tabs apply to the other views"' if by == "section" else "",
               L.seg(tabs, "data-sec", "", "Section"), L.seg([("all", "all entries", "", ""), ("formed", "formed only", "", "")], "data-cs", "all", "Cards"),
               L.seg([(v, VIEW_LABEL[v], "", "") for v in VIEWS], "data-bl-by", by, "View")))


def _filters(rows):
    live = [r for r in rows if r["state"] != "done"]
    prios = [L.chip("none" if p == "none" else "#" + p, sum(1 for r in live if (r["priority"] or "none") == p), "prio", p, L.PRIO_COLOR.get(p)) for p in L.PRIORITIES]
    stages = [s for s in STAGE_ORDER if any(r["stage"] == s for r in rows)]
    chips = [L.chip(s, sum(1 for r in live if r["stage"] == s), "stage", s, stage_color(s)) for s in stages]
    return L.filter_row([("priority", prios), ("stage", chips)], "search text, record, feature  ( / )")


def render_backlog_board(view, by="outline", today=None):
    if by not in VIEWS:
        by = "outline"
    today = datetime.date.fromisoformat(today) if today else datetime.date.today()
    c = view["counts"]
    status = "backlog %s: %d entries, %d findings" % (view["path"], c["entries"], c["findings"])
    if not view["exists"]:
        return ('<div class="lb bb" data-board="backlog"><div class="bb-foot" data-entries="0" data-status="%s"></div>'
                '<div class="empty-state">No backlog file.</div></div>' % esc(status))
    rows = sorted((r for g in view["by_stage"] for r in g["rows"]), key=lambda r: r["line"])
    body = _outline(rows, view["outline"], view["path"], today, view["targets"]) if by == "outline" else _by(rows, by, view["path"], today)
    foot = ('<div class="foot bb-foot" data-entries="%d" data-status="%s">%s, <span class="bb-n">%d</span> of %d entries shown, %d grammar findings%s</div>'
            % (c["entries"], esc(status), esc(view["path"]), c["entries"], c["entries"], c["findings"],
               ' (<code>/said:backlog lint</code>)' if c["findings"] else ""))
    return ('<div class="lb bb" data-board="backlog">%s%s<div class="bl-groups%s" data-by="%s">%s</div>'
            '<p class="bb-empty empty-state" hidden>Nothing matches the filters.</p>%s</div>'
            % (_toolbar(rows, by, view["targets"]), _filters(rows), " blist" if by == "outline" else "", by, body, foot))
