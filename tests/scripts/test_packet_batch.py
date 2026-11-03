"""Review packet: hunks of every changed file (#62), stale test failures judged over the whole run (#55)."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent.parent / "skills" / "subagent-driven-development" / "scripts"
SCRIPT = SCRIPTS / "pt_review.py"
_spec = importlib.util.spec_from_file_location("pt_review_batch", SCRIPT)
pt = importlib.util.module_from_spec(_spec)
sys.modules["pt_review_batch"] = pt
_spec.loader.exec_module(pt)

PLAN = "# p\n\n### T1 thing · Complexity 1\n**Owns:** src/a.py\n\n## Review Focus\n- none\n"


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), "-c", "user.email=t@t", "-c", "user.name=t", *args],
                          capture_output=True, text=True, check=True).stdout


@pytest.fixture()
def proj(tmp_path: Path) -> Path:
    (tmp_path / ".superlite").mkdir()
    (tmp_path / "plan.md").write_text(PLAN, encoding="utf-8")
    git(tmp_path, "init", "-q")
    return tmp_path


def commit_base(proj: Path, files: dict[str, int]) -> None:
    for name, n in files.items():
        f = proj / name
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("".join(f"old {i}\n" for i in range(n)), encoding="utf-8")
    git(proj, "add", "-A")
    git(proj, "commit", "-qm", "base")


def change(proj: Path, name: str, n: int) -> None:
    f = proj / name
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("".join(f"new {i}\n" for i in range(n)), encoding="utf-8")


def packet(proj: Path, *extra: str) -> str:
    r = subprocess.run([sys.executable, str(SCRIPT), "packet", "--plan", str(proj / "plan.md"),
                        "--root", str(proj), "--out", str(proj / "packet.md"), *extra],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return (proj / "packet.md").read_text(encoding="utf-8")


def sec8(text: str) -> str:
    return text.split("## 8.", 1)[1]


def test_changed_file_without_item_gets_hunks(proj):
    commit_base(proj, {"hooks/guard": 3})
    change(proj, "hooks/guard", 3)
    s = sec8(packet(proj))
    assert "### hooks/guard" in s and "+new 0" in s


def test_order_hot_hooks_code_rest(proj):
    commit_base(proj, {"src/a.py": 2, "hooks/guard": 2, "src/b.py": 2, "tests/test_b.py": 2, "README.md": 2})
    for n in ("src/a.py", "hooks/guard", "src/b.py", "tests/test_b.py", "README.md"):
        change(proj, n, 2)
    (proj / ".superlite" / "incidents.jsonl").write_text(json.dumps(
        {"kind": "exception", "file": "src/a.py", "line": 1, "context": "boom", "resolution": "", "agent": "T1"}) + "\n",
        encoding="utf-8")
    s = sec8(packet(proj))
    order = ("src/a.py", "hooks/guard", "src/b.py", "tests/test_b.py", "README.md")
    heads = [h[4:] for h in s.splitlines() if h.startswith("### ")]
    assert heads == list(order)


def test_hook_cap_400(proj):
    commit_base(proj, {"hooks/h300": 1, "hooks/h500": 1, "src/big.py": 1})
    change(proj, "hooks/h300", 300)
    s = sec8(packet(proj))
    assert "(truncated" not in s and "+new 299" in s
    change(proj, "hooks/h300", 1)
    change(proj, "hooks/h500", 500)
    change(proj, "src/big.py", 500)
    s = sec8(packet(proj, "--max-tokens", "40000"))
    assert "(truncated: 400 of" in s and "(truncated: 120 of" in s


def fill_total(proj: Path) -> None:
    commit_base(proj, {f"src/f{i}.py": 1 for i in range(8)})
    for i in range(8):
        change(proj, f"src/f{i}.py", 300)


def test_left_out_named(proj):
    fill_total(proj)
    s = sec8(packet(proj, "--max-tokens", "40000")).splitlines()
    first = next(line for line in s[1:] if line.strip())
    assert first.startswith("Left out: ") and "src/f7.py" in first and "src/f0.py" not in first


def test_left_out_survives_size_cap(proj):
    fill_total(proj)
    text = packet(proj, "--max-tokens", "500")
    assert "Left out: " in text and "src/f7.py" in text


def test_nothing_left_out_no_line(proj):
    commit_base(proj, {"src/a.py": 2})
    change(proj, "src/a.py", 2)
    assert "Left out:" not in packet(proj)


def test_checkpoint_diff_used(proj):
    commit_base(proj, {"src/a.py": 2, "src/b.py": 2})
    change(proj, "src/a.py", 2)
    git(proj, "add", "-A")
    git(proj, "commit", "-qm", "ckpt")
    sha = git(proj, "rev-parse", "HEAD").strip()
    change(proj, "src/b.py", 2)  # after the checkpoint: not part of the diff
    first = git(proj, "rev-list", "--max-parents=0", "HEAD").split()[0]
    (proj / pt.autocommit.STATE).write_text(json.dumps({"entries": [{"sha": sha}]}), encoding="utf-8")
    s = sec8(packet(proj, "--base", first))
    assert "### src/a.py" in s and "src/b.py" not in s and "Left out:" not in s


# ---- stale over the whole run

def inc(file="tests/a.py", ctx="tests/a.py::test_x failed"):
    return {"kind": "test-failure", "file": file, "line": 1, "context": ctx, "resolution": "open", "agent": "T1"}


def summ(path: Path, files: dict, failures=(), mtime: float | None = None):
    path.write_text(json.dumps({"passed": 1, "failed": len(failures), "skipped": 0, "mode": "full",
                                "failures": list(failures), "skipped_tests": [], "files": files}), encoding="utf-8")
    if mtime:
        os.utime(path, (mtime, mtime))


def log(proj: Path, entries):
    (proj / ".superlite" / "incidents.jsonl").write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")


def open_count(text: str) -> str:
    return text.split("\n")[3]


def test_focused_summary_keeps_stale(proj):
    sl = proj / ".superlite"
    log(proj, [inc()])
    summ(sl / "test-summary-1.json", {"tests/a.py": [3, 0]}, mtime=1000)
    summ(sl / "test-summary.json", {"tests/b.py": [1, 0]}, mtime=2000)
    t = packet(proj)
    assert "dropped 1 stale" in t and "Nothing is open" in t


def test_newest_covering_summary_decides(proj):
    sl = proj / ".superlite"
    log(proj, [inc()])
    summ(sl / "test-summary-1.json", {"tests/a.py": [3, 0]}, mtime=1000)
    summ(sl / "test-summary.json", {"tests/a.py": [3, 1]}, failures=["tests/a.py::test_x"], mtime=2000)
    t = packet(proj)
    assert "dropped" not in t and "Nothing is open" not in t


def test_no_covering_summary_stays_open(proj):
    sl = proj / ".superlite"
    log(proj, [inc()])
    summ(sl / "test-summary.json", {"tests/b.py": [1, 0]})
    assert "dropped" not in packet(proj)


@pytest.mark.parametrize("newest_red", [False, True])
def test_finish_matches_packet(proj, newest_red):
    sys.path.insert(0, str(SCRIPTS))
    import finish
    sl = proj / ".superlite"
    log(proj, [inc()])
    summ(sl / "test-summary-1.json", {"tests/a.py": [3, 0]}, mtime=1000)
    if newest_red:
        summ(sl / "test-summary.json", {"tests/a.py": [3, 1]}, failures=["tests/a.py::test_x"], mtime=2000)
    else:
        summ(sl / "test-summary.json", {"tests/b.py": [1, 0]}, mtime=2000)
    opened = finish.open_incidents(sl / "incidents.jsonl", finish.load_run_summaries(sl))
    assert bool(opened) == newest_red
    assert ("dropped" not in packet(proj)) == newest_red


def test_report_counts_open_over_whole_run(tmp_path):
    sys.path.insert(0, str(SCRIPTS))
    sys.path.insert(0, str(HERE))
    import report
    from test_metrics_history import setup_run
    from test_routing import mech_plan
    plan = mech_plan(tmp_path, 2)
    setup_run(tmp_path)
    sl = tmp_path / ".superlite"
    (sl / "incidents.jsonl").write_text(json.dumps(inc()) + "\n", encoding="utf-8")
    summ(sl / "test-summary-1.json", {"tests/a.py": [3, 0]}, mtime=1000)
    summ(sl / "test-summary.json", {"tests/b.py": [1, 0]}, mtime=2000)
    assert report.collect(plan, sl)["quality"]["open_incidents"] == 0


def _tool(res, ctx):
    return {"kind": "exception", "file": "hooks/x.sh", "line": 0, "context": ctx, "resolution": res, "agent": "commit_task"}


def test_resolved_tool_refusal_not_open(proj):
    log(proj, [_tool("open", "T1 out-of-scope block"), _tool("fixed", "committed with T3; earlier block resolved")])
    t = packet(proj)
    assert "FAST PATH" in t and "hooks/x.sh:0" not in t


def test_resolved_repeat_from_reviewer_still_listed(proj):
    es = [dict(_tool("open", "a"), agent="package-reviewer"), dict(_tool("fixed", "b"), agent="package-reviewer")]
    log(proj, es)
    assert "hooks/x.sh:0" in packet(proj)
