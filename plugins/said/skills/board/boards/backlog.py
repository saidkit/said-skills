"""said:board, the backlog board: the backlog file's entries as a stage-grouped card grid, by stage or by priority.

A board is one page module over one thing. This one renders the view model `said_backlog.board_view()` builds,
the same model `said_backlog.py --board backlog` prints as text and `--json`, so the page and the terminal carry
the same numbers. It writes nothing; every string goes through `esc`. The page shape: a tab per view, filter
bars (area, stage, record class, search, show closed, reset, priority), one card per entry with a detail block
the page's side panel shows, and a status line the page's header shows. A feature's `next` comes from the
features board's cache when it is already warm; the backlog board never runs the analyzer.
"""
from serve import esc  # the shell's helper

VIEWS = ("stage", "priority")
STATE_WORD = {"open": "open", "wip": "in progress", "done": "done"}
STAGE_COLOR = {"Entry": "#64748b", "Idea": "#2563eb", "Owed reply": "#0891b2", "Scoped": "#7c3aed",
               "Bugfix": "#dc2626", "Wip only": "#b91c1c", "Promoted": "#d97706", "Resolved": "#6b7280",
               "Done": "#6b7280"}
CLOSED_STAGES = ("Done", "Resolved")
PRIO_COLOR = {"A": "#dc2626", "B": "#d97706", "C": "#2563eb"}
REC_CLASSES = ("feature", "idea", "handover", "bugfix", "entry")


def stage_color(stage):
    return STAGE_COLOR.get(stage, "#64748b")


def prio_badge(letter):
    """The priority badge: `#A` / `#B` / `#C` in its colour, a dashed `none` without one."""
    if letter in PRIO_COLOR:
        return '<span class="lb-prio" style="background:%s" title="priority #%s">#%s</span>' % (PRIO_COLOR[letter], letter, letter)
    return '<span class="lb-prio none" title="no priority">none</span>'


def write_controls(row):
    """The row's two writes, no confirm: a priority button per letter (none clears) and, for a top-level entry, up and down."""
    out = ['<span class="row-ctl pctl" role="group" aria-label="Priority and order">']
    for letter in ("A", "B", "C", "none"):
        on = (row["priority"] or "none") == letter
        out.append('<button type="button" class="btn btn-ghost btn-xs%s" data-w="priority" data-letter="%s" aria-pressed="%s" title="%s">%s</button>'
                   % (" btn-active" if on else "", letter, "true" if on else "false",
                      "clear the priority" if letter == "none" else "priority #" + letter, letter))
    pos = int(row.get("position") or 0)
    if pos >= 1:
        if pos > 1:
            out.append('<button type="button" class="btn btn-ghost btn-xs" data-w="order" data-to="%d" aria-label="Move up" title="move up">&uarr;</button>' % (pos - 1))
        out.append('<button type="button" class="btn btn-ghost btn-xs" data-w="order" data-to="%d" aria-label="Move down" title="move down">&darr;</button>' % (pos + 1))
    out.append('<span class="row-msg muted" role="status"></span></span>')
    return "".join(out)


def rec_class(row):
    if row["feature"]:
        return "feature"
    if row["record"] and row["trail"]:
        return row["trail"][0]["kind"] if row["trail"][0]["kind"] in REC_CLASSES else "idea"
    return "entry"


def card_id(row):
    """The bold id of a card: the feature, else the record folder, else the stamp, else the line."""
    if row["feature"]:
        return row["feature"]
    if row["record"]:
        return row["record"]
    if row["stamp"]:
        return "@" + row["stamp"]
    return "line %d" % row["line"]


def area(row):
    return row["section"] + (" / " + row["group"] if row["group"] else "")


def trail_text(row):
    """records: idea 2026-01-02, scope, spec, tasks; a missing one is named."""
    if not row["trail"]:
        return "no idea, scope, spec or tasks file"
    return ", ".join("%s%s%s" % (t["kind"], (" " + t["date"]) if t.get("date") else "", "" if t["exists"] else " (missing)")
                     for t in row["trail"])


def flags(row, nexts):
    out = ["%s file missing: %s" % (t["kind"], t["path"]) for t in row["trail"] if not t["exists"]]
    if row["state"] == "unknown":
        out.append("the state is not open, in progress or done")
    return out


def _trail_spans(row):
    return ", ".join('<span class="lb-trail%s" title="%s">%s</span>%s'
                     % ("" if t["exists"] else " missing", esc(t["path"]), esc(t["kind"]),
                        (" " + esc(t["date"])) if t.get("date") else "")
                     for t in row["trail"]) or "no idea, scope, spec or tasks file"


def _detail(row, path, related, nexts):
    """The side panel's content for one card, rendered here; the page only moves it into the panel."""
    dl = []

    def add(k, v):
        if v:
            dl.append("<dt>%s</dt><dd>%s</dd>" % (esc(k), v))
    add("kind", "backlog entry (%s)" % esc(rec_class(row)))
    add("area", esc(area(row)))
    add("stage", '<span class="lb-stage" style="--sc:%s">%s</span>' % (stage_color(row["stage"]), esc(row["stage"])))
    add("priority", "%s, home %s:%d (the entry line)" % ("#" + esc(row["priority"]) if row["priority"] else "none", esc(path), row["line"]))
    add("status", esc(STATE_WORD.get(row["state"], row["state"])))
    add("raised", esc(row["date"] or ""))
    add("records", "<ul>%s</ul>" % "".join('<li>%s%s <code>%s</code>%s</li>' % (esc(t["kind"]), (" " + esc(t["date"])) if t.get("date") else "",
                                                                             esc(t["path"]), "" if t["exists"] else ' <span class="lb-flag">missing</span>')
                                           for t in row["trail"]) if row["trail"] else "none")
    if row["feature"]:
        add("feature", '<a class="bl-feature link" href="/#%s">%s</a>' % (esc(row["feature"]), esc(row["feature"])))
    add("next", ("<code>%s</code>" % esc(nexts[row["feature"]])) if nexts.get(row["feature"]) else "")
    add("flags", "<br>".join(esc(f) for f in flags(row, nexts)))
    add("notes", "<ul>%s</ul>" % "".join("<li>%s</li>" % esc(n) for n in row.get("notes") or []) if row.get("notes") else "")
    add("record key", "<code>%s</code>" % esc(row["key"]))
    add("source", "<code>%s:%d</code>" % (esc(path), row["line"]))
    add("text", esc(row["text"]))
    rel = ""
    if related:
        rel = ('<h3>Related, as the records state</h3><ul class="lb-rel">%s</ul>'
               % "".join('<li><button type="button" class="link" data-open="%s">%s</button> %s</li>'
                         % (esc(r["key"]), esc(card_id(r)), esc(r["text"][:80])) for r in related))
    return ('<template class="lb-detail"><h2>%s</h2><div class="lb-dtitle">%s</div><dl class="lb-dl">%s</dl>%s'
            '<div class="lb-dctl">%s %s</div></template>'
            % (esc(card_id(row)), esc(row["text"]), "".join(dl), rel, prio_badge(row["priority"]), write_controls(row)))


def _card(row, path, related, nexts):
    nxt = nexts.get(row["feature"]) if row["feature"] else ""
    q = " ".join((card_id(row), row["text"], area(row), trail_text(row), nxt or "", " ".join(row.get("notes") or []))).lower()
    feat = ""
    if row["feature"]:
        feat = ' <a class="bl-feature link" href="/#%s">%s</a>' % (esc(row["feature"]), esc(row["feature"]))  # the features board's deep link
    fl = flags(row, nexts)
    return ('<li class="bl-row" data-key="%s" data-id="%s" data-line="%d" data-state="%s" data-stage="%s" data-area="%s" '
            'data-rec="%s" data-closed="%s" data-q="%s" tabindex="0" role="button" aria-label="%s, %s" style="--sc:%s" data-priority="%s">'
            '<div class="lb-h">%s<b>%s</b><span class="lb-badge">%s</span><span class="lb-stage">%s</span>%s%s</div>'
            '<div class="lb-t">%s</div>'
            '<div class="lb-m">records: %s%s</div>%s%s%s</li>'
            % (esc(row["key"]), esc(row["key"]), row["line"], esc(row["state"]), esc(row["stage"]), esc(row["section"]),
               rec_class(row), "1" if row["stage"] in CLOSED_STAGES else "0", esc(q), esc(card_id(row)), esc(row["stage"]),
               stage_color(row["stage"]), esc(row["priority"]),
               prio_badge(row["priority"]), esc(card_id(row)), esc(area(row)), esc(row["stage"]),
               (' <span class="lb-raised">raised %s</span>' % esc(row["date"])) if row["date"] else "", write_controls(row),
               esc(row["text"]), _trail_spans(row), feat,
               ('<div class="lb-m">next: <code>%s</code></div>' % esc(nxt)) if nxt else "",
               ('<div class="lb-f">%s</div>' % esc("; ".join(fl))) if fl else "",
               _detail(row, path, related, nexts)))


def _chips(attr, label, items, colors=None):
    out = ['<div class="lb-bar" role="group" aria-label="%s"><span class="lb-lbl">%s:</span>' % (esc(label), esc(label))]
    for value, n in items:
        dot = ('<i style="background:%s"></i>' % colors[value]) if colors and value in colors else ""
        out.append('<button type="button" class="lb-chip" data-f="%s" data-v="%s" aria-pressed="true">%s%s <span class="muted">(%d)</span></button>'
                   % (attr, esc(value), dot, esc(value if attr != "prio" or value == "none" else "#" + value), n))
    out.append("</div>")
    return "".join(out)


def _counted(rows, key, order=None):
    seen = {}
    for r in rows:
        seen[key(r)] = seen.get(key(r), 0) + 1
    names = [v for v in (order or []) if v in seen] + sorted(v for v in seen if v not in (order or []))
    return [(v, seen[v]) for v in names]


def render_backlog_board(view, by="stage", nexts=None):
    if by not in VIEWS:
        by = "stage"
    nexts = nexts or {}
    c = view["counts"]
    status = "backlog: %d entries, %d findings" % (c["entries"], c["findings"])
    head = ('<div class="bl-head lb-head" data-entries="%d" data-status="%s"><span class="muted">%s</span> '
            '<span class="bl-count">%d entries</span>'
            % (c["entries"], esc(status), esc(view["path"]), c["entries"]))
    if c["findings"]:
        head += ' <span class="warn">%d findings</span> <span class="muted">(<code>/said:backlog lint</code>)</span>' % c["findings"]
    head += "</div>"
    tabs = ('<div class="lb-tabs" role="tablist">%s</div>'
            % "".join('<button type="button" role="tab" data-bl-by="%s" aria-selected="%s">%s</button>'
                      % (v, "true" if v == by else "false", "By stage" if v == "stage" else "By priority")
                      for v in VIEWS))
    if not view["exists"]:
        return '<div class="lb" data-board="backlog">' + tabs + head + '<div class="empty-state">No backlog file.</div></div>'
    rows = [r for g in view["by_stage"] for r in g["rows"]]
    groups = view["by_stage"] if by == "stage" else view["by_priority"]
    # related: the other entries that name the same record or the same feature
    by_ref = {}
    for r in rows:
        for ref in (("r", r["record"]), ("f", r["feature"])):
            if ref[1]:
                by_ref.setdefault(ref, []).append(r)

    def related(r):
        out, seen = [], {r["key"]}
        for ref in (("r", r["record"]), ("f", r["feature"])):
            for o in by_ref.get(ref, []) if ref[1] else []:
                if o["key"] not in seen:
                    seen.add(o["key"])
                    out.append(o)
        return out
    stage_names = [g["stage"] for g in view["by_stage"]]
    bars = (_chips("area", "area", _counted(rows, lambda r: r["section"]))
            + _chips("stage", "stage", _counted(rows, lambda r: r["stage"], stage_names), STAGE_COLOR)
            + _chips("rec", "record", _counted(rows, rec_class, list(REC_CLASSES)))
            + '<div class="lb-bar"><input type="search" class="lb-q" placeholder="filter by id, title, record, next" aria-label="filter">'
              '<label class="lb-lbl"><input type="checkbox" class="lb-closed"> show closed / done</label>'
              '<button type="button" class="link lb-reset">reset filters</button></div>'
            + _chips("prio", "priority", [(p, sum(1 for r in rows if (r["priority"] or "none") == p)) for p in ("A", "B", "C", "none")], PRIO_COLOR))
    note = ('<div class="lb-note">Stage is read off the records present: an entry alone = Entry; an idea or handover record = '
            'its stage; a feature link = Promoted; a ticked box = Done. Raised = the entry\'s stamp. Enter or a click opens the detail.</div>')
    out = ['<div class="lb" data-board="backlog">', tabs, head, bars, note, '<div class="bl-groups" data-by="%s">' % by]
    for g in groups:
        label = g["stage"] if by == "stage" else ("Priority #" + g["priority"] if g["priority"] != "none" else "No priority")
        color = stage_color(g["stage"]) if by == "stage" else PRIO_COLOR.get(g["priority"], "#64748b")
        out.append('<section class="bl-group lb-group" style="--sc:%s"><h3>%s <span class="lb-count" data-of="%d">%d of %d</span></h3><ul class="lb-grid">%s</ul></section>'
                   % (color, esc(label), len(g["rows"]), len(g["rows"]), len(g["rows"]),
                      "".join(_card(r, view["path"], related(r), nexts) for r in g["rows"])))
    out.append('</div><p class="lb-empty empty-state" hidden>No entry matches the filters.</p>'
               '<div class="lb-foot" data-total="%d">%d of %d entries shown.</div></div>' % (len(rows), len(rows), len(rows)))
    return "".join(out)
