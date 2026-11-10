# tests/scripts/test_fleet_lean_377.py
import pytest
from test_fleet import REAL, fleet, world  # noqa: F401  (world is a fixture)

FLAGS = ["--strict-mcp-config", "--no-chrome", "--disable-slash-commands"]
DENY = ["Artifact", "ArtifactComments", "ArtifactData", "ListAgents", "ReadNotifications", "ReportFindings"]
A1 = ["--agent", "superlite:implementer", "--model", "sonnet", "--disallowedTools", "AskUserQuestion"]
A2 = ["--agent", "x"]
A3 = ["--agent", "superlite:researcher", "--model", "sonnet", "--disallowedTools", "AskUserQuestion", "Edit", "Write", "NotebookEdit", "Bash", "Artifact"]

def test_lean_argv_inserts_flags_before_the_deny_list():
    before = list(A1)
    assert fleet.lean_argv(A1) == ["--agent", "superlite:implementer", "--model", "sonnet", *FLAGS, "--disallowedTools", "AskUserQuestion", *DENY]
    assert A1 == before

def test_lean_argv_adds_a_deny_list_when_none():
    assert fleet.lean_argv(A2) == ["--agent", "x", *FLAGS, "--disallowedTools", *DENY]

def test_lean_argv_keeps_research_writers_and_repeats_nothing():
    assert fleet.lean_argv(A3) == ["--agent", "superlite:researcher", "--model", "sonnet", *FLAGS, "--disallowedTools",
                                   "AskUserQuestion", "Edit", "Write", "NotebookEdit", "Bash", "Artifact", *DENY[1:]]
    for a in (A1, A2, A3):
        assert fleet.lean_argv(fleet.lean_argv(a)) == fleet.lean_argv(a)
    out = fleet.lean_argv(["--disallowedTools", "AskUserQuestion", "--effort", "high"])
    assert out == [*FLAGS, "--disallowedTools", "AskUserQuestion", *DENY, "--effort", "high"]

@pytest.mark.skipif(REAL, reason="argv is read from the in-process fake")
def test_spawn_starts_every_role_lean(world, tmp_path):
    fleet.main(["on"])
    other = tmp_path / "elsewhere"; other.mkdir()
    for i, role in enumerate(["implementer", "package-reviewer", "research"]):
        fleet.spawn(world.sd, world.plan, "sonnet" if role == "implementer" else None, other, role=role)
        argv = [c for c in world.fh.calls if c[0] == "start_agent"][i][2]
        for f in FLAGS:
            assert argv.count(f) == 1
        assert "Artifact" in argv[argv.index("--disallowedTools"):]
        assert argv[-2:] == ["--add-dir", str(world.sd.resolve())]
        if role == "implementer":
            assert argv[:6] == ["--agent", "superlite:implementer", "--model", "sonnet", "--effort", "medium"]
