#!/usr/bin/env python3
"""cite_check.py: the one check of a `path:line` cite and of the words quoted after it. Stdlib only; it reads and
prints and writes no file.

A cite is `<path>:<line>` or `<path>:<line>-<line>`, the path relative to the lane root. A path that is absolute or
has a `..` part is outside the lane; the test is on the text of the path, so a link inside the lane is followed.
The cite holds when the file is there and every line it names exists. A quote is the words in double quotes
directly after the cite; it holds when, whitespace folded, the words stand on the cited line (on one of the lines of
a range), read as written or with each ' read as ".

  cite_check.py --lane <lane> <file>    check every cite in the text of <file>

Prints one `<cite>: <why>` line per failing cite, in text order. Exit 0 every cite holds, 1 a cite fails, 2 an input
is missing or unreadable (`error: <why>`).
"""
import os
import re
import sys

CITE = re.compile(r'^([\w./-]+):(\d+)$')
# a cite inside free text: a path with a / or a .ext, then :line, :line-line; a quote may follow (after a closing ` or :)
IN_TEXT = re.compile(r'(?<![\w./:@-])([\w./-]*[/.][\w./-]*):(\d+)(?:-(\d+))?(?!\w)(?!:\d)(?:[`:]{0,2}[ \t]*"([^"\n]+)")?')


def fold(s):
    return re.sub(r'\s+', ' ', s).strip()


def read_lines(lane, path):
    with open(os.path.join(lane, path), encoding='utf-8') as fh:
        t = fh.read()
    ls = t.split('\n')
    return ls[:-1] if t.endswith('\n') else ls


def inside(path):
    """False when the path is absolute or has a `..` part."""
    return not (path.startswith('/') or '..' in path.split('/'))


def cite_line(lane, cite, isfile=None, lines=None):
    """(path, line) of a `path:line` cite whose file is in the lane and whose line exists, else None. isfile(full
    path) and lines(lane-relative path) default to the disk; a caller with its own view of the files passes its own."""
    isfile = isfile or os.path.isfile
    lines = lines or (lambda p: read_lines(lane, p))
    m = CITE.match(cite)
    if not m or not inside(m.group(1)):
        return None
    if not isfile(os.path.join(lane, m.group(1))) or not 1 <= int(m.group(2)) <= len(lines(m.group(1))):
        return None
    return (m.group(1), int(m.group(2)))


def quote_at(line, words):
    """True when the quoted words stand on the line, whitespace folded, as written or with ' read as "."""
    return fold(words.replace("'", '"')) in fold(line) or fold(words) in fold(line)


def text_faults(lane, text):
    """[(cite, why)] for every cite in the text that fails, in text order."""
    out = []
    for m in IN_TEXT.finditer(text):
        path, a, b, words = m.group(1), int(m.group(2)), m.group(3), m.group(4)
        cite = '%s:%s%s' % (path, m.group(2), '-' + b if b else '')
        if not re.search(r'[A-Za-z]', path) or ('/' not in path and (len(m.group(2)) >= 4 or not re.search(r'\.[A-Za-z]\w*$', path))):
            continue  # a number (1.5:2), a version (v1.2:3) or a host and port (example.com:8080), not a path
        if not inside(path):
            out.append((cite, 'outside the lane'))
            continue
        if not os.path.isfile(os.path.join(lane, path)):
            out.append((cite, 'no such file'))
            continue
        try:
            ls = read_lines(lane, path)
        except (OSError, UnicodeError):
            out.append((cite, 'the file cannot be read'))
            continue
        span = range(a, int(b) + 1) if b else range(a, a + 1)
        bad = next((n for n in (a, int(b) if b else a) if not 1 <= n <= len(ls)), None)
        if bad is not None or not span:
            out.append((cite, 'no line %d' % (bad if bad is not None else a)))
            continue
        if words is not None and (not fold(words) or not any(quote_at(ls[n - 1], words) for n in span)):
            out.append((cite, 'the quoted words are not on the line'))
    return out


def main(argv):
    lane, files, i = None, [], 0
    while i < len(argv):
        if argv[i] == '--lane' and i + 1 < len(argv):
            lane, i = argv[i + 1], i + 2
        else:
            files.append(argv[i])
            i += 1
    if not lane or len(files) != 1:
        print('error: usage: cite_check.py --lane <lane> <file>')
        return 2
    lane = os.path.realpath(os.path.abspath(lane))
    try:
        with open(os.path.abspath(files[0]), encoding='utf-8') as fh:
            text = fh.read()
    except (OSError, UnicodeError) as e:
        print('error: %s cannot be read (%s)' % (files[0], e.__class__.__name__))
        return 2
    faults = text_faults(lane, text)
    for cite, why in faults:
        print('%s: %s' % (cite, why))
    return 1 if faults else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
