# superlite build report

projection: fixed forecast saved at lint 2026-11-19T19:56:44

                         Projected    Actual  Delta
wall-clock (min)               6.7       1.7  -5.0 (-75%)
agent cost (USD, +rework)      0.11      0.25  +0.15 (+139%)
task-minutes                   6.7       1.7  -5.0 (-75%)
agents                           1         3  +2 (+200%)
cost split: agents $0.25, rework $0.00, coordinator n/a, total $0.25
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (6.7 min)
model mix: sonnet 1 tasks $0.25
quality: tests 13148 passed, 0 failed; first-time pass 1/1 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      6.7     1.7  -5.0 (-75%)     $0.253

takeaway: ran 75% faster than projected; cost 139% over; biggest miss T1
