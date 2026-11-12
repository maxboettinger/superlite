#!/usr/bin/env python3
"""Isolated test tree per task, so parallel agents never compile each other's half-edited files.

    trees.py clean [--plan P] [--module-cache-hours H]
                                remove every tree under .superlite/trees, print `removed N`, then remove the
                                Xcode DerivedData folders of trees that no longer exist; with the option, also
                                the ModuleCache.noindex entries untouched for H hours
    trees.py path Tn [--plan P] print the tree path of task Tn (without creating it)

`--plan P` (anywhere in the arguments) works in the git checkout holding P, else in the current folder.

A tree is a detached git worktree at `.superlite/trees/<task>` on the base commit (the newest
checkpoint, else HEAD). `prepare` resets it to the base and overlays only the task's own files
(modified, new or deleted in the main tree). Untracked build output in the tree is never removed by `prepare`.
Cleanup (GitHub #574): `busy` marks a tree in use (`<key>.busy.<pid>`), `reap` drops the trees of committed tasks and
stopped workers that are not busy, `clean_idle` drops every tree nothing runs in, `sweep_scratch_builds` removes Xcode
build folders in a removed worktree's Claude Code session scratchpads (#614), `sweep_derived_data` removes orphaned DerivedData of removed trees, `disk_gate`
refuses on a nearly full disk. Thresholds come from SUPERLITE_DISK_FLOOR_GB (20), SUPERLITE_DISK_WARN_GB (50) and
SUPERLITE_DERIVED_DATA_HOME, read at call time. Nothing is removed outside .superlite/trees and the DerivedData home.
Stdlib only.
"""
# Complexity notation: f = changed files in the main tree, o = Owns globs, T = trees
import contextlib  # O(1)
import json  # O(1)
import os  # O(1)
import plistlib  # O(1)
import re  # O(1)
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


def disk_gate(path):  # -> ("ok" | "warn" | "refuse", one line) | O(1)
    floor = _env_gb("SUPERLITE_DISK_FLOOR_GB", 20)  # O(1)
    warn = _env_gb("SUPERLITE_DISK_WARN_GB", 50)  # O(1)
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


def main(argv=None):  # O(T) + spawns
    import autocommit  # O(1) lazy: run_tests imports this module
    import state  # O(1) lazy
    argv = list(sys.argv[1:] if argv is None else argv)  # O(len argv)
    rest, plan = autocommit.split_plan(argv)  # O(len argv)
    usage = "usage: trees.py clean | path Tn [--plan P]"  # O(1)
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
    print(usage, file=sys.stderr)  # O(1)
    return 2  # O(1)


if __name__ == "__main__":  # O(1)
    sys.exit(main())  # O(1)
