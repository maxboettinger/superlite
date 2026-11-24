# superlite build report

projection: fixed forecast saved at lint 2026-11-24T08:24:12

                         Projected    Actual  Delta
wall-clock (min)               3.3       1.2  -2.1 (-63%)
agent cost (USD, +rework)      0.12      0.25  +0.13 (+107%)
task-minutes                   3.3       1.2  -2.1 (-63%)
agents                           1         3  +2 (+200%)
cost split: agents $0.25, rework $0.00, coordinator n/a, total $0.25
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (3.3 min)
model mix: sonnet 1 tasks $0.25
quality: tests 13686 passed, 0 failed; first-time pass 1/1 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      3.3     1.2  -2.1 (-63%)     $0.249

takeaway: ran 63% faster than projected; cost 107% over; biggest miss T1
