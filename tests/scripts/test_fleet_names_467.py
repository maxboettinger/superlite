# tests/scripts/test_fleet_names_467.py
import hashlib, re, sys
from pathlib import Path
import pytest
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import fleet_state as fs  # noqa: E402

PAT = r"[a-z][a-z0-9_-]{0,31}"


def _repo(tmp_path, name="superlite"):
    r = tmp_path / name; (r / ".git").mkdir(parents=True); (r / ".superlite").mkdir()
    return r


def _worktree(repo, folder, admin=None):
    wt = repo / ".claude" / "worktrees" / folder; (wt / ".superlite").mkdir(parents=True)
    gd = repo / ".git" / "worktrees" / (admin or folder); gd.mkdir(parents=True)
    (wt / ".git").write_text(f"gitdir: {gd}\n", encoding="utf-8")
    return wt


def _h(p):
    return hashlib.sha1(str(Path(p).resolve()).encode()).hexdigest()[:4]


def test_main_checkout_is_repo_and_main(tmp_path):
    r = _repo(tmp_path)
    assert fs.run_names(r) == ("superlite", "main")
    assert fs.full_name(r / ".superlite", "final-reviewer") == "sl:superlite-main-final-reviewer"
    assert fs.full_name(r / ".superlite") == "sl:superlite-main"


def test_worktree_drops_the_repo_prefix(tmp_path):
    wt = _worktree(_repo(tmp_path), "superlite-b81-fleet-wait")
    assert fs.run_names(wt) == ("superlite", "b81-fleet-wait")
    assert fs.full_name(wt / ".superlite", "T3") == "sl:superlite-b81-fleet-wait-T3"


def test_worktree_without_the_prefix_keeps_its_folder_name(tmp_path):
    assert fs.run_names(_worktree(_repo(tmp_path), "hotfix", admin="hotfix1")) == ("superlite", "hotfix")


def test_relative_gitdir_and_a_subfolder_root(tmp_path):
    r = _repo(tmp_path); (r / ".git" / "worktrees" / "wt-x").mkdir(parents=True)
    wt = tmp_path / "wt-x"; (wt / "pkg").mkdir(parents=True)
    (wt / ".git").write_text("gitdir: ../superlite/.git/worktrees/wt-x\n", encoding="utf-8")
    assert fs.run_names(wt / "pkg") == ("superlite", "wt-x")


def test_bare_repo_worktree(tmp_path):
    bare = tmp_path / "tool.git"; gd = bare / "worktrees" / "tool-feat"; gd.mkdir(parents=True)
    wt = tmp_path / "tool-feat"; wt.mkdir(); (wt / ".git").write_text(f"gitdir: {gd}\n", encoding="utf-8")
    assert fs.run_names(wt) == ("tool", "feat")


def test_no_git_falls_back_to_the_folder_and_main(tmp_path):
    p = tmp_path / "proj"; p.mkdir()
    assert fs.run_names(p) == ("proj", "main")


def test_unreadable_git_file_falls_back(tmp_path):
    p = tmp_path / "proj"; p.mkdir(); (p / ".git").write_text("garbage\n", encoding="utf-8")
    assert fs.run_names(p) == ("proj", "main")


def test_submodule_counts_as_its_own_main_checkout(tmp_path):
    sup = _repo(tmp_path, "super"); m = sup / ".git" / "modules" / "lib"; m.mkdir(parents=True)
    sub = sup / "lib"; sub.mkdir(); (sub / ".git").write_text(f"gitdir: {m}\n", encoding="utf-8")
    assert fs.run_names(sub) == ("lib", "main")


def test_slug_lowercases_and_turns_odd_characters_into_one_dash():
    assert fs.slug("sl:Super Lite-main-W1", "W1") == "sl-super-lite-main-w1"
    assert fs.slug("sl:a..b--c-W2", "W2") == "sl-a-b-c-w2"
    assert fs.slug("sl:superlite-main-W1", "W1") == "sl-superlite-main-w1"


def test_slug_never_starts_with_a_non_letter():
    assert fs.slug("9lives") == "sl-9lives"
    assert fs.slug("") == "sl"
    assert re.fullmatch(PAT, fs.slug(":::-_x"))


def test_slug_cut_keeps_the_identifier_whole():
    assert fs.slug("sl:superlite-b102-agent-naming-W3", "W3") == "sl-superlite-b102-agent-namin-w3"
    assert fs.slug("sl:superlite-b102-agent-naming-lead", "lead") == "sl-superlite-b102-agent-nam-lead"
    assert fs.slug("sl:abcdefghijklmnopqrstuvwxy-z-W1", "W1") == "sl-abcdefghijklmnopqrstuvwxy-w1"


def test_slug_cuts_an_overlong_identifier_and_a_missing_one():
    n = fs.slug("sl:repo-main-" + "x" * 40, "x" * 40)
    assert len(n) <= 32 and re.fullmatch(PAT, n) and n.startswith("sl-") and n.endswith("x" * 28)
    assert fs.slug("sl:" + "a" * 40, "zz") == ("sl-" + "a" * 40)[:32]


def test_agent_name_is_the_slug_of_the_full_name(tmp_path):
    r = _repo(tmp_path)
    assert fs.agent_name(r / ".superlite", "W1") == "sl-superlite-main-w1"
    wt = _worktree(r, "superlite-b102-agent-naming")
    assert fs.agent_name(wt / ".superlite", "W3") == "sl-superlite-b102-agent-namin-w3"


def test_lead_is_named_by_its_worktree(tmp_path):
    r = _repo(tmp_path); wt = _worktree(r, "superlite-b102-agent-naming")
    assert fs.agent_name(r / ".superlite", "W5", root=wt, ident="lead") == "sl-superlite-b102-agent-nam-lead"
    taken = {"sl-superlite-b102-agent-nam-lead"}
    assert fs.agent_name(r / ".superlite", "W5", root=wt, ident="lead", taken=taken) == f"sl-superlite-b102-agen-{_h(wt)}-lead"


def test_a_taken_name_gets_the_run_hash(tmp_path):
    r = _repo(tmp_path); sd = r / ".superlite"
    plain = fs.agent_name(sd, "W1")
    assert fs.agent_name(sd, "W1", taken={plain}) == f"sl-superlite-main-{_h(r)}-w1"
    assert fs.agent_name(sd, "W1", taken={"sl-other-main-w1"}) == plain


def test_worktrees_with_a_long_shared_prefix_stay_apart_when_taken(tmp_path):
    """Spike S1: worktrees ...-phase-2 and -phase-3 cut to one readable name; the second start sees it taken."""
    r = _repo(tmp_path)
    a, b = _worktree(r, "superlite-fleet-leads-phase-2"), _worktree(r, "superlite-fleet-leads-phase-3")
    na = fs.agent_name(a / ".superlite", "W1")
    assert na == fs.agent_name(b / ".superlite", "W1") == "sl-superlite-fleet-leads-phas-w1"
    nb = fs.agent_name(b / ".superlite", "W1", taken={na})
    assert nb != na and re.fullmatch(PAT, nb) and nb.endswith("-w1")
    assert fs.agent_name(Path("/u/a/superlite/.superlite"), "W1", taken={"sl-superlite-main-w1"}) != \
        fs.agent_name(Path("/u/b/superlite/.superlite"), "W1", taken={"sl-superlite-main-w1"})
