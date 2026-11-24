"""A remote worker gets the files under .superlite/briefs/ its brief, prime or plan names, at the same path in its tree (#1067)."""
import sys
from test_fleet_remote_worker import world, start_files, show, plan_for  # noqa: F401
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import fleet_remote as fr  # noqa: E402
import fleet_remote_worker as rw  # noqa: E402


def refs(world):
    ref = world.sd / "briefs" / "ref" / "github" / "other"; (ref / "docs").mkdir(parents=True)
    (ref / "docs" / "spec.md").write_text("spec"); (ref / "README.md").write_text("readme")
    (world.sd / "briefs" / "notes.md").write_text("n"); (world.sd / "briefs" / "unnamed.md").write_text("u")
    return ref


def test_named_brief_files_lists_files_and_folder_contents(world):
    ref = refs(world)
    text = f"Read {ref}/docs/spec.md, the repo `{ref}` and .superlite/briefs/notes.md."
    assert rw.named_brief_files(world.sd, world.proj, [text]) == ["notes.md", "ref/github/other/README.md", "ref/github/other/docs/spec.md"]


def test_named_brief_files_ignores_escapes_and_missing(world):
    refs(world)
    text = f"{world.sd}/briefs/../fleet.json {world.sd}/briefs/gone.md {world.proj}/.superlite/briefs/notes.md"
    assert rw.named_brief_files(world.sd, world.proj, [text]) == ["notes.md"]


def test_spawn_ships_the_named_ref_files(world):
    ref = refs(world)
    b = world.sd / "briefs" / "r.md"; b.write_text(f"Answer from {ref}/docs/spec.md and {ref}/README.md.")
    rw.spawn(world.sd, "research", None, world.proj, "box", brief=str(b))
    names, start = start_files(world)
    assert {".superlite/briefs/ref/github/other/docs/spec.md", ".superlite/briefs/ref/github/other/README.md", ".superlite/briefs/r.md"} <= set(names)
    assert ".superlite/briefs/unnamed.md" not in names and ".superlite/briefs/notes.md" not in names
    assert show(world, start, ".superlite/briefs/ref/github/other/docs/spec.md") == "spec"


def test_implementer_ships_ref_files_its_prime_names(world):
    ref = refs(world)
    plan = plan_for(world)
    prime = world.sd / "prime.md"; prime.write_text(prime.read_text() + f"## Standing note\n    Reference: {ref}/README.md\n")
    rw.spawn(world.sd, "implementer", "sonnet", world.proj, "box", task="T3", plan=str(plan))
    names, _ = start_files(world)
    assert ".superlite/briefs/ref/github/other/README.md" in names and ".superlite/briefs/ref/github/other/docs/spec.md" not in names


def test_send_brief_ships_the_named_ref_files(world):
    ref = refs(world)
    rw.spawn(world.sd, "research", None, world.proj, "box")
    b = world.sd / "briefs" / "q.md"; b.write_text(f"Read the repo at {ref}.")
    rw.send_brief(world.sd, "W1", str(b), "Q1")
    tree = world.trees / fr.tree_name(world.sd, "W1")
    assert (tree / ".superlite/briefs/ref/github/other/docs/spec.md").read_text() == "spec"
    assert (tree / ".superlite/remote/W1/briefs/q.md").read_text() == f"Read the repo at {tree}/.superlite/briefs/ref/github/other."
    assert not (tree / ".superlite/briefs/unnamed.md").exists()


def test_docs_name_the_rule():
    text = (SCRIPTS.parents[2] / "docs" / "fleet.md").read_text(encoding="utf-8")
    assert "(#1067)" in text and "`.superlite/briefs/ref/`" in text and "at the same path in its tree" in text
