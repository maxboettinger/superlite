# superlite build report

projection: fixed forecast saved at lint 2026-11-10T09:05:48

                         Projected    Actual  Delta
wall-clock (min)               1.8       2.1  +0.3 (+16%)
agent cost (USD, +rework)      0.24      0.48  +0.24 (+100%)
task-minutes                   1.8       2.1  +0.3 (+16%)
agents                           1         3  +2 (+200%)
cost split: agents $0.48, rework $0.00, coordinator n/a, total $0.48
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (1.8 min)
model mix: sonnet 1 tasks $0.48
quality: tests 5291 passed, 0 failed; first-time pass n/a; rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      1.8     2.1  +0.3 (+16%)     $0.480

takeaway: ran 16% slower than projected; cost 100% over; biggest miss T1
