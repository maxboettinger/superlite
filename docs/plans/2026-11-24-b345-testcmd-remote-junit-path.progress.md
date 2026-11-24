- start d86682d017fe4316c0e64b691d709474b9e147f2
- unblocked: dispatched T1 at 23:33:47; waiting on fixes: none
- tests fast passed=0 failed=9 skipped=0 seconds=1.6
- tests fast passed=62 failed=1 skipped=0 seconds=6.2
- tests fast passed=63 failed=0 skipped=0 seconds=5.6
- commit T1 e5dd9e186c in-tree remote junit with fetch
Ruling: T1's edit of the plan's verbatim red-run test (it also reads .superlite/test-output.log, since a red run prints only the log path) keeps its intent - accepted - cost if wrong: one weaker assertion
Ruling: T1 names the new run_other locals rcommand and fetch_report (report is taken further down) - accepted - cost if wrong: none
- tests fast passed=63 failed=0 skipped=0 seconds=7.0
- tests full passed=14514 failed=2 skipped=12 seconds=340.3
- commit T1 048fa6d309 in-tree remote junit with fetch
- tests full passed=14517 failed=0 skipped=12 seconds=332.4
