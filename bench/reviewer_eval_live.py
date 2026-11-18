#!/usr/bin/env python3
"""Reviewer eval live adapters: clone a case, build its packet, run the final reviewer, grade a pool.

    checkout(case, work) -> work/<id>, a clone detached at the merge commit, without a remote
    packet(clone, case) -> the inline review packet path, built against the case's base
    review(case, variant, work) -> {"findings", "unverified", "cost_usd", "seconds"}
    grade(case, pooled, model="opus") -> {fp: {"grade", "serious"}}; {} when the reply holds no array

Every subprocess and model call goes through `_run` or `_ask`; tests patch those two.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SCRIPTS = ROOT / "skills" / "subagent-driven-development" / "scripts"
for p in (str(SCRIPTS), str(HERE / "experiments"), str(HERE)):
    if p not in sys.path:
        sys.path.insert(0, p)
import common  # noqa: E402
import finding_check  # noqa: E402
import fleet_report  # noqa: E402
import mechanical_ab  # noqa: E402

DIFF_LIMIT = 60000
REVIEW_BUDGET = 3.0
REVIEW_TIMEOUT = 1800
GRADE_BUDGET = 2.0
GRADE_INSTRUCTION = ("Grade each finding. Answer only a JSON array of "
                     '{"fp": "<fp>", "grade": "real"|"nit"|"wrong", "serious": true|false}. '
                     "real = a defect the change introduces or leaves in the changed code, nit = true but no defect, wrong = not true; "
                     "serious = wrong results, data loss, a crash or a security hole.")


class LiveError(RuntimeError):
    """A subprocess or model call of the live eval failed."""


def _run(cmd, cwd, env=None, timeout=600):
    """subprocess.run with captured text output; git's hook variables never leak in."""
    base = dict(os.environ if env is None else env)
    for k in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE"):
        base.pop(k, None)
    return subprocess.run(cmd, cwd=cwd, env=base, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout)


def _ask(prompt, cwd, model="opus"):
    """One tool-less model call, as bench/experiments/e4_review.py makes it."""
    return common.run_claude(prompt, model=model, cwd=Path(cwd), budget=GRADE_BUDGET, timeout=900,
                             extra_args=["--disable-slash-commands", "--disallowedTools",
                                         "Bash Edit Write Read Glob Grep Agent WebFetch WebSearch"])


def _git(cmd, cwd):
    try:
        out = _run(["git", *cmd], cwd)
    except subprocess.TimeoutExpired as exc:
        raise LiveError(f"git {' '.join(cmd)} timed out") from exc
    if out.returncode != 0:
        raise LiveError(f"git {' '.join(cmd)} failed: {out.stderr.strip()}")
    return out.stdout


def checkout(case: dict, work: Path) -> Path:
    if Path(str(case["id"])).name != str(case["id"]) or str(case["id"]) in ("", ".", ".."):
        raise LiveError(f"case id {case['id']!r} is not a plain folder name")
    dest = Path(work) / case["id"]
    if dest.exists():
        shutil.rmtree(dest)
    Path(work).mkdir(parents=True, exist_ok=True)
    _git(["clone", "--no-hardlinks", "-q", case["repo"], str(dest)], work)
    _git(["checkout", "-q", "--detach", case["merge"]], dest)
    _git(["remote", "remove", "origin"], dest)
    return dest


def packet(clone: Path, case: dict) -> Path:
    sd = Path(clone) / ".superlite"
    sd.mkdir(exist_ok=True)
    (sd / "spec.md").write_text(f"# {case['title']}\n\n{case['body']}\n", encoding="utf-8")
    cmd = [str(SCRIPTS / "sl"), "plan_tools", "packet", "--inline", "--spec", ".superlite/spec.md", "--base", case["base"]]
    try:
        out = _run(cmd, Path(clone))
    except subprocess.TimeoutExpired as exc:
        raise LiveError(f"packet timed out for {case['id']}") from exc
    if out.returncode != 0:
        raise LiveError(f"packet failed for {case['id']}: {out.stderr.strip()}")
    return sd / "review-packet.md"


def _with_effort(cmd: list, effort: str) -> list:
    cmd = list(cmd)
    if "--effort" in cmd:
        cmd[cmd.index("--effort") + 1] = effort
    else:
        cmd += ["--effort", effort]
    return cmd


def review(case: dict, variant: dict, work: Path) -> dict:
    where = f"case {case['id']}, variant {variant['name']}"
    clone = checkout(case, work)
    pkt = packet(clone, case)
    prompt = fleet_report.brief_message("final-reviewer", str(pkt))
    cmd = _with_effort(mechanical_ab.claude_cmd(variant["model"], prompt, REVIEW_BUDGET, agent="final-reviewer"), variant["effort"])
    t0 = time.time()
    try:
        out = _run(cmd, clone, env=common.clean_env(), timeout=REVIEW_TIMEOUT)
    except subprocess.TimeoutExpired as exc:
        raise LiveError(f"reviewer timed out ({where})") from exc
    run = common.parse_stream(out.stdout or "", time.time() - t0)
    if not run.result:
        raise LiveError(f"reviewer gave no result ({where}): {(out.stderr or '').strip()[:200]}")
    findings, unverified = [], 0
    for f in fleet_report.parse(run.text)["findings"]:
        v = finding_check.verify(clone, f)
        if v["state"] == "unverified":
            unverified += 1
            continue
        line = v["line"] if v["state"] == "moved" else f["line"]
        findings.append({**f, "line": line, "fp": finding_check.fingerprint(f["file"], f["quote"], f["problem"])})
    return {"findings": findings, "unverified": unverified, "cost_usd": run.cost, "seconds": run.seconds}


def grade(case: dict, pooled: list, model: str = "opus") -> dict:
    try:
        out = _run(["git", "diff", case["base"], case["merge"]], case["repo"])
    except subprocess.TimeoutExpired as exc:
        raise LiveError(f"git diff timed out for {case['id']}") from exc
    if out.returncode != 0:
        raise LiveError(f"git diff failed for {case['id']}: {(out.stderr or '').strip()}")
    diff = out.stdout or ""
    if len(diff) > DIFF_LIMIT:
        diff = diff[:DIFF_LIMIT] + "\n(diff cut)"
    lines = "\n".join(f"{e['fp']} | {e['file']}:{e['line']} | {e['problem']} | {e['quote']}" for e in pooled)
    prompt = (f"Pull request: {case['title']}\n\n{case['body']}\n\n<diff>\n{diff}\n</diff>\n\n"
              f"Findings (fp | file:line | problem | quote):\n{lines}\n\n{GRADE_INSTRUCTION}")
    with tempfile.TemporaryDirectory() as tmp:
        try:
            run = _ask(prompt, tmp, model)
        except subprocess.TimeoutExpired as exc:
            raise LiveError(f"grader timed out for {case['id']}") from exc
    items = []
    for m in re.finditer(r"\[", run.text):
        try:
            got, _ = json.JSONDecoder().raw_decode(run.text, m.start())
        except ValueError:
            continue
        if isinstance(got, list) and any(isinstance(i, dict) for i in got):
            items = got
            break
    out = {}
    for item in items if isinstance(items, list) else []:
        if isinstance(item, dict) and isinstance(item.get("fp"), str):
            out[item["fp"]] = {"grade": item.get("grade"), "serious": item.get("serious") is True}
    return out
