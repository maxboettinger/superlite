# superlite build report

projection: fixed forecast saved at lint 2026-11-13T02:58:19

                         Projected    Actual  Delta
wall-clock (min)              10.3      12.1  +1.8 (+17%)
agent cost (USD, +rework)      0.41      1.20  +0.79 (+192%)
task-minutes                  14.1       4.5  -9.6 (-68%)
agents                           4        10  +6 (+150%)
cost split: agents $1.06, rework $0.14, coordinator n/a, total $1.20
concurrency: peak 2 at once (projected 2); critical path actual T1 T2 T4; projected T1 > T2 > T4 (10.3 min)
model mix: sonnet 4 tasks $1.20
quality: tests 8701 passed, 0 failed; first-time pass 3/4 (75%); rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T3    sonnet      3.8     0.6  -3.2 (-84%)     $0.156
T1    sonnet      3.1     0.8  -2.4 (-75%)     $0.234
T4    sonnet      3.0     0.8  -2.2 (-74%)     $0.323  first-time miss
T2    sonnet      4.2     2.3  -1.8 (-44%)     $0.489

takeaway: ran 17% slower than projected; cost 192% over; biggest miss T3
