# tests/scripts/test_session_start_roles.py
import json
import pytest
from test_fleet_hooks import run_hook, sd, worker_env  # noqa: F401  (sd is a fixture)

BUILD = "The coordinator sends your task as a message; build it, then finish with your report."

def note(sd, **extra):
    stdin = json.dumps({"session_id": "s1", "source": "startup", "cwd": str(sd.parent)})
    r = run_hook("session-start", stdin, {**worker_env(sd), **extra}, sd.parent)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]

def test_implementer_note_is_unchanged(sd):
    assert BUILD in note(sd) and BUILD in note(sd, SUPERLITE_FLEET_ROLE="implementer")

@pytest.mark.parametrize("role,agent", [("fixer", "superlite:fixer-opus"), ("package-reviewer", "superlite:package-reviewer"),
                                        ("final-reviewer", "superlite:final-reviewer"), ("research", "superlite:researcher")])
def test_brief_roles_get_the_brief_note(sd, role, agent):
    assert note(sd, SUPERLITE_FLEET_ROLE=role, SUPERLITE_FLEET_AGENT=agent) == (
        f"You are superlite fleet worker W1 ({role}, {agent}). The coordinator sends one brief file: "
        "do what it says, then end with the status line and the JSON block it asks for. Do not start a superlite run.")

def test_unknown_role_falls_back_to_the_implementer_note(sd):
    t = note(sd, SUPERLITE_FLEET_ROLE='x" injected')
    assert BUILD in t and "injected" not in t
