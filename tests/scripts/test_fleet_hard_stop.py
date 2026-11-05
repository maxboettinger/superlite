import json, os, shutil, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SL = ROOT / "skills" / "subagent-driven-development" / "scripts" / "sl"
VERSION = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))["version"]
LINE = f"superlite {VERSION} at {ROOT}"

def run(argv, cwd, **extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith("SUPERLITE_") and k != "CLAUDE_ENV_FILE"}
    env.update(CLAUDE_PLUGIN_ROOT=str(ROOT), SUPERLITE_HOME=str(cwd / "home"), SUPERLITE_CACHE_DIR=str(cwd / "cache"), **extra)
    return subprocess.run(["bash", *map(str, argv)], input="", capture_output=True, text=True, encoding="utf-8", cwd=cwd, env=env)

def context(r):
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]

def test_session_start_names_root_version_and_sl(tmp_path):
    ctx = context(run([ROOT / "hooks" / "session-start"], tmp_path))
    assert LINE in ctx and f"{ROOT}/skills/subagent-driven-development/scripts/sl <tool>" in ctx

def test_worker_note_stays_short(tmp_path):
    r = run([ROOT / "hooks" / "session-start"], tmp_path, SUPERLITE_FLEET_WORKER="W1")
    assert "superlite fleet worker W1" in r.stdout and LINE not in r.stdout

def test_root_with_space_stays_valid_json(tmp_path):
    root = tmp_path / "plug in"
    for rel in ("hooks/session-start", "hooks/superlite-state.sh", "skills/using-superlite/SKILL.md", "package.json"):
        (root / rel).parent.mkdir(parents=True, exist_ok=True); shutil.copy(ROOT / rel, root / rel)
    assert f"superlite {VERSION} at {root.resolve()}" in context(run([root / "hooks" / "session-start"], tmp_path))

def test_sl_version_prints_root_and_tools(tmp_path):
    r = run([SL, "version"], tmp_path)
    assert r.returncode == 0 and r.stdout.splitlines()[0] == LINE and "fleet" in r.stdout.split()

def test_unknown_and_bare_sl_name_the_copy(tmp_path):
    r = run([SL, "fleeet"], tmp_path)
    assert r.returncode == 2 and "sl: unknown tool 'fleeet'" in r.stderr and LINE in r.stderr
    r = run([SL], tmp_path)
    assert r.returncode == 2 and LINE in r.stderr

def test_sdd_fleet_line_is_a_hard_stop():
    sdd = (ROOT / "skills" / "subagent-driven-development" / "SKILL.md").read_text(encoding="utf-8")
    line = next(l for l in sdd.splitlines() if l.startswith("Fleet mode"))
    assert '"$SL" fleet on' in line and "report BLOCKED" in line and "never in-process" in line and len(sdd) <= 11700
