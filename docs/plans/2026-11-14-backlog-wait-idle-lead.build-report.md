# superlite build report

projection: fixed forecast saved at lint 2026-11-14T23:20:12

                         Projected    Actual  Delta
wall-clock (min)              12.9       1.0  -11.9 (-92%)
agent cost (USD, +rework)      0.16      0.40  +0.24 (+154%)
task-minutes                  24.9       1.4  -23.5 (-94%)
agents                           2         7  +5 (+250%)
cost split: agents $0.40, rework $0.00, coordinator n/a, total $0.40
concurrency: peak 2 at once (projected 2); critical path actual T2; projected T2 (12.9 min)
model mix: sonnet 2 tasks $0.40
quality: tests 9957 passed, 0 failed; first-time pass 1/2 (50%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet     12.9     1.0  -11.9 (-92%)    $0.279
T1    sonnet     12.0     0.4  -11.6 (-97%)    $0.118  first-time miss

takeaway: ran 92% faster than projected; cost 154% over; biggest miss T2
