"""test_layers: matrix, stamps, Stop hook protocol."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "test_layers.py"
spec = importlib.util.spec_from_file_location("test_layers", SCRIPT)
tl = importlib.util.module_from_spec(spec)
sys.modules["test_layers"] = tl
spec.loader.exec_module(tl)  # puts scripts/ on sys.path, so layer_store imports below
import layer_store as real_store  # noqa: E402

FILES = ["hooks/x", "hooks/session-start", "skills/a/SKILL.md", "agents/a.md", "commands/a.md",
         "tests/e2e/harness.py", "evals/c/prompt.md"]


def git(root, *args):
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


class FakeStore:
    """In-memory stand-in for layer_store: the same eight functions, no files."""

    def __init__(self):
        self.green, self.files, self.locks = {}, {}, {}

    def store_path(self, root):
        return Path(root) / "fake-store.json"

    def is_green(self, store, layer, digest):
        return digest in self.green.get(layer, [])

    def record_green(self, store, layer, digest, files):
        self.green.setdefault(layer, []).append(digest)
        self.files[layer] = dict(files)

    def changed_files(self, store, layer, files):
        old = self.files.get(layer, {})
        return sorted(p for p in set(files) | set(old) if files.get(p) != old.get(p))

    def has_manifest(self, store, layer):
        return layer in self.files

    def start_run(self, store, layer, digest, pid):
        self.locks[layer] = digest

    def running(self, store, layer, digest):
        return self.locks.get(layer) == digest

    def end_run(self, store, layer):
        self.locks.pop(layer, None)


@pytest.fixture
def store_api(monkeypatch):
    """The store module test_layers calls in-process: the fake by default, layer_store when SUPERLITE_REAL=1."""
    api = real_store if os.environ.get("SUPERLITE_REAL") == "1" else FakeStore()
    monkeypatch.setattr(tl, "layer_store", api)
    return api


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q")
    git(root, "config", "user.email", "a@b.c")
    git(root, "config", "user.name", "t")
    for f in FILES:
        p = root / f
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x\n")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "init")
    return root


DEFAULT = object()


def store_file(root):
    """The tmp store every cli() call of one test shares (beside the repo, so a worktree sibling shares it too)."""
    return Path(root).parent / "layer-store" / "test-layers.json"


def cli(root, *args, stdin="", env=None, state=DEFAULT):
    """Run the script with --root and --state; state=None leaves the default store (the git common dir's)."""
    e = {**os.environ, "SUPERLITE_TEST_LAYERS": ""}
    e.update(env or {})
    extra = [] if state is None else ["--state", str(store_file(root) if state is DEFAULT else state)]
    return subprocess.run([sys.executable, str(SCRIPT), *args, "--root", str(root), *extra], input=stdin,
                          capture_output=True, text=True, env=e)


def stale_names(root, **kw):
    """The layers `check` names: the first word of each output line."""
    return [line.split()[0] for line in cli(root, "check", **kw).stdout.splitlines()]


def stamp_all(root, **kw):
    for layer in ("unit", "headless", "tui", "evals"):
        assert cli(root, "stamp", layer, "--ruling", "r", **kw).returncode == 0


def test_layers_for_matrix():
    assert tl.layers_for(["hooks/session-start"]) == ["unit", "headless", "tui"]
    assert tl.layers_for(["skills/brainstorming/SKILL.md"]) == ["headless", "evals"]
    assert tl.layers_for(["docs/testing.md"]) == []
    assert tl.layers_for(["README.md"], {"README.md": "+ set CLAUDE_CODE_FORK_SUBAGENT=0"}) == ["tui"]
    assert tl.layers_for(["tests/scripts/test_x.py"]) == ["unit"]
    assert tl.layers_for(["agents/implementer.md"]) == ["headless", "evals"]
    assert tl.layers_for(["evals/c/graders/g.md"]) == ["evals"]


def test_check_exit_codes(repo):
    r = cli(repo, "check")
    assert r.returncode == 2
    assert [line.split()[0] for line in r.stdout.splitlines()] == ["unit", "headless", "tui", "evals"]
    assert r.stdout.splitlines()[0] == "unit stale: no green stamp"
    stamp_all(repo)
    r = cli(repo, "check")
    assert (r.returncode, r.stdout) == (0, "")


def test_stamp_then_clean_is_not_stale(repo):
    cli(repo, "stamp", "headless", "--ruling", "r")
    assert "headless" not in stale_names(repo)


def test_change_after_stamp_is_stale(repo):
    stamp_all(repo)
    with open(repo / "hooks" / "session-start", "a") as f:
        f.write("more\n")
    assert stale_names(repo) == ["unit", "headless", "tui"]


def test_layer_hash_ignores_untracked_results(repo):
    before = tl.layer_hash("evals", repo)
    (repo / "evals" / "results").mkdir()
    (repo / "evals" / "results" / "last.json").write_text("{}")
    assert tl.layer_hash("evals", repo) == before
    (repo / "evals" / "c" / "new.md").write_text("n")
    assert tl.layer_hash("evals", repo) != before


def test_hook_blocks_with_layers_and_commands(repo):
    stamp_all(repo)
    (repo / "agents" / "a.md").write_text("changed\n")
    r = cli(repo, "check", "--hook", stdin=json.dumps({"stop_hook_active": False, "cwd": str(repo)}))
    assert r.returncode == 0
    out = json.loads(r.stdout.strip())
    assert out["decision"] == "block"
    assert "headless" in out["reason"]
    assert "python3 scripts/test_layers.py run headless" in out["reason"]
    assert out["reason"].endswith(" (status: python3 scripts/test_layers.py status)")


def test_hook_silent_when_stop_hook_active(repo):
    r = cli(repo, "check", "--hook", stdin=json.dumps({"stop_hook_active": True, "cwd": str(repo)}))
    assert (r.returncode, r.stdout) == (0, "")
    r = cli(repo, "check", "--hook", stdin=json.dumps({"stop_hook_active": False, "cwd": str(repo)}),
            env={"SUPERLITE_TEST_LAYERS": "off"})
    assert (r.returncode, r.stdout) == (0, "")
    r = cli(repo, "check", "--hook", stdin=json.dumps({"stop_hook_active": True}),
            env={"SUPERLITE_TEST_LAYERS": "off"})
    assert (r.returncode, r.stdout) == (0, "")


def test_hook_silent_during_active_run(repo):
    (repo / ".superlite").mkdir()
    (repo / ".superlite" / "pool.json").write_text("{}")
    r = cli(repo, "check", "--hook", stdin=json.dumps({"stop_hook_active": False, "cwd": str(repo)}))
    assert (r.returncode, r.stdout) == (0, "")


def test_run_stamps_only_green_layers(repo):
    r = cli(repo, "run", "unit", "headless", "--command-override", "unit=true", "headless=false")
    assert r.returncode == 1
    assert "unit: green" in r.stdout and "headless: red" in r.stdout
    stale = stale_names(repo)
    assert "unit" not in stale and "headless" in stale


def test_default_e2e_commands_use_sl_run_tests():
    for layer, name in (("headless", "test_headless"), ("tui", "test_tui")):
        cmd = tl.COMMANDS[layer]
        assert f"run_tests --fast tests/e2e/{name}.py" in cmd
        assert "-m pytest" not in cmd


def test_run_sets_superlite_e2e_for_e2e_layers_only(repo, tmp_path):
    out = tmp_path / "out"
    env = {"SUPERLITE_E2E": ""}
    over = [f"{layer}=printf %s \"$SUPERLITE_E2E\" > {out}-{layer}" for layer in ("unit", "headless")]
    assert cli(repo, "run", "unit", "headless", "--command-override", *over, env=env).returncode == 0
    assert (Path(f"{out}-headless").read_text(), Path(f"{out}-unit").read_text()) == ("1", "")


def test_stamp_ruling_appends_progress_line(repo):
    assert cli(repo, "stamp", "tui", "--ruling", "no tmux here").returncode == 0
    text = (repo / ".superlite" / "progress.md").read_text()
    assert "Ruling: skip tui - no tmux here" in text


def test_hook_never_raises_on_bad_cwd():
    r = subprocess.run([sys.executable, str(SCRIPT), "check", "--hook"],
                       input=json.dumps({"cwd": ["not", "a", "path"]}), capture_output=True, text=True,
                       env={**os.environ, "SUPERLITE_TEST_LAYERS": ""}, cwd="/")
    assert (r.returncode, r.stdout, r.stderr) == (0, "", "")
    r = subprocess.run([sys.executable, str(SCRIPT), "check", "--hook"], input="{not json",
                       capture_output=True, text=True, env={**os.environ, "SUPERLITE_TEST_LAYERS": ""},
                       cwd="/")
    assert r.returncode == 0 and r.stderr == ""


def test_tui_keyword_file_is_stamped_clear_and_plans_skipped(repo):
    (repo / "README.md").write_text("set CLAUDE_CODE_FORK_SUBAGENT=0\n")
    (repo / "docs" / "plans").mkdir(parents=True)
    (repo / "docs" / "plans" / "p.md").write_text("agent_summary\n")
    assert "README.md" in tl.layer_files("tui", repo)
    assert "docs/plans/p.md" not in tl.layer_files("tui", repo)
    cli(repo, "stamp", "tui", "--ruling", "r")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "c")
    assert "tui" not in stale_names(repo)
    (repo / "README.md").write_text("changed CLAUDE_CODE_FORK_SUBAGENT=1\n")
    assert "tui" in stale_names(repo)


def test_stale_layers_ignores_unmapped(tmp_path, store_api):
    root = tmp_path / "r"
    root.mkdir()
    git(root, "init", "-q")
    (root / "docs").mkdir()
    (root / "docs" / "a.md").write_text("x")
    assert tl.stale_layers(root, root / "s.json") == []


def hook_no_root(cwd, stdin):
    return subprocess.run([sys.executable, str(SCRIPT), "check", "--hook"], input=stdin, capture_output=True,
                          text=True, env={**os.environ, "SUPERLITE_TEST_LAYERS": ""}, cwd=cwd)


def test_hook_silent_on_empty_stdin(tmp_path):
    r = hook_no_root(tmp_path, "")
    assert (r.returncode, r.stdout, r.stderr) == (0, "", "")


def test_hook_silent_on_non_json_stdin(tmp_path):
    r = hook_no_root(tmp_path, "{not json")
    assert (r.returncode, r.stdout, r.stderr) == (0, "", "")


def test_hook_silent_in_git_worktree_cwd(repo, tmp_path):
    wt = tmp_path / "wt"
    git(repo, "worktree", "add", "-q", str(wt), "-b", "side")
    assert (wt / ".git").is_file()
    for layer in ("unit", "headless", "tui", "evals"):
        assert cli(wt, "stamp", layer, "--ruling", "r", state=None).returncode == 0
    r = hook_no_root("/", json.dumps({"stop_hook_active": False, "cwd": str(wt)}))
    assert (r.returncode, r.stdout, r.stderr) == (0, "", "")
    (wt / "agents" / "a.md").write_text("changed\n")
    r = hook_no_root("/", json.dumps({"cwd": str(wt)}))
    assert r.returncode == 0 and json.loads(r.stdout)["decision"] == "block"


def test_hook_silent_in_non_repo_cwd(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / "hooks").mkdir()
    (plain / "hooks" / "x").write_text("x")
    r = hook_no_root("/", json.dumps({"cwd": str(plain)}))
    assert (r.returncode, r.stdout, r.stderr) == (0, "", "")


def test_layers_for_normalises_backslash_paths():
    assert tl.layers_for(["hooks\\session-start"]) == tl.layers_for(["hooks/session-start"])
    assert tl.layers_for(["hooks\\session-start"]) == ["unit", "headless", "tui"]
    assert tl.layers_for(["evals\\results\\x.json"]) == []
    assert tl.layers_for(["README.md"], {"README.md": "agent_summary"}) == ["tui"]


def test_layer_hash_ignores_results_and_superlite_state(repo):
    before = {l: tl.layer_hash(l, repo) for l in ("evals", "unit")}
    (repo / "evals" / "results").mkdir()
    (repo / "evals" / "results" / "run.json").write_text("{}")
    (repo / ".superlite").mkdir()
    (repo / ".superlite" / "progress.md").write_text("p")
    (repo / ".superlite" / "test-layers.json").write_text("{}")
    assert {l: tl.layer_hash(l, repo) for l in before} == before
    (repo / "evals" / "results" / "run.json").write_text('{"changed": 1}')
    assert {l: tl.layer_hash(l, repo) for l in before} == before


def test_agents_md_runs_layers_through_test_layers():
    text = (Path(__file__).resolve().parents[2] / "AGENTS.md").read_text(encoding="utf-8")
    assert "-m pytest" not in text
    assert "test_layers.py run headless" in text and "test_layers.py run tui" in text
    assert "coordinator's step" in text


def test_tools_doc_matches_record_and_claim_code():
    text = (Path(__file__).resolve().parents[2] / "docs" / "tools.md").read_text(encoding="utf-8")
    assert "--record --passed N [--failed N] [--skipped N] [--seconds S] --command CMD" in text
    assert "not with `--also`" in text


PLUGIN = '{"name": "x", "version": "1.0.0"}\n'


def write_manifests(root, version, name="x", spaced=False):
    sep = ' :  ' if spaced else ': '
    plugin = f'{{"name": "{name}", "version"{sep}"{version}"}}\n'
    files = {".claude-plugin/plugin.json": plugin, ".claude-plugin/marketplace.json": plugin.replace('"x"', '"m"'),
             "package.json": plugin, "gemini-extension.json": plugin}
    for path, text in files.items():
        (root / path).parent.mkdir(exist_ok=True)
        (root / path).write_text(text)


def hashes(root):
    return {layer: tl.layer_hash(layer, root) for layer in ("unit", "headless", "tui", "evals")}


def test_version_only_change_keeps_hashes(repo):
    write_manifests(repo, "1.0.0")
    before = hashes(repo)
    plugin_digest = tl.layer_digests("headless", repo)[".claude-plugin/plugin.json"]
    assert plugin_digest == hashlib.sha256(b'{"name": "x", "version": ""}\n').hexdigest()
    write_manifests(repo, "1.0.1")
    assert hashes(repo) == before
    write_manifests(repo, "1.0.2", spaced=True)
    assert hashes(repo) == before
    assert all(tl.is_manifest(p) for p in (".claude-plugin/plugin.json", ".codex-plugin/plugin.json", "package.json",
                                           "gemini-extension.json"))
    assert not any(tl.is_manifest(p) for p in ("sub/package.json", ".claude-plugin/sub/x.json", "hooks/hooks.json"))


def test_manifest_other_change_moves_headless(repo):
    write_manifests(repo, "1.0.0")
    before = hashes(repo)
    write_manifests(repo, "1.0.0", name="y")
    assert hashes(repo)["headless"] != before["headless"]


def test_keyword_lines_only(repo):
    (repo / "notes").mkdir()
    page = repo / "notes" / "x.py"
    page.write_text('a = 1\nos.environ["CLAUDE_CODE_FORK_SUBAGENT"]\n')
    assert "notes/x.py" in tl.layer_files("tui", repo)
    before = tl.layer_hash("tui", repo)
    page.write_text('a = 2\nos.environ["CLAUDE_CODE_FORK_SUBAGENT"]\n')
    assert tl.layer_hash("tui", repo) == before
    page.write_text('a = 2\nos.environ["CLAUDE_CODE_FORK_SUBAGENT"] = "0"\n')
    assert tl.layer_hash("tui", repo) != before


def test_keyword_hash_edge_cases(repo):
    (repo / "notes").mkdir()
    page = repo / "notes" / "y.bin"
    page.write_bytes(b"\xff\xfe\x00 agent_summary")
    before = tl.layer_hash("tui", repo)
    assert "notes/y.bin" in tl.layer_digests("tui", repo)
    page.write_bytes(b"\xff\xfe\x00 agent_summary!")
    assert tl.layer_hash("tui", repo) != before
    page.write_bytes(b"\xff\xfe\x00 nothing")
    assert "notes/y.bin" not in tl.layer_digests("tui", repo)
    assert tl.layer_hash("tui", repo) != before


def test_keyword_scan_skips_tests_scripts(repo):
    (repo / "tests" / "scripts").mkdir(parents=True)
    (repo / "tests" / "scripts" / "conftest.py").write_text('os.environ["CLAUDE_CODE_FORK_SUBAGENT"]\n')
    assert "tests/scripts/conftest.py" not in tl.layer_digests("tui", repo)


def test_green_in_worktree_counts_in_main(repo, tmp_path):
    wt = tmp_path / "wt"
    git(repo, "worktree", "add", "-q", str(wt), "-b", "side")
    stamp_all(wt, state=None)
    r = cli(repo, "check", state=None)
    assert (r.returncode, r.stdout) == (0, "")


def test_check_names_changed_files(repo):
    r = cli(repo, "check")
    assert r.returncode == 2 and "unit stale: no green stamp" in r.stdout.splitlines()
    (repo / "hooks" / "a").write_text("1\n")
    assert cli(repo, "run", "unit", "--command-override", "unit=true").returncode == 0
    (repo / "hooks" / "a").write_text("2\n")
    (repo / "hooks" / "b").write_text("1\n")
    r = cli(repo, "check")
    assert r.returncode == 2
    assert "unit stale: hooks/a, hooks/b" in r.stdout.splitlines()
    for i in range(1, 8):
        (repo / "hooks" / f"n{i}").write_text("n\n")
    line = next(l for l in cli(repo, "check").stdout.splitlines() if l.startswith("unit "))
    assert line == "unit stale: hooks/a, hooks/b, hooks/n1, hooks/n2, hooks/n3 (+4 more)"


def test_status_lists_every_layer(repo, tmp_path):
    s = store_file(repo)
    assert cli(repo, "stamp", "unit", "--ruling", "r").returncode == 0
    real_store.start_run(s, "headless", tl.layer_hash("headless", repo), os.getpid())
    r = cli(repo, "status")
    lines = r.stdout.splitlines()
    assert r.returncode == 0 and len(lines) == 4
    assert lines[0].startswith("unit green ")
    assert lines[1].startswith("headless running ")
    assert lines[2].startswith("tui stale ")
    assert lines[3].startswith("evals stale ")
    bare = tmp_path / "bare"
    bare.mkdir()
    git(bare, "init", "-q")
    (bare / "hooks").mkdir()
    (bare / "hooks" / "x").write_text("x\n")
    assert cli(bare, "status").stdout.splitlines()[2:] == ["tui none", "evals none"]


def test_hook_skips_running_layer(repo):
    hook = json.dumps({"stop_hook_active": False, "cwd": str(repo)})
    for layer in ("headless", "tui", "evals"):
        assert cli(repo, "stamp", layer, "--ruling", "r").returncode == 0
    r = cli(repo, "check", "--hook", stdin=hook)
    assert json.loads(r.stdout)["decision"] == "block" and "unit" in json.loads(r.stdout)["reason"]
    real_store.start_run(store_file(repo), "unit", tl.layer_hash("unit", repo), os.getpid())
    r = cli(repo, "check", "--hook", stdin=hook)
    assert (r.returncode, r.stdout) == (0, "")


def test_stale_layers_skips_green_and_running(repo, tmp_path, store_api):
    state = tmp_path / "s" / "test-layers.json"
    assert tl.stale_layers(repo, state) == ["unit", "headless", "tui", "evals"]
    store_api.record_green(state, "unit", tl.layer_hash("unit", repo), tl.layer_digests("unit", repo))
    store_api.start_run(state, "headless", tl.layer_hash("headless", repo), os.getpid())
    assert tl.stale_layers(repo, state) == ["tui", "evals"]
    store_api.end_run(state, "headless")
    assert tl.stale_layers(repo, state) == ["headless", "tui", "evals"]


def test_run_releases_lock(repo, tmp_path):
    s = store_file(repo)
    assert cli(repo, "run", "unit", "--command-override", "unit=true").returncode == 0
    digest = tl.layer_hash("unit", repo)
    assert real_store.is_green(s, "unit", digest) and not real_store.running(s, "unit", digest)
    other = tmp_path / "other" / "test-layers.json"
    r = cli(repo, "run", "unit", "--command-override", "unit=false", state=other)
    assert r.returncode == 1
    assert not real_store.is_green(other, "unit", digest) and not real_store.running(other, "unit", digest)
    assert json.loads((other.parent / "running.json").read_text()) == {}


def test_run_holds_lock_during_command(repo, tmp_path):
    seen = tmp_path / "seen.json"
    lock = store_file(repo).parent / "running.json"
    cmd = f"unit=cp {shlex.quote(str(lock))} {shlex.quote(str(seen))}"
    assert cli(repo, "run", "unit", "--command-override", cmd).returncode == 0
    assert json.loads(seen.read_text())["unit"]["digest"] == tl.layer_hash("unit", repo)


def test_stamp_ruling_records_green(repo):
    assert cli(repo, "stamp", "tui", "--ruling", "why").returncode == 0
    assert real_store.is_green(store_file(repo), "tui", tl.layer_hash("tui", repo))
    assert "Ruling: skip tui - why\n" in (repo / ".superlite" / "progress.md").read_text()
