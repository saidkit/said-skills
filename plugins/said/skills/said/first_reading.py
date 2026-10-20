#!/usr/bin/env python3
"""Print a session's first reading: the context size of the first model call recorded in its transcript.

Usage: python3 first_reading.py --session-id <id> [--store <dir>]

The store is Claude Code's per-project transcript folder, `<config dir>/projects` (the config dir is
$CLAUDE_CONFIG_DIR, else ~/.claude); the transcript is `<store>/<project>/<session id>.jsonl`. The first reading is
input + cache read + cache creation tokens of the first main (non-sidechain) assistant row with a non-zero usage.
Prints one line, `first-reading: <N>` or `first-reading: none` (no plain session id, no transcript, nothing readable),
and exits 0. Read-only: it never writes a file and never prints a transcript's text.
"""
import glob
import json
import os
import re
import sys


def store_dir(argv):
    if "--store" in argv and argv.index("--store") + 1 < len(argv):
        return argv[argv.index("--store") + 1]
    base = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
    return os.path.join(base, "projects")


def first_reading(sid, store):
    if not re.fullmatch(r"[A-Za-z0-9_-]+", sid or ""):
        return None
    root = os.path.realpath(store)
    for path in sorted(glob.glob(os.path.join(glob.escape(store), "*", sid + ".jsonl"))):
        real = os.path.realpath(path)
        if os.path.commonpath([root, real]) != root or not os.path.isfile(real):
            continue
        with open(real, "r", errors="replace") as fh:
            for line in fh:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(row, dict) or row.get("type") != "assistant" or row.get("isSidechain"):
                    continue
                msg = row.get("message")
                use = msg.get("usage") if isinstance(msg, dict) else None
                if not isinstance(use, dict):
                    continue
                total = 0
                for key in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"):
                    value = use.get(key)
                    total += value if isinstance(value, int) and value > 0 else 0
                if total:
                    return total
        return None
    return None


def main(argv):
    sid = argv[argv.index("--session-id") + 1] if "--session-id" in argv and argv.index("--session-id") + 1 < len(argv) else ""
    try:
        value = first_reading(sid, store_dir(argv))
    except Exception:
        value = None
    print("first-reading: %s" % (value if value else "none"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
