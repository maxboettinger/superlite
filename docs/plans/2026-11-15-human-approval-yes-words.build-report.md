# superlite build report

projection: fixed forecast saved at lint 2026-11-15T10:50:25 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               4.7       1.9  -2.8 (-59%)
agent cost (USD, +rework)      0.11      0.15  +0.04 (+41%)
task-minutes                   4.7       1.9  -2.8 (-59%)
agents                           1         3  +2 (+200%)
cost split: agents $0.15, rework $0.00, coordinator n/a, total $0.15
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (4.7 min)
model mix: sonnet 1 tasks $0.15
quality: tests 10965 passed, 0 failed; first-time pass 1/1 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      4.7     1.9  -2.8 (-59%)     $0.153

takeaway: ran 59% faster than projected; cost 41% over; biggest miss T1
