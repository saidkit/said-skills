"""said:board, the shared pieces of the backlog and todo screens: the toolbar, the filter row, the priority box,
the folding heading and the entry sheet's parts. Each board module composes them; every string goes through `esc`
and every value is from a closed set the caller names. The client half is lists.js and lists.css.
"""
import datetime
import re

from serve import esc  # the shell's helper
import said_backlog

PRIO_COLOR = {"A": "var(--prio-a)", "B": "var(--prio-b)", "C": "var(--prio-c)"}
PRIORITIES = ("A", "B", "C", "none")
CARET = '<span class="caret" aria-hidden="true"><b class="op">-</b><b class="cl">+</b></span>'
GRIP = ('<span class="grip" draggable="true" title="drag to move among its siblings" aria-label="move">'
        '<svg viewBox="0 0 8 14" width="8" height="14" aria-hidden="true"><g fill="currentColor">'
        '<circle cx="2" cy="2" r="1.2"/><circle cx="6" cy="2" r="1.2"/><circle cx="2" cy="7" r="1.2"/>'
        '<circle cx="6" cy="7" r="1.2"/><circle cx="2" cy="12" r="1.2"/><circle cx="6" cy="12" r="1.2"/></g></svg></span>')


def prio(letter):
    """The priority box: `#A` in its colour, a dash when none."""
    if letter in PRIO_COLOR:
        return '<span class="prio" data-p="%s" title="priority #%s">#%s</span>' % (letter, letter, letter)
    return '<span class="prio none" data-p="" title="no priority">-</span>'


def pslot(letter, attrs=""):
    """The box that opens the in-place picker (#A #B #C none); `attrs` is the caller's own escaped attributes."""
    return '<span class="pslot" role="button" tabindex="0" title="set priority" aria-label="set priority"%s>%s</span>' % ((" " + attrs) if attrs else "", prio(letter))


def seg(items, attr, on, label):
    """A segmented toggle: items are (value, html, extra class, title); the one equal to `on` is active."""
    out = ['<span class="join" role="group" aria-label="%s">' % esc(label)]
    for v, html, cls, title in items:
        out.append('<button type="button" class="btn btn-xs join-item%s%s"%s %s="%s">%s</button>'
                   % (" btn-active" if v == on else "", (" " + cls) if cls else "", (' title="%s"' % esc(title)) if title else "", attr, esc(v), html))
    out.append("</span>")
    return "".join(out)


def chip(label, n, group, value, color=None):
    return ('<button type="button" class="chip" aria-pressed="true" data-set="%s" data-v="%s">%s%s <span class="n">%d</span></button>'
            % (esc(group), esc(value), ('<i style="--sc:%s"></i>' % color) if color else "", esc(label), n))


def filter_row(groups, placeholder):
    """The one filter row: chip groups split by a thin rule, then the search box and the Clear button.
    `groups` is [(label, [chip html])]."""
    fg = "".join('<span class="fg"><span class="lbl">%s</span>%s</span>' % (esc(label), "".join(chips)) for label, chips in groups)
    return ('<div class="bars"><div class="bar">%s<input type="search" class="input input-bordered input-xs bb-q" placeholder="%s" aria-label="search">'
            '<button type="button" class="btn btn-xs clr bb-clear" disabled title="clear search and filters">Clear</button></div></div>'
            % (fg, esc(placeholder)))


def heading(tag, ck, label, count, extra_cls="", tail=""):
    """A heading that folds on its small box; `count` is the html after the label, `tail` the html after the count."""
    return ('<%s class="hd%s" data-ck="%s">%s%s %s%s</%s>' % (tag, (" " + extra_cls) if extra_cls else "", esc(ck), CARET, esc(label), count, tail, tag))


def steps(names, at, acts=None):
    """The stage chain; with `acts` (one attribute string per step, or None) each step is a button, the current one disabled."""
    def one(i, n):
        if not acts or acts[i] is None:
            return esc(n)
        return '<button type="button" class="stepbtn" %s%s>%s</button>' % (acts[i], " disabled aria-current=\"step\"" if i == at else "", esc(n))
    return '<ul class="steps steps-horizontal d-steps">%s</ul>' % "".join(
        '<li class="step%s">%s</li>' % (" step-primary" if i <= at else "", one(i, n)) for i, n in enumerate(names))


def editable(raw):
    """A line the editor may hold: nothing the page would have to clean or cut, so what it sends back is what the file holds."""
    return raw == said_backlog.clean(raw, said_backlog.LINE_CAP)


def ed_attrs(op, line, raw, **extra):
    """The attributes the sheet's editor reads: the operation, the line and the line's text as the file held it."""
    return 'data-ed="%s" data-line="%d" data-raw="%s"%s' % (op, line, esc(raw), "".join(' data-%s="%s"' % (k, esc(str(v))) for k, v in extra.items()))


def state_attrs(state, line, raw):
    """The attributes of a control that sets a todo line's state: the state, the line and the line's text as the file held it."""
    return 'data-set-state="%s" data-line="%d" data-raw="%s"' % (esc(state), line, esc(raw))


def next_action(label, attrs, why):
    """The Next row of a sheet whose action is a button, not a command: a label, the button, one muted line under it."""
    return ('<div class="d-next"><span class="lbl">next</span><button type="button" class="btn btn-xs nextbtn" %s>%s</button><span class="nwhy">%s</span></div>'
            % (attrs, esc(label), why))


def next_row(cmd, why):
    """The Features sheet's Next row: a command in a code box and a copy button, one muted line under it."""
    box = ('<code class="nextcmd">%s</code><button type="button" class="btn btn-xs copybtn" onclick="copyNext(this)">copy</button>' % esc(cmd)) if cmd else ""
    return '<div class="d-next"><span class="lbl">next</span>%s<span class="nwhy%s">%s</span></div>' % (box, "" if cmd else " solo", why)


def prio_switch(letter):
    return ('<div class="eprio"><span class="lbl">priority</span>%s</div>'
            % seg([(p, "none" if p == "none" else "#" + p, "", "") for p in PRIORITIES], "data-w=\"priority\" data-letter", letter or "none", "set priority"))


def esec(title, body):
    return '<section class="esec"><h4>%s</h4>%s</section>' % (esc(title), body)


def inline(text):
    """An escaped line with inline `code`, **bold** and a markdown link shown as its label."""
    s = esc(text)
    s = re.sub(r"`([^`\n]{1,44})`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*\n]{1,80})\*\*", r"<b>\1</b>", s)
    return re.sub(r"\[([^\]\n]{1,80})\]\(([^)\n]{1,200})\)", r'<span class="ref">\1</span>', s)


def count(n):
    """The heading's `N of N` count the client keeps in step with the filters."""
    return '<span class="cnt" data-of="%d">%d of %d</span>' % (n, n, n)


def age(date, today):
    try:
        return "%dd" % max(0, (today - datetime.date.fromisoformat(date)).days)
    except ValueError:
        return ""
