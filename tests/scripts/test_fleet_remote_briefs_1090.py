"""A remote worker gets the run's whole briefs folder, also files written later, and the host's plugin path in every brief (#1090)."""
import json
import sys
from pathlib import Path
from test_fleet_remote_worker import world, start_files, show, plan_for  # noqa: F401
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import fleet_remote as fr  # noqa: E402
import fleet_remote_worker as rw  # noqa: E402

SL = "skills/subagent-driven-development/scripts/sl run_tests"


def pushes(world, wid="W1"):
    name = fr.tree_name(world.sd, wid)
    es = [json.loads(x) for x in (world.tmp / "log").read_text().splitlines()]
    return [e["argv"] for e in es if e["argv"][0] == "push" and name in e["argv"]]


def files_of(argv):
    return [argv[i + 1] for i, a in enumerate(argv) if a == "--file"]


def spawn_folder(world):
    b = world.sd / "briefs"
    (b / "r.md").write_text("the brief"); (b / "unnamed.md").write_text("u")
    (b / "ref" / "x").mkdir(parents=True); (b / "ref" / "x" / "README.md").write_text("readme")
    out = world.tmp / "outside.md"; out.write_text("secret"); (b / "link.md").symlink_to(out)
    return b / "r.md"


def test_spawn_ships_the_whole_briefs_folder(world):
    brief = spawn_folder(world)
    rw.spawn(world.sd, "research", None, world.proj, "box", brief=str(brief))
    names, start = start_files(world)
    assert show(world, start, ".superlite/briefs/unnamed.md") == "u" and show(world, start, ".superlite/briefs/ref/x/README.md") == "readme"
    assert ".superlite/briefs/link.md" not in names
    sent = json.loads((world.sd / "remote" / "W1" / "briefs-sent.json").read_text())
    assert sorted(sent) == ["r.md", "ref/x/README.md", "unnamed.md"]


def test_briefs_listing_and_delta(world):
    spawn_folder(world)
    got = rw.briefs_listing(world.sd)
    assert sorted(got) == ["r.md", "ref/x/README.md", "unnamed.md"] and got["unnamed.md"][0] == 1
    assert rw.briefs_delta(world.sd, "W9")[0] == sorted(got)
    assert rw.briefs_delta(world.sd, "W9", frozenset({"r.md"}))[0] == ["ref/x/README.md", "unnamed.md"]


def test_send_brief_ships_files_written_after_spawn(world):
    spawn_folder(world)
    rw.spawn(world.sd, "research", None, world.proj, "box")
    (world.sd / "briefs" / "later.md").write_text("later")
    q = world.sd / "briefs" / "q.md"; q.write_text("question")
    rw.send_brief(world.sd, "W1", str(q), "Q1")
    tree = world.trees / fr.tree_name(world.sd, "W1")
    assert (tree / ".superlite/briefs/later.md").read_text() == "later"
    files = files_of(pushes(world)[-1])
    assert ".superlite/briefs/later.md" in files and ".superlite/remote/W1/briefs/q.md" in files and ".superlite/briefs/unnamed.md" not in files


def test_send_task_ships_new_briefs_files(world):
    plan = plan_for(world)
    rw.spawn(world.sd, "implementer", "sonnet", world.proj, "box", task="T3", plan=str(plan))
    (world.sd / "briefs" / "addendum.md").write_text("more")
    rw.send_task(world.sd, "W1", str(plan), ["T3"], "sl")
    tree = world.trees / fr.tree_name(world.sd, "W1")
    assert (tree / ".superlite/briefs/addendum.md").read_text() == "more"


def test_unchanged_briefs_are_not_pushed_twice(world):
    spawn_folder(world)
    rw.spawn(world.sd, "research", None, world.proj, "box")
    (world.sd / "briefs" / "later.md").write_text("later")
    for n in ("q1.md", "q2.md"):
        q = world.sd / "briefs" / n; q.write_text(n)
        rw.send_brief(world.sd, "W1", str(q), n)
    assert files_of(pushes(world)[-1]) == [".superlite/remote/W1/briefs/q2.md", ".superlite/briefs/q1.md"]  # q1 was pushed mapped only, so q2's send ships it raw (F-T1-1)
    rw.send_brief(world.sd, "W1", str(world.sd / "briefs" / "q2.md"), "q2")
    assert files_of(pushes(world)[-1]) == [".superlite/remote/W1/briefs/q2.md"]


def test_outside_sd_pushes_no_briefs_files(world, tmp_path):
    sd = tmp_path / "osd"; (sd / "briefs").mkdir(parents=True)
    (sd / "prime.md").write_text("prime")
    (sd / "briefs" / "other.md").write_text("o")
    rw.spawn(sd, "research", None, world.proj, "box")
    (sd / "briefs" / "later.md").write_text("later")
    q = world.proj / "q.md"; q.write_text("question")
    rw.send_brief(sd, "W1", str(q), "Q1")
    last = [e["argv"] for e in map(json.loads, (world.tmp / "log").read_text().splitlines()) if e["argv"][0] == "push"][-1]
    assert files_of(last) and not [f for f in files_of(last) if "other.md" in f or "later.md" in f]


def test_send_brief_maps_the_plugin_path(world):
    rw.spawn(world.sd, "research", None, world.proj, "box")
    q = world.sd / "briefs" / "q.md"; q.write_text(f"Run {rw.SUPERLITE_ROOT}/{SL}")
    rw.send_brief(world.sd, "W1", str(q), "Q1")
    plugin = rw.fs.load(world.sd)["workers"]["W1"]["remote"]["plugin"]
    tree = world.trees / fr.tree_name(world.sd, "W1")
    assert (tree / ".superlite/remote/W1/briefs/q.md").read_text() == f"Run {plugin}/{SL}"


def test_tilde_plugin_path_is_mapped(world, monkeypatch, tmp_path):
    home = tmp_path / "hm"; root = home / "github" / "superlite"; root.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home)); monkeypatch.setattr(rw, "SUPERLITE_ROOT", str(root))
    plugin = rw.fr.plugin("box", str(root))
    text = f"Run ~/github/superlite/{SL}"
    b = world.sd / "briefs" / "r.md"; b.write_text(text)
    rw.spawn(world.sd, "research", None, world.proj, "box", brief=str(b))
    _, start = start_files(world)
    assert show(world, start, ".superlite/briefs/r.md") == f"Run {plugin}/{SL}"
    q = world.sd / "briefs" / "q.md"; q.write_text(text)
    rw.send_brief(world.sd, "W1", str(q), "Q1")
    tree = world.trees / fr.tree_name(world.sd, "W1")
    assert (tree / ".superlite/remote/W1/briefs/q.md").read_text() == f"Run {plugin}/{SL}"


def test_pairs_tilde_forms(monkeypatch):
    monkeypatch.setenv("HOME", "/u"); monkeypatch.setattr(rw, "SUPERLITE_ROOT", "/u/github/superlite")
    got = rw._pairs(Path("/w/p/.superlite"), Path("/w/p"), "/h/t", "/h/plug", None)
    assert ("/w/p", "/h/t") in got and ("/u/github/superlite", "/h/plug") in got and ("~/github/superlite", "/h/plug") in got


def test_docs_name_1090():
    text = (SCRIPTS.parents[2] / "docs" / "fleet.md").read_text(encoding="utf-8")
    assert "(#1090)" in text and "briefs-sent.json" in text
