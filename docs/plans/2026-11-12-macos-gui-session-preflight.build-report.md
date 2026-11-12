# superlite build report

projection: fixed forecast saved at lint 2026-11-12T16:39:21

                         Projected    Actual  Delta
wall-clock (min)               8.9       3.8  -5.1 (-58%)
agent cost (USD, +rework)      0.40      0.73  +0.33 (+82%)
task-minutes                  12.1       4.3  -7.8 (-64%)
agents                           3         6  +3 (+100%)
cost split: agents $0.73, rework $0.00, coordinator n/a, total $0.73
concurrency: peak 2 at once (projected 2); critical path actual T1 T3; projected T2 > T3 (8.9 min)
model mix: sonnet 3 tasks $0.73
quality: tests 7648 passed, 0 failed; first-time pass 2/3 (66%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet      4.1     1.0  -3.1 (-75%)     $0.160
T3    sonnet      4.8     2.2  -2.6 (-55%)     $0.362
T1    sonnet      3.2     1.2  -2.1 (-64%)     $0.210  first-time miss

takeaway: ran 58% faster than projected; cost 82% over; biggest miss T2
