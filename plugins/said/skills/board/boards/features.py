"""said:board, the features board: the roster, the kanban and a feature's deep-dive, rendered from the analyzer's data.

A board is one page module over one thing; the shell (serve.py) owns the server, routes, header, refresh and
cache, the keyboard shell and the write guard. This board registers no route and writes nothing.
"""
from datetime import datetime

import said_status
from serve import PHASE_SEQ, _md_inline, chip, esc, mount  # the shell's helpers


def _pct(f):
    d = f["denominator"]
    return round(100 * f["done"] / d) if d else 0


def _pill(phase):
    return '<span class="ph" data-phase="%s">%s</span>' % (esc(phase), esc(phase))


def _bar(pct, empty=False):
    if empty:
        return '<progress class="progress prog empty" value="0" max="100"></progress>'
    return '<progress class="progress progress-success prog" value="%d" max="100"></progress>' % pct


def _flag_html(f):
    if f["phase"] == "Closed":
        return '<span class="muted">%d canceled</span>' % f["counts"]["Canceled"] if f["counts"]["Canceled"] else '<span class="shipped">shipped</span>'
    bits = []
    if f["sub"]:
        idle = "" if (f["stale"] or f["idle_days"] is None) else \
            (", active" if f["idle_days"] == 0 else ", %dd" % f["idle_days"])
        lbl = f["sub"] + idle
        bits.append('<span class="muted">%s</span>' % esc(lbl))
    if f["stale"]:
        bits.append('<span class="warn">⚠ %dd idle</span>' % f["idle_days"])
    if f.get("integrity"):  # compact in the row (full detail on hover) — long text overflowed the row
        bits.append('<span class="warn" title="%s">⚠ tasks≠status</span>' % esc(f["integrity"]))
    return " ".join(bits)


def render_row(f):
    d = f["denominator"]
    mid = ('%s<small class="nm">%d/%d</small>' % (_bar(_pct(f)), f["done"], d)) if d \
        else ('%s<small class="nm">—</small>' % _bar(0, empty=True))
    todo = '<small class="todo">%d&nbsp;Todo</small>' % f["todo"] if f["todo"] else '<small class="todo">—</small>'
    return (
        '<button class="row" data-id="%s" data-phase="%s" onclick="selectRow(this)" '
        'hx-get="/fragment/feature/%s" hx-target="#detail" hx-swap="innerHTML" aria-label="%s %s">'
        '<span class="rid">%s</span>%s<span class="mid">%s</span>%s<span class="rflag">%s</span>'
        "</button>"
    ) % (esc(f["id"]), esc(f["phase"]), esc(f["id"]), esc(f["id"]), esc(f["phase"]),
         esc(f["id"]), _pill(f["phase"]), mid, todo, _flag_html(f))


def render_kcard(f):
    d = f["denominator"]
    prog = (('<progress class="progress progress-success kc-bar" value="%d" max="100"></progress>'
             '<span class="kc-nm">%d/%d</span>') % (_pct(f), f["done"], d)) if d else '<span class="kc-nm muted">no tasks</span>'
    todo = '<span class="kc-todo">%d Todo</span>' % f["todo"] if f["todo"] else ""
    if f["stale"]:
        flag = '<div class="kc-flag warn">⚠ %dd idle</div>' % f["idle_days"]
    elif f["phase"] == "Closed":
        flag = '<div class="kc-flag muted">%s</div>' % ("%d canceled" % f["counts"]["Canceled"] if f["counts"]["Canceled"] else "shipped")
    elif f["sub"]:
        flag = '<div class="kc-flag muted">%s</div>' % esc(f["sub"])
    else:
        flag = ""
    # the feature name rides beside the id, clipped to the card — never wraps, never overflows
    nm = f.get("display_name")
    name = '<span class="kc-name" title="%s">%s</span>' % (esc(nm), esc(nm)) if nm else ""
    return (
        '<button class="kcard" data-id="%s" data-phase="%s" hx-get="/fragment/feature/%s" '
        'hx-target="#drawer-content" hx-swap="innerHTML" onclick="openDrawer(this)">'
        '<div class="kc-idrow"><span class="kc-id">%s</span>%s</div><div class="kc-mid">%s%s</div>%s</button>'
    ) % (esc(f["id"]), esc(f["phase"]), esc(f["id"]), esc(f["id"]), name, prog, todo, flag)


def render_kanban(data, stale_only=False, lane=None):
    feats = [f for f in data["features"] if (not stale_only or f["stale"])]
    if lane:
        feats = [f for f in feats if f["lane"] == lane]
    buckets = {p: [] for p in PHASE_SEQ}
    for f in feats:
        buckets.get(f["phase"], buckets["Scope"]).append(f)
    stamp = '<span id="updated" hx-swap-oob="true" class="stamp">updated %s</span>' % datetime.now().strftime("%H:%M:%S")
    cols = []
    for p in PHASE_SEQ:
        items = buckets[p]
        cards = "".join(render_kcard(f) for f in items) or '<div class="kcol-empty">none</div>'
        cols.append('<div class="kcol" data-phase="%s"><div class="kcol-h"><span class="kcol-name">%s</span>'
                    '<span class="kcol-n">%d</span></div><div class="kcol-body">%s</div></div>'
                    % (esc(p), esc(p), len(items), cards))
    return stamp + "".join(cols)


def render_roster(data, stale_only=False, lane=None):
    # OOB stamp updates the header clock on every htmx swap
    out = ['<span id="updated" hx-swap-oob="true" class="stamp">updated %s</span>' % datetime.now().strftime("%H:%M:%S")]
    lanes = [lr for lr in data["lanes"] if (lane is None or lr["name"] == lane)]
    multi = data["lane_count"] > 1
    shown = False
    for lr in lanes:
        rows = [f for f in lr["features"] if (not stale_only or f["stale"])]
        if multi and stale_only and not rows:
            continue
        if multi and lane is None:  # the select names the lane; no lanehead when one is chosen
            out.append('<div class="lanehead">%s <span class="muted">, %s</span></div>' % (esc(lr["name"]), esc(lr["root"])))
        for f in rows:
            out.append(render_row(f))
            shown = True
        legacy = [] if stale_only else lr["legacy_prefixes"]
        if legacy:
            out.append('<div class="legacy">legacy: %s <span class="muted">— not issued here</span></div>' % esc(", ".join(legacy)))
    if not shown:
        out.append('<div class="empty-state">%s</div>' % (
            "Nothing stale — all caught up." if stale_only else "No features found. Check <code>--prefixes</code> / <code>--root</code>."))
    return "\n".join(out)


SEC_ORDER = ["Problem", "Root cause", "Approach", "Reading list", "Acceptance",
             "Fix", "Deviations", "Gotchas", "Out of scope"]


def render_tasks(tasks, fid=None):
    if not tasks:
        return '<section class="d-tasks"><h4>Tasks</h4><div class="sec-b muted">No task log yet.</div></section>'
    rows = []
    for t in tasks:
        status = t["status"]
        cls, disp = (status or "none").lower(), (status or "—")
        secs = t["sections"]
        order = [s for s in SEC_ORDER if s in secs] + [s for s in secs if s not in SEC_ORDER]
        body = []
        for name in order:
            txt = secs[name]
            if len(txt) > 700:
                txt = txt[:700].rstrip() + " ..."
            body.append('<div class="sec"><span class="sec-h">%s</span><div class="sec-b">%s</div></div>'
                        % (esc(name), _md_inline(esc(txt))))
        detail = "".join(body) or '<div class="sec-b muted">No recorded detail.</div>'
        # the task thread mounts at the END of the task body — collapsed tasks cost a DOM node
        # and zero requests; the bundle hydrates one only when its <details> is opened.
        detail += mount("thread", scope="task", feature=fid, task=t["id"])
        dt = '<span class="t-date">%s</span>' % esc(t["date"] or "")
        rows.append(
            '<details class="task t-%s"><summary>'
            '<span class="t-dot"></span><code class="t-id">%s</code>'
            '<span class="t-title">%s</span>%s%s<span class="t-status">%s</span>'
            "</summary><div class=\"task-body\">%s</div></details>"
            % (esc(cls), esc(t["id"]), esc(t["title"] or ""), dt, chip(fid, t["id"]), esc(disp), detail))
    total = len(tasks)
    todo_n = sum(1 for t in tasks if (t["status"] or "").lower() == "todo")
    default = "todo" if todo_n else "all"

    def fbtn(mode, label):
        active = " btn-active" if mode == default else ""
        return ('<button class="btn btn-xs join-item%s" data-mode="%s" onclick="setTaskFilter(this)">%s</button>'
                % (active, mode, label))
    head = ('<div class="d-tasks-h"><div class="th-left">'
            '<h4>Tasks, <span class="tcount">%d</span></h4>'
            '<div class="join tfilter">%s%s</div></div>'
            '<button class="btn btn-xs" onclick="toggleAll(this)">expand all</button></div>'
            % (todo_n if default == "todo" else total, fbtn("todo", "Todo"), fbtn("all", "All")))
    return ('<section class="d-tasks" data-filter="%s" data-all="%d" data-todo="%d">%s%s'
            '<div class="tempty">No open tasks.</div></section>'
            % (default, total, todo_n, head, "".join(rows)))


def render_feature(data, fid, lane=None):
    hits = [x for x in data["features"] if x["id"].lower() == fid.lower()
            or x["id"].lower().startswith(fid.lower() + "-")]
    # the same id in two lanes: the named lane's match first; an unknown or absent lane keeps the first match
    f = next((x for x in hits if lane and x["lane"] == lane), None) or (hits[0] if hits else None)
    if not f:
        return '<div class="empty-state">No such feature: <code>%s</code></div>' % esc(fid)
    ci = PHASE_SEQ.index(f["phase"]) if f["phase"] in PHASE_SEQ else -1
    steps = "".join('<li class="step %s">%s</li>' % ("step-primary" if i <= ci else "", esc(p))
                    for i, p in enumerate(PHASE_SEQ))
    g = f["gates"]
    gate_line = ", ".join([
        "Evals: ",
        "review-qa %s" % ("✓" if g["qa"] else "○"), "review-ux %s" % ("✓" if g["ux"] else "○"),
        "accept %s" % ("✓" if g["accept"] else "○"), "debrief %s" % ("✓" if f["debrief_closed"] else "○"),
    ])
    dates = ", ".join(x for x in [
        "started %s" % esc(f["started"]) if f["started"] else "",
        "last %s" % esc(f["last_activity"]) if f["last_activity"] else "",
        "age %dd" % f["age_days"] if f["age_days"] is not None else "",
        ((said_status.idle_phrase(f["idle_days"]) or "") + (" ⚠" if f["stale"] else "")) if f["idle_days"] is not None else "",
    ] if x)
    nxt = ""
    if f["next"]:
        nxt = ('<div class="d-next"><span class="lbl">Next</span><code class="nextcmd">%s</code>'
               '<button class="btn btn-xs copybtn" onclick="copyNext(this)">copy</button></div>') % esc(f["next"])
    prog = ('<div class="d-prog"><progress class="progress progress-success" value="%d" max="100"></progress>'
            '<span class="nm">%d / %d, %d%%</span></div>' % (_pct(f), f["done"], f["denominator"], _pct(f))) if f["denominator"] else ""
    fp = f.get("paths_rel") or f["paths"]  # display relative to the project root
    files = ", ".join(esc(p) for p in (fp["spec"], fp["tasks"], fp["scope"]) if p)
    lane_tag = '<span class="badge badge-outline badge-sm">%s</span>' % esc(f["lane"]) if data["lane_count"] > 1 else ""
    # the feature name sits below the id in the detail header — full text, wraps freely here
    nm = f.get("display_name")
    d_name = '<div class="d-name">%s</div>' % esc(nm) if nm else ""
    # the recorded completeness note (under-spec WARN + per-unit last-revised) -- advisory, non-gating
    comp = ('<div class="d-complete"><span class="lbl">Complete</span> %s</div>'
            % esc(f["completeness_note"])) if f.get("completeness_note") else ""
    tasks = render_tasks(said_status.feature_tasks([f["paths"]["tasks"]] if f["paths"]["tasks"] else []), f["id"])
    return (
        '<div class="d-head"><span class="rid big">%s</span>%s%s%s</div>%s'
        '<ul class="steps steps-horizontal d-steps">%s</ul>'
        '<div class="d-gates">%s</div>%s%s'
        '<div class="d-dates">%s</div>%s%s%s'
        '<div class="d-files">%s</div>'
    ) % (esc(f["id"]), _pill(f["phase"]), lane_tag, chip(f["id"]), d_name, steps, esc(gate_line), comp, prog, dates,
         tasks, mount("thread", scope="feature", feature=f["id"]), nxt, files)
