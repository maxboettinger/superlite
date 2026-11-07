# superlite build report

projection: fixed forecast saved at lint 2026-11-07T10:00:35

                         Projected    Actual  Delta
wall-clock (min)               1.9       1.7  -0.2 (-12%)
agent cost (USD, +rework)      0.24      0.81  +0.57 (+234%)
task-minutes                   4.9       2.9  -2.0 (-41%)
agents                           3         4  +1 (+33%)
cost split: agents $0.81, rework $0.00, coordinator n/a, total $0.81
concurrency: peak 2 at once (projected 3); critical path actual T3; projected T1 (1.9 min)
model mix: sonnet 3 tasks $0.81
quality: tests 4 passed, 0 failed; first-time pass n/a; rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet      1.6     0.8  -0.8 (-47%)     $0.219
T1    sonnet      1.9     1.2  -0.7 (-38%)     $0.370
T3    sonnet      1.4     0.8  -0.5 (-38%)     $0.219

takeaway: ran 12% faster than projected; cost 234% over; biggest miss T2
