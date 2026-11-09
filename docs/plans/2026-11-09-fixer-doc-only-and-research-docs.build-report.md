# superlite build report

projection: fixed forecast saved at lint 2026-11-09T10:53:55

                         Projected    Actual  Delta
wall-clock (min)               1.3       0.5  -0.8 (-62%)
agent cost (USD, +rework)      0.01      0.40  +0.39 (+4935%)
task-minutes                   2.2       0.8  -1.4 (-64%)
agents                           2         4  +2 (+100%)
cost split: agents $0.40, rework $0.00, coordinator n/a, total $0.40
concurrency: peak 2 at once (projected 2); critical path actual T2; projected T1 (1.3 min)
model mix: sonnet 2 tasks $0.40
quality: tests 4 passed, 0 failed; first-time pass n/a; rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      1.3     0.5  -0.8 (-64%)     $0.198
T2    sonnet      1.0     0.3  -0.6 (-65%)     $0.200

takeaway: ran 62% faster than projected; cost 4935% over; biggest miss T1
