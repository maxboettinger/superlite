#!/usr/bin/env bash
set -euo pipefail
mkdir -p src/notes tests docs
cat > pyproject.toml <<'TOML'
[project]
name = "notes"
version = "0.1.0"

[tool.pytest.ini_options]
pythonpath = ["src"]
TOML
touch src/notes/__init__.py
cat > src/notes/store.py <<'PY'
import json


def load(path):
    with open(path) as f:
        return json.load(f)


def save(path, notes):
    with open(path, "w") as f:
        json.dump(notes, f)
PY
cat > src/notes/cli.py <<'PY'
import argparse

from notes import store

PATH = "notes.json"


def main(argv=None):
    parser = argparse.ArgumentParser(prog="notes")
    sub = parser.add_subparsers(dest="cmd", required=True)
    add = sub.add_parser("add")
    add.add_argument("text")
    sub.add_parser("list")
    args = parser.parse_args(argv)
    notes = store.load(PATH)
    if args.cmd == "add":
        notes.append({"id": len(notes) + 1, "text": args.text})
        store.save(PATH, notes)
    else:
        for n in notes:
            print(n["id"], n["text"])


if __name__ == "__main__":
    main()
PY
cat > tests/test_store.py <<'PY'
from notes import store


def test_round_trip(tmp_path):
    path = tmp_path / "n.json"
    store.save(path, [{"id": 1, "text": "a"}])
    assert store.load(path) == [{"id": 1, "text": "a"}]
PY
cat > notes.json <<'JSON'
[{"id": 1, "text": "buy milk"}, {"id": 2, "text": "call Sam"}]
JSON
cat > docs/spec.md <<'MD'
# Notes: SQLite storage, tags and mail import

Notes move from notes.json to a SQLite database, notes.db, next to it.

## Commands

- `notes add TEXT [--tag TAG]...` prints the new id.
- `notes list [--tag TAG]` prints `id  text  [tags]`, newest first.
- `notes tag ID TAG` adds a tag.
- `notes import DIR` adds every `*.txt` file in DIR as a note tagged `mail`, then deletes the file. A cron job runs `notes import inbox` every five minutes; a mail rule drops the files in `inbox/`.

## Store

`Store.add(text, tags) -> int`, `Store.list(tag=None) -> list[Note]`, `Store.tag(id, tag) -> None` replace the JSON store; `cli.py` keeps its commands.
MD
