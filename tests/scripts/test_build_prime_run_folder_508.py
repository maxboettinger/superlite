# tests/scripts/test_build_prime_run_folder_508.py: build_prime --plan accepts the run folder (#508)
import json, shutil, sys
import pytest
from test_plan_tools import SCRIPTS, make_plan
sys.path.insert(0, str(SCRIPTS))
import build_prime  # noqa: E402


@pytest.fixture
def proj(tmp_path, monkeypatch):
    p = tmp_path / "proj"
    (p / ".superlite").mkdir(parents=True)
    monkeypatch.delenv("SUPERLITE_STATE_DIR", raising=False)
    monkeypatch.chdir(p)
    return p, p / ".superlite", make_plan(p, [{"id": "T1", "owns": "src/a.py"}])


def test_run_folder_uses_stable_plan(proj, tmp_path):
    p, sd, plan = proj
    (sd / "stable.json").write_text(json.dumps({"plan": str(plan.resolve())}))
    o1, o2 = tmp_path / "o1.md", tmp_path / "o2.md"
    assert build_prime.main(["--plan", str(sd), "--out", str(o1)]) == 0
    assert build_prime.main(["--plan", str(plan), "--out", str(o2)]) == 0
    assert o1.read_bytes() == o2.read_bytes()


def test_run_folder_uses_plan_md(proj, tmp_path):
    p, sd, plan = proj
    shutil.copy(plan, sd / "plan.md")
    o1 = tmp_path / "o1.md"
    assert build_prime.main(["--plan", str(sd), "--out", str(o1)]) == 0
    assert o1.is_file()


def test_run_folder_without_plan_exits_2(proj, tmp_path, capsys):
    p, sd, plan = proj
    o1 = tmp_path / "o1.md"
    with pytest.raises(SystemExit) as e:
        build_prime.main(["--plan", str(sd), "--out", str(o1)])
    assert e.value.code == 2
    assert (f"error: --plan {sd} is a run folder with no plan file (stable.json, pool.json or plan.md name none); "
            "pass the plan file") in capsys.readouterr().err
    assert not o1.exists()
