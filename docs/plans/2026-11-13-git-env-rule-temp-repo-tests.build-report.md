# superlite build report

projection: fixed forecast saved at lint 2026-11-13T09:15:13 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               5.9       0.3  -5.5 (-94%)
agent cost (USD, +rework)      0.00      0.09  +0.09 (+2469%)
task-minutes                   5.9       0.3  -5.5 (-94%)
agents                           1         3  +2 (+200%)
cost split: agents $0.09, rework $0.00, coordinator n/a, total $0.09
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (5.9 min)
model mix: sonnet 1 tasks $0.09
quality: tests 9479 passed, 0 failed; first-time pass 1/1 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      5.9     0.3  -5.5 (-94%)     $0.090

takeaway: ran 94% faster than projected; cost 2469% over; biggest miss T1
