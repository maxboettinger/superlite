- start 8c60fa5b8177e1f128fd6d497e888a5e543d250f
- unblocked: dispatched T1 T2 at 11:37:00; waiting on fixes: none
Ruling: fleet placement local - B236/B238 saw remote write workers' fixes never reach the run root - slower builds if wrong
- tests fast passed=231 failed=0 skipped=0 seconds=2.3
- tests fast passed=7 failed=17 skipped=0 seconds=1.4
Ruling: accept predicted 36 min - T2 and T3 both edit guard_judge.py, so they run one after the other - a slower batch if wrong
- tests fast passed=131 failed=0 skipped=0 seconds=7.2
- commit T1 ee8779cfdc Link makers in code, Path link targets
- commit T2 f4a66fe7f6 Glob and tree copy runs are unknown, rsync --link-dest links
- tests fast passed=236 failed=0 skipped=0 seconds=2.2
- tests fast passed=20 failed=12 skipped=0 seconds=1.9
- tests fast passed=174 failed=0 skipped=0 seconds=11.5
- commit T1 89273241c6 Link makers in code, Path link targets
- commit T3 1cc18a6f0a `cat F >` and `git show REV:F >` text, links made by code
- tests fast passed=29 failed=7 skipped=0 seconds=1.9
- tests fast passed=105 failed=0 skipped=0 seconds=3.3
- commit T2 5b17d87172 Glob and tree copy runs are unknown, rsync --link-dest links
- Ruling: T3 also commits docs/hooks.md - docs/hooks.md bullet for #883/#884, listed by no open batch
- commit T3 714809dbbb `cat F >` and `git show REV:F >` text, links made by code
- tests full passed=12291 failed=0 skipped=12 seconds=639.6
- tests fast passed=73 failed=3 skipped=0 seconds=4.2
- tests fast passed=358 failed=0 skipped=0 seconds=8.6
- tests fast passed=372 failed=0 skipped=0 seconds=8.9
- tests fast passed=82 failed=12 skipped=0 seconds=2.9
- tests fast passed=372 failed=0 skipped=0 seconds=8.4
- commit T1 dfa5844718 Link makers in code, Path link targets
- commit T2 58124079ab Glob and tree copy runs are unknown, rsync --link-dest links
- commit T3 97eb190121 `cat F >` and `git show REV:F >` text, links made by code
Ruling: F-T2-2 dismissed - a one-file long-option copy is already in st.shared['wrote'] through _check (inner dest/name), so its run is an unknown target; the fixer pinned it with tests - a stale-text hole if wrong
Ruling: FR2 (last fresh review, per Max's guard-round precedent): fix only finding 1 (the code-link flag is lost for a script file's code, a defect of this branch's #883 fix) with a delta review; finding 4 (option value after the operands read as the destination) is an older gap, filed as a follow-up; findings 2 and 3 did not reproduce (lead's in-process probes block on branch and start commit) - more stale-text holes if wrong
- tests fast passed=50 failed=3 skipped=0 seconds=5.1
- tests fast passed=96 failed=1 skipped=0 seconds=3.5
- tests fast passed=96 failed=1 skipped=0 seconds=2.8
- tests fast passed=52 failed=1 skipped=0 seconds=5.9
- tests fast passed=130 failed=0 skipped=0 seconds=4.8
- commit T2 59ba474de9 Glob and tree copy runs are unknown, rsync --link-dest links
- tests full passed=12313 failed=0 skipped=12 seconds=326.7
Ruling: FR3 (delta review) approved the F-T2-4 code fix; its one test-strength finding is fixed without another review round (test-only change, the suite verifies it) - a weak pin if wrong
- tests fast passed=55 failed=0 skipped=0 seconds=3.0
- tests fast passed=52 failed=3 skipped=0 seconds=3.1
- tests fast passed=55 failed=0 skipped=0 seconds=3.2
- commit T2 82c47afe9f Glob and tree copy runs are unknown, rsync --link-dest links
- tests full passed=12316 failed=0 skipped=12 seconds=312.9
