# tests/scripts/test_judge_housekeeping.py
import io, json, os, subprocess, sys
import pytest
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import guard_judge as gj  # noqa: E402

BLOCK_LINE = ("- New code belongs to an implementer task. You may write only docs/plans/**, docs/*/plans/**, SPEC*.md, "
              "docs/**/*.md, docs/** images (png, jpg, jpeg, gif, svg, webp), any docs.md and .superlite/**, and rm a "
              "file git does not track and no task Owns.")


def git(P, *a):
    subprocess.run(["git", "-C", str(P), "-c", "user.email=t@t", "-c", "user.name=t", *a], check=True,
                   capture_output=True)


@pytest.fixture
def P(tmp_path):
    p = tmp_path / "proj"
    (p / "src").mkdir(parents=True)
    (p / "docs" / "x").mkdir(parents=True)
    (p / ".superlite").mkdir()
    (p / ".superlite" / "pool.json").write_text("{}")
    (p / "docs" / "plans").mkdir()
    plan = p / "docs" / "plans" / "plan.md"
    plan.write_text("# Plan\n\n### T1 a\n**Owns:** src/a.py, src/new.py\n")
    (p / "src" / "a.py").write_text("x = 1\n")
    (p / ".gitignore").write_text("build/\n")
    subprocess.run(["git", "init", "-q", str(p)], check=True)
    git(p, "add", "-A")
    git(p, "commit", "-q", "-m", "init")
    (p / ".superlite" / "stable.json").write_text(json.dumps({"plan": str(plan), "stable": []}))
    return p


def j(P, cmd, mode="active", cwd=None):
    return gj.judge(cmd, cwd=str(cwd or P), project=str(P), mode=mode, sds=(str(P / ".superlite"),))


def test_doc_images_pass(P):
    for cmd in ("cp /tmp/a.png docs/x/a.png", "rm docs/x/a.png", "mv docs/a.svg docs/b/a.webp", "cp a.jpg docs/"):
        assert j(P, cmd) is None, cmd


def test_images_outside_docs_and_human_mode_block(P):
    assert j(P, "cp /tmp/a.png src/a.png").kind == "code"
    assert j(P, "cp /tmp/a.png docs/x/a.png", mode="human").kind == "human"
    assert j(P, "cp /tmp/a.png docs/../src/a.png").kind == "code"


def test_rm_untracked_unowned_file_passes(P):
    (P / "src" / "a.py-E").write_text("x")
    assert j(P, "rm src/a.py-E") is None
    assert j(P, "rm -f src/a.py-E") is None
    assert j(P, "unlink src/a.py-E") is None


def test_rm_ignored_file_passes(P):
    (P / "build").mkdir()
    (P / "build" / "out.bin").write_text("x")
    assert j(P, "rm build/out.bin") is None


def test_rm_blocks_on_any_doubt(P):
    s = P / "src"
    (s / "a.py-E").write_text("x")
    (s / "new.py").write_text("x")
    (s / "tmpdir").mkdir()
    (s / "tmpdir" / "f").write_text("x")
    os.symlink(s / "a.py", s / "link-E")
    for cmd in ("rm src/a.py", "rm src/new.py", "rm src/a.py-E src/a.py", "rm src/*.py-E", "rm -r src/tmpdir",
                "rm src/link-E"):
        assert j(P, cmd).kind == "code", cmd
    assert j(P, "rm src/a.py-E", mode="human").kind == "human"
    st = P / ".superlite" / "stable.json"
    st.write_text(json.dumps({"plan": "/nope.md"}))
    assert j(P, "rm src/a.py-E").kind == "code"
    st.unlink()
    assert j(P, "rm src/a.py-E").kind == "code"


def run_main(P, monkeypatch, capsys, command, cwd):
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(
        {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(cwd)})))
    rc = gj.main(["--mode", "active", "--project", str(P), "--sd", str(P / ".superlite")])
    rows = [json.loads(x) for x in (P / ".superlite" / "incidents.jsonl").read_text().splitlines()]
    return rc, rows, capsys.readouterr().err


def test_block_row_has_rule_and_cwd(P, monkeypatch, capsys):
    rc, rows, err = run_main(P, monkeypatch, capsys, "rm a.py", P / "src")
    assert rc == 2
    assert rows[-1]["rule"] == "code" and rows[-1]["cwd"] == str(P / "src") and rows[-1]["target"] == "src/a.py"
    assert BLOCK_LINE in err.splitlines()


def test_command_target_keeps_400_chars(P, monkeypatch, capsys):
    rc, rows, _ = run_main(P, monkeypatch, capsys, "echo " + "a" * 450 + " && rm $(cat list)", P)
    assert rc == 2
    assert len(rows[-1]["target"]) == 400 and rows[-1]["target"].startswith("echo aaa")


def test_guard_error_row_unchanged(P):
    gj._incident(str(P / ".superlite"), "guard-error", "Bash", "x" * 300)
    row = json.loads((P / ".superlite" / "incidents.jsonl").read_text().splitlines()[-1])
    assert "rule" not in row and "cwd" not in row and len(row["target"]) == 120


def test_rm_skip_needs_one_known_folder_and_literal_target(P):
    (P / "src" / "stray-E").write_text("x")
    (P / "stray-E").write_text("x")
    for cmd in ("cd $X && rm stray-E", "cd nope || true; rm stray-E", "cd src; cd $X; rm stray-E",
                "rm $X/stray-E", "rm src/$X", "rm src/`echo a.py`", "(cd src || cd ..) && rm a.py"):
        v = j(P, cmd)
        assert v is not None and v.kind == "code", cmd
    assert j(P, "cd src && rm stray-E") is None
