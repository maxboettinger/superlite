"""A private copy of tests/scripts/fixtures, so no fixture plan resolves to the checkout's live .superlite.
Also drops the host's session id and state override from os.environ: test modules snapshot it into ENV at import,
and a tests/regression module imports them before pytest loads tests/scripts/conftest.py."""
import atexit
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

SOURCE = Path(__file__).resolve().parent / "fixtures"
HOST_VARS = ("CLAUDE_CODE_SESSION_ID", "SUPERLITE_SESSION_ID", "SUPERLITE_STATE_DIR", "CLAUDE_PROJECT_DIR", "CLAUDE_ENV_FILE",
             "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_FORK_SUBAGENT",  # the budget's agent-summary note reads these
             "SUPERLITE_FLEET_WORKER", "SUPERLITE_FLEET_AGENT",  # the SessionStart hook injects the worker note on these
             "SUPERLITE_FLEET_ROLE", "SUPERLITE_FLEET_PARENT_DIR")  # a batch lead pane exports these

# On first import, before any ENV snapshot (test_run_scripts imports this first): a host session id there would send a
# subprocess's default state (ledger, checkpoints, pool.json, gate) to the host session's bound .superlite.
for _var in HOST_VARS:
    os.environ.pop(_var, None)


def _in_git(path):
    return subprocess.run(["git", "-C", str(path), "rev-parse"], capture_output=True).returncode == 0


def _make():
    base = Path(tempfile.mkdtemp(prefix="sl_fixtures_")).resolve()
    if _in_git(base):  # TMPDIR inside a repo: fall back to /tmp
        shutil.rmtree(base, ignore_errors=True)
        base = Path(tempfile.mkdtemp(prefix="sl_fixtures_", dir="/tmp")).resolve()
        if _in_git(base):
            shutil.rmtree(base, ignore_errors=True)
            raise RuntimeError("no temp folder outside a git repository for the fixture copy")
    atexit.register(shutil.rmtree, base, ignore_errors=True)
    dest = base / "fixtures"
    shutil.copytree(SOURCE, dest, symlinks=True)
    return dest


FIXTURES = _make()

# Host-free subprocesses (#631), set on first import like HOST_VARS so every module ENV snapshot and every subprocess
# carries them: no disk floor or warn level (a 2 GB CI sandbox or a full Mac refused dispatch and run_tests), and a git
# identity on a host without one. The identity sits in a global config that includes the host's own global files, so a
# repository's own user.name (test_autocommit asserts it) still wins; a host with an identity keeps its config untouched.
DISK_FREE = {"SUPERLITE_DISK_FLOOR_GB": "0", "SUPERLITE_DISK_WARN_GB": "0"}  # a test env that drops SUPERLITE_* adds these back
os.environ.update(DISK_FREE)


def _git_identity(base):
    missing = {k: v for k, v in (("name", "superlite tests"), ("email", "tests@superlite.invalid"))
               if not subprocess.run(["git", "config", f"user.{k}"], cwd=base, capture_output=True, text=True).stdout.strip()}
    if not missing:
        return
    own = os.environ.get("GIT_CONFIG_GLOBAL")  # git reads it alone; else XDG git/config, then ~/.gitconfig (the later wins)
    host = [own] if own else [str(Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "git" / "config"),
                              str(Path.home() / ".gitconfig")]
    cfg = base / "gitconfig"  # git skips an include whose file is missing
    cfg.write_text("".join(f"[include]\n\tpath = {p}\n" for p in host)
                   + "[user]\n" + "".join(f"\t{k} = {v}\n" for k, v in missing.items()), encoding="utf-8")
    os.environ["GIT_CONFIG_GLOBAL"] = str(cfg)


_git_identity(FIXTURES.parent)
