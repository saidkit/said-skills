"""said:board, the todo board: one tab per lane with a todo file, its features table and its process notes.

A board is one page module over one thing. This one renders the view model `said_backlog.todo_view()` builds,
the same model `said_backlog.py --board todo` prints as text and `--json`. It writes nothing; every string goes
through `esc`, and every query value is checked against a closed set. The page shape: a tab per lane, filter
bars (search, state, priority), the lane's features by engine phase when the features board's cache is already
warm (never a derive of its own), the engine next per lane, and the todo lines grouped by their sections, each
line with a detail block the page's side panel shows.
"""
import os

from serve import esc, _md_inline  # the shell's helpers
from said_backlog import TODO_STATES, todo_filter
from boards.backlog import prio_badge, write_controls

STATE_CHOICES = ("all",) + TODO_STATES
PRIORITY_CHOICES = ("all", "A", "B", "C", "none")
STATE_WORD = {"open": "open", "wip": "wip", "done": "done"}
PHASE_ORDER = ("Implement", "Deliver", "Architect", "Scope", "Closed")


def _pick(value, choices):
    return value if value in choices else choices[0]


def _detail(r, path):
    dl = []

    def add(k, v):
        if v:
            dl.append("<dt>%s</dt><dd>%s</dd>" % (esc(k), v))
    add("kind", "todo line")
    add("group", esc(r["section"] + (" / " + r["subsection"] if r["subsection"] else "")))
    add("status", esc(STATE_WORD.get(r["state"], r["state"])))
    add("priority", "%s, home %s:%d (the todo line)" % ("#" + esc(r["priority"]) if r["priority"] else "none", esc(path), r["line"]))
    add("raised", esc(r["date"] or ""))
    add("notes", "<ul>%s</ul>" % "".join("<li>%s %s</li>" % (esc(b["kind"]), _md_inline(esc(b["text"]))) for b in r["sub_bullets"])
        if r["sub_bullets"] else "")
    add("record key", "<code>%s</code>" % esc(r["key"]))
    add("source", "<code>%s:%d</code>" % (esc(path), r["line"]))
    return ('<template class="lb-detail"><h2>%s</h2><div class="lb-dtitle">%s</div><dl class="lb-dl">%s</dl>'
            '<div class="lb-dctl">%s %s</div></template>'
            % (esc(STATE_WORD.get(r["state"], r["state"]) + " " + ("@" + r["stamp"] if r["stamp"] else "line %d" % r["line"])),
               _md_inline(esc(r["text"])), "".join(dl), prio_badge(r["priority"]), write_controls(r)))


def _row(r, path, matched=True):
    subs = ""
    if r["sub_bullets"]:
        subs = ('<details class="td-subs"><summary class="muted">%d notes</summary><ul>%s</ul></details>'
                % (len(r["sub_bullets"]), "".join('<li><span class="td-kind">%s</span> %s</li>' % (esc(b["kind"]), _md_inline(esc(b["text"])))
                                                  for b in r["sub_bullets"])))
    q = " ".join([r["text"], r["section"], r["subsection"], path] + [b["text"] for b in r["sub_bullets"]]).lower()
    return ('<li class="td-row%s" data-key="%s" data-line="%d" data-depth="%d" data-state="%s" data-priority="%s" data-id="%s" '
            'data-q="%s" tabindex="0" role="button" style="--depth:%d">'
            '<div class="td-h">%s<span class="td-state lb-state-%s">%s</span>%s'
            '<span class="td-text">%s</span> <code class="td-src">%s:%d</code>%s</div>%s%s</li>'
            % ("" if matched else " td-context", esc(r["key"]), r["line"], r["depth"], esc(r["state"]), esc(r["priority"]),
               esc(r["key"]), esc(q), int(r["depth"]),
               prio_badge(r["priority"]), esc(r["state"]), esc(STATE_WORD.get(r["state"], r["state"])),
               (' <span class="lb-raised">%s</span>' % esc(r["date"])) if r["date"] else "",
               _md_inline(esc(r["text"])), esc(path), r["line"], write_controls(r) if matched else "", subs, _detail(r, path)))


def _chips(attr, label, choices, current):
    return ('<div class="lb-bar" role="group" aria-label="%s"><span class="lb-lbl">%s:</span>%s</div>'
            % (esc(label), esc(label), "".join('<button type="button" class="lb-chip%s" %s="%s" aria-pressed="%s">%s</button>'
                                                % (" btn-active" if c == current else "", attr, esc(c), "true" if c == current else "false",
                                                   esc(c if attr != "data-td-priority" or c in ("all", "none") else "#" + c))
                                                for c in choices)))


def _lane_names(tab, lanes, root):
    """The analyzer lanes whose root is the todo lane's root."""
    if not root:
        return set()
    want = os.path.realpath(os.path.join(root, tab.get("root") or ""))
    return {L["name"] for L in lanes if os.path.realpath(L.get("root") or "") == want}


def _features(tab, features, lanes, root):
    names = _lane_names(tab, lanes, root)
    feats = [f for f in features if f.get("lane") in names]
    feats.sort(key=lambda f: (PHASE_ORDER.index(f["phase"]) if f.get("phase") in PHASE_ORDER else 9, f["id"]))
    if not feats:
        return ""
    rows = []
    for f in feats:
        g = f.get("gates") or {}
        gates = ", ".join("%s %s" % (k, "yes" if g.get(k) else "no") for k in ("qa", "ux", "accept"))
        src = (f.get("paths_rel") or {}).get("tasks") or (f.get("paths_rel") or {}).get("spec") or (f.get("paths_rel") or {}).get("scope") or ""
        rows.append('<tr data-phase="%s"><td>%s</td><td><a class="link" href="/#%s">%s</a></td><td><span class="ph" data-phase="%s">%s</span></td>'
                    '<td>%d of %d</td><td>%s</td><td>%s</td><td><code>%s</code></td></tr>'
                    % (esc(f.get("phase") or ""), prio_badge(""), esc(f["id"]), esc(f["id"]), esc(f.get("phase") or ""),
                       esc(f.get("phase") or ""), int(f.get("done") or 0), int(f.get("denominator") or 0), esc(gates),
                       ("<code>%s</code>" % esc(f["next"])) if f.get("next") else "-", esc(src)))
    nexts = [f["next"] for f in feats if f.get("next")]
    return ('<h2>Features by engine phase <span class="lb-count">%d</span></h2>'
            '<table class="lb-table"><tr><th>prio</th><th>id</th><th>phase</th><th>progress</th><th>gates</th><th>next</th><th>source</th></tr>%s</table>'
            '<details class="lb-details" open><summary>Engine next, per lane</summary><ul>%s</ul></details>'
            % (len(feats), "".join(rows), "".join("<li><code>%s</code></li>" % esc(n) for n in nexts) or "<li>none (every feature Closed, or no feature)</li>"))


def render_todo_board(view, lane=None, state="all", priority="all", features=None, lanes=None, root=None):
    state, priority = _pick(state, STATE_CHOICES), _pick(priority, PRIORITY_CHOICES)
    c = view["counts"]
    if not view["tabs"]:
        head = '<div class="td-head" data-tabs="%d" data-entries="%d" data-status="no todo file">' % (c["tabs"], c["entries"])
        if not view["checked"]:
            return '<div class="lb" data-board="todo">' + head + '</div><div class="empty-state td-none">No lane has a todo file: no lane is configured.</div></div>'
        return ('<div class="lb" data-board="todo">' + head + '</div><div class="empty-state td-none">No lane has a todo file. Checked: <ul>%s</ul></div></div>'
                % "".join("<li><code>%s</code></li>" % esc(p) for p in view["checked"]))
    names = [t["lane"] for t in view["tabs"]]
    tab = view["tabs"][names.index(lane)] if lane in names else view["tabs"][0]
    rows = todo_filter(tab["rows"], state, priority)
    shown = sum(1 for _, m in rows if m)
    tc = tab["counts"]
    status = "todo %s: %d lines, %d open, %d in progress" % (tab["lane"], tc["entries"], tc["open"], tc["wip"])
    tabs = "".join('<button type="button" role="tab" class="tab%s" data-td-lane="%s" aria-selected="%s">%s <span class="muted">(%d)</span></button>'
                   % (" tab-active" if t is tab else "", esc(t["lane"]), "true" if t is tab else "false", esc(t["lane"]),
                      t["counts"]["open"] + t["counts"]["wip"])
                   for t in view["tabs"])
    out = ['<div class="lb" data-board="todo">',
           '<div class="td-head" data-tabs="%d" data-entries="%d" data-status="%s">' % (c["tabs"], c["entries"], esc(status)),
           '<div role="tablist" class="lb-tabs td-tabs">%s</div>' % tabs, "</div>",
           '<div class="td-filters">',
           '<div class="lb-bar"><input type="search" class="lb-q" placeholder="filter by title, group or source" aria-label="filter"></div>',
           _chips("data-td-state", "state", STATE_CHOICES, state), _chips("data-td-priority", "priority", PRIORITY_CHOICES, priority),
           "</div>",
           _features(tab, features or [], lanes or [], root),
           '<h2>Process notes: <code>%s</code> <span class="lb-count">%d open or in progress of %d</span></h2>'
           % (esc(tab["path"]), tc["open"] + tc["wip"], tc["entries"]),
           '<div class="lb-note">As recorded, not as plan. Enter or a click on a line opens its detail.</div>',
           '<div class="td-list" data-lane="%s" data-state="%s" data-priority="%s" data-shown="%d" data-total="%d">'
           % (esc(tab["lane"]), state, priority, shown, tc["entries"])]
    groups, cur = [], None
    for r, m in rows:
        g = r["section"] + (" / " + r["subsection"] if r["subsection"] else "")
        if cur is None or g != cur[0]:
            cur = (g, [])
            groups.append(cur)
        cur[1].append((r, m))
    for g, items in groups:
        all_in = [r for r in tab["rows"] if (r["section"] + (" / " + r["subsection"] if r["subsection"] else "")) == g]
        n_shown = sum(1 for _, m in items if m)
        n_open = sum(1 for r in all_in if r["state"] != "done")
        out.append('<details class="lb-details td-group"%s><summary>%s <small>%d shown, %d open of %d</small></summary><ul class="td-ul">%s</ul></details>'
                   % (" open" if n_shown <= 12 else "", esc(g or "(no section)"), n_shown, n_open, len(all_in),
                      "".join(_row(r, tab["path"], m) for r, m in items)))
    if not groups:
        out.append('<p class="empty-state">No line matches the filters.</p>')
    out.append('</div><div class="lb-foot" data-total="%d">%d of %d lines shown.</div></div>' % (tc["entries"], shown, tc["entries"]))
    return "".join(out)
