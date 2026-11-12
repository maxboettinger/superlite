"""fleet.py CLI: --help lists every subcommand (#387), fleet report (#376), an unusable --plan exits 2 (#372)."""
import re
import json, os, sys
import pytest
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import fleet  # noqa: E402

SUBS = ("on", "off", "status", "spawn", "stop", "name", "report", "send", "keys", "wait", "run", "restore")
HINT = "; pass the plan file or the run's .superlite folder, or leave --plan out to use the current directory's run"


def test_help_lists_every_subcommand(capsys):
    with pytest.raises(SystemExit) as e:
        fleet.main(["--help"])
    out = capsys.readouterr().out
    assert e.value.code == 0
    choices = re.search(r"\{([a-z,]+)\}", out).group(1)
    assert set(choices.split(",")) == set(SUBS)
    for s in SUBS:
        assert any(x.split()[:1] == [s] and len(x.split()) > 1 for x in out.splitlines()), s


@pytest.fixture
def run(tmp_path):
    sd = (tmp_path / ".superlite").resolve(); (sd / "fleet" / "reports").mkdir(parents=True)
    (sd / "fleet.json").write_text(json.dumps({"on": True, "label": "sl:x", "workspace_id": None, "root_pane": None, "accounts": [], "next": 6,
        "workers": {"W1": {"state": "ready", "task": None, "last_task": "T3,T4"}, "W2": {"state": "busy", "task": "T5", "last_task": "T1"},
                    "W3": {"state": "stopped", "task": None, "last_task": "layer-headless"}, "W4": {"state": "ready", "task": None},
                    "W5": {"state": "stopped", "task": None, "last_task": "T9"}}}))
    (sd / "fleet" / "reports" / "T3.md").write_text("Status: DONE\nchanged src/c.py\n")
    (sd / "fleet" / "reports" / "FR1.md").write_text("Verdict: APPROVED")
    (sd / "fleet" / "reports" / "layer-headless.json").write_text('{"status": "GREEN"}\n')
    return sd


def test_report_prints_the_workers_last_report(run, capsys):
    before = (run / "fleet.json").read_text()
    assert fleet.main(["report", "W1", "--plan", str(run)]) == 0
    assert capsys.readouterr().out == "Status: DONE\nchanged src/c.py\n"
    assert (run / "fleet.json").read_text() == before


def test_report_by_label_and_json_fallback(run, capsys):
    assert fleet.main(["report", "FR1", "W3", "--plan", str(run)]) == 0
    r = run / "fleet" / "reports"
    assert capsys.readouterr().out == f"== FR1 {r / 'FR1.md'}\nVerdict: APPROVED\n== W3 {r / 'layer-headless.json'}\n{{\"status\": \"GREEN\"}}\n"


def test_report_busy_unknown_and_missing(run, capsys):
    assert fleet.main(["report", "W2", "W9", "W4", "W5", "W1", "--plan", str(run)]) == 1
    cap = capsys.readouterr()
    for s in ("error: W2 is busy on T5; run sl fleet wait W2 first", "error: unknown worker or report label W9",
              "error: W4 has no collected report; run sl fleet wait W4 first", f"error: W5 T9: no report file in {run / 'fleet' / 'reports'}"):
        assert s in cap.err, s
    assert cap.out == f"== W1 {run / 'fleet' / 'reports' / 'T3.md'}\nStatus: DONE\nchanged src/c.py\n"


@pytest.mark.parametrize("argv", [["spawn", "--role", "research", "--plan", "/dev/null"], ["on", "--plan", "/dev/null"],
                                  ["wait", "--plan=/dev/null"], ["report", "W1", "--plan", "/dev/null"], ["run", "--layer", "tui", "--plan", "/dev/null"]])
def test_plan_that_is_no_file_or_folder_exits_2(argv, capsys):
    assert fleet.main(argv) == 2
    assert capsys.readouterr().err == "error: --plan /dev/null: not a plan file or folder" + HINT + "\n"


@pytest.mark.skipif(getattr(os, "geteuid", lambda: 1)() == 0, reason="root writes everywhere")
def test_plan_whose_state_folder_cannot_be_created_exits_2(tmp_path, capsys):
    ro = tmp_path / "ro"; ro.mkdir(); ro.chmod(0o555)
    try:
        assert fleet.main(["on", "--plan", str(ro / "plan.md")]) == 2
    finally:
        ro.chmod(0o755)
    assert capsys.readouterr().err == f"error: --plan {ro / 'plan.md'}: cannot create {(ro / '.superlite').resolve()}" + HINT + "\n"
    assert not (ro / ".superlite").exists()


def test_new_plan_file_in_a_writable_folder_passes_the_check(tmp_path, capsys):
    assert fleet.main(["status", "--plan", str(tmp_path / "docs" / "new-plan.md")]) == 0
    assert capsys.readouterr().out == "fleet: off\n"


def test_spawn_without_plan_uses_the_current_directorys_run(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("SUPERLITE_STATE_DIR", raising=False)
    monkeypatch.setattr(fleet.state, "bound", lambda: None)
    monkeypatch.setattr(fleet.state, "session_id", lambda: "")
    monkeypatch.chdir(tmp_path)
    assert fleet.main(["spawn", "--role", "research"]) == 3
    assert capsys.readouterr().out.startswith(f"BLOCKED: fleet is off in {(tmp_path / '.superlite').resolve()}; run sl fleet on first")


def test_report_blocked_worker_names_its_screen_not_an_older_report(run, capsys):
    data = json.loads((run / "fleet.json").read_text(encoding="utf-8"))
    data["workers"]["W1"].update({"state": "blocked", "task": "T7"})
    (run / "fleet.json").write_text(json.dumps(data), encoding="utf-8")
    assert fleet.main(["report", "W1", "--plan", str(run)]) == 1
    cap = capsys.readouterr()
    assert cap.out == ""
    assert cap.err == f"error: W1 is blocked on T7 (BLOCKED-UI); screen: {run / 'fleet' / 'screens' / 'W1.txt'}\n"


def test_last_plan_flag_wins_like_argparse(capsys):
    assert fleet._plan_arg(["status", "--plan", "/a", "--plan=/b"]) == "/b"
    assert fleet._plan_arg(["status", "--plan=/a", "--plan", "/b"]) == "/b"
    assert fleet.main(["status", "--plan", "/dev/null", "--plan", "/dev/null"]) == 2
