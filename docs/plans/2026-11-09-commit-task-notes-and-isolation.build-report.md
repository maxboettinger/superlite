# superlite build report

projection: fixed forecast saved at lint 2026-11-09T19:31:59 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               2.3      27.4  +25.1 (+1067%)
agent cost (USD, +rework)      0.26      1.00  +0.74 (+282%)
task-minutes                   2.3      12.8  +10.5 (+447%)
agents                           2         3  +1 (+50%)
cost split: agents $0.77, rework $0.24, coordinator n/a, total $1.00
concurrency: peak 2 at once (projected 1); critical path actual T1; projected T1 > T2 (2.3 min)
model mix: sonnet 2 tasks $1.00
quality: tests 5025 passed, 0 failed; first-time pass n/a; rework dispatches 1; open incidents 3

task  model      pred  actual  delta             cost
T2    sonnet      1.2     7.1  +5.9 (+499%)    $0.309
T1    sonnet      1.2     5.8  +4.6 (+394%)    $0.694

takeaway: ran 1067% slower than projected; cost 282% over; biggest miss T2
