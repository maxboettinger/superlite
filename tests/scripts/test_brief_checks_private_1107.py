"""send --brief, review_brief and findings.route take the project from state.project, and send refuses a brief naming its own report (#1107)."""
import types

import pytest
from test_fleet_io import io, world  # noqa: F401  (world is a fixture)
from test_plan_tools import SCRIPTS
import state  # noqa: E402


@pytest.fixture
def priv(tmp_path, monkeypatch):
    home = tmp_path / "home"; psd = home / "sessions" / "s1.d" / ".superlite"; psd.mkdir(parents=True)
    proj = tmp_path / "proj"; (proj / ".git").mkdir(parents=True); (proj / "src").mkdir(); (proj / "src" / "a.py").write_text("x")
    monkeypatch.setenv("SUPERLITE_HOME", str(home))
    for v in ("CLAUDE_PROJECT_DIR", "SUPERLITE_STATE_DIR"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.chdir(proj / "src")
    return types.SimpleNamespace(home=home, psd=psd, proj=proj, tmp=tmp_path)


def test_brief_refusal_passes_a_project_brief_for_a_private_folder(priv):
    b = priv.proj / "notes" / "b.md"; b.parent.mkdir(); b.write_text(f"Read {priv.proj}/src/a.py.\n")
    assert io.brief_refusal(priv.psd, b, "research") is None


def test_brief_refusal_still_refuses_outside_paths_for_a_private_folder(priv):
    other = priv.tmp / "other"; other.mkdir(); (other / "x.md").write_text("x")
    b = priv.psd / "briefs" / "b.md"; b.parent.mkdir(); b.write_text(f"Read {other}/x.md.\n")
    why = io.brief_refusal(priv.psd, b, "research")
    assert why.startswith("error: brief") and "other/x.md" in why


def test_review_brief_root_is_the_launch_project(world, monkeypatch):  # inputs as test_fleet_io_review_422
    sentinel = world.proj / "sentinel"
    monkeypatch.setattr(state, "project", lambda sd: sentinel)
    assert f"Root: {sentinel}" in io.review_brief(world.sd, world.plan, ["T3"], "/sl/sl", "/sl")


def test_findings_route_takes_state_project():
    for name in ("findings.py", "fleet_io.py"):
        text = (SCRIPTS / name).read_text(encoding="utf-8")
        assert "state.git_root(sd) or sd.parent" not in text and "state.project(sd)" in text


def _brief(world, text, name="R1.md"):
    b = world.sd / "briefs" / name; b.parent.mkdir(exist_ok=True); b.write_text(text)
    return b


def test_send_refuses_brief_naming_own_report(world, capsys):
    b = _brief(world, f"Write {world.sd}/fleet/reports/R1.md.\n")
    assert io.main(["send", "W1", "--brief", str(b), "--plan", str(world.sd)]) == 2
    err = capsys.readouterr().err
    assert "(#1094)" in err and "fleet wait saves the worker's reply" in err
    assert [c for c in world.fh.calls if c[0] == "prompt"] == []


def test_send_allows_full_report_name(world):
    b = _brief(world, f"Write {world.sd}/fleet/reports/R1-full.md.\n")
    assert io.main(["send", "W1", "--brief", str(b), "--plan", str(world.sd)]) == 0
    assert [c for c in world.fh.calls if c[0] == "prompt"]
