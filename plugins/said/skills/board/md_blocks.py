#!/usr/bin/env python3
"""md_blocks.py - a Markdown block parser for the GFM subset the todo-md format uses (stdlib, no regular expressions).

Layer one of the reader: lines in, a tree of blocks out. It follows the CommonMark / GFM block rules for the
constructs the format spec lists: a leading front matter block, ATX headings, setext headings, thematic breaks,
fenced code, HTML comments, paragraphs, bullet and ordered list items (nesting by content column, lazy
continuation) and block quotes. Anything else an indented line can start (indented code) is kept as an opaque
block; no input raises. The profile layer (todo_md.py) reads the tree; this module knows nothing of the format.

Block kinds (the `kind` attribute):
  front     lines, closed
  heading   level, text, line            (ATX)
  setext    level, lines, underline      (a paragraph turned heading by its underline)
  thematic  line
  fence     open (no, raw), lines (inner), close (no, raw) or None, char, info
  html      lines, closed                (a comment block)
  code      lines                        (indented code, opaque)
  quote     lines (every line it holds), children
  para      lines                        (first line, then continuation lines, lazy ones included)
  list      items, ordered
  item      line, raw, marker, marker_col, content_col, ordered, number, delim, children, empty
Every line is a (number, raw text) pair; numbers are 1-based, raw text is the physical line.
"""

TAB_STOP = 4
BULLETS = "-+*"
MAX_OPEN = 32  # open containers (items and quotes) at once; a list or quote marker past it is paragraph text


class Block(object):
    def __init__(self, kind, **kw):
        self.kind = kind
        self.__dict__.update(kw)

    def __repr__(self):
        return "Block(%s)" % ", ".join("%s=%r" % kv for kv in sorted(self.__dict__.items()) if kv[0] not in ("children", "items"))


def is_blank(text):
    return not text.strip()


def spaces_of(text, start=0):
    """The count of leading spaces of `text` from index `start`."""
    i = start
    while i < len(text) and text[i] == " ":
        i += 1
    return i - start


def expand_indent(raw):
    """`raw` with the tabs of its leading whitespace turned into spaces (tab stops of four)."""
    out, col, i = [], 0, 0
    while i < len(raw) and raw[i] in " \t":
        if raw[i] == "\t":
            step = TAB_STOP - col % TAB_STOP
            out.append(" " * step)
            col += step
        else:
            out.append(" ")
            col += 1
        i += 1
    return "".join(out) + raw[i:]


def parse_atx(s):
    """(level, text) of an ATX heading line `s` (no leading space), else None. Level is the count of `#`
    (any count; the block parser accepts one to six); text has its closing `#` run removed."""
    n = 0
    while n < len(s) and s[n] == "#":
        n += 1
    if not n or (n < len(s) and s[n] not in " \t"):
        return None
    body = s[n:].strip()
    if body.endswith("#"):
        head = body.rstrip("#")
        if not head or head[-1] in " \t":
            body = head.rstrip()
    return n, body


def is_thematic(s):
    """True for a thematic break line (`s` without its leading indent): three or more `-`, `_` or `*`, spaces between."""
    c = s[:1]
    if c not in ("-", "_", "*"):
        return False
    count = 0
    for ch in s:
        if ch == c:
            count += 1
        elif ch not in " \t":
            return False
    return count >= 3


def setext_level(s):
    """1 for a line of `=`, 2 for a line of `-` (trailing spaces allowed), else 0."""
    t = s.rstrip(" \t")
    if t and not t.strip("="):
        return 1
    if t and not t.strip("-"):
        return 2
    return 0


def fence_open(s):
    """(char, run length, info) when `s` opens a fenced code block, else None."""
    c = s[:1]
    if c not in ("`", "~"):
        return None
    n = 0
    while n < len(s) and s[n] == c:
        n += 1
    if n < 3:
        return None
    info = s[n:].strip()
    if c == "`" and "`" in info:
        return None
    return c, n, info


def fence_closes(s, char, length):
    n = 0
    while n < len(s) and s[n] == char:
        n += 1
    return n >= length and not s[n:].strip()


def html_open(s):
    """The marker that ends an HTML block opened by `s` (a comment, a processing instruction, a declaration, CDATA), else None."""
    if s.startswith("<!--"):
        return "-->"
    if s.startswith("<?"):
        return "?>"
    if s.startswith("<![CDATA["):
        return "]]>"
    if s.startswith("<!") and s[2:3].isalpha() and s[2:3].isascii():
        return ">"
    return None


def scan_list_marker(s):
    """The list marker at the start of `s` (no leading space): a dict, else None.
    marker (text), width (marker length), ordered, number, delim, after (the text after the marker),
    empty (nothing after it). A marker needs a space, a tab or the line end after it."""
    if not s:
        return None
    if s[0] in BULLETS:
        width, ordered, number, delim = 1, False, 0, s[0]
    else:
        n = 0
        while n < len(s) and n < 10 and s[n].isascii() and s[n].isdigit():
            n += 1
        if not 1 <= n <= 9 or n >= len(s) or s[n] not in ".)":
            return None
        width, ordered, number, delim = n + 1, True, int(s[:n]), s[n]
    after = s[width:]
    if after and after[0] not in " \t":
        return None
    return {"marker": s[:width], "width": width, "ordered": ordered, "number": number, "delim": delim,
            "after": after, "empty": not after.strip()}


class _Open(object):
    """An open container: an item or a quote, with the column where its content begins."""

    def __init__(self, kind, node, content_col):
        self.kind, self.node, self.content_col = kind, node, content_col


class _Parser(object):
    def __init__(self):
        self.root = Block("document", children=[])
        self.opens = []
        self.tip = None  # the open leaf block: para, fence, html or code

    def container_children(self):
        return self.opens[-1].node.children if self.opens else self.root.children

    # --- closing

    def close_leaf(self):
        self.tip = None

    def close_to(self, k):
        del self.opens[k:]
        self.close_leaf()

    # --- block starts

    def starts_block(self, rest):
        """True when `rest` (after the matched containers) would start a block of its own."""
        sp = spaces_of(rest)
        if sp >= 4:
            return False
        s = rest[sp:]
        if not s.strip():
            return False
        return (s[0] == ">" or (s[0] == "#" and parse_atx(s) is not None and parse_atx(s)[0] <= 6)
                or fence_open(s) is not None or html_open(s) is not None or is_thematic(s)
                or scan_list_marker(s) is not None)

    def add_line_to_quotes(self, no, raw, upto):
        for o in self.opens[:upto]:
            if o.kind == "quote":
                o.node.lines.append((no, raw))

    def feed(self, no, raw):
        t = expand_indent(raw)
        pos, k = 0, 0
        blank = is_blank(t)
        lead = spaces_of(t)
        for o in self.opens:
            if o.kind == "item":
                if blank:
                    if o.node.empty and not o.node.children and no > o.node.line:
                        break
                    k += 1
                    continue
                if (lead if pos <= lead else pos + spaces_of(t, pos)) >= o.content_col:
                    pos = o.content_col
                    k += 1
                    continue
                break
            sp = spaces_of(t, pos)
            if sp < 4 and t[pos + sp:pos + sp + 1] == ">":
                pos += sp + 1
                if t[pos:pos + 1] == " ":
                    pos += 1
                k += 1
                continue
            break
        full = k == len(self.opens)
        rest = t[pos:]
        tip = self.tip
        if tip is not None and full and tip.kind in ("fence", "html", "code"):
            if self.continue_leaf(tip, no, raw, rest, blank):
                self.add_line_to_quotes(no, raw, k)
                return
        elif tip is not None and not full and tip.kind == "para" and not blank and not self.starts_block(rest):
            tip.lines.append((no, raw))
            self.add_line_to_quotes(no, raw, k)
            return
        if not full:
            self.close_to(k)
        self.add_line_to_quotes(no, raw, len(self.opens))
        self.start_blocks(no, raw, t, pos)

    def continue_leaf(self, tip, no, raw, rest, blank):
        """Feed a line to the open fence, html block or indented code; True when it was taken."""
        if tip.kind == "fence":
            sp = spaces_of(rest)
            if sp < 4 and fence_closes(rest[sp:], tip.char, tip.length):
                tip.close = (no, raw)
                self.close_leaf()
            else:
                tip.lines.append((no, raw))
            return True
        if tip.kind == "html":
            tip.lines.append((no, raw))
            if tip.end in rest:
                tip.closed = True
                self.close_leaf()
            return True
        if blank or spaces_of(rest) >= 4:
            if not blank:
                tip.lines.append((no, raw))
            return True
        self.close_leaf()
        return False

    def start_blocks(self, no, raw, t, pos):
        while True:
            rest = t[pos:]
            sp = spaces_of(rest)
            s = rest[sp:]
            para_open = self.tip is not None and self.tip.kind == "para"
            if not s.strip():
                self.close_leaf()
                return
            if sp >= 4:
                if para_open:
                    self.tip.lines.append((no, raw))
                else:
                    blk = Block("code", lines=[(no, raw)])
                    self.container_children().append(blk)
                    self.tip = blk
                return
            if para_open:
                lv = setext_level(s)
                if lv:
                    par = self.tip
                    self.container_children()[-1] = Block("setext", level=lv, lines=par.lines, underline=(no, raw))
                    self.close_leaf()
                    return
            if s[0] == ">" and not self.too_deep():
                self.close_leaf()
                node = Block("quote", lines=[(no, raw)], children=[])
                self.container_children().append(node)
                pos += sp + 1
                if t[pos:pos + 1] == " ":
                    pos += 1
                self.opens.append(_Open("quote", node, 0))
                continue
            atx = parse_atx(s) if s[0] == "#" else None
            if atx and atx[0] <= 6:
                self.close_leaf()
                self.container_children().append(Block("heading", level=atx[0], text=atx[1], line=(no, raw)))
                return
            fo = fence_open(s)
            if fo:
                blk = Block("fence", open=(no, raw), lines=[], close=None, char=fo[0], length=fo[1], info=fo[2])
                self.close_leaf()
                self.container_children().append(blk)
                self.tip = blk
                return
            end = html_open(s)
            if end:
                blk = Block("html", lines=[(no, raw)], closed=end in s[2:], end=end)
                self.close_leaf()
                self.container_children().append(blk)
                self.tip = None if blk.closed else blk
                return
            if is_thematic(s):
                self.close_leaf()
                self.container_children().append(Block("thematic", line=(no, raw)))
                return
            mk = scan_list_marker(s)
            if mk and self.too_deep():
                mk = None
            if mk and not (para_open and (mk["empty"] or (mk["ordered"] and mk["number"] != 1))):
                self.close_leaf()
                self.open_item(no, raw, pos + sp, mk)
                item = self.opens[-1]
                if item.node.empty:
                    return
                pos = item.content_col
                continue
            if para_open:
                self.tip.lines.append((no, raw))
            else:
                blk = Block("para", lines=[(no, raw)])
                self.container_children().append(blk)
                self.tip = blk
            return

    def too_deep(self):
        """True when MAX_OPEN containers are open: no list or quote opens, its marker stays paragraph text."""
        return len(self.opens) >= MAX_OPEN

    def open_item(self, no, raw, marker_col, mk):
        after = mk["after"]
        lead = spaces_of(after)
        content = marker_col + mk["width"] + (lead if 1 <= lead <= 4 and not mk["empty"] else 1)
        item = Block("item", line=no, raw=raw, marker=mk["marker"], marker_col=marker_col, content_col=content,
                     ordered=mk["ordered"], number=mk["number"], delim=mk["delim"], children=[], empty=mk["empty"])
        kids = self.container_children()
        last = kids[-1] if kids else None
        if last is not None and last.kind == "list" and last.ordered == item.ordered and last.sig == (mk["delim"] if item.ordered else mk["marker"]):
            last.items.append(item)
        else:
            kids.append(Block("list", items=[item], ordered=item.ordered, sig=mk["delim"] if item.ordered else mk["marker"]))
        o = _Open("item", item, content)
        self.opens.append(o)


def parse(lines):
    """The block tree of `lines` (physical lines without their newline): a Block of kind `document` whose
    `children` are the top-level blocks. A leading front matter block is read first. Never raises on text."""
    p = _Parser()
    start = 0
    if lines and lines[0].strip() == "---":
        end = next((j for j in range(1, len(lines)) if lines[j].strip() == "---"), None)
        stop = len(lines) if end is None else end + 1
        p.root.children.append(Block("front", lines=[(i + 1, lines[i]) for i in range(stop)], closed=end is not None))
        start = stop
    for i in range(start, len(lines)):
        p.feed(i + 1, lines[i])
    return p.root


def walk(block):
    """Every block under `block` in document order (a list's items and an item's children included), iteratively."""
    out, stack = [], [block]
    while stack:
        b = stack.pop()
        out.append(b)
        kids = getattr(b, "items", None) or getattr(b, "children", None) or []
        stack.extend(reversed(kids))
    return out
