# superlite build report

projection: fixed forecast saved at lint 2026-11-11T00:38:03 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               4.4      11.6  +7.2 (+164%)
agent cost (USD, +rework)      0.78      1.95  +1.17 (+150%)
task-minutes                   9.5       9.3  -0.2 (-2%)
agents                           6        12  +6 (+100%)
cost split: agents $1.78, rework $0.17, coordinator $6.93 (77 turns, context median 332.6k, peak 366.7k; session $13.83), coordinator per task $1.16 (target $1.00), total $8.89
concurrency: peak 3 at once (projected 3); critical path actual T1 T4; projected T1 > T2 > T3 (4.4 min)
model mix: sonnet 6 tasks $1.95, coordinator opus $6.93
quality: tests 5878 passed, 0 failed; first-time pass n/a; rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      1.5     1.2  -0.3 (-21%)     $0.226
T5    sonnet      1.5     1.6  +0.2 (+13%)     $0.308
T2    sonnet      1.5     1.3  -0.2 (-12%)     $0.276
T4    sonnet      1.8     2.0  +0.1 (+6%)      $0.509
T6    sonnet      1.8     1.8  +0.0 (+1%)      $0.329
(+1 smaller misses; `sl report --json` lists all)

takeaway: ran 164% slower than projected; cost 150% over; biggest miss T1
