#!/usr/bin/env python3
"""Run archive: finished runs live in the main checkout's `.superlite/runs/<id>/`, so they outlive a worktree.

API:
  MANIFEST, KEEP_FULL, KEEP_ALWAYS   manifest file name, runs kept whole, files prune never removes
  archive_dir(sd)                    <main checkout>/.superlite/runs (sd/runs outside git)
  new_run(sd, label=None)            a fresh, never-existing run folder (falls back to sd/runs when the archive is unwritable)
  write_manifest(run, info)          writes run/run.json
  read_manifest(run)                 the manifest dict, {} when missing or invalid
  runs(archive)                      manifests (plus "id", "dir") newest name first
  run_dirs(sd)                       run folders that belong to the checkout of sd, oldest first (legacy sd/runs included)
  prune(archive, keep)               trims runs older than the newest `keep` to their ledger files; returns runs trimmed
Stdlib only.
"""
# Complexity notation:
#   R = runs in the archive, F = files in one run
import json  # O(1)
import re  # O(1)
import shutil  # O(1)
import sys  # O(1)
import time  # O(1)
from pathlib import Path  # O(1)

HERE = Path(__file__).resolve().parent  # O(1)
if str(HERE) not in sys.path:  # O(1)
    sys.path.insert(0, str(HERE))  # O(1)

import worktree  # noqa: E402  | O(1)

MANIFEST = "run.json"  # O(1)
KEEP_FULL = 30  # O(1)
KEEP_ALWAYS = ("run.json", "progress.md", "metrics.jsonl", "incidents.jsonl", "build-report.md",  # O(1)
               "build-report.json")  # O(1)


def archive_dir(sd: Path) -> Path:  # O(1)
    sd = Path(sd)  # O(1)
    start = sd  # O(1)
    while not start.exists() and start.parent != start:  # O(depth)
        start = start.parent  # O(1)
    try:  # O(1)
        rc, out, _ = worktree.git(start, "rev-parse", "--path-format=absolute", "--git-common-dir")  # O(1) + spawn
    except OSError:  # O(1)
        return sd / "runs"  # O(1)
    common = Path(out) if not rc and out else None  # O(1)
    if common is None or common.name != ".git":  # O(1) a bare repo has no main checkout
        return sd / "runs"  # O(1)
    return common.parent.resolve() / ".superlite" / "runs"  # O(1)


def _slug(label: str) -> str:  # O(1)
    return re.sub(r"[^A-Za-z0-9._-]+", "-", label).strip("-")[:40]  # O(len)


def _make(parent: Path, base: str) -> Path:  # O(1)
    parent.mkdir(parents=True, exist_ok=True)  # O(1)
    n = 1  # O(1)
    while True:  # O(clashes)
        p = parent / (base if n == 1 else f"{base}-{n}")  # O(1)
        try:  # O(1)
            p.mkdir()  # O(1)
            return p  # O(1)
        except FileExistsError:  # O(1)
            n += 1  # O(1)


def new_run(sd: Path, label: str | None = None) -> Path:  # O(1)
    base = time.strftime("%Y%m%d-%H%M%S")  # O(1)
    slug = _slug(label) if label else ""  # O(len)
    if slug:  # O(1)
        base += "-" + slug  # O(1)
    try:  # O(1)
        return _make(archive_dir(sd), base)  # O(clashes)
    except OSError:  # O(1)
        return _make(Path(sd) / "runs", base)  # O(clashes)


def write_manifest(run: Path, info: dict) -> Path:  # O(1)
    p = Path(run) / MANIFEST  # O(1)
    p.write_text(json.dumps(info, indent=2, default=str) + "\n")  # O(size)
    return p  # O(1)


def read_manifest(run: Path) -> dict:  # O(1)
    try:  # O(1)
        d = json.loads((Path(run) / MANIFEST).read_text())  # O(size)
    except (OSError, ValueError):  # O(1)
        return {}  # O(1)
    return d if isinstance(d, dict) else {}  # O(1)


def runs(archive: Path) -> list[dict]:  # O(1)
    try:  # O(1)
        dirs = [p for p in Path(archive).iterdir() if p.is_dir()]  # O(R)
    except OSError:  # O(1)
        return []  # O(1)
    out = []  # O(1)
    for p in sorted(dirs, key=lambda q: q.name, reverse=True):  # O(R log R)
        out.append({**read_manifest(p), "id": p.name, "dir": p})  # O(F)
    return out  # O(R)


def _same(a, b) -> bool:  # O(1)
    try:  # O(1)
        return Path(a).resolve() == Path(b).resolve()  # O(1)
    except (OSError, TypeError, ValueError):  # O(1)
        return False  # O(1)


def run_dirs(sd: Path) -> list[Path]:  # O(R log R)
    sd = Path(sd)  # O(1)
    if not sd.is_dir():  # O(1)
        return []  # O(1)
    found = {}  # O(1)
    for r in runs(sd / "runs"):  # O(R)
        if not r.get("worktree") or _same(r["worktree"], sd.parent):  # O(1)
            found[r["dir"].resolve()] = r["dir"]  # O(1)
    for r in runs(archive_dir(sd)):  # O(R)
        if r.get("worktree") and _same(r["worktree"], sd.parent):  # O(1)
            found.setdefault(r["dir"].resolve(), r["dir"].resolve())  # O(1)
    return sorted(found.values(), key=lambda q: q.name)  # O(R log R)


def _trim(run: Path) -> bool:  # O(1)
    cut = False  # O(1)
    try:  # O(1)
        entries = list(run.iterdir())  # O(F)
    except OSError:  # O(1)
        return False  # O(1)
    for p in entries:  # O(F)
        if p.name in KEEP_ALWAYS or (p.name.startswith("test-summary") and p.suffix == ".json"):  # O(1)
            continue  # O(1)
        try:  # O(1)
            if p.is_symlink() or not p.is_dir():  # O(1)
                p.unlink()  # O(1)
            else:  # O(1)
                shutil.rmtree(p)  # O(size)
            cut = True  # O(1)
        except OSError:  # O(1)
            pass  # O(1)
    return cut  # O(1)


def prune(archive: Path, keep: int = KEEP_FULL) -> int:  # O(1)
    n = 0  # O(1)
    for r in runs(archive)[max(keep, 0):]:  # O(R)
        if not r["dir"].is_symlink() and _trim(r["dir"]):  # O(F)
            n += 1  # O(1)
    return n  # O(1)


def plans_dir(root: Path) -> Path:  # O(1)
    """`<root>/docs/superpowers/plans` when that folder exists, else `<root>/docs/plans`; created when missing."""
    root = Path(root)  # O(1)
    sp = root / "docs" / "superpowers" / "plans"  # O(1)
    d = sp if sp.is_dir() else root / "docs" / "plans"  # O(1)
    try:  # O(1)
        d.mkdir(parents=True, exist_ok=True)  # O(1)
    except OSError:  # O(1)
        pass  # O(1)
    return d  # O(1)


def _same_bytes(a: Path, b: Path) -> bool:  # O(size)
    try:  # O(1)
        return a.read_bytes() == b.read_bytes()  # O(size)
    except OSError:  # O(1)
        return False  # O(1)


def keep_in_plans(plan: str, sd: str, today: str | None = None) -> list[str]:  # O(F)
    """Copy the plan, its build report and progress.md into the plans folder; return the paths written, relative to the root.
    Fails open: an OSError ends the copy and returns what was written so far."""
    written: list[str] = []  # O(1)
    try:  # O(1)
        sdp = Path(sd)  # O(1)
        if not plan or sdp.name != ".superlite" or not Path(plan).is_file():  # O(1)
            return []  # O(1)
        root = sdp.resolve().parent  # O(1)
        src = Path(plan).resolve()  # O(1)
        dest = plans_dir(root)  # O(1)
        if src.parent == dest.resolve():  # O(1) the plan already lives in the plans folder
            stem, pairs = src.stem, []  # O(1)
        else:  # O(1)
            stem = src.stem  # O(1)
            if not re.match(r"\d{4}-\d{2}-\d{2}-", stem):  # O(1)
                stem = (today or time.strftime("%Y-%m-%d")) + "-" + stem  # O(1)
            base, n = stem, 1  # O(1)
            while (dest / f"{stem}.md").exists() and not _same_bytes(src, dest / f"{stem}.md"):  # O(clashes)
                n += 1  # O(1)
                stem = f"{base}-{n}"  # O(1)
            pairs = [(src, f"{stem}.md"), (src.with_name(src.stem + ".build-report.md"), f"{stem}.build-report.md"),  # O(1)
                     (src.with_name(src.stem + ".build-report.json"), f"{stem}.build-report.json")]  # O(1)
        pairs.append((sdp.resolve() / "progress.md", f"{stem}.progress.md"))  # O(1)
        for s, name in pairs:  # O(1) iterations
            if not s.is_file():  # O(1)
                continue  # O(1)
            shutil.copyfile(s, dest / name)  # O(size)
            written.append((dest / name).resolve().relative_to(root).as_posix())  # O(1)
    except (OSError, ValueError):  # O(1)
        pass  # O(1)
    return written  # O(F)
