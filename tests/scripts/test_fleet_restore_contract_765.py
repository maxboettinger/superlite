# tests/scripts/test_fleet_restore_contract_765.py
# fleet restore's continue prompt ends with the worker's own report contract (fleet_io.report_contract), so a busy batch
# implementer is asked for its red run per task id (WORK_BATCH), not the single `red` string (#765).
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"))
import fleet_report  # noqa: E402
import fleet_restore as fr  # noqa: E402
from test_fleet_restore_577 import idle_agent, w, worker  # noqa: E402,F401

ROOT = Path(__file__).resolve().parents[2]
TOOLS = (ROOT / "docs/tools.md").read_text(encoding="utf-8")


def prompt_of(w, name="sl-a-w1"):
    return next(c for c in w.fake.calls if c[0] == "prompt" and c[1] == name)[2]


def test_batch_implementer_continue_asks_red_per_task(w):
    w.save({"W1": worker(task="T5,T6")})
    w.fake.agents = [idle_agent()]
    w.run()
    assert prompt_of(w) == fr.CONTINUE + "\n\n" + fleet_report.WORK_BATCH


def test_single_task_implementer_keeps_work(w):
    w.fake.agents = [idle_agent()]
    w.run()
    assert prompt_of(w) == fr.CONTINUE + "\n\n" + fleet_report.WORK


def test_final_reviewer_continue_keeps_review(w):
    w.save({"W1": worker(role="final-reviewer", agent="superlite:final-reviewer", task="FR1")})
    w.fake.agents = [idle_agent()]
    w.run()
    assert prompt_of(w) == fr.CONTINUE + "\n\n" + fleet_report.REVIEW


def row(name):
    return next(l for l in TOOLS.splitlines() if l.startswith(f"| `{name}` |"))


def test_tools_md_names_reds_and_work_batch():
    r = row("fleet_io")
    for s in ("`reds`", "`Red run Tn:`", "WORK_BATCH", "report_contract"):
        assert s in r, s


def test_tools_md_names_also_edit():
    for name in ("task", "fleet_io"):
        assert "`Also edit:" in row(name), name


def test_tools_md_restore_names_report_contract():
    assert "report contract" in row("fleet").split("restore [--plan P]", 1)[1]
