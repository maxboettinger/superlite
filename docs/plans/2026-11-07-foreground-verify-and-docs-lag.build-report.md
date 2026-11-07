# superlite build report

projection: fixed forecast saved at lint 2026-11-07T17:31:59

                         Projected    Actual  Delta
wall-clock (min)               1.4       1.1  -0.2 (-17%)
agent cost (USD, +rework)      0.01      0.54  +0.53 (+5529%)
task-minutes                   2.5       1.6  -0.9 (-37%)
agents                           2         3  +1 (+50%)
cost split: agents $0.54, rework $0.00, coordinator n/a, total $0.54
concurrency: peak 2 at once (projected 2); critical path actual T2; projected T2 (1.4 min)
model mix: sonnet 2 tasks $0.54
quality: tests 4123 passed, 0 failed; first-time pass n/a; rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      1.1     0.4  -0.7 (-62%)     $0.204
T2    sonnet      1.4     1.1  -0.2 (-17%)     $0.335

takeaway: ran 17% faster than projected; cost 5529% over; biggest miss T1
