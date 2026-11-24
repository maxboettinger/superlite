# tests/scripts/test_build_prime_plan_folder_1116.py: build_prime writes the plan's run folder, not the cwd (#1116)
import json, sys
import pytest
from test_plan_tools import SCRIPTS, make_plan
sys.path.insert(0, str(SCRIPTS))
import build_prime  # noqa: E402


@pytest.fixture
def env(tmp_path, monkeypatch):
    proj = tmp_path / "proj"
    (proj / ".git").mkdir(parents=True)
    plan = make_plan(proj, [{"id": "T1", "owns": "src/a.py"}])
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.delenv("SUPERLITE_STATE_DIR", raising=False)
    monkeypatch.chdir(elsewhere)
    return tmp_path, proj, plan, elsewhere


def test_default_out_is_the_plan_folder_not_the_cwd(env):
    tmp, proj, plan, elsewhere = env
    assert build_prime.main(["--plan", str(plan)]) == 0
    assert (proj / ".superlite" / "prime.md").is_file()
    assert not (elsewhere / ".superlite").exists()


def test_explicit_out_still_wins(env):
    tmp, proj, plan, elsewhere = env
    out = tmp / "x" / "prime.md"
    assert build_prime.main(["--plan", str(plan), "--out", str(out)]) == 0
    assert out.is_file()
    assert not (proj / ".superlite" / "prime.md").exists()


def test_haiku_default_goes_to_the_plan_folder(env):
    tmp, proj, plan, elsewhere = env
    assert build_prime.main(["--plan", str(plan), "--tier", "haiku"]) == 0
    assert (proj / ".superlite" / "prime-haiku.md").is_file()
    assert not (elsewhere / ".superlite").exists()


def test_run_folder_plan_writes_into_that_folder(env):
    tmp, proj, plan, elsewhere = env
    sd = proj / ".superlite"
    sd.mkdir(exist_ok=True)
    (sd / "stable.json").write_text(json.dumps({"plan": str(plan.resolve())}))
    assert build_prime.main(["--plan", str(sd)]) == 0
    assert (sd / "prime.md").is_file()
