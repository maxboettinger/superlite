- start 74e5d33e9da22422e86e3e9a3ca58ca50dbe33cf
- unblocked: dispatched T1 at 20:21:10; waiting on fixes: none
- tests fast passed=0 failed=6 skipped=0 seconds=0.7
- tests fast passed=155 failed=3 skipped=0 seconds=10.3
Ruling: T1 judge test uses `python3 Scripts/record_fixtures.py > src/recorded-v2.json`; the guard reads no Makefile so `make` passes, and no make rule is added - a make rule would block every make call - cost if wrong: the bullet is not proven on a make sighting.
Ruling: fleet.md gets a separate `- Checker command check (#1157):` bullet after the Checker bullet - test_docs_checker_600 pins the Checker line whole - cost if wrong: none.
- tests fast passed=158 failed=0 skipped=0 seconds=14.4
- commit T1 2baaf74a8b checker command check and guard bullet
- tests fast passed=6 failed=1 skipped=0 seconds=1.5
- tests fast passed=42 failed=0 skipped=0 seconds=4.0
- commit T1 fcc6c599ad checker command check and guard bullet
- tests full passed=14427 failed=0 skipped=12 seconds=677.1
