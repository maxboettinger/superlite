# superlite build report

projection: fixed forecast saved at lint 2026-11-13T02:14:28

                         Projected    Actual  Delta
wall-clock (min)               9.1      14.9  +5.8 (+64%)
agent cost (USD, +rework)      0.38      1.43  +1.05 (+274%)
task-minutes                  19.6       4.1  -15.5 (-79%)
agents                           5        17  +12 (+240%)
cost split: agents $1.04, rework $0.39, coordinator n/a, total $1.43
concurrency: peak 3 at once (projected 4); critical path actual T3; projected T1 > T2 (9.1 min)
model mix: sonnet 5 tasks $1.43
quality: tests 8555 passed, 0 failed; first-time pass 2/5 (40%); rework dispatches 3; open incidents 1

task  model      pred  actual  delta             cost
T2    sonnet      4.5     0.9  -3.6 (-81%)     $0.325  first-time miss
T5    sonnet      3.8     0.6  -3.2 (-84%)     $0.180
T1    sonnet      4.6     1.4  -3.2 (-69%)     $0.474  first-time miss
T4    sonnet      3.7     0.6  -3.1 (-83%)     $0.143
T3    sonnet      3.0     0.6  -2.4 (-79%)     $0.306  first-time miss

takeaway: ran 64% slower than projected; cost 274% over; biggest miss T2
