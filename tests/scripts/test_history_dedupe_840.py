"""#840: history rows with an equal content key count once, and a rerun of record_run records nothing new."""
import importlib
import json
import sys

from test_metrics_history import HISTORY, _hist, _row, setup_run
from test_plan_tools import SCRIPTS, run
from test_routing import mech_plan

sys.path.insert(0, str(SCRIPTS))
import history  # noqa: E402
import predict  # noqa: E402


def row(task="T1", run_id="r1", dur=90.0, tin=100, tout=200, model="sonnet", day="2026-11-14", language="python", **kw):
    r = {"v": 1, "date": day, "run": run_id, "source": "run", "language": language, "task": task, "kind": "mechanical", "loc": 40,
         "components": 1, "tests": "fast", "band": "mechanical/le60/fast", "tier": "sonnet", "model": model, "duration_s": dur,
         "tokens": {"in": tin, "out": tout, "cache_read": 0, "cache_write": 0}, "cost_usd": 0.05, "first_time_pass": True, "pred_min": 1.5}
    r.update(kw)
    return r


def write(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows), encoding="utf-8")


def lines(path):
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def stub_runs(monkeypatch, *batches):
    calls = iter(batches)
    monkeypatch.setattr(history, "run_rows", lambda plan_path, sl_dir=".superlite", run_id=None: next(calls))


def run_dir(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("SUPERLITE_HOME", str(home))
    sl = tmp_path / ".superlite"
    sl.mkdir()
    return home, sl


def test_row_key_ignores_the_run_id_and_predictions():
    a = row(run_id="20261114-101500", pred_min=1.5, slack_min=0.0, critical_path=True)
    b = row(run_id="20261114-101742", pred_min=2.25, slack_min=3.0, critical_path=False, experiment="x", run_config="c")
    assert history.row_key(a) == history.row_key(b)
    for other in (row(task="T2"), row(dur=91.0), row(tin=101), row(tout=201), row(model="haiku"), row(day="2026-11-15"), row(language="swift")):
        assert history.row_key(other) != history.row_key(a)


def test_row_key_survives_odd_rows():
    keys = {history.row_key(r) for r in ({}, {"task": "T1", "tokens": None}, {"task": "T1", "tokens": [1, 2]}, {"task": "T1", "duration_s": {"x": 1}})}
    assert len(keys) == 3  # tokens None and tokens [1, 2] both give None in and out


def test_unique_rows_keeps_the_first_of_each_key_in_order():
    a1, b, a2, c = row("T1", "r1"), row("T2"), row("T1", "r2", pred_min=9.0), row("T3")
    assert history.unique_rows([a1, b, a2, c]) == [a1, b, c]
    assert history.unique_rows([]) == []


def test_record_run_twice_for_one_run_keeps_one_row(tmp_path, monkeypatch):
    home, sl = run_dir(tmp_path, monkeypatch)
    stub_runs(monkeypatch, [row("T1", "20261114-101500"), row("T2", "20261114-101500", dur=120.0)],
              [row("T1", "20261114-101742", pred_min=2.0), row("T2", "20261114-101742", dur=120.0, pred_min=3.0)])
    first = history.record_run("plan.md", sl)
    second = history.record_run("plan.md", sl)
    assert [r["task"] for r in first] == ["T1", "T2"] and second == []
    for f in (home / "history.jsonl", sl / "history.jsonl"):
        assert [(r["task"], r["run"]) for r in lines(f)] == [("T1", "20261114-101500"), ("T2", "20261114-101500")]
    for f in (home / "stats.json", sl / "stats.json"):
        assert json.loads(f.read_text(encoding="utf-8"))["rows"] == 2


def test_record_run_skips_a_task_its_run_already_recorded(tmp_path, monkeypatch):
    home, sl = run_dir(tmp_path, monkeypatch)
    stub_runs(monkeypatch, [row("T1", "r7")], [row("T1", "r7", dur=150.0), row("T2", "r7")])
    history.record_run("plan.md", sl, "r7")
    second = history.record_run("plan.md", sl, "r7")
    assert [r["task"] for r in second] == ["T2"]
    for f in (home / "history.jsonl", sl / "history.jsonl"):
        assert [(r["task"], r["duration_s"]) for r in lines(f)] == [("T1", 90.0), ("T2", 90.0)]


def test_another_repositorys_run_and_task_do_not_block(tmp_path, monkeypatch):
    home, sl = run_dir(tmp_path, monkeypatch)
    write(home / "history.jsonl", [row("T1", "20261114-101500", dur=300.0, language="go")])
    stub_runs(monkeypatch, [row("T1", "20261114-101500")])
    assert len(history.record_run("plan.md", sl)) == 1
    assert [(r["language"], r["duration_s"]) for r in lines(home / "history.jsonl")] == [("go", 300.0), ("python", 90.0)]
    assert len(lines(sl / "history.jsonl")) == 1


def test_a_row_the_global_file_holds_is_not_appended_there_again(tmp_path, monkeypatch):
    home, sl = run_dir(tmp_path, monkeypatch)
    write(home / "history.jsonl", [row("T1", "20261114-101500")])
    stub_runs(monkeypatch, [row("T1", "20261114-101742")])
    history.record_run("plan.md", sl)
    assert [r["run"] for r in lines(home / "history.jsonl")] == ["20261114-101500"]
    assert [r["run"] for r in lines(sl / "history.jsonl")] == ["20261114-101742"]


def test_duplicate_rows_give_the_same_stats_as_the_deduped_copy(tmp_path, monkeypatch):
    clean = [row("T1", "r1", dur=60.0), row("T2", "r1", dur=200.0, first_time_pass=False, tier="haiku", model="haiku"),
             row("T3", "r1", dur=95.0, band="design/le150/fast", kind="design", loc=120)]
    dup = clean[:2] + [dict(clean[0], run="r1b", pred_min=7.0), clean[2], dict(clean[1], run="r1b"), dict(clean[1], run="r1c")]
    write(tmp_path / "dup" / "history.jsonl", dup)
    write(tmp_path / "clean" / "history.jsonl", clean)
    assert history.read_rows(tmp_path / "dup" / "history.jsonl") == clean
    assert len(lines(tmp_path / "dup" / "history.jsonl")) == 6  # the file itself is not rewritten
    for name in ("dup", "clean"):
        monkeypatch.setenv("SUPERLITE_HOME", str(tmp_path / name))
        cp = run(HISTORY, "derive", cwd=tmp_path)
        assert cp.returncode == 0, cp.both
    stats = [{k: v for k, v in json.loads((tmp_path / n / "stats.json").read_text(encoding="utf-8")).items() if k != "updated"} for n in ("dup", "clean")]
    assert stats[0] == stats[1] and stats[0]["rows"] == 3


def test_the_predictor_counts_a_duplicated_row_once(tmp_path, monkeypatch):
    importlib.reload(predict)
    home = tmp_path / "home"
    monkeypatch.setenv("SUPERLITE_HOME", str(home))
    monkeypatch.setenv("SUPERLITE_HISTORY_MIN", "31")
    shipped = predict.load_coef()
    rows = [_row(i, dur=60.0 + i, loc=40 + 10 * (i % 8)) for i in range(30)]
    _hist(home, rows + [dict(r, run=r["run"] + "b") for r in rows])
    assert predict.load_coef() == shipped  # 30 distinct rows, under the 31-row minimum: no refit
    _hist(home, rows + [_row(30, dur=95.0, loc=70)] + [dict(r, run=r["run"] + "b") for r in rows])
    assert predict.load_coef()["fit"]["n"] == 31


def test_history_write_twice_for_one_run_appends_once(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("SUPERLITE_HOME", str(home))
    p = mech_plan(tmp_path, 2)
    setup_run(tmp_path)
    sl = tmp_path / ".superlite"
    first = run(HISTORY, "write", "--plan", p, "--dir", sl, "--run", "20261114-101500", cwd=tmp_path)
    assert first.returncode == 0, first.both
    assert "history: 3 rows appended" in first.out
    second = run(HISTORY, "write", "--plan", p, "--dir", sl, "--run", "20261114-101742", cwd=tmp_path)
    assert second.returncode == 0, second.both
    assert "history: 0 rows appended" in second.out
    assert len(lines(home / "history.jsonl")) == 3 and len(lines(sl / "history.jsonl")) == 3
