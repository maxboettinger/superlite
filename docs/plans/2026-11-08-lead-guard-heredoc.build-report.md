# superlite build report

projection: fixed forecast saved at lint 2026-11-08T01:08:02

                         Projected    Actual  Delta
wall-clock (min)               1.7      20.0  +18.2 (+1043%)
agent cost (USD, +rework)      0.19      1.28  +1.09 (+559%)
task-minutes                   1.7       2.1  +0.4 (+22%)
agents                           1         8  +7 (+700%)
cost split: agents $0.52, rework $0.76, coordinator n/a, total $1.28
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (1.7 min)
model mix: sonnet 1 tasks $1.28
quality: tests 4 passed, 0 failed; first-time pass n/a; rework dispatches 3; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      1.7     2.1  +0.4 (+22%)     $1.279

takeaway: ran 1043% slower than projected; cost 559% over; biggest miss T1
