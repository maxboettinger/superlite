"""#577: the layer shell records its pid so a restore can tell a dead layer run."""
import os
import shlex
import sys
from test_fleet_layer import run_world  # noqa: F401  (fixture)
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import fleet_layer as fl  # noqa: E402


def test_command_records_shell_pid(run_world):
    pid = run_world.sd / "fleet" / "layers" / "W5-headless.pid"
    pid.parent.mkdir(parents=True, exist_ok=True)
    pid.write_text("1")
    fl.run(run_world.sd, "headless", run_world.root, env={"HOME": "/u"})
    (_, command), = run_world.pane.calls
    assert command.startswith("echo $$ > %s; " % shlex.quote(str(pid)))
    assert not pid.exists()


def test_alive_examples(tmp_path):
    d = tmp_path / "fleet" / "layers"
    d.mkdir(parents=True)
    w = {"layer": "headless"}
    assert fl.alive(tmp_path, "W3", w) is None
    f = d / "W3-headless.pid"
    f.write_text(str(os.getpid()))
    assert fl.alive(tmp_path, "W3", w) is True
    f.write_text("999999")
    assert fl.alive(tmp_path, "W3", w) is False
    f.write_text("garbage")
    assert fl.alive(tmp_path, "W3", w) is None
