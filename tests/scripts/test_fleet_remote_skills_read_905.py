import sys
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import fleet_roles as fr  # noqa: E402
from test_fleet_remote_worker import record, started, world  # noqa: F401,E402  (world is a fixture)


def test_remote_worker_reads_its_machine_plugin_skills(world):
    started(world)
    argv = next(c for c in world.fh.calls if c[0] == "start_agent")[2]
    assert argv[0] == "--plugin-dir"
    i, j = argv.index("--allowedTools"), argv.index("--disallowedTools")
    assert "Read(/" + argv[1].rstrip("/") + "/skills/**)" in argv[i + 1:j]
    assert "Read(/" + fr.SKILLS.as_posix() + "/**)" not in argv
    assert argv.count("--allowedTools") == 1 and record(world)["launch"]["argv"] == argv
