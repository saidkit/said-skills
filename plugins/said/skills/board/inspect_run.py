#!/usr/bin/env python3
"""The feature-level Inspect in one command, outside the driving session: the cold read, the gate recompute, the
Covers read, the round and the sign-off, every write through the bundled scripts.

  inspect_run.py <feature-id> --root <lane-root> [--base <rev>] [--mount-base <mount>=<rev>]...
                 [--capture-ref <file|none>] [--ledger <file>]... [--yes <token>]

Steps, in order, one run per lane at a time (a second run while one holds the lane is refused; the lock is a file in
the lane's git dir, never in the tree). A --ledger, a SAID path key outside the lane root, a missing ledger, spec or
task log is an error before any estimate:
  1. The feature-reviewer's read, when the record reads it owed: review-feature/review_feature.py (the code
     /said:review-feature runs) builds the brief, the agent runs headless (`claude -p`, or $SAID_CLAUDE_BIN) and the
     same module files its reply as <working>/review-feature-<id>.md (review-doc-editorial-<id>.md on a doc lane)
     and runs gate_record_row.py --kind feature-review, which validates it and writes its rows. A read spends model
     tokens: without --yes the runner prints the estimate and its yes token and runs no read; --yes runs it only when
     the token is the one the current estimate prints (it covers HEAD, the base and the uncommitted changes). --base (the feature's base commit) and --capture-ref (a
     non-empty capture file in the working dir, never the gate record, or `none` on a feature with no capture) are needed
     for the read. A reply with no verdict line is not filed;
     a reply the writer refuses is not filed either, and is kept in a temp file outside the lane whose path is printed.
  2. gate_recompute.sh over every unit (SAID_GATE_UNITS is never passed), writing the record.
  3. covers-read.py over the task log, its output in <working>/covers-<id>.txt (--ledger names the decision ledgers).
  4. gate_record.py round from that output, then check over every read; the report of the record is printed.
Exit 0 the record is current on every read, 1 something is owed, 2 an input or step error (`error: <why>`),
3 refused: another run holds the lane.
"""
import fcntl
import hashlib
import os
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "review-feature"))
import gate_record  # noqa: E402  the one reader and writer of the record
import review_feature  # noqa: E402  the read's one code path: the brief, the filing and the row write

AGENT_FILE = os.path.join(HERE, "..", "..", "agents", "feature-reviewer.md")
GIT_SET = "`Bash` is for read-only git only:"


def reader_tools(path=AGENT_FILE):
    """The headless reader's --allowedTools, read from the agent's own file: its `tools:` line, with Bash narrowed to
    the git commands its Contract names, so the two cannot drift."""
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    head = text.split("\n---", 1)[0].split("\n")
    tools = [t.strip() for ln in head if ln.startswith("tools:") for t in ln[len("tools:"):].split(",") if t.strip()]
    body = " ".join(text.split())
    if GIT_SET not in body or "Bash" not in tools:
        raise Halt("agents/feature-reviewer.md names no read-only git set")
    git = [g.strip(" `") for g in (body + " ").split(GIT_SET, 1)[1].split(". ", 1)[0].split(",")]
    if not git or not all(g.startswith("git ") for g in git):
        raise Halt("agents/feature-reviewer.md git set is not a list of `git <command>`")
    return ",".join([t for t in tools if t != "Bash"] + ["Bash(%s:*)" % g for g in git])
Halt = review_feature.Error


def round_verdict(root, working, fid):
    """The verdict file when its `target-sha:` is the lane's HEAD, else None: an older read never reads as this one."""
    path = review_feature.out_path(root, working, fid)[0]
    head = (review_feature.git(root, "rev-parse", "HEAD") or "").strip()
    try:
        with open(path, encoding="utf-8") as fh:
            top = [fh.readline() for _ in range(5)]
    except (OSError, UnicodeDecodeError):
        return None
    return path if head and "target-sha: %s\n" % head in top else None


def parse(argv):
    if not argv or argv[0].startswith("-"):
        raise Halt("usage: inspect_run.py <feature-id> --root <lane-root> [--base <rev>] [--mount-base <mount>=<rev>]..."
                   " [--capture-ref <file|none>] [--ledger <file>]... [--yes <token>]")
    fid, opts, ledgers, i = review_feature.feature_id(argv[0]), {"mount-base": []}, [], 1
    while i < len(argv):
        k = argv[i]
        if i + 1 >= len(argv) or k not in ("--root", "--base", "--mount-base", "--capture-ref", "--ledger", "--yes"):
            raise Halt("unknown or incomplete option %s" % k)
        if k == "--ledger":
            ledgers.append(argv[i + 1])
        elif k == "--mount-base":
            opts["mount-base"].append(argv[i + 1])
        else:
            opts[k[2:]] = argv[i + 1]
        i += 2
    opts["root"] = review_feature.lane_root(opts.get("root"))
    opts["ledgers"] = review_feature.ledgers(opts["root"], ledgers)
    opts["mount-base"] = review_feature.mount_bases(opts["mount-base"])
    return fid, opts


def lock(root):
    """The lane's run lock, held until this process exits; None when another run holds it. It lives in the lane's git
    dir (never in the tree, so the store is not touched); a lane outside git uses the temp dir."""
    name = "said-inspect-%s.lock" % hashlib.sha256(root.encode("utf-8")).hexdigest()[:16]
    where = (git(root, "rev-parse", "--absolute-git-dir") or "").strip() or tempfile.gettempdir()
    fh = open(os.path.join(where, name), "a")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fh.close()
        return None
    return fh


def git(root, *args):
    r = subprocess.run(["git", "-C", root] + list(args), capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def feature_review(fid, opts, root):
    """Run the read when it is owed and the yes matches; print what was done. Never raises on a reader failure."""
    p = review_feature.prepare(fid, root, opts.get("base"), opts.get("capture-ref"), opts["ledgers"], opts["mount-base"])
    if p["state"] != "ready":
        print("feature-review: %s" % (p["why"] if p["state"] != "owed" else "owed (%s)" % p["why"]))
        return
    dirty = hashlib.sha256((git(root, "status", "--porcelain", "-z") or "").encode("utf-8")).hexdigest()
    token = hashlib.sha256(("%s|%s|%s|%s|%d" % (root, p["head"], p["base"] + p["mounts"], dirty, p["tokens"])).encode("utf-8")).hexdigest()[:10]
    print("estimate: at least %d input tokens (%d characters read once, divided by 4); every reader turn re-sends"
          " what it has read, so the spend is several times that" % (p["tokens"], p["chars"]))
    print("yes token: %s" % token)
    if "yes" not in opts:
        print("feature-review: owed (no read without a yes: rerun with --yes %s to spend)" % token)
        return
    if opts["yes"] != token:
        print("feature-review: refused, --yes is not the token of this estimate (%s); no read" % token)
        return
    cmd = [os.environ.get("SAID_CLAUDE_BIN") or "claude", "-p", "--agent", review_feature.AGENT, "--allowedTools", reader_tools(),
           "--output-format", "text"]
    try:
        r = subprocess.run(cmd, input=p["brief"], capture_output=True, text=True, cwd=root, timeout=3600)
        reply = r.stdout if r.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired) as e:
        reply = ""
        print("feature-review: the read did not run (%s)" % e.__class__.__name__)
    code, lines = review_feature.file_reply(fid, root, reply, opts["ledgers"])
    print("feature-review: %s" % (lines[1] if len(lines) > 1 else lines[0]))  # the writer's first line, else why not filed
    if code and lines[0].startswith("not filed"):  # a refused reply is kept outside the lane, never at the verdict path
        print("feature-review: the refused reply is kept at %s" % review_feature.keep_refused(fid, reply))


def main(argv):
    try:
        fid, opts = parse(argv)
        root = opts["root"]
        working = review_feature.lane_path(root, "working", fid)
        tasks = review_feature.lane_path(root, "task-log", fid)
        record = os.path.join(working, "gate-%s.md" % fid)
    except (Halt, gate_record.Error) as e:
        print("error: %s" % e)
        return 2
    held = lock(root)
    if held is None:
        print("refused: another inspect run holds this lane; one gate run at a time")
        return 3
    try:
        os.makedirs(working, exist_ok=True)
        feature_review(fid, opts, root)
        env = {k: v for k, v in os.environ.items() if k not in ("SAID_GATE_UNITS",)}
        env.update(SAID_ROOT=root, SAID_GATE_OUT=record)
        g = subprocess.run(["bash", os.path.join(HERE, "gate_recompute.sh")], capture_output=True, text=True, env=env)
        if g.returncode > 1:
            raise Halt("gate_recompute.sh exit %d: %s" % (g.returncode, (g.stdout.strip().split("\n") or [""])[-1]))
        print("gate-recompute: exit %d, %d row(s)" % (g.returncode, g.stdout.count("gate-recompute: ")))
        covers = [sys.executable, os.path.join(HERE, "..", "review-qa", "covers-read.py"), "--task-file", tasks,
                  "--root", root, "--working", working, "--rulings", os.path.join(working, "rulings.md")]
        docs = (gate_record.lane_key(root, "docs-root") or "docs/").strip().strip("`'\"")
        for flag, name in (("--todo", "todo.md"), ("--backlog", "backlog.md")):
            if os.path.isfile(os.path.join(root, docs, name)):
                covers += [flag, os.path.join(root, docs, name)]
        for p in opts["ledgers"]:
            covers += ["--ledger", p]
        verdict = round_verdict(root, working, fid)
        if verdict:  # the matrix reviewer column reads the round's verdict
            covers += ["--reviewer", verdict]
        c = subprocess.run(covers, capture_output=True, text=True)
        if c.returncode == 2:
            raise Halt("covers-read.py: %s" % c.stdout.strip()[-300:])
        cov = os.path.join(working, "covers-%s.txt" % fid)
        with open(cov, "w", encoding="utf-8") as fh:
            fh.write(c.stdout)
        gate_record.do_round(root, record, cov, [])
        rep = gate_record.report(root, record)
        print("\n".join(gate_record.report_text(rep, root)))
        code, line = gate_record.check(root, record, list(gate_record.READS))
        print(line)
        return 0 if code == 0 and not rep["owed"] else 1
    except gate_record.Refused as e:
        print("error: round refused: %s" % e)
        return 2
    except (Halt, gate_record.Error, OSError) as e:
        print("error: %s" % e)
        return 2
    finally:
        held.close()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
