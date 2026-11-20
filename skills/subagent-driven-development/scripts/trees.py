#!/usr/bin/env python3
"""Isolated test tree per task, so parallel agents never compile each other's half-edited files.

    trees.py clean [--plan P] [--module-cache-hours H]
                                remove every tree under .superlite/trees, print `removed N`, then remove the
                                Xcode DerivedData folders of trees that no longer exist; with the option, also
                                the ModuleCache.noindex entries untouched for H hours
    trees.py path Tn [--plan P] print the tree path of task Tn (without creating it)
    trees.py refresh [--onto REV] [--plan P]
                                report how the trees follow a run moved off its base; with --onto, first move
                                the run onto REV (fast-forward or rebase) unless REV changes files of the run (#908)

`--plan P` (anywhere in the arguments) works in the git checkout holding P, else in the current folder.

A tree is a detached git worktree at `.superlite/trees/<task>` on the base commit (the newest
checkpoint, else HEAD; after the run moved onto a newer HEAD (fast-forward or rebase), HEAD plus the newest
checkpoint's changes since the run's base, `moved_base`, #908). `prepare` resets it to the base and overlays only the task's own files
(modified, new or deleted in the main tree). Untracked build output in the tree is never removed by `prepare`.
Cleanup (GitHub #574): `busy` marks a tree in use (`<key>.busy.<pid>`), `reap` drops the trees of committed tasks and
stopped workers that are not busy, `clean_idle` drops every tree nothing runs in, `sweep_scratch_builds` removes Xcode
build folders in a removed worktree's Claude Code session scratchpads (#614), `sweep_derived_data` removes orphaned DerivedData of removed trees, `disk_gate`
refuses on a nearly full disk (`disk_levels` gives its two levels). Thresholds come from SUPERLITE_DISK_FLOOR_GB (20), SUPERLITE_DISK_WARN_GB (50) and
SUPERLITE_DERIVED_DATA_HOME, read at call time. Nothing is removed outside .superlite/trees and the DerivedData home.
Simulators (#672): `listed_simulators` reads a worktree's .superlite/simulators.txt, `remove_simulators` shuts down and
deletes each listed one (argv list, never a shell; `simctl_argv` is `xcrun simctl` or SUPERLITE_SIMCTL),
`simulator_devices` lists the devices, `present_simulators` keeps the entries a device still matches.
Stdlib only.
"""
# Complexity notation: f = changed files in the main tree, o = Owns globs, T = trees
import contextlib  # O(1)
import json  # O(1)
import os  # O(1)
import plistlib  # O(1)
import re  # O(1)
import shlex  # O(1)
import time  # O(1)
import shutil  # O(1)
import subprocess  # O(1)
import sys  # O(1)
from pathlib import Path  # O(1)

sys.path.insert(0, str(Path(__file__).resolve().parent))  # O(path list)
import next_tasks as nt  # noqa: E402  # O(1) module load

TREES = ".superlite/trees"  # O(1)
STATE = ".superlite/checkpoints.json"  # O(1) same file as autocommit.STATE
GIB = 1024 ** 3  # O(1)
KEY = re.compile(r"[A-Za-z0-9_-]+")  # O(1) a tree key that may be removed
STAGE_TIMEOUT = 240  # O(1) seconds one stage git call may run; below the 300 s tree lock wait


def git(root, *args):  # O(output) + process spawn
    r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, encoding="utf-8", errors="replace")  # O(output)
    if r.returncode:  # O(1)
        raise RuntimeError(f"git {' '.join(args)} failed: {r.stderr.strip()}")  # O(1)
    return r.stdout  # O(1)


_MOVED = {}  # O(1) (resolved root, base, newest, head) -> moved_base result, per process
_WARNED = set()  # O(1) memo keys whose fallback line was printed


def _git_env(root, args, env=None, stdin=None):  # git with extra environment and optional stdin; stdout | O(output) + spawn
    full = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE")}  # O(env)
    full.update(env or {})  # O(env)
    r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, encoding="utf-8", errors="replace", env=full, input=stdin)  # O(output)
    if r.returncode:  # O(1)
        raise RuntimeError(f"git {' '.join(args)} failed: {r.stderr.strip()}")  # O(1)
    return r.stdout  # O(1)


def _tree_changes(root, a, b):  # {path: (mode, sha)} of a..b; mode "0" marks a deletion | O(changes) + spawn
    parts = git(root, "diff-tree", "-r", "-z", "--no-renames", a, b).split("\0")  # O(output)
    out, i = {}, 0  # O(1)
    while i < len(parts) and parts[i].startswith(":"):  # O(changes) iterations
        meta = parts[i][1:].split()  # O(1) oldmode newmode oldsha newsha status
        path = parts[i + 1] if i + 1 < len(parts) else ""  # O(1)
        out[path] = ("0", "0" * 40) if meta[4].startswith("D") else (meta[1], meta[3])  # O(1)
        i += 2  # O(1)
    return out  # O(1)


def _build_moved(root, base, newest, head):  # the moved-base dict for one memo key | O(changes) + spawns
    info = {"base": base, "head": head, "checkpoint": newest, "sha": "", "files": [], "overlap": [], "error": ""}  # O(1)
    idx = Path(root) / ".superlite" / "trees" / f"base-{os.getpid()}.index"  # O(1)
    try:  # O(1)
        changes = _tree_changes(root, base, newest)  # O(changes)
        info["files"] = sorted(changes)  # O(c log c)
        clean_env = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE")}  # O(env)
        if subprocess.run(["git", "-C", str(root), "merge-base", "--is-ancestor", newest, head], capture_output=True, env=clean_env).returncode == 0:  # O(1) + spawn: HEAD already holds the checkpoints
            info["sha"] = head  # O(1)
            return info  # O(1)
        moved =set(split_z(git(root, "diff", "--name-only", "--no-renames", "-z", base, head)))  # O(f)
        info["overlap"] = sorted(moved & set(changes))  # O(f)
        stamp = git(root, "show", "-s", "--format=%ct", newest).strip()  # O(1)
        idx.parent.mkdir(parents=True, exist_ok=True)  # O(1)
        idx.unlink(missing_ok=True)  # O(1)
        env = {"GIT_INDEX_FILE": str(idx)}  # O(1)
        _git_env(root, ["read-tree", head], env)  # O(files)
        lines = "".join(f"{m} {sha}\t{p}\0" for p, (m, sha) in changes.items())  # O(changes)
        if lines:  # O(1)
            _git_env(root, ["update-index", "-z", "--index-info"], env, lines)  # O(changes)
        tree = _git_env(root, ["write-tree"], env).strip()  # O(files)
        ident = {"GIT_AUTHOR_NAME": "superlite", "GIT_AUTHOR_EMAIL": "superlite@localhost", "GIT_COMMITTER_NAME": "superlite",  # O(1)
                 "GIT_COMMITTER_EMAIL": "superlite@localhost", "GIT_AUTHOR_DATE": f"{stamp} +0000", "GIT_COMMITTER_DATE": f"{stamp} +0000"}  # O(1)
        msg = f"superlite tree base: checkpoint {newest[:7]} on HEAD {head[:7]}"  # O(1)
        info["sha"] = _git_env(root, ["commit-tree", tree, "-p", head, "--no-gpg-sign", "-m", msg], ident).strip()  # O(1)
    except (RuntimeError, OSError) as e:  # O(1)
        info.update(sha="", error=(str(e).splitlines() or ["git failed"])[0])  # O(1)
    finally:  # O(1)
        idx.unlink(missing_ok=True)  # O(1)
    return info  # O(1)


def moved_base(root):  # None, or the base rebuilt on a HEAD that moved off checkpoints.json's base; memoized | O(changes) + spawns
    root = Path(root).resolve()  # O(1)
    try:  # O(1)
        st = json.loads((root / STATE).read_text(encoding="utf-8"))  # O(file)
        base = st.get("base") or st.get("head") or ""  # O(1)
        newest = (st.get("entries") or [])[-1].get("sha") or ""  # O(1)
    except (OSError, ValueError, AttributeError, IndexError):  # O(1)
        return None  # O(1)
    if not base or not newest:  # O(1)
        return None  # O(1)
    try:  # O(1)
        head = git(root, "rev-parse", "--verify", "-q", "HEAD").strip()  # O(1) + spawn
    except RuntimeError:  # O(1)
        return None  # O(1)
    if not head or head == base:  # O(1)
        return None  # O(1)
    key = (str(root), base, newest, head)  # O(1)
    if key not in _MOVED:  # O(1)
        _MOVED[key] = _build_moved(root, base, newest, head)  # O(changes)
    return dict(_MOVED[key])  # O(1)


def base_commit(root):  # O(checkpoints) + spawns when HEAD moved off the base, or no checkpoint
    root = Path(root)  # O(1)
    mb = moved_base(root)  # O(1) memoized
    if mb and mb["sha"]:  # O(1)
        return mb["sha"]  # O(1)
    if mb:  # O(1) the rebuild failed: today's behaviour, said once
        key = (str(root.resolve()), mb["base"], mb["checkpoint"], mb["head"])  # O(1)
        if key not in _WARNED:  # O(1)
            _WARNED.add(key)  # O(1)
            print(f"trees: base not rebuilt on HEAD {mb['head'][:7]}: {mb['error']}; trees use the newest checkpoint {mb['checkpoint'][:7]}", file=sys.stderr)  # O(1)
        return mb["checkpoint"]  # O(1)
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


def _stage_git(tree, args, paths):  # one git call with NUL pathspecs on stdin; "" or one stderr line | O(paths) + spawn
    try:  # O(1)
        p = subprocess.Popen(["git", "-C", str(tree), "--literal-pathspecs", *args, "--pathspec-from-file=-", "--pathspec-file-nul"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", start_new_session=True)  # own process group | O(1)
    except OSError as e:  # O(1)
        return str(e).strip()[:200]  # O(1)
    try:  # O(1)
        _, stderr = p.communicate(input="\0".join(paths) + "\0", timeout=STAGE_TIMEOUT)  # O(paths)
    except subprocess.TimeoutExpired:  # O(1) a hanging clean filter
        try:  # O(1)
            os.killpg(p.pid, 9)  # the whole group: git and its filter | O(1)
        except (OSError, AttributeError):  # no killpg on Windows | O(1)
            p.kill()  # O(1)
        try:  # O(1)
            p.communicate(timeout=5)  # reap | O(1)
        except subprocess.TimeoutExpired:  # a filter child still holds the pipes | O(1)
            for f in (p.stdin, p.stdout, p.stderr):  # O(1)
                try:  # O(1)
                    if f:  # O(1)
                        f.close()  # O(1)
                except (OSError, ValueError):  # O(1)
                    pass  # O(1)
            try:  # O(1)
                p.wait(timeout=5)  # O(1)
            except subprocess.TimeoutExpired:  # O(1)
                pass  # O(1)
        msg = f"git {args[0]} timed out after {STAGE_TIMEOUT} s"  # O(1)
        try:  # O(1)
            lk = subprocess.run(["git", "-C", str(tree), "rev-parse", "--git-path", "index.lock"], capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.strip()  # O(1) + spawn
            lp = Path(lk) if lk else None  # O(1)
            if lp is not None and not lp.is_absolute():  # O(1)
                lp = Path(tree) / lp  # O(1)
            if lp is not None and lp.exists():  # O(1)
                lp.unlink()  # O(1)
                msg += f"; removed {lp}"  # O(1)
        except OSError:  # O(1)
            pass  # O(1)
        return msg  # O(1)
    if p.returncode:  # O(1)
        return " ".join((stderr.strip() or f"git exit {p.returncode}").split())[:200]  # O(len stderr)
    return ""  # O(1)


def stage(tree, copy, delete):  # stage the overlay in the tree's index; "" or one error line; never raises | O(paths) + two spawns
    for args, paths in ((["add", "-A", "-f"], copy), (["rm", "-q", "--cached", "--ignore-unmatch"], delete)):  # O(2)
        if paths:  # O(1)
            err = _stage_git(tree, args, paths)  # O(paths)
            if err:  # O(1)
                return err  # O(1)
    return ""  # O(1)


def prepare(root, task, owns):  # O(f * o) + git checkout of the tree
    root = Path(root).resolve()  # absolute: git -C and the tree path must agree | O(1)
    with lock(root, task):  # O(1)
        return _prepare(root, task, owns)  # O(f * o)


def prepare_at(root, key, rev):  # a detached tree at rev with no overlay; its path | O(files) + git checkout
    root = Path(root).resolve()  # O(1)
    with lock(root, key):  # O(1)
        tree = tree_path(root, key)  # O(1)
        tree.parent.mkdir(parents=True, exist_ok=True)  # O(1)
        if (tree / ".git").exists():  # O(1) reuse: keeps untracked build output
            git(tree, "checkout", "--force", "--detach", rev)  # O(changed files)
        else:  # O(1)
            git(root, "worktree", "prune")  # O(T)
            git(root, "worktree", "add", "--force", "--detach", str(tree), rev)  # O(files)
        return tree  # O(1)


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
    mb = moved_base(root)  # O(1) memoized
    if mb and mb["sha"]:  # O(1)
        note = f"trees: {task} tree on HEAD {mb['head'][:7]} plus the run's checkpoints (the run moved off its base {mb['base'][:7]})"  # O(1)
        if mb["overlap"]:  # O(1)
            shown = ", ".join(mb["overlap"][:8]) + (" ..." if len(mb["overlap"]) > 8 else "")  # O(1)
            note += f"; checkpointed files the move also changed keep the checkpoint's version: {shown} (re-checkpoint their tasks with sl commit_task)"  # O(1)
        print(note, file=sys.stderr)  # O(1)
    err = stage(tree, copy, delete)  # O(f) + spawns
    if err:  # O(1)
        print(f"trees: {task} tree index not updated: {err}; git-index checks in the tree see the base", file=sys.stderr)  # O(1)
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


def derived_data_path(tree):  # O(1)
    return Path(tree) / ".build" / "DerivedData"  # O(1)


def _pid_alive(pid):  # O(1)
    try:  # O(1)
        os.kill(pid, 0)  # O(1)
    except ProcessLookupError:  # O(1)
        return False  # O(1)
    except OSError:  # O(1) PermissionError: the process exists
        return True  # O(1)
    return True  # O(1)


@contextlib.contextmanager
def busy(root, key):  # marks the tree in use by this process | O(1)
    marker = Path(root) / TREES / f"{key}.busy.{os.getpid()}"  # O(1)
    marker.parent.mkdir(parents=True, exist_ok=True)  # O(1)
    marker.write_text("", encoding="utf-8")  # O(1)
    try:  # O(1)
        yield  # O(1)
    finally:  # O(1)
        marker.unlink(missing_ok=True)  # O(1)


def is_busy(root, key):  # a marker of a dead pid is removed | O(markers of key)
    found = False  # O(1)
    for m in (Path(root) / TREES).glob(f"{key}.busy.*"):  # O(markers) iterations
        tail = m.name.rsplit(".", 1)[-1]  # O(1)
        if tail.isdigit() and _pid_alive(int(tail)):  # O(1)
            found = True  # O(1)
        else:  # O(1)
            m.unlink(missing_ok=True)  # O(1)
    return found  # O(1)


def drop(root, key):  # remove one tree and its overlay list; True when a tree was removed | O(tree size)
    if not isinstance(key, str) or not KEY.fullmatch(key):  # O(len key)
        return False  # O(1)
    root = Path(root)  # O(1)
    tree = tree_path(root, key)  # O(1)
    overlay_file(root, key).unlink(missing_ok=True)  # O(1)
    if not tree.is_dir():  # O(1)
        return False  # O(1)
    try:  # O(1)
        git(root, "worktree", "remove", "--force", str(tree))  # O(tree size)
    except RuntimeError:  # O(1)
        shutil.rmtree(tree, ignore_errors=True)  # O(tree size)
    try:  # O(1)
        git(root, "worktree", "prune")  # O(T)
    except RuntimeError:  # O(1)
        pass  # O(1)
    return not tree.exists()  # O(1)


def reap(root, committed, stopped, keep=frozenset()):  # drop unneeded, idle trees; never raises | O(T) + drops
    dropped = []  # O(1)
    try:  # O(1)
        keys = sorted(d.name for d in (Path(root) / TREES).iterdir() if d.is_dir())  # O(T log T)
    except OSError:  # O(1)
        return dropped  # O(1)
    for key in keys:  # O(T) iterations
        needed = key in committed or (key.startswith("worker-") and key[len("worker-"):] in stopped)  # O(1)
        if not needed or key in keep:  # O(1)
            continue  # O(1)
        try:  # O(1)
            if not is_busy(root, key) and drop(root, key):  # O(tree size)
                dropped.append(key)  # O(1)
        except Exception:  # noqa: BLE001  # O(1) reaping is best effort
            continue  # O(1)
    return dropped  # O(1)


def clean_idle(root):  # drop every tree nothing runs in; the dropped keys; never raises | O(T) + drops
    dropped = []  # O(1)
    try:  # O(1)
        keys = sorted(d.name for d in (Path(root) / TREES).iterdir() if d.is_dir())  # O(T log T)
    except OSError:  # O(1)
        return dropped  # O(1)
    for key in keys:  # O(T) iterations
        try:  # O(1)
            if not is_busy(root, key) and drop(root, key):  # O(tree size)
                dropped.append(key)  # O(1)
        except Exception:  # noqa: BLE001  # O(1) cleanup is best effort
            continue  # O(1)
    return dropped  # O(1)


def scratch_home(home=None):  # O(1)
    if home is not None:  # O(1)
        return Path(home)  # O(1)
    env = os.environ.get("SUPERLITE_SCRATCH_HOME")  # O(1)
    if env:  # O(1)
        return Path(env)  # O(1)
    return Path(os.environ.get("CLAUDE_CODE_TMPDIR") or "/tmp") / f"claude-{os.getuid()}"  # O(1)


def _slug(path):  # O(len path)
    return re.sub(r"[^A-Za-z0-9]", "-", str(path))  # O(len path)


def _is_build_folder(d):  # a real directory that holds Xcode build output | O(1)
    if d.is_symlink() or not d.is_dir():  # O(1)
        return False  # O(1)
    if (d / "ModuleCache.noindex").is_dir():  # O(1)
        return True  # O(1)
    return (d / "Build").is_dir() and ((d / "Logs").is_dir() or (d / "info.plist").is_file())  # O(1)


def _sweep_below(folder, depth):  # remove build folders at most depth levels below folder -> (folders, bytes) | O(entries + files)
    n = freed = 0  # O(1)
    try:  # O(1)
        entries = sorted(folder.iterdir())  # O(entries)
    except OSError:  # O(1)
        return 0, 0  # O(1)
    for e in entries:  # O(entries) iterations
        try:  # O(1)
            if e.is_symlink() or not e.is_dir():  # O(1)
                continue  # O(1)
            if _is_build_folder(e):  # O(1)
                size = _size(e)  # O(files)
                shutil.rmtree(e, ignore_errors=True)  # O(files)
                if not e.exists():  # O(1)
                    n += 1  # O(1)
                    freed += size  # O(1)
            elif depth > 1:  # O(1)
                a, b = _sweep_below(e, depth - 1)  # O(entries + files)
                n += a  # O(1)
                freed += b  # O(1)
        except OSError:  # O(1)
            continue  # O(1)
    return n, freed  # O(1)


def sweep_scratch_builds(worktree, home=None):  # Xcode build folders in the worktree's session scratchpads -> (folders, bytes) | O(entries + files)
    n = freed = 0  # O(1)
    try:  # O(1)
        base = scratch_home(home)  # O(1)
        paths = list(dict.fromkeys([Path(worktree).absolute(), Path(worktree).resolve()]))  # O(len path)
        for p in paths:  # O(1) iterations
            slug = base / _slug(p)  # O(len path)
            for sess in sorted(slug.glob("*/scratchpad")):  # O(sessions)
                if sess.is_symlink():  # O(1)
                    continue  # O(1)
                a, b = _sweep_below(sess, 3)  # O(entries + files)
                n += a  # O(1)
                freed += b  # O(1)
    except Exception:  # noqa: BLE001  # O(1) cleanup is best effort
        return n, freed  # O(1)
    return n, freed  # O(1)


def stopped_workers(sd):  # ids of workers whose state is stopped | O(workers)
    try:  # O(1)
        workers = json.loads((Path(sd) / "fleet.json").read_text(encoding="utf-8")).get("workers") or {}  # O(file)
        return {w for w, v in workers.items() if isinstance(v, dict) and v.get("state") == "stopped"}  # O(workers)
    except (OSError, ValueError, AttributeError):  # O(1)
        return set()  # O(1)


def derived_data_home(home=None):  # O(1)
    if home is not None:  # O(1)
        return Path(home)  # O(1)
    return Path(os.environ.get("SUPERLITE_DERIVED_DATA_HOME") or "~/Library/Developer/Xcode/DerivedData").expanduser()  # O(1)


def _size(path):  # bytes of every file below path | O(files)
    total = 0  # O(1)
    for dp, _dn, fns in os.walk(path):  # O(dirs) iterations
        for fn in fns:  # O(files) iterations
            try:  # O(1)
                total += os.lstat(os.path.join(dp, fn)).st_size  # O(1)
            except OSError:  # O(1)
                pass  # O(1)
    return total  # O(1)


def _orphan_tree(workspace):  # the tree folder a path inside .superlite/trees/<key> belongs to, else None | O(len path)
    parts = Path(workspace).parts  # O(len path)
    for i in range(len(parts) - 2):  # O(len path) iterations
        if parts[i] == ".superlite" and parts[i + 1] == "trees":  # O(1)
            return Path(*parts[:i + 3])  # O(1)
    return None  # O(1)


def sweep_derived_data(home=None):  # remove DerivedData folders of trees that are gone -> (folders, bytes) | O(folders + files)
    base = derived_data_home(home)  # O(1)
    n = freed = 0  # O(1)
    try:  # O(1)
        entries = sorted(base.iterdir())  # O(folders)
    except OSError:  # O(1)
        return 0, 0  # O(1)
    for d in entries:  # O(folders) iterations
        if d.name == "ModuleCache.noindex" or not d.is_dir():  # O(1)
            continue  # O(1)
        try:  # O(1)
            with open(d / "info.plist", "rb") as fh:  # O(1)
                ws = plistlib.load(fh).get("WorkspacePath")  # O(file)
        except (OSError, ValueError, plistlib.InvalidFileException):  # O(1)
            continue  # O(1)
        tree = _orphan_tree(ws) if isinstance(ws, str) else None  # O(len path)
        if tree is None or tree.exists():  # O(1)
            continue  # O(1)
        size = _size(d)  # O(files)
        shutil.rmtree(d, ignore_errors=True)  # O(files)
        if not d.exists():  # O(1)
            n += 1  # O(1)
            freed += size  # O(1)
    return n, freed  # O(1)


def _newest_mtime(path):  # newest mtime of path and everything below it | O(files)
    newest = os.lstat(path).st_mtime  # O(1)
    for dp, dn, fns in os.walk(path):  # O(dirs) iterations
        for name in dn + fns:  # O(entries) iterations
            try:  # O(1)
                newest = max(newest, os.lstat(os.path.join(dp, name)).st_mtime)  # O(1)
            except OSError:  # O(1)
                pass  # O(1)
    return newest  # O(1)


def prune_module_cache(hours, home=None):  # remove ModuleCache.noindex entries untouched for hours -> (entries, bytes) | O(files)
    mc = derived_data_home(home) / "ModuleCache.noindex"  # O(1)
    n = freed = 0  # O(1)
    try:  # O(1)
        entries = sorted(mc.iterdir())  # O(entries)
    except OSError:  # O(1)
        return 0, 0  # O(1)
    cutoff = time.time() - hours * 3600  # O(1)
    for e in entries:  # O(entries) iterations
        try:  # O(1)
            if _newest_mtime(e) >= cutoff:  # O(files)
                continue  # O(1)
            size = _size(e) if e.is_dir() and not e.is_symlink() else e.lstat().st_size  # O(files)
            if e.is_dir() and not e.is_symlink():  # O(1)
                shutil.rmtree(e, ignore_errors=True)  # O(files)
            else:  # O(1)
                e.unlink(missing_ok=True)  # O(1)
        except OSError:  # O(1)
            continue  # O(1)
        if not e.exists():  # O(1)
            n += 1  # O(1)
            freed += size  # O(1)
    return n, freed  # O(1)


def free_gb(path):  # O(1)
    return shutil.disk_usage(path).free / GIB  # O(1)


def _env_gb(name, default):  # O(1)
    try:  # O(1)
        return float(os.environ.get(name, default))  # O(1)
    except ValueError:  # O(1)
        return float(default)  # O(1)


def disk_levels():  # -> (floor GB, warn GB) | O(1)
    return _env_gb("SUPERLITE_DISK_FLOOR_GB", 20), _env_gb("SUPERLITE_DISK_WARN_GB", 50)  # O(1)


def disk_gate(path):  # -> ("ok" | "warn" | "refuse", one line) | O(1)
    floor, warn = disk_levels()  # O(1)
    shown = Path(path).resolve()  # O(len path)
    try:  # O(1)
        free = free_gb(shown)  # O(1)
    except OSError:  # O(1)
        return "ok", ""  # O(1)
    if floor > 0 and free < floor:  # O(1)
        return "refuse", f"disk: {free:.1f} GB free on {shown}, below the {floor:g} GB floor; run sl trees clean (trees, orphaned Xcode DerivedData) and free space, then rerun"  # O(1)
    if warn > 0 and free < warn:  # O(1)
        return "warn", f"disk: WARNING: {free:.1f} GB free on {shown}, below {warn:g} GB; run sl trees clean soon"  # O(1)
    return "ok", ""  # O(1)


SIMULATORS = Path(".superlite") / "simulators.txt"  # O(1)
UDID = re.compile(r"[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}")  # O(1)
SIMCTL_TIMEOUT = 60  # O(1) seconds per simctl call


def listed_simulators(worktree):  # -> entries in order, deduplicated | O(lines)
    try:  # O(1)
        text = (Path(worktree) / SIMULATORS).read_text(encoding="utf-8")  # O(size)
    except (OSError, UnicodeDecodeError):  # O(1)
        return []  # O(1)
    out = []  # O(1)
    for raw in text.splitlines():  # O(lines)
        line = raw.strip()  # O(len line)
        if not line or line.startswith(("#", "-")) or any(ord(c) < 32 or ord(c) == 127 for c in line):  # O(len line)
            continue  # O(1)
        first = line.split()[0]  # O(len line)
        entry = first.upper() if UDID.fullmatch(first) else line  # O(1)
        if entry not in out:  # O(entries)
            out.append(entry)  # O(1)
    return out  # O(1)


def simctl_argv():  # O(len env)
    raw = os.environ.get("SUPERLITE_SIMCTL", "")  # O(1)
    return shlex.split(raw) if raw.strip() else ["xcrun", "simctl"]  # O(len raw)


def _last_line(text):  # O(len text)
    lines = [x.strip() for x in (text or "").splitlines() if x.strip()]  # O(len text)
    return (lines[-1] if lines else "")[:120]  # O(1)


def simulator_devices():  # -> {UDID: name}; raises RuntimeError(one-line reason) | O(devices)
    try:  # O(1)
        r = subprocess.run(simctl_argv() + ["list", "devices", "-j"], capture_output=True, text=True, timeout=SIMCTL_TIMEOUT)  # O(simctl)
    except OSError as e:  # O(1)
        raise RuntimeError(f"simctl not runnable: {e}")  # O(1)
    except subprocess.TimeoutExpired:  # O(1)
        raise RuntimeError(f"simctl list timed out after {SIMCTL_TIMEOUT} s")  # O(1)
    if r.returncode != 0:  # O(1)
        raise RuntimeError(f"simctl list exit {r.returncode}: {_last_line(r.stdout + chr(10) + r.stderr)}")  # O(len output)
    try:  # O(1)
        groups = json.loads(r.stdout)["devices"].values()  # O(len output)
        return {str(d["udid"]).upper(): str(d.get("name", "")) for g in groups for d in g}  # O(devices)
    except (ValueError, KeyError, TypeError, AttributeError):  # O(1)
        raise RuntimeError("simctl list gave no device JSON")  # O(1)


def _matches(entry, devices):  # -> UDIDs of the devices an entry names | O(devices)
    if UDID.fullmatch(entry) and entry.upper() in devices:  # O(1)
        return [entry.upper()]  # O(1)
    if UDID.fullmatch(entry):  # O(1)
        return []  # O(1)
    return [u for u, n in devices.items() if n == entry]  # O(devices)


def remove_simulators(worktree):  # -> (removed, already gone, [{"sim", "why"}]); never raises | O(entries x devices)
    entries = listed_simulators(worktree)  # O(file)
    if not entries:  # O(1)
        return [], [], []  # O(1)
    try:  # O(1)
        devices = simulator_devices()  # O(simctl)
    except RuntimeError as e:  # O(1)
        return [], [], [{"sim": x, "why": str(e)} for x in entries]  # O(entries)
    removed, gone, owed = [], [], []  # O(1)
    for entry in entries:  # O(entries)
        found = _matches(entry, devices)  # O(devices)
        if not found:  # O(1)
            gone.append(entry)  # O(1)
            continue  # O(1)
        if len(found) > 1:  # O(1)
            owed.append({"sim": entry, "why": f"{len(found)} simulators share this name; list its UDID"})  # O(1)
            continue  # O(1)
        udid = found[0]  # O(1)
        try:  # O(1)
            subprocess.run(simctl_argv() + ["shutdown", udid], capture_output=True, text=True, timeout=SIMCTL_TIMEOUT)  # O(simctl)
        except (OSError, subprocess.SubprocessError):  # O(1)
            pass  # O(1) shutdown result is ignored
        try:  # O(1)
            r = subprocess.run(simctl_argv() + ["delete", udid], capture_output=True, text=True, timeout=SIMCTL_TIMEOUT)  # O(simctl)
        except OSError as e:  # O(1)
            owed.append({"sim": entry, "why": f"simctl not runnable: {e}"})  # O(1)
            continue  # O(1)
        except subprocess.SubprocessError:  # O(1)
            owed.append({"sim": entry, "why": f"delete timed out after {SIMCTL_TIMEOUT} s"})  # O(1)
            continue  # O(1)
        if r.returncode == 0:  # O(1)
            removed.append(entry)  # O(1)
        else:  # O(1)
            owed.append({"sim": entry, "why": f"delete failed: {_last_line(r.stderr + chr(10) + r.stdout)}"})  # O(len output)
    return removed, gone, owed  # O(1)


def present_simulators(sims):  # -> the entries a device still matches, or None when the list fails | O(entries x devices)
    try:  # O(1)
        devices = simulator_devices()  # O(simctl)
    except RuntimeError:  # O(1)
        return None  # O(1)
    return [s for s in sims if _matches(s, devices)]  # O(entries x devices)


def _tree_count(root):  # task trees (folders holding .git) under .superlite/trees | O(T)
    base = Path(root) / TREES  # O(1)
    return sum(1 for d in base.iterdir() if (d / ".git").exists()) if base.is_dir() else 0  # O(T)


def _some(paths):  # the first 8 paths, comma-separated, " ..." when more | O(1)
    return ", ".join(paths[:8]) + (" ..." if len(paths) > 8 else "")  # O(1)


def _report(root):  # print what the moved base means for the trees; the exit code | O(changes) + spawns
    try:  # O(1)
        head = git(root, "rev-parse", "--verify", "-q", "HEAD").strip()  # O(1) + spawn
    except RuntimeError:  # O(1)
        print("trees refresh: no HEAD to move", file=sys.stderr)  # O(1)
        return 2  # O(1)
    try:  # O(1)
        entries = json.loads((root / STATE).read_text(encoding="utf-8")).get("entries") or []  # O(file)
    except (OSError, ValueError, AttributeError):  # O(1)
        entries = []  # O(1)
    if not entries:  # O(1)
        print(f"trees refresh: no checkpoints; trees follow HEAD {head[:7]}")  # O(1)
        return 0  # O(1)
    mb = moved_base(root)  # O(changes)
    if mb is None:  # O(1)
        print(f"trees refresh: HEAD {head[:7]} is the run's base; trees are current")  # O(1)
        return 0  # O(1)
    if not mb["sha"]:  # O(1)
        print(f"trees refresh: base not rebuilt on HEAD {head[:7]}: {mb['error']}", file=sys.stderr)  # O(1)
        return 3  # O(1)
    print(f"trees refresh: base {mb['base'][:7]} -> HEAD {head[:7]}; {_tree_count(root)} task trees rebuild on {mb['sha'][:7]} "  # O(1)
          f"(HEAD plus {len(mb['files'])} checkpointed files) at their next run")  # O(1)
    if mb["overlap"]:  # O(1)
        print(f"trees refresh: checkpointed files the move also changed: {_some(mb['overlap'])}; "  # O(1)
              "the trees keep the checkpoint's version: re-checkpoint their tasks with sl commit_task")  # O(1)
        return 1  # O(1)
    return 0  # O(1)


def _run_files(root, mb_rev, head, onto_has_head):  # paths the run touches: working changes, untracked, checkpoints, own commits | O(f) + spawns
    files = split_z(git(root, "diff", "--name-only", "--no-renames", "-z", "HEAD"))  # O(f)
    files += split_z(git(root, "ls-files", "-o", "--exclude-standard", "-z"))  # O(f)
    try:  # O(1)
        st = json.loads((root / STATE).read_text(encoding="utf-8"))  # O(file)
        base, newest = st.get("base") or st.get("head") or "", (st.get("entries") or [])[-1].get("sha") or ""  # O(1)
        if base and newest:  # O(1)
            files += list(_tree_changes(root, base, newest))  # O(changes)
    except (OSError, ValueError, AttributeError, IndexError, RuntimeError):  # O(1)
        pass  # O(1)
    if not onto_has_head:  # O(1) HEAD is not an ancestor of REV: the run has commits of its own
        files += split_z(git(root, "diff", "--name-only", "-z", "--no-renames", mb_rev, head))  # O(f)
    return {p for p in files if not p.startswith(".superlite/")}  # O(f)


def _try(root, args):  # (returncode, last stderr line) of one git call | O(output) + spawn
    r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, encoding="utf-8", errors="replace")  # O(output)
    return r.returncode, (r.stderr.strip().splitlines() or [""])[-1]  # O(1)


def refresh(root, onto):  # move the run onto REV when safe, then report the trees; the exit code | O(f) + spawns
    root = Path(root).resolve()  # O(1)
    try:  # O(1)
        head = git(root, "rev-parse", "--verify", "-q", "HEAD").strip()  # O(1) + spawn
    except RuntimeError:  # O(1)
        print("trees refresh: no HEAD to move", file=sys.stderr)  # O(1)
        return 2  # O(1)
    if onto is None:  # O(1)
        return _report(root)  # O(changes)
    try:  # O(1)
        rev = git(root, "rev-parse", "--verify", "-q", f"{onto}^{{commit}}").strip()  # O(1) + spawn
    except RuntimeError:  # O(1)
        print(f"trees refresh: unknown revision {onto}", file=sys.stderr)  # O(1)
        return 2  # O(1)
    if _try(root, ["merge-base", "--is-ancestor", rev, head])[0] == 0:  # O(1)
        print(f"trees refresh: HEAD already contains {onto}")  # O(1)
        return _report(root)  # O(changes)
    try:  # O(1)
        mb = git(root, "merge-base", head, rev).strip()  # O(history)
        incoming = set(split_z(git(root, "diff", "--name-only", "-z", "--no-renames", mb, rev)))  # O(f)
        ff = _try(root, ["merge-base", "--is-ancestor", head, rev])[0] == 0  # O(1)
        common = sorted(incoming & _run_files(root, mb, head, ff))  # O(f)
    except RuntimeError as e:  # O(1)
        print(f"trees refresh: cannot compare with {onto}: {e}; nothing moved", file=sys.stderr)  # O(1)
        return 3  # O(1)
    if common:  # O(1)
        print(f"trees refresh: refused, {onto} changes files of the run: {_some(common)}; move the run by hand", file=sys.stderr)  # O(1)
        return 2  # O(1)
    branch = _try(root, ["symbolic-ref", "--short", "-q", "HEAD"])  # O(1)
    name = git(root, "symbolic-ref", "--short", "-q", "HEAD").strip() if branch[0] == 0 else "HEAD"  # O(1)
    if ff:  # O(1)
        rc, err = _try(root, ["merge", "--ff-only", rev])  # O(changed files)
        kind = "fast-forward"  # O(1)
    else:  # O(1)
        n = git(root, "rev-list", "--count", f"{rev}..{head}").strip()  # O(history)
        rc, err = _try(root, ["rebase", "--autostash", rev])  # O(commits)
        kind = "rebase"  # O(1)
        if rc:  # O(1)
            _try(root, ["rebase", "--abort"])  # O(1) result ignored
    if rc:  # O(1)
        print(f"trees refresh: {kind} onto {onto} failed: {err}; nothing moved", file=sys.stderr)  # O(1)
        return 3  # O(1)
    new = git(root, "rev-parse", "HEAD").strip()  # O(1)
    if ff:  # O(1)
        print(f"trees refresh: fast-forwarded {name} {head[:7]} -> {new[:7]}")  # O(1)
    else:  # O(1)
        print(f"trees refresh: rebased {name} ({n} commits) onto {rev[:7]}")  # O(1)
    return _report(root)  # O(changes)


def main(argv=None):  # O(T) + spawns
    import autocommit  # O(1) lazy: run_tests imports this module
    import state  # O(1) lazy
    argv = list(sys.argv[1:] if argv is None else argv)  # O(len argv)
    rest, plan = autocommit.split_plan(argv)  # O(len argv)
    usage = "usage: trees.py clean | path Tn | refresh [--onto REV] [--plan P]"  # O(1)
    if plan == "":  # O(1) --plan without a value
        print(usage, file=sys.stderr)  # O(1)
        return 2  # O(1)
    root = (state.git_root(plan) or ".") if plan else "."  # O(d)
    if rest[:1] == ["clean"] and (len(rest) == 1 or rest[1] == "--module-cache-hours"):  # O(1)
        hours = None  # O(1)
        if len(rest) > 1:  # O(1)
            try:  # O(1)
                hours = float(rest[2]) if len(rest) == 3 else -1.0  # O(1)
            except ValueError:  # O(1)
                hours = -1.0  # O(1)
            if not hours >= 0:  # O(1) also NaN
                print("trees: --module-cache-hours needs a number of hours", file=sys.stderr)  # O(1)
                return 2  # O(1)
        print(f"removed {clean(root)}")  # O(T)
        n, freed = sweep_derived_data()  # O(folders + files)
        if n:  # O(1)
            print(f"derived data: removed {n} orphaned folder(s), {freed / GIB:.1f} GB")  # O(1)
        if hours is not None:  # O(1)
            n, freed = prune_module_cache(hours)  # O(files)
            print(f"module cache: removed {n} entries older than {hours:g} h, {freed / GIB:.1f} GB")  # O(1)
        return 0  # O(1)
    if len(rest) == 2 and rest[0] == "path":  # O(1)
        print(tree_path(root, rest[1]).resolve())  # O(1)
        return 0  # O(1)
    if rest[:1] == ["refresh"] and (len(rest) == 1 or (len(rest) == 3 and rest[1] == "--onto" and not rest[2].startswith("-"))):  # O(1)
        return refresh(root, rest[2] if len(rest) == 3 else None)  # O(f)
    print(usage, file=sys.stderr)  # O(1)
    return 2  # O(1)


if __name__ == "__main__":  # O(1)
    sys.exit(main())  # O(1)
