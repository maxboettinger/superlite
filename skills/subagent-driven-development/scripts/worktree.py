#!/usr/bin/env python3
"""Find or create the run's own git worktree, so a change never starts in a shared checkout.

    worktree.py ensure TOPIC [--repo DIR] [--branch NAME] [--dir NAME]     print the absolute path of the run folder
    worktree.py inplace --reason TEXT         opt the marked inline flow out of the main-checkout write refusal
    --plan P (anywhere): accepted and ignored (every lead brief passes it to every sl call, #336)

From a linked worktree the tool returns that worktree. Otherwise it returns (or creates)
`<main root>/.claude/worktrees/superlite-<slug>` on branch `superlite/<slug>`. With `--branch NAME` the branch is NAME as given and the folder `superlite-<slug of NAME>` (reused when it exists). With `--dir NAME` the folder is `<main root>/.claude/worktrees/NAME`, NAME as given, case kept (`[A-Za-z0-9][A-Za-z0-9._-]{0,79}`, else exit 2); the branch rule is unchanged; from a linked worktree `--dir` changes nothing.
The main checkout's
branch and files are never changed. No repository, a real bare one, or no commit yet: the start folder.
Exit 2 when a plain folder sits at the target path, or when the main checkout carries `core.bare=true` (git treats it as bare; `bare_flag(start)` names the cause, #589). A new worktree gets a stderr line naming the ignored
top-level entries of the main checkout it lacks (`.env`, `.venv/`; names only, nothing is copied).
`inplace` sets `inplace` to the reason in the marker `<state folder>/inline-flow.json` that hooks/mark-inline-flow wrote
(hooks/inline-worktree-guard then lets edits in the main checkout pass) and appends `Ruling: in place - TEXT` to the
state folder's progress.md; no marker: nothing changes, exit 0 (#148).
Other open runs of the repository (#493): `ensure` prints stderr lines only. With a plan in the run folder, one `WARNING: OVERLAP:` line per other run whose files the plan's Owns share; without one, one line per other run naming its files. Warn only.
Stdlib only; another run's plan is read through plan_tools.
"""
# Complexity notation: n = length of the topic, w = registered worktrees, e = lines of info/exclude, i = ignored entries,
# r = length of the reason, f = size of the marker file, b = backlog batches, k = files a run owns
import argparse  # O(1)
import fnmatch  # O(1)
import json  # O(1)
import re  # O(1)
import subprocess  # O(1)
import sys  # O(1)
from pathlib import Path  # O(1)

PARENT = ".claude/worktrees"  # O(1)
INTERNAL = {".git", ".superlite", ".claude", "__pycache__", ".DS_Store"}  # (.DS_Store: OS noise a global gitignore lists) never listed as missing (#141) | O(1)
SHOWN = 10  # names in the "missing here" line | O(1)
TAIL = "; the run that merges second merges the default branch first"  # ends every OVERLAP line | O(1)
MARKER = "inline-flow.json"  # in the state folder: written by hooks/mark-inline-flow, read by hooks/inline-worktree-guard | O(1)


class Taken(Exception):  # O(1)
    """A plain folder (not a worktree) sits at the target path."""


class BareCheckout(Exception):  # O(1)
    """The main checkout carries core.bare=true, so git treats it as bare (#589)."""


class BadBranch(Exception):  # O(1)
    """The --branch name is not a valid branch name."""


class BadFolder(Exception):  # O(1)
    """The --dir name is not a valid folder name."""


def git(root, *args):  # O(output) + process spawn
    r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, encoding="utf-8", errors="replace")  # O(output)
    return r.returncode, r.stdout.strip(), r.stderr.strip()  # O(1)


def _bare_common(start):  # O(1) + spawns
    """-> the common git dir (Path) when `start` is a bare-flagged normal checkout, else None."""
    if git(start, "rev-parse", "--is-bare-repository")[1] != "true":  # O(1) + spawn
        return None  # O(1)
    rc, out, _ = git(start, "rev-parse", "--path-format=absolute", "--git-common-dir")  # O(1) + spawn
    common = Path(out) if not rc and out else None  # O(1)
    return common if common is not None and common.name == ".git" else None  # O(1) a real bare repo is not named .git


def bare_flag(start):  # O(1) + spawns
    """-> 'core.bare=true in <config>' when `start` sits in a normal checkout flagged bare, else ''."""
    common = _bare_common(start)  # O(1) + spawns
    return "" if common is None else f"core.bare=true in {common / 'config'}"  # O(1)


def slug(topic):  # O(n)
    s = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")[:40].strip("-")  # O(n)
    return s or "change"  # O(1)


def is_linked(root):  # O(1) file read
    try:  # O(1)
        text = (Path(root) / ".git").read_text(encoding="utf-8", errors="replace")  # O(file)
    except OSError:  # O(1) no .git file (a directory raises too)
        return False  # O(1)
    for line in text.splitlines():  # O(lines)
        if line.startswith("gitdir:"):  # O(1)
            parts = line[7:].strip().replace("\\", "/").rstrip("/").split("/")  # O(len line)
            return len(parts) >= 2 and parts[-2] == "worktrees"  # O(1)
    return False  # O(1)


def no_repo_reason(start):  # O(1) + spawns
    """-> why `start` is not usable as a repository ('' when it is)."""
    if git(start, "rev-parse", "--show-toplevel")[0]:  # O(1) + spawn
        return "no git repository"  # O(1)
    if git(start, "rev-parse", "--verify", "-q", "HEAD")[0]:  # O(1) + spawn
        return "no commit yet"  # O(1)
    return ""  # O(1)


def add_exclude(root, rel, probe):  # O(e) + spawns
    if git(root, "check-ignore", "-q", probe)[0] == 0:  # O(1) + spawn
        return  # O(1) already ignored
    rc, out, _ = git(root, "rev-parse", "--git-common-dir")  # O(1) + spawn
    if rc or not out:  # O(1) no git dir to write to
        return  # O(1)
    common = Path(root) / out  # O(1) absolute out replaces root
    f = common / "info" / "exclude"  # O(1)
    line = rel.rstrip("/") + "/"  # O(1)
    old = f.read_text(encoding="utf-8", errors="replace") if f.exists() else ""  # O(file)
    if line in old.splitlines():  # O(e)
        return  # O(1)
    f.parent.mkdir(parents=True, exist_ok=True)  # O(1)
    f.write_text(old + ("" if not old or old.endswith("\n") else "\n") + line + "\n", encoding="utf-8")  # O(file)


def missing_ignored(main, wt):  # O(i) + one process spawn
    """-> sorted names (`.env`, `.venv/`) of the ignored top-level entries of the main checkout that `wt` lacks."""
    rc, out, _ = git(main, "ls-files", "-z", "--others", "--ignored", "--exclude-standard", "--directory")  # O(i) + spawn
    if rc:  # O(1)
        return []  # O(1)
    names = set()  # O(1)
    for entry in out.split("\0"):  # O(i)
        bare = entry.rstrip("/")  # O(1)
        if bare and "/" not in bare and bare not in INTERNAL and not (Path(wt) / bare).exists():  # O(1) stat
            names.add(entry)  # O(1)
    return sorted(names)  # O(i log i)


def missing_line(names):  # O(1)
    """-> the stderr line for `missing_ignored` names, '' when there are none."""
    if not names:  # O(1)
        return ""  # O(1)
    more = f" (+{len(names) - SHOWN} more)" if len(names) > SHOWN else ""  # O(1)
    return "worktree: ignored in the main checkout, missing here: " + ", ".join(names[:SHOWN]) + more  # O(1)


def listed_branch(top, target):  # O(w) + spawn
    """-> None when no registered worktree sits at `target`, else its short branch name ('' when detached)."""
    found = None  # O(1)
    here = False  # O(1)
    for ln in git(top, "worktree", "list", "--porcelain")[1].splitlines():  # O(w)
        if ln.startswith("worktree "):  # O(1)
            here = Path(ln[9:]).resolve() == target.resolve()  # O(1)
            found = "" if here else found  # O(1)
        elif here and ln.startswith("branch refs/heads/"):  # O(1)
            found = ln[18:]  # O(1)
    return found  # O(1)


def ensure(topic, start, branch=None, folder=None):  # O(w) + spawns
    """-> (run folder, state): created / exists / linked / no-repo. `branch` names the branch and the folder (superlite-<slug of branch>); `folder` names the folder as given."""
    if folder is not None and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", folder):  # O(len folder)
        raise BadFolder(f"invalid folder name: {folder}")  # O(1)
    start = Path(start).resolve()  # O(1)
    common = _bare_common(start)  # O(1) + spawns
    if common is not None:  # O(1)
        raise BareCheckout(f"core.bare=true in {common / 'config'}: git treats the checkout {common.parent} as bare; run git -C {common.parent} config core.bare false")  # O(1)
    if no_repo_reason(start):  # O(1) + spawns
        return start, "no-repo"  # O(1)
    top = Path(git(start, "rev-parse", "--show-toplevel")[1])  # O(1) + spawn
    if git(top, "rev-parse", "--is-bare-repository")[1] == "true":  # O(1) + spawn
        return start, "no-repo"  # O(1)
    if branch is not None:  # O(1)
        rc, out, _ = git(top, "check-ref-format", "--branch", branch)  # O(1) + spawn
        if rc or out != branch:  # O(1)
            raise BadBranch(f"invalid branch name: {branch}")  # O(1)
    if is_linked(top):  # O(1)
        return top, "linked"  # O(1)
    s = slug(topic if branch is None else branch)  # O(n)
    name = f"superlite-{s}" if folder is None else folder  # O(1)
    target = top / PARENT / name  # O(1)
    br = f"superlite/{s}" if branch is None else branch  # O(1)
    other = listed_branch(top, target)  # O(w) + spawn
    if other is not None:  # O(1)
        if target.is_dir():  # O(1)
            if branch is None or other == branch:  # O(1)
                return target, "exists"  # O(1)
            raise Taken(f"{target} is a worktree on {other or 'a detached HEAD'}, not {branch}")  # O(1)
        git(top, "worktree", "prune")  # O(w) + spawn: folder was deleted, drop the stale registration
    if target.exists() or target.is_symlink():  # O(1)
        raise Taken(f"{target} exists and is not a git worktree")  # O(1)
    add_exclude(top, PARENT, f"{PARENT}/{name}/x")  # O(e) + spawns
    if git(top, "show-ref", "--verify", "-q", f"refs/heads/{br}")[0] == 0:  # O(1) + spawn
        rc, _, err = git(top, "worktree", "add", str(target), br)  # O(files) + spawn
    else:  # O(1)
        rc, _, err = git(top, "worktree", "add", "-b", br, str(target), "HEAD")  # O(files) + spawn
    if rc:  # O(1)
        raise RuntimeError(f"git worktree add failed: {err}")  # O(1)
    return target, "created"  # O(1)


def run_plan(root):  # O(f) file read
    """-> the plan file named by `root/.superlite/stable.json` (key `plan`) when it exists, else None."""
    try:  # O(1)
        data = json.loads((Path(root) / ".superlite" / "stable.json").read_text(encoding="utf-8"))  # O(f)
        plan = Path(data["plan"])  # O(1)
        return plan if plan.is_file() else None  # O(1)
    except (OSError, ValueError, KeyError, TypeError):  # O(1) absent, unreadable or not an object
        return None  # O(1)


def _plan_owns(plan):  # O(plan) parse
    """-> every Owns entry of the plan's tasks ([] when the plan is unreadable)."""
    try:  # O(1)
        import plan_tools  # noqa: E402  # O(1) lazy: only an open run's plan needs it
        return [o for t in plan_tools.Plan.load(str(plan)).tasks for o in t.owns]  # O(plan)
    except Exception:  # O(1) warn only: a broken plan gives no files
        return []  # O(1)


def _batches(main):  # O(f + b)
    """-> the batches of `main/.superlite/backlog.json` ([] when absent or broken)."""
    try:  # O(1)
        data = json.loads((Path(main) / ".superlite" / "backlog.json").read_text(encoding="utf-8"))  # O(f)
        batches = data["batches"]  # O(1)
        return [b for b in batches if isinstance(b, dict)] if isinstance(batches, list) else []  # O(b)
    except (OSError, ValueError, KeyError, TypeError):  # O(1)
        return []  # O(1)


def open_runs(top, here=None):  # O(w*plan + b) + spawn
    """-> the other open runs of the repository of `top`: [{label, path, files}] sorted by path; [] on any failure."""
    try:  # O(1)
        me = Path(here if here is not None else top).resolve()  # O(1)
        rc, out, _ = git(top, "worktree", "list", "--porcelain")  # O(w) + spawn
        if rc:  # O(1)
            return []  # O(1)
        blocks = [b.splitlines() for b in out.split("\n\n") if b.strip()]  # O(w)
        runs = {}  # resolved path -> run | O(1)
        main = None  # O(1)
        for i, lines in enumerate(blocks):  # O(w)
            path = Path(lines[0][9:]).resolve() if lines[0].startswith("worktree ") else None  # O(1)
            if i == 0:  # O(1)
                main = path  # O(1)
            if path is None or "bare" in lines or path == me or not path.is_dir():  # O(1)
                continue  # O(1)
            plan = run_plan(path)  # O(f)
            if plan is None:  # O(1)
                continue  # O(1)
            branch = next((ln[18:] for ln in lines if ln.startswith("branch refs/heads/")), path.name)  # O(1)
            runs[path] = {"label": branch, "path": path.as_posix(), "files": set(_plan_owns(plan))}  # O(plan)
        for b in _batches(main) if main is not None else []:  # O(b)
            wt, state = b.get("worktree"), b.get("state")  # O(1)
            if not wt or state in ("planned", "shipped") or not Path(str(wt)).is_dir():  # O(1)
                continue  # O(1)
            path = Path(str(wt)).resolve()  # O(1)
            if path == me:  # O(1)
                continue  # O(1)
            run = runs.setdefault(path, {"label": "", "path": path.as_posix(), "files": set()})  # O(1)
            run["label"] = f"{b.get('id', '?')} ({state})"  # O(1)
            run["files"].update(str(f) for f in b.get("files") or [] if isinstance(f, str))  # O(k)
        return [{"label": r["label"], "path": r["path"], "files": sorted(r["files"])} for _, r in sorted(runs.items(), key=lambda kv: kv[1]["path"]) if r["files"]]  # O(w*k log k)
    except Exception:  # O(1) warn only
        return []  # O(1)


def _norm(entry):  # O(len entry)
    e = entry.replace("\\", "/")  # O(len)
    while e.startswith("./"):  # O(1)
        e = e[2:]  # O(len)
    return e  # O(1)


def _same(a, b):  # O(len a + len b)
    if a == b:  # O(1)
        return True  # O(1)
    if (a.endswith("/") and b.startswith(a)) or (b.endswith("/") and a.startswith(b)):  # O(len)
        return True  # O(1) one is a folder holding the other
    return fnmatch.fnmatchcase(a, b) or fnmatch.fnmatchcase(b, a)  # O(len a * len b)


def overlaps(mine, theirs):  # O(k*j)
    """-> the entries of `mine` (as written, sorted, unique) that equal, sit under, or glob-match an entry of `theirs`."""
    other = [_norm(t) for t in theirs]  # O(j)
    return sorted({m for m in mine if any(_same(_norm(m), t) for t in other)})  # O(k*j)


def shown_list(items, limit=5):  # O(limit)
    more = f" (+{len(items) - limit} more)" if len(items) > limit else ""  # O(1)
    return ", ".join(items[:limit]) + more  # O(limit)


def overlap_line(run, shared):  # O(limit)
    return f"OVERLAP: {shown_list(shared)} also owned by open run {run['label']} at {run['path']}" + TAIL  # O(limit)


def ensure_lines(path, state):  # O(w*plan) + spawn
    """-> the stderr lines about other open runs for the run folder `path`; [] for no-repo or on any failure."""
    if state == "no-repo":  # O(1)
        return []  # O(1)
    try:  # O(1)
        runs = open_runs(path, here=path)  # O(w*plan)
        plan = run_plan(path)  # O(f)
        if plan is None:  # O(1)
            return [f"worktree: open run {r['label']} at {r['path']} owns {len(r['files'])} file{'' if len(r['files']) == 1 else 's'}: {shown_list(r['files'])}; keep your plan's Owns off them (plan lint warns on a shared file)" for r in runs]  # O(w*k)
        mine = _plan_owns(plan)  # O(plan)
        return [f"worktree: WARNING: {overlap_line(r, sh)}" for r in runs for sh in [overlaps(mine, r["files"])] if sh]  # O(w*k*j)
    except Exception:  # O(1) warn only
        return []  # O(1)


def inplace(reason, sd):  # O(f + r)
    """Record the in-place opt-out in the inline-flow marker of state folder `sd` and the ledger -> False when no marker."""
    f = Path(sd) / MARKER  # O(1)
    try:  # O(1)
        data = json.loads(f.read_text(encoding="utf-8"))  # O(f)
    except (OSError, ValueError):  # O(1) absent or unreadable
        return False  # O(1)
    if not isinstance(data, dict):  # O(1)
        return False  # O(1)
    data["inplace"] = reason  # O(1)
    f.write_text(json.dumps(data) + "\n", encoding="utf-8")  # O(f + r)
    with (Path(sd) / "progress.md").open("a", encoding="utf-8") as fh:  # O(1)
        fh.write(f"Ruling: in place - {reason}\n")  # O(r)
    return True  # O(1)


def main(argv=None):  # O(w) + spawns
    import autocommit  # O(1) lazy, as trees.main
    argv, plan = autocommit.split_plan(list(sys.argv[1:] if argv is None else argv))  # --plan P / --plan=P removed, value ignored | O(len argv)
    if plan == "":  # O(1) --plan without a value
        print("usage: worktree ensure TOPIC [--repo DIR] [--branch NAME] [--dir NAME] | inplace --reason TEXT [--plan P]", file=sys.stderr)  # O(1)
        return 2  # O(1)
    ap = argparse.ArgumentParser(prog="worktree", epilog="--plan P (anywhere): accepted and ignored; lead briefs pass it to every sl call (#336)")  # O(1)
    sub = ap.add_subparsers(dest="cmd", required=True)  # O(1)
    e = sub.add_parser("ensure")  # O(1)
    e.add_argument("topic")  # O(1)
    e.add_argument("--repo", default=".")  # O(1)
    e.add_argument("--branch", metavar="NAME", default=None)  # O(1)
    e.add_argument("--dir", metavar="NAME", default=None, dest="folder")  # O(1)
    i = sub.add_parser("inplace")  # O(1)
    i.add_argument("--reason", required=True)  # O(1)
    a = ap.parse_args(argv)  # O(args)
    if a.cmd == "inplace":  # O(1)
        import state  # noqa: E402  # O(1) module load, only for this subcommand
        reason = " ".join(a.reason.split())  # one ledger line | O(r)
        if not reason:  # O(1)
            print("worktree: inplace needs a non-empty --reason", file=sys.stderr)  # O(1)
            return 2  # O(1)
        if not inplace(reason, state.resolve()):  # O(d + f)
            print("worktree: no inline flow is marked here; nothing to opt out of", file=sys.stderr)  # O(1)
            return 0  # O(1)
        print(f"worktree: in place - {reason}; edits in this checkout are no longer refused")  # O(r)
        return 0  # O(1)
    try:  # O(1)
        path, state = ensure(a.topic, Path(a.repo), a.branch, a.folder)  # O(w) + spawns
    except (Taken, BadBranch, BadFolder, BareCheckout) as ex:  # O(1)
        print(f"worktree: {ex}", file=sys.stderr)  # O(1)
        return 2  # O(1)
    except RuntimeError as ex:  # O(1)
        print(f"worktree: {ex}", file=sys.stderr)  # O(1)
        return 1  # O(1)
    if state == "no-repo":  # O(1)
        print(f"worktree: {no_repo_reason(path) or 'bare repository'}; using {path.as_posix()} as is", file=sys.stderr)  # O(1)
    elif state == "linked" and a.branch is not None:  # O(1)
        cur = git(path, "rev-parse", "--abbrev-ref", "HEAD")[1]  # O(1) + spawn
        if cur != a.branch:  # O(1)
            print(f"worktree: linked worktree is on {cur}, not {a.branch}; --branch ignored", file=sys.stderr)  # O(1)
    elif state == "linked" and a.folder is not None and path.name != a.folder:  # O(1)
        print(f"worktree: linked worktree is {path.as_posix()}; --dir ignored", file=sys.stderr)  # O(1)
    elif state == "created":  # O(1)
        line = missing_line(missing_ignored(path.parents[len(PARENT.split("/"))], path))  # the main root above <PARENT>/<name> | O(i) + spawn
        if line:  # O(1)
            print(line, file=sys.stderr)  # O(1)
    for line in ensure_lines(path, state):  # O(w*plan)
        print(line, file=sys.stderr)  # O(1)
    print(path.as_posix())  # O(1)
    return 0  # O(1)


if __name__ == "__main__":  # O(1)
    sys.exit(main())  # O(1)
