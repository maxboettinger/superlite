# superlite build report

projection: fixed forecast saved at lint 2026-11-11T15:41:11

                         Projected    Actual  Delta
wall-clock (min)               1.7      17.6  +15.9 (+965%)
agent cost (USD, +rework)      0.21      0.55  +0.33 (+158%)
task-minutes                   3.2       4.5  +1.3 (+39%)
agents                           2         5  +3 (+150%)
cost split: agents $0.47, rework $0.08, coordinator n/a, total $0.55
concurrency: peak 2 at once (projected 2); critical path actual T1; projected T1 (1.7 min)
model mix: sonnet 2 tasks $0.55
quality: tests 6427 passed, 0 failed; first-time pass n/a; rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet      1.6     2.6  +1.0 (+62%)     $0.118
T1    sonnet      1.7     1.9  +0.3 (+17%)     $0.427

takeaway: ran 965% slower than projected; cost 158% over; biggest miss T2
