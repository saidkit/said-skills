#!/usr/bin/env python3
"""Statusline install for said:setup: check it, or apply it after the operator consented.

The context checkpoint reads a context.json that only the plugin's statusline script writes, and a
plugin cannot set settings.json "statusLine" itself. This script owns that one environment item:

  --check          print one ledger row (ok / STALE / ADVISORY, never BLOCKER); always exits 0.
  --apply          print the planned change and exit 3 (nothing written): show it to the operator.
  --apply --yes    only after the operator confirmed: back up settings.json, copy the version-stable
                   wrapper to ~/.claude/said-statusline.sh, set "statusLine" to run it (no other key
                   is touched), re-parse; exit 0 on success, 1 on any failure (nothing left changed).

Env overrides (tests): SAID_SETTINGS (settings file), SAID_HOME (home dir), SAID_WRAPPER_SRC (the
wrapper to copy).
"""
import argparse
import datetime
import filecmp
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FIX = "run /said:setup statusline"
PINNED = re.compile(r"/said/[^/\s]+/hooks/statusline-context\.sh")


def paths():
    home = os.environ.get("SAID_HOME") or os.path.expanduser("~")
    settings = os.environ.get("SAID_SETTINGS") or os.path.join(home, ".claude", "settings.json")
    src = os.environ.get("SAID_WRAPPER_SRC") or os.path.join(HERE, "..", "..", "hooks", "said-statusline.sh")
    dest = os.path.join(home, ".claude", "said-statusline.sh")
    command = "bash ~/.claude/said-statusline.sh" if "SAID_HOME" not in os.environ else "bash %s" % dest
    return settings, os.path.normpath(src), dest, command


def load(settings):
    """-> (data, error). A missing file is an empty dict; an unparseable one is an error."""
    if not os.path.exists(settings):
        return {}, None
    try:
        with open(settings) as fh:
            data = json.load(fh)
    except (OSError, ValueError) as e:
        return None, "cannot parse %s: %s" % (settings, e)
    if not isinstance(data, dict):
        return None, "%s is not a JSON object" % settings
    return data, None


def check_row():
    """-> dict(item, verdict, severity, remediation): the statusline ledger row."""
    settings, src, dest, _ = paths()
    row = {"item": "statusline", "verdict": "ok", "severity": "ADVISORY", "remediation": "installed"}
    data, err = load(settings)
    if err:
        row.update(verdict="unresolvable", remediation="%s; fix the file, then %s" % (err, FIX))
        return row
    cmd = str(((data or {}).get("statusLine") or {}).get("command") or "")
    if "said-statusline.sh" in cmd:
        if not os.path.isfile(dest) or (os.path.isfile(src) and not filecmp.cmp(src, dest, shallow=False)):
            row.update(verdict="stale", severity="STALE", remediation="wrapper copy missing or outdated; %s" % FIX)
    elif PINNED.search(cmd):
        row.update(verdict="stale", severity="STALE",
                   remediation="statusLine pins a versioned plugin path (breaks on update); %s" % FIX)
    elif "statusline-context.sh" in cmd:
        pass  # an unversioned direct path works; leave it
    else:
        row.update(verdict="missing", remediation="context checkpoint inactive; %s" % FIX)
    return row


def render(row):
    if row["verdict"] == "ok":
        return "  [ok] %-24s %s" % (row["item"], row["remediation"])
    return "  [%s] %-24s %-13s %s" % (row["severity"], row["item"], row["verdict"], row["remediation"])


def _atomic_copy(src, dest, mode=None):
    """Copy src over dest via a sibling tmp file + rename: dest is either the old or the new file."""
    tmp = "%s.tmp-%d" % (dest, os.getpid())
    try:
        shutil.copyfile(src, tmp)
        if mode is not None:
            os.chmod(tmp, mode)
        os.replace(tmp, dest)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def apply(yes):
    settings, src, dest, command = paths()
    data, err = load(settings)
    if err:
        print("ABORT: %s -- nothing written." % err)
        return 1
    if not os.path.isfile(src):
        print("ABORT: wrapper not found at %s -- nothing written." % src)
        return 1
    new = {"type": "command", "command": command}
    real = os.path.realpath(settings)  # write through a symlinked settings.json, never replace the link
    print("settings: %s%s" % (settings, "" if real == os.path.abspath(settings) else " -> %s" % real))
    print("  statusLine now: %s" % json.dumps(data.get("statusLine")))
    print("  statusLine new: %s" % json.dumps(new))
    print("wrapper: copy %s -> %s" % (src, dest))
    if not yes:
        print("PLAN ONLY: nothing written. Re-run with --yes after the operator confirms.")
        return 3

    existed = os.path.exists(real)
    backup = "%s.bak-%s" % (real, datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")) if existed else None
    try:
        if backup:
            shutil.copy2(real, backup)
    except OSError as e:
        print("ABORT: cannot write the backup (%s) -- nothing written." % e)
        if backup and os.path.exists(backup):
            os.remove(backup)
        return 1

    tmp = "%s.tmp-%d" % (real, os.getpid())
    try:
        data["statusLine"] = new
        os.makedirs(os.path.dirname(real), exist_ok=True)
        with open(tmp, "w") as fh:
            json.dump(data, fh, indent=2)
            fh.write("\n")
        os.replace(tmp, real)
        with open(real) as fh:
            json.load(fh)  # parse after write
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        _atomic_copy(src, dest, 0o755)  # last: an old wrapper stays intact until this rename
    except (OSError, ValueError) as e:
        if os.path.exists(tmp):
            os.remove(tmp)
        if backup:
            shutil.copy2(backup, real)
            print("FAILED: %s -- settings restored from backup %s." % (e, backup))
        else:
            if os.path.exists(real):
                os.remove(real)
            print("FAILED: %s -- no settings file existed; none left behind." % e)
        return 1
    if backup:
        print("backup: %s" % backup)
    print("wrote: %s (statusLine only), %s" % (real, dest))
    return 0


def main():
    ap = argparse.ArgumentParser(description="said:setup statusline install (check, or apply with consent).")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true", help="print the statusline ledger row; exit 0")
    g.add_argument("--apply", action="store_true", help="show the change; with --yes, write it")
    ap.add_argument("--yes", action="store_true", help="the operator confirmed the shown change")
    ap.add_argument("--json", action="store_true", help="--check: emit the row as JSON")
    a = ap.parse_args()
    if a.check:
        row = check_row()
        print(json.dumps(row) if a.json else render(row))
        return 0
    return apply(a.yes)


if __name__ == "__main__":
    sys.exit(main())
