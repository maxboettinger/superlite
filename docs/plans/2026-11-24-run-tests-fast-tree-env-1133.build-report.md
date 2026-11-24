# superlite build report

projection: fixed forecast saved at lint 2026-11-24T16:39:57

                         Projected    Actual  Delta
wall-clock (min)               6.3       0.9  -5.4 (-85%)
agent cost (USD, +rework)      0.14      0.18  +0.04 (+30%)
task-minutes                   6.3       0.9  -5.4 (-85%)
agents                           1         4  +3 (+300%)
cost split: agents $0.18, rework $0.00, coordinator n/a, total $0.18
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (6.3 min)
model mix: sonnet 1 tasks $0.18
quality: tests 14235 passed, 0 failed; first-time pass 1/1 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      6.3     0.9  -5.4 (-85%)     $0.185

takeaway: ran 85% faster than projected; cost 30% over; biggest miss T1
