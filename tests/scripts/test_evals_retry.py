import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import evals_retry  # noqa: E402


def case(name, score, runs):
    agg = {} if score is None else {"score": score}
    return {"name": name, "aggregates": agg, "arms": {"with": [{"passed": p} for p in runs]}}


def result(cases, partial=False, threshold=1.0):
    return {"partial": partial, "suite": {"threshold": threshold}, "cases": cases}


def test_disagreeing_cases_are_retried():
    r = result([case("a", 0.5, [True, False]), case("ok", 1.0, [True, True]), case("b", 0.5, [False, True])])
    assert evals_retry.retry_cases(r) == (["a", "b"], "")


def test_no_retry_reasons():
    dis = case("a", 0.5, [True, False])
    assert evals_retry.retry_cases(result([dis, case("z", 0.0, [False, False])])) == ([], "z failed every run")
    assert evals_retry.retry_cases(result([case("ok", 1.0, [True, True])])) == ([], "no failing case")
    assert evals_retry.retry_cases(result([case("m", 0.6, [True, False])], threshold=0.5)) == ([], "no failing case")
    assert evals_retry.retry_cases(result([case("n", None, [True, False])])) == ([], "n failed every run")
    assert evals_retry.retry_cases(result([dis], partial=True)) == ([], "partial run")


def test_unsafe_case_name_is_not_retried():
    r = result([case("x; rm -rf /", 0.5, [True, False])])
    assert evals_retry.retry_cases(r) == ([], "unsafe case name: x; rm -rf /")


def test_cli_exit_codes(tmp_path, capsys):
    p = tmp_path / "r.json"
    p.write_text(json.dumps(result([case("a", 0.5, [True, False]), case("b", 0.5, [False, True])])))
    assert evals_retry.main([str(p)]) == 0
    cap = capsys.readouterr()
    assert cap.out == "a\nb\n"
    p.write_text(json.dumps(result([case("a", 0.0, [False, False])])))
    assert evals_retry.main([str(p)]) == 1
    cap = capsys.readouterr()
    assert cap.out == "" and "a failed every run" in cap.err
    assert evals_retry.main([str(tmp_path / "missing.json")]) == 2
    p.write_text("not json")
    assert evals_retry.main([str(p)]) == 2


FAKE = """#!/usr/bin/env python3
import json, sys
from pathlib import Path
base = Path(__file__).parent
with open(base / "calls.log", "a") as f:
    f.write(" ".join(sys.argv[1:]) + "\\n")
lines = (base / "queue.txt").read_text().splitlines()
head, rest = lines[0], lines[1:]
(base / "queue.txt").write_text("\\n".join(rest) + ("\\n" if rest else ""))
code, _, payload = head.partition("|")
if payload:
    out = sys.argv[sys.argv.index("--json") + 1]
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(payload)
sys.exit(int(code))
"""

DIS = json.dumps(result([case("ai-asks-once", 0.5, [True, False])]))
ALL = json.dumps(result([case("ai-asks-once", 0.0, [False, False])]))


def run_sh(tmp_path, queue):
    (tmp_path / "scripts").mkdir()
    for n in ("evals.sh", "evals_retry.py"):
        shutil.copy(ROOT / "scripts" / n, tmp_path / "scripts" / n)
    fake = tmp_path / "bin"
    fake.mkdir()
    (fake / "claude").write_text(FAKE)
    (fake / "claude").chmod(0o755)
    (fake / "queue.txt").write_text("\n".join(queue) + "\n")
    env = dict(os.environ, PATH=f"{fake}{os.pathsep}{os.environ['PATH']}")
    r = subprocess.run(["bash", str(tmp_path / "scripts/evals.sh"), "--runs", "1"], env=env,
                       capture_output=True, text=True, cwd=tmp_path)
    log = fake / "calls.log"
    calls = log.read_text().splitlines() if log.exists() else []
    return r, calls


def test_evals_sh_retries_once_and_turns_green(tmp_path):
    r, calls = run_sh(tmp_path, [f"1|{DIS}", "0"])
    assert r.returncode == 0, r.stderr
    assert len(calls) == 2
    assert "--runs 1 --case ai-asks-once --json evals/results/retry-ai-asks-once.json" in calls[1]
    assert "evals: retry once: ai-asks-once (its runs disagreed)" in r.stderr


def test_evals_sh_no_retry_paths(tmp_path):
    r, calls = run_sh(tmp_path / "a", [f"1|{ALL}"]) if (tmp_path / "a").mkdir() is None else None
    assert r.returncode == 1 and len(calls) == 1
    (tmp_path / "b").mkdir()
    r, calls = run_sh(tmp_path / "b", ["2"])
    assert r.returncode == 2 and len(calls) == 1
    (tmp_path / "c").mkdir()
    r, calls = run_sh(tmp_path / "c", [f"1|{DIS}", "1"])
    assert r.returncode == 1 and len(calls) == 2
    (tmp_path / "d").mkdir()
    (tmp_path / "d" / "evals" / "results").mkdir(parents=True)
    (tmp_path / "d" / "evals" / "results" / "last.json").write_text(DIS)
    r, calls = run_sh(tmp_path / "d", ["1"])
    assert r.returncode == 1 and len(calls) == 1
