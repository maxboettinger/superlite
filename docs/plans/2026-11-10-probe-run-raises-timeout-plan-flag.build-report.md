# superlite build report

projection: fixed forecast saved at lint 2026-11-10T10:13:10

                         Projected    Actual  Delta
wall-clock (min)               3.7       5.9  +2.2 (+61%)
agent cost (USD, +rework)      0.42      1.10  +0.69 (+164%)
task-minutes                   3.7       5.5  +1.8 (+48%)
agents                           2         4  +2 (+100%)
cost split: agents $1.10, rework $0.00, coordinator n/a, total $1.10
concurrency: peak 1 at once (projected 1); critical path actual T1 T2; projected T1 > T2 (3.7 min)
model mix: sonnet 2 tasks $1.10
quality: tests 4 passed, 0 failed; first-time pass n/a; rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      1.9     3.2  +1.3 (+67%)     $0.609
T2    sonnet      1.8     2.3  +0.5 (+28%)     $0.495

takeaway: ran 61% slower than projected; cost 164% over; biggest miss T1
