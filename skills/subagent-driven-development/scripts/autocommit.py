#!/usr/bin/env python3
"""Opt-in auto-commit and hidden checkpoints for superlite runs.

    autocommit.py on|off|status
    autocommit.py apply [--no-squash]   real commits on the current branch, one per task (--no-squash: one per checkpoint)
    autocommit.py clean      delete refs/superlite/* and the checkpoint state

Default is OFF: commit_task then records a shadow checkpoint commit (never on HEAD, the
branch or the user's index) under refs/superlite/<run>/<Tn> and the work stays uncommitted
in the tree. `on` (or SUPERLITE_AUTOCOMMIT=1, which overrides the file) makes commit_task
commit on the current branch as before. State: .superlite/autocommit.json and
.superlite/checkpoints.json. Stdlib only; commits use the user's git identity, no trailers.
"""
import json
import os
import re
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


def ticket(plan):
    """The first `**Ticket:** KEY` header line of the plan, or None."""
    try:
        for ln in Path(plan).read_text(encoding="utf-8").splitlines():
            if re.match(r"##+\s", ln):  # header block only: a task body never sets the ticket
                break
            m = re.match(r"\s*\*\*Ticket:\*\*\s*(\S.*?)\s*$", ln)
            if m:
                return m.group(1)
    except (OSError, TypeError, ValueError):
        pass
    return None


def message(tid, title, plan):
    """Commit message of a task: `KEY Tn: title` with a plan ticket, else `Tn: title`."""
    key = ticket(plan) if plan else None
    return f"{key} {tid}: {title}" if key else f"{tid}: {title}"


def plan_key(plan):
    """The plan as an absolute path: `plan.md`, `./plan.md` and `/abs/plan.md` name one run."""
    return str(Path(plan).resolve()) if plan else plan


def stage(files, env):
    """Stage the working-tree state of `files` into the temporary index `env` names; return its tree."""
    indexed = set(git("ls-files", "-z", "--", *files, env=env).stdout.split("\0")) if files else set()  # O(f + i)
    staged = [f for f in files if os.path.lexists(f) or f in indexed
              or any(i.startswith(f.rstrip("/") + "/") for i in indexed)]  # a removed directory stays staged; O(f * i)
    if staged:  # O(1)
        git("add", "-A", "--", *staged, env=env)  # O(f)
    return git("write-tree", env=env).stdout.strip()  # O(1)


def checkpoint(tid, title, files, plan):
    """Shadow-commit `files` on top of the previous checkpoint (HEAD for the first); return the sha.

    A temporary index holds the parent's tree plus the owned files, so HEAD, the branch,
    the user's index and the working tree are not touched. A file gone from disk and from
    the parent (moved away in an earlier checkpoint) has nothing left to stage."""
    st = load_state()
    if not st or plan_key(st.get("plan")) != plan_key(plan):
        stem = Path(plan).stem if plan else "run"
        st = {"plan": plan_key(plan), "run": f"{stem}-{date.today():%Y%m%d}", "head": head_sha(),
              "branch": git("symbolic-ref", "-q", "HEAD", check=False).stdout.strip(),
              "entries": []}
    parent = st["entries"][-1]["sha"] if st["entries"] else st["head"]
    idx = str(Path(TEMP_INDEX).resolve())
    Path(idx).parent.mkdir(parents=True, exist_ok=True)
    Path(idx).unlink(missing_ok=True)
    env = {"GIT_INDEX_FILE": idx}
    try:
        git("read-tree", parent, env=env) if parent else git("read-tree", "--empty", env=env)
        tree = stage(files, env)
    finally:
        Path(idx).unlink(missing_ok=True)
    msg = message(tid, title, plan)
    cmd = ["commit-tree", tree, "-m", msg] + (["-p", parent] if parent else [])
    sha = git(*cmd).stdout.strip()
    git("update-ref", f"{REF_ROOT}/{st['run']}/{tid}", sha)
    st["entries"].append({"task": tid, "sha": sha, "title": msg, "files": files})
    save_state(st)
    return sha


def refs():
    r = git("for-each-ref", "--format=%(refname)", REF_ROOT, check=False)
    return r.stdout.split()


def plan_stem(plan):
    """The stored plan relative to the repo without its suffix (`docs/plans/p` for docs/plans/p.md), or None."""
    top = git("rev-parse", "--show-toplevel", check=False)
    if not plan or top.returncode != 0:
        return None
    try:
        rel = Path(plan).resolve().relative_to(Path(top.stdout.strip()).resolve())
    except ValueError:
        return None
    return rel.with_suffix("").as_posix()


def dirty_outside(files, plan=None):
    r = git("status", "--porcelain", "-z", "--untracked-files=all", "--no-renames")
    stem = plan_stem(plan)
    bad = []
    for e in r.stdout.split("\0"):
        if len(e) > 3:
            p = e[3:].replace("\\", "/")
            if not p.startswith(".superlite/") and "__pycache__/" not in p \
                    and not p.endswith(".pyc") and p not in files \
                    and not (stem and p.startswith(stem + ".")):
                bad.append(p)
    return bad


def edited_since(tree, files):
    """Sorted `files` whose working-tree state differs from `tree`: staging them again would change it."""
    idx = str(Path(TEMP_INDEX).resolve())  # O(1)
    Path(idx).parent.mkdir(parents=True, exist_ok=True)  # O(1)
    Path(idx).unlink(missing_ok=True)  # O(1)
    env = {"GIT_INDEX_FILE": idx}
    try:
        git("read-tree", tree, env=env)  # O(t)
        now = stage(files, env)  # O(f * i)
    finally:
        Path(idx).unlink(missing_ok=True)  # O(1)
    if now == tree:  # O(1)
        return []
    return sorted(p for p in git("diff", "--name-only", "-z", tree, now).stdout.split("\0") if p)  # O(d)


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


def squash_entries(entries):
    """One entry per task in first-seen order: newest sha, first title, union of files in first-seen order."""
    groups = {}
    for e in entries:
        g = groups.get(e["task"])
        if g is None:
            groups[e["task"]] = {"task": e["task"], "sha": e["sha"], "title": e["title"], "files": list(e["files"])}
        else:
            g["sha"] = e["sha"]
            g["files"] += [f for f in e["files"] if f not in g["files"]]
    return list(groups.values())


def interleaved_file(entries):
    """First file where another task's entry sits between a task's first and last entry and touches its files."""
    for g in squash_entries(entries):
        pos = [i for i, e in enumerate(entries) if e["task"] == g["task"]]
        for e in entries[pos[0] + 1:pos[-1]]:
            if e["task"] != g["task"]:
                for f in e["files"]:
                    if f in g["files"]:
                        return f
    return ""


def build_chain(start, entries, moved):
    """Commit each entry on top of `start`; return (list of (entry, tree), final tree) without writing commits."""
    parent, out = start, []
    for e in entries:
        tree = replay_tree(parent, e) if moved else git("rev-parse", f"{e['sha']}^{{tree}}").stdout.strip()
        out.append((e, tree))
        parent = tree
    return out, parent


def apply(squash=True):
    st = load_state()
    if not st or not st.get("entries"):
        sys.exit("apply: no checkpoints recorded (nothing to commit)")
    if git("symbolic-ref", "-q", "HEAD", check=False).stdout.strip() != st.get("branch", ""):
        sys.exit("apply: refused, the checked-out branch changed since the run started")
    files = {f for e in st["entries"] for f in e["files"]}
    left = dirty_outside(files, st.get("plan"))  # unrelated changes stay in the tree, uncommitted
    moved = head_sha() != st["head"]
    hit = moved_overlap(st["head"], head_sha(), files)
    if hit:
        sys.exit("apply: refused, commits made since the run started touched checkpointed files: "
                 + ", ".join(hit[:8]) + (" ..." if len(hit) > 8 else "")
                 + "; commit the files yourself with `git add -A && git commit`")
    start = head_sha()
    plan, note = st["entries"], ""
    groups = squash_entries(st["entries"]) if squash else plan
    hit_file = interleaved_file(plan) if len(groups) != len(plan) else ""
    if hit_file:
        note = f"squash skipped: tasks interleave on {hit_file}"
    elif len(groups) != len(plan):
        ref, ref_tree = build_chain(start, plan, moved)
        if moved:
            ref_final = ref_tree
        else:
            ref_final = git("rev-parse", f"{plan[-1]['sha']}^{{tree}}").stdout.strip()
        chain, final = build_chain(start, groups, True)
        if final == ref_final:
            plan = groups
        else:
            d = git("diff", "--name-only", final, ref_final).stdout.split()
            note = f"squash skipped: tasks interleave on {d[0] if d else '?'}"
    parent = start
    chain, final = build_chain(start, plan, moved or plan is not st["entries"])
    edited = edited_since(final, sorted(files))
    if edited:
        sys.exit("apply: refused, files edited after their checkpoint: "
                 + ", ".join(edited[:8]) + (" ..." if len(edited) > 8 else "")
                 + "; checkpoint them again with `sl commit_task`, or commit the files yourself with `git add -A && git commit`")
    for e, tree in chain:
        parent = git("commit-tree", tree, "-m", e["title"],
                     *(["-p", parent] if parent else [])).stdout.strip()
    git("update-ref", "-m", "superlite: apply checkpoints", "HEAD", parent, *([start] if start else []))
    git("reset", "-q", "--", *sorted(files), env={"GIT_LITERAL_PATHSPECS": "1"})  # the run's files to the new HEAD; unrelated staged changes stay staged, the tree is untouched
    if note:
        print(note)
    print(f"applied {len(plan)} commit(s) on {st.get('branch') or 'HEAD'}:")
    for e in plan:
        print(f"- {e['title']}")
    if left:
        print("apply: left uncommitted: " + ", ".join(left[:8]) + (" ..." if len(left) > 8 else ""))
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
    elif cmd == "apply" and set(argv[1:]) <= {"--no-squash"}:
        return apply(squash="--no-squash" not in argv[1:])
    elif cmd == "clean":
        clean()
    else:
        print(__doc__.split("\n")[0] + "\nusage: autocommit.py on|off|status|apply [--no-squash]|clean", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
