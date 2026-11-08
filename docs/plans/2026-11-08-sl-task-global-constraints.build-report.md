# superlite build report

projection: fixed forecast saved at lint 2026-11-08T14:29:37

                         Projected    Actual  Delta
wall-clock (min)               2.7       1.8  -1.0 (-35%)
agent cost (USD, +rework)      0.27      0.44  +0.17 (+63%)
task-minutes                   2.7       1.5  -1.2 (-45%)
agents                           2         3  +1 (+50%)
cost split: agents $0.44, rework $0.00, coordinator n/a, total $0.44
concurrency: peak 1 at once (projected 1); critical path actual T1 T2; projected T1 > T2 (2.7 min)
model mix: sonnet 2 tasks $0.44
quality: tests 4 passed, 0 failed; first-time pass n/a; rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet      1.5     0.7  -0.8 (-55%)     $0.160
T1    sonnet      1.3     0.9  -0.4 (-32%)     $0.280

takeaway: ran 35% faster than projected; cost 63% over; biggest miss T2
