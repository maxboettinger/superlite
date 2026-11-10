# superlite build report

projection: fixed forecast saved at lint 2026-11-10T07:44:39

                         Projected    Actual  Delta
wall-clock (min)               2.8       2.7  -0.1 (-5%)
agent cost (USD, +rework)      0.29      0.72  +0.43 (+151%)
task-minutes                   2.8       2.2  -0.6 (-22%)
agents                           2         4  +2 (+100%)
cost split: agents $0.72, rework $0.00, coordinator n/a, total $0.72
concurrency: peak 1 at once (projected 1); critical path actual T1 T2; projected T1 > T2 (2.8 min)
model mix: sonnet 2 tasks $0.72
quality: tests 5207 passed, 0 failed; first-time pass n/a; rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet      1.6     1.0  -0.6 (-36%)     $0.347
T1    sonnet      1.3     1.2  -0.1 (-6%)      $0.371

takeaway: ran 5% faster than projected; cost 151% over; biggest miss T2
