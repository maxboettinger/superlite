# superlite build report

projection: fixed forecast saved at lint 2026-11-07T16:56:36

                         Projected    Actual  Delta
wall-clock (min)               1.5       1.1  -0.4 (-24%)
agent cost (USD, +rework)      0.18      0.70  +0.52 (+292%)
task-minutes                   2.6       1.6  -1.0 (-38%)
agents                           2         4  +2 (+100%)
cost split: agents $0.70, rework $0.00, coordinator n/a, total $0.70
concurrency: peak 2 at once (projected 2); critical path actual T2; projected T2 (1.5 min)
model mix: sonnet 2 tasks $0.70
quality: tests 4089 passed, 0 failed; first-time pass n/a; rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      1.1     0.5  -0.6 (-56%)     $0.279
T2    sonnet      1.5     1.1  -0.4 (-24%)     $0.425

takeaway: ran 24% faster than projected; cost 292% over; biggest miss T1
