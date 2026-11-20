"""fleet spawn refuses a brief naming paths outside the project, the run folder and the plugin skills folder, before any pane starts (#1015)."""
import json
import types
import pytest
from test_fleet import world, SCRIPTS  # noqa: F401
from test_plan_tools import make_plan
import fleet  # noqa: E402
import fleet_roles  # noqa: E402

TAIL = "a worker cannot read them: copy each file into"


@pytest.fixture
def roots(tmp_path, monkeypatch):
    proj = tmp_path / "proj"; sd = proj / ".superlite"; sd.mkdir(parents=True)
    (proj / "docs").mkdir(); (proj / "docs" / "x.md").write_text("x")
    skills = tmp_path / "plug" / "skills"; (skills / "a").mkdir(parents=True); (skills / "a" / "SKILL.md").write_text("x")
    other = tmp_path / "other"; other.mkdir(); (other / "spec.md").write_text("spec")
    monkeypatch.setattr(fleet_roles, "SKILLS", skills)
    return types.SimpleNamespace(proj=proj, sd=sd, skills=skills, other=other, tmp=tmp_path)


def test_outside_path_is_named(roots):
    assert fleet.outside_paths(f"Read {roots.other}/spec.md first.\n", roots.proj, roots.sd) == [f"{roots.other}/spec.md"]


def test_inside_paths_are_not_named(roots):
    text = f"Read {roots.proj}/docs/x.md, {roots.sd}/briefs/b.md and `{roots.skills}/a/SKILL.md`; also docs/x.md.\n"
    assert fleet.outside_paths(text, roots.proj, roots.sd) == []


def test_new_file_in_an_existing_outside_folder_is_named(roots):
    assert fleet.outside_paths(f"Write {roots.other}/new.md\n", roots.proj, roots.sd) == [f"{roots.other}/new.md"]


def test_prose_urls_and_commands_are_not_paths(roots):
    text = ("Run /superlite:review and /commit-merge, see https://github.com/a/b and read/write it.\n"
            "Pipe to 2>/dev/null; call /usr/bin/env python3; never /etc/hosts.\n"
            "Templates: <tree>/.build/DerivedData and Read(//<plugin root>/skills/**).\n"
            f"Gone: {roots.tmp}/missing/deep/file.md\n")
    assert fleet.outside_paths(text, roots.proj, roots.sd) == []


def test_home_and_parent_relative_paths_count(roots, monkeypatch):
    monkeypatch.setenv("HOME", str(roots.tmp))
    text = "Read ~/other/spec.md, ../other/spec.md and ../proj/docs/x.md.\n"
    assert fleet.outside_paths(text, roots.proj, roots.sd) == ["~/other/spec.md", "../other/spec.md"]


def test_file_urls_globs_and_duplicates(roots):
    text = f"[spec](file://{roots.other}/spec.md) then `{roots.other}/**` and {roots.other}/spec.md again.\n"
    assert fleet.outside_paths(text, roots.proj, roots.sd) == [f"{roots.other}/spec.md", f"{roots.other}"]


def test_skills_argument_overrides_the_default(roots, tmp_path):
    assert fleet.outside_paths(f"Read {roots.skills}/a/SKILL.md\n", roots.proj, roots.sd, skills=tmp_path / "elsewhere") == [f"{roots.skills}/a/SKILL.md"]


def test_error_names_at_most_five():
    msg = fleet.outside_error("brief", "/r/b.md", ["/a", "/b", "/c", "/d", "/e", "/f", "/g"], "/r/.superlite")
    assert msg == ("error: brief /r/b.md names paths outside the project, the run folder and the plugin skills folder: "
                   "/a, /b, /c, /d, /e and 2 more; a worker cannot read them: copy each file into /r/.superlite/briefs/ "
                   "and name the copy, or drop the path (#1015)")
    assert fleet.outside_error("note", "/r/n.md", ["/a"], "/r/.superlite").startswith("error: note /r/n.md names paths outside the project, the run folder and the plugin skills folder: /a; ")


def _other(tmp_path):
    other = tmp_path / "other"; other.mkdir(); (other / "spec.md").write_text("s")
    return other


def _brief(world, text, name="R1.md"):
    b = world.sd / "briefs" / name; b.parent.mkdir(exist_ok=True); b.write_text(text)
    return b


def test_spawn_refuses_brief_naming_outside_path(world, capsys, tmp_path):
    fleet.main(["on"])
    other = _other(tmp_path)
    brief = _brief(world, f"Read {other}/spec.md.\n")
    n = len(world.fh.calls)
    assert fleet.main(["spawn", "--role", "research", "--brief", str(brief), "--plan", str(world.sd)]) == 2
    err = capsys.readouterr().err
    assert f"error: brief {brief.resolve()} names paths outside the project, the run folder and the plugin skills folder: {other}/spec.md; {TAIL}" in err
    assert len(world.fh.calls) == n
    assert json.loads((world.sd / "fleet.json").read_text()).get("workers", {}) == {}


@pytest.mark.parametrize("role", ["implementer", "fixer", "writer", "checker", "final-reviewer"])
def test_every_worker_role_is_checked(world, capsys, tmp_path, role):
    fleet.main(["on"])
    other = _other(tmp_path)
    brief = _brief(world, f"Read {other}/spec.md.\nOutput: out.md\n")
    n = len(world.fh.calls)
    assert fleet.main(["spawn", "--role", role, "--brief", str(brief), "--plan", str(world.sd)]) == 2
    assert f"{other}/spec.md; {TAIL}" in capsys.readouterr().err
    assert len(world.fh.calls) == n


def test_spawn_with_inside_paths_still_starts(world, monkeypatch):
    fleet.main(["on"])
    brief = _brief(world, f"Read {world.proj}/src/a.py and {world.sd}/briefs/x.md.\n")
    monkeypatch.setattr(fleet, "spawn", lambda *a, **k: {"id": "W1"})
    import fleet_io
    monkeypatch.setattr(fleet_io, "send_brief", lambda *a, **k: None)
    assert fleet.main(["spawn", "--role", "research", "--brief", str(brief), "--plan", str(world.sd)]) == 0


def test_global_constraints_are_checked_too(world, capsys, tmp_path):
    fleet.main(["on"])
    other = _other(tmp_path)
    plan = make_plan(world.proj, [{"id": "T1", "owns": "src/a.py"}], header=f"\nGlobal constraints:\n- The spec is {other}/spec.md.\n")
    brief = _brief(world, "Answer the question.\n")
    n = len(world.fh.calls)
    assert fleet.main(["spawn", "--role", "research", "--brief", str(brief), "--plan", str(plan)]) == 2
    assert f"{other}/spec.md; {TAIL}" in capsys.readouterr().err
    assert len(world.fh.calls) == n


def test_brief_file_outside_is_refused(world, capsys, tmp_path):
    fleet.main(["on"])
    b = tmp_path / "b.md"; b.write_text("Answer the question.\n")
    n = len(world.fh.calls)
    assert fleet.main(["spawn", "--role", "research", "--brief", str(b), "--plan", str(world.sd)]) == 2
    assert (f"error: brief {b.resolve()} is outside the project, the run folder and the plugin skills folder; a worker cannot read it: "
            f"move it into {world.sd.resolve()}/briefs/ (#1015)") in capsys.readouterr().err
    assert len(world.fh.calls) == n


def test_review_note_naming_outside_path_is_refused(world, capsys, tmp_path):
    fleet.main(["on"])
    other = _other(tmp_path)
    note = world.proj / "note.md"; note.write_text(f"Compare with {other}/spec.md.\n")
    n = len(world.fh.calls)
    assert fleet.main(["spawn", "--for-review", "T1", "--note", str(note), "--plan", str(world.plan)]) == 2
    assert f"error: note {note.resolve()} names paths outside the project, the run folder and the plugin skills folder: {other}/spec.md; {TAIL}" in capsys.readouterr().err
    assert len(world.fh.calls) == n


def test_lead_brief_is_not_checked(world, monkeypatch, tmp_path):
    fleet.main(["on"])
    other = _other(tmp_path)
    brief = _brief(world, f"Read {other}/spec.md.\n", "lead.md")
    import fleet_lead
    monkeypatch.setattr(fleet_lead, "start_plan_lead", lambda *a, **k: (0, "W1"))
    assert fleet.main(["spawn", "--role", "lead", "--plan", str(world.plan), "--brief", str(brief)]) == 0


def test_docs_name_the_refusal():
    doc = (SCRIPTS.parents[2] / "docs" / "fleet.md").read_text(encoding="utf-8")
    assert "`fleet spawn` refuses a brief that names one before any pane starts" in doc and "#1015" in doc
    assert "(#1015)" in fleet.__doc__


@pytest.mark.parametrize("fence", ["```diff", "~~~", "````"])
def test_fenced_code_blocks_are_skipped(roots, fence):
    close = "~~~" if fence.startswith("~") else fence[:3] + fence[3:].replace("diff", "")
    inner = f"+ see {roots.other}/spec.md\n"
    assert fleet.outside_paths(f"Review:\n{fence}\n{inner}{close}\n", roots.proj, roots.sd) == []
    assert fleet.outside_paths(f"{fence}\n{inner}{close}\nThen read {roots.other}/spec.md.\n", roots.proj, roots.sd) == [f"{roots.other}/spec.md"]
    assert fleet.outside_paths(f"{fence}\n{inner}", roots.proj, roots.sd) == []


def test_inline_code_spans_still_count(roots):
    assert fleet.outside_paths(f"Read `{roots.other}/spec.md`.\n", roots.proj, roots.sd) == [f"{roots.other}/spec.md"]


def test_spawn_calls_fleet_io_brief_refusal(world, capsys, monkeypatch):
    fleet.main(["on"])
    import fleet_io
    seen = []
    def stub(sd, brief, role="", plan=None):
        seen.append((str(sd), str(brief), role, plan))
        return "error: stub refusal (#1027)"
    monkeypatch.setattr(fleet_io, "brief_refusal", stub)
    brief = _brief(world, "Answer the question.\n")
    n = len(world.fh.calls)
    assert fleet.main(["spawn", "--role", "research", "--brief", str(brief), "--plan", str(world.plan)]) == 2
    assert "error: stub refusal (#1027)" in capsys.readouterr().err
    assert len(world.fh.calls) == n
    assert len(seen) == 1 and seen[0][1:3] == (str(brief), "research")
    assert seen[0][3] is not None and str(seen[0][3]) == str(world.plan)


def test_location_message_lives_only_in_fleet_io():
    lit = "is outside the project, the run folder and the plugin skills folder; a worker cannot read it"
    assert lit not in (SCRIPTS / "fleet.py").read_text(encoding="utf-8")
    assert (SCRIPTS / "fleet_io.py").read_text(encoding="utf-8").count(lit) == 1


def test_brief_and_constraint_paths_share_one_line(world, capsys, tmp_path):
    fleet.main(["on"])
    other = _other(tmp_path); (other / "notes.md").write_text("n")
    plan = make_plan(world.proj, [{"id": "T1", "owns": "src/a.py"}], header=f"\nGlobal constraints:\n- The spec is {other}/spec.md.\n")
    brief = _brief(world, f"Read {other}/notes.md.\n")
    assert fleet.main(["spawn", "--role", "research", "--brief", str(brief), "--plan", str(plan)]) == 2
    assert f"the plugin skills folder: {other}/notes.md, {other}/spec.md; {TAIL}" in capsys.readouterr().err
    assert brief.read_text() == f"Read {other}/notes.md.\n"
