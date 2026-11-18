#!/usr/bin/env python3
"""Reviewer eval CLI: build a case set from merged pull requests, run the final reviewer on it, read the scores.

    uv run --no-project python bench/reviewer_eval_cli.py make-case --repo PATH --pr N --set NAME
    uv run --no-project python bench/reviewer_eval_cli.py run --set NAME [--variant name=model:effort]... [--limit N] [--grader-model opus] [--work DIR]
    uv run --no-project python bench/reviewer_eval_cli.py report --set NAME

A set lives in `$SUPERLITE_HOME/reviewer-eval/<set>/` (default `~/.superlite/`): `cases.json` and `results/<UTC timestamp>.json`.
Exit codes: 0 done, 1 a case failed, 2 usage error.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import reviewer_eval as ev  # noqa: E402
import reviewer_eval_live as live  # noqa: E402

AGENT = HERE.parent / "agents" / "final-reviewer.md"
NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def set_dir(name: str) -> Path:
    if not NAME.match(name or "") or ".." in name:
        raise ValueError(f"bad set name {name!r}")
    home = os.environ.get("SUPERLITE_HOME") or str(Path.home() / ".superlite")
    return Path(home) / "reviewer-eval" / name


def _gh(repo, pr):
    out = subprocess.run(["gh", "pr", "view", str(pr), "--json", "mergeCommit,title,body"], cwd=repo,
                         capture_output=True, text=True, encoding="utf-8", timeout=120)
    if out.returncode != 0:
        raise ValueError(f"gh pr view failed: {out.stderr.strip()}")
    return json.loads(out.stdout)


def _first_parent(repo, sha):
    env = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE")}
    out = subprocess.run(["git", "rev-parse", f"{sha}^1"], cwd=repo, env=env, capture_output=True, text=True, timeout=60)
    if out.returncode != 0:
        raise ValueError(f"no parent for {sha}: {out.stderr.strip()}")
    return out.stdout.strip()


def _err(msg):
    print(msg, file=sys.stderr)
    return 2


def make_case(a):
    d = set_dir(a.set)
    cases = ev.load_cases(d) if (d / "cases.json").exists() else []
    cid = f"pr-{a.pr}"
    if any(c["id"] == cid for c in cases):
        return _err(f"{cid} already in the set")
    info = _gh(a.repo, a.pr)
    merge = (info.get("mergeCommit") or {}).get("oid")
    if not merge:
        return _err(f"pull request {a.pr} has no merge commit")
    cases.append({"id": cid, "repo": str(Path(a.repo).resolve()), "base": _first_parent(a.repo, merge), "merge": merge,
                  "title": info.get("title") or "", "body": info.get("body") or ""})
    d.mkdir(parents=True, exist_ok=True)
    (d / "cases.json").write_text(json.dumps(cases, indent=1), encoding="utf-8")
    print(f"added {cid} to {a.set}")
    return 0


def default_variant():
    text = AGENT.read_text(encoding="utf-8")
    model = re.search(r"^model:\s*(\S+)", text, re.M)
    effort = re.search(r"^effort:\s*(\S+)", text, re.M)
    if not model or not effort:
        raise ValueError("agents/final-reviewer.md lacks model or effort")
    return {"name": "current", "model": model.group(1), "effort": effort.group(1)}


def run(a):
    d = set_dir(a.set)
    cases = ev.load_cases(d)
    if a.limit is not None:
        if a.limit < 1:
            return _err("--limit must be at least 1")
        cases = cases[:a.limit]
    variants = [ev.parse_variant(v) for v in a.variant] or [default_variant()]
    work = Path(a.work) if a.work else Path(tempfile.mkdtemp(prefix="reviewer-eval-"))
    rows, failed = [], []
    try:
        for case in cases:
            try:
                rows.append(ev.run_case(case, variants, live.review, lambda c, p: live.grade(c, p, a.grader_model), work))
            except live.LiveError as exc:
                failed.append({"case": case["id"], "error": str(exc)})
    finally:
        if not a.work:
            shutil.rmtree(work, ignore_errors=True)
    summary = ev.summarize(rows)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (d / "results").mkdir(exist_ok=True)
    (d / "results" / f"{stamp}.json").write_text(
        json.dumps({"set": a.set, "variants": variants, "rows": rows, "failed": failed, "summary": summary}, indent=1), encoding="utf-8")
    for f in failed:
        print(f"failed {f['case']}: {f['error']}")
    print(ev.table(summary))
    return 1 if failed else 0


def report(a):
    results = sorted((set_dir(a.set) / "results").glob("*.json"))
    if not results:
        return _err(f"no results in {a.set}")
    print(ev.table(json.loads(results[-1].read_text(encoding="utf-8"))["summary"]))
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="reviewer_eval_cli")
    sub = p.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("make-case")
    m.add_argument("--repo", required=True)
    m.add_argument("--pr", type=int, required=True)
    m.add_argument("--set", required=True)
    r = sub.add_parser("run")
    r.add_argument("--set", required=True)
    r.add_argument("--variant", action="append", default=[])
    r.add_argument("--limit", type=int)
    r.add_argument("--grader-model", default="opus")
    r.add_argument("--work")
    sub.add_parser("report").add_argument("--set", required=True)
    try:
        a = p.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2
    try:
        return {"make-case": make_case, "run": run, "report": report}[a.cmd](a)
    except (ValueError, OSError) as exc:  # CaseError is a ValueError
        return _err(str(exc))


if __name__ == "__main__":
    sys.exit(main())
