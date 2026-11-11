#!/usr/bin/env python3
"""SessionStart hook body (matcher: clear|compact): re-anchor the session from disk after a /clear or a compaction.

Started once by reanchor.sh with the hook JSON on stdin. Prints the status reconstruction, the open run-protocol
files left in this project's session scratchpads, and a re-issue instruction; stdout is injected into the new
context. Silent on every other source, silent outside a SAID lane (the hook is active wherever the plugin is
enabled), and silent on any failure: it always exits 0.
Env: SAID_STATUS    path to said_status.py (default: the one bundled with this plugin)
     SCRATCH_ROOT   root of the per-session scratchpads (default: /private/tmp/claude-<uid>, else /tmp/claude-<uid>)
     SAID_SETTINGS  user settings file checked for a statusline install (default: ~/.claude/settings.json)
"""
import json
import os
import sys

# Imports the early exit does not need (subprocess, glob, re, time) are loaded after the source check: a startup
# run, the common case, only reads the JSON.


def text(v):
    return "" if v is None else str(v)


def is_lane(path):
    """A CLAUDE.md whose heading is exactly "## Lane" at column 0, outside code fences ("## Lanes" is not it)."""
    import re
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            body = fh.read()
    except OSError:
        return False, ""
    fenced = False
    found = False
    for line in body.split("\n"):
        if line.startswith("```") or line.startswith("~~~"):
            fenced = not fenced
            continue
        if not fenced and re.fullmatch(r"## Lane[ \t\r]*", line):
            found = True
            break
    return found, body


def run(cmd, cap, deadline):
    import subprocess
    import time
    left = min(cap, deadline - time.monotonic())
    if left <= 0:
        return None
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=left)
    except Exception:
        return None
    return p.stdout if p.returncode == 0 else None


def found(out):
    return bool(out and out.strip()) and not out.startswith("no such feature in registry:")


def status_block(status, cwd, feature, has_registry):
    """The status reconstruction. At a root whose lane block declares a lane registry: a branch feature that does
    not resolve here is tried in each lane the registry resolves, and a lane root that is its own git repository
    adds one line for its own branch feature. Only rows the registry names are tried; a row the reader cannot
    resolve is passed over. A root with no registry line asks the registry nothing."""
    import re
    import time
    deadline = time.monotonic() + 8  # one budget for every call below; what is left unasked is left out

    def st(*args):
        return run([sys.executable, status] + list(args), 20, deadline)

    def branch_feature(path):
        out = (run(["git", "-C", path, "branch", "--show-current"], 5, deadline) or "").strip()
        m = re.match(r"[a-z]*/([A-Za-z]*-[0-9][0-9]*)", out)
        return m.group(1).upper() if m else ""

    here = os.path.realpath(cwd)
    rows = []
    if has_registry:
        rows = [r for r in (st("--registry", "--resolve", "--root", cwd) or "").splitlines()
                if ":root=" in r and not r.startswith("skipped:")]
    lanes = []
    for r in rows:
        token, rest = r.split(":", 1)
        root = rest.split(";", 1)[0][len("root="):]
        path = os.path.realpath(os.path.join(cwd, root))
        if path != here:
            lanes.append((token, root, path, r))
    out = st(feature, "--root", cwd) if feature else st("--stale", "--root", cwd)
    shown = None
    if feature and not found(out):
        for token, root, path, r in lanes:
            o = st(feature, "--root", cwd, "--lane", r)
            if found(o):
                out, shown = "Feature %s resolves in lane %s (%s):\n%s" % (feature, token, root, o), token
                break
    if out is None:
        print("(status unavailable) -- run /said:board --cli to reconstruct.", flush=True)
    else:
        print("\n".join(out.splitlines()[:60 if feature else 40]), flush=True)
    extra = []
    for token, root, path, r in lanes:
        if token == shown:
            continue
        top = (run(["git", "-C", path, "rev-parse", "--show-toplevel"], 5, deadline) or "").strip()
        if not top or os.path.realpath(top) != path:
            continue
        f = branch_feature(path)
        if not f:
            continue
        o = st(f, "--root", cwd, "--lane", r)
        if found(o):
            extra.append("lane %s (%s), on its own branch: %s" % (token, root, o.splitlines()[0]))
    for line in extra[:8]:
        print(line)
    if len(extra) > 8:
        print("+%d more lanes on a feature branch of their own (run /said:board --cli in the lane)" % (len(extra) - 8))


def open_runs(root):
    """Live leaves only: a think-<id>.md whose Closed: header is "no", whose Gate log carries no final verdict,
    and which no other open run names as its Parent. Newest first, capped at 20."""
    import glob
    import re
    runs = {}
    for f in sorted(glob.glob(os.path.join(root, "*", "scratchpad", "think-*.md"))):
        with open(f, errors="replace") as fh:
            t = fh.read()
        m = re.search(r"Closed:\s*([^\s|]*)", t)
        closed = bool(m) and m.group(1).lower() not in ("", "no")
        gate = t.split("## Gate log", 1)[1] if "## Gate log" in t else ""
        if closed or re.search(r"all PASS|escalated", gate):
            continue
        p = re.search(r"Parent:\s*([^\s|]+)", t)
        runs[f] = (os.path.basename(f)[len("think-"):-len(".md")], p.group(1) if p else "none")
    parents = {par for _, par in runs.values()}
    leaves = sorted((f for f, (rid, _) in runs.items() if rid not in parents), key=os.path.getmtime, reverse=True)
    lines = list(leaves[:20])
    if len(leaves) > 20:
        lines.append("+%d more (older; list them with the run manager)" % (len(leaves) - 20))
    return lines


def main():
    try:
        d = json.load(sys.stdin)
    except Exception:
        return
    if not isinstance(d, dict):
        return
    src = text(d.get("source") or d.get("session_source") or "")
    if src not in ("clear", "compact"):
        return
    import re
    import time
    cwd = text(d.get("cwd", ""))
    if not cwd:
        return
    lane, claude_md = is_lane(os.path.join(cwd, "CLAUDE.md"))
    if not lane:
        return
    try:
        os.chdir(cwd)
    except OSError:
        pass
    here = os.path.dirname(os.path.abspath(__file__))
    status = os.environ.get("SAID_STATUS") or os.path.join(here, "..", "skills", "board", "said_status.py")
    scratch = os.environ.get("SCRATCH_ROOT")
    if not scratch:
        scratch = ("/private/tmp/claude-%d" if os.path.isdir("/private/tmp") else "/tmp/claude-%d") % os.getuid()
    slug = cwd.replace("/", "-")

    print("RE-ANCHOR after `%s` -- state below is read from disk, not from the conversation summary." % src)
    branch = (run(["git", "branch", "--show-current"], 5, time.monotonic() + 5) or "").strip()
    m = re.match(r"[a-z]*/([A-Za-z]*-[0-9][0-9]*)", branch)
    feature = m.group(1).upper() if m else ""
    if os.path.isfile(status):
        try:
            status_block(status, cwd, feature, "SAID.lanes" in claude_md)
        except Exception:
            print("(status unavailable) -- run /said:board --cli to reconstruct.")
    else:
        print("(status script not found; set SAID_STATUS) -- run /said:board --cli to reconstruct.")

    try:
        runs = open_runs(os.path.join(scratch, slug))
    except Exception:
        runs = []
    if runs:
        print("Open run protocols (continue one with its path):")
        for line in runs:
            print("  " + line)
    print("Next: re-issue the same directive; the skill re-derives its phase by inspection.")

    # Inactive-checkpoint hint: one line when this session switched the context checkpoint on (the variable
    # SAID_CONTEXT_CHECKPOINT=on, or the marker checkpoint-on in its scratchpad), has no context.json, and the
    # user settings name no said statusline script (the checkpoint then has nothing to read). Informational only.
    sid = text(d.get("session_id", ""))
    settings = os.environ.get("SAID_SETTINGS") or os.path.join(os.path.expanduser("~"), ".claude", "settings.json")
    pad = os.path.join(scratch, slug, sid, "scratchpad")
    if os.environ.get("SAID_CONTEXT_CHECKPOINT") == "on" or os.path.isfile(os.path.join(pad, "checkpoint-on")):
        if not os.path.isfile(os.path.join(pad, "context.json")):
            try:
                with open(settings, errors="replace") as fh:
                    named = re.search(r"statusline-context\.sh|said-statusline\.sh", fh.read()) is not None
            except OSError:
                named = False
            if not named:
                print("context checkpoint inactive: run /said:setup statusline")


if __name__ == "__main__":
    try:
        main()
        sys.stdout.flush()
    except BaseException:
        pass  # a hook never breaks the session: nothing more is printed, the exit is 0
    sys.exit(0)
