"""Eval suite layout: cases, graders, frontmatter keys, scaffolds, runner flags."""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVALS = ROOT / "evals"
CASES = {"brainstorm-first", "setup-report", "debug-flow", "brainstorm-coverage",
         "ai-asks-once", "ai-bounded-quiet", "feature-routing"}
PROMPT_KEYS = {"schema_version", "name", "description", "tags", "plugins", "runs", "expected_outcome", "model",
               "max_turns", "timeout_seconds", "allowed_tools", "append_system_prompt", "env"}
GRADER_TYPES = {"regex", "tool_used", "tool_order", "file_exists", "llm", "baseline"}


def parse_lines(text: str) -> dict:
    out = {}
    for line in text.splitlines():
        if ":" in line and not line.lstrip().startswith("#"):
            key, _, value = line.strip().partition(":")
            out[key.strip()] = value.strip().strip("\"'")
    return out


def frontmatter(path: Path) -> dict:
    text = path.read_text()
    if not text.startswith("---\n"):
        return {}
    return parse_lines(text.split("---\n")[1])


def case_dirs():
    return sorted(p for p in EVALS.iterdir() if p.is_dir() and ((p / "prompt.md").exists() or (p / "case.yaml").exists()))


def test_every_case_has_prompt_and_grader():
    dirs = case_dirs()
    assert {p.name for p in dirs} == CASES
    for d in dirs:
        assert (d / "prompt.md").exists(), d
        assert list((d / "graders").glob("*.md")), d


def test_frontmatter_keys_are_known():
    for d in case_dirs():
        assert set(frontmatter(d / "prompt.md")) <= PROMPT_KEYS, d
        for g in (d / "graders").glob("*.md"):
            assert frontmatter(g).get("type") in GRADER_TYPES, g
        settings = frontmatter(d / "prompt.md") if not (d / "case.yaml").exists() else parse_lines((d / "case.yaml").read_text())
        assert settings["model"] == "sonnet", d
        assert settings["runs"] == ("3" if d.name == "debug-flow" else "2"), d


def test_scaffold_scripts_are_executable_bash(tmp_path):
    scripts = sorted(EVALS.glob("*/scaffold.sh"))
    assert {s.parent.name for s in scripts} == {"setup-report", "debug-flow", "brainstorm-coverage", "ai-asks-once",
                                                     "ai-bounded-quiet", "feature-routing"}
    for s in scripts:
        assert s.read_text().startswith("#!/usr/bin/env bash")
        assert os.access(s, os.X_OK), s
        assert subprocess.run(["bash", "-n", str(s)]).returncode == 0
        work = tmp_path / s.parent.name
        work.mkdir()
        subprocess.run([str(s)], cwd=work, check=True)
        assert (work / "pyproject.toml").exists()
        assert (work / "tests").is_dir()
    debug = tmp_path / "debug-flow"
    assert "return 28" in (debug / "src/calc/core.py").read_text()
    assert "2024" in (debug / "tests/test_core.py").read_text()
    assert "pythonpath" in (debug / "pyproject.toml").read_text()
    assert (tmp_path / "setup-report/src/app/__init__.py").exists()
    for name in ("ai-asks-once", "ai-bounded-quiet", "feature-routing"):
        assert (tmp_path / name / "src/notes/cli.py").exists(), name
        assert 'version = "1.2.3"' in (tmp_path / name / "pyproject.toml").read_text(), name


def test_runner_flags():
    text = (ROOT / "scripts/evals.sh").read_text()
    for flag in ("--trust-plugin", "--no-publish", "--scaffold", "--judge-model haiku", "--max-cost-usd",
                 "--json evals/results/last.json"):
        assert flag in text, flag
    assert "evals/results/" in (ROOT / ".gitignore").read_text().splitlines()
    assert os.access(ROOT / "scripts/evals.sh", os.X_OK)


def test_case_yaml_is_optional_when_prompt_md_has_the_run_fields():
    required = ("model", "runs", "max_turns", "allowed_tools")
    brainstorm = frontmatter(EVALS / "brainstorm-first" / "prompt.md")
    for key in required:
        assert key in brainstorm, key
    for d in case_dirs():
        if not (d / "case.yaml").exists():
            fm = frontmatter(d / "prompt.md")
            for key in required:
                assert key in fm, (d, key)


def test_regex_graders_nest_file_targets_under_target():
    for d in case_dirs():
        for g in (d / "graders").glob("*.md"):
            fm = frontmatter(g)
            if fm.get("type") != "regex":
                continue
            assert "source" not in fm and "path" not in fm, g
            if "source" in fm.get("target", ""):
                assert "path" in fm["target"], g


def test_ai_cases_grade_outcomes():
    once = EVALS / "ai-asks-once" / "graders"
    for name in ("no-code-edit", "no-code-write"):
        fm = frontmatter(once / f"{name}.md")
        assert fm["type"] == "tool_used" and fm["min"] == "0" and fm["max"] == "0" and fm["arm"] == "both", name
        pattern = re.compile(fm["input_match"])
        assert pattern.search('"file_path": "/x/src/notes/cli.py"'), name
        assert not pattern.search('"file_path": "/x/docs/plan.md"'), name
    for name in ("raises-decisions", "one-batch"):
        fm = frontmatter(once / f"{name}.md")
        assert fm["type"] == "llm" and fm.get("criteria"), name
    one_batch = frontmatter(once / "one-batch.md")
    assert "requests to enable a denied tool or permission are not counted" in one_batch["criteria"]
    quiet = EVALS / "ai-bounded-quiet" / "graders"
    assert frontmatter(quiet / "no-questions.md")["type"] == "llm"
    fm = frontmatter(quiet / "changed.md")
    assert fm["type"] == "regex"
    assert "source: file" in fm["target"] and "path: src/notes/cli.py" in fm["target"]
    assert fm["pattern"] == "--version"


def test_ai_prompts_name_the_orchestrator():
    for name in ("ai-asks-once", "ai-bounded-quiet"):
        text = (EVALS / name / "prompt.md").read_text()
        assert "AI orchestrator" in text and "I am at my desk" in text, name
        assert not text.startswith("/"), name


def test_testing_doc_counts_cases():
    row = next(l for l in (ROOT / "docs/testing.md").read_text().splitlines() if l.startswith("| evals"))
    assert "six cases" in row
