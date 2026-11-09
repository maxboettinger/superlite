# superlite build report

projection: fixed forecast saved at lint 2026-11-09T17:16:45

                         Projected    Actual  Delta
wall-clock (min)               4.1      10.3  +6.1 (+148%)
agent cost (USD, +rework)      0.68      1.90  +1.22 (+180%)
task-minutes                   5.8      11.6  +5.8 (+101%)
agents                           4         7  +3 (+75%)
cost split: agents $1.90, rework $0.00, coordinator n/a, total $1.90
concurrency: peak 2 at once (projected 2); critical path actual T1 T2 T3; projected T1 > T2 > T3 (4.1 min)
model mix: sonnet 4 tasks $1.90
quality: tests 4899 passed, 0 failed; first-time pass 1/1 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T3    sonnet      1.3     3.4  +2.2 (+170%)    $0.493
T1    sonnet      1.2     3.2  +2.0 (+167%)    $0.408
T2    sonnet      1.7     2.9  +1.2 (+73%)     $0.490
T4    sonnet      1.7     2.1  +0.5 (+28%)     $0.508

takeaway: ran 148% slower than projected; cost 180% over; biggest miss T3
