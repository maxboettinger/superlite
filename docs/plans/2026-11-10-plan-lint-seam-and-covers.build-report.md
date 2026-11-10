# superlite build report

projection: fixed forecast saved at lint 2026-11-10T11:24:57 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               5.1       5.2  +0.1 (+2%)
agent cost (USD, +rework)      0.59      1.14  +0.55 (+93%)
task-minutes                   5.1       4.5  -0.6 (-12%)
agents                           3         5  +2 (+67%)
cost split: agents $1.14, rework $0.00, coordinator n/a, total $1.14
concurrency: peak 1 at once (projected 1); critical path actual T1 T2 T3; projected T1 > T2 > T3 (5.1 min)
model mix: sonnet 3 tasks $1.14
quality: tests 4 passed, 0 failed; first-time pass n/a; rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet      1.6     1.1  -0.5 (-31%)     $0.321
T1    sonnet      2.1     2.0  -0.1 (-5%)      $0.474
T3    sonnet      1.5     1.4  -0.0 (-3%)      $0.347

takeaway: ran 2% slower than projected; cost 93% over; biggest miss T2
