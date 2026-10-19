#!/usr/bin/env python3
"""Read a work's rulings list for debrief. Read-only: it never writes a list or any other file.

  rulings-read.py list <rulings.md>          every ruling line by status, pending lines with their evidence
  rulings-read.py status <rulings.md> <id>   one ruling's current status (the re-read after a mark)

The list grammar is read with the hold gate's own line parser, loaded by the sibling-skill path
(`../review-qa/hold-gate.py`), so debrief never reads a ruling line differently from the gate.
Exit: 0 read (or no list: `warn: no rulings list`), 1 an id not in the list, 2 an unreadable or invalid list.
"""
import importlib.util
import os
import sys


def _gate():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "review-qa", "hold-gate.py")
    sys.dont_write_bytecode = True  # read-only: no bytecode cache beside the gate
    spec = importlib.util.spec_from_file_location("said_hold_gate", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load(gate, path):
    """(entries, malformed line numbers) for one list, or None when no list exists at the path."""
    try:
        os.lstat(path)
    except FileNotFoundError:
        return None
    except OSError as e:
        raise gate.ConfigError(f"cannot read {gate.shown(path, 200)}: {e.strerror or e}")
    if not os.path.isfile(path):
        raise gate.ConfigError(f"not a file: {gate.shown(path, 200)}")
    if not os.access(path, os.R_OK):
        raise gate.ConfigError(f"cannot read {gate.shown(path, 200)}")
    entries, broken = gate.load_rulings([path])
    return [(n, e) for _, n, e in entries], broken.get(path, [])


def _row(gate, n, e):
    row = f"{e['status']} {e['id']} line {n}: {gate.shown(e['text'])}"
    if e["links"]:
        row += " | evidence: " + ", ".join(gate.shown(p) for p in e["links"])
    if e["arrow"]:
        row += " | -> " + gate.shown(e["arrow"])
    return row


def cmd_list(gate, path):
    got = _load(gate, path)
    if got is None:
        print(f"warn: no rulings list at {gate.shown(path, 200)}")
        return 0
    entries, broken = got
    counts = {st: sum(1 for _, e in entries if e["status"] == st) for st in gate.RULING_STATUSES}
    total = len(entries) + len(broken)
    print(f"rulings: {gate.shown(path, 200)}, {total} lines: "
          + ", ".join(f"{counts[st]} {st}" for st in gate.RULING_STATUSES) + f", {len(broken)} malformed")
    for n, e in entries:
        print(_row(gate, n, e))
    for n in broken:
        print(f"malformed line {n}")
    return 0


def cmd_status(gate, path, rid):
    got = _load(gate, path)
    if got is None:
        print(f"warn: no rulings list at {gate.shown(path, 200)}")
        return 0
    for n, e in got[0]:
        if e["id"] == rid:
            print(f"{e['id']} {e['status']}" + (f" -> {gate.shown(e['arrow'])}" if e["arrow"] else "") + f" (line {n})")
            return 0
    print(f"{gate.shown(rid, 40)}: not in {gate.shown(path, 200)}")
    return 1


def main(argv):
    if len(argv) == 2 and argv[0] == "list":
        form = lambda g: cmd_list(g, argv[1])
    elif len(argv) == 3 and argv[0] == "status":
        form = lambda g: cmd_status(g, argv[1], argv[2])
    else:
        print("usage: rulings-read.py list <rulings.md> | status <rulings.md> <id>")
        return 2
    try:
        gate = _gate()
    except Exception as e:
        print(f"error: the hold gate's parser could not load ({type(e).__name__})")
        return 2
    try:
        return form(gate)
    except gate.ConfigError as e:
        print(f"error: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
