# superlite build report

projection: fixed forecast saved at lint 2026-11-23T08:35:28

                         Projected    Actual  Delta
wall-clock (min)               9.2       0.5  -8.7 (-94%)
agent cost (USD, +rework)      0.08      0.15  +0.08 (+98%)
task-minutes                   9.2       0.5  -8.7 (-94%)
agents                           1         5  +4 (+400%)
cost split: agents $0.15, rework $0.00, coordinator n/a, total $0.15
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (9.2 min)
model mix: sonnet 1 tasks $0.15
quality: tests 13568 passed, 0 failed; first-time pass 1/1 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      9.2     0.5  -8.7 (-94%)     $0.155

takeaway: ran 94% faster than projected; cost 98% over; biggest miss T1
