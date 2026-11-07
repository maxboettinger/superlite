# superlite build report

projection: fixed forecast saved at lint 2026-11-07T17:09:47

                         Projected    Actual  Delta
wall-clock (min)               1.8      66.4  +64.5 (+3527%)
agent cost (USD, +rework)      0.19      2.41  +2.22 (+1158%)
task-minutes                   1.8       7.2  +5.4 (+296%)
agents                           1        12  +11 (+1100%)
cost split: agents $0.90, rework $1.52, coordinator n/a, total $2.41
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (1.8 min)
model mix: sonnet 1 tasks $2.41
quality: tests 4152 passed, 0 failed; first-time pass n/a; rework dispatches 5; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      1.8     7.2  +5.4 (+296%)    $2.410

takeaway: ran 3527% slower than projected; cost 1158% over; biggest miss T1
