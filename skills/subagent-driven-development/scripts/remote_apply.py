#!/usr/bin/env python3
"""Git plumbing for remote write workers: a start commit for a worker's tree, a snapshot of its result, and the three-state apply of that result into the local tree.

`start_commit` records base + the listed files as on disk + extra blobs under a ref; `snapshot` records a tree's working state (never `.superlite/`)
as a commit on HEAD; `apply` copies the paths stop changed over start into the local tree when the local file still equals start (or already equals stop),
and writes nothing when any path conflicts. Every git call uses a temporary index and `timeout=30`; a failure is `RuntimeError(one line)`.
CLI: `remote_apply.py snapshot --ref R` prints the sha (exit 0) or one stderr line (exit 1).
"""
# Complexity notation:
# f = files, p = changed paths, b = bytes of content
import argparse  # O(1)
import os  # O(1)
import subprocess  # O(1)
import sys  # O(1)
import tempfile  # O(1)
from pathlib import Path  # O(1)

sys.path.insert(0, str(Path(__file__).resolve().parent))  # O(1)
import next_tasks  # noqa: E402 | O(1)

TIMEOUT = 30  # O(1)
_IDENT = {"GIT_AUTHOR_NAME": "superlite", "GIT_AUTHOR_EMAIL": "superlite@localhost",
          "GIT_COMMITTER_NAME": "superlite", "GIT_COMMITTER_EMAIL": "superlite@localhost"}  # O(1)


def _git(cwd, args, env_extra=None, data=None, check=True):  # O(b) | bytes out; RuntimeError on failure
    env = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE")}  # O(env)
    env.update(env_extra or {})  # O(1)
    try:  # O(1)
        p = subprocess.run(["git", *args], cwd=cwd, env=env, input=data, capture_output=True, timeout=TIMEOUT)  # O(b)
    except (OSError, subprocess.SubprocessError) as e:  # O(1)
        raise RuntimeError(f"git {args[0]} failed: {type(e).__name__}") from None  # O(1)
    if p.returncode != 0 and check:  # O(1)
        err = p.stderr.decode("utf-8", "replace").strip().splitlines()  # O(b)
        raise RuntimeError(f"git {args[0]} failed: {err[-1] if err else p.returncode}")  # O(1)
    return p  # O(1)


def _out(cwd, args, **kw):  # O(b)
    return _git(cwd, args, **kw).stdout.decode("utf-8", "replace").strip()  # O(b)


def _commit(cwd, idx, parent, ref, msg):  # O(f) | write-tree, commit-tree, update-ref with the temp index
    env = {"GIT_INDEX_FILE": idx, **_IDENT}  # O(1)
    tree = _out(cwd, ["write-tree"], env_extra=env)  # O(f)
    sha = _out(cwd, ["commit-tree", tree, "-p", parent, "-m", msg], env_extra=env)  # O(1)
    _git(cwd, ["update-ref", ref, sha])  # O(1)
    return sha  # O(1)


def start_commit(root, base, files, blobs, ref):  # O(f + b)
    with tempfile.TemporaryDirectory() as td:  # O(1)
        idx = str(Path(td) / "index")  # O(1)
        env = {"GIT_INDEX_FILE": idx}  # O(1)
        _git(root, ["read-tree", base], env_extra=env)  # O(tree)
        for f in files:  # O(f) iterations
            p = Path(root) / f  # O(1)
            if p.is_symlink():  # O(1)
                sha = _out(root, ["hash-object", "-w", "--stdin"], data=os.fsencode(os.readlink(p)))  # O(b)
                _git(root, ["update-index", "--add", "--cacheinfo", f"120000,{sha},{f}"], env_extra=env)  # O(1)
            elif p.is_file():  # O(1)
                sha = _out(root, ["hash-object", "-w", "--", f])  # O(b)
                mode = "100755" if os.access(p, os.X_OK) else "100644"  # O(1)
                _git(root, ["update-index", "--add", "--cacheinfo", f"{mode},{sha},{f}"], env_extra=env)  # O(1)
            else:  # O(1)
                _git(root, ["update-index", "--force-remove", "--", f], env_extra=env)  # O(1)
        for path, data in blobs.items():  # O(blobs) iterations
            sha = _out(root, ["hash-object", "-w", "--stdin"], data=data)  # O(b)
            _git(root, ["update-index", "--add", "--cacheinfo", f"100644,{sha},{path}"], env_extra=env)  # O(1)
        return _commit(root, idx, base, ref, "superlite remote start")  # O(f)


def snapshot(tree, ref):  # O(f + b)
    with tempfile.TemporaryDirectory() as td:  # O(1)
        idx = str(Path(td) / "index")  # O(1)
        env = {"GIT_INDEX_FILE": idx}  # O(1)
        head = _out(tree, ["rev-parse", "HEAD"])  # O(1)
        _git(tree, ["read-tree", head], env_extra=env)  # O(tree)
        _git(tree, ["add", "-A", "--", ".", ":(exclude).superlite"], env_extra=env)  # O(f + b)
        return _commit(tree, idx, head, ref, "superlite remote stop")  # O(f)


def _blob(root, rev, path):  # O(b) | content of path at rev, None if absent
    p = _git(root, ["cat-file", "blob", f"{rev}:{path}"], check=False)  # O(b)
    return p.stdout if p.returncode == 0 else None  # O(1)


def _mode(root, rev, path):  # O(1) | mode of path at rev, None if absent
    out = _out(root, ["ls-tree", rev, "--", path])  # O(1)
    return out.split()[0] if out else None  # O(1)


def apply(root, start, stop, allowed):  # O(p * b)
    raw = _git(root, ["diff-tree", "-r", "--no-renames", "--raw", "-z", start, stop]).stdout.decode("utf-8", "surrogateescape")  # O(p)
    parts = raw.split("\0")  # O(p)
    changes = []  # O(1)
    for i in range(0, len(parts) - 1, 2):  # O(p) iterations
        meta = parts[i].lstrip(":").split()  # O(1)
        changes.append((parts[i + 1], meta[1], meta[4][0]))  # path, new mode, status | O(1)
    applied, skipped, conflicts, writes = [], [], [], []  # O(1)
    for path, mode, status in changes:  # O(p) iterations
        if path.startswith(".superlite/") or (allowed is not None and not next_tasks.owns_match(path, allowed)):  # O(f)
            skipped.append(path)  # O(1)
            continue  # O(1)
        lp = Path(root) / path  # O(1)
        if lp.is_symlink():  # O(1)
            local = os.fsencode(os.readlink(lp))  # O(b)
        else:  # O(1)
            local = lp.read_bytes() if lp.is_file() else None  # O(b)
        new = None if status == "D" else _blob(root, stop, path)  # O(b)
        old = _blob(root, start, path)  # O(b)
        local_link = lp.is_symlink()  # O(1)
        start_mode = _mode(root, start, path)  # O(1)
        exec_ok, exec_start = True, True  # O(1)
        if new is not None and mode != "120000" and lp.is_file() and not local_link:  # O(1)
            have = os.access(lp, os.X_OK)  # O(1)
            exec_ok = have == (mode == "100755")  # O(1)
            exec_start = start_mode is None or have == (start_mode == "100755")  # O(1)
        if local == new and (new is None or local_link == (mode == "120000")) and exec_ok:  # O(b)
            applied.append(path)  # O(1)
        elif local == new and (new is None or local_link == (mode == "120000")) and exec_start:  # O(b)
            writes.append((lp, new, mode))  # O(1)
            applied.append(path)  # O(1)
        elif local == old and (old is None or local_link == (start_mode == "120000")) and exec_start:  # O(b)
            writes.append((lp, new, mode))  # O(1)
            applied.append(path)  # O(1)
        else:  # O(1)
            conflicts.append(path)  # O(1)
    if conflicts:  # O(1)
        return {"applied": [], "skipped": skipped, "conflicts": conflicts}  # O(1)
    for lp, new, mode in writes:  # O(p) iterations
        if new is None:  # O(1)
            lp.unlink()  # O(1)
        else:  # O(1)
            lp.parent.mkdir(parents=True, exist_ok=True)  # O(1)
            if lp.is_symlink():  # O(1)
                lp.unlink()  # O(1)
            if mode == "120000":  # O(1)
                os.symlink(os.fsdecode(new), lp)  # O(1)
                continue  # O(1)
            lp.write_bytes(new)  # O(b)
            lp.chmod(0o755 if mode == "100755" else 0o644)  # O(1)
    return {"applied": applied, "skipped": skipped, "conflicts": conflicts}  # O(1)


def main(argv=None):  # O(f + b)
    ap = argparse.ArgumentParser(prog="remote_apply.py")  # O(1)
    sub = ap.add_subparsers(dest="cmd", required=True)  # O(1)
    sp = sub.add_parser("snapshot")  # O(1)
    sp.add_argument("--ref", required=True)  # O(1)
    a = ap.parse_args(argv)  # O(1)
    try:  # O(1)
        print(snapshot(os.getcwd(), a.ref))  # O(f + b)
    except RuntimeError as e:  # O(1)
        print(str(e).splitlines()[0], file=sys.stderr)  # O(1)
        return 1  # O(1)
    return 0  # O(1)


if __name__ == "__main__":  # O(1)
    sys.exit(main())  # O(1)
