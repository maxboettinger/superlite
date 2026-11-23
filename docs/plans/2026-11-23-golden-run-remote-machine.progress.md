- start a021bb1eafa815752b2330d7d0151efaa0df9485
- unblocked: dispatched T1 at 08:34:47; waiting on fixes: T2
- tests fast passed=0 failed=7 skipped=0 seconds=0.8
- tests fast passed=32 failed=0 skipped=0 seconds=6.8
- unblocked: dispatched T2 at 08:36:04; waiting on fixes: none
- tests fast passed=71 failed=11 skipped=0 seconds=0.6
- tests fast passed=97 failed=0 skipped=0 seconds=2.0
Ruling: T1's wrapper runs the script in a subshell `( cd cwd && script )`, not the plan's `{ ...; }` group: a script that calls `exit` would end the group's shell before the `exit N` line is written - cost if wrong: none (same output for a script without exit)
- commit T1 4e25d14b6f host script helpers
- commit T2 5caa331dd9 golden attempt and machine flag
- tests fast passed=32 failed=0 skipped=0 seconds=11.3
- tests fast passed=0 failed=1 skipped=0 seconds=0.4
- tests fast passed=18 failed=0 skipped=0 seconds=0.4
- commit T3 81eab57de3 remote golden attempt
- tests fast passed=18 failed=0 skipped=0 seconds=0.4
- tests fast passed=97 failed=0 skipped=0 seconds=1.7
- tests fast passed=17 failed=2 skipped=0 seconds=0.2
- tests fast passed=19 failed=0 skipped=0 seconds=0.2
- commit T3 11b24b96f9 remote golden attempt
Ruling: golden_remote.ready returns fr.check's text unchanged (it is already 'unreachable: <error>', 'unknown machine M' or 'herdr machine status failed: ...'); the plan's ready e.g. was ambiguous and T3 first prefixed it again - fixed by F1 - cost if wrong: none
- tests full passed=13602 failed=0 skipped=12 seconds=483.1
- tests fast passed=7 failed=1 skipped=0 seconds=0.5
- tests fast passed=8 failed=0 skipped=0 seconds=0.8
- commit T1 c25c3ba9de host script helpers
Ruling: FR1's finding fixed by F2: fleet_remote_worker.script_result reads the host output over growing offsets until an empty chunk, like golden_remote._read_all, so a long output still shows its exit line - cost if wrong: one extra remote read per finished poll
- tests full passed=13603 failed=0 skipped=12 seconds=312.8
