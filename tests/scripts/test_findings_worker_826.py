"""#826: a fixer brief's plain Verify line names run_tests --worker fix-<first finding id>."""
import json
import sys
from pathlib import Path
from test_plan_tools import SCRIPTS, make_plan
sys.path.insert(0, str(SCRIPTS))
import findings  # noqa: E402
from test_findings_route import put  # noqa: E402

TAIL = ", then run the printed `wait:` line in the foreground (never as a background command) and end your turn only after it reports."


def test_worker_name():
    assert findings.worker_name("F-T1-1") == "fix-F-T1-1"
    assert findings.worker_name("F-UI3a-2") == "fix-F-UI3a-2"
    assert findings.worker_name("F-T1.2-3") == "fix-F-T1-2-3"
    assert len(findings.worker_name("F-" + "T" * 80 + "-1")) == 64


def test_plain_line_names_worker():
    lines = findings.shared_lines("/sl/sl", worker="fix-F-T1-1")
    assert "Verify: `/sl/sl run_tests --fast <the test files you touched> --worker fix-F-T1-1 --background`" + TAIL in lines


def test_no_worker_keeps_old_line():
    assert "Verify: `/sl/sl run_tests --fast <the test files you touched> --background`" + TAIL in findings.shared_lines("/sl/sl")


def test_cmd_line_has_no_worker():
    text = "\n".join(findings.shared_lines("/sl/sl", "T1", Path("/p/plan.md"), "bash t.sh", worker="fix-F-T1-1"))
    assert "--task T1 --plan /p/plan.md --background" in text and "--worker" not in text


def test_routed_brief_names_its_worker(tmp_path):
    root = tmp_path / "repo"; sd = root / ".superlite"; (sd / "fleet" / "reports").mkdir(parents=True)
    plan = make_plan(sd, [{"id": "T2", "owns": "src/b.py", "tests": "fast"}], name="plan.md")
    put(root, "src/b.py", 3, "code at 3")
    item = {"file": "src/b.py", "line": 3, "problem": "p", "fix": "x", "tier": 1, "quote": "code at 3"}
    rep = sd / "fleet" / "reports" / "FR1.json"
    rep.write_text(json.dumps({"id": "W4", "label": "FR1", "status": "CHANGES_REQUESTED", "findings": [item], "valid": True}))
    findings.route(sd, plan, [str(rep)], "/sl/sl")
    assert "--worker fix-F-T2-1 --background`" in (sd / "briefs" / "fix-F-T2-1.md").read_text()
