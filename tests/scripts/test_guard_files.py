import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"))

import guard_files  # noqa: E402
from guard_files import COMMANDS, targets  # noqa: E402


def test_examples():
    assert targets(["cp", "-r", "a", "b", "dst/"]) == ["dst/"]
    assert targets(["cp", "-t", "dst", "a", "b"]) == ["dst/"]
    assert targets(["sed", "-i", "s/a/b/", "x.py"]) == ["x.py"]
    assert targets(["sed", "-i", "", "s/a/b/", "x.py"]) == ["x.py"]
    assert targets(["sed", "s/a/b/", "x.py"]) == []
    assert targets(["tee", "-a", "log.txt", "docs/a.md"]) == ["log.txt", "docs/a.md"]
    assert targets(["dd", "if=a", "of=src/b"]) == ["src/b"]
    assert targets(["rm", "-rf", "--", "-x", "y"]) == ["-x", "y"]


def test_getopt_clusters():
    assert targets(["rm", "-rfv", "a"]) == ["a"]
    assert targets(["cp", "-av", "a", "b"]) == ["b"]
    assert targets(["mv", "-fT", "a", "b"]) == ["a", "b"]  # the source is removed, the target written
    assert targets(["sed", "-Ei.bak", "s/x/y/", "f"]) == ["f"]
    assert targets(["perl", "-pi", "-e", "s/x/y/", "f"]) == ["f"]
    assert targets(["perl", "-i.orig", "-pe", "1", "f"]) == ["f"]


def test_each_command():
    assert targets(["cp", "a", "b"]) == ["b"]
    assert targets(["mv", "a", "b"]) == ["a", "b"]
    assert targets(["mv", "-t", "d", "a", "b"]) == ["a", "b", "d/"]
    assert targets(["rm", "-r", "a", "b/"]) == ["a", "b/"]
    assert targets(["rmdir", "-p", "a/b"]) == ["a/b"]
    assert targets(["unlink", "a"]) == ["a"]
    assert targets(["shred", "-n", "3", "-u", "a"]) == ["a"]
    assert targets(["shred", "--iterations=3", "a"]) == ["a"]
    assert targets(["tee", "a"]) == ["a"]
    assert targets(["install", "-D", "-m", "755", "a", "b/c"]) == ["b/c"]
    assert targets(["install", "-t", "dst", "a", "b"]) == ["dst/"]
    assert targets(["install", "-d", "x", "y/z"]) == ["x", "y/z"]
    assert targets(["ln", "-s", "a", "b"]) == ["b"]
    assert targets(["ln", "-sf", "-t", "dst", "a", "b"]) == ["dst/"]
    assert targets(["ln", "-s", "dir/a"]) == ["a"]  # one operand: the link is created in the working directory
    assert targets(["touch", "a", "b"]) == ["a", "b"]
    assert targets(["touch", "-t", "202001010000", "a"]) == ["a"]
    assert targets(["touch", "-r", "ref", "a"]) == ["a"]
    assert targets(["dd", "of=out.bin", "bs=1M", "if=in"]) == ["out.bin"]
    assert targets(["truncate", "-s", "0", "f"]) == ["f"]
    assert targets(["rsync", "-a", "src/", "dst/"]) == ["dst/"]
    assert targets(["rsync", "-a", "a", "b", "dst"]) == ["dst"]
    assert targets(["patch", "-o", "out", "f"]) == ["out"]
    assert targets(["patch", "-p1", "f", "x.diff"]) == ["f"]
    assert targets(["patch", "f"]) == ["f"]
    assert targets(["patch"]) == ["?"]
    assert targets(["patch", "-p1", "-i", "x.diff"]) == ["?"]
    assert targets(["patch", "-d", "sub", "-p1", "-i", "x.diff"]) == ["?"]
    assert targets(["sed", "--in-place", "s/a/b/", "f"]) == ["f"]
    assert targets(["sed", "--in-place=.bak", "s/a/b/", "f", "g"]) == ["f", "g"]
    assert targets(["perl", "-i", "-pe", "1", "f", "g"]) == ["f", "g"]
    assert COMMANDS == frozenset({"cp", "mv", "rm", "rmdir", "unlink", "shred", "tee", "install", "ln", "touch",
                                  "dd", "truncate", "rsync", "patch", "sed", "perl"})
    for name in COMMANDS:  # every listed name is handled (no operand: nothing written, nothing raised)
        assert isinstance(targets([name]), list)


def test_long_options_with_values():
    assert targets(["cp", "--target-directory=d", "a"]) == ["d/"]
    assert targets(["cp", "--target-directory", "d", "a"]) == ["d/"]
    assert targets(["install", "--mode", "644", "a", "d/"]) == ["d/"]
    assert targets(["rsync", "-e", "ssh", "a", "d/"]) == ["d/"]
    assert targets(["rsync", "--exclude", "*.o", "a", "d/"]) == ["d/"]
    assert targets(["truncate", "--size", "0", "f"]) == ["f"]
    assert targets(["touch", "--date", "yesterday", "f"]) == ["f"]
    assert targets(["cp", "--sparse", "always", "a", "b"]) == ["b"]
    assert targets(["patch", "--output", "out"]) == ["out"]
    assert targets(["patch", "--output=out", "f"]) == ["out"]


def test_read_only_forms():
    assert targets(["sed", "-n", "p", "f"]) == []
    assert targets(["cp", "--help"]) == []
    assert targets(["rm"]) == []
    assert targets(["touch", "-r", "ref"]) == []
    assert targets(["cp", "a"]) == []  # missing destination
    assert targets(["mv", "a"]) == []
    assert targets(["rsync", "a"]) == []  # a listing
    assert targets(["rm", "--version"]) == []
    assert targets(["patch", "--dry-run", "f"]) == []
    assert targets(["patch", "--help"]) == []
    assert targets(["sed", "-i", "s/a/b/"]) == []  # no file
    assert targets(["sed", "-n", "-e", "p", "f", "g"]) == []
    assert targets(["perl", "-ne", "print", "f"]) == []
    assert targets(["perl", "script.pl", "f"]) == []
    assert targets(["truncate", "-s", "0"]) == []
    assert targets(["dd", "if=a"]) == []
    assert targets([]) == []
    assert targets(["ls", "-la"]) == []


def test_dash_and_dev_are_not_targets():
    assert targets(["tee", "-"]) == []
    assert targets(["tee", "/dev/null", "a"]) == ["a"]
    assert targets(["dd", "of=/dev/null"]) == []
    assert targets(["dd", "of=/dev/stdout", "if=x"]) == []
    assert targets(["cp", "a", "/dev/null"]) == []
    assert targets(["rm", "-f", "/dev/null"]) == []
    assert targets(["touch", "-"]) == []
    assert targets(["rm", ""]) == []
    assert targets(["cp", "-t", "/dev/shm", "a"]) == []
    assert targets(["sed", "-i", "s/a/b/", "-"]) == []


def test_command_word_forms():
    assert targets(["/bin/rm", "a"]) == ["a"]
    assert targets(["rm.exe", "a"]) == ["a"]
    assert targets(["/usr/bin/env"]) == []


def test_option_terminator_and_permuted_options():
    assert targets(["rm", "--", "-rf", "-x"]) == ["-rf", "-x"]
    assert targets(["rm", "a", "-f", "b"]) == ["a", "b"]  # GNU permutes options after operands
    assert targets(["cp", "a", "b", "-v"]) == ["b"]
    assert targets(["cp", "--", "-a", "-b"]) == ["-b"]
    assert targets(["touch", "--", "-t"]) == ["-t"]
    assert targets(["sed", "s/a/b/", "-i", "f"]) == ["f"]
    assert targets(["perl", "-pe", "1", "-i", "f"]) == ["f"]  # perl reads switches until the first file
    assert targets(["perl", "-i", "-pe", "1", "f", "-w"]) == ["f", "-w"]  # after it they are file names


def test_sed_script_forms_never_hide_the_file():
    for words in (["sed", "-ie", "s/a/b/", "f"], ["sed", "-i.bak", "s/a/b/", "f"], ["sed", "-i", "", "s/a/b/", "f"],
                  ["sed", "-i", "-e", "s/a/b/", "f"], ["sed", "-e", "s/a/b/", "-i", "f"],
                  ["sed", "-ie", "-e", "s/a/b/", "f"], ["sed", "-i", "-es/a/b/", "f"],
                  ["sed", "-n", "-i", "-es/a/b/p", "f"], ["sed", "-i", "--expression=s/a/b/", "f"],
                  ["sed", "--in-place", "--expression=s/a/b/", "f"], ["sed", "-i", "--file=s.sed", "f"],
                  ["sed", "-i", "--file", "s.sed", "f"], ["sed", "-i", "-f", "s.sed", "f"],
                  ["sed", "-Ei", "", "s/a/b/", "f"], ["sed", "-i", "-E", "s/a/b/", "f"],
                  ["perl", "-i", "-pes/a/b/", "f"], ["perl", "-pi", "-E", "s/a/b/", "f"],
                  ["perl", "-0pi", "-e", "s/a/b/", "f"], ["perl", "-0777", "-pi", "-e", "1", "f"],
                  ["perl", "-lpi.bak", "-e", "1", "f"], ["perl", "-Ilib", "-Mstrict", "-pi", "-e", "1", "f"],
                  ["perl", "-pi", "script.pl", "f"]):
        assert targets(words) == ["f"], words
    assert targets(["sed", "-i", "-e", "s/a/b/", "-e", "s/c/d/", "f", "g"]) == ["f", "g"]


def test_ln_single_operand_edge_forms():
    assert targets(["ln", "a/b/"]) == ["b"]
    assert targets(["ln", "-s", "/"]) == []
    assert targets(["ln", "-s", ".."]) == []
    assert targets(["ln", "-sT", "a", "b"]) == ["b"]


def test_rsync_remote_destination_is_not_local():
    assert targets(["rsync", "-a", "src/", "host:dst/"]) == []
    assert targets(["rsync", "-a", "src/", "user@host:/srv/x"]) == []
    assert targets(["rsync", "-a", "src/", "rsync://host/mod/"]) == []
    assert targets(["rsync", "-a", "src/", "host::mod"]) == []
    assert targets(["rsync", "-a", "host:src", "dst/"]) == ["dst/"]
    assert targets(["rsync", "-a", "src/", "C:/out"]) == ["C:/out"]
    assert targets(["rsync", "-a", "src/", "./a:b"]) == ["./a:b"]


def test_target_directory_trailing_slash_not_doubled():
    assert targets(["cp", "-t", "dst/", "a"]) == ["dst/"]
    assert targets(["cp", "-t", ".", "a"]) == ["./"]
    assert targets(["install", "-t", "d", "a"]) == ["d/"]
    assert targets(["cp", "-t"]) == []  # -t without its value


def test_module_exports():
    assert callable(guard_files.targets)
    assert isinstance(guard_files.COMMANDS, frozenset)


def test_review_sed_w_command_writes_file():
    assert targets(["sed", "-n", "w src/x", "f"]) == ["src/x"]
    assert targets(["sed", "s/a/b/w src/x", "f"]) == ["src/x"]
    assert targets(["sed", "-n", "/a/w src/x", "f"]) == ["src/x"]
    assert targets(["sed", "-e", "1,3w src/x", "-e", "p", "f"]) == ["src/x"]
    assert targets(["sed", "-n", "p;w /dev/stdout", "f"]) == []
    assert targets(["sed", "s/a/w b/", "f"]) == []
    assert targets(["sed", "1e rm x", "f"]) == ["?"]
    assert targets(["sed", "s/a/b/e", "f"]) == ["?"]
    assert targets(["sed", "-i", "w src/x", "f"]) == ["src/x", "f"]


def test_review_dev_dotdot_is_not_dev():
    assert targets(["tee", "/dev/../tmp/x"]) == ["/dev/../tmp/x"]
    assert targets(["tee", "/dev/null"]) == []


def test_review_rsync_remove_source_files_names_sources():
    assert targets(["rsync", "--remove-source-files", "a", "d/"]) == ["a", "d/"]
    assert targets(["rsync", "-a", "a", "d/"]) == ["d/"]
