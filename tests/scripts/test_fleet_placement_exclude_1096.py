"""A project config entry keeps named machines out of fleet placement (#1096)."""
import json, subprocess, sys
import pytest
from test_fleet_placement import env, workers  # noqa: F401 (env is the fixture)
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import fleet_placement as fp  # noqa: E402

THREE = {"machines": [{"name": "host1", "state": "ready", "room": 12}, {"name": "box", "state": "ready", "room": 12},
                      {"name": "mxn", "state": "ready", "room": 20}]}


def cfg(folder, data):
    p = folder / ".superlite" / "placement.json"; p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(data if isinstance(data, str) else json.dumps(data))
    return p


def test_no_config_keeps_placement(env):
    assert fp.excluded(env.proj) == (set(), [], None)
    workers(env, None, None, None)
    assert fp.choose(env.sd, "implementer", env.proj, now=1.0) == "box"


def test_excluded_machine_is_never_chosen(env):
    p = cfg(env.proj, {"exclude": [" Box "]})
    assert fp.excluded(env.proj) == ({"box"}, [p], None)
    workers(env, None, None, None)
    assert fp.choose(env.sd, "implementer", env.proj, now=1.0) is None


def test_other_machines_still_placed(env, monkeypatch):
    monkeypatch.setenv("FAKE_ROOM_JSON", json.dumps(THREE))
    monkeypatch.setattr(fp.hc, "machines", lambda: [{"label": "box", "enabled": True}, {"label": "mxn", "enabled": True}])
    workers(env, None, None, None)
    assert fp.choose(env.sd, "implementer", env.proj, now=1.0) == "mxn"
    cfg(env.proj, {"exclude": ["MXN.lan"]})
    assert fp.choose(env.sd, "implementer", env.proj, now=2.0) == "box"


def test_is_excluded_by_short_name():
    assert fp.is_excluded("box.lan", {"box"}) and fp.is_excluded("BOX", {"box"}) and fp.is_excluded("box", {"box.lan"})
    assert not fp.is_excluded("boxer", {"box"}) and not fp.is_excluded("box", set())


@pytest.mark.parametrize("bad,why", [("{", "not valid JSON"), ("[]", "not a JSON object"),
                                     ('{"exclude": "box"}', "exclude must be a list of machine names"),
                                     ('{"exclude": ["box", " "]}', "exclude must be a list of machine names")])
def test_unreadable_config_keeps_every_worker_local(env, capsys, bad, why):
    p = cfg(env.proj, bad)
    assert fp.excluded(env.proj) == (set(), [p], f"{p}: {why}")
    workers(env, None, None, None)
    assert fp.choose(env.sd, "implementer", env.proj, now=1.0) is None
    assert f"placement: {p}: {why}; every worker of this project stays local (#1096)" in capsys.readouterr().err


def test_object_without_exclude_excludes_nothing(env):
    p = cfg(env.proj, {"note": "x"})
    assert fp.excluded(env.proj) == (set(), [p], None)


def git(*a):
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *a], check=True, capture_output=True)


def test_worktree_reads_the_main_checkout_config(tmp_path):
    main = tmp_path / "main"; main.mkdir()
    git("-C", str(main), "init", "-q"); git("-C", str(main), "commit", "-q", "--allow-empty", "-m", "x")
    wt = tmp_path / "wt"; git("-C", str(main), "worktree", "add", "-q", str(wt))
    pm, pw = cfg(main, {"exclude": ["mxn"]}), cfg(wt, {"exclude": ["box"]})
    names, files, err = fp.excluded(wt)
    assert names == {"mxn", "box"} and err is None
    assert [f.resolve() for f in files] == [pw.resolve(), pm.resolve()]
    assert [f.resolve() for f in fp.config_files(main)] == [pm.resolve()]
    assert [f.resolve() for f in fp.config_files(tmp_path / "nogit")] == [(tmp_path / "nogit" / ".superlite" / "placement.json").resolve()]


def test_machine_refusal(env):
    assert fp.machine_refusal(env.proj, "box") is None
    p = cfg(env.proj, {"exclude": ["box"]})
    assert fp.machine_refusal(env.proj, "Box") == f"error: machine Box is excluded from this project's fleet by {p}; drop --machine or pass --machine local (#1096)"
    assert fp.machine_refusal(env.proj, "mxn") is None and fp.machine_refusal(env.proj, "local") is None and fp.machine_refusal(env.proj, None) is None
    cfg(env.proj, "{")
    assert fp.machine_refusal(env.proj, "mxn") == f"error: {p}: not valid JSON; fix it before a remote spawn (#1096)"


def test_docstring_names_the_config():
    assert ".superlite/placement.json" in fp.__doc__ and "(#1096)" in fp.__doc__
