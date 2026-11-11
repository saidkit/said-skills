#!/usr/bin/env bash
# SessionStart hook (matcher: clear|compact): launcher for reanchor.py, which re-anchors the session from disk
# after a /clear or a compaction (status reconstruction, open run-protocol files, re-issue instruction). The hook
# JSON on stdin goes straight to the Python file. A missing python3 or any failure prints nothing and exits 0.
# Env: SAID_STATUS, SCRATCH_ROOT, SAID_SETTINGS (read by reanchor.py)
here="$(cd "$(dirname "$0")" && pwd)"
python3 "$here/reanchor.py" 2>/dev/null
exit 0
