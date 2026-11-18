import json

from test_fleet_hooks import run_hook

HEAD = "Project corrections (binding, from the user; docs/superlite/corrections.md):"
CAPTURE = 'When the user corrects you in a way later runs need, record it: sl corrections add "<rule>".'
HEADER = "# Corrections\n\nOne line per correction from the user; superlite gives this file to every run. Managed by sl corrections.\n\n"


def put(proj, body):
    p = proj / "docs" / "superlite" / "corrections.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")


def ctx(proj, **env):
    stdin = json.dumps({"session_id": "s1", "source": "startup", "cwd": str(proj)})
    r = run_hook("session-start", stdin, env, proj)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]


def test_main_session_gets_the_corrections_lines(tmp_path):
    put(tmp_path, HEADER + "- Use uv, never pip\n- German UI strings\n")
    t = ctx(tmp_path)
    assert HEAD + "\n- Use uv, never pip\n- German UI strings" in t
    assert "One line per correction" not in t


def test_every_main_session_gets_the_capture_line(tmp_path):
    assert CAPTURE in ctx(tmp_path)
    assert "Project corrections" not in ctx(tmp_path)
    put(tmp_path, HEADER + "- a\n")
    assert CAPTURE in ctx(tmp_path)


def test_oversize_file_is_skipped(tmp_path):
    put(tmp_path, HEADER + "- " + "a" * 3000 + "\n")
    t = ctx(tmp_path)
    assert "Project corrections" not in t and CAPTURE in t


def test_worker_session_gets_no_corrections(tmp_path):
    put(tmp_path, HEADER + "- a\n")
    t = ctx(tmp_path, SUPERLITE_FLEET_WORKER="W1")
    assert "Project corrections" not in t and CAPTURE not in t


def test_lead_session_gets_them(tmp_path):
    put(tmp_path, HEADER + "- a\n")
    t = ctx(tmp_path, SUPERLITE_FLEET_WORKER="W1", SUPERLITE_FLEET_ROLE="lead")
    assert HEAD + "\n- a" in t and CAPTURE in t


def test_output_stays_valid_json(tmp_path):
    put(tmp_path, HEADER + '- say "hi" \\ there\tend\n')
    assert 'say "hi" \\ there\tend' in ctx(tmp_path)
