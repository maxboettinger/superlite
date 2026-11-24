- start aeb610feebc35cb4856c0de301a84e42ef824b2c
- unblocked: dispatched T1 at 12:47:10; waiting on fixes: none
Ruling: T1's not-run test_backlog_answer*.py is covered by the full suite before the final review: the answer path calls check_step without keys, which keeps the old branch - lead's ruling - cost if wrong: one red found at the full run
- commit T1 3dcd6dfc68 main_steps take Jira keys
- tests fast passed=1707 failed=0 skipped=0 seconds=73.1
- tests full passed=13954 failed=0 skipped=12 seconds=376.9
