# superlite build report

projection: fixed forecast saved at lint 2026-11-10T07:45:12

                         Projected    Actual  Delta
wall-clock (min)               1.7       1.6  -0.1 (-8%)
agent cost (USD, +rework)      0.19      0.56  +0.37 (+189%)
task-minutes                   1.7       1.6  -0.1 (-8%)
agents                           1         2  +1 (+100%)
cost split: agents $0.56, rework $0.00, coordinator n/a, total $0.56
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (1.7 min)
model mix: sonnet 1 tasks $0.56
quality: tests 5162 passed, 0 failed; first-time pass n/a; rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      1.7     1.6  -0.1 (-8%)      $0.560

takeaway: ran 8% faster than projected; cost 189% over; biggest miss T1
