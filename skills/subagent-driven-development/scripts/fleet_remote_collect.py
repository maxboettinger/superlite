#!/usr/bin/env python3
"""Bring a remote write worker's result home: fetch its snapshot and apply it to the local tree under the three-state rule.

`collect(sd, wid, report)` reads the newest mirrored stop record of the worker (`<sd>/remote/<wid>/metrics.jsonl`), fetches its `snapshot`
(`fleet_remote.fetch`) and applies start..snapshot (`remote_apply.apply`). The report gains `collected` {applied, skipped, sha}; skipped paths,
conflicts, a missing snapshot and an unreachable host become concerns (the last three turn the status BLOCKED). A snapshot is applied once.
"""
# Complexity notation:
# w = workers, m = lines of the mirrored metrics.jsonl, f = changed files
import json  # O(1)
import subprocess  # O(1)
import sys  # O(1)
from pathlib import Path  # O(1)

sys.path.insert(0, str(Path(__file__).resolve().parent))  # O(1)
import fleet_remote as fr  # noqa: E402 | O(1)
import fleet_state as fs  # noqa: E402 | O(1)
import remote_apply  # noqa: E402 | O(1)


def _snapshot(sd, wid):  # the snapshot of the newest stop record, None when it has none | O(m)
    try:  # O(1)
        lines = (Path(sd) / "remote" / wid / "metrics.jsonl").read_text(encoding="utf-8", errors="replace").splitlines()  # O(m)
    except OSError:  # O(1)
        return None  # O(1)
    for raw in reversed(lines):  # O(m)
        try:  # O(1)
            e = json.loads(raw)  # O(1)
        except ValueError:  # O(1)
            continue  # O(1)
        if isinstance(e, dict) and e.get("ev") == "stop":  # O(1)
            return e.get("snapshot") or None  # O(1)
    return None  # O(1)


def _blocked(report, concern):  # O(1)
    return {**report, "status": "BLOCKED", "concerns": [*(report.get("concerns") or []), concern]}  # O(1)


def _allowed(project, start, sha, owns):  # owns plus every changed path under tests/regression/ (owns_match skips nested ones) | O(f)
    if owns is None:  # O(1)
        return None  # O(1)
    try:  # O(1)
        out = subprocess.run(["git", "-C", project, "diff", "--name-only", "-z", start, sha], capture_output=True, text=True, timeout=30).stdout  # O(f)
    except (OSError, subprocess.SubprocessError):  # O(1)
        return list(owns)  # O(1)
    return [*owns, *(x for x in out.split("\0") if x.startswith("tests/regression/"))]  # O(f)


def collect(sd, wid, report):  # O(m + f)
    sd = Path(sd)  # O(1)
    rec = (fs.load(sd).get("workers") or {}).get(wid) or {}  # O(w)
    remote = rec.get("remote") or {}  # O(1)
    if not rec.get("machine") or not remote.get("write"):  # a local or read-only worker | O(1)
        return report  # O(1)
    snap = _snapshot(sd, wid)  # O(m)
    if not snap:  # O(1)
        return _blocked(report, f"remote worker {wid} left no snapshot")  # O(1)
    if snap == remote.get("collected"):  # O(1)
        return report  # O(1)
    ref = remote.get("snapshot_ref") or ""  # O(1)
    project = remote.get("project") or str(sd.resolve().parent)  # O(1)
    try:  # O(1)
        sha = fr.fetch(remote["label"], project, remote["name"], ref)  # O(objects)
    except fr.RemoteError as e:  # O(1)
        return _blocked(report, f"cannot fetch {wid}'s work: {e}")  # O(1)
    if sha != snap:  # O(1)
        return _blocked(report, f"fetched {sha} but the stop record names {snap}")  # O(1)
    try:  # O(1)
        res = remote_apply.apply(project, remote["start"], sha, _allowed(project, remote["start"], sha, remote.get("owns")))  # O(f)
    except (RuntimeError, OSError) as e:  # O(1)
        return _blocked(report, f"cannot apply {wid}'s work: {e}")  # O(1)
    if res["conflicts"]:  # O(1)
        kept = f"refs/maxapp/{remote['label']}/{remote['name']}/{ref[len('refs/'):]}"  # O(1)
        return _blocked(report, f"remote changes conflict with local edits: {', '.join(res['conflicts'])} (kept at {kept})")  # O(f)
    with fs.locked(sd):  # O(1)
        data = fs.load(sd)  # O(w)
        live = ((data.get("workers") or {}).get(wid) or {}).get("remote")  # O(1)
        if live is not None:  # O(1)
            live["collected"] = snap  # O(1)
            fs.save(sd, data)  # O(w)
    out = {**report, "collected": {"applied": res["applied"], "skipped": res["skipped"], "sha": snap}}  # O(f)
    if res["skipped"]:  # O(1)
        out["concerns"] = [*(report.get("concerns") or []), f"remote changes outside the task not applied: {', '.join(res['skipped'])}"]  # O(f)
    return out  # O(1)
