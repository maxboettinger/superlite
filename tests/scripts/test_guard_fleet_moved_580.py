import json

from test_fleet_hooks import sd  # noqa: F401  (sd is a fixture)
from test_guard_fleet_agents import guard


def put(d, **kw):
    d.mkdir(parents=True, exist_ok=True)
    (d / "fleet.json").write_text(json.dumps(kw))


def test_block_names_fleet_folder(sd):
    put(sd, on=True)
    r = guard(sd, "superlite:implementer")
    assert r.returncode == 2
    assert f" Fleet state read: {sd}/fleet.json." in r.stderr


def test_moved_fleet_blocks_and_names_both(sd):
    other = sd.parent.parent / "other"
    put(sd, on=False, moved_to=str(other))
    put(other, on=True)
    r = guard(sd, "superlite:implementer")
    assert r.returncode == 2
    assert f" Fleet state read: {sd}/fleet.json, moved to {other}/fleet.json." in r.stderr
    assert f"PLAN is the plan file, or {other} for a build without a plan." in r.stderr
    assert (other / "incidents.jsonl").exists()


def test_moved_research_hint_uses_target(sd):
    other = sd.parent.parent / "other"
    put(sd, on=False, moved_to=str(other))
    put(other, on=True)
    r = guard(sd, "superlite:researcher")
    assert r.returncode == 2
    assert f"write the prompt to {other}/briefs/<name>.md;" in r.stderr


def test_moved_to_off_target_passes(sd):
    other = sd.parent.parent / "other"
    put(sd, on=False, moved_to=str(other))
    put(other, on=False)
    assert guard(sd, "superlite:implementer").returncode == 0


def chain(sd, n):
    base = sd.parent.parent
    dirs = [sd] + [base / f"d{i}" for i in range(1, n + 1)]
    for i, d in enumerate(dirs):
        if i < n:
            put(d, on=False, moved_to=str(dirs[i + 1]))
        else:
            put(d, on=True)


def test_chain_limit(sd):
    chain(sd, 5)
    assert guard(sd, "superlite:implementer").returncode == 2
    for f in sd.parent.parent.glob("d*/fleet.json"):
        f.unlink()
    chain(sd, 6)
    assert guard(sd, "superlite:implementer").returncode == 0


def test_relative_moved_to_ignored(sd):
    put(sd, on=False, moved_to="rel/x")
    assert guard(sd, "superlite:implementer").returncode == 0


def test_backslash_moved_to_read_as_slash(sd):
    other = sd.parent.parent / "other"
    put(sd, on=False)
    (sd / "fleet.json").write_text('{"on": false, "moved_to": "' + str(other).replace("/", "\\\\") + '"}')
    put(other, on=True)
    assert guard(sd, "superlite:implementer").returncode == 2


def test_checker_blocked_with_fleet_on(sd):
    put(sd, on=True)
    for name in ("superlite:checker", "Superlite:Checker"):
        r = guard(sd, name)
        assert r.returncode == 2
        assert "sl fleet spawn --role checker" in r.stderr
