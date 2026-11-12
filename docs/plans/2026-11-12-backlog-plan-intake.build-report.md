# superlite build report

projection: fixed forecast saved at lint 2026-11-12T00:03:27

                         Projected    Actual  Delta
wall-clock (min)               5.6      44.9  +39.3 (+698%)
agent cost (USD, +rework)      0.80      2.75  +1.95 (+245%)
task-minutes                   8.9       8.1  -0.8 (-9%)
agents                           5        10  +5 (+100%)
cost split: agents $1.55, rework $1.20, coordinator n/a, total $2.75
concurrency: peak 3 at once (projected 3); critical path actual T2 T4 T5; projected T2 > T4 > T5 (5.6 min)
model mix: sonnet 5 tasks $2.75
quality: tests 6625 passed, 0 failed; first-time pass 1/5 (20%); rework dispatches 3; open incidents 0

task  model      pred  actual  delta             cost
T5    sonnet      1.6     3.1  +1.5 (+92%)     $1.535  first-time miss
T2    sonnet      2.4     1.3  -1.1 (-46%)     $0.335  first-time miss
T3    sonnet      1.6     0.9  -0.7 (-42%)     $0.187  first-time miss
T1    sonnet      1.6     0.9  -0.7 (-41%)     $0.187
T4    sonnet      1.6     1.8  +0.2 (+10%)     $0.506  first-time miss

takeaway: ran 698% slower than projected; cost 245% over; biggest miss T5
