# superlite build report

projection: fixed forecast saved at lint 2026-11-12T03:16:10 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               5.5      47.7  +42.2 (+762%)
agent cost (USD, +rework)      0.59      1.72  +1.13 (+192%)
task-minutes                   9.8       7.4  -2.4 (-24%)
agents                           4        10  +6 (+150%)
cost split: agents $1.63, rework $0.09, coordinator n/a, total $1.72
concurrency: peak 2 at once (projected 2); critical path actual T2; projected T2 > T4 (5.5 min)
model mix: sonnet 5 tasks $1.72
quality: tests 6799 passed, 0 failed (last full run; newer fast run: 558 passed, 0 failed); first-time pass 3/5 (60%); rework dispatches 1; open incidents 8

task  model      pred  actual  delta             cost
T3    sonnet      2.6     1.1  -1.5 (-58%)     $0.239
T1    sonnet      1.7     0.6  -1.1 (-64%)     $0.128
T2    sonnet      2.8     1.8  -1.0 (-37%)     $0.413  first-time miss
T4    sonnet      2.7     2.5  -0.2 (-8%)      $0.654  first-time miss
T5    sonnet      n/a     1.5  n/a             $0.288

takeaway: ran 762% slower than projected; cost 192% over; biggest miss T3
