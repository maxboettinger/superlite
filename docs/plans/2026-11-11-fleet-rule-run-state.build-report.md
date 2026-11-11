# superlite build report

projection: fixed forecast saved at lint 2026-11-11T13:24:30 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               1.6       1.4  -0.2 (-13%)
agent cost (USD, +rework)      0.24      0.50  +0.26 (+107%)
task-minutes                   4.9       2.0  -2.8 (-58%)
agents                           3         6  +3 (+100%)
cost split: agents $0.50, rework $0.00, coordinator n/a, total $0.50
concurrency: peak 2 at once (projected 3); critical path actual T3; projected T2 (1.6 min)
model mix: sonnet 3 tasks $0.50
quality: tests 6307 passed, 0 failed; first-time pass n/a; rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T3    sonnet      1.6     0.5  -1.1 (-70%)     $0.109
T1    sonnet      1.6     0.6  -1.0 (-65%)     $0.138
T2    sonnet      1.6     1.0  -0.7 (-41%)     $0.248

takeaway: ran 13% faster than projected; cost 107% over; biggest miss T3
