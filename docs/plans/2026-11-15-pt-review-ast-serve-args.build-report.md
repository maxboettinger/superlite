# superlite build report

projection: fixed forecast saved at lint 2026-11-15T00:04:53

                         Projected    Actual  Delta
wall-clock (min)               6.4       1.5  -4.9 (-76%)
agent cost (USD, +rework)      0.16      0.21  +0.05 (+33%)
task-minutes                   6.4       1.5  -4.9 (-76%)
agents                           1         3  +2 (+200%)
cost split: agents $0.21, rework $0.00, coordinator n/a, total $0.21
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (6.4 min)
model mix: sonnet 1 tasks $0.21
quality: tests 10084 passed, 0 failed; first-time pass 1/1 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      6.4     1.5  -4.9 (-76%)     $0.212

takeaway: ran 76% faster than projected; cost 33% over; biggest miss T1
