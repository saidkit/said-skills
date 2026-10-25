#!/usr/bin/env bash
# SessionStart hook (matcher: clear|compact): re-anchor the session from disk after a /clear or a compaction.
# Prints the status reconstruction, the open run-protocol files left in this project's session scratchpads,
# and a re-issue instruction; stdout is injected into the new context. Silent on every other source, and
# silent outside a SAID lane (the hook is active wherever the plugin is enabled).
# Env: SAID_STATUS  path to said_status.py (default: the one bundled with this plugin)
#      SCRATCH_ROOT root of the per-session scratchpads (default: /private/tmp/claude-<uid>, else /tmp/claude-<uid>)
#      SAID_SETTINGS user settings file checked for a statusline install (default: ~/.claude/settings.json)
input=$(cat)
here="$(cd "$(dirname "$0")" && pwd)"   # before any cd: $0 may be relative
field() { printf '%s' "$input" | python3 -c "import json,sys; d=json.load(sys.stdin); v=$1; print('' if v is None else v)" 2>/dev/null; }

src=$(field 'd.get("source") or d.get("session_source") or ""')
case "$src" in clear|compact) ;; *) exit 0 ;; esac

cwd=$(field 'd.get("cwd","")')
# Only a SAID lane (a CLAUDE.md whose heading is exactly "## Lane" at column 0, outside code fences; "## Lanes"
# is not it) is re-anchored; anywhere else stay silent.
[ -n "$cwd" ] && awk '/^(```|~~~)/ { f = !f; next } !f && /^## Lane[ \t\r]*$/ { found = 1; exit } END { exit !found }' \
  "$cwd/CLAUDE.md" 2>/dev/null || exit 0
cd "$cwd" 2>/dev/null

status="${SAID_STATUS:-$here/../skills/board/said_status.py}"
if [ -z "${SCRATCH_ROOT:-}" ]; then
  if [ -d /private/tmp ]; then SCRATCH_ROOT="/private/tmp/claude-$(id -u)"; else SCRATCH_ROOT="/tmp/claude-$(id -u)"; fi
fi
slug=$(printf '%s' "$cwd" | sed 's#/#-#g')

echo "RE-ANCHOR after \`$src\` -- state below is read from disk, not from the conversation summary."
feature=$(git branch --show-current 2>/dev/null | sed -n 's#^[a-z]*/\([A-Za-z]*-[0-9][0-9]*\).*#\1#p' | tr '[:lower:]' '[:upper:]')
if [ -f "$status" ]; then
  # At a root whose lane block declares a lane registry: a branch feature that does not resolve here is tried in
  # each lane the registry resolves, and a lane root that is its own git repository adds one line for its own
  # branch feature. Only rows the registry names are tried; a row the reader cannot resolve is passed over.
  python3 - "$status" "$cwd" "$feature" <<'PY' 2>/dev/null
import os, re, subprocess, sys, time
status, cwd, feature = sys.argv[1], sys.argv[2], sys.argv[3]
deadline = time.monotonic() + 8  # one budget for every call below; what is left unasked is left out
def run(cmd, cap):
    left = min(cap, deadline - time.monotonic())
    if left <= 0:
        return None
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=left)
    except Exception:
        return None
    return p.stdout if p.returncode == 0 else None
def st(*args):
    return run([sys.executable, status] + list(args), 20)
def found(out):
    return bool(out and out.strip()) and not out.startswith("no such feature in registry:")
def branch_feature(path):
    m = re.match(r"[a-z]*/([A-Za-z]*-[0-9][0-9]*)", (run(["git", "-C", path, "branch", "--show-current"], 5) or "").strip())
    return m.group(1).upper() if m else ""
here = os.path.realpath(cwd)
rows = [r for r in (st("--registry", "--resolve", "--root", cwd) or "").splitlines() if ":root=" in r and not r.startswith("skipped:")]
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
    top = (run(["git", "-C", path, "rev-parse", "--show-toplevel"], 5) or "").strip()
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
PY
  [ $? -eq 0 ] || echo "(status unavailable) -- run /said:board --cli to reconstruct."
else
  echo "(status script not found; set SAID_STATUS) -- run /said:board --cli to reconstruct."
fi

# Open run protocols: live leaves only -- a think-<id>.md whose Closed: header is "no", whose Gate log carries
# no final verdict, and which no other open run names as its Parent. Newest first, capped at 20.
open_runs=$(python3 - "$SCRATCH_ROOT/$slug" <<'PY' 2>/dev/null
import glob, os, re, sys
runs = {}
for f in sorted(glob.glob(os.path.join(sys.argv[1], "*", "scratchpad", "think-*.md"))):
    t = open(f, errors="replace").read()
    m = re.search(r"Closed:\s*([^\s|]*)", t)
    closed = bool(m) and m.group(1).lower() not in ("", "no")
    gate = t.split("## Gate log", 1)[1] if "## Gate log" in t else ""
    if closed or re.search(r"all PASS|escalated", gate):
        continue
    p = re.search(r"Parent:\s*([^\s|]+)", t)
    runs[f] = (os.path.basename(f)[len("think-"):-len(".md")], p.group(1) if p else "none")
parents = {par for _, par in runs.values()}
leaves = sorted((f for f, (rid, _) in runs.items() if rid not in parents), key=os.path.getmtime, reverse=True)
for f in leaves[:20]:
    print(f)
if len(leaves) > 20:
    print("+%d more (older; list them with the run manager)" % (len(leaves) - 20))
PY
)
if [ -n "$open_runs" ]; then
  echo "Open run protocols (continue one with its path):"
  printf '%s\n' "$open_runs" | sed 's/^/  /'
fi
echo "Next: re-issue the same directive; the skill re-derives its phase by inspection."

# Inactive-checkpoint hint: one line when this session switched the context checkpoint on (the variable
# SAID_CONTEXT_CHECKPOINT=on, or the marker checkpoint-on in its scratchpad), has no context.json, and the user
# settings name no said statusline script (the checkpoint then has nothing to read). Informational only.
sid=$(field 'd.get("session_id","")')
settings="${SAID_SETTINGS:-$HOME/.claude/settings.json}"
if { [ "${SAID_CONTEXT_CHECKPOINT:-}" = on ] || [ -f "$SCRATCH_ROOT/$slug/$sid/scratchpad/checkpoint-on" ]; } &&
   [ ! -f "$SCRATCH_ROOT/$slug/$sid/scratchpad/context.json" ] &&
   ! grep -Eq 'statusline-context\.sh|said-statusline\.sh' "$settings" 2>/dev/null; then
  echo "context checkpoint inactive: run /said:setup statusline"
fi
exit 0
