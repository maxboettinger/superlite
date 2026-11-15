"""Golden case files: list, create and verify golden cases under bench/golden/<id>/case.json (T3)."""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Complexity notation: c = cases, h = hidden tests, i = closing issues, r = batch rows

SIZES = ("small", "typical", "large")
ORDER = {s: i for i, s in enumerate(SIZES)}
REQUIRED = ("id", "size", "topic", "base", "merge", "issues", "test_cmd", "hidden_tests")
TEST_CMD = "uv run --no-project --with pytest python -m pytest -q -p no:cacheprovider"


PRIVATE = (("a home path", re.compile(r"(?:/Users/|/home/|[A-Za-z]:\\Users\\)[\w.-]+")),
           ("a token", re.compile(r"\b(?:gh[pousr]_\w{20,}|github_pat_\w{20,}|sk-[A-Za-z0-9_-]{20,}|xox[abp]-[\w-]{10,}|AKIA[0-9A-Z]{16})\b")),
           ("a hostname", re.compile(r"\b[\w]+(?:\.[\w-]+)*\.ts\.net\b|\b[A-Za-z0-9]+-[\w-]*\.(?:local|lan)\b|\b[A-Za-z]+\d[\w-]*\.(?:local|lan)\b", re.I)))


class CaseError(ValueError):
    """A golden case file is missing, malformed or unsafe."""


def private_text(case: dict) -> str | None:  # O(text)
    """The kind of private content (home path, token, hostname) in the case's issues and hidden tests, else None."""
    parts = [x for it in case.get("issues", []) if isinstance(it, dict) for x in (it.get("title"), it.get("body"))]  # O(i)
    parts += [h.get("text") for h in case.get("hidden_tests", []) if isinstance(h, dict)]  # O(h)
    for kind, rx in PRIVATE:  # O(1)
        if any(isinstance(t, str) and rx.search(t) for t in parts):  # O(text)
            return kind  # O(1)
    return None  # O(1)


def _run(cmd: list, cwd=None, timeout=None) -> tuple[int, str]:  # O(output)
    env = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE")}  # O(env)
    try:  # O(1)
        r = subprocess.run(cmd, cwd=None if cwd is None else str(cwd), capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout, env=env)  # O(output)
    except (OSError, subprocess.TimeoutExpired) as e:  # O(1)
        return 127, str(e)  # O(1)
    return r.returncode, (r.stdout or "") + (r.stderr or "")  # O(output)


def _safe_path(p) -> bool:  # O(len)
    if not isinstance(p, str) or not p or p.startswith(("/", "\\")) or "\\" in p or (len(p) > 1 and p[1] == ":"):  # O(1)
        return False  # O(1)
    return ".." not in p.split("/") and "" not in p.split("/")  # O(len)


def load(case_dir: Path) -> dict:  # O(h)
    f = Path(case_dir) / "case.json"  # O(1)
    try:  # O(1)
        d = json.loads(f.read_text(encoding="utf-8"))  # O(file)
    except OSError as e:  # O(1)
        raise CaseError(f"{f}: {e}") from e  # O(1)
    except ValueError as e:  # O(1)
        raise CaseError(f"{f}: bad JSON: {e}") from e  # O(1)
    if not isinstance(d, dict):  # O(1)
        raise CaseError(f"{f}: not a JSON object")  # O(1)
    for k in REQUIRED:  # O(1)
        if k not in d:  # O(1)
            raise CaseError(f"{f}: missing key {k}")  # O(1)
    if not isinstance(d["topic"], str) or not d["topic"]:  # seal names the batch after it | O(1)
        raise CaseError(f"{f}: topic is not a non-empty string")  # O(1)
    if not isinstance(d["issues"], list):  # O(1)
        raise CaseError(f"{f}: issues is not a list")  # O(1)
    for it in d["issues"]:  # seal uses the number as a file name | O(i)
        if (not isinstance(it, dict) or not isinstance(it.get("number"), int) or isinstance(it.get("number"), bool)
                or not isinstance(it.get("title"), str) or not isinstance(it.get("body"), str)):  # O(1)
            raise CaseError(f"{f}: issue entry malformed (needs int number, str title, str body): {it!r}")  # O(1)
    if not isinstance(d["hidden_tests"], list):  # O(1)
        raise CaseError(f"{f}: hidden_tests is not a list")  # O(1)
    for h in d["hidden_tests"]:  # O(h)
        if not isinstance(h, dict) or not isinstance(h.get("text"), str) or not _safe_path(h.get("path")):  # O(len)
            raise CaseError(f"{f}: hidden test path unsafe or entry malformed: {h.get('path') if isinstance(h, dict) else h!r}")  # O(1)
    bad = private_text(d)  # O(text)
    if bad:  # O(1)
        raise CaseError(f"{f}: case text holds {bad}")  # O(1)
    d.setdefault("baseline", {})  # O(1)
    d["dir"] = str(Path(case_dir).resolve())  # O(1)
    return d  # O(1)


def cases(root: Path) -> list:  # O(c log c)
    base = Path(root) / "bench" / "golden"  # O(1)
    if not base.is_dir():  # O(1)
        return []  # O(1)
    out = [load(p) for p in base.iterdir() if (p / "case.json").is_file()]  # O(c)
    return sorted(out, key=lambda c: (ORDER.get(c["id"], len(ORDER)), c["id"]))  # O(c log c)


def _git(root, *args) -> str:  # O(output)
    rc, out = _run(["git", *args], cwd=root)  # O(output)
    if rc != 0:  # O(1)
        raise CaseError(f"git {' '.join(args)} failed: {out.strip()}")  # O(1)
    return out  # O(1)


def _gh_json(root, *args) -> dict:  # O(output)
    rc, out = _run(["gh", *args], cwd=root)  # O(output)
    try:  # O(1)
        if rc != 0:  # O(1)
            raise ValueError(out.strip())  # O(1)
        return json.loads(out)  # O(output)
    except ValueError as e:  # O(1)
        raise CaseError(f"gh {' '.join(args[:3])} failed: {e}") from e  # O(1)


def _baseline(root: Path, batch: str | None) -> dict:  # O(r)
    if not batch:  # O(1)
        return {}  # O(1)
    import batch_cost  # O(1)
    rows = [r for r in batch_cost.read_rows(root) if r.get("row") == "batch" and r.get("batch") == batch]  # O(r)
    if not rows:  # O(1)
        raise CaseError(f"no batch row for {batch}")  # O(1)
    lead, wt = rows[-1].get("lead") or {}, rows[-1].get("workers_total") or {}  # O(1)
    lu = float(lead.get("cost_usd", 0) or 0)  # O(1)
    return {"lead_usd": lu, "total_usd": round(lu + float(wt.get("cost_usd", 0) or 0), 6),
            "lead_turns": int(lead.get("turns", 0) or 0), "wall_min": round(float(lead.get("wall_s", 0) or 0) / 60, 1)}  # O(1)


def make(root: Path, pr: int, case_id: str, size: str, batch: str | None = None) -> Path:  # O(i + h)
    root = Path(root)  # O(1)
    if size not in SIZES:  # O(1)
        raise CaseError(f"size must be one of {', '.join(SIZES)}, got {size}")  # O(1)
    if not _safe_path(case_id) or "/" in case_id:  # O(1)
        raise CaseError(f"bad case id {case_id!r}")  # O(1)
    view = _gh_json(root, "pr", "view", str(pr), "--json", "mergeCommit,title,closingIssuesReferences")  # O(output)
    merge = (view.get("mergeCommit") or {}).get("oid")  # O(1)
    if not merge:  # O(1)
        raise CaseError(f"PR {pr} has no merge commit")  # O(1)
    base = _git(root, "rev-parse", f"{merge}^1").strip()  # O(1)
    status = _git(root, "diff", "--name-status", base, merge, "--", "tests/")  # O(files)
    paths = [ln.split("\t", 1)[1] for ln in status.splitlines() if ln.startswith("A\t")]  # O(files)
    if not paths:  # O(1)
        raise CaseError(f"PR {pr} adds no test file")  # O(1)
    hidden = [{"path": p, "text": _git(root, "show", f"{merge}:{p}")} for p in paths]  # O(h)
    issues = []  # O(1)
    for ref in view.get("closingIssuesReferences") or []:  # O(i)
        n = ref["number"]  # O(1)
        iv = _gh_json(root, "issue", "view", str(n), "--json", "title,body")  # O(output)
        issues.append({"number": n, "title": iv.get("title", ""), "body": iv.get("body", "")})  # O(1)
    case = {"id": case_id, "size": size, "topic": f"golden-{case_id}", "base": base, "merge": merge, "issues": issues,
            "test_cmd": TEST_CMD, "hidden_tests": hidden, "baseline": _baseline(root, batch)}  # O(1)
    bad = private_text(case)  # O(text)
    if bad:  # O(1)
        raise CaseError(f"case {case_id} refused: its text holds {bad}")  # O(1)
    d = root / "bench" / "golden" / case_id  # O(1)
    d.mkdir(parents=True, exist_ok=True)  # O(1)
    (d / "case.json").write_text(json.dumps(case, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")  # O(file)
    return d  # O(1)


def tests_green(code: int, out: str) -> bool:  # the one pass check of verify and of a golden run | O(out)
    passed = re.search(r"(\d+) passed", out)  # a skipped module exits 0 without running a test | O(out)
    skipped = re.search(r"(\d+) skipped", out)  # O(out)
    return code == 0 and bool(passed) and int(passed.group(1)) > 0 and not (skipped and int(skipped.group(1)) > 0)  # O(1)


def _passes(root: Path, sha: str, case: dict) -> bool:  # O(h + test run)
    tmp = Path(tempfile.mkdtemp(prefix="golden-verify-"))  # O(1)
    try:  # O(1)
        clone = tmp / "clone"  # O(1)
        for cmd in (["git", "clone", "-q", "--no-checkout", str(root), str(clone)], ["git", "checkout", "-q", sha]):  # O(1)
            rc, out = _run(cmd, cwd=clone if cmd[1] == "checkout" else None)  # O(clone)
            if rc != 0:  # O(1)
                raise CaseError(f"{' '.join(cmd[:2])} {sha}: {out.strip()}")  # O(1)
        paths = []  # O(1)
        for h in case["hidden_tests"]:  # O(h)
            if not _safe_path(h["path"]):  # O(len)
                raise CaseError(f"hidden test path unsafe: {h['path']}")  # O(1)
            f = clone / h["path"]  # O(1)
            f.parent.mkdir(parents=True, exist_ok=True)  # O(1)
            f.write_text(h["text"], encoding="utf-8", newline="\n")  # O(file)
            paths.append(h["path"])  # O(1)
        rc, out = _run([*shlex.split(case["test_cmd"]), *paths], cwd=clone, timeout=900)  # O(test run)
        return tests_green(rc, out)  # O(out)
    finally:  # O(1)
        shutil.rmtree(tmp, ignore_errors=True)  # O(clone)


def verify(root: Path, case: dict) -> dict:  # O(test runs)
    return {"base_fails": not _passes(Path(root), case["base"], case), "merge_passes": _passes(Path(root), case["merge"], case)}  # O(test runs)


def main(argv: list | None = None) -> int:  # O(c)
    ap = argparse.ArgumentParser(prog="golden_case")  # O(1)
    ap.add_argument("--root", default=".")  # O(1)
    sub = ap.add_subparsers(dest="cmd", required=True)  # O(1)
    m = sub.add_parser("make")  # O(1)
    m.add_argument("--pr", type=int, required=True)  # O(1)
    m.add_argument("--id", required=True)  # O(1)
    m.add_argument("--size", required=True, choices=SIZES)  # O(1)
    m.add_argument("--batch")  # O(1)
    v = sub.add_parser("verify")  # O(1)
    v.add_argument("id", nargs="?")  # O(1)
    sub.add_parser("list")  # O(1)
    a = ap.parse_args(argv)  # O(1)
    root = Path(a.root)  # O(1)
    try:  # O(1)
        if a.cmd == "make":  # O(1)
            print(make(root, a.pr, a.id, a.size, a.batch))  # O(1)
            return 0  # O(1)
        cs = cases(root)  # O(c)
        if a.cmd == "list":  # O(1)
            for c in cs:  # O(c)
                print(f"{c['id']}\t{c['size']}")  # O(1)
            return 0  # O(1)
        if a.id:  # O(1)
            cs = [c for c in cs if c["id"] == a.id]  # O(c)
            if not cs:  # O(1)
                print(f"golden_case: no case {a.id}", file=sys.stderr)  # O(1)
                return 2  # O(1)
        bad = 0  # O(1)
        for c in cs:  # O(c)
            r = verify(root, c)  # O(test runs)
            print(f"{c['id']}\tbase_fails={r['base_fails']}\tmerge_passes={r['merge_passes']}")  # O(1)
            bad += not all(r.values())  # O(1)
        return 1 if bad else 0  # O(1)
    except CaseError as e:  # O(1)
        print(f"golden_case: {e}", file=sys.stderr)  # O(1)
        return 2  # O(1)


if __name__ == "__main__":
    sys.exit(main())
