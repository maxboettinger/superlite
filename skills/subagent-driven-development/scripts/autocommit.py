#!/usr/bin/env python3
"""Opt-in auto-commit and hidden checkpoints for superlite runs.

    autocommit.py on|off|status
    autocommit.py apply      make real commits on the current branch from the checkpoints
    autocommit.py clean      delete refs/superlite/* and the checkpoint state

Default is OFF: commit_task then records a shadow checkpoint commit (never on HEAD, the
branch or the user's index) under refs/superlite/<run>/<Tn> and the work stays uncommitted
in the tree. `on` (or SUPERLITE_AUTOCOMMIT=1, which overrides the file) makes commit_task
commit on the current branch as before. State: .superlite/autocommit.json and
.superlite/checkpoints.json. Stdlib only; commits use the user's git identity, no trailers.
"""
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

CONFIG = ".superlite/autocommit.json"
STATE = ".superlite/checkpoints.json"
TEMP_INDEX = ".superlite/checkpoint.index"
REF_ROOT = "refs/superlite"
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
TRUE, FALSE = ("1", "true", "yes", "on"), ("0", "false", "no", "off")


def git(*args, env=None, check=True):
    r = subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8",
                       env={**os.environ, **env} if env else None)
    if check and r.returncode != 0:
        sys.exit(f"git {' '.join(args[:2])} failed: {(r.stderr or r.stdout).strip()}")
    return r


def is_on():
    """Env SUPERLITE_AUTOCOMMIT wins, then .superlite/autocommit.json; default off."""
    env = os.environ.get("SUPERLITE_AUTOCOMMIT", "").strip().lower()
    if env in TRUE:
        return True
    if env in FALSE and env:
        return False
    try:
        return bool(json.loads(Path(CONFIG).read_text(encoding="utf-8")).get("autocommit"))
    except (OSError, ValueError, AttributeError):
        return False


def set_on(value):
    p = Path(CONFIG)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"autocommit": bool(value)}) + "\n", encoding="utf-8")


def load_state():
    try:
        return json.loads(Path(STATE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def save_state(st):
    p = Path(STATE)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(st, indent=1) + "\n", encoding="utf-8")


def head_sha():
    r = git("rev-parse", "--verify", "-q", "HEAD", check=False)
    return r.stdout.strip() if r.returncode == 0 else ""


def checkpoint(tid, title, files, plan):
    """Shadow-commit `files` on top of the previous checkpoint (HEAD for the first); return the sha.

    A temporary index holds the parent's tree plus the owned files, so HEAD, the branch,
    the user's index and the working tree are not touched."""
    st = load_state()
    if not st or st.get("plan") != plan:
        stem = Path(plan).stem if plan else "run"
        st = {"plan": plan, "run": f"{stem}-{date.today():%Y%m%d}", "head": head_sha(),
              "branch": git("symbolic-ref", "-q", "HEAD", check=False).stdout.strip(),
              "entries": []}
    parent = st["entries"][-1]["sha"] if st["entries"] else st["head"]
    idx = str(Path(TEMP_INDEX).resolve())
    Path(idx).parent.mkdir(parents=True, exist_ok=True)
    Path(idx).unlink(missing_ok=True)
    env = {"GIT_INDEX_FILE": idx}
    try:
        git("read-tree", parent, env=env) if parent else git("read-tree", "--empty", env=env)
        git("add", "-A", "--", *files, env=env)
        tree = git("write-tree", env=env).stdout.strip()
    finally:
        Path(idx).unlink(missing_ok=True)
    cmd = ["commit-tree", tree, "-m", f"{tid}: {title}"] + (["-p", parent] if parent else [])
    sha = git(*cmd).stdout.strip()
    git("update-ref", f"{REF_ROOT}/{st['run']}/{tid}", sha)
    st["entries"].append({"task": tid, "sha": sha, "title": f"{tid}: {title}", "files": files})
    save_state(st)
    return sha


def refs():
    r = git("for-each-ref", "--format=%(refname)", REF_ROOT, check=False)
    return r.stdout.split()


def dirty_outside(files):
    r = git("status", "--porcelain", "-z", "--untracked-files=all", "--no-renames")
    bad = []
    for e in r.stdout.split("\0"):
        if len(e) > 3:
            p = e[3:].replace("\\", "/")
            if not p.startswith(".superlite/") and "__pycache__/" not in p \
                    and not p.endswith(".pyc") and p not in files:
                bad.append(p)
    return bad


def moved_overlap(base, head, files):
    """Checkpointed files touched by the commits in base..head, sorted; [] when HEAD did not move."""
    if base == head or not head or not files:
        return []
    base = base or EMPTY_TREE  # unborn at the start: every file in HEAD now is new since then
    r = git("diff", "--name-only", "-z", base, head, "--", *sorted(files), env={"GIT_LITERAL_PATHSPECS": "1"})
    return sorted(p for p in r.stdout.split("\0") if p)


def replay_tree(parent, entry):
    """Tree of `parent` with each file of the entry taken from the checkpoint (removed when absent there)."""
    idx = str(Path(TEMP_INDEX).resolve())
    Path(idx).parent.mkdir(parents=True, exist_ok=True)
    Path(idx).unlink(missing_ok=True)
    env = {"GIT_INDEX_FILE": idx}
    try:
        git("read-tree", parent, env=env) if parent else git("read-tree", "--empty", env=env)
        lit = {"GIT_LITERAL_PATHSPECS": "1"}
        for f in entry["files"]:
            line = git("ls-tree", "-z", entry["sha"], "--", f, env=lit).stdout.strip("\0")
            if line:
                meta, path = line.split("\t", 1)
                mode, kind, blob = meta.split()
                git("update-index", "--add", "--cacheinfo", f"{mode},{blob},{path}", env=env)
            else:
                git("update-index", "--force-remove", "--", f, env=env)
        return git("write-tree", env=env).stdout.strip()
    finally:
        Path(idx).unlink(missing_ok=True)


def apply():
    st = load_state()
    if not st or not st.get("entries"):
        sys.exit("apply: no checkpoints recorded (nothing to commit)")
    if git("symbolic-ref", "-q", "HEAD", check=False).stdout.strip() != st.get("branch", ""):
        sys.exit("apply: refused, the checked-out branch changed since the run started")
    files = {f for e in st["entries"] for f in e["files"]}
    bad = dirty_outside(files)
    if bad:
        sys.exit("apply: refused, the tree has changes unrelated to the run: "
                 + ", ".join(bad[:8]) + (" ..." if len(bad) > 8 else "")
                 + "; commit or stash them first")
    moved = head_sha() != st["head"]
    hit = moved_overlap(st["head"], head_sha(), files)
    if hit:
        sys.exit("apply: refused, commits made since the run started touched checkpointed files: "
                 + ", ".join(hit[:8]) + (" ..." if len(hit) > 8 else "")
                 + "; commit the files yourself with `git add -A && git commit`")
    start = head_sha()
    parent = start
    for e in st["entries"]:
        if moved:
            tree = replay_tree(parent, e)
        else:
            tree = git("rev-parse", f"{e['sha']}^{{tree}}").stdout.strip()
        parent = git("commit-tree", tree, "-m", e["title"],
                     *(["-p", parent] if parent else [])).stdout.strip()
    git("update-ref", "-m", "superlite: apply checkpoints", "HEAD", parent, *([start] if start else []))
    git("reset", "-q")  # index to the new HEAD; the working tree keeps the agents' files
    print(f"applied {len(st['entries'])} commit(s) on {st.get('branch') or 'HEAD'}:")
    for e in st["entries"]:
        print(f"- {e['title']}")
    clean()
    return 0


def clean():
    for r in refs():
        git("update-ref", "-d", r, check=False)
    Path(STATE).unlink(missing_ok=True)
    print("checkpoints removed")


def listing():
    st = load_state()
    if not st:
        return "no checkpoints"
    out = [f"checkpoints for run {st['run']} (base {st['head'][:10]}):"]
    out += [f"- {e['sha'][:10]} {e['title']} ({len(e['files'])} files)" for e in st["entries"]]
    return "\n".join(out)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    cmd = argv[0] if argv else "status"
    if cmd in ("on", "off"):
        set_on(cmd == "on")
        print(f"autocommit {cmd}")
    elif cmd == "status":
        print(f"autocommit: {'on (commit each task on your branch)' if is_on() else 'off (hidden checkpoints, work stays uncommitted)'}")
        print(listing())
    elif cmd == "apply":
        return apply()
    elif cmd == "clean":
        clean()
    else:
        print(__doc__.split("\n")[0] + "\nusage: autocommit.py on|off|status|apply|clean", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
