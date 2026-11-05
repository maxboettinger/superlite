"""File utilities: name the paths a simple command writes.

Library: targets(words) -> the paths the command writes, as written (not resolved); "?" for a write whose target
is unknown (patch with no named file). COMMANDS is the set of command names handled. Words come decoded from guard_lex;
words[0] is the command (a path or `.exe` suffix is dropped). Rules:
- a target-directory form (-t DIR, --target-directory DIR) names DIR with a trailing "/"; without it the last operand
  of cp, mv, install and ln is the destination (ln with one operand makes a link named after it in the working dir);
- mv also names its sources (they are removed); cp, install, ln and rsync do not; rsync names a local last operand;
- rm, rmdir, unlink, shred, tee, touch, truncate: every operand; dd: each of= value; install -d: every operand;
- sed and perl write only with -i (--in-place); the operands after the script are the files; sed also writes the file of
  a `w`/`W` command or an `s///w` flag, and "?" for an `e` command or `s///e` flag (a shell command), with or without -i;
- link_sources(words) names the sources of a link-making command (ln, cp -l/-s/--link/--symbolic-link): a link to a
  protected file is a way to write it, so the judge checks them too (`link` is read as `ln` by the judge);
- `-`, an empty word and a /dev/ path are not targets; --help, --version and a missing operand write nothing.
Options follow getopt: clusters (-rfv), a value attached or in the next word (-t d, -td, --size 0, --size=0), `--` ends
options; GNU permutes options after operands, perl stops its switches at the first operand.
"""
# Complexity notation:
#   n = words in the command, m = length of the longest word
import os  # O(1)
import re  # O(1)

COMMANDS = frozenset({"cp", "mv", "rm", "rmdir", "unlink", "shred", "tee", "install", "ln", "touch", "dd",  # O(1)
                      "truncate", "rsync", "patch", "sed", "perl"})  # O(1)

# per command: short options taking a value (the rest of the cluster, else the next word), short options taking
# only the rest of the cluster (sed/perl -i[SUFFIX]), long options taking a value (--name=V or --name V)
_RSYNC = frozenset({"--rsh", "--rsync-path", "--exclude", "--include", "--exclude-from", "--include-from",  # O(1)
                    "--files-from", "--filter", "--port", "--bwlimit", "--backup-dir", "--suffix", "--temp-dir",  # O(1)
                    "--partial-dir", "--log-file", "--log-file-format", "--link-dest", "--compare-dest",  # O(1)
                    "--copy-dest", "--timeout", "--contimeout", "--address", "--sockopts", "--max-size",  # O(1)
                    "--min-size", "--modify-window", "--chmod", "--chown", "--usermap", "--groupmap",  # O(1)
                    "--read-batch", "--write-batch", "--only-write-batch", "--password-file", "--out-format",  # O(1)
                    "--info", "--debug", "--iconv", "--checksum-choice", "--compress-level", "--compress-choice",  # O(1)
                    "--block-size", "--skip-compress", "--remote-option", "--max-delete", "--stop-after",  # O(1)
                    "--stop-at", "--outbuf", "--protocol"})  # O(1)
_PATCH = frozenset({"--backup-prefix", "--directory", "--input", "--output", "--strip", "--reject-file",  # O(1)
                    "--version-control", "--suffix", "--prefix", "--basename-prefix", "--reject-format", "--fuzz",  # O(1)
                    "--get", "--read-only", "--debug"})  # O(1)
_SPEC = {  # O(1)
    "cp": ("tS", "", frozenset({"--target-directory", "--suffix", "--no-preserve", "--sparse"})),  # O(1)
    "mv": ("tS", "", frozenset({"--target-directory", "--suffix"})),  # O(1)
    "install": ("mgoStBf", "", frozenset({"--mode", "--group", "--owner", "--suffix", "--target-directory",  # O(1)
                                          "--strip-program"})),  # O(1)
    "ln": ("St", "", frozenset({"--suffix", "--target-directory"})),  # O(1)
    "rm": ("", "", frozenset()),  # O(1)
    "rmdir": ("", "", frozenset()),  # O(1)
    "unlink": ("", "", frozenset()),  # O(1)
    "tee": ("", "", frozenset()),  # O(1)
    "shred": ("ns", "", frozenset({"--iterations", "--size", "--random-source"})),  # O(1)
    "touch": ("dtrA", "", frozenset({"--date", "--reference", "--time"})),  # O(1)
    "truncate": ("sr", "", frozenset({"--size", "--reference"})),  # O(1)
    "rsync": ("efBMT@", "", _RSYNC),  # O(1)
    "patch": ("BdDFgiopVrxzY", "", _PATCH),  # O(1)
    "sed": ("efl", "i", frozenset({"--expression", "--file", "--line-length"})),  # O(1)
    "perl": ("eE", "iIMmxdDFCV", frozenset()),  # O(1)
}  # O(1)
_HELP = ("--help", "--version")  # O(1)


def _parse(words, name, permute=True):  # O(n*m) | (opts [(name, value or None)], operands); short names are bare chars
    sv, sr, lv = _SPEC[name]  # O(1)
    opts, ops = [], []  # O(1)
    end = False  # O(1)
    i, n = 1, len(words)  # O(1)
    while i < n:  # O(n)
        w = words[i]  # O(1)
        i += 1  # O(1)
        if end or len(w) < 2 or w[0] != "-":  # an operand (a lone "-" too) | O(1)
            ops.append(w)  # O(1)
            end = end or not permute  # O(1)
            continue  # O(1)
        if w == "--":  # O(1)
            end = True  # O(1)
            continue  # O(1)
        if w[1] == "-":  # O(m)
            key, eq, val = w.partition("=")  # O(m)
            if eq:  # O(1)
                opts.append((key, val))  # O(1)
            elif key in lv and i < n:  # O(1)
                opts.append((key, words[i]))  # O(1)
                i += 1  # O(1)
            else:  # O(1)
                opts.append((key, None))  # O(1)
            continue  # O(1)
        j = 1  # a cluster of short options | O(1)
        while j < len(w):  # O(m)
            c = w[j]  # O(1)
            j += 1  # O(1)
            if c in sv:  # the rest of the cluster is the value, else the next word | O(1)
                if j < len(w):  # O(1)
                    opts.append((c, w[j:]))  # O(m)
                elif i < n:  # O(1)
                    opts.append((c, words[i]))  # O(1)
                    i += 1  # O(1)
                else:  # O(1)
                    opts.append((c, None))  # O(1)
                break  # O(1)
            if c in sr:  # the rest of the cluster is a suffix (sed -i'' on BSD takes an empty next word) | O(1)
                opts.append((c, w[j:]))  # O(m)
                if j >= len(w) and name == "sed" and i < n and words[i] == "":  # O(1)
                    i += 1  # O(1)
                break  # O(1)
            opts.append((c, None))  # O(1)
    return opts, ops  # O(1)


def _has(opts, *names):  # O(len(opts) * len(names))
    return any(k in names for k, _ in opts)  # O(len(opts) * len(names))


def _val(opts, *names):  # O(len(opts) * len(names)) | the last value of any of the options, or None
    found = None  # O(1)
    for k, v in opts:  # O(len(opts))
        if k in names and v is not None:  # O(len(names))
            found = v  # O(1)
    return found  # O(1)


def _real(p):  # O(m) | a word that names a file (/dev/../x leaves /dev)
    return bool(p) and p != "-" and (not p.startswith("/dev/") or ".." in p.replace("\\", "/").split("/"))  # O(m)


def _dir(d):  # O(m)
    return d if d.endswith("/") else d + "/"  # O(m)


def _remote(p):  # O(m) | an rsync operand on another host (host:path, host::module, rsync://), not a drive letter
    if p.startswith("rsync://"):  # O(m)
        return True  # O(1)
    k = p.find(":")  # O(m)
    if k < 0 or "/" in p[:k]:  # O(m)
        return False  # O(1)
    return not (k == 1 and p[0].isalpha())  # O(1)


def _copy(words, name):  # O(n*m) | cp, mv, install, ln
    opts, ops = _parse(words, name)  # O(n*m)
    if _has(opts, *_HELP):  # O(1)
        return []  # O(1)
    if name == "install" and _has(opts, "d", "--directory"):  # every operand is a directory to create | O(1)
        return [p for p in ops if _real(p)]  # O(n*m)
    d = _val(opts, "t", "--target-directory")  # O(len(opts))
    srcs = ops  # O(1)
    if d is not None:  # O(1)
        out = [_dir(d)] if _real(d) else []  # O(m)
    elif name == "ln" and len(ops) == 1:  # a link named after the operand, made in the working directory | O(1)
        base = os.path.basename(ops[0].rstrip("/"))  # O(m)
        out = [] if base in ("", ".", "..") else [base]  # O(1)
        srcs = []  # O(1)
    elif len(ops) >= 2:  # O(1)
        out, srcs = [ops[-1]], ops[:-1]  # O(n)
    else:  # a missing destination | O(1)
        return []  # O(1)
    if name != "mv":  # only mv removes its sources | O(1)
        srcs = []  # O(1)
    return [p for p in srcs + out if _real(p)]  # O(n*m)


def _is_link_opt(k):  # O(m) | -l, -s or a (GNU-abbreviated) --link / --symbolic-link of cp
    return k in ("l", "s") or (k.startswith("--") and (len(k) >= 3 and "--link".startswith(k)
                                                        or len(k) >= 4 and "--symbolic-link".startswith(k)))  # O(m)


def link_sources(words):  # O(n*m) | the sources a link-making ln or cp -l/-s names, as written (the link's content)
    if not words:  # O(1)
        return []  # O(1)
    name = words[0].replace("\\", "/").rsplit("/", 1)[-1].removesuffix(".exe")  # O(m)
    if name not in ("ln", "cp"):  # O(1)
        return []  # O(1)
    opts, ops = _parse(words, name)  # O(n*m)
    if _has(opts, *_HELP) or (name == "cp" and not any(_is_link_opt(k) for k, _ in opts)):  # O(n*m)
        return []  # O(1)
    if _val(opts, "t", "--target-directory") is None and len(ops) >= 2:  # the last operand is the link, else all are sources | O(1)
        ops = ops[:-1]  # O(n)
    return [p for p in ops if _real(p)]  # O(n*m)


def _every(words, name):  # O(n*m) | rm, rmdir, unlink, shred, tee, touch, truncate: every operand
    opts, ops = _parse(words, name)  # O(n*m)
    if _has(opts, *_HELP):  # O(1)
        return []  # O(1)
    return [p for p in ops if _real(p)]  # O(n*m)


def _dd(words):  # O(n*m) | each of= value
    return [w[3:] for w in words[1:] if w.startswith("of=") and _real(w[3:])]  # O(n*m)


def _rsync(words):  # O(n*m) | a local last operand
    opts, ops = _parse(words, "rsync")  # O(n*m)
    if _has(opts, *_HELP, "V") or len(ops) < 2:  # a listing writes nothing | O(1)
        return []  # O(1)
    out = [ops[-1]] if _real(ops[-1]) and not _remote(ops[-1]) else []  # O(m)
    if _has(opts, "--remove-source-files", "--remove-sent-files"):  # the sources are deleted after the transfer | O(1)
        out = [p for p in ops[:-1] if _real(p) and not _remote(p)] + out  # O(n*m)
    return out  # O(1)


def _patch(words):  # O(n*m) | -o FILE, else the file operand, else "?" (the files are named inside the patch)
    opts, ops = _parse(words, "patch")  # O(n*m)
    if _has(opts, *_HELP, "v", "--dry-run"):  # O(1)
        return []  # O(1)
    if _has(opts, "d", "--directory"):  # paths are relative to another directory | O(1)
        return ["?"]  # O(1)
    out = _val(opts, "o", "--output")  # O(len(opts))
    if out is not None:  # O(1)
        return [out] if _real(out) else []  # O(m)
    if ops:  # O(1)
        return [ops[0]] if _real(ops[0]) else []  # O(m)
    return ["?"]  # O(1)


_SED_W = re.compile(r"(?:^|[;{}\n])[ \t]*(?:\d+|\$|/(?:[^/\\\n]|\\.)*/)?(?:[ \t]*,[ \t]*(?:\d+|\$|/(?:[^/\\\n]|\\.)*/))?"
                    r"[ \t]*!?[ \t]*[wW][ \t]*([^\n]+)")  # O(1) | the w and W commands write the file named to the end of the line
_SED_SW = re.compile(r"(?:^|[;{}\n])[^;\n]*?\bs([^\w\s\\])(?:[^\\\n]|\\.)*?\1(?:[^\\\n]|\\.)*?\1[a-zA-Z0-9]*w[ \t]*([^\n]+)")  # O(1)
_SED_E = re.compile(r"(?:^|[;{}\n])[ \t]*(?:\d+|\$|/(?:[^/\\\n]|\\.)*/)?[ \t]*!?[ \t]*e[ \t]+\S|\bs([^\w\s\\])(?:[^\\\n]|\\.)*?\1(?:[^\\\n]|\\.)*?\1[a-zA-Z0-9]*e")  # O(1)


def _sed_scripts(opts, ops):  # O(n*m) | the script texts: every -e / --expression value, else the first operand
    sc = [v for k, v in opts if k in ("e", "--expression") and v is not None]  # O(len(opts))
    if sc:  # O(1)
        return sc, ops  # O(1)
    return ([ops[0]], ops[1:]) if ops else ([], ops)  # O(1)


def _sed_writes(opts, ops):  # O(n*m) | files a sed script writes without -i (w, W, s///w) or "?" for e (a shell command)
    out = []  # O(1)
    for sc in _sed_scripts(opts, ops)[0]:  # O(n)
        for rx in (_SED_W, _SED_SW):  # O(1)
            out.extend(m.group(m.lastindex).strip() for m in rx.finditer(sc))  # O(m)
        if _SED_E.search(sc):  # O(m)
            out.append("?")  # O(1)
    return out  # O(1)


def _inplace(words, name):  # O(n*m) | sed, perl: the operands after the script, only with -i
    opts, ops = _parse(words, name, permute=(name == "sed"))  # O(n*m)
    if _has(opts, *_HELP):  # O(1)
        return []  # O(1)
    wr = [p for p in _sed_writes(opts, ops) if p == "?" or _real(p)] if name == "sed" else []  # O(n*m)
    if not _has(opts, "i", "--in-place"):  # O(len(opts))
        return wr  # O(1)
    script = _has(opts, "e", "f", "--expression", "--file") if name == "sed" else _has(opts, "e", "E")  # O(len(opts))
    return wr + [p for p in (ops if script else ops[1:]) if _real(p)]  # O(n*m)


def targets(words):  # O(n*m) | the paths `words` (one simple command, decoded) writes, as written; "?" when unknown
    if not words:  # O(1)
        return []  # O(1)
    name = words[0].replace("\\", "/").rsplit("/", 1)[-1].removesuffix(".exe")  # O(m)
    if name not in COMMANDS:  # O(1)
        return []  # O(1)
    if name in ("cp", "mv", "install", "ln"):  # O(1)
        return _copy(words, name)  # O(n*m)
    if name == "dd":  # O(1)
        return _dd(words)  # O(n*m)
    if name == "rsync":  # O(1)
        return _rsync(words)  # O(n*m)
    if name == "patch":  # O(1)
        return _patch(words)  # O(n*m)
    if name in ("sed", "perl"):  # O(1)
        return _inplace(words, name)  # O(n*m)
    return _every(words, name)  # O(n*m)
