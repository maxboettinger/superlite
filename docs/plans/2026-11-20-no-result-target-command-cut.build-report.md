# superlite build report

projection: fixed forecast saved at lint 2026-11-20T14:43:27 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               7.6       0.5  -7.1 (-94%)
agent cost (USD, +rework)      0.05      0.12  +0.07 (+142%)
task-minutes                   7.6       0.5  -7.1 (-94%)
agents                           1         3  +2 (+200%)
cost split: agents $0.12, rework $0.00, coordinator n/a, total $0.12
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (7.6 min)
model mix: sonnet 1 tasks $0.12
quality: tests 13436 passed, 0 failed; first-time pass 1/1 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      7.6     0.5  -7.1 (-94%)     $0.123

takeaway: ran 94% faster than projected; cost 142% over; biggest miss T1
