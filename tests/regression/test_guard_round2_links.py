import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"))

import guard_files  # noqa: E402
from guard_judge import judge  # noqa: E402


@pytest.fixture
def proj(tmp_path):
    p = tmp_path / "proj"
    (p / ".superlite").mkdir(parents=True)
    (p / "docs" / "plans").mkdir(parents=True)
    (p / "src").mkdir()
    (p / ".superlite" / "orchestrator.json").write_text("{}")
    (p / "src" / "a.py").write_text("")
    (p / "docs" / "plans" / "x.md").write_text("")
    return os.path.realpath(p)


def _blocked(proj, cmd, mode="human", cwd=None):
    v = judge(cmd, cwd or proj, proj, mode)
    return v is not None


LINKS = [
    "ln -s ../../.superlite/orchestrator.json docs/plans/a.review.md",
    "ln -s .superlite/orchestrator.json docs/plans/a.review.md",
    "ln .superlite/orchestrator.json docs/plans/a.review.md",
    "link .superlite/orchestrator.json docs/plans/a.review.md",
    "cp -s ../../.superlite/orchestrator.json docs/plans/a.review.md",
    "cp -l .superlite/orchestrator.json docs/plans/a.review.md",
    "cp -al .superlite/orchestrator.json docs/plans/a.review.md",
    "cp --link .superlite/orchestrator.json docs/plans/a.review.md",
    "cp --symbolic-link .superlite/orchestrator.json docs/plans/a.review.md",
    "ln -s ../../.superlite docs/plans/d.review.md",
    "ln -sf -t docs/plans ../../.superlite/orchestrator.json",
    "ln -s .superlite/orch* docs/plans/a.review.md",
]


@pytest.mark.parametrize("cmd", LINKS)
@pytest.mark.parametrize("mode", ["human", "active"])
def test_a_link_to_a_protected_file_blocks(proj, cmd, mode):
    assert _blocked(proj, cmd, mode), cmd


def test_a_link_from_inside_the_run_folder(proj):
    assert _blocked(proj, "ln -s orchestrator.json ../docs/plans/a.review.md", cwd=proj + "/.superlite")
    assert _blocked(proj, "cd .superlite && ln orchestrator.json ../docs/plans/a.review.md")


@pytest.mark.parametrize("cmd", [
    "ln -s ../a.md docs/plans/b.review.md",
    "ln -s ../../src/a.py docs/plans/b.review.md",
    "cp -l docs/plans/x.md docs/plans/y.review.md",
    "cp -s ../x.md docs/plans/y.review.md",
    "ln -s /usr/bin/env docs/plans/env.review.md",
])
def test_a_link_to_an_ordinary_file_is_not_a_protected_hit(proj, cmd):
    v = judge(cmd, proj, proj, "human")
    assert v is None or v.kind != "protected", cmd


def test_link_sources_in_guard_files():
    f = guard_files.link_sources
    assert f(["ln", "-s", "a", "b"]) == ["a"]
    assert f(["ln", "a"]) == ["a"]
    assert f(["ln", "-t", "d", "a", "b"]) == ["a", "b"]
    assert f(["cp", "-l", "a", "b"]) == ["a"]
    assert f(["cp", "--symbolic-link", "a", "b"]) == ["a"]
    assert f(["cp", "a", "b"]) == []
    assert f(["cp", "-r", "a", "b"]) == []


FOLDERS = [
    "rsync -a /tmp/p/ .superlite/",
    "rsync -a /tmp/p/ .superlite",
    "cp -r /tmp/p/. .superlite/",
    "cp -r /tmp/p/ .superlite/",
    "tar -xf a.tar -C .superlite",
    "tar -xf a.tar --directory=.superlite",
    "unzip -d .superlite a.zip",
    "unzip a.zip -d .superlite",
    "mv /tmp/p/* .superlite/",
    "cd .superlite && tar -xf /tmp/a.tar",
]


@pytest.mark.parametrize("cmd", FOLDERS)
def test_a_folder_target_that_holds_a_protected_file_blocks_in_human_mode(proj, cmd):
    assert _blocked(proj, cmd, "human"), cmd


@pytest.mark.parametrize("cmd", [
    "cp /tmp/p/f .superlite/",
    "cp /tmp/p/f .superlite/notes.md",
    "cp -r /tmp/p .superlite/fixes/",
    "rsync -a /tmp/p/ .superlite/fixes/",
    "tar -xf a.tar -C .superlite/fixes",
])
def test_a_named_file_or_a_deeper_folder_still_passes_in_run_folder(proj, cmd):
    os.makedirs(proj + "/.superlite/fixes", exist_ok=True)
    assert not _blocked(proj, cmd, "human"), cmd
