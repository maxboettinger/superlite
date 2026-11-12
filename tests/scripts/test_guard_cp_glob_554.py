"""Guard false block (#554): cp and mv of a glob into a folder judge the glob's extension."""
from test_block_coordinator_edits import bash, proj  # noqa: F401


def test_cp_md_glob_into_docs(proj):
    (proj / "docs" / "x").mkdir(parents=True, exist_ok=True)
    assert bash(proj, "cp a/*.md docs/x/").returncode == 0
    assert bash(proj, "cp a/*.py docs/x/").returncode == 2
    assert bash(proj, "mv docs/a/*.md docs/x").returncode == 0
    assert bash(proj, "cp a/* docs/x/").returncode == 2
