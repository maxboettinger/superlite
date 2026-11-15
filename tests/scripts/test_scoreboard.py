# tests/scripts/test_scoreboard.py
import json
import sys

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import scoreboard as sb  # noqa: E402


def row(n, lead=3.0, workers=1.0, turns=60, points=1, tasks=4, first=4, letter="A", end="shipped"):
    return {"row": "batch", "batch": f"B{n}", "end": end, "lead": {"cost_usd": lead, "turns": turns},
            "workers_total": {"cost_usd": workers},
            "grade": {"points": points, "tasks": tasks, "first_time_pass": first, "letter": letter}}


def rows30(**kw_now):
    return [row(i) for i in range(15)] + [row(i + 15, **kw_now) for i in range(15)]


def test_metrics_example():
    r = {"lead": {"cost_usd": 3.0, "turns": 60}, "workers_total": {"cost_usd": 1.0},
         "grade": {"points": 2, "tasks": 4, "first_time_pass": 3, "letter": "B"}}
    assert sb.metrics(r) == {"lead_usd": 3.0, "total_usd": 4.0, "lead_turns": 60, "points": 2, "first_pass": 0.75}


def test_zero_tasks_first_pass_none():
    assert sb.metrics(row(1, tasks=0, first=0))["first_pass"] is None
    rs = [row(i, tasks=0, first=0) for i in range(15)] + [row(i + 15, first=4) for i in range(15)]
    assert "first_pass" not in sb.board(rs)["metrics"]
    assert sb.board(rs)["flags"] == []


def test_malformed_row_skipped():
    rs = rows30()
    rs.insert(3, {"row": "batch", "batch": "BX", "end": "shipped"})
    assert sb.board(rs)["now"] == 15 and sb.board(rs)["baseline"] == 15


def test_latest_shipped_only():
    rs = [row(1, end="parked"), row(1), row(2, end="parked")]
    b = sb.board(rs)
    assert b["now"] == 1 and b["baseline"] == 0


def test_empty():
    assert sb.board([]) == {"enough": False, "window": 15, "now": 0, "baseline": 0, "metrics": {}, "flags": [], "outliers": []}


def test_not_enough():
    b = sb.board([row(i) for i in range(20)])
    assert b["enough"] is False and b["flags"] == []


def test_cost_flag():
    rs = [row(i, lead=4.0) for i in range(15)] + [row(i + 15, lead=6.0) for i in range(15)]
    b = sb.board(rs)
    assert b["flags"] == ["lead_usd +50% (4.00 -> 6.00)", "total_usd +40% (5.00 -> 7.00)"]
    assert b["enough"] is True


def test_cost_flag_only_lead():
    rs = [row(i, lead=4.0, workers=10) for i in range(15)] + [row(i + 15, lead=6.0, workers=8) for i in range(15)]
    assert sb.board(rs)["flags"] == ["lead_usd +50% (4.00 -> 6.00)"]


def test_no_flag_within_30pct():
    rs = [row(i, lead=4.0, workers=10) for i in range(15)] + [row(i + 15, lead=5.0, workers=10) for i in range(15)]
    assert sb.board(rs)["flags"] == []


def test_points_flag_abs():
    mk = lambda p: [row(i, points=1.0) for i in range(15)] + [row(i + 15, points=p) for i in range(15)]
    assert sb.board(mk(3.5))["flags"] == ["points +2.5 (1.0 -> 3.5)"]
    assert sb.board(mk(2.5))["flags"] == []


def test_first_pass_flag():
    rs = [row(i, tasks=10, first=9) for i in range(15)] + [row(i + 15, tasks=4, first=3) for i in range(15)]
    assert sb.board(rs)["flags"] == ["first_pass -0.15 (0.90 -> 0.75)"]


def test_outlier_letter_d():
    rs = rows30()
    rs[20] = row(7, letter="D")
    assert "B7 grade D" in sb.board(rs)["outliers"]


def test_outlier_cost():
    rs = [row(i, lead=3.0, workers=1.0) for i in range(15)] + [row(i + 15) for i in range(15)]
    rs[-1] = row(9, lead=10.0, workers=5.0)
    assert "B9 cost 15.00 (3x median 4.00)" in sb.board(rs)["outliers"]


def seed(tmp_path, rows):
    (tmp_path / ".superlite").mkdir()
    (tmp_path / ".superlite" / "batch-costs.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")


def test_cli_exit(tmp_path, capsys):
    seed(tmp_path, [row(i, lead=4.0) for i in range(15)] + [row(i + 15, lead=6.0) for i in range(15)])
    assert sb.main(["--root", str(tmp_path)]) == 1
    assert "FLAG lead_usd +50% (4.00 -> 6.00)" in capsys.readouterr().out
    assert sb.main(["--root", str(tmp_path), "--json"]) == 1
    assert json.loads(capsys.readouterr().out)["flags"]
    seed2 = tmp_path / "b"
    seed2.mkdir()
    seed(seed2, rows30())
    assert sb.main(["--root", str(seed2)]) == 0


def test_unknown_root_exit_0(tmp_path, capsys):
    assert sb.main(["--root", str(tmp_path)]) == 0
    assert capsys.readouterr().out.strip() == "scoreboard: no batch rows"


def test_outside_git_repository_no_traceback(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert sb.main([]) == 2
    assert sb.main(["--root", ""]) == 2
    assert "not in a git repository" in capsys.readouterr().err
