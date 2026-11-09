# superlite build report

projection: fixed forecast saved at lint 2026-11-09T14:46:58

                         Projected    Actual  Delta
wall-clock (min)               1.5       1.8  +0.4 (+24%)
agent cost (USD, +rework)      0.20      0.67  +0.47 (+230%)
task-minutes                   2.5       2.5  -0.1 (-2%)
agents                           2         5  +3 (+150%)
cost split: agents $0.67, rework $0.00, coordinator n/a, total $0.67
concurrency: peak 2 at once (projected 2); critical path actual T1; projected T2 (1.5 min)
model mix: sonnet 2 tasks $0.67
quality: tests 4759 passed, 0 failed; first-time pass n/a; rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet      1.5     0.8  -0.7 (-45%)     $0.344
T1    sonnet      1.1     1.7  +0.6 (+59%)     $0.330

takeaway: ran 24% slower than projected; cost 230% over; biggest miss T2
