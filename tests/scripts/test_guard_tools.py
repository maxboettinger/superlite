import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"))

import guard_tools  # noqa: E402
from guard_tools import COMMANDS, targets  # noqa: E402


def test_examples():
    assert targets(["git", "checkout", "--", "src/a.py"]) == ["src/a.py"]
    assert targets(["git", "reset", "--hard"]) == ["."]
    assert targets(["git", "status"]) == []
    assert targets(["git", "-C", "sub", "restore", "x"]) == ["sub/x"]
    assert targets(["python3", "-c", "open('src/a.py','w').write('x')"]) == ["src/a.py"]
    assert targets(["python3", "-c", "p=input(); open(p,'w')"]) == ["?"]
    assert targets(["node", "-e", "require('fs').renameSync('/tmp/s','.superlite/orchestrator.json')"]) == [
        ".superlite/orchestrator.json"
    ]
    assert targets(["tar", "-xf", "/tmp/x.tar", "-C", "src"]) == ["src/"]
    assert targets(["unzip", "a.zip", "-d", "out"]) == ["out/"]


def test_commands_and_names():
    assert {"git", "tar", "unzip", "node", "python3", "ruby", "php", "set-content"} <= COMMANDS
    assert targets(["/usr/bin/git", "reset", "--hard"]) == ["."]
    assert targets(["GIT.exe", "reset", "--hard"]) == ["."]
    assert targets([]) == []
    assert targets(["ls", "a"]) == []


def test_review_149_items():
    # 1: node renameSync
    assert targets(["node", "-e", "require('fs').renameSync('/tmp/s','.superlite/orchestrator.json')"]) == [
        ".superlite/orchestrator.json"
    ]
    # 2: move APIs imported by name
    dst = [".superlite/orchestrator.json"]
    assert targets(["python3", "-c", "from shutil import move; move('/tmp/s', '.superlite/orchestrator.json')"]) == dst
    assert targets(["python3", "-c", "from os import replace; replace('/tmp/s', '.superlite/orchestrator.json')"]) == dst
    assert targets(["python3", "-c", "from shutil import copyfile; copyfile('/tmp/s', '.superlite/orchestrator.json')"]) == dst
    assert targets(["python3", "-c", "x.replace('a', 'b')"]) == []
    # 6-8: a no-value option that is a prefix of a value option takes no value, the member lands in the shell's directory
    for opt in ("--xattrs", "--checkpoint", "--inc"):
        assert targets(["tar", "-xf", "/tmp/x.tar", opt, "a.py", "-C", "/tmp"]) == ["a.py", "/tmp/"]
    # 9: value options missing from the table
    for opt in ("--older-than", "--older", "--older-mtime", "--older-mtime-than", "--newer-mtime-than",
                "--sparse-version", "--exclude-ignore", "--exclude-ignore-recursive", "--set-mtime-format"):
        assert targets(["tar", "-x", opt, "2020-01-01", "-C", "/tmp"]) == ["/tmp/"], opt


def test_tar_reading():
    assert targets(["tar", "xf", "a.tar"]) == ["./"]
    assert targets(["tar", "xCf", "src", "a.tar"]) == ["src/"]
    assert targets(["tar", "-xzf", "a.tgz", "--directory=out"]) == ["out/"]
    assert targets(["tar", "-xf", "a.tar", "-C", "a", "-C", "b"]) == ["a/b/"]
    assert targets(["tar", "-xf", "a.tar", "--strip-components", "1", "-C", "src"]) == ["src/"]
    assert targets(["tar", "-xf", "a.tar", "--strip-components=1"]) == ["./"]
    assert targets(["tar", "-tf", "a.tar"]) == []
    assert targets(["tar", "-cf", "a.tar", "src"]) == []
    assert targets(["tar", "-xOf", "a.tar"]) == []
    assert targets(["tar", "-xPf", "a.tar"]) == ["?"]
    assert targets(["tar", "-xf", "a.tar", "-I", "zstd", "-C", "x"]) == ["x/"]


def test_unzip():
    assert targets(["unzip", "a.zip"]) == ["./"]
    assert targets(["unzip", "-odout", "a.zip"]) == ["out/"]
    assert targets(["unzip", "-d", "out", "a.zip"]) == ["out/"]
    assert targets(["unzip", "-l", "a.zip"]) == []
    assert targets(["unzip", "-p", "a.zip"]) == []
    assert targets(["unzip", "-:", "a.zip"]) == ["?"]


def test_git_writers():
    assert targets(["git", "checkout", "HEAD", "--", "a", "b"]) == ["a", "b"]
    assert targets(["git", "restore", "a", "b"]) == ["a", "b"]
    assert targets(["git", "restore", "--staged", "a"]) == []
    assert targets(["git", "restore", "-S", "-W", "a"]) == ["a"]
    assert targets(["git", "restore", "--source", "HEAD~1", "a"]) == ["a"]
    assert targets(["git", "rm", "-r", "a"]) == ["a"]
    assert targets(["git", "rm", "--cached", "a"]) == []
    assert targets(["git", "mv", "a", "b"]) == ["a", "b"]
    assert targets(["git", "clean", "-n"]) == []
    assert targets(["git", "clean", "-f", "x"]) == ["x"]
    for words in (
        ["git", "checkout", "-f"],
        ["git", "switch", "--discard-changes", "main"],
        ["git", "switch", "-f", "main"],
        ["git", "reset", "--hard"],
        ["git", "reset", "--har", "HEAD~1"],
        ["git", "reset", "--merge"],
        ["git", "stash", "pop"],
        ["git", "stash", "apply"],
        ["git", "stash", "branch", "b"],
    ):
        assert targets(words) == ["."], words
    assert targets(["git", "-C", "sub", "reset", "--hard"]) == ["sub"]
    assert targets(["git", "clean", "-fd"]) == ["./?"]  # any file below the directory it runs in, not the folder itself
    assert targets(["git", "-C", "sub", "clean", "-f"]) == ["sub/?"]
    assert targets(["git", "apply", "p.diff"]) == ["."]
    assert targets(["git", "am", "p.mbox"]) == ["."]
    assert targets(["git", "-C", "/tmp/o", "am", "p.mbox"]) == ["/tmp/o"]
    assert targets(["git", "restore", "--pathspec-from-file=l"]) == ["?"]
    assert targets(["git", "restore", ":(glob)*.py"]) == ["?"]
    assert targets(["git", "-c", "alias.zz=!rm a", "zz"]) == ["a"]
    for sub in ("log", "diff", "show", "status", "branch", "fetch"):
        assert targets(["git", sub]) == [], sub
    assert targets(["git", "stash"]) == []
    assert targets(["git", "reset", "--soft", "HEAD~1"]) == []
    assert targets(["git", "checkout", "-b", "new"]) == []
    assert targets(["git", "checkout", "main"]) == [] or Path("main").exists()


def test_interpreter_writers():
    py = lambda code: targets(["python3", "-c", code])  # noqa: E731
    for mode in ("w", "a", "x", "r+", "wb"):
        assert py(f"open('p', '{mode}')") == ["p"], mode
    assert py("open('p', mode='w')") == ["p"]
    assert py("open('p')") == []
    assert py("open('p', 'r')") == []
    assert py("open(p, 'w')") == ["?"]
    assert py("open('p', m)") == ["p"]
    assert py("from pathlib import Path; Path('p').write_text('x')") == ["p"]
    assert py("Path('p').write_bytes(b'x')") == ["p"]
    assert py("Path('p').open('w')") == ["p"]
    assert py("Path('p').open()") == []
    assert py("Path(d).write_text('x')") == ["?"]
    assert py("(Path('a')/'b').write_text('x')") == ["a/b"]
    assert py("import shutil; shutil.copy('a', 'b')") == ["b"]
    assert py("shutil.copy2('a', 'b')") == ["b"]
    assert py("shutil.copyfile('a', 'b')") == ["b"]
    assert py("shutil.move('a', 'b')") == ["b"]
    assert py("shutil.copytree('a', 'b')") == ["b"]
    assert py("import os; os.rename('a', 'b')") == ["b"]
    assert py("os.replace('a', 'b')") == ["b"]
    assert py("os.remove('a')") == ["a"]
    assert py("os.unlink('a')") == ["a"]
    assert py("Path('a').unlink()") == ["a"]
    assert py("Path('a').rename('b')") == ["b"]
    assert py("shutil.move(a, 'b')") == ["b"]
    assert py("shutil.move('a', b)") == ["?"]
    assert py("print(open('f').read()); x = s.replace('a','b')") == []
    assert py("print(1)") == []
    assert targets(["python3", "-Bc", "open('p','w')"]) == ["p"]
    assert targets(["python3", "-copen('p','w')"]) == ["p"]
    assert targets(["python3", "x.py"]) == []
    assert targets(["python3.11", "-c", "os.remove('a')"]) == ["a"]

    node = lambda code: targets(["node", "-e", code])  # noqa: E731
    assert node("fs.writeFileSync('p', 'x')") == ["p"]
    assert node("fs.appendFileSync('p', 'x')") == ["p"]
    assert node("fs.copyFileSync('a', 'p')") == ["p"]
    assert node("fs.rmSync('p', {recursive: true})") == ["p"]
    assert node("fs.unlinkSync('p')") == ["p"]
    assert node("require('fs').promises.writeFile('p', 'x')") == ["p"]
    assert node("fs.writeFileSync(p, 'x')") == ["?"]
    assert node("fs.writeFileSync(`${d}/x`, 'x')") == ["?"]
    assert node("console.log(fs.readFileSync('p'))") == []
    assert node("x.rename('a')") == []
    assert targets(["node", "--eval=fs.rmSync('p')"]) == ["p"]
    assert targets(["node", "-p", "fs.rmSync('p')"]) == ["p"]

    rb = lambda code: targets(["ruby", "-e", code])  # noqa: E731
    assert rb("File.write('p', 'x')") == ["p"]
    assert rb("File.write 'p', 'x'") == ["p"]
    assert rb("File.open('p', 'w') { |f| f << 1 }") == ["p"]
    assert rb("File.open('p') { |f| f.read }") == []
    assert rb("FileUtils.cp('a', 'b')") == ["b"]
    assert rb("FileUtils.mv 'a', 'b'") == ["b"]
    assert rb("FileUtils.rm('p')") == ["p"]
    assert rb("FileUtils.rm_rf(d)") == ["?"]
    assert rb("File.write(\"#{d}/p\", 1)") == ["?"]
    assert rb("puts File.read('p')") == []

    php = lambda code: targets(["php", "-r", code])  # noqa: E731
    assert php("file_put_contents('p', 'x');") == ["p"]
    assert php("file_put_contents($p, 'x');") == ["?"]
    assert php("file_put_contents(\"a$b\", 'x');") == ["?"]
    assert php("copy('a', 'b');") == ["b"]
    assert php("unlink('p');") == ["p"]
    assert php("$f = fopen('p', 'w');") == ["p"]
    assert php("$f = fopen('p', 'r');") == []
    assert php("echo file_get_contents('p');") == []


def test_powershell_cmdlets():
    cases = [
        ["Set-Content", "-Path", "a", "-Value", "x"],
        ["Set-Content", "a", "x"],
        ["Add-Content", "a", "x"],
        ["Out-File", "-FilePath", "a"],
        ["Out-File", "a"],
        ["New-Item", "a"],
        ["New-Item", "-ItemType", "File", "-Path", "a"],
        ["Remove-Item", "a"],
        ["Remove-Item", "-Recurse", "-Force", "a"],
        ["Remove-Item", "-LiteralPath:a"],
        ["Copy-Item", "x", "-Destination", "a"],
        ["Copy-Item", "-Path", "x", "-Destination", "a"],
        ["Copy-Item", "x", "a"],
        ["Move-Item", "x", "a"],
        ["Move-Item", "-Path", "x", "-Dest", "a"],
        ["sEt-cOnTeNt", "-Path", "a"],
    ]
    for words in cases:
        assert targets(words) == ["a"], words
    assert targets(["New-Item", "-Path", "d", "-Name", "f"]) == ["d/f"]
    assert targets(["Remove-Item", "a,b"]) == ["a", "b"]
    assert targets(["Set-Content", "$p", "x"]) == ["?"]
    assert targets(["Get-Content", "a"]) == []


def test_other_archives():
    assert targets(["7z", "x", "a.7z", "-oout"]) == ["out/"]
    assert targets(["7z", "x", "a.7z"]) == ["./"]
    assert targets(["7za", "e", "a.7z", "-aoa"]) == ["./"]
    assert targets(["7z", "l", "a.7z"]) == []
    assert targets(["cpio", "-i"]) == ["?"]
    assert targets(["cpio", "-idv"]) == ["?"]
    assert targets(["cpio", "--extract"]) == ["?"]
    assert targets(["cpio", "-o"]) == []
    assert targets(["cpio", "-t"]) == []


@pytest.mark.parametrize("cmd", sorted(COMMANDS))
def test_every_command_runs_without_error(cmd):
    assert isinstance(guard_tools.targets([cmd]), list)
    assert isinstance(guard_tools.targets([cmd, "-x", "--", ""]), list)


def test_review_tar_aliases():
    assert targets(["bsdtar", "-xf", "a.tar", "-C", "src"]) == ["src/"]
    assert targets(["gtar", "-xf", "a.tar"]) == ["./"]


def test_review_rmtree_is_one_target():
    assert targets(["python3", "-c", "import shutil; shutil.rmtree('/tmp/x')"]) == ["/tmp/x"]


@pytest.mark.parametrize("code,expected", [
    ("import os; os.system('rm src/a')", ["src/a"]),
    ("import os; os.system('echo x > src/a')", ["src/a"]),
    ("import os; os.system('ls; cp /tmp/x src/a')", ["src/a"]),
    ("import os; os.system('sudo -u x rm src/a')", ["src/a"]),
    ("import os; os.system('echo hi')", []),
    ("import os; os.system(cmd)", ["?"]),
    ("import subprocess; subprocess.run(['rm','src/a'])", ["src/a"]),
    ("import subprocess; subprocess.run(['bash','-c','rm src/a'], check=True)", ["src/a"]),
    ("import subprocess; subprocess.run(['ls','-l'])", []),
    ("import subprocess; subprocess.run(['rm', x])", ["?"]),
    ("import os; os.system('find . -delete')", ["?"]),
])
def test_review_python_embedded_shell(code, expected):
    assert targets(["python3", "-c", code]) == expected


def test_review_other_interpreters_embedded_shell():
    assert targets(["node", "-e", "require('child_process').execSync('rm src/a')"]) == ["src/a"]
    assert targets(["node", "-e", "require('child_process').spawnSync('rm',['src/a'])"]) == ["src/a"]
    assert targets(["node", "-e", "cp.execSync(`rm ${x}`)"]) == ["?"]
    assert targets(["ruby", "-e", "system('rm','src/a')"]) == ["src/a"]
    assert targets(["ruby", "-e", "`rm src/a`"]) == ["src/a"]
    assert targets(["ruby", "-e", "x=%x(rm y)"]) == ["?"]
    assert targets(["php", "-r", "system('rm src/a');"]) == ["src/a"]
    assert targets(["php", "-r", "echo `rm src/a`;"]) == ["src/a"]


def test_review_perl_inline_code():
    assert targets(["perl", "-e", "unlink 'x'"]) == ["x"]
    assert targets(["perl", "-e", "unlink('a','b'); rename 'c','d'"]) == ["a", "b", "d"]
    assert targets(["perl", "-e", "open(F, '>>src/a')"]) == ["src/a"]
    assert targets(["perl", "-e", "open(my $fh, '>', 'src/a')"]) == ["src/a"]
    assert targets(["perl", "-e", "open(my $fh, '<', 'src/a')"]) == []
    assert targets(["perl", "-e", 'open(F, "> $x")']) == ["?"]
    assert targets(["perl", "-e", "system('rm src/a')"]) == ["src/a"]
    assert targets(["perl", "-E", "say 1"]) == []


def test_review_python_extract_and_download():
    assert targets(["python3", "-c", "import zipfile; zipfile.ZipFile('a.zip').extractall('src')"]) == ["src"]
    assert targets(["python3", "-c", "urllib.request.urlretrieve('http://x','src/a')"]) == ["src/a"]
    assert targets(["python3", "-c", "fileinput.input('src/a', inplace=True)"]) == ["src/a"]


def test_review_git_output_files():
    assert targets(["git", "diff", "--output=src/x"]) == ["src/x"]
    assert targets(["git", "log", "--output", "src/x"]) == ["src/x"]
    assert targets(["git", "show", "HEAD:f", "--out=src/a"]) == ["src/a"]
    assert targets(["git", "format-patch", "-o", "src/p", "HEAD~1"]) == ["src/p"]
    assert targets(["git", "archive", "-o", "src/a.tar", "HEAD"]) == ["src/a.tar"]
    assert targets(["git", "-C", "sub", "diff", "--output=x"]) == ["sub/x"]
    assert targets(["git", "diff", "--stat"]) == []
    assert targets(["git", "checkout-index", "--prefix=src/", "f"]) == ["src/"]
    assert targets(["git", "checkout", "--theirs", "f"]) == ["f"]
    assert targets(["git", "checkout", "main"]) == []


def test_review_powershell_aliases_and_cmdexe():
    assert targets(["del", "/q", "src\\a.py"]) == ["src\\a.py"]
    assert targets(["rd", "/s", "/q", "src"]) == ["src"]
    assert targets(["ri", "-Recurse", "src/a"]) == ["src/a"]
    assert targets(["ri", "-LiteralPath", "src/a"]) == ["src/a"]
    assert targets(["Remove-Item", "a", "b"]) == ["a", "b"]
    assert targets(["Rename-Item", "-Path", "docs/a.md", "-NewName", "a.py"]) == ["docs/a.md", "docs/a.py"]
    assert targets(["Expand-Archive", "a.zip", "-DestinationPath", "src"]) == ["src/"]
    assert targets(["iwr", "http://x", "-OutFile", "src/a"]) == ["src/a"]
    assert targets(["iwr", "http://x"]) == []
    assert targets(["Tee-Object", "-FilePath", "src/a"]) == ["src/a"]


@pytest.mark.parametrize("code,expected", [
    ("p='docs/plans/a.md'; open(p,'w').write('x')", ["docs/plans/a.md"]),
    ("p='src/a.py'; open(p,'w')", ["src/a.py"]),
    ("p='a'\np='b'\nopen(p,'w')", ["a", "b"]),
    ("p='a'\np=input()\nopen(p,'w')", ["?"]),
    ("p='a'\np+='x'\nopen(p,'w')", ["?"]),
    ("p='a'+x\nopen(p,'w')", ["?"]),
    ("p=Path('src/a'); p.write_text('x')", ["src/a"]),
    ("p='src/a'; Path(p).write_text('x')", ["src/a"]),
    ("p=Path('src')/'a'; p.write_text('x')", ["src/a"]),
    ("m='r'; p='src/a'; open(p,m)", []),
    ("import os; p='src/a'; os.remove(p)", ["src/a"]),
])
def test_review_name_assigned_literals_python(code, expected):
    assert targets(["python3", "-c", code]) == expected


def test_review_name_assigned_literals_other_languages():
    assert targets(["node", "-e", "const p='x/y'; fs.writeFileSync(p,'z')"]) == ["x/y"]
    assert targets(["node", "-e", "let p='x'; p=q; fs.writeFileSync(p,'z')"]) == ["?"]
    assert targets(["node", "-e", "fs.writeFileSync(p,'z')"]) == ["?"]
    assert targets(["ruby", "-e", "p='x'; File.write(p,'z')"]) == ["x"]
    assert targets(["php", "-r", "$p='x'; file_put_contents($p,'z');"]) == ["x"]


def test_git_alias_is_judged_as_what_it_runs():
    t = lambda *w, **kw: targets(["git", *w], **kw)  # noqa: E731
    assert t("-c", "alias.st=status", "st") == []
    assert t("-c", "alias.co=checkout", "co", "--", "src/a.py") == ["src/a.py"]
    assert t("-c", "alias.x=checkout -f", "x") == ["."]
    assert t("-c", "alias.x=!rm", "x", "src/a.py") == ["src/a.py"]
    assert t("-c", "alias.x=!echo hi > docs/p.md", "x", top="/p") == ["/p/docs/p.md"]  # a ! alias runs at the top
    assert t("-c", "alias.x=!echo hi > docs/p.md", "x", top="/p", cwd="/elsewhere") == ["docs/p.md"]
    assert t("-c", "alias.x=!echo hi > docs/p.md", "-C", "/elsewhere", "x", top="/p", cwd="/elsewhere") == ["/p/docs/p.md"]  # -C names the repo
    assert t("-c", "alias.a=b", "-c", "alias.b=status", "a") == ["?"]  # an alias of an alias is not followed
    assert t("-c", "alias.x=x", "x") == ["?"]


def test_git_config_the_guard_cannot_read_makes_an_unknown_subcommand_unknown():
    assert targets(["git", "--config-env=alias.x=CMD", "x"]) == ["?"]
    assert targets(["git", "--config-env", "alias.x=CMD", "x"]) == ["?"]
    assert targets(["git", "-c", "include.path=/tmp/c", "x"]) == ["?"]
    assert targets(["git", "-c", "includeIf.gitdir:/a.path=/c", "x"]) == ["?"]
    assert targets(["git", "x"], text="GIT_DIR=/p/.git git x") == ["?"]
    assert targets(["git", "x"], text="GIT_CONFIG_PARAMETERS=\"'alias.x=!rm a'\" git x") == ["?"]
    assert targets(["git", "w"], text="git config alias.w '!rm a' && git w") == ["?"]
    assert targets(["git", "--git-dir=/p/.git", "x"]) == ["?"]
    assert targets(["git", "x"]) == []  # no config read from elsewhere: a plain unknown word writes nothing
    assert targets(["git", "status"], text="git config user.name x && git status") == []
    assert targets(["git", "config", "user.name", "x"], text="git config user.name x") == []


def test_git_work_tree_from_the_environment_and_config():
    co = ["git", "checkout", "--", "src/a.py"]
    assert targets(co, env={"GIT_WORK_TREE": "/p"}) == ["/p/src/a.py"]
    assert targets(co, env={"GIT_WORK_TREE": "/tmp/x"}) == ["/tmp/x/src/a.py"]
    assert targets(["git", "--work-tree=/tmp/x", *co[1:]], env={"GIT_WORK_TREE": "/p"}) == ["/tmp/x/src/a.py"]
    assert targets(["git", "-c", "core.worktree=/p", *co[1:]]) == ["/p/src/a.py"]
    assert targets(co, env={"GIT_WORK_TREE": None}) == ["$GIT_WORK_TREE/src/a.py"]  # a variable: unknown
    assert targets(co, text="export GIT_WORK_TREE=$X; git checkout -- src/a.py") == ["$GIT_WORK_TREE/src/a.py"]
    assert targets(co, text="git config core.worktree /p && git checkout -- src/a.py") == ["$GIT_WORK_TREE/src/a.py"]
    assert targets(["git", "-C", "$X", "checkout", "HEAD", "--", "SPEC.md"]) == ["$X/SPEC.md"]


def test_git_checkout_operand_is_a_path_when_it_exists_below_cwd(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x")
    assert targets(["git", "checkout", "src/a.py"], cwd=str(tmp_path)) == ["src/a.py"]
    assert targets(["git", "checkout", "a.py"], cwd=str(tmp_path / "src")) == ["a.py"]
    assert targets(["git", "checkout", "main"], cwd=str(tmp_path)) == []
    assert targets(["git", "-C", "src", "checkout", "a.py"], cwd=str(tmp_path)) == ["src/a.py"]
    assert targets(["git", "-C", "$X", "checkout", "a.py"], cwd=str(tmp_path)) == []


def test_literal_path_compositions_name_the_path():
    py = lambda code: targets(["python3", "-c", code])  # noqa: E731
    assert py("import os; open(os.path.join('/tmp/s','x'),'w')") == ["/tmp/s/x"]
    assert py("import os; open(os.path.join('/tmp/s','/p/src/a.py'),'w')") == ["/p/src/a.py"]  # an absolute part starts over
    assert py("(Path('/tmp/s') / 'x.json').write_text('x')") == ["/tmp/s/x.json"]
    assert py("(Path('/tmp/s') / 'a' / 'x').write_text('x')") == ["/tmp/s/a/x"]
    assert py("(Path('/tmp/s') / '/p/src/a.py').write_text('x')") == ["/p/src/a.py"]
    assert py("d = Path('/tmp/s')\n(d / 'x.json').write_text('x')") == ["/tmp/s/x.json"]
    assert py("d = Path('/tmp/s')\ne = d / 'a'\nopen(e / 'x', 'w')") == ["/tmp/s/a/x"]  # a name joined from literal names
    assert py("d = '/tmp/s'\nopen(f'{d}/a.py', 'w')") == ["/tmp/s/a.py"]
    assert py("Path(os.path.join('/tmp/s', 'x')).write_text('x')") == ["/tmp/s/x"]
    assert py("open(str(Path('/tmp/s') / 'x'), 'w')") == ["/tmp/s/x"]


def test_an_unknown_piece_is_a_question_mark_component_below_an_absolute_prefix():
    py = lambda code: targets(["python3", "-c", code])  # noqa: E731
    assert py("open(f'/tmp/s/{x}.json','w')") == ["/tmp/s/?"]
    assert py("open(f\"/tmp/s/{1}.json\",'w')") == ["/tmp/s/?"]
    assert py("import os; open(os.path.join('/tmp/s', x),'w')") == ["/tmp/s/?"]
    assert py("(Path('/tmp/s') / x).write_text('x')") == ["/tmp/s/?"]
    assert py("open(f'/tmp/s/ab{x}','w')") == ["/tmp/s/?"]
    # a relative prefix, or an unknown first piece, may be anything: all unknown
    assert py("open(f'src/{n}.py','w')") == ["?"]
    assert py("open(f'{d}/a.py','w')") == ["?"]
    assert py("open(os.path.join(x, 'a'),'w')") == ["?"]
    assert py("p = Path('.') / sys.argv[1]\np.write_text('x')") == ["?"]
    assert py("p = 'docs/plans/' + sys.argv[1]\nopen(p, 'w')") == ["?"]  # a string `+` is not followed
    assert py("open('p', m)") == ["p"]  # an unknown mode still counts as a write


def test_a_for_loop_rebinding_a_name_yields_every_value():
    py = lambda code: targets(["python3", "-c", code])  # noqa: E731
    assert py("for p in ('a','b'): open(p,'w')") == ["a", "b"]
    assert py("f = '.superlite/n.md'\nfor f in ['src/a.py']:\n    open(f,'w')") == [".superlite/n.md", "src/a.py"]
    assert py("[open(x, 'w') for x in ['a', 'b']]") == ["a", "b"]
    assert py("for p in files: open(p,'w')") == ["?"]
    assert py("for p in ('a', q): open(p,'w')") == ["?"]
    assert py("for a, b in (('x', 'y'),): open(a,'w')") == ["?"]


def test_str_replace_on_a_name_bound_to_strings_is_no_move():
    py = lambda code: targets(["python3", "-c", code])  # noqa: E731
    # final review: `s = 'see X'; s.replace(...)` is str.replace; it named 'X' as a moved-onto file and blocked.
    assert py("s = 'see X'\nt = s.replace('X', '.superlite/orchestrator.json')\nopen('/tmp/o/c.md','w').write(t)") == [
        "/tmp/o/c.md"]
    assert py("s = f'{a}/x'\nu = s.replace('a', 'b')") == []
    assert py("s = os.path.join('a', b)\nu = s.replace('a', 'b')") == []
    # a Path, a for-loop name or an unknown binding keeps the move reading
    assert py("p = Path('/tmp/t')\np.replace('b')") == ["b"]
    assert py("p = 'a' / Path('q')\np.replace('b')") == ["b"]
    assert py("s = 'a'\ns = Path(s)\ns.replace('b')") == ["b"]
    assert py("for p in ('a',): p.replace('b')") == ["b"]
