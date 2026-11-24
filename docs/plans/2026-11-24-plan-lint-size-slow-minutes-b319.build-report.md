# superlite build report

projection: fixed forecast saved at lint 2026-11-24T14:58:43

                         Projected    Actual  Delta
wall-clock (min)               6.8       0.9  -5.9 (-87%)
agent cost (USD, +rework)      0.10      0.19  +0.09 (+85%)
task-minutes                   6.8       0.9  -5.9 (-87%)
agents                           1         3  +2 (+200%)
cost split: agents $0.19, rework $0.00, coordinator n/a, total $0.19
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (6.8 min)
model mix: sonnet 1 tasks $0.19
quality: tests 14084 passed, 0 failed; first-time pass 1/1 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      6.8     0.9  -5.9 (-87%)     $0.193

takeaway: ran 87% faster than projected; cost 85% over; biggest miss T1
