# superlite build report

projection: fixed forecast saved at lint 2026-11-11T16:38:35

                         Projected    Actual  Delta
wall-clock (min)               1.6      90.8  +89.2 (+5486%)
agent cost (USD, +rework)      0.15      0.64  +0.49 (+338%)
task-minutes                   1.6       2.2  +0.6 (+37%)
agents                           1         5  +4 (+400%)
cost split: agents $0.38, rework $0.26, coordinator n/a, total $0.64
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (1.6 min)
model mix: sonnet 1 tasks $0.64
quality: tests 6466 passed, 0 failed; first-time pass 0/1 (0%); rework dispatches 2; open incidents 1

task  model      pred  actual  delta             cost
T1    sonnet      1.6     2.2  +0.6 (+37%)     $0.639  first-time miss

takeaway: ran 5486% slower than projected; cost 338% over; biggest miss T1
