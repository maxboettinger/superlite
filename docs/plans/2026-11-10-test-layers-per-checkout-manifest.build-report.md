# superlite build report

projection: fixed forecast saved at lint 2026-11-10T08:03:33

                         Projected    Actual  Delta
wall-clock (min)               1.6       1.0  -0.6 (-37%)
agent cost (USD, +rework)      0.16      0.31  +0.16 (+99%)
task-minutes                   1.6       1.0  -0.6 (-37%)
agents                           1         3  +2 (+200%)
cost split: agents $0.31, rework $0.00, coordinator n/a, total $0.31
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (1.6 min)
model mix: sonnet 1 tasks $0.31
quality: tests 5169 passed, 0 failed; first-time pass n/a; rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      1.6     1.0  -0.6 (-37%)     $0.314

takeaway: ran 37% faster than projected; cost 99% over; biggest miss T1
