# superlite build report

projection: fixed forecast saved at lint 2026-11-13T05:40:16

                         Projected    Actual  Delta
wall-clock (min)               6.2       1.0  -5.3 (-84%)
agent cost (USD, +rework)      0.15      0.26  +0.11 (+78%)
task-minutes                   6.2       1.0  -5.3 (-84%)
agents                           1         5  +4 (+400%)
cost split: agents $0.26, rework $0.00, coordinator n/a, total $0.26
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (6.2 min)
model mix: sonnet 1 tasks $0.26
quality: tests 8977 passed, 0 failed; first-time pass 1/1 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      6.2     1.0  -5.3 (-84%)     $0.262

takeaway: ran 84% faster than projected; cost 78% over; biggest miss T1
