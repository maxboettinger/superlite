"""predict.load_coef: a per-language time scale learned from history (#10).

The scale is the median of actual / predicted minutes over the history rows of the project's language, with the
prediction recomputed from each row's features (never the stored pred_min, which already carries a scale). It applies
only from LANG_MIN_ROWS rows of that language and is clamped to LANG_CLAMP."""
from __future__ import annotations

import json
import sys

import pytest

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import predict  # noqa: E402


def write_history(home, language, n, ratio, model="sonnet"):
    models, coef = predict.load_models(), predict.load_coef(predict.CONFIG_DIR / "predictor.json")
    rows = []
    for i in range(n):
        loc = 40 + 10 * i
        pred = predict.time_from({"components": 1, "loc": loc, "tests": "fast"}, model, models, coef)
        rows.append({"v": 1, "language": language, "task": f"T{i}", "loc": loc, "components": 1, "tests": "fast", "model": model,
                     "duration_s": round(pred * ratio * 60, 3), "pred_min": 99.0})
    home.mkdir(parents=True, exist_ok=True)
    with (home / "history.jsonl").open("a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")


@pytest.fixture
def swift_project(tmp_path, monkeypatch):
    root = tmp_path / "app"
    (root / ".superlite").mkdir(parents=True)
    (root / "App.xcodeproj").mkdir()
    monkeypatch.chdir(root)
    monkeypatch.setenv("SUPERLITE_HISTORY_MIN", "100000")  # keep the global refit out: the shipped coefficients stay the base
    return root


def home(tmp_path):
    return tmp_path / "_sl_home"  # conftest points SUPERLITE_HOME here


def scale(coef):
    return coef["time"].get("language_scale")


def test_enough_rows_of_the_project_language_scale_its_time(tmp_path, swift_project):
    write_history(home(tmp_path), "swift", predict.LANG_MIN_ROWS, 2.5)
    coef = predict.load_coef()
    assert scale(coef) == pytest.approx(2.5, abs=0.01)
    assert coef["language"] == {"name": "swift", "rows": predict.LANG_MIN_ROWS, "scale": scale(coef)}
    base = predict.load_coef(predict.CONFIG_DIR / "predictor.json")
    feats, models = {"components": 2, "loc": 120, "tests": "fast"}, predict.load_models()
    assert predict.time_from(feats, "sonnet", models, coef) == pytest.approx(2.5 * predict.time_from(feats, "sonnet", models, base), rel=0.01)


def test_too_few_rows_leave_the_time_unscaled(tmp_path, swift_project):
    write_history(home(tmp_path), "swift", predict.LANG_MIN_ROWS - 1, 2.5)
    assert scale(predict.load_coef()) is None


def test_other_languages_rows_do_not_scale_this_project(tmp_path, swift_project):
    write_history(home(tmp_path), "javascript", predict.LANG_MIN_ROWS, 2.5)
    write_history(home(tmp_path), "unknown", predict.LANG_MIN_ROWS, 2.5)
    assert scale(predict.load_coef()) is None


def test_the_scale_is_clamped(tmp_path, swift_project):
    write_history(home(tmp_path), "swift", predict.LANG_MIN_ROWS, 10.0)
    assert scale(predict.load_coef()) == predict.LANG_CLAMP[1]


def test_an_explicit_coef_file_has_no_scale(tmp_path, swift_project):
    write_history(home(tmp_path), "swift", predict.LANG_MIN_ROWS, 2.5)
    assert scale(predict.load_coef(predict.CONFIG_DIR / "predictor.json")) is None


def test_the_plan_forecast_names_the_scale_and_a_refit_never_stores_it(tmp_path, swift_project):
    write_history(home(tmp_path), "swift", predict.LANG_MIN_ROWS, 2.5)
    coef = predict.load_coef()

    class Plan:
        tasks = []
    assert predict.predict_plan(Plan(), predict.load_models(), coef)["language"]["name"] == "swift"
    obs = [{"components": 1.0, "loc": 50.0 * i, "slow": False, "model": "sonnet", "actual": 3.0 * i, "overhead": None} for i in range(1, 6)]
    new, _ = predict.refit(obs, predict.load_models(), coef)
    assert "language" not in new and "language_scale" not in new["time"]
