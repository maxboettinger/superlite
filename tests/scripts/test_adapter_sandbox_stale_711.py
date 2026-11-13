"""#711: an adapter generated before the run= sandbox is rebuilt by lint and refused by probe_run."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills" / "subagent-driven-development" / "scripts"
PROBE_RUN = ROOT / "skills" / "subagent-driven-development" / "probes" / "probe_run.py"
sys.path.insert(0, str(SCRIPTS))

import plan_tools  # noqa: E402
import pt_review  # noqa: E402

_spec = importlib.util.spec_from_file_location("probe_run_stale_711", PROBE_RUN)
pr = importlib.util.module_from_spec(_spec)
sys.modules["probe_run_stale_711"] = pr
_spec.loader.exec_module(pr)

REL = ".superlite/probes/adapter.py"
WHY = "the adapter's run= predates the sandbox"
REFUSED = "probe_run: adapter's run= predates the sandbox; rebuild with plan_tools adapter"


def built(root: Path, entry: str) -> tuple[Path, Path]:
    plan = root / "plan.md"
    plan.write_text(f"# p\n\n**Probe entry:** {entry}\n", encoding="utf-8")
    assert pt_review.main(["adapter", "--plan", str(plan), "--root", str(root)]) == 0
    return plan, root / REL


def aged(adapter: Path) -> None:
    adapter.write_text(adapter.read_text(encoding="utf-8").replace("SANDBOX_DROP", "OLD_DROP"), encoding="utf-8")


def test_old_run_adapter_is_rebuilt(tmp_path):
    plan, adapter = built(tmp_path, "run=python -m tool")
    aged(adapter)
    assert plan_tools.refresh_adapter(str(plan)) == f"ADAPTER: rebuilt {REL} ({WHY})"
    assert "SANDBOX_DROP" in adapter.read_text(encoding="utf-8")
    assert plan_tools.refresh_adapter(str(plan)) == ""


def test_plain_lint_names_the_rebuild(tmp_path):
    plan, adapter = built(tmp_path, "run=python -m tool")
    aged(adapter)
    line = plan_tools.refresh_adapter(str(plan), write=False)
    assert line.startswith("RUN: ") and line.endswith(f"(the probe adapter is stale: {WHY})")
    assert "OLD_DROP" in adapter.read_text(encoding="utf-8")


def test_call_only_adapter_stays_quiet(tmp_path):
    plan, adapter = built(tmp_path, "call=a.parse")
    assert "SANDBOX_DROP" not in adapter.read_text(encoding="utf-8")
    assert plan_tools.refresh_adapter(str(plan)) == ""


def test_unsandboxed_adapter_detection(tmp_path):
    _, adapter = built(tmp_path, "run=python -m tool")
    assert pr.unsandboxed_adapter(adapter) is False
    aged(adapter)
    assert pr.unsandboxed_adapter(adapter) is True
    hand = tmp_path / "hand.py"
    hand.write_text("def run(args, stdin):\n    return 0, '', ''\n", encoding="utf-8")
    assert pr.unsandboxed_adapter(hand) is False
    assert pr.unsandboxed_adapter(tmp_path / "missing.py") is False


def test_probe_run_refuses_an_unsandboxed_adapter(tmp_path):
    _, adapter = built(tmp_path, "run=python -m tool")
    aged(adapter)
    p = subprocess.run([sys.executable, str(PROBE_RUN), "--adapter", str(adapter), "--root", str(tmp_path)],
                       capture_output=True, text=True, timeout=120)
    assert p.returncode == 2 and REFUSED in p.stderr
