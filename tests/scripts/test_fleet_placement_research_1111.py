"""A research worker whose brief names a read-only reference path stays local (#1111)."""
import sys
from test_fleet_placement import env, workers  # noqa: F401 (env is the fixture)
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_brief as bb  # noqa: E402
import fleet_placement as fp  # noqa: E402

LINE = ("placement: research worker stays local: its brief may name a read-only reference path from the lead brief's research line, "
        "which only this machine has (#1111)")


def setup(env, tmp_path, text, lead=True):
    ref = tmp_path / "ref"; ref.mkdir(); (ref / "notes.md").write_text("n")
    ref2 = tmp_path / "ref2"; ref2.mkdir(); (ref2 / "x.md").write_text("x")
    (env.sd / "briefs").mkdir(exist_ok=True)
    if lead:
        (env.sd / "briefs" / "lead.md").write_text(bb.REF_READ.format(items=str(ref)) + "\n")
    b = env.sd / "briefs" / "R1.md"
    if text is not None:
        b.write_text(text.format(ref=ref, ref2=ref2))
    workers(env, None, None, None)
    return b


def test_research_brief_naming_read_path_stays_local(env, tmp_path, capsys):
    b = setup(env, tmp_path, "Read {ref}/notes.md and answer.")
    assert fp.choose(env.sd, "research", env.proj, now=1.0, brief=b) is None
    assert LINE in capsys.readouterr().err


def test_research_brief_naming_read_folder_stays_local(env, tmp_path):
    b = setup(env, tmp_path, "Read {ref} and answer.")
    assert fp.choose(env.sd, "research", env.proj, now=1.0, brief=b) is None


def test_research_brief_without_read_path_is_placed(env, tmp_path, capsys):
    b = setup(env, tmp_path, "Read src/a.py.")
    assert fp.choose(env.sd, "research", env.proj, now=1.0, brief=b) == "box"
    assert "#1111" not in capsys.readouterr().err


def test_sibling_path_is_no_match(env, tmp_path):
    b = setup(env, tmp_path, "Read {ref2}/x.md.")
    assert fp.choose(env.sd, "research", env.proj, now=1.0, brief=b) == "box"


def test_research_without_brief_stays_local_when_reads_exist(env, tmp_path):
    setup(env, tmp_path, None)
    assert fp.choose(env.sd, "research", env.proj, now=1.0, brief=None) is None


def test_no_research_line_places_research(env, tmp_path):
    setup(env, tmp_path, None, lead=False)
    assert fp.choose(env.sd, "research", env.proj, now=1.0) == "box"
    assert fp.research_local(env.sd, env.proj, None) is False


def test_implementer_ignores_research_line(env, tmp_path):
    b = setup(env, tmp_path, "Read {ref}/notes.md and answer.")
    assert fp.choose(env.sd, "implementer", env.proj, now=1.0, brief=b) == "box"


def test_unreadable_brief_stays_local(env, tmp_path):
    setup(env, tmp_path, None)
    assert fp.research_local(env.sd, env.proj, env.sd / "briefs" / "missing.md") is True
