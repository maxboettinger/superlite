# superlite build report

projection: fixed forecast saved at lint 2026-11-06T17:45:09

                         Projected    Actual  Delta
wall-clock (min)               4.1       9.4  +5.3 (+129%)
agent cost (USD, +rework)      0.69      2.59  +1.90 (+275%)
task-minutes                  18.8      10.0  -8.8 (-47%)
agents                          10        10  +0 (+0%)
cost split: agents $2.15, rework $0.43, coordinator n/a, total $2.59
concurrency: peak 4 at once (projected 6); critical path actual T4 T5 T10; projected T1 > T4 (4.1 min)
model mix: sonnet 10 tasks $2.59
quality: tests 3698 passed, 0 failed; first-time pass n/a; rework dispatches 2; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet      1.9     0.6  -1.3 (-69%)     $0.148
T6    sonnet      1.7     0.6  -1.1 (-66%)     $0.148
T3    sonnet      2.0     0.9  -1.1 (-55%)     $0.267
T9    sonnet      1.7     0.7  -1.1 (-62%)     $0.107
T10   sonnet      1.7     0.7  -1.0 (-62%)     $0.299
(+5 smaller misses; `sl report --json` lists all)

takeaway: ran 129% slower than projected; cost 275% over; biggest miss T2
