"""said:board, the todo board: one tab per lane with a todo file, its lines as an outline of cards.

A board is one page module over one thing. This one renders the view model `said_backlog.todo_view()` builds,
the same model `said_backlog.py --board todo` prints as text and `--json`. It writes nothing; every string goes
through `esc`, and every query value is checked against a closed set. One fragment carries the lane's lines once,
in file order under their section and subsection headings, each with its sheet as a hidden template; the filter
row, the folds, the cursor, the picker and the drags are the shared list client (lists.js).
"""
import datetime

from serve import esc  # the shell's helper
from said_backlog import TODO_STATES, strip_id, todo_filter
from boards import lists as L

STATE_CHOICES = ("all",) + TODO_STATES
PRIORITY_CHOICES = ("all", "A", "B", "C", "none")
STATE_WORD = {"open": "open", "wip": "in progress", "done": "done", "unknown": "unknown"}
STATE_LABEL = {"open": "Open", "wip": "In progress", "done": "Done"}
STATE_COLOR = {"open": "var(--st-record)", "wip": "var(--warn)", "done": "var(--ok)"}
CHAIN = ("Open", "In progress", "Done")
NEXT = {"open": ("wip", "Mark in progress", "marks the line as being worked on, in its file"),
        "wip": ("done", "Mark done", "marks the line done; it stays in its file as the record")}


def _pick(value, choices):
    return value if value in choices else choices[0]


def _where(r):
    return r["section"] + ((" / " + r["subsection"]) if r["subsection"] else "")


def _rest(b):
    """A sub-bullet's text without its leading kind word."""
    t = b["text"]
    return t[len(b["kind"]):].lstrip(":").strip() if t.startswith(b["kind"]) else t


def _sub(b, serves):
    """A sub-item row: its kind in mono, its words; the feature id a line serves is a link to the Features board."""
    rest = _rest(b)
    ed = b["kind"] in ("in", "adr", "ref") and "](" not in b["text"] and L.editable(b["raw"])
    words = L.inline(rest)
    if b["kind"] == "in" and serves and rest.startswith(serves):
        words = ('<a class="flink" href="/#%s" title="open %s on the Features board">%s</a>%s' % (esc(serves), esc(serves), esc(serves), L.inline(rest[len(serves):])))
    if not ed:
        return '<li class="sub"><code class="t-id">%s</code> %s</li>' % (esc(b["kind"]), words)
    return ('<li class="sub" %s><code class="t-id">%s</code> <span class="nt" tabindex="0" role="button" title="click to edit">%s</span>'
            '<button type="button" class="nx" %s aria-label="remove this sub-item" title="remove">x</button></li>'
            % (L.ed_attrs("sub", b["line"], b["raw"], value=b["text"]), esc(b["kind"]), words, L.ed_attrs("sub-del", b["line"], b["raw"])))


def _sheet(r, tab, rows, today):
    """The sheet on the entry sheet's anatomy, from the line's own data; the page moves it into the drawer."""
    parent = next((x for x in rows if x["line"] == r["parent_line"]), None) if r["parent_line"] else None
    kids = [x for x in rows if x["parent_line"] == r["line"]]
    crumb = esc(tab["lane"]) + " todo / " + esc(_where(r))
    dates = "raised %s%s" % (esc(r["date"] or "-"), (", age " + L.age(r["date"], today)) if r["date"] and L.age(r["date"], today) else "")
    ed = L.editable(r["raw"])
    out = ['<div class="d-head"><span class="estate" data-state="%s">%s</span></div><div class="ecrumb">%s</div>'
           % (esc(r["state"]), esc(STATE_WORD.get(r["state"], r["state"])), crumb)]
    if parent:
        out.append('<div class="tpar">under <button type="button" class="linkbtn" data-open-key="%s">%s</button></div>' % (esc(parent["key"]), L.inline(parent["text"])))
    text, _ident = strip_id(r["text"])
    out.append('<div class="d-name solo"%s>%s</div>'
               % ((' %s tabindex="0" role="button" title="click to edit"' % L.ed_attrs("text", r["line"], r["raw"], value=text)) if ed else "", L.inline(text)))
    keys = tuple(STATE_LABEL)
    out.append(L.steps(CHAIN, keys.index(r["state"]) if r["state"] in STATE_LABEL else -1, [L.state_attrs(k, r["line"], r["raw"]) if ed else None for k in keys]))
    if r["state"] in NEXT and ed:
        to, label, why = NEXT[r["state"]]
        out.append(L.next_action(label, L.state_attrs(to, r["line"], r["raw"]), why))
    else:
        out.append(L.next_row("", "no action: a done line is kept in its file as the record" if r["state"] == "done" else "this line cannot be edited from the board"))
    out.append(L.prio_switch(r["priority"]))
    out.append('<div class="d-dates">%s</div>' % dates)
    subs = '<ul class="subs">%s</ul>' % "".join(_sub(b, r["serves"]) for b in r["sub_bullets"]) if r["sub_bullets"] else '<div class="eempty">No sub-items.</div>'
    add = ('<button type="button" class="addnote" %s>+ add sub-item</button>' % L.ed_attrs("sub-add", r["line"], r["raw"])) if ed else ""
    out.append(L.esec("Sub-items", subs + add))
    if kids:
        out.append(L.esec("Lines under it", "".join(
            '<button type="button" class="erow kline" data-open-key="%s" data-state="%s"><span class="t-dot"></span><span class="ep">%s</span><span class="t-status">%s</span></button>'
            % (esc(k["key"]), esc(k["state"]), L.inline(k["text"]), esc(STATE_WORD.get(k["state"], k["state"]))) for k in kids)))
    where = "position %d in its group" % r["position"] if r["position"] else "nested under line %d" % r["parent_line"]
    out.append(L.esec("Source", '<div class="esrc"><code>%s:%d</code><span>%s</span></div>' % (esc(tab["path"]), r["line"], esc(where))))
    return '<template class="lb-detail">%s</template>' % "".join(out)


def _card(r, cid, tab, rows, today, matched):
    right = "%s%s" % (('<span class="st">%s</span>' % esc(STATE_WORD.get(r["state"], r["state"]))) if r["state"] != "open" else "",
                      ('<span class="dt">%s</span>' % esc(r["date"])) if r["date"] else "")
    drag = r["depth"] == 0 and r["position"] >= 1
    subs = ('<ul class="subs">%s</ul>' % "".join('<li class="sub">%s</li>' % L.inline(b["text"]) for b in r["sub_bullets"])) if r["sub_bullets"] else ""
    q = " ".join([r["text"], r["section"], r["subsection"], r["stamp"]] + [b["text"] for b in r["sub_bullets"]]).lower()
    return ('<li class="td-row ecard%s%s" data-key="%s" data-line="%d" data-depth="%d" data-state="%s" data-priority="%s" data-cid="%s" data-q="%s" '
            'tabindex="0" role="button" style="--depth:%d" aria-label="%s"><div class="er"><span class="lead">%s%s</span><span class="tx">%s</span>%s</div>%s%s</li>'
            % (" dnd" if drag and matched else "", "" if matched else " td-context", esc(r["key"]), r["line"], r["depth"], esc(r["state"]), esc(r["priority"]),
               esc(cid), esc(q), r["depth"], esc(r["text"][:80]), L.GRIP if drag and matched else "", L.pslot(r["priority"]), L.inline(r["text"]), right, subs,
               _sheet(r, tab, rows, today)))


def _outline(items, tab, today):
    secs = {}
    for r, m in items:
        s = secs.setdefault(r["section"], {"direct": [], "groups": {}})
        (s["groups"].setdefault(r["subsection"], []) if r["subsection"] else s["direct"]).append((r, m))
    out = []
    for name, s in secs.items():
        n = len(s["direct"]) + sum(len(g) for g in s["groups"].values())
        label = name or "(no section)"
        ck = "tsec:%s|%s" % (tab["lane"], name)
        out.append('<div class="grp">%s' % L.heading("h2", ck, label, L.count(n)))
        if s["direct"]:
            out.append('<ul class="entries">%s</ul>' % "".join(_card(r, name + "|", tab, tab["rows"], today, m) for r, m in s["direct"]))
        for g, grows in s["groups"].items():
            out.append('<div class="topic">%s<ul class="entries">%s</ul></div>'
                       % (L.heading("h3", "tgrp:%s|%s|%s" % (tab["lane"], name, g), g, '<small data-of="%d">%d</small>' % (len(grows), len(grows))),
                          "".join(_card(r, "%s|%s" % (name, g), tab, tab["rows"], today, m) for r, m in grows)))
        out.append("</div>")
    return "".join(out)


def _toolbar(view):
    return ('<div class="btool"><div class="bt-l"><span class="lbl">lane</span>%s</div></div>'
            % L.seg([(t["lane"], '%s <span class="tn">%d</span>' % (esc(t["lane"]), t["counts"]["open"]), "", "") for t in view["tabs"]],
                    "data-td-lane", view["tab"]["lane"], "Lane"))


def _filters(rows):
    prios = [L.chip("none" if p == "none" else "#" + p, sum(1 for r in rows if (r["priority"] or "none") == p), "prio", p, L.PRIO_COLOR.get(p)) for p in L.PRIORITIES]
    states = [L.chip(STATE_LABEL[s], sum(1 for r in rows if r["state"] == s), "state", s, STATE_COLOR[s]) for s in TODO_STATES]
    return L.filter_row([("priority", prios), ("state", states)], "search text, section  ( / )")


def render_todo_board(view, lane=None, state="all", priority="all", today=None):
    state, priority = _pick(state, STATE_CHOICES), _pick(priority, PRIORITY_CHOICES)
    today = datetime.date.fromisoformat(today) if today else datetime.date.today()
    if not view["tabs"]:
        body = ('No lane has a todo file: no lane is configured.' if not view["checked"]
                else 'No lane has a todo file. Checked: <ul>%s</ul>' % "".join("<li><code>%s</code></li>" % esc(p) for p in view["checked"]))
        return ('<div class="lb bb" data-board="todo"><div class="foot bb-foot" data-entries="%d" data-status="no todo file"></div>'
                '<div class="empty-state td-none">%s</div></div>' % (view["counts"]["entries"], body))
    names = [t["lane"] for t in view["tabs"]]
    tab = view["tabs"][names.index(lane)] if lane in names else view["tabs"][0]
    view = dict(view, tab=tab)
    items = todo_filter(tab["rows"], state, priority)
    shown = sum(1 for _, m in items if m)
    tc = tab["counts"]
    status = "todo %s: %d lines, %d open, %d in progress" % (tab["lane"], tc["entries"], tc["open"], tc["wip"])
    note = ('<div class="lb-note">Process notes of %s, <code>%s</code>, as recorded, not as plan: %d open, %d in progress of %d.</div>'
            % (esc(tab["lane"]), esc(tab["path"]), tc["open"], tc["wip"], tc["entries"]))
    body = _outline(items, tab, today) if items else '<p class="empty-state">No line matches the filters.</p>'
    return ('<div class="lb bb td" data-board="todo">%s%s%s<div class="bl-groups blist td-list" data-by="outline" data-lane="%s" data-state="%s" data-priority="%s" '
            'data-shown="%d" data-total="%d">%s</div><p class="bb-empty empty-state" hidden>Nothing matches the filters.</p>'
            '<div class="foot bb-foot" data-entries="%d" data-status="%s">%s, <span class="bb-n">%d</span> of %d lines shown</div></div>'
            % (_toolbar(view), _filters(tab["rows"]), note, esc(tab["lane"]), state, priority, shown, tc["entries"], body,
               tc["entries"], esc(status), esc(tab["path"]), shown, tc["entries"]))
