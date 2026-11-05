"""F-T11-4 / F-T11-5: resume resets ship_runs; start and answer refuse inside a fleet worker."""
from test_backlog_run import bk, put, get, run, b  # noqa: F401


def test_start_resume_resets_ship_runs(bk, capsys):
    put(bk, b("B1", ["a.py"], "parked", reason="x", ship_runs=5))
    assert run(capsys, "start", "B1")[0] == 0
    assert get(bk, "B1")["ship_runs"] == 0


def test_start_and_answer_refuse_in_a_fleet_worker(bk, capsys, monkeypatch, tmp_path):
    monkeypatch.setenv("SUPERLITE_FLEET_WORKER", "W1")
    put(bk, b("B1", ["a.py"]))
    f = tmp_path / "a.json"; f.write_text("{}")
    assert run(capsys, "start")[0] == 2 and not any(c[0] == "spawn" for c in bk.calls)
    assert run(capsys, "answer", "B1", "--file", str(f))[0] == 2
    assert get(bk, "B1")["state"] == "planned"
