# superlite build report

projection: fixed forecast saved at lint 2026-11-15T20:35:54 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               8.8      41.1  +32.3 (+369%)
agent cost (USD, +rework)      1.21      4.76  +3.55 (+295%)
task-minutes                  32.0      13.3  -18.7 (-58%)
agents                           8        18  +10 (+125%)
cost split: agents $2.49, rework $2.26, coordinator $12.04 (88 turns, context median 171.4k, peak 366.3k, 1 compaction, largest 370.7k tokens; session $26.31), coordinator per task $1.34 (target $1.00), total $16.80
concurrency: peak 8 at once (projected 6); critical path actual T2; projected T7 > T8 (8.8 min)
model mix: haiku 1 tasks $0.01, sonnet 8 tasks $4.74, coordinator fable $12.04
quality: tests 11298 passed, 0 failed; first-time pass 4/9 (44%); rework dispatches 9; open incidents 1

task  model      pred  actual  delta             cost
T8    sonnet      4.8     0.7  -4.1 (-85%)     $0.197
T4    sonnet      4.5     1.5  -3.0 (-66%)     $0.106
T3    sonnet      3.9     1.4  -2.5 (-65%)     $0.408  first-time miss
T2    sonnet      3.7     1.4  -2.3 (-63%)     $0.432  first-time miss
T5    sonnet      3.9     1.7  -2.2 (-57%)     $0.816  first-time miss
(+4 smaller misses; `sl report --json` lists all)

takeaway: ran 369% slower than projected; cost 295% over; biggest miss T8
