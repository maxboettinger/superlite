"""#177 / #180: a stale adapter never lingers or runs, an arity error is a setup error, the packet names truncated files."""
from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SDD = ROOT / "skills" / "subagent-driven-development"
PROBE_RUN = SDD / "probes" / "probe_run.py"
_spec = importlib.util.spec_from_file_location("pt_review_adapter_packet", SDD / "scripts" / "pt_review.py")
pt = importlib.util.module_from_spec(_spec)
sys.modules["pt_review_adapter_packet"] = pt
_spec.loader.exec_module(pt)

STALE = "probe_run: adapter is stale (plan entry changed); rebuild with plan_tools adapter"
ONE_ARG = "def f(text):\n    return text.upper()\n\n\ndef g(text):\n    return text.lower()\n"


def project(tmp_path: Path, source: str = ONE_ARG) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text(source, encoding="utf-8")
    return tmp_path


def plan_with(root: Path, entry: str) -> Path:
    p = root / "plan.md"
    p.write_text(f"# p\n\n**Probe entry:** {entry}\n", encoding="utf-8")
    return p


def build_adapter(root: Path, plan: Path) -> Path:
    assert pt.main(["adapter", "--plan", str(plan), "--root", str(root)]) == 0
    return root / ".superlite" / "probes" / "adapter.py"


def probe_run(root: Path, adapter: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(PROBE_RUN), "--adapter", str(adapter), "--root", str(root), *extra],
                          capture_output=True, text=True, timeout=300)


def results(root: Path) -> dict:
    return json.loads((root / ".superlite" / "probes" / "probe-results.json").read_text(encoding="utf-8"))


# ----------------------------------------------------------------------------- adapter and probe_run


def test_adapter_removed_when_entry_none(tmp_path, capsys):
    root = project(tmp_path)
    adapter = build_adapter(root, plan_with(root, "call=a.f"))
    assert adapter.is_file()
    capsys.readouterr()
    plan_with(root, "none")
    assert pt.main(["adapter", "--plan", str(root / "plan.md"), "--root", str(root)]) == 0
    assert not adapter.exists()
    assert "adapter: no Probe entry lines; removed stale adapter.py" in capsys.readouterr().out


def test_adapter_kept_when_not_generated(tmp_path, capsys):
    """Only a file this tool wrote is removed: a hand-written adapter at the same path stays."""
    root = project(tmp_path)
    mine = root / ".superlite" / "probes" / "adapter.py"
    mine.parent.mkdir(parents=True)
    mine.write_text("def call(text):\n    return text\n", encoding="utf-8")
    assert pt.main(["adapter", "--plan", str(plan_with(root, "none")), "--root", str(root)]) == 0
    assert mine.is_file() and "adapter: no Probe entry lines; probes skipped" in capsys.readouterr().out


def test_probe_run_refuses_mismatched_adapter(tmp_path):
    root = project(tmp_path)
    plan = plan_with(root, "call=a.f")
    adapter = build_adapter(root, plan)
    plan_with(root, "call=a.g")  # the plan's entry changed after the adapter was built
    p = probe_run(root, adapter, "--categories", "deep")
    assert p.returncode == 2 and STALE in p.stderr + p.stdout
    assert not (root / ".superlite" / "probes" / "probe-results.json").exists()  # nothing ran
    build_adapter(root, plan)  # rebuilt: the same plan now matches
    p = probe_run(root, adapter, "--categories", "deep")
    assert STALE not in p.stderr + p.stdout and results(root)["probes"]


def test_probe_run_without_a_recorded_plan_runs_as_before(tmp_path):
    """A hand-written adapter (no ENTRIES, no PLAN) is never judged stale."""
    root = project(tmp_path)
    adapter = root / "adapter.py"
    adapter.write_text("def call(text):\n    return text\n", encoding="utf-8")
    p = probe_run(root, adapter, "--categories", "deep")
    assert STALE not in p.stderr + p.stdout and results(root)["probes"]


def test_arity_error_is_setup_error(tmp_path):
    root = project(tmp_path, "def f(text, b, c):\n    return text\n")
    adapter = build_adapter(root, plan_with(root, "call=a.f"))
    p = probe_run(root, adapter, "--categories", "deep,encoding")
    probes = results(root)["probes"]
    assert probes and {x["status"] for x in probes} == {"setup-error"}, p.stdout + p.stderr
    assert not any(x["status"] == "crash" for x in probes)
    failures = results(root)["failures"]
    assert len(failures) == 1 and failures[0]["kind"] == "setup-error" and failures[0]["regression_test"] is None
    assert "a.f" in failures[0]["detail"] and "required" in failures[0]["detail"]
    assert not (root / "tests" / "regression").exists()  # no regression test for a setup error
    assert p.returncode == 1  # still a failure the reviewer sees


def test_one_argument_target_still_runs(tmp_path):
    root = project(tmp_path)
    adapter = build_adapter(root, plan_with(root, "call=a.f"))
    probe_run(root, adapter, "--categories", "deep")
    assert "setup-error" not in {x["status"] for x in results(root)["probes"]}


# ----------------------------------------------------------------------------- packet and final reviewer


def test_packet_names_truncated_paths():
    lines = [f"+line {i}" for i in range(300)]
    out = pt.render_excerpts(["src/a.py", "src/b.py"], [("src/a.py", lines), ("src/b.py", lines[:5])], per_file=50)
    assert re.search(r"\(truncated: 50 of 300 diff lines shown, per-file cap; read src/a\.py in full\)", out), out
    assert "src/b.py in full" not in out  # a file shown whole needs no note
    out = pt.render_excerpts(["src/a.py"], [("src/a.py", lines)], per_file=200, budget=1200, floor=10)
    assert re.search(r"\(truncated: \d+ of 300 diff lines shown, size cap; read src/a\.py in full\)", out), out


def test_packet_section_8_names_the_path(tmp_path):
    root = project(tmp_path, "".join(f"old {i}\n" for i in range(3)))
    git = lambda *a: subprocess.run(["git", "-C", str(root), "-c", "user.email=t@t", "-c", "user.name=t", *a], capture_output=True, text=True, check=True)
    (root / ".superlite").mkdir()
    plan = plan_with(root, "none")
    git("init", "-q"); git("add", "-A"); git("commit", "-qm", "base")
    (root / "src" / "a.py").write_text("".join(f"new {i}\n" for i in range(300)), encoding="utf-8")
    out = root / "packet.md"
    assert pt.main(["packet", "--plan", str(plan), "--root", str(root), "--out", str(out), "--max-tokens", "500000"]) == 0
    sec = out.read_text(encoding="utf-8").split("## 8.", 1)[1]
    assert "per-file cap; read src/a.py in full)" in sec


def test_final_reviewer_may_read_truncated():
    text = (ROOT / "agents" / "final-reviewer.md").read_text(encoding="utf-8")
    assert "read <path> in full" in text and "truncated" in text
    assert "may read" in text and "nothing else" in text  # that file only, still nothing else
    assert "tools: Read, Grep, Glob" in text  # the reviewer stays read-only
