# superlite build report

projection: fixed forecast saved at lint 2026-11-16T17:04:50 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               6.4       0.5  -5.8 (-92%)
agent cost (USD, +rework)      0.10      0.14  +0.04 (+44%)
task-minutes                   6.4       0.5  -5.8 (-92%)
agents                           1         3  +2 (+200%)
cost split: agents $0.14, rework $0.00, coordinator n/a, total $0.14
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (6.4 min)
model mix: sonnet 1 tasks $0.14
quality: tests 11821 passed, 0 failed; first-time pass 1/1 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      6.4     0.5  -5.8 (-92%)     $0.145

takeaway: ran 92% faster than projected; cost 44% over; biggest miss T1
