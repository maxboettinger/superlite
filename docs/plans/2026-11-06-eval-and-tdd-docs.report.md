# superlite build report

projection: fixed forecast saved at lint 2026-11-06T09:23:53

                         Projected    Actual  Delta
wall-clock (min)               2.3      28.2  +25.9 (+1122%)
agent cost (USD, +rework)      0.19      1.26  +1.06 (+556%)
task-minutes                   7.9       1.8  -6.1 (-78%)
agents                           4         7  +3 (+75%)
cost split: agents $0.49, rework $0.77, coordinator n/a, total $1.26
concurrency: peak 3 at once (projected 4); critical path actual T4; projected T3 (2.3 min)
model mix: sonnet 4 tasks $1.26
quality: tests 4 passed, 0 failed; first-time pass n/a; rework dispatches 4; open incidents 0

task  model      pred  actual  delta             cost
T4    sonnet      2.0     0.3  -1.6 (-83%)     $0.682
T3    sonnet      2.3     0.8  -1.5 (-66%)     $0.398
T1    sonnet      1.9     0.3  -1.5 (-82%)     $0.088
T2    sonnet      1.8     0.3  -1.5 (-81%)     $0.088

takeaway: ran 1122% slower than projected; cost 556% over; biggest miss T4
