# superlite build report

projection: fixed forecast saved at lint 2026-11-11T10:41:16

                         Projected    Actual  Delta
wall-clock (min)               2.3      40.0  +37.7 (+1666%)
agent cost (USD, +rework)      0.28      1.05  +0.77 (+270%)
task-minutes                   3.9       5.2  +1.3 (+33%)
agents                           2         6  +4 (+200%)
cost split: agents $0.89, rework $0.16, coordinator n/a, total $1.05
concurrency: peak 2 at once (projected 2); critical path actual T1; projected T1 (2.3 min)
model mix: sonnet 2 tasks $1.05
quality: tests 6145 passed, 0 failed; first-time pass n/a; rework dispatches 2; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet      1.6     2.5  +0.9 (+53%)     $0.397
T1    sonnet      2.3     2.7  +0.4 (+19%)     $0.651

takeaway: ran 1666% slower than projected; cost 270% over; biggest miss T2
