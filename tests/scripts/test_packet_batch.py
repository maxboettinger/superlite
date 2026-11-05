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


def test_hook_uncapped_at_default_budget(proj):
    commit_base(proj, {"hooks/h500": 1})
    change(proj, "hooks/h500", 500)
    s = sec8(packet(proj))
    assert "+new 499" in s and "(truncated:" not in s


def test_hook_cut_by_size_cap(proj):
    commit_base(proj, {"hooks/h500": 1})
    change(proj, "hooks/h500", 500)
    s = sec8(packet(proj, "--max-tokens", "2000"))
    assert "size cap" in s and "of 506" in s and "+new 499" not in s


def fill_total(proj: Path) -> None:
    commit_base(proj, {f"src/f{i}.py": 1 for i in range(8)})
    for i in range(8):
        change(proj, f"src/f{i}.py", 300)


def test_left_out_named(proj):
    fill_total(proj)
    s = sec8(packet(proj, "--max-tokens", "2000")).splitlines()
    first = next(line for line in s[1:] if line.strip())
    assert first.startswith("Left out: ") and "src/f7.py" in first and "src/f0.py" not in first


def change_wide(proj: Path, name: str, n: int, width: int = 60) -> None:
    f = proj / name
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("".join(f"new {i} ".ljust(width, "x") + "\n" for i in range(n)), encoding="utf-8")


def headed(s: str) -> list[str]:
    return [h[4:] for h in s.splitlines() if h.startswith("### ")]


def test_default_budget_scales_with_changed_code(proj):
    """#80: by default every changed code file gets its capped hunks; the packet grows past 20k tokens to fit them."""
    names = [f"src/f{i}.py" for i in range(8)]
    commit_base(proj, {n: 1 for n in names})
    for n in names:
        change_wide(proj, n, 300)
    text = packet(proj)
    s = sec8(text)
    assert headed(s) == names
    assert "Left out:" not in text
    assert s.count("(truncated: 120 of") == 8
    assert int(20000 * 1.9) < len(text) <= int(60000 * 1.9)


def test_default_budget_ceiling_60k(proj):
    """#80: the scaled default stops at 60k tokens; files past the ceiling are named in Left out."""
    names = [f"src/f{i:02}.py" for i in range(40)]
    commit_base(proj, {n: 1 for n in names})
    for n in names:
        change_wide(proj, n, 300, width=80)
    text = packet(proj)
    assert len(text) <= int(60000 * 1.9)
    assert "Left out: " in text and "src/f39.py" in text.split("Left out: ", 1)[1]
    assert "(truncated: 40 of" in sec8(text)  # past the ceiling every shown file gets the floor first


def test_floor_before_fill(proj):
    """#80: one large hook no longer crowds out the core files; each changed code file gets hunks first."""
    code = [f"src/f{i}.py" for i in range(6)]
    commit_base(proj, {"hooks/guard": 1, **{n: 1 for n in code}})
    change_wide(proj, "hooks/guard", 500, width=20)
    for n in code:
        change_wide(proj, n, 300, width=20)
    s = sec8(packet(proj, "--max-tokens", "20000"))
    assert headed(s) == ["hooks/guard", *code]
    assert "Left out:" not in s


def test_explicit_max_tokens_still_caps(proj):
    names = [f"src/f{i}.py" for i in range(8)]
    commit_base(proj, {n: 1 for n in names})
    for n in names:
        change_wide(proj, n, 300)
    assert len(packet(proj, "--max-tokens", "3000")) <= int(3000 * 1.9)


def test_hot_test_file_gets_the_floor(proj):
    """#80 review: a hot-spot test file (an incident points at it) gets its floor before the code files."""
    code = [f"src/f{i}.py" for i in range(10)]
    commit_base(proj, {"tests/test_hot.py": 1, **{n: 1 for n in code}})
    change_wide(proj, "tests/test_hot.py", 300)
    for n in code:
        change_wide(proj, n, 300)
    (proj / ".superlite" / "incidents.jsonl").write_text(json.dumps(
        {"kind": "exception", "file": "tests/test_hot.py", "line": 1, "context": "boom", "resolution": "", "agent": "T1"})
        + "\n", encoding="utf-8")
    s = sec8(packet(proj, "--max-tokens", "6000"))
    assert headed(s)[0] == "tests/test_hot.py"


def test_excerpts_fit_their_budget(proj):
    """#80 review: long paths, truncation notes and the Left out line are charged; every fence is closed."""
    names = [f"skills/subagent-driven-development/scripts/module_number_{i:02}.py" for i in range(40)]
    commit_base(proj, {n: 1 for n in names})
    for n in names:
        change_wide(proj, n, 300)
    for budget in (3000, 5000, 20000):
        out = pt.source_excerpts(proj, None, [], budget=budget)
        assert len(out) <= budget, budget
        assert out.startswith("Left out: ")
        assert out.count("```diff") == sum(1 for ln in out.splitlines() if ln == "```"), budget


def test_max_tokens_must_be_positive(proj):
    for bad in ("0", "-5"):
        r = subprocess.run([sys.executable, str(SCRIPT), "packet", "--plan", str(proj / "plan.md"),
                            "--root", str(proj), "--out", str(proj / "packet.md"), "--max-tokens", bad],
                           capture_output=True, text=True, timeout=60)
        assert r.returncode == 2, bad


def test_items_keep_their_share_when_excerpts_grow(proj):
    """#80 review: a large diff grows the packet for its excerpts, not at the expense of the items."""
    log = "\n".join(json.dumps({"kind": "perf", "file": "src/a.py", "line": n + 1, "context": f"issue {n} " + "x" * 120,
                                "resolution": "", "agent": "T1"}) for n in range(200)) + "\n"
    names = [f"src/f{i}.py" for i in range(8)]
    commit_base(proj, {"src/a.py": 1, **{n: 1 for n in names}})
    (proj / ".superlite" / "incidents.jsonl").write_text(log, encoding="utf-8")
    for n in names:
        change_wide(proj, n, 300)
    fixed = packet(proj, "--max-tokens", "20000")  # the old default: excerpts get a third
    grown = packet(proj)
    count = lambda t: sum(1 for ln in t.splitlines() if ln.startswith("### [")) # noqa: E731
    assert count(grown) == count(fixed) > 0
    assert len(grown) > len(fixed)


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
