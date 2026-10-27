#!/usr/bin/env python3
"""Isolated test tree per task, so parallel agents never compile each other's half-edited files.

    trees.py clean            remove every tree under .superlite/trees, print `removed N`
    trees.py path Tn          print the tree path of task Tn (without creating it)

A tree is a detached git worktree at `.superlite/trees/<task>` on the base commit (the newest
checkpoint, else HEAD). `prepare` resets it to the base and overlays only the task's own files
(modified, new or deleted in the main tree). Untracked build output in the tree is never removed.
Stdlib only.
"""
# Complexity notation: f = changed files in the main tree, o = Owns globs, T = trees
import contextlib  # O(1)
import json  # O(1)
import os  # O(1)
import time  # O(1)
import shutil  # O(1)
import subprocess  # O(1)
import sys  # O(1)
from pathlib import Path  # O(1)

sys.path.insert(0, str(Path(__file__).resolve().parent))  # O(path list)
import next_tasks as nt  # noqa: E402  # O(1) module load

TREES = ".superlite/trees"  # O(1)
STATE = ".superlite/checkpoints.json"  # O(1) same file as autocommit.STATE


def git(root, *args):  # O(output) + process spawn
    r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, encoding="utf-8", errors="replace")  # O(output)
    if r.returncode:  # O(1)
        raise RuntimeError(f"git {' '.join(args)} failed: {r.stderr.strip()}")  # O(1)
    return r.stdout  # O(1)


def base_commit(root):  # O(checkpoints) + one spawn when no checkpoint
    root = Path(root)  # O(1)
    try:  # O(1)
        entries = json.loads((root / STATE).read_text(encoding="utf-8")).get("entries") or []  # O(file)
        if entries and entries[-1].get("sha"):  # O(1)
            return entries[-1]["sha"]  # O(1)
    except (OSError, ValueError, AttributeError):  # O(1)
        pass  # O(1)
    return git(root, "rev-parse", "HEAD").strip()  # O(1) + spawn


def tree_path(root, task):  # O(1)
    return Path(root) / TREES / task  # O(1)


def overlay_file(root, task):  # O(1)
    return Path(root) / TREES / f"{task}.overlay.json"  # O(1)


def split_z(text):  # O(len text)
    return [p for p in text.split("\0") if p]  # O(len text)


def own_changes(root, base, owns):  # O(f * o) + two spawns
    """-> (paths to copy, paths to delete): owned files that differ from base in the main tree."""
    changed = split_z(git(root, "diff", "--name-only", "--no-renames", "-z", base))  # tracked: modified or deleted | O(f)
    changed += split_z(git(root, "ls-files", "-o", "--exclude-standard", "-z"))  # untracked | O(f)
    copy, delete = [], []  # O(1)
    for p in dict.fromkeys(changed):  # O(f) iterations
        if p.startswith(".superlite/") or not nt.owns_match(p, owns):  # O(o)
            continue  # O(1)
        (copy if (Path(root) / p).is_file() else delete).append(p)  # O(1)
    return copy, delete  # O(1)


@contextlib.contextmanager
def lock(root, task, wait=300.0, stale=600.0):  # one prepare per task at a time | O(wait / 0.05)
    path = Path(root) / TREES / f"{task}.lock"  # O(1)
    path.parent.mkdir(parents=True, exist_ok=True)  # O(1)
    t0 = time.monotonic()  # O(1)
    while True:  # O(wait / 0.05) iterations
        try:  # O(1)
            os.close(os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY))  # O(1)
            break  # O(1)
        except FileExistsError:  # O(1)
            try:  # O(1)
                if time.time() - path.stat().st_mtime > stale:  # a crashed holder | O(1)
                    path.unlink(missing_ok=True)  # O(1)
                    continue  # O(1)
            except OSError:  # O(1)
                continue  # O(1)
            if time.monotonic() - t0 > wait:  # O(1)
                raise RuntimeError(f"tree lock for {task} busy") from None  # O(1)
            time.sleep(0.05)  # O(1)
    try:  # O(1)
        yield  # O(1)
    finally:  # O(1)
        path.unlink(missing_ok=True)  # O(1)


def prepare(root, task, owns):  # O(f * o) + git checkout of the tree
    root = Path(root).resolve()  # absolute: git -C and the tree path must agree | O(1)
    with lock(root, task):  # O(1)
        return _prepare(root, task, owns)  # O(f * o)


def _prepare(root, task, owns):  # O(f * o) + git checkout of the tree
    tree = tree_path(root, task)  # O(1)
    base = base_commit(root)  # O(1) + spawn
    tree.parent.mkdir(parents=True, exist_ok=True)  # O(1)
    if (tree / ".git").exists():  # O(1) reuse: keeps untracked build output
        git(tree, "checkout", "--force", "--detach", base)  # O(changed files)
    else:  # O(1)
        git(root, "worktree", "prune")  # drop a registration whose directory vanished | O(T)
        git(root, "worktree", "add", "--force", "--detach", str(tree), base)  # O(files)
    ov = overlay_file(root, task)  # O(1)
    try:  # O(1)
        old = json.loads(ov.read_text(encoding="utf-8"))  # O(overlay)
    except (OSError, ValueError):  # O(1)
        old = []  # O(1)
    tracked = set(split_z(git(tree, "ls-files", "-z")))  # O(files)
    for p in old:  # O(overlay) iterations: untracked-at-base files overlaid last time
        if p not in tracked:  # O(1)
            (tree / p).unlink(missing_ok=True)  # O(1)
    copy, delete = own_changes(root, base, owns)  # O(f * o)
    for p in delete:  # O(f)
        (tree / p).unlink(missing_ok=True)  # O(1)
    for p in copy:  # O(f)
        dst = tree / p  # O(1)
        dst.parent.mkdir(parents=True, exist_ok=True)  # O(1)
        shutil.copy2(root / p, dst)  # O(file size)
    ov.write_text(json.dumps(copy + delete) + "\n", encoding="utf-8")  # O(f)
    return tree  # O(1)


def clean(root):  # O(T) + spawns
    root = Path(root)  # O(1)
    base = root / TREES  # O(1)
    n = 0  # O(1)
    if base.is_dir():  # O(1)
        for d in sorted(base.iterdir()):  # O(T) iterations
            if d.is_dir():  # O(1)
                try:  # O(1)
                    git(root, "worktree", "remove", "--force", str(d))  # O(tree size)
                except RuntimeError:  # O(1)
                    shutil.rmtree(d, ignore_errors=True)  # O(tree size)
                n += 1  # O(1)
            else:  # O(1)
                d.unlink(missing_ok=True)  # O(1) overlay lists
    try:  # O(1)
        git(root, "worktree", "prune")  # O(T)
    except RuntimeError:  # O(1)
        pass  # O(1)
    return n  # O(1)


def main(argv=None):  # O(T) + spawns
    argv = list(sys.argv[1:] if argv is None else argv)  # O(len argv)
    if argv[:1] == ["clean"] and len(argv) == 1:  # O(1)
        print(f"removed {clean('.')}")  # O(T)
        return 0  # O(1)
    if argv[:1] == ["path"] and len(argv) == 2:  # O(1)
        print(tree_path(".", argv[1]).resolve())  # O(1)
        return 0  # O(1)
    print("usage: trees.py clean | path Tn", file=sys.stderr)  # O(1)
    return 2  # O(1)


if __name__ == "__main__":  # O(1)
    sys.exit(main())  # O(1)
