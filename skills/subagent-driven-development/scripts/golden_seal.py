"""Sealed lead start for golden runs: a clone with no remote, issues frozen as files, one lead started in it.

    golden_seal.seal(case, src, work)      clone src into work/<id> at the case base, write state and issue files
    golden_seal.start(clone, config)       `backlog_run.py start B1` in the clone
    golden_seal.wait(clone, timeout_s)     `backlog_run.py wait` in the clone, parsed to a state
    golden_seal.row(clone)                 the last batch row of the clone's batch-costs.jsonl
    golden_seal.worktree(clone)            the lead worktree path from the clone's state
    golden_seal.suite(clone)               the newest full-mode test summary of the lead worktree, {"passed": n, "failed": n}, None when none
    golden_seal.patch(wt, base)            the lead's change against the base as one patch text, "" on failure
    golden_seal.cleanup(clone)             stop the fleet in the clone and remove it
"""
# Complexity notation: i = issues, r = rows, L = output lines
import atexit  # O(1)
import json  # O(1)
import os  # O(1)
import re  # O(1)
import shutil  # O(1)
import subprocess  # O(1)
import tempfile  # O(1)
from pathlib import Path  # O(1)

HERE = Path(__file__).resolve().parent  # O(1)
BATCH = "B1"  # O(1)
START_TIMEOUT = 600  # O(1) seconds a start may take


DROP_ENV = ("SUPERLITE_STATE_DIR", "GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE", "GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN", "GH_HOST", "GH_CONFIG_DIR")  # O(1)
_GH_DIR: list = []  # O(1) the empty gh config folder of this process, made on first use, removed in cleanup and at exit
_EXIT: list = []  # O(1) set once the exit hook is registered


def _drop_gh() -> None:  # the empty gh config folder goes with cleanup and at exit, never left in the temp folder | O(1)
    for d in _GH_DIR:  # O(1)
        shutil.rmtree(d, ignore_errors=True)  # O(1)


def _env() -> dict:  # the caller's state folder, tokens and stored gh login never reach the clone's tools | O(env)
    if not _GH_DIR or not Path(_GH_DIR[0]).is_dir():  # O(1)
        _GH_DIR[:] = [tempfile.mkdtemp(prefix="golden-gh-")]  # O(1)
        if not _EXIT:  # O(1)
            _EXIT.append(1)  # O(1)
            atexit.register(_drop_gh)  # O(1)
    env = {k: v for k, v in os.environ.items() if k not in DROP_ENV and not k.startswith("SUPERLITE_FLEET_")}  # O(env)
    env["GH_CONFIG_DIR"] = _GH_DIR[0]  # an empty config folder: gh has no login | O(1)
    return env  # O(1)


def _run(cmd: list, cwd=None, timeout=None) -> tuple[int, str]:  # O(cmd)
    try:  # O(1)
        r = subprocess.run(cmd, cwd=str(cwd) if cwd else None, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout, env=_env())  # O(cmd)
    except subprocess.TimeoutExpired:  # O(1)
        return 124, "timeout"  # O(1)
    except OSError as e:  # O(1)
        return 127, str(e)  # O(1)
    return r.returncode, (r.stdout + r.stderr).strip()  # O(out)


def _git(clone: Path, *args: str) -> None:  # O(git)
    rc, out = _run(["git", *args], cwd=clone)  # O(git)
    if rc != 0:  # O(1)
        raise RuntimeError(f"git {' '.join(args)}: {out}")  # O(1)


def _scrub(clone: Path) -> None:  # only main at the base stays: no later branch, tag or object holds the hidden tests | O(refs)
    rc, out = _run(["git", "for-each-ref", "--format=%(refname)"], cwd=clone)  # O(refs)
    if rc != 0:  # O(1)
        raise RuntimeError(f"git for-each-ref: {out}")  # O(1)
    for ref in out.split():  # O(refs)
        if ref != "refs/heads/main":  # O(1)
            _git(clone, "update-ref", "-d", ref)  # O(1)
    _git(clone, "reflog", "expire", "--expire=now", "--all")  # O(1)
    _git(clone, "gc", "-q", "--prune=now")  # O(size)


def seal(case: dict, src: Path, work: Path) -> Path:  # O(clone + i)
    src, work = Path(src), Path(work)  # O(1)
    clone = work / case["id"]  # O(1)
    if clone.exists():  # O(1)
        shutil.rmtree(clone, ignore_errors=True)  # O(size)
    work.mkdir(parents=True, exist_ok=True)  # O(1)
    rc, out = _run(["git", "clone", "--no-hardlinks", "-q", str(src), str(clone)])  # O(clone)
    if rc != 0:  # O(1)
        raise RuntimeError(f"git clone: {out}")  # O(1)
    _git(clone, "checkout", "-q", "-B", "main", case["base"])  # O(tree)
    _git(clone, "remote", "remove", "origin")  # O(1)
    _scrub(clone)  # O(refs)
    sd = clone / ".superlite"  # O(1)
    issue_dir = sd / "golden" / "issues"  # O(1)
    issue_dir.mkdir(parents=True, exist_ok=True)  # O(1)
    for it in case["issues"]:  # O(i)
        (issue_dir / f"{it['number']}.md").write_text(f"# {it['title']}\n\n{it['body']}\n", encoding="utf-8")  # O(len)
    state = {"repo": "", "approved_ship": None, "sealed": {"issue_dir": str(issue_dir)},
             "titles": {str(it["number"]): it["title"] for it in case["issues"]},
             "batches": [{"id": BATCH, "topic": case["topic"], "issues": [it["number"] for it in case["issues"]],
                          "state": "planned", "files": []}]}  # O(i)
    (sd / "backlog.json").write_text(json.dumps(state, indent=2), encoding="utf-8")  # O(i)
    tc = Path(src) / ".superlite" / "test-cmd.json"  # O(1)
    if tc.is_file():  # O(1)
        shutil.copyfile(tc, sd / "test-cmd.json")  # O(1)
    return clone  # O(1)


def _script(clone: Path, *args: str) -> list:  # O(1)
    return ["python3", str(HERE / "backlog_run.py"), *args]  # O(1)


def start(clone: Path, config: str | None = None) -> dict:  # O(L)
    cmd = _script(clone, "start", BATCH) + (["--config", config] if config else [])  # O(1)
    rc, out = _run(cmd, cwd=clone, timeout=START_TIMEOUT)  # O(start)
    ok = rc == 0 and bool(re.search(rf"^{BATCH} running\b", out, re.M)) and "BLOCKED" not in out  # O(L)
    m = re.search(r"lead=(\S+)", out)  # O(L)
    return {"ok": ok, "lead": m.group(1) if ok and m else None, "out": out}  # O(1)


def wait(clone: Path, timeout_s: int = 5400) -> dict:  # O(L)
    rc, out = _run(_script(clone, "wait", "--timeout", str(timeout_s)), cwd=clone, timeout=timeout_s + 120)  # O(wait)
    if rc == 124 or re.search(r"^TIMEOUT\s*$", out, re.M):  # O(L)
        return {"state": "timeout", "reason": ""}  # O(1)
    m = re.search(rf"^{BATCH} parked: (.*)$", out, re.M)  # O(L)
    if m:  # O(1)
        return {"state": "parked", "reason": m.group(1).strip()}  # O(1)
    m = re.search(rf"^{BATCH} needs_decision(?: question=(.*))?$", out, re.M)  # O(L)
    if m:  # O(1)
        return {"state": "needs_decision", "reason": (m.group(1) or "").strip()}  # O(1)
    return {"state": "done" if rc == 0 else "error", "reason": out[-300:]}  # O(1)


def row(clone: Path) -> dict | None:  # O(r)
    try:  # O(1)
        lines = (Path(clone) / ".superlite" / "batch-costs.jsonl").read_text(encoding="utf-8", errors="replace").splitlines()  # O(r)
    except OSError:  # O(1)
        return None  # O(1)
    last = None  # O(1)
    for ln in lines:  # O(r)
        try:  # O(1)
            d = json.loads(ln)  # O(len)
        except ValueError:  # O(1)
            continue  # O(1)
        if isinstance(d, dict) and d.get("row") == "batch":  # O(1)
            last = d  # O(1)
    return last  # O(1)


def lead_cost(clone: Path) -> float:  # the lead's cost so far, from the same builder that writes the batch row | O(m + T)
    try:  # O(1)
        import batch_cost  # O(1)
        data = json.loads((Path(clone) / ".superlite" / "backlog.json").read_text(encoding="utf-8"))  # O(size)
        b = next(x for x in data.get("batches", []) if x.get("id") == BATCH)  # O(b)
        return float((batch_cost.build_row(Path(clone), b, "running").get("lead") or {}).get("cost_usd") or 0)  # O(m + T)
    except Exception:  # a cost lookup never ends a run | O(1)
        return 0.0  # O(1)


def worktree(clone: Path) -> Path | None:  # O(b)
    try:  # O(1)
        data = json.loads((Path(clone) / ".superlite" / "backlog.json").read_text(encoding="utf-8"))  # O(size)
    except (OSError, ValueError):  # O(1)
        return None  # O(1)
    for b in data.get("batches", []):  # O(b)
        if b.get("id") == BATCH and b.get("worktree"):  # O(1)
            return Path(b["worktree"])  # O(1)
    return None  # O(1)


def suite(clone: Path) -> dict | None:  # the newest full run_tests summary of the lead: its worktree's .superlite/ or the clone's .superlite/runs/*/, read before cleanup | O(files)
    wt = worktree(clone)  # O(b)
    files = list(Path(wt).glob(".superlite/test-summary*.json")) if wt else []  # O(files)
    files += list(Path(clone).glob(".superlite/runs/*/test-summary*.json"))  # `orchestrator end` moves a run's files into the main checkout's runs/ | O(files)
    best, best_t = None, -1.0  # O(1)
    for f in files:  # O(files)
        try:  # O(1)
            d = json.loads(f.read_text(encoding="utf-8", errors="replace"))  # O(size)
            t = f.stat().st_mtime  # O(1)
        except (OSError, ValueError):  # O(1)
            continue  # O(1)
        if isinstance(d, dict) and d.get("mode") == "full" and t > best_t:  # a fast, recorded or torn summary is no suite run | O(1)
            best, best_t = d, t  # O(1)
    if best is None:  # O(1)
        return None  # O(1)
    return {"passed": int(best.get("passed") or 0), "failed": int(best.get("failed") or 0)}  # O(1)


PATCH_CAP = 2 * 1024 * 1024  # O(1) bytes of a saved patch


_PATCH_ERR: dict = {}  # O(w) worktree -> first stderr line of the git step that failed


def _fail(wt, r) -> None:  # O(1)
    lines = r.stderr.decode("utf-8", errors="replace").strip().splitlines()  # O(err)
    _PATCH_ERR[str(wt)] = lines[0][:200] if lines else f"git exit {r.returncode}"  # O(1)


def patch_error(wt: Path) -> str:  # why the last patch of wt gave "" ("" when it did not fail) | O(1)
    return _PATCH_ERR.get(str(wt), "")  # O(1)


def patch(wt: Path, base: str) -> str:  # the lead's change against the base, tracked and new files, never .superlite/; "" on any failure | O(tree)
    tmp = None  # O(1)
    _PATCH_ERR.pop(str(wt), None)  # O(1)
    try:  # O(1)
        tmp = tempfile.mkdtemp(prefix="golden-idx-")  # O(1)
        env = _env()  # O(env)
        env["GIT_INDEX_FILE"] = str(Path(tmp) / "index")  # a throwaway index: the clone's own stays untouched | O(1)
        for cmd in (["read-tree", base], ["add", "-A"], ["rm", "-r", "-q", "--cached", "--ignore-unmatch", ".superlite"]):  # an ignored .superlite makes an exclude pathspec fail | O(1)
            r = subprocess.run(["git", *cmd], cwd=str(wt), capture_output=True, env=env, timeout=120)  # O(tree)
            if r.returncode != 0:  # O(1)
                _fail(wt, r)  # O(1)
                return ""  # O(1)
        r = subprocess.run(["git", "diff", "--cached", "--binary", base], cwd=str(wt), capture_output=True, env=env, timeout=120)  # O(diff)
        if r.returncode != 0:  # O(1)
            _fail(wt, r)  # O(1)
            return ""  # O(1)
        raw = r.stdout  # O(diff)
        if len(raw) > PATCH_CAP:  # O(1)
            raw = raw[:PATCH_CAP].rsplit(b"\n", 1)[0] + b"\n... cut\n"  # O(diff)
        return raw.decode("utf-8", errors="replace")  # O(diff)
    except Exception as e:  # a patch never ends a run | O(1)
        _PATCH_ERR[str(wt)] = f"{type(e).__name__}: {e}"[:200]  # O(1)
        return ""  # O(1)
    finally:  # O(1)
        if tmp:  # O(1)
            shutil.rmtree(tmp, ignore_errors=True)  # O(1)


def cleanup(clone: Path) -> None:  # O(size)
    clone = Path(clone)  # O(1)
    if not clone.exists():  # O(1)
        _drop_gh()  # O(1)
        return  # O(1)
    _run(["python3", str(HERE / "fleet.py"), "stop", "--all", "--plan", str(clone / ".superlite")], cwd=clone, timeout=120)  # the clone's own folder, never the caller's run | O(fleet)
    shutil.rmtree(clone, ignore_errors=True)  # O(size)
    _drop_gh()  # O(1)
