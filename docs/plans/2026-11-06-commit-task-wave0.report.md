# superlite build report

projection: fixed forecast saved at lint 2026-11-06T11:35:11

                         Projected    Actual  Delta
wall-clock (min)               4.3      14.3  +10.1 (+237%)
agent cost (USD, +rework)      0.41      1.43  +1.02 (+246%)
task-minutes                  10.0       5.5  -4.5 (-45%)
agents                           5         8  +3 (+60%)
cost split: agents $1.26, rework $0.17, coordinator n/a, total $1.43
concurrency: peak 3 at once (projected 4); critical path actual T3 T5; projected T3 > T5 (4.3 min)
model mix: sonnet 5 tasks $1.43
quality: tests 3582 passed, 0 failed; first-time pass n/a; rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T4    sonnet      1.9     0.4  -1.5 (-79%)     $0.137
T1    sonnet      1.8     0.4  -1.4 (-78%)     $0.137
T2    sonnet      2.0     1.0  -1.0 (-49%)     $0.258
T5    sonnet      2.2     1.8  -0.5 (-21%)     $0.603
T3    sonnet      2.0     1.9  -0.1 (-3%)      $0.294

takeaway: ran 237% slower than projected; cost 246% over; biggest miss T4
